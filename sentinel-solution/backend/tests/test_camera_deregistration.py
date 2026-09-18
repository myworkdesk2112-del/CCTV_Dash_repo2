"""Camera deregister/re-register (2026-09-18) — see routes_cameras.py's
deregister_camera/reregister_camera. Soft-flag only, mirroring
under_maintenance's pattern: never deletes the CameraRegistry row (real
VehicleEvent/Alert evidence rows may already reference this camera_id —
CLAUDE.md's evidence-preservation stance forbids dropping that)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.auth import Principal
from app.api.routes_cameras import (
    CameraOnboard,
    DeregisterRequest,
    _compute_gap_analysis,
    camera_audit_log,
    catalogue,
    deregister_camera,
    get_camera,
    list_cameras,
    onboard_camera,
    reregister_camera,
)
from app.db.models import CameraRegistry


def test_deregister_sets_flag_and_records_audit(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_decom", department="Police"), session, admin)

    result = deregister_camera("cam_decom", DeregisterRequest(reason="returned to vendor"), session, admin)

    assert result["deregistered"] is True
    assert result["deregistered_reason"] == "returned to vendor"
    assert result["deregistered_at"] is not None

    row = session.get(CameraRegistry, "cam_decom")
    assert row.deregistered is True
    assert row.deregistered_reason == "returned to vendor"

    audit = camera_audit_log("cam_decom", db=session, _admin=admin)
    assert audit[0]["action"] == "deregistered"


def test_deregistered_camera_is_not_deleted_and_stays_queryable(session):
    """The camera must remain a real CameraRegistry row — this is a status
    flag, not a delete — so its id, audit trail, and any historical
    evidence referencing it stay intact and queryable."""
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_decom2", department="Police"), session, admin)
    deregister_camera("cam_decom2", DeregisterRequest(reason="decommissioned"), session, admin)

    detail = get_camera("cam_decom2", db=session, principal=admin)
    assert detail["deregistered"] is True
    assert detail["onboarded"] is True  # still a real registry row

    rows = list_cameras(db=session, principal=admin)
    assert any(r["id"] == "cam_decom2" for r in rows)


def test_register_reverses_deregister_and_records_audit(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_back", department="Police"), session, admin)
    deregister_camera("cam_back", DeregisterRequest(reason="temporary pull"), session, admin)

    result = reregister_camera("cam_back", session, admin)

    assert result["deregistered"] is False
    row = session.get(CameraRegistry, "cam_back")
    assert row.deregistered is False
    assert row.deregistered_reason is None
    assert row.deregistered_at is None

    audit = camera_audit_log("cam_back", db=session, _admin=admin)
    assert audit[0]["action"] == "re_registered"


def test_register_is_idempotent_on_an_already_active_camera(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_active", department="Police"), session, admin)

    result = reregister_camera("cam_active", session, admin)

    assert result["deregistered"] is False


def test_deregister_requires_existing_camera(session):
    admin = Principal("admin1", "admin", None)
    with pytest.raises(HTTPException) as exc_info:
        deregister_camera("cam_never_onboarded", DeregisterRequest(), session, admin)
    assert exc_info.value.status_code == 404


def test_register_requires_existing_camera(session):
    admin = Principal("admin1", "admin", None)
    with pytest.raises(HTTPException) as exc_info:
        reregister_camera("cam_never_onboarded", session, admin)
    assert exc_info.value.status_code == 404


def test_deregistered_camera_excluded_from_unhealthy_and_ageing_gap_lists(session):
    """Same reasoning as under_maintenance: a decommissioned camera is
    neither an unexpected failure nor an ageing-infrastructure risk to
    flag — it's intentionally out of service."""
    import datetime as dt

    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(
        CameraOnboard(id="cam_old_decom", department="Police", install_date=dt.datetime(2015, 1, 1)),
        session, admin,
    )
    session.get(CameraRegistry, "cam_old_decom").is_healthy = False
    session.commit()

    deregister_camera("cam_old_decom", DeregisterRequest(reason="decommissioned"), session, admin)

    report = _compute_gap_analysis(session, admin)
    assert report["unhealthy"] == []
    assert report["ageing"] == []
    assert report["deregistered"] == ["cam_old_decom"]


def test_list_cameras_deregistered_filter(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_active2", department="Police"), session, admin)
    onboard_camera(CameraOnboard(id="cam_gone", department="Police"), session, admin)
    deregister_camera("cam_gone", DeregisterRequest(), session, admin)

    # Default: both still visible (no breaking change to the existing
    # response shape for callers that don't pass the new filter).
    all_rows = list_cameras(db=session, principal=admin)
    assert {r["id"] for r in all_rows} == {"cam_active2", "cam_gone"}

    active_only = list_cameras(deregistered=False, db=session, principal=admin)
    assert [r["id"] for r in active_only] == ["cam_active2"]

    deregistered_only = list_cameras(deregistered=True, db=session, principal=admin)
    assert [r["id"] for r in deregistered_only] == ["cam_gone"]
