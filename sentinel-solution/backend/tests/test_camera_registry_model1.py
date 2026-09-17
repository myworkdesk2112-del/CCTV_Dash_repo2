"""Regression coverage for Model 1's remaining P3 deliverables (see
TASKS.md, closed 2026-09-10): ageing-infrastructure tracking
(install_date/coverage_radius_m), backend search/filter query params on
list_cameras, and the camera-onboarding audit trail."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi import HTTPException

from app.api.auth import Principal
from app.api.routes_cameras import (
    CameraOnboard,
    MaintenanceUpdate,
    _compute_gap_analysis,
    camera_audit_log,
    catalogue,
    list_cameras,
    onboard_camera,
    set_maintenance_status,
)
from app.db.models import CameraAuditLog, CameraRegistry


def test_onboard_sets_ageing_fields_and_records_audit_log(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    body = CameraOnboard(id="cam01", department="Police", install_date=dt.datetime(2018, 1, 1), coverage_radius_m=150.0)

    onboard_camera(body, session, admin)

    row = list_cameras(db=session, principal=admin)[0]
    assert row["install_date"].startswith("2018-01-01")
    assert row["coverage_radius_m"] == 150.0

    audit = camera_audit_log("cam01", db=session, _admin=admin)
    assert len(audit) == 1
    assert audit[0]["action"] == "onboarded"
    assert audit[0]["user_id"] == "admin1"

    # Re-onboarding the same camera is an update, not a second "onboarded".
    onboard_camera(body, session, admin)
    audit = camera_audit_log("cam01", db=session, _admin=admin)
    assert [a["action"] for a in audit] == ["updated", "onboarded"]


def test_gap_analysis_flags_ageing_and_missing_install_date(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    old = CameraOnboard(id="cam_old", department="Police", install_date=dt.datetime(2015, 1, 1))
    fresh = CameraOnboard(id="cam_new", department="Police", install_date=dt.datetime.utcnow())
    unknown = CameraOnboard(id="cam_unknown", department="Police")
    for body in (old, fresh, unknown):
        onboard_camera(body, session, admin)

    report = _compute_gap_analysis(session, admin)
    assert report["ageing"] == ["cam_old"]
    assert report["missing_install_date"] == ["cam_unknown"]


def test_list_cameras_filters_by_department_and_query(session):
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam01", department="Police", location_name="MG Road"), session, admin)
    onboard_camera(CameraOnboard(id="cam02", department="Health", location_name="Civil Hospital"), session, admin)

    police_only = list_cameras(department="Police", db=session, principal=admin)
    assert [r["id"] for r in police_only] == ["cam01"]

    hospital_search = list_cameras(q="hospital", db=session, principal=admin)
    assert [r["id"] for r in hospital_search] == ["cam02"]

    no_match = list_cameras(camera_type="ptz", db=session, principal=admin)
    assert no_match == []


def test_maintenance_status_excludes_camera_from_unhealthy_gap_list(session):
    """The named Model 1 gap this closes: an unhealthy-but-under-maintenance
    camera must not read as an unexpected failure in gap-analysis."""
    catalogue._cameras = {}
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_broken", department="Police"), session, admin)
    onboard_camera(CameraOnboard(id="cam_maint", department="Police"), session, admin)
    for cam_id in ("cam_broken", "cam_maint"):
        session.get(CameraRegistry, cam_id).is_healthy = False
    session.commit()

    set_maintenance_status(
        "cam_maint", MaintenanceUpdate(under_maintenance=True, reason="lens replacement"), session, admin
    )

    report = _compute_gap_analysis(session, admin)
    assert report["unhealthy"] == ["cam_broken"]
    assert report["under_maintenance"] == ["cam_maint"]

    row = list_cameras(db=session, principal=admin)
    maint_row = next(r for r in row if r["id"] == "cam_maint")
    assert maint_row["under_maintenance"] is True
    assert maint_row["maintenance_reason"] == "lens replacement"

    audit = camera_audit_log("cam_maint", db=session, _admin=admin)
    assert audit[0]["action"] == "maintenance_set"

    # Clearing maintenance drops the reason and moves the camera back to
    # being judged on its real health signal.
    set_maintenance_status("cam_maint", MaintenanceUpdate(under_maintenance=False), session, admin)
    report = _compute_gap_analysis(session, admin)
    assert report["under_maintenance"] == []
    assert sorted(report["unhealthy"]) == ["cam_broken", "cam_maint"]
    audit = camera_audit_log("cam_maint", db=session, _admin=admin)
    assert audit[0]["action"] == "maintenance_cleared"


def test_maintenance_status_requires_existing_camera(session):
    admin = Principal("admin1", "admin", None)
    with pytest.raises(HTTPException) as exc_info:
        set_maintenance_status(
            "cam_never_onboarded", MaintenanceUpdate(under_maintenance=True), session, admin
        )
    assert exc_info.value.status_code == 404
