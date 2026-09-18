"""End-to-end wiring check for VehicleEvent.speed_kmh (2026-09-18):
AnalyticsPipeline._finalize_tracks must populate it only for a camera
that has actually been calibrated (CameraRegistry.homography_json set),
and must leave it None — never fabricated — for every other camera,
exactly like speed_px_per_s always has been.

Uses an isolated on-disk SQLite engine (not the shared `session` fixture,
which isn't wired into pipeline.py's own SessionLocal) via monkeypatch, the
same technique test_regressions_20260913.py already uses for db/session.py
internals.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analytics import pipeline as pipeline_module
from app.analytics.calibration import CalibrationPoint, compute_homography_json
from app.analytics.pipeline import AnalyticsPipeline
from app.analytics.tracker import Track
from app.db.models import Base, CameraRegistry, VehicleEvent


@pytest.fixture()
def isolated_pipeline(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline_test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(pipeline_module, "SessionLocal", test_session_local)
    pipeline = AnalyticsPipeline(detector_factory=lambda: None, plate_reader=None)
    return pipeline, test_session_local


def _moving_track(track_id: int) -> Track:
    # 50px right over 2000ms — same scenario as test_calibration.py's
    # hand-verified 0.9 km/h case.
    return Track(
        track_id=track_id,
        bbox=(50.0, 0.0, 60.0, 10.0),
        last_pts_ms=2000.0,
        first_pts_ms=0.0,
        vehicle_type="car",
        first_bbox=(0.0, 0.0, 10.0, 10.0),
    )


def test_speed_kmh_is_none_for_an_uncalibrated_camera(isolated_pipeline):
    pipeline, test_session_local = isolated_pipeline
    pipeline._finalize_tracks("cam_uncal", [_moving_track(1)])

    db = test_session_local()
    event = db.query(VehicleEvent).filter_by(camera_id="cam_uncal").one()
    assert event.speed_px_per_s is not None  # unaffected, still computed as before
    assert event.speed_kmh is None
    db.close()


def test_speed_kmh_is_populated_for_a_calibrated_camera(isolated_pipeline):
    pipeline, test_session_local = isolated_pipeline

    homography_json = compute_homography_json([
        CalibrationPoint(0, 0, 0, 0),
        CalibrationPoint(100, 0, 1, 0),
        CalibrationPoint(100, 100, 1, 1),
        CalibrationPoint(0, 100, 0, 1),
    ])
    db = test_session_local()
    db.add(CameraRegistry(id="cam_cal", homography_json=homography_json))
    db.commit()
    db.close()

    pipeline._finalize_tracks("cam_cal", [_moving_track(2)])

    db = test_session_local()
    event = db.query(VehicleEvent).filter_by(camera_id="cam_cal").one()
    assert event.speed_kmh == pytest.approx(0.9, abs=0.05)
    db.close()


def test_finalize_tracks_registers_a_brand_new_camera_before_reading_it_back(isolated_pipeline):
    """Regression guard: _finalize_tracks fetches CameraRegistry once,
    right after _ensure_camera_registered, to feed the homography lookup —
    that fetch must see a brand-new camera's own just-added row (requires
    an explicit flush; SessionLocal is autoflush=False), not silently
    treat it as unregistered for its very first batch."""
    pipeline, test_session_local = isolated_pipeline
    pipeline._finalize_tracks("cam_never_seen_before", [_moving_track(3)])

    db = test_session_local()
    assert db.get(CameraRegistry, "cam_never_seen_before") is not None
    event = db.query(VehicleEvent).filter_by(camera_id="cam_never_seen_before").one()
    assert event.speed_kmh is None  # never calibrated, so still honestly None
    db.close()
