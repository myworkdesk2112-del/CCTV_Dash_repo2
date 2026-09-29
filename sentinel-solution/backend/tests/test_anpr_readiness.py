"""Camera ANPR-suitability scoring and the /cameras/anpr-readiness view.

The behaviour worth protecting here is not the arithmetic — it is the
epistemics: a heuristic plate region may rule ANPR out but never rule it
in, and a camera that is demonstrably reading plates may not be talked out
of it by a geometric estimate.
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi import HTTPException

from app.analytics import anpr_suitability as fitness
from app.analytics.anpr_suitability import anpr_suitability_by_camera
from app.analytics.attributes import VehicleAttributes
from app.analytics.pipeline import AnalyticsPipeline
from app.analytics.plate_detector import StubPlateDetector
from app.analytics.tracker import CameraTracker, Track
from app.api.auth import Principal
from app.api.routes_cameras import anpr_readiness
from app.db.models import CameraRegistry, VehicleEvent, VehicleIdentity


def _events(session, camera_id, *, count, reads, region_w=None, region_h=None,
            localiser="StubPlateDetector", attempts_each=0, reads_each=0):
    """`reads` sightings carry a validated plate; the rest carry none."""
    for n in range(count):
        identity = VehicleIdentity()
        session.add(identity)
        session.flush()
        session.add(VehicleEvent(
            identity_id=identity.id,
            camera_id=camera_id,
            pts_ms=float(n),
            plate=f"GJ01AB{1000 + n}" if n < reads else None,
            plate_region_w_px=region_w,
            plate_region_h_px=region_h,
            plate_localiser=localiser if region_w is not None else None,
            plate_ocr_attempts=attempts_each or None,
            plate_ocr_reads=reads_each or None,
        ))
    session.commit()


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def test_upper_bound_region_below_vendor_floor_proves_the_camera_unsuitable(session):
    """cam01's real finding: plates localised, none ever read, and the
    region they were read from is far below the vendor floor. The point of
    recording geometry is that this stops being 'our OCR is bad'."""
    session.add(CameraRegistry(id="cam01"))
    _events(session, "cam01", count=8, reads=0, region_w=25.0, region_h=16.0)

    score = anpr_suitability_by_camera(session, ["cam01"])["cam01"]
    assert score["classification"] == "UNSUITABLE"
    assert score["geometry_verdict"] == "UNSUITABLE"
    assert score["geometry_basis"] == "upper_bound_region"
    assert "even as an upper bound" in score["geometry_reason"]
    # The remediation must name the physical fix, not a model fix.
    assert "zoom" in score["recommendation"].lower()


def test_wide_upper_bound_region_is_inconclusive_and_never_promotes_to_capable(session):
    """A heuristic region is a bound on the plate, not the plate. A generous
    bound therefore cannot establish capability — the honest verdict is
    INCONCLUSIVE, and the camera stays at whatever its real reads support."""
    session.add(CameraRegistry(id="cam_wide"))
    _events(session, "cam_wide", count=10, reads=2, region_w=400.0, region_h=120.0)

    score = anpr_suitability_by_camera(session, ["cam_wide"])["cam_wide"]
    assert score["geometry_verdict"] == "INCONCLUSIVE"
    assert score["classification"] == "MARGINAL"  # from the 20% read rate, not the geometry
    assert score["read_rate_verdict"] == "MARGINAL"


def test_model_localised_plate_at_threshold_supports_capable_geometry(session):
    session.add(CameraRegistry(id="cam_yolo"))
    _events(session, "cam_yolo", count=10, reads=9, region_w=150.0, region_h=34.0,
            localiser="YoloPlateDetector")

    score = anpr_suitability_by_camera(session, ["cam_yolo"])["cam_yolo"]
    assert score["geometry_basis"] == "model_localised_plate"
    assert score["geometry_verdict"] == "CAPABLE"
    assert score["classification"] == "CAPABLE"
    assert "plate_localised_width" in score["measured_factors"]


def test_geometry_below_floor_drags_a_marginal_read_rate_down(session):
    session.add(CameraRegistry(id="cam_mixed"))
    _events(session, "cam_mixed", count=10, reads=2, region_w=60.0, region_h=20.0)

    score = anpr_suitability_by_camera(session, ["cam_mixed"])["cam_mixed"]
    assert score["read_rate_verdict"] == "MARGINAL"
    assert score["geometry_verdict"] == "UNSUITABLE"
    assert score["classification"] == "UNSUITABLE"  # worst of the two


def test_a_proven_read_rate_is_never_overridden_by_a_geometric_estimate(session):
    """Observation beats inference. If the camera is actually producing
    validated plates at an acceptable rate, an estimate that says it cannot
    be is the thing that is wrong — and the disagreement is surfaced, not
    silently resolved in either direction."""
    session.add(CameraRegistry(id="cam_reads"))
    _events(session, "cam_reads", count=10, reads=9, region_w=30.0, region_h=12.0)

    score = anpr_suitability_by_camera(session, ["cam_reads"])["cam_reads"]
    assert score["classification"] == "CAPABLE"
    assert score["geometry_verdict"] == "UNSUITABLE"
    assert score["measures_disagree"] is True


def test_mixed_localiser_history_is_treated_as_bounded(session):
    """If half a camera's history came from the heuristic region, the
    combined mean can only claim the weaker basis."""
    session.add(CameraRegistry(id="cam_swap"))
    _events(session, "cam_swap", count=5, reads=1, region_w=400.0, region_h=100.0,
            localiser="StubPlateDetector")
    _events(session, "cam_swap", count=5, reads=1, region_w=400.0, region_h=100.0,
            localiser="YoloPlateDetector")

    score = anpr_suitability_by_camera(session, ["cam_swap"])["cam_swap"]
    assert score["geometry_basis"] == "mixed_upper_bound_region"
    assert score["geometry_verdict"] == "INCONCLUSIVE"
    assert score["classification"] != "CAPABLE"


def test_no_geometry_recorded_reports_plate_pixel_width_as_unmeasured(session):
    """Rows written before this feature existed carry no geometry. That must
    read as 'not measured', never as 'measured and fine'."""
    session.add(CameraRegistry(id="cam_legacy"))
    _events(session, "cam_legacy", count=6, reads=5)

    score = anpr_suitability_by_camera(session, ["cam_legacy"])["cam_legacy"]
    assert score["geometry_verdict"] is None
    assert score["geometry_samples"] == 0
    assert "plate_pixel_width" in score["unmeasured_factors"]
    assert score["classification"] == "CAPABLE"  # on read history alone


def test_frame_level_ocr_yield_is_reported_separately_from_sighting_reads(session):
    """One sighting collapses many frame attempts into a single consensus
    plate, so a per-sighting read rate cannot show how often OCR actually
    fired and failed. Both numbers are kept."""
    session.add(CameraRegistry(id="cam_yield"))
    _events(session, "cam_yield", count=5, reads=5, region_w=200.0, region_h=50.0,
            attempts_each=10, reads_each=3)

    score = anpr_suitability_by_camera(session, ["cam_yield"])["cam_yield"]
    assert score["ocr_success_rate"] == 1.0          # every sighting reached consensus
    assert score["frame_ocr_attempts"] == 50
    assert score["frame_ocr_reads"] == 15
    assert score["frame_ocr_yield"] == pytest.approx(0.3)


def test_thresholds_carry_their_provenance():
    t = fitness.thresholds()
    assert t["plate_width_capable_px"] == 120.0
    assert "VENDOR CLAIM" in t["plate_width_source"]
    assert "PROJECT-CHOSEN" in t["read_rate_source"]


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------

def test_readiness_endpoint_is_department_scoped_and_excludes_deregistered(session):
    session.add_all([
        CameraRegistry(id="police_a", department="Police"),
        CameraRegistry(id="police_dead", department="Police", deregistered=True),
        CameraRegistry(id="transport_a", department="Transport"),
    ])
    _events(session, "police_a", count=6, reads=0, region_w=25.0, region_h=16.0)
    _events(session, "police_dead", count=6, reads=0, region_w=25.0, region_h=16.0)
    _events(session, "transport_a", count=6, reads=6, region_w=200.0, region_h=50.0)

    police = Principal("police-investigator", "investigator", "Police")
    result = anpr_readiness(db=session, principal=police)

    assert [row["camera_id"] for row in result["cameras"]] == ["police_a"]
    assert result["summary"]["UNSUITABLE"] == 1
    assert result["thresholds"]["plate_width_floor_px"] == 100.0
    assert "not measured by this deployment" in result["method"]

    admin = Principal("admin", "admin", None)
    everything = anpr_readiness(db=session, principal=admin)
    assert {row["camera_id"] for row in everything["cameras"]} == {"police_a", "transport_a"}
    assert everything["summary"] == {"CAPABLE": 1, "MARGINAL": 0, "UNSUITABLE": 1}

    only_bad = anpr_readiness(classification="unsuitable", db=session, principal=admin)
    assert [row["camera_id"] for row in only_bad["cameras"]] == ["police_a"]


def test_readiness_endpoint_counts_insufficient_sample_apart_from_marginal(session):
    """'We have not measured this yet' must not be presented as 'we measured
    it and it was mediocre'."""
    session.add(CameraRegistry(id="cam_new", department="Police"))
    _events(session, "cam_new", count=2, reads=2)

    result = anpr_readiness(db=session, principal=Principal("a", "admin", None))
    assert result["summary"]["MARGINAL"] == 1
    assert result["insufficient_sample"] == 1


