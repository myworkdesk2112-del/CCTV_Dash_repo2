"""Within-camera tracking, purely to support temporal fusion.

Association (deciding "is this detection the same vehicle as last frame")
now prefers Ultralytics' real ByteTrack when the detector supplies a
`track_id` (see `detector.py`'s `YoloVehicleDetector`, which calls
`model.track(..., tracker="bytetrack.yaml")`). This class's own IOU-overlap
matching is the fallback for when no external track_id is available — the
stub detector (no ByteTrack), or a detection ByteTrack hasn't confirmed
into a track yet. Both paths converge on the same `Track` accumulation
logic below, so temporal fusion (plate-vote consensus, motion attributes)
works identically regardless of which association method placed the
observation into a track.

Why this matters: a single OCR read is unreliable (glare/blur/angle on any
one frame). A vehicle is visible across several sampled frames as it
crosses the camera's view; voting across those reads is far more reliable
than trusting frame 1. See the "what happens if we can't see the plate"
discussion — this is the fix for the case where *some* frames read fine
and others don't, not the case where *no* frame ever does (that's the
attribute-fallback path in attributes.py / routes_vehicle.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .attributes import VehicleAttributes
from .reid import ColorHistogramEncoder, ReIdEncoder, cosine_similarity

BBox = Tuple[float, float, float, float]

IOU_MATCH_THRESHOLD = 0.3
# A vehicle not re-detected within this many ms of stream-relative PTS is
# considered gone (left the frame, or the read gap is too large to trust
# as continuous). Finalize and flush rather than hold forever.
TRACK_TIMEOUT_MS = 3000.0
# Matches identity.py's conservative cross-camera similarity floor.  This is
# only a guard against joining visibly different vehicles when fallback IOU
# overlaps; it never rejects a same-track OCR misread based on plate text.
# Known limitation, inherited from the same measurement that already
# constrains identity.py's use of this threshold (see
# scripts/calibrate_embedding_threshold.py's 2026-09-10 run, TASKS.md P1):
# ColorHistogramEncoder scored 41.87% of 3,000 real confirmed-DIFFERENT
# vehicle crop pairs at >= 0.80 similarity. That means this guard reliably
# catches only grossly dissimilar vehicles (see
# test_iou_overlap_with_visibly_different_crop_starts_a_new_track, which
# uses solid black vs. solid white crops) and will likely still miss the
# realistic contamination case — two similarly-colored/same-class vehicles
# swapping in the same queued spot. A real fix needs a stronger encoder,
# not a threshold change on this one (raising it further would reject
# legitimate same-vehicle lighting/angle variation instead).
IOU_ASSOCIATION_MIN_REID_SIMILARITY = 0.80


def _iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass(eq=False)
class Track:
    track_id: int
    bbox: BBox
    last_pts_ms: float
    first_pts_ms: float
    vehicle_type: str
    # Raw (plate_string, confidence) per frame-read, in observation order —
    # kept raw (not pre-bucketed by exact string) so consensus_plate() can
    # vote per character position, not just per whole string. See its
    # docstring for why: an exact-string majority vote splits a vehicle's
    # votes across every OCR variant a single misread character produces.
    plate_reads: List[Tuple[str, float]] = field(default_factory=list)
    best_attrs: Optional[VehicleAttributes] = None
    best_attrs_confidence: float = -1.0
    best_crop: Optional[np.ndarray] = None  # crop from the highest-confidence detection, for Re-ID
    detection_confidences: List[float] = field(default_factory=list)
    # First observed bbox, for motion-attribute derivation (displacement from
    # here to the latest bbox over elapsed PTS). Set on the first observation.
    first_bbox: Optional[BBox] = None
    # Real ByteTrack ID (see detector.py), when available. When set, new
    # observations are associated by this ID directly rather than by IOU —
    # ByteTrack already solved the association problem more robustly
    # (Kalman-predicted motion, not just last-frame overlap).
    external_track_id: Optional[int] = None

    def add_observation(
        self,
        bbox: BBox,
        pts_ms: float,
        detection_confidence: float,
        attrs: VehicleAttributes,
        plate_result: Optional[Tuple[str, float]],
        crop: Optional[np.ndarray] = None,
    ) -> None:
        if self.first_bbox is None:
            self.first_bbox = bbox
        self.bbox = bbox
        self.last_pts_ms = pts_ms
        self.detection_confidences.append(detection_confidence)
        if detection_confidence > self.best_attrs_confidence:
            self.best_attrs = attrs
            self.best_attrs_confidence = detection_confidence
            self.best_crop = crop
        if plate_result:
            self.plate_reads.append(plate_result)

    def consensus_plate(self) -> Tuple[Optional[str], Optional[float]]:
        """Position-weighted character vote, not exact-string majority vote.

        Exact-string voting has a real failure mode on noisy real footage:
        one single-character misread (e.g. `GJ01RP6128` read once as
        `GU01RP6128`) used to create a second, distinct "candidate" that
        siphons votes away from the correct plate — harmless when the
        correct plate still has a comfortable majority (as in the real
        cam06 case this locks in as a regression test), but a genuinely
        worse split (more disagreeing frames, or several different
        single-character misreads) can dilute every candidate below
        `PLATE_MIN_CONFIDENCE` even though most reads agree on most
        characters. Voting per character position instead means agreeing
        positions build unanimous support regardless of where OTHER
        positions disagree, and the reconstructed plate can be a string
        that was never literally one of the raw OCR reads — don't assume
        otherwise downstream.

        Reads are grouped by length first: position voting is only
        meaningful within same-length reads (a different-length read is
        either a different plate, or an OCR miss that dropped/added a
        character — this pass doesn't attempt edit-distance alignment
        across lengths, per TASKS.md's documented scope). The length-group
        with the most total confidence wins, generalizing the old
        algorithm's "highest vote mass wins" selection from exact strings
        to length-groups.

        Known, tested, unmitigated limitation: if `plate_reads` ever mixed
        sightings of two different vehicles (e.g. an IOU-overlap
        association merging a second car into this track), the vote could
        return a hybrid plate nobody's camera actually saw — see
        test_tracker.py's contamination test. No character-agreement rule
        can fix this without also breaking the legitimate same-vehicle
        severe-misread case (isolates_higher_vote_share /
        confidence_is_vote_share_not_count both require outvoting a
        majority-disagreeing single stray read). A real fix needs signal
        outside the plate string — an appearance-embedding check at
        association time — not attempted here (see TASKS.md).
        """
        if not self.plate_reads:
            return None, None

        groups: Dict[int, List[Tuple[str, float]]] = {}
        for plate, conf in self.plate_reads:
            groups.setdefault(len(plate), []).append((plate, conf))

        winning_length = max(groups, key=lambda length: sum(c for _, c in groups[length]))
        group = groups[winning_length]
        total = sum(c for _, c in group)

        chars: List[str] = []
        min_share = 1.0
        for pos in range(winning_length):
            votes: Dict[str, float] = {}
            first_seen_order: List[str] = []
            for plate, conf in group:
                ch = plate[pos]
                if ch not in votes:
                    votes[ch] = 0.0
                    first_seen_order.append(ch)
                votes[ch] += conf
            # max() over a list returns the FIRST max on a tie (iterates in
            # first_seen_order) — matches the old exact-string tie-break
            # ("first-inserted wins", pinned by
            # test_consensus_plate_confidence_is_vote_share_not_count).
            best_char = max(first_seen_order, key=lambda c: votes[c])
            min_share = min(min_share, votes[best_char] / total)
            chars.append(best_char)

        # Confidence is the WEAKEST position's agreement, not an average —
        # a plate with one badly-split character position is only as
        # trustworthy as that position, same bottleneck semantics as the
        # old algorithm (which this reproduces exactly when reads share one
        # length, since a single differing position IS the old algorithm's
        # winning-plate vote share in that case).
        return "".join(chars), round(min(1.0, min_share), 2)

    def motion_attributes(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Returns (dwell_time_s, speed_px_per_s, direction_deg) derived from
        the bbox path over PTS. IMAGE-PLANE metrics only — see the honest
        caveat on VehicleEvent.dwell_time_s in db/models.py. All timing is
        from PTS deltas (never wall-clock), per the sandbox timing rules.

        dwell is always meaningful; speed/direction need actual movement
        across at least two observations with a positive time delta, else
        they're None (a single-frame track has no measurable motion)."""
        import math

        dwell_ms = self.last_pts_ms - self.first_pts_ms
        dwell_time_s = round(dwell_ms / 1000.0, 2) if dwell_ms >= 0 else None

        if self.first_bbox is None or dwell_ms <= 0:
            return dwell_time_s, None, None

        fx = (self.first_bbox[0] + self.first_bbox[2]) / 2.0
        fy = (self.first_bbox[1] + self.first_bbox[3]) / 2.0
        lx = (self.bbox[0] + self.bbox[2]) / 2.0
        ly = (self.bbox[1] + self.bbox[3]) / 2.0
        dx, dy = lx - fx, ly - fy
        displacement = math.hypot(dx, dy)

        speed_px_per_s = round(displacement / (dwell_ms / 1000.0), 2)
        # atan2(dy, dx): 0°=right, 90°=down, 180/-180=left, -90=up (image
        # coords, y grows downward). Normalized to [0, 360).
        direction_deg = round(math.degrees(math.atan2(dy, dx)) % 360.0, 1) if displacement > 1.0 else None
        return dwell_time_s, speed_px_per_s, direction_deg


class CameraTracker:
    """One instance per camera. Not thread-safe by itself — the pipeline
    calls it from a single frame-handling context per camera worker."""

    def __init__(self, reid_encoder: ReIdEncoder | None = None):
        self._active: List[Track] = []
        self._next_id = 1
        self._reid_encoder = reid_encoder or ColorHistogramEncoder()

    def _appearance_compatible(self, track: Track, crop: Optional[np.ndarray]) -> bool:
        """Reject an IOU-only merge only when both real crops disagree.

        Missing/empty crops leave the established IOU fallback intact rather
        than inventing an appearance result.  ByteTrack-owned associations do
        not pass here: their external ID is the association authority.
        """
        if track.best_crop is None or crop is None or track.best_crop.size == 0 or crop.size == 0:
            return True
        similarity = cosine_similarity(self._reid_encoder.encode(track.best_crop), self._reid_encoder.encode(crop))
        return similarity >= IOU_ASSOCIATION_MIN_REID_SIMILARITY

    def update(
        self,
        bbox: BBox,
        pts_ms: float,
        vehicle_type: str,
        detection_confidence: float,
        attrs: VehicleAttributes,
        plate_result: Optional[Tuple[str, float]],
        crop: Optional[np.ndarray] = None,
        external_track_id: Optional[int] = None,
    ) -> Track:
        if external_track_id is not None:
            for track in self._active:
                if track.external_track_id == external_track_id:
                    track.add_observation(bbox, pts_ms, detection_confidence, attrs, plate_result, crop)
                    return track
            # No track owns this external_track_id yet. ByteTrack reports
            # box.id=None on a detection's first frame and only assigns the
            # real id from the second frame the vehicle is seen — so without
            # this check, frame 1 creates an IOU-fallback track (external_id
            # None) and frame 2 always falls through to create a *second*,
            # disconnected track, permanently orphaning frame 1's data. Claim
            # that IOU-fallback track instead, if its bbox still matches.
            best_track, best_iou = None, 0.0
            for track in self._active:
                if track.external_track_id is not None:
                    continue
                score = _iou(track.bbox, bbox)
                if score > best_iou:
                    best_track, best_iou = track, score
            if (
                best_track is not None
                and best_iou >= IOU_MATCH_THRESHOLD
                and self._appearance_compatible(best_track, crop)
            ):
                best_track.external_track_id = external_track_id
                best_track.add_observation(bbox, pts_ms, detection_confidence, attrs, plate_result, crop)
                return best_track
            # Fall through to create a new track below — genuinely a new
            # ByteTrack id with no matching in-flight track.
        else:
            best_track, best_iou = None, 0.0
            for track in self._active:
                if track.external_track_id is not None:
                    continue  # don't let IOU steal a track ByteTrack owns
                score = _iou(track.bbox, bbox)
                if score > best_iou:
                    best_track, best_iou = track, score

            if (
                best_track is not None
                and best_iou >= IOU_MATCH_THRESHOLD
                and self._appearance_compatible(best_track, crop)
            ):
                best_track.add_observation(bbox, pts_ms, detection_confidence, attrs, plate_result, crop)
                return best_track

        track = Track(
            track_id=self._next_id,
            bbox=bbox,
            last_pts_ms=pts_ms,
            first_pts_ms=pts_ms,
            vehicle_type=vehicle_type,
            external_track_id=external_track_id,
        )
        self._next_id += 1
        track.add_observation(bbox, pts_ms, detection_confidence, attrs, plate_result, crop)
        self._active.append(track)
        return track

    def pop_expired(self, current_pts_ms: float) -> List[Track]:
        expired = [t for t in self._active if current_pts_ms - t.last_pts_ms > TRACK_TIMEOUT_MS]
        self._active = [t for t in self._active if t not in expired]
        return expired

    def flush_all(self) -> List[Track]:
        """Force-finalize every active track — used on a scene discontinuity,
        since a vehicle can't sensibly be tracked across a hard cut."""
        flushed, self._active = self._active, []
        return flushed
