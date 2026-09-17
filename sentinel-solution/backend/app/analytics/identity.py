"""Cross-camera vehicle identity resolution.

This is the fix for "plate not readable -> tracking failed." Implements:

    Camera 1: plate ❌, white SUV, embedding e1
    Camera 2: plate ❌, white SUV, embedding e2  (~e1, similar) -> same identity
    Camera 3: plate ✅ GJ01AB1234, embedding e3  (~e1/e2, similar)
              -> identity upgraded to GJ01AB1234
              -> camera 1 and 2 sightings retroactively belong to this plate

We never claim a plate identity before it's actually observed — an
anonymous identity stays anonymous until ANPR succeeds on ANY of its
sightings; only then does the whole chain resolve to that plate. See
STRATEGY.md's "plate-first, appearance-second" principle: plate is the
strongest signal, appearance is what carries identity through the gaps.

GEO-FEASIBILITY GATE (added after running this against continuous live
sandbox traffic, not synthetic data): appearance-only matching used to be
pure cosine similarity against every identity in the time window, with no
check on whether the candidate's last-known camera was even physically
reachable. Under real, high-volume, multi-camera traffic, this let an
identity drift across ~100 unrelated real vehicles across the state within
15 minutes — any sufficiently common colour/shape (grey sedan, silver
hatchback) would match, regardless of distance. Every appearance-match
candidate is now also checked against the same haversine/plausible-speed
physics used in geo.py's forward/backward feasibility filters: if reaching
the candidate's last camera from the new sighting's camera would require an
implausible speed, it's excluded from consideration entirely, not just
deprioritised. Same honesty stance as geo.py: if either camera lacks GPS,
the check can't be assessed and does NOT block the match (an incomplete
registry must not make the system silently over-reject). Same evidence-based
gate also applies to non-positive elapsed time between two sightings (e.g.
cross-thread clock skew): distant cameras still get rejected, since clock
skew explains a few seconds of disagreement, not two simultaneous sightings
hundreds of kilometres apart.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Dict, Optional, Tuple

import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import CameraRegistry, VehicleIdentity
from .geo import MAX_PLAUSIBLE_KMH, haversine_km
from .reid import cosine_similarity

# How long an identity stays eligible for cross-camera association after
# its last sighting — a coarse outer bound on candidate lookup, NOT the
# thing that decides whether a match is physically plausible. That job now
# belongs to the geo-feasibility gate in _best_match, which reasons about
# actual distance and elapsed time. Before the gate existed, this window was
# the ONLY defense against merging unrelated vehicles, so it had to stay
# tight (15 min); real testing then showed it rejecting a genuinely
# plausible same-vehicle match — a 35-minute, 44 km/h hop between two real
# Ahmedabad-area cameras — before the gate ever got a chance to evaluate it.
# 60 minutes comfortably covers a realistic multi-camera city route at
# MAX_PLAUSIBLE_KMH-bounded speeds (see geo.py) while the gate still rejects
# anything actually implausible within that window.
ASSOCIATION_WINDOW = dt.timedelta(minutes=60)
# Calibrated 2026-09-10 against real crop data (`scripts/
# calibrate_embedding_threshold.py`, see CODEX_HANDOFF_PROMPT.md's ML-3
# section for the full writeup) — NOT changed by that calibration, on
# purpose. Finding: 41.87% of 3,000 confirmed-different-vehicle real crop
# pairs scored >= 0.80 (this threshold alone is a weak discriminator), but
# there was zero independent positive-pair data to check what raising it
# would do to recall — the geo-feasibility gate below is doing real
# compensating work when GPS is present, and the actual demo-lead camera
# (cam06) has GPS set. Residual exposure: cameras with no GPS coordinates
# rely on this threshold alone. Re-calibrate with real same-vehicle pairs
# (a controlled test driving one vehicle past 2+ real cameras) before
# changing this number, not off negative-side evidence alone.
EMBEDDING_SIMILARITY_THRESHOLD = 0.80


@dataclasses.dataclass
class LinkInfo:
    """Why this sighting got attached to the identity it did — persisted
    onto the VehicleEvent so the "why was this vehicle linked?"
    explainability panel has real data instead of nothing. Captured here,
    at the moment of the match decision, because it can't be reconstructed
    later: VehicleIdentity only keeps its latest embedding, not history."""

    method: str  # "new_identity" | "plate_continuation" | "plate_upgrade" | "appearance_match"
    score: Optional[float] = None  # cosine similarity, only set for appearance_match
    time_gap_s: Optional[float] = None  # seconds since the identity's previous sighting


class IdentityResolver:
    def resolve(
        self,
        session: Session,
        plate: Optional[str],
        plate_confidence: Optional[float],
        embedding: np.ndarray,
        observed_at: dt.datetime,
        camera_id: str,
    ) -> Tuple[VehicleIdentity, LinkInfo]:
        if plate:
            return self._resolve_with_plate(session, plate, plate_confidence, embedding, observed_at, camera_id)
        return self._resolve_anonymous(session, embedding, observed_at, camera_id)

    def _resolve_with_plate(
        self,
        session: Session,
        plate: str,
        plate_confidence: Optional[float],
        embedding: np.ndarray,
        observed_at: dt.datetime,
        camera_id: str,
    ) -> Tuple[VehicleIdentity, LinkInfo]:
        # 1. Same plate already has an identity -> just continue it. A
        #    direct plate re-read is strong ground truth on its own — the
        #    geo-feasibility gate below only applies to appearance-only
        #    matching, where the evidence is much weaker.
        existing = (
            session.query(VehicleIdentity)
            .filter(VehicleIdentity.plate == plate)
            .order_by(VehicleIdentity.last_seen_at.desc())
            .first()
        )
        if existing:
            gap_s = (observed_at - existing.last_seen_at).total_seconds()
            existing.last_seen_at = observed_at
            existing.last_camera_id = camera_id
            existing.set_embedding(embedding)
            if plate_confidence is not None and (existing.plate_confidence or 0) < plate_confidence:
                existing.plate_confidence = plate_confidence
            return existing, LinkInfo(method="plate_continuation", time_gap_s=gap_s)

        # 2. No identity has this plate yet — but an anonymous identity with
        #    a matching appearance might be THIS vehicle, seen earlier
        #    without a readable plate. Upgrade it instead of creating a
        #    disconnected new identity.
        candidate, score = self._best_anonymous_match(session, embedding, observed_at, camera_id)
        if candidate is not None:
            gap_s = (observed_at - candidate.last_seen_at).total_seconds()
            try:
                # Flush (never commit): the pipeline owns the transaction
                # that includes both this mutation and its VehicleEvent.
                candidate.plate = plate
                candidate.plate_confidence = plate_confidence
                candidate.last_seen_at = observed_at
                candidate.last_camera_id = camera_id
                candidate.set_embedding(embedding)
                session.flush()
            except IntegrityError:
                # Another camera's worker thread committed an identity with
                # this exact plate between our SELECT above and this COMMIT
                # (each camera runs its own thread/session — see
                # streaming/manager.py — so this is a real, reachable race,
                # not theoretical). Discard our local upgrade and fall
                # through to the winner instead of creating a duplicate.
                session.rollback()
                return self._resolve_with_plate(session, plate, plate_confidence, embedding, observed_at, camera_id)
            return candidate, LinkInfo(method="plate_upgrade", score=score, time_gap_s=gap_s)

        # 3. Genuinely new, plate known from the start.
        identity = VehicleIdentity(
            plate=plate, plate_confidence=plate_confidence,
            first_seen_at=observed_at, last_seen_at=observed_at, last_camera_id=camera_id,
        )
        identity.set_embedding(embedding)
        try:
            session.add(identity)
            session.flush()
        except IntegrityError:
            # Same race as above: another thread's identity for this plate
            # landed first. Re-resolve — this time the plate exists, so we
            # take the "continue existing" path (case 1) instead of a retry
            # loop, since the losing `identity` object above is never
            # persisted (rolled back) and safely discarded.
            session.rollback()
            return self._resolve_with_plate(session, plate, plate_confidence, embedding, observed_at, camera_id)
        return identity, LinkInfo(method="new_identity")

    def _resolve_anonymous(
        self, session: Session, embedding: np.ndarray, observed_at: dt.datetime, camera_id: str
    ) -> Tuple[VehicleIdentity, LinkInfo]:
        # Try to continue an existing identity (anonymous OR already-plated —
        # a plated vehicle can still have a later sighting where ANPR fails;
        # that sighting should still attach to the known identity, not spawn
        # a new anonymous one).
        candidate, score = self._best_match_any(session, embedding, observed_at, camera_id)
        if candidate is not None:
            gap_s = (observed_at - candidate.last_seen_at).total_seconds()
            candidate.last_seen_at = observed_at
            candidate.last_camera_id = camera_id
            return candidate, LinkInfo(method="appearance_match", score=score, time_gap_s=gap_s)

        identity = VehicleIdentity(first_seen_at=observed_at, last_seen_at=observed_at, last_camera_id=camera_id)
        identity.set_embedding(embedding)
        session.add(identity)
        session.flush()
        return identity, LinkInfo(method="new_identity")

    def _best_anonymous_match(
        self, session: Session, embedding: np.ndarray, observed_at: dt.datetime, camera_id: str
    ) -> Tuple[Optional[VehicleIdentity], Optional[float]]:
        return self._best_match(session, embedding, observed_at, camera_id, plate_is_null=True)

    def _best_match_any(
        self, session: Session, embedding: np.ndarray, observed_at: dt.datetime, camera_id: str
    ) -> Tuple[Optional[VehicleIdentity], Optional[float]]:
        return self._best_match(session, embedding, observed_at, camera_id, plate_is_null=None)

    def _best_match(
        self,
        session: Session,
        embedding: np.ndarray,
        observed_at: dt.datetime,
        camera_id: str,
        plate_is_null: Optional[bool],
    ) -> Tuple[Optional[VehicleIdentity], Optional[float]]:
        cutoff = observed_at - ASSOCIATION_WINDOW
        query = session.query(VehicleIdentity).filter(VehicleIdentity.last_seen_at >= cutoff)
        if plate_is_null is True:
            query = query.filter(VehicleIdentity.plate.is_(None))
        candidates = query.all()

        new_camera = session.get(CameraRegistry, camera_id)
        new_gps = (new_camera.latitude, new_camera.longitude) if new_camera and new_camera.latitude is not None else None

        # Fetch only the cameras actually referenced by candidates' last
        # sighting — not the whole registry — so this stays cheap as the
        # registry grows toward the statewide target.
        referenced_ids = {c.last_camera_id for c in candidates if c.last_camera_id}
        cameras_by_id: Dict[str, CameraRegistry] = {}
        if referenced_ids:
            for cam in session.query(CameraRegistry).filter(CameraRegistry.id.in_(referenced_ids)).all():
                cameras_by_id[cam.id] = cam

        best, best_score = None, EMBEDDING_SIMILARITY_THRESHOLD
        for identity in candidates:
            other = identity.get_embedding()
            if other is None:
                continue
            score = cosine_similarity(embedding, other)
            if score <= best_score:
                continue
            if not self._geo_feasible(new_gps, identity.last_camera_id, observed_at, identity.last_seen_at, cameras_by_id):
                continue
            best, best_score = identity, score
        return best, (best_score if best is not None else None)

    @staticmethod
    def _geo_feasible(
        new_gps: Optional[Tuple[float, float]],
        candidate_camera_id: Optional[str],
        observed_at: dt.datetime,
        candidate_last_seen_at: dt.datetime,
        cameras_by_id: Dict[str, CameraRegistry],
    ) -> bool:
        """Hard gate, not a score adjustment — an infeasible candidate is
        excluded outright, same ELIMINATED semantics as geo.py. Returns True
        (don't block) whenever feasibility genuinely can't be assessed —
        missing GPS on either side — rather than guessing."""
        if new_gps is None or candidate_camera_id is None:
            return True
        cand_cam = cameras_by_id.get(candidate_camera_id)
        if cand_cam is None or cand_cam.latitude is None or cand_cam.longitude is None:
            return True
        distance_km = haversine_km(new_gps[0], new_gps[1], cand_cam.latitude, cand_cam.longitude)
        elapsed_s = (observed_at - candidate_last_seen_at).total_seconds()
        if elapsed_s <= 0:
            # Two sightings with a non-positive gap — same-camera re-finalize
            # or cross-thread clock skew (each camera's frame loop reads its
            # own wall clock independently — see pipeline.py). Clock skew
            # explains a few seconds of disagreement, not being in two
            # cities at once, so this is a distance check, not a free pass:
            # adjacent/same-junction cameras are still plausible, anything
            # farther is not, regardless of what the (untrustworthy) elapsed
            # time claims.
            return distance_km <= 2.0
        required_kmh = distance_km / (elapsed_s / 3600.0)
        return required_kmh <= MAX_PLAUSIBLE_KMH


identity_resolver = IdentityResolver()
