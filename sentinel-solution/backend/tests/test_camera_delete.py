"""Hard camera delete (2026-09-27) — see routes_cameras.py's
delete_camera. Distinct from deregister_camera (soft, reversible, never
drops the row): this actually removes the CameraRegistry row, but must
refuse whenever real evidence (VehicleEvent/Alert) references the camera
— SQLite's FK enforcement is off in this project (see db/session.py), so
this is the only thing standing between a registry cleanup and silently
orphaned evidence rows."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.auth import Principal
from app.api.routes_cameras import CameraOnboard, delete_camera, onboard_camera
from app.db.models import (
    Alert,
    CameraAuditLog,
    CameraDensityWindow,
    CameraRegistry,
    VehicleEvent,
    VehicleIdentity,
)


def test_delete_removes_a_clean_camera(session):
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_test", department="Police"), session, admin)

    result = delete_camera("cam_test", session, admin)

    assert result == {"id": "cam_test", "deleted": True}
    assert session.get(CameraRegistry, "cam_test") is None


def test_delete_also_removes_its_own_density_windows_and_audit_log(session):
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_test", department="Police"), session, admin)
    session.add(CameraDensityWindow(
        camera_id="cam_test", window_started_at=__import__("datetime").datetime(2026, 1, 1),
        window_seconds=60, sampled_frames=10, vehicle_detections=2, person_detections=1,
    ))
    session.commit()
    assert session.query(CameraAuditLog).filter_by(camera_id="cam_test").count() == 1

    delete_camera("cam_test", session, admin)

    assert session.query(CameraDensityWindow).filter_by(camera_id="cam_test").count() == 0
    assert session.query(CameraAuditLog).filter_by(camera_id="cam_test").count() == 0


def test_delete_refuses_a_camera_with_a_vehicle_event(session):
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_evidence", department="Police"), session, admin)
    identity = VehicleIdentity(plate="GJ01AB1234")
    session.add(identity)
    session.commit()
    session.add(VehicleEvent(identity_id=identity.id, camera_id="cam_evidence", pts_ms=0.0, plate="GJ01AB1234"))
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_camera("cam_evidence", session, admin)
    assert exc_info.value.status_code == 409
    # The row and its evidence must both survive the refused attempt.
    assert session.get(CameraRegistry, "cam_evidence") is not None
    assert session.query(VehicleEvent).filter_by(camera_id="cam_evidence").count() == 1


def test_delete_refuses_a_camera_with_an_alert(session):
    admin = Principal("admin1", "admin", None)
    onboard_camera(CameraOnboard(id="cam_alerted", department="Police"), session, admin)
    identity = VehicleIdentity(plate="GJ01AB1234")
    session.add(identity)
    session.commit()
    event = VehicleEvent(identity_id=identity.id, camera_id="cam_alerted", pts_ms=0.0, plate="GJ01AB1234")
    session.add(event)
    session.commit()
    session.add(Alert(plate="GJ01AB1234", camera_id="cam_alerted", reason="stolen",
                       vehicle_event_id=event.id, status="new"))
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_camera("cam_alerted", session, admin)
    assert exc_info.value.status_code == 409
    assert session.get(CameraRegistry, "cam_alerted") is not None


def test_delete_unknown_camera_is_404(session):
    admin = Principal("admin1", "admin", None)
    with pytest.raises(HTTPException) as exc_info:
        delete_camera("cam_never_existed", session, admin)
    assert exc_info.value.status_code == 404
