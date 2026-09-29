"""Evidence-labelled camera ANPR suitability from real event history.

Answers a question camera *health* cannot: a camera can be perfectly
online, streaming and stable and still be geometrically incapable of
producing a plate read. Departments need that told apart from "the OCR is
bad", because the remediation is completely different — one is a camera
placement/optics job, the other is a model job.

Two independent measures, both from persisted real data, never guessed:

1. **Observed OCR yield** — what fraction of this camera's sightings
   actually carried a validated plate, plus the finer-grained frame-level
   attempt/read counts the pipeline records per track.
2. **Plate-region geometry** — the pixel width the plate localiser
   actually had to work with, against the convergent four-vendor
   requirement of >=120 px plate width (100-150 px preferred), recorded in
   DECISION_REVIEW_2026-09-11.md section H from Eocortex, Bosch, Axis and
   Plate Recognizer. That is a VENDOR CLAIM, not a measurement of this
   system, and is labelled as such in the API response.

The geometry measure carries a basis, because the two plate-localiser
seams support very different conclusions:

* ``StubPlateDetector`` returns a fixed lower-middle region of the vehicle
  crop. The real plate is a SUBSET of that region, so the measurement is
  an **upper bound**. An upper bound below the vendor floor is a genuine
  proof of incapability (if even the generous region is too small, the
  plate inside it certainly is). An upper bound ABOVE the threshold proves
  nothing at all, and is reported as ``INCONCLUSIVE`` rather than promoted
  to CAPABLE.
* A trained ``YoloPlateDetector`` returns the plate itself, so its
  measurement can support CAPABLE.

Blur, glare, illuminance, view angle, lens and distance are still not
measured anywhere in this deployment, and none is inferred here — they
stay in ``unmeasured_factors`` so a reader can see the limits of the score
rather than assume it is comprehensive.
"""
from __future__ import annotations

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..db.models import VehicleEvent

MINIMUM_SAMPLE_EVENTS = 5
CAPABLE_READ_RATE = 0.60

# Vendor-stated plate geometry requirements — see module docstring for
# provenance. VENDOR CLAIM, convergent across four independent vendors;
# not a threshold this project measured or calibrated itself.
PLATE_WIDTH_CAPABLE_PX = 120.0
PLATE_WIDTH_FLOOR_PX = 100.0

# Localiser class names whose output bounds the plate rather than being the
# plate. Matched by name (not isinstance) because this module scores
# persisted history: the row records the class name that ran at write time,
# and that class may not even be the one configured today.
_UPPER_BOUND_LOCALISERS = frozenset({"StubPlateDetector"})

CAPABLE = "CAPABLE"
MARGINAL = "MARGINAL"
UNSUITABLE = "UNSUITABLE"
INCONCLUSIVE = "INCONCLUSIVE"

# Worst-first, so min(candidates, key=_SEVERITY.index) picks the least
# favourable verdict when two measures disagree.
_SEVERITY = [UNSUITABLE, MARGINAL, CAPABLE]

# Factors nothing in this deployment measures. Character height is on this
# list deliberately even though plate-region HEIGHT is now recorded: the
# vendor threshold is stated against character height (>=20 px), and a
# plate region's height is not its character height (a two/three-line
# Indian plate carries the same characters at roughly half the per-line
# height). Reporting region height against a character-height threshold
# would conflate two different measurements, so the verdict below uses
# width only and the height is reported as context.
_NEVER_MEASURED = [
    "plate_character_height",
    "blur",
    "glare_or_low_light",
    "view_angle",
    "lens_or_focal_length",
    "camera_resolution",
    "distance_or_zoom_proxy",
]


def _geometry_verdict(width_px: float | None, basis: str) -> tuple[str | None, str | None]:
    """(verdict, reason) for the geometry measure alone, or (None, None).

    An upper-bound measurement can only ever prove a camera DOWN, never up
    — see the module docstring.
    """
    if width_px is None:
        return None, None
    bounded = "upper_bound_region" in basis
    if width_px < PLATE_WIDTH_FLOOR_PX:
        return UNSUITABLE, (
            f"Plate region measures {width_px:.0f} px wide, below the "
            f"{PLATE_WIDTH_FLOOR_PX:.0f} px vendor floor"
            + (" even as an upper bound" if bounded else "")
            + "."
        )
    if width_px < PLATE_WIDTH_CAPABLE_PX:
        return MARGINAL, (
            f"Plate region measures {width_px:.0f} px wide — above the "
            f"{PLATE_WIDTH_FLOOR_PX:.0f} px floor but below the "
            f"{PLATE_WIDTH_CAPABLE_PX:.0f} px vendor requirement."
        )
    if bounded:
        return INCONCLUSIVE, (
            f"Plate region measures {width_px:.0f} px wide, but that region is "
            "a heuristic bound on the plate, not the plate itself — it can "
            "rule capability out, never establish it."
        )
    return CAPABLE, (
        f"Model-localised plate measures {width_px:.0f} px wide, at or above "
        f"the {PLATE_WIDTH_CAPABLE_PX:.0f} px vendor requirement."
    )