def test_readiness_endpoint_requires_investigator(session):
    from app.api.auth import require_role

    with pytest.raises(HTTPException) as exc:
        require_role("investigator")(Principal("v", "viewer", None))
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------
# Measurement plumbing
# --------------------------------------------------------------------------

def _attrs():
    return VehicleAttributes(vehicle_type="car", color="white", color_confidence=0.9,
                             width_px=100, height_px=80, aspect_ratio=1.25)


def test_track_records_region_geometry_and_attempt_counts_only_when_localised():
    track = Track(track_id=1, bbox=(0, 0, 10, 10), last_pts_ms=0, first_pts_ms=0, vehicle_type="car")
    track.add_observation((0, 0, 10, 10), 0, 0.9, _attrs(), ("GJ01AB1234", 0.9), plate_region=(120.0, 30.0))
    track.add_observation((0, 0, 10, 10), 100, 0.9, _attrs(), None, plate_region=(100.0, 20.0))
    # Localisation failed on this frame: it contributes NO measurement at
    # all, rather than a zero that would drag the median down.
    track.add_observation((0, 0, 10, 10), 200, 0.9, _attrs(), None, plate_region=None)

    assert track.plate_ocr_attempts == 2
    assert track.plate_ocr_reads == 1
    assert track.plate_region_median() == (110.0, 25.0)


