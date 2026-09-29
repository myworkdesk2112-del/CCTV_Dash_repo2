"""Regression coverage for Model 1's storage-details field, added
2026-09-27: the official spec text lists "location, department, camera
type, ownership, connectivity status, storage details" as onboarding
metadata, and storage had no field anywhere in the schema until now."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.auth import Principal
from app.api.routes_cameras import CameraOnboard, _compute_gap_analysis, get_camera, onboard_camera
from app.db.models import CameraRegistry


def test_onboard_persists_storage_details(session):
    admin = Principal("admin1", "admin", None)
    body = CameraOnboard(
        id="cam_store", department="Police",
        storage_medium="local NVR", storage_retention_days=15,
        storage_capacity_note="2TB, overwrites at capacity",
    )
    onboard_camera(body, session, admin)

    row = session.get(CameraRegistry, "cam_store")
    assert row.storage_medium == "local NVR"
    assert row.storage_retention_days == 15
    assert row.storage_capacity_note == "2TB, overwrites at capacity"

    view = get_camera("cam_store", db=session, principal=Principal("v1", "viewer", None))
    assert view["storage_medium"] == "local NVR"
    assert view["storage_retention_days"] == 15


def test_storage_details_default_to_none_and_are_never_fabricated():
    """No onboarding source (the real sandbox catalogue included) has
    storage information — must stay honestly NULL, never guessed."""
    body = CameraOnboard(id="cam_bare")
    assert body.storage_medium is None
    assert body.storage_retention_days is None
    assert body.storage_capacity_note is None


def test_negative_retention_days_is_rejected():
    with pytest.raises(ValidationError):
        CameraOnboard(id="cam_bad", storage_retention_days=-1)


def test_gap_analysis_flags_missing_storage_details(session):
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_no_storage", department="Police"), session, admin)
    onboard_camera(
        CameraOnboard(id="cam_with_storage", department="Police", storage_medium="cloud"),
        session, admin,
    )

    report = _compute_gap_analysis(session, admin)

    assert "cam_no_storage" in report["missing_storage_details"]
    assert "cam_with_storage" not in report["missing_storage_details"]


def test_camera_id_is_case_normalized_on_onboard(session):
    """A manual entry of 'CAM06' and a CSV row of 'cam06' must land on the
    same registry row, not silently fork into two cameras."""
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="CAM06", department="Police"), session, admin)
    onboard_camera(CameraOnboard(id="cam06", department="Health"), session, admin)

    assert session.query(CameraRegistry).filter(CameraRegistry.id.in_(["cam06", "CAM06"])).count() == 1
    row = session.get(CameraRegistry, "cam06")
    assert row is not None
    assert row.department == "Health"  # the second (update) call won