def _read_verdict(events: int, reads: int, rate: float | None) -> tuple[str | None, str, str]:
    """(verdict, data_status, reason) for the observed-read measure."""
    if events < MINIMUM_SAMPLE_EVENTS:
        return None, "insufficient_sample", (
            f"Only {events} vehicle sighting(s) recorded — fewer than the "
            f"{MINIMUM_SAMPLE_EVENTS} needed before a read rate means anything."
        )
    if rate is not None and rate >= CAPABLE_READ_RATE:
        return CAPABLE, "measured", (
            f"{reads} of {events} sightings carried a validated plate "
            f"({rate:.0%}), at or above the {CAPABLE_READ_RATE:.0%} threshold."
        )
    if reads:
        return MARGINAL, "measured", (
            f"Only {reads} of {events} sightings carried a validated plate "
            f"({(rate or 0.0):.0%}), below the {CAPABLE_READ_RATE:.0%} threshold."
        )
    return UNSUITABLE, "measured", (
        f"None of {events} sightings produced a validated plate read."
    )


def _recommend(
    classification: str,
    geometry_verdict: str | None,
    read_verdict: str | None,
    basis: str | None,
) -> str:
    if classification == UNSUITABLE and geometry_verdict == UNSUITABLE:
        return (
            "Geometric finding, not an OCR failure: zoom in, move the camera "
            "closer to the traffic lane, fit a longer lens, or install a "
            "dedicated ANPR camera here. Re-measure after the change."
        )
    if classification == UNSUITABLE:
        return (
            "No plate has ever been read here. Check framing and view angle "
            "against passing plates, then collect another real sample before "
            "concluding the camera cannot be used for ANPR."
        )
    if classification == MARGINAL and geometry_verdict == MARGINAL:
        return (
            "Plate pixels are near the vendor floor. A modest zoom or re-angle "
            "should move this camera into the usable band; re-measure after."
        )
    if classification == MARGINAL and read_verdict == MARGINAL:
        return "Review framing and zoom, then collect another real sample after adjustment."
    if classification == MARGINAL:
        return (
            f"Collect at least {MINIMUM_SAMPLE_EVENTS} real vehicle events before "
            "changing camera placement or optics."
        )
    if basis and "upper_bound_region" in basis:
        return (
            "Reading plates at an acceptable rate. Plate-pixel geometry is only "
            "bounded, not measured — deploy a trained plate localiser to confirm "
            "the geometric margin."
        )
    return "Continue monitoring real plate-read rate; no placement change is indicated by available data."