def test_track_with_no_localisation_at_all_reports_no_geometry():
    track = Track(track_id=1, bbox=(0, 0, 10, 10), last_pts_ms=0, first_pts_ms=0, vehicle_type="car")
    track.add_observation((0, 0, 10, 10), 0, 0.9, _attrs(), None)
    assert track.plate_region_median() == (None, None)
    assert track.plate_ocr_attempts == 0


def test_camera_tracker_threads_the_region_through_to_the_track():
    tracker = CameraTracker()
    tracker.update(bbox=(0, 0, 10, 10), pts_ms=0, vehicle_type="car", detection_confidence=0.9,
                   attrs=_attrs(), plate_result=None, plate_region=(80.0, 20.0))
    track = tracker.flush_all()[0]
    assert track.plate_regions == [(80.0, 20.0)]


def test_read_plate_measures_the_clipped_region_before_enhancement_upscaling():
    """enhance_plate_crop() upscales small crops. Those interpolated pixels
    are not plate detail, so counting them would inflate every camera's
    readiness — the measurement must be taken before that step."""
    pipeline = AnalyticsPipeline(
        detector_factory=lambda: None,
        plate_reader=type("R", (), {"read": staticmethod(lambda crop: None)})(),
        plate_detector=StubPlateDetector(),
    )
    vehicle_crop = np.zeros((100, 200, 3), dtype=np.uint8)
    _result, region = pipeline._read_plate(vehicle_crop)

    # StubPlateDetector takes x in [0.2w, 0.8w] and y in [0.55h, 0.95h].
    assert region == (120.0, 40.0)
    assert region[0] < 200  # not the whole vehicle crop
    # enhance_plate_crop would have upscaled a 120px-wide crop by 1x here,
    # but the contract is that the region is measured pre-enhancement.


def test_read_plate_reports_no_region_when_localisation_fails():
    """'No region found' must stay distinguishable from 'a zero-pixel
    region', or a camera that never localises anything would look like a
    camera measured at 0 px."""
    pipeline = AnalyticsPipeline(
        detector_factory=lambda: None,
        plate_reader=type("R", (), {"read": staticmethod(lambda crop: None)})(),
        plate_detector=StubPlateDetector(),
    )
    tiny = np.zeros((4, 4, 3), dtype=np.uint8)  # below StubPlateDetector's floor
    assert pipeline._read_plate(tiny) == (None, None)
