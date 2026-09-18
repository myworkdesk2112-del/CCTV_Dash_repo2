"""Per-camera homography calibration for real-world speed.

`VehicleEvent.speed_px_per_s` (see db/models.py's docstring) is an honest
image-plane metric — it was never meant to answer "how fast, in km/h, was
this vehicle actually going." That requires a mapping from image pixels to
ground-plane metres, which requires someone to have actually surveyed the
camera's view: at least 4 (image_x, image_y) <-> (world_x, world_y) point
correspondences on the road plane. `cv2.findHomography()` (already a
project dependency) fits the 3x3 perspective-transform matrix from those
points.

This module is deliberately narrow: it only turns *already-collected*
survey points into a stored matrix, and applies that matrix to a track's
bbox centres to get a real speed. It never invents calibration points for a
camera nobody has surveyed — `CameraRegistry.homography_json` stays NULL
(and `speed_kmh` stays None) until an admin actually submits real points via
POST /cameras/{id}/calibration.

IRC 086:2018 (Indian Roads Congress, geometric design of urban roads) is
used as the demo/reference calibration aid where a lane-width proxy is
needed: 3.5m is its standard single-lane carriageway width, a real
India-specific reference distance rather than an invented one.
"""
from __future__ import annotations

import json
import math
from typing import List, NamedTuple, Optional, Sequence, Tuple

MIN_CALIBRATION_POINTS = 4


class CalibrationPoint(NamedTuple):
    image_x: float
    image_y: float
    world_x: float  # metres, arbitrary local ground-plane origin
    world_y: float  # metres


def compute_homography_json(points: Sequence[CalibrationPoint]) -> str:
    """Fits a 3x3 image-plane -> world-plane (metres) homography from real
    surveyed point correspondences and returns it JSON-encoded for storage
    on `CameraRegistry.homography_json`. Raises ValueError for too few
    points or a degenerate (e.g. collinear) point set — better to fail loud
    at calibration time than silently store a useless matrix that produces
    garbage speeds later."""
    if len(points) < MIN_CALIBRATION_POINTS:
        raise ValueError(
            f"at least {MIN_CALIBRATION_POINTS} calibration points are required, got {len(points)}"
        )

    import cv2
    import numpy as np

    image_pts = np.array([[p.image_x, p.image_y] for p in points], dtype=np.float64)
    world_pts = np.array([[p.world_x, p.world_y] for p in points], dtype=np.float64)
    matrix, _mask = cv2.findHomography(image_pts, world_pts, method=0)
    if matrix is None:
        raise ValueError("could not fit a homography from these points — check for duplicate/collinear points")
    return json.dumps(matrix.tolist())


def _apply_homography(matrix: Sequence[Sequence[float]], x: float, y: float) -> Tuple[float, float]:
    """Projects one image-plane point through the (already row-major 3x3)
    homography matrix into world-plane metres."""
    m = matrix
    denom = m[2][0] * x + m[2][1] * y + m[2][2]
    if denom == 0:
        raise ValueError("degenerate homography: zero denominator for this point")
    wx = (m[0][0] * x + m[0][1] * y + m[0][2]) / denom
    wy = (m[1][0] * x + m[1][1] * y + m[1][2]) / denom
    return wx, wy


def calibrated_speed_kmh(
    homography_json: Optional[str],
    first_bbox: Optional[Tuple[float, float, float, float]],
    last_bbox: Optional[Tuple[float, float, float, float]],
    dwell_ms: float,
) -> Optional[float]:
    """Real-world speed in km/h between a track's first and last bbox,
    using this camera's stored homography — the calibrated counterpart to
    Track.motion_attributes()'s image-plane speed_px_per_s. Returns None
    (never a fabricated number) when the camera has no calibration, the
    track has no measurable displacement, or the matrix can't be applied to
    these points — same "uncalibrated cameras report nothing new" gate as
    the STRATEGY.md-mandated honesty stance on this metric.
    """
    if homography_json is None or first_bbox is None or last_bbox is None or dwell_ms <= 0:
        return None
    try:
        matrix = json.loads(homography_json)
        fx = (first_bbox[0] + first_bbox[2]) / 2.0
        fy = (first_bbox[1] + first_bbox[3]) / 2.0
        lx = (last_bbox[0] + last_bbox[2]) / 2.0
        ly = (last_bbox[1] + last_bbox[3]) / 2.0
        wfx, wfy = _apply_homography(matrix, fx, fy)
        wlx, wly = _apply_homography(matrix, lx, ly)
        distance_km = math.hypot(wlx - wfx, wly - wfy) / 1000.0
        hours = (dwell_ms / 1000.0) / 3600.0
        return round(distance_km / hours, 1) if hours > 0 else None
    except Exception:  # noqa: BLE001 — a bad/corrupted matrix must degrade, not crash the pipeline
        return None
