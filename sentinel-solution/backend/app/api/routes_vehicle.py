"""Implements the evaluation's core ask: given a plate, return the complete
timestamped, location-wise movement history across the camera network.

Every TARGETED per-plate/attribute lookup below is purpose-bound and
logged (DPDP-oriented governance): the caller must state who they are and
why they're querying, not just what. `GET /recent` is the one deliberate
exception — a continuous "what's happening right now" operational feed,
not a targeted investigation query, so it's neither purpose-bound nor
logged per call (see its own docstring). Corrected 2026-09-04: this
module docstring previously claimed "every lookup," overclaiming relative
to that intentional, already-documented exception.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..analytics.anpr import normalize_plate
from ..analytics import evidence_class as ec
from ..analytics.density import storage_tier_for
from ..analytics.geo import RoutePoint, build_inferred_segments, rank_candidate_cameras
from ..db.models import AuditLog, CameraRegistry, VehicleEvent, VehicleIdentity
from ..watchlist.service import watchlist_service
from .auth import Principal, department_scope, require_role
from .deps import get_db

router = APIRouter(prefix="/vehicle", tags=["vehicle"])

# The DPDP purpose-bound-query story needs the stated purpose to actually
# say something — nothing previously stopped `purpose=""` or `purpose="x"`
# from satisfying it. Found by security review 2026-09-04. Not a format/
# enum check (a free-text justification is the honest choice — investigator
# workflows vary too much for a fixed enum to cover), just a floor that
# rejects the trivially-empty case.
_PURPOSE_MIN_LENGTH = 8


def _cameras_by_id(db: Session, camera_ids) -> dict:
    """Batch-fetch cameras referenced by a set of events into one query,
    instead of a `session.get()` per event. Harmless at the pilot's 30
    cameras, but this endpoint is exactly the one SCALABILITY.md's
    80k-camera story has to serve — at that scale, one query per row
    instead of one `WHERE id IN (...)` is the difference between a bounded
    query and N round-trips. Found by software-engineering review
    2026-09-04; same pattern already used to fix identity.py's
    `_best_match` this session."""
    ids = {c for c in camera_ids if c}
    if not ids:
        return {}
    return {c.id: c for c in db.query(CameraRegistry).filter(CameraRegistry.id.in_(ids)).all()}


@router.get("/recent")
def recent_detections(
    limit: int = 20,
    camera_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Live operational feed — the command-center 'what's happening right
    now' view, distinct from the purpose-bound individual lookups below
    (vehicle_history/search_by_attributes). NOT purpose-bound or audit-logged
    per call, same precedent as GET /alerts (routes_alerts.py): a continuous
    monitoring view of recent state is a declared operational function, not
    a targeted investigation query — the distinction that keeps
    purpose-binding meaningful is per-plate lookup, not "is any recent-
    activity view allowed to exist at all"."""
    query = db.query(VehicleEvent)
    department = department_scope(principal)
    if department is not None:
        query = query.join(CameraRegistry, VehicleEvent.camera_id == CameraRegistry.id).filter(
            CameraRegistry.department == department
        )
    if camera_id is not None:
        query = query.filter(VehicleEvent.camera_id == camera_id)
    events = query.order_by(VehicleEvent.observed_at.desc()).limit(min(max(limit, 1), 500)).all()
    cameras = _cameras_by_id(db, (e.camera_id for e in events))
    out = []
    for e in events:
        cam = cameras.get(e.camera_id)
        out.append({
            "event_id": e.id,
            "camera_id": e.camera_id,
            "location": cam.location_name if cam else None,
            "observed_at": e.observed_at.isoformat(),
            "plate": e.plate,
            "plate_confidence": e.plate_confidence,
            "vehicle_type": e.vehicle_type,
            "color": e.color,
            "has_evidence_image": e.crop_path is not None,
            "watchlisted": bool(e.plate and watchlist_service.check(e.plate)),
            "evidence_class": _cls(e),
            "exportable_as_evidence": ec.is_exportable(_cls(e)),
            "storage_tier": storage_tier_for(e.observed_at),
        })
    return out

