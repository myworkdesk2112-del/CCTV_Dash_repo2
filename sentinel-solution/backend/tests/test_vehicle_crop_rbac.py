"""Regression coverage for GET /vehicle/event/{event_id}/crop's department
scoping (api/routes_vehicle.py's vehicle_event_crop).

Real bug found 2026-09-13 while verifying an RBAC fix end-to-end: an earlier
version of this endpoint gated VIEWING on `evidence_class.is_exportable()`,
which meant any non-CONFIRMED sighting's crop 404'd even for its own
department. Checked against the live sentinel.db: 12,274 of 12,280 saved
crops (99.95%) are non-CONFIRMED, so that version broke evidence viewing for
nearly every sighting in the app. Viewing must NOT be gated on evidence
class — only an actual export/download action should be (enforced
separately, in the frontend, via `exportable_as_evidence`). Department
scoping (added in the same fix) is correct and stays: a viewer outside the
owning department gets 404; an investigator outside it is allowed through
but the access is audited.
"""
from __future__ import annotations

from app.analytics import evidence_class as evclass
from app.api.auth import Principal
from app.api.routes_vehicle import vehicle_event_crop
from app.db.models import AuditLog, CameraRegistry, VehicleEvent, VehicleIdentity
from fastapi import HTTPException
from fastapi.responses import FileResponse
import pytest


def _seed_lead_only_event(session, tmp_path, department="Police"):
    camera = CameraRegistry(id="cam01", department=department)
    identity = VehicleIdentity(plate=None)
    session.add(camera)
    session.add(identity)
    session.commit()

    crop_path = str(tmp_path / "crop.jpg")
    with open(crop_path, "wb") as f:
        f.write(b"fake-jpeg-bytes")

    event = VehicleEvent(
        identity_id=identity.id,
        camera_id=camera.id,
        pts_ms=0.0,
        plate=None,
        link_method="appearance_match",  # LEAD_ONLY, not exportable
        crop_path=crop_path,
    )
    session.add(event)
    session.commit()
    assert evclass.classify(event.plate, event.link_method) == evclass.LEAD_ONLY
    return event


def test_lead_only_crop_is_viewable_by_own_department_investigator(session, tmp_path):
    event = _seed_lead_only_event(session, tmp_path, department="Police")
    investigator = Principal("i1", "investigator", "Police")

    result = vehicle_event_crop(event.id, db=session, principal=investigator)

    assert isinstance(result, FileResponse)


def test_lead_only_crop_is_viewable_with_no_department_scope(session, tmp_path):
    """Unscoped (department=None) investigator keys remain unrestricted,
    matching department_scope's documented contract. Viewers are refused
    at the role gate — see test_security_review_20260926.py."""
    event = _seed_lead_only_event(session, tmp_path, department="Police")
    investigator = Principal("i1", "investigator", None)

    result = vehicle_event_crop(event.id, db=session, principal=investigator)

    assert isinstance(result, FileResponse)


def test_cross_department_investigator_without_purpose_is_refused(session, tmp_path):
    event = _seed_lead_only_event(session, tmp_path, department="Police")
    outside_investigator = Principal("i2", "investigator", "Health")

    with pytest.raises(HTTPException) as exc_info:
        vehicle_event_crop(event.id, db=session, principal=outside_investigator)
    assert exc_info.value.status_code == 400
    assert session.query(AuditLog).count() == 0


def test_cross_department_investigator_is_allowed_and_audited(session, tmp_path):
    event = _seed_lead_only_event(session, tmp_path, department="Police")
    outside_investigator = Principal("i2", "investigator", "Health")

    result = vehicle_event_crop(
        event.id, purpose="cross_dept_lead_check", case_id="C-1",
        db=session, principal=outside_investigator,
    )

    assert isinstance(result, FileResponse)
    rows = session.query(AuditLog).filter_by(user_id="i2").all()
    assert len(rows) == 1
    assert "cross-department access" in rows[0].query
    assert rows[0].purpose == "cross_dept_lead_check"


def test_own_department_investigator_is_not_audited(session, tmp_path):
    event = _seed_lead_only_event(session, tmp_path, department="Police")
    own_investigator = Principal("i1", "investigator", "Police")

    vehicle_event_crop(event.id, db=session, principal=own_investigator)

    assert session.query(AuditLog).filter_by(user_id="i1").count() == 0
