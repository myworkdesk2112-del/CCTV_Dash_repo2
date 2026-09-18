"""Homography speed calibration (analytics/calibration.py, 2026-09-18).

Uses a simple, exactly-verifiable scene: a camera looking straight down at
a flat road so image pixels map to world metres by a uniform scale factor
(no perspective skew) — lets the expected world coordinates be computed by
hand instead of trusting cv2's own fit.
"""
from __future__ import annotations

import json

import pytest

from app.analytics.calibration import (
    MIN_CALIBRATION_POINTS,
    CalibrationPoint,
    calibrated_speed_kmh,
    compute_homography_json,
)

# 100 image pixels == 1 real-world metre — a square 0..100px image maps
# onto a 0..1m x 0..1m world square.
SCALE_PX_PER_M = 100.0
SQUARE_POINTS = [
    CalibrationPoint(0, 0, 0, 0),
    CalibrationPoint(SCALE_PX_PER_M, 0, 1, 0),
    CalibrationPoint(SCALE_PX_PER_M, SCALE_PX_PER_M, 1, 1),
    CalibrationPoint(0, SCALE_PX_PER_M, 0, 1),
]


def test_compute_homography_requires_minimum_points():
    with pytest.raises(ValueError, match=f"at least {MIN_CALIBRATION_POINTS}"):
        compute_homography_json(SQUARE_POINTS[:3])


def test_compute_homography_rejects_degenerate_collinear_points():
    collinear = [CalibrationPoint(x, 0, x / 10.0, 0) for x in (0, 10, 20, 30)]
    with pytest.raises(ValueError):
        compute_homography_json(collinear)


def test_calibrated_speed_matches_hand_computed_uniform_scale():
    homography_json = compute_homography_json(SQUARE_POINTS)

    # Vehicle moves 50px right over 2 seconds -> 0.5m in 2s -> 0.25 m/s -> 0.9 km/h.
    first_bbox = (0.0, 0.0, 10.0, 10.0)   # centre (5, 5)
    last_bbox = (50.0, 0.0, 60.0, 10.0)   # centre (55, 5)
    speed = calibrated_speed_kmh(homography_json, first_bbox, last_bbox, dwell_ms=2000.0)

    assert speed == pytest.approx(0.9, abs=0.01)


def test_calibrated_speed_is_none_without_a_homography():
    speed = calibrated_speed_kmh(None, (0, 0, 10, 10), (50, 0, 60, 10), dwell_ms=2000.0)
    assert speed is None


def test_calibrated_speed_is_none_for_zero_or_negative_dwell():
    homography_json = compute_homography_json(SQUARE_POINTS)
    assert calibrated_speed_kmh(homography_json, (0, 0, 10, 10), (50, 0, 60, 10), dwell_ms=0.0) is None
    assert calibrated_speed_kmh(homography_json, (0, 0, 10, 10), (50, 0, 60, 10), dwell_ms=-5.0) is None


def test_calibrated_speed_is_none_for_missing_bboxes():
    homography_json = compute_homography_json(SQUARE_POINTS)
    assert calibrated_speed_kmh(homography_json, None, (50, 0, 60, 10), dwell_ms=2000.0) is None
    assert calibrated_speed_kmh(homography_json, (0, 0, 10, 10), None, dwell_ms=2000.0) is None


def test_calibrated_speed_degrades_quietly_on_corrupted_matrix():
    """A corrupted/hand-edited homography_json must never crash the
    pipeline — a bad calibration should just mean no speed_kmh, not a
    finalize_tracks exception that drops the whole batch."""
    assert calibrated_speed_kmh("not valid json", (0, 0, 10, 10), (50, 0, 60, 10), dwell_ms=2000.0) is None
    degenerate_zero_matrix = json.dumps([[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    assert calibrated_speed_kmh(degenerate_zero_matrix, (0, 0, 10, 10), (50, 0, 60, 10), dwell_ms=2000.0) is None