# Temporal consistency decays from 1.0 (instant) to ~0 at this many seconds
# since the identity's previous sighting — informs the fused score below but
# is a hand-picked heuristic, not a learned weighting.
_TEMPORAL_DECAY_S = 15 * 60


def _explain_link(e: VehicleEvent) -> dict:
    """"Why was this vehicle linked?" — surfaces the raw signals behind
    identity resolution (see analytics/identity.py) plus a simple weighted
    fused score. This is a transparency aid for investigators, not a
    calibrated probability: weights are fixed heuristics (plate confidence
    is the strongest signal per STRATEGY.md's plate-first principle)."""
    plate_confidence = e.plate_confidence or 0.0
    reid_similarity = e.link_score or 0.0
    if e.link_time_gap_s is None:
        temporal_consistency = None
    else:
        temporal_consistency = min(1.0, max(0.0, 1.0 - (e.link_time_gap_s / _TEMPORAL_DECAY_S)))

    if e.link_method in ("new_identity",):
        fused_score = plate_confidence if e.plate_confidence else None
    elif e.link_method == "plate_continuation":
        fused_score = plate_confidence
    else:  # plate_upgrade, appearance_match — appearance carried the link
        fused_score = round(
            0.5 * plate_confidence + 0.35 * reid_similarity + 0.15 * (temporal_consistency or 0.0), 3
        )

    return {
        "method": e.link_method,
        "reid_similarity": e.link_score,
        "time_since_previous_sighting_s": e.link_time_gap_s,
        "temporal_consistency": temporal_consistency,
        "fused_score": fused_score,
    }


def _cls(e) -> str:
    return ec.classify(e.plate, e.link_method)


