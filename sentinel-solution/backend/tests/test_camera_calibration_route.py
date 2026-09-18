"""POST /cameras/{id}/calibration (2026-09-18) — see routes_cameras.py's
set_camera_calibration and analytics/calibration.py."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.auth import Principal
from app.api.routes_cameras import (
    CalibrationPointIn,
    CalibrationSubmit,
    get_camera,
    set_camera_calibration,
)
from app.db.models import CameraAuditLog, CameraRegistry

VALID_POINTS = [
    CalibrationPointIn(image_x=0, image_y=0, world_x=0, world_y=0),
    CalibrationPointIn(image_x=100, image_y=0, world_x=1, world_y=0),
    CalibrationPointIn(image_x=100, image_y=100, world_x=1, world_y=1),
    CalibrationPointIn(image_x=0, image_y=100, world_x=0, world_y=1),
]


def test_calibration_set_stores_matrix_and_records_audit(session):
    admin = Principal("admin1", "admin", None)
    session.add(CameraRegistry(id="cam_cal"))
    session.commit()

    result = set_camera_calibration(
        "cam_cal",
        CalibrationSubmit(points=VALID_POINTS, reference_note="IRC 086:2018 3.5m lane width, manual survey"),
        session,
        admin,
    )

    assert result["homography_calibrated"] is True
    assert result["homography_reference_note"].startswith("IRC 086:2018")

    row = session.get(CameraRegistry, "cam_cal")
    assert row.homography_json is not None
    assert row.homography_calibrated_at is not None

    audit = session.query(CameraAuditLog).filter_by(camera_id="cam_cal").all()
    assert audit[0].action == "calibration_set"
    assert audit[0].user_id == "admin1"


def test_calibration_reflected_in_camera_detail_view(session):
    admin = Principal("admin1", "admin", None)
    session.add(CameraRegistry(id="cam_cal2"))
    session.commit()

    set_camera_calibration(
        "cam_cal2",
        CalibrationSubmit(points=VALID_POINTS, reference_note="survey 2026-09-18"),
        session,
        admin,
    )

    detail = get_camera("cam_cal2", db=session, principal=admin)
    assert detail["homography_calibrated"] is True
    assert detail["homography_calibrated_at"] is not None
    assert detail["homography_reference_note"] == "survey 2026-09-18"


def test_calibration_requires_existing_camera(session):
    admin = Principal("admin1", "admin", None)
    with pytest.raises(HTTPException) as exc_info:
        set_camera_calibration(
            "cam_never_onboarded",
            CalibrationSubmit(points=VALID_POINTS, reference_note="survey"),
            session,
            admin,
        )
    assert exc_info.value.status_code == 404


def test_calibration_rejects_fewer_than_minimum_points():
    with pytest.raises(ValueError):
        CalibrationSubmit(points=VALID_POINTS[:3], reference_note="survey")


def test_calibration_rejects_missing_reference_note():
    with pytest.raises(ValueError):
        CalibrationSubmit(points=VALID_POINTS, reference_note="")


def test_calibration_rejects_degenerate_points(session):
    admin = Principal("admin1", "admin", None)
    session.add(CameraRegistry(id="cam_cal3"))
    session.commit()

    collinear = [
        CalibrationPointIn(image_x=x, image_y=0, world_x=x / 10.0, world_y=0) for x in (0, 10, 20, 30)
    ]
    with pytest.raises(HTTPException) as exc_info:
        set_camera_calibration(
            "cam_cal3",
            CalibrationSubmit(points=collinear, reference_note="survey"),
            session,
            admin,
        )
    assert exc_info.value.status_code == 400