def anpr_suitability_by_camera(db: Session, camera_ids: list[str]) -> dict[str, dict]:
    """Return real OCR-read history, plate geometry, and an explicitly
    limited recommendation, per camera.

    ``MARGINAL`` with ``insufficient_sample`` is intentionally not promoted
    to CAPABLE/UNSUITABLE until enough real detections exist to support that
    judgment.
    """
    if not camera_ids:
        return {}
    rows = (
        db.query(
            VehicleEvent.camera_id,
            func.count(VehicleEvent.id).label("events"),
            func.coalesce(func.sum(case((VehicleEvent.plate.is_not(None), 1), else_=0)), 0).label("reads"),
            # Mean of per-sighting MEDIAN region widths (tracker.py already
            # reduced each track's frames to a median before persisting), so
            # one vehicle that happened to pass directly under the camera
            # cannot drag a whole camera's score upward the way a max would.
            func.avg(VehicleEvent.plate_region_w_px).label("mean_w"),
            func.avg(VehicleEvent.plate_region_h_px).label("mean_h"),
            func.max(VehicleEvent.plate_region_w_px).label("max_w"),
            func.count(VehicleEvent.plate_region_w_px).label("geometry_samples"),
            func.coalesce(func.sum(VehicleEvent.plate_ocr_attempts), 0).label("ocr_attempts"),
            func.coalesce(func.sum(VehicleEvent.plate_ocr_reads), 0).label("ocr_reads"),
        )
        .filter(VehicleEvent.camera_id.in_(camera_ids))
        .group_by(VehicleEvent.camera_id)
        .all()
    )
    by_camera = {row.camera_id: row for row in rows}

    # Which localiser(s) produced this camera's geometry. Fetched as
    # distinct pairs rather than a string aggregate because SQLite spells
    # that group_concat and PostgreSQL spells it string_agg — this project's
    # migrations are written to stay portable across both (see
    # db/session.py), and a second small query costs nothing at the scale a
    # camera-list page actually asks for.
    localiser_rows = (
        db.query(VehicleEvent.camera_id, VehicleEvent.plate_localiser)
        .filter(
            VehicleEvent.camera_id.in_(camera_ids),
            VehicleEvent.plate_localiser.is_not(None),
        )
        .distinct()
        .all()
    )
    localisers: dict[str, set[str]] = {}
    for camera_id, localiser in localiser_rows:
        localisers.setdefault(camera_id, set()).add(localiser)

    result: dict[str, dict] = {}
    for camera_id in camera_ids:
        row = by_camera.get(camera_id)
        events = int(row.events) if row else 0
        reads = int(row.reads) if row else 0
        rate = (reads / events) if events else None
        geometry_samples = int(row.geometry_samples) if row else 0
        mean_w = float(row.mean_w) if row is not None and row.mean_w is not None else None
        mean_h = float(row.mean_h) if row is not None and row.mean_h is not None else None
        max_w = float(row.max_w) if row is not None and row.max_w is not None else None
        ocr_attempts = int(row.ocr_attempts) if row else 0
        ocr_reads = int(row.ocr_reads) if row else 0

        used = sorted(localisers.get(camera_id, set()))
        if not used:
            basis = None
        elif all(name in _UPPER_BOUND_LOCALISERS for name in used):
            basis = "upper_bound_region"
        elif any(name in _UPPER_BOUND_LOCALISERS for name in used):
            # Mixed history (the deployment swapped localisers partway).
            # Treat the whole aggregate as bounded: the weaker basis is the
            # only one the combined mean can honestly claim.
            basis = "mixed_upper_bound_region"
        else:
            basis = "model_localised_plate"

        geometry_verdict, geometry_reason = _geometry_verdict(mean_w, basis or "")
        read_verdict, data_status, read_reason = _read_verdict(events, reads, rate)

        # Observation beats inference (CLAUDE.md 4.3 / 24.6): if this camera
        # is demonstrably reading plates at an acceptable rate, that is
        # ground truth and geometry cannot override it. A geometric verdict
        # that disagrees with a proven read rate means the GEOMETRY estimate
        # is wrong for this camera (most likely the heuristic region is not
        # landing on the plate), not that the reads did not happen — so the
        # disagreement is surfaced rather than silently resolved either way.
        candidates = [v for v in (geometry_verdict, read_verdict) if v in _SEVERITY]
        if read_verdict == CAPABLE:
            classification = CAPABLE
        elif candidates:
            classification = min(candidates, key=_SEVERITY.index)
        else:
            classification = MARGINAL

        measured_factors = ["confirmed_plate_read_history"]
        unmeasured = list(_NEVER_MEASURED)
        if geometry_samples:
            measured_factors.append(
                "plate_region_upper_bound_width"
                if basis and "upper_bound_region" in basis
                else "plate_localised_width"
            )
        else:
            unmeasured.insert(0, "plate_pixel_width")

        result[camera_id] = {
            "classification": classification,
            "data_status": data_status,
            "sample_vehicle_events": events,
            "confirmed_plate_reads": reads,
            "ocr_success_rate": rate,
            "measured_factors": measured_factors,
            "unmeasured_factors": unmeasured,
            "recommendation": _recommend(classification, geometry_verdict, read_verdict, basis),
            # --- added with the ANPR Readiness view; older callers ignore ---
            "read_rate_verdict": read_verdict,
            "read_rate_reason": read_reason,
            "geometry_verdict": geometry_verdict,
            "geometry_reason": geometry_reason,
            "geometry_basis": basis,
            "geometry_samples": geometry_samples,
            "plate_region_mean_w_px": round(mean_w, 1) if mean_w is not None else None,
            "plate_region_mean_h_px": round(mean_h, 1) if mean_h is not None else None,
            "plate_region_max_w_px": round(max_w, 1) if max_w is not None else None,
            "plate_localisers": used,
            "frame_ocr_attempts": ocr_attempts,
            "frame_ocr_reads": ocr_reads,
            "frame_ocr_yield": (ocr_reads / ocr_attempts) if ocr_attempts else None,
            "measures_disagree": read_verdict == CAPABLE and geometry_verdict == UNSUITABLE,
        }
    return result


def thresholds() -> dict:
    """The stated thresholds and their provenance, for the API/UI to show
    next to a verdict — a classification with an unstated threshold is not
    an auditable finding."""
    return {
        "plate_width_capable_px": PLATE_WIDTH_CAPABLE_PX,
        "plate_width_floor_px": PLATE_WIDTH_FLOOR_PX,
        "read_rate_capable": CAPABLE_READ_RATE,
        "minimum_sample_events": MINIMUM_SAMPLE_EVENTS,
        "plate_width_source": (
            "VENDOR CLAIM — >=120 px plate width (100-150 px preferred) and "
            ">=20 px character height, convergent across Eocortex, Bosch, Axis "
            "and Plate Recognizer; recorded in "
            "docs/strategy/DECISION_REVIEW_2026-09-11.md section H. Not a "
            "threshold measured or calibrated by this project."
        ),
        "read_rate_source": (
            "PROJECT-CHOSEN — no external standard defines an acceptable "
            "per-camera plate-read rate; 60% is this project's own operational "
            "cut-off for 'this camera is producing usable ANPR'."
        ),
    }