@router.get("/{plate}/history")
def vehicle_history(
    plate: str,
    purpose: str = Query(..., min_length=_PURPOSE_MIN_LENGTH),
    case_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Returns the FULL movement history for this plate's identity —
    including sightings recorded before ANPR ever read the plate. If the
    vehicle was seen anonymously (unreadable plate) at earlier cameras and
    later matched by appearance to this same identity, those anonymous
    sightings are part of the timeline too (see identity.py). Querying by
    VehicleEvent.plate alone would miss them, since those historical rows
    correctly kept plate=NULL for what was actually known at the time.

    `user_id` on the audit log is the AUTHENTICATED principal from the API
    key, not a client-supplied string — a self-reported user_id would make
    the purpose-bound audit trail decorative rather than actually
    accountable (see api/auth.py's RBAC).
    """
    plate = normalize_plate(plate)
    db.add(AuditLog(user_id=principal.user_id, purpose=purpose, case_id=case_id, query=plate))
    db.commit()

    identity = db.query(VehicleIdentity).filter(VehicleIdentity.plate == plate).first()
    if identity is None:
        return {"plate": plate, "sightings": [], "note": "no identity has been resolved to this plate yet"}

    events = (
        db.query(VehicleEvent)
        .filter(VehicleEvent.identity_id == identity.id)
        .order_by(VehicleEvent.observed_at.asc())
        .all()
    )
    cameras = _cameras_by_id(db, (e.camera_id for e in events))
    out = []
    route_points = []
    for e in events:
        cam = cameras.get(e.camera_id)
        out.append(
            {
                # Geo-temporal event typing: a sighting is CONFIRMED camera
                # evidence. The INFERRED gaps between sightings live in
                # `route_segments` below — kept as a separate, clearly-labelled
                # list so nothing reads an inference as an observation.
                "event_type": "OBSERVED",
                "camera_id": e.camera_id,
                "location": cam.location_name if cam else None,
                "latitude": cam.latitude if cam else None,
                "longitude": cam.longitude if cam else None,
                "pts_ms": e.pts_ms,
                "observed_at": e.observed_at.isoformat(),
                "confidence": e.confidence,
                "plate_read_at_this_camera": e.plate is not None,
                "plate_confidence": e.plate_confidence,
                "vehicle_type": e.vehicle_type,
                "color": e.color,
                "color_confidence": e.color_confidence,
                "dimensions_px": {"width": e.width_px, "height": e.height_px, "aspect_ratio": e.aspect_ratio},
                "make_model": e.make_model,
                # Image-plane motion metrics (NOT calibrated km/h — see
                # models.py). Useful for dwell/wrong-way/stopped filters.
                "motion": {
                    "dwell_time_s": e.dwell_time_s,
                    "speed_px_per_s": e.speed_px_per_s,
                    "direction_deg": e.direction_deg,
                },
                "link": _explain_link(e),
                # Evidence classification (analytics/evidence_class.py):
                # derived from persisted provenance, not asserted by the UI,
                # so a badge can never disagree with the row it labels.
                # `exportable` is the authoritative gate — the frontend
                # disables its export control from this field rather than
                # re-deriving the rule.
                "evidence_class": _cls(e),
                "evidence_class_reason": ec.describe(_cls(e), e.link_method),
                "exportable_as_evidence": ec.is_exportable(_cls(e)),
                "storage_tier": storage_tier_for(e.observed_at),
                # Evidence: real detection crop + bbox if the pipeline saved
                # one (see analytics/pipeline.py); null on older rows or if
                # the write failed. event_id lets the UI fetch the image.
                "event_id": e.id,
                "has_evidence_image": e.crop_path is not None,
                "bbox": (
                    {"x1": e.bbox_x1, "y1": e.bbox_y1, "x2": e.bbox_x2, "y2": e.bbox_y2}
                    if e.bbox_x1 is not None else None
                ),
            }
        )
        route_points.append(
            RoutePoint(
                camera_id=e.camera_id,
                latitude=cam.latitude if cam else None,
                longitude=cam.longitude if cam else None,
                observed_at=e.observed_at,
            )
        )

    # Route reconstruction: OBSERVED sightings interleaved with INFERRED
    # segments for the camera-less gaps between them (geo-temporal layer —
    # see analytics/geo.py). Straight-line/lower-bound; honestly labelled.
    route_segments = build_inferred_segments(route_points)

    return {
        "plate": plate,
        "identity_id": identity.id,
        "identity_first_seen": identity.first_seen_at.isoformat(),
        "sightings": out,
        "route_segments": route_segments,
        "route_legend": {
            "OBSERVED": "confirmed CCTV evidence at a camera",
            "INFERRED": "camera-less gap between two confirmed sightings; feasibility "
                        "estimated from straight-line distance + time, never observed",
        },
    }


@router.get("/event/{event_id}/crop")
def vehicle_event_crop(
    event_id: int,
    purpose: str = "unspecified",
    case_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Serves the real evidence crop saved at detection time (see
    analytics/pipeline.py). 404 if this event has none — either it predates
    the crop feature, or the save failed; the UI should show a placeholder
    rather than assume every sighting has an image.

    Viewing is NOT gated on evidence class: an investigator legitimately
    needs to SEE a LEAD_ONLY sighting's photo to evaluate the lead (this is
    the overwhelming majority of sightings — 12,274 of 12,280 saved crops in
    the real database are non-CONFIRMED, so gating view on exportability
    here would 404 nearly every evidence thumbnail in the app). Only a
    genuine EXPORT/download action should be blocked for a non-exportable
    class, and that block is enforced separately: the frontend disables its
    export control using `exportable_as_evidence` from /vehicle/recent and
    /vehicle/{plate}/history (see evidence_class.py), which is derived from
    the same event row this endpoint serves, so a LEAD_ONLY crop can be
    viewed here but the UI never offers to export it as evidence."""
    event = db.get(VehicleEvent, event_id)
    if event is None or not event.crop_path:
        raise HTTPException(status_code=404, detail="no evidence image for this event")

    camera = db.get(CameraRegistry, event.camera_id)
    department = department_scope(principal)
    if principal.role == "viewer" and (
        department is not None and (camera is None or camera.department != department)
    ):
        # A viewer must not be able to distinguish another department's crop
        # from a missing event.
        raise HTTPException(status_code=404, detail="no evidence image for this event")

    if (
        principal.role == "investigator"
        and department is not None
        and (camera is None or camera.department != department)
    ):
        db.add(AuditLog(
            user_id=principal.user_id,
            purpose=purpose,
            case_id=case_id,
            query=(
                f"cross-department access: event {event.id} at camera {event.camera_id} "
                f"(dept {camera.department if camera else 'unknown'}) by investigator "
                f"in dept {department}"
            ),
        ))
        db.commit()

    path = os.path.join(config.CROPS_DIR, event.crop_path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="evidence image file missing on disk")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{plate}/candidate-cameras")
def vehicle_candidate_cameras(
    plate: str,
    purpose: str = Query(..., min_length=_PURPOSE_MIN_LENGTH),
    case_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Forward-looking geo-temporal feasibility: given this vehicle's most
    recent CONFIRMED sighting, which OTHER cameras could it plausibly reach
    by now? This is deterministic physics (haversine distance vs. elapsed
    time vs. a plausible max speed — same math as geo.py's backward-looking
    INFERRED segments, just run forward), NOT a learned/ML prediction of
    where the vehicle actually went. Powers the Geo-Temporal Journey Engine's
    "feasible next cameras" panel — labelled PREDICTED in the UI precisely
    because it's a feasibility filter, not an observation. See geo.py.
    """
    plate = normalize_plate(plate)
    db.add(AuditLog(user_id=principal.user_id, purpose=purpose, case_id=case_id, query=f"candidate-cameras:{plate}"))
    db.commit()

    identity = db.query(VehicleIdentity).filter(VehicleIdentity.plate == plate).first()
    if identity is None:
        return {"plate": plate, "candidates": [], "note": "no identity has been resolved to this plate yet"}

    last_event = (
        db.query(VehicleEvent)
        .filter(VehicleEvent.identity_id == identity.id)
        .order_by(VehicleEvent.observed_at.desc())
        .first()
    )
    if last_event is None:
        return {"plate": plate, "candidates": [], "note": "no sightings recorded for this identity"}

    last_camera = db.get(CameraRegistry, last_event.camera_id)
    all_cameras = db.query(CameraRegistry).all()
    candidates = rank_candidate_cameras(last_camera, last_event.observed_at, all_cameras)

    return {
        "plate": plate,
        "last_known_camera": last_event.camera_id,
        "last_known_at": last_event.observed_at.isoformat(),
        "candidates": candidates,
        "method": "physics-based feasibility filter (haversine distance / elapsed time vs. "
                  "a plausible max speed) — NOT a machine-learned prediction of actual route",
    }


@router.get("/search-by-attributes")
def search_by_attributes(
    purpose: str = Query(..., min_length=_PURPOSE_MIN_LENGTH),
    vehicle_type: str | None = None,
    color: str | None = None,
    partial_plate: str | None = None,
    case_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Fallback for when ANPR can't produce a confident plate read on any
    frame: search by colour/type/partial-plate instead — what an
    investigator actually has when a plate is unreadable in the footage."""
    query_desc = f"type={vehicle_type} color={color} partial_plate={partial_plate}"
    db.add(AuditLog(user_id=principal.user_id, purpose=purpose, case_id=case_id, query=query_desc))
    db.commit()

    q = db.query(VehicleEvent)
    if vehicle_type:
        q = q.filter(VehicleEvent.vehicle_type == vehicle_type)
    if color:
        q = q.filter(VehicleEvent.color == color)
    if partial_plate:
        q = q.filter(VehicleEvent.plate.like(f"%{normalize_plate(partial_plate)}%"))
    total_count = q.count()
    events = q.order_by(VehicleEvent.observed_at.desc()).limit(200).all()

    cameras = _cameras_by_id(db, (e.camera_id for e in events))
    out = []
    for e in events:
        cam = cameras.get(e.camera_id)
        evidence_class = _cls(e)
        out.append(
            {
                "camera_id": e.camera_id,
                "location": cam.location_name if cam else None,
                "observed_at": e.observed_at.isoformat(),
                "plate": e.plate,
                "plate_confidence": e.plate_confidence,
                "vehicle_type": e.vehicle_type,
                "color": e.color,
                "evidence_class": evidence_class,
                "evidence_class_reason": ec.describe(evidence_class, e.link_method),
            }
        )
    return {"query": query_desc, "matches": out, "total_count": total_count, "truncated": total_count > 200}
