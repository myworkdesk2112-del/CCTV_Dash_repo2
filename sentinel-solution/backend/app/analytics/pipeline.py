"""Wires a single video Frame through the full chain:

    detect vehicle -> locate plate region -> enhance -> OCR
        -> temporal fusion (tracker.py, within-camera)
        -> Re-ID embedding -> cross-camera identity resolution (identity.py)
        -> persist -> watchlist check

Called by StreamManager for each sampled frame.

Core design principle (see STRATEGY.md / the "what if we can't see the
plate" discussion): ANPR failure must not mean tracking failure.

    Plate not readable
            v
    Don't discard the vehicle
            v
    Generate a vehicle fingerprint (colour + type + appearance embedding)
            v
    Track it as an anonymous identity across cameras
            v
    Upgrade to a real plate the moment ANY sighting reads one

A single OCR read is also unreliable on its own (glare/blur/angle on one
frame), so within a camera we don't trust frame 1 — plate reads are
majority-voted across the whole time a vehicle is in view (tracker.py)
before ever reaching the identity resolver.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Callable, Dict

from .. import config
from ..db.models import CameraRegistry, VehicleEvent
from ..db.session import SessionLocal
from ..streaming.rtsp_client import Frame
from ..watchlist.service import watchlist_service
from .anomaly import raise_anomaly_alerts
from .calibration import calibrated_speed_kmh
from . import evidence_class as evclass
from . import evidence_integrity
from .anpr import PlateReader
from .attributes import MakeModelClassifier, StubMakeModelClassifier, extract_attributes
from .detector import VehicleDetector
from .density import DensityBatcher, PendingDensity, record_batched_counts
from .identity import identity_resolver
from .plate_detector import PlateDetector, StubPlateDetector, crop_plate, enhance_plate_crop
from .reid import EMBEDDING_DIM, ColorHistogramEncoder, ReIdEncoder

import cv2
import numpy as np
from .tracker import CameraTracker, Track

logger = logging.getLogger("sentinel.pipeline")


class AnalyticsPipeline:
    def __init__(
        self,
        detector_factory: Callable[[], VehicleDetector],
        plate_reader: PlateReader,
        make_model_classifier: MakeModelClassifier = StubMakeModelClassifier(),
        plate_detector: PlateDetector = StubPlateDetector(),
        reid_encoder: ReIdEncoder = ColorHistogramEncoder(),
        clock: Callable[[], dt.datetime] = dt.datetime.utcnow,
    ):
        # One detector PER CAMERA, not shared: YoloVehicleDetector's
        # ByteTrack state (persist=True) is only meaningful for a single
        # continuous stream — sharing one instance across concurrent cameras
        # would let unrelated scenes' tracks associate with each other.
        self._detector_factory = detector_factory
        self._detectors: Dict[str, VehicleDetector] = {}
        self._plate_reader = plate_reader
        self._make_model_classifier = make_model_classifier
        self._plate_detector = plate_detector
        self._reid_encoder = reid_encoder
        self._clock = clock
        self._trackers: Dict[str, CameraTracker] = {}
        self._density_batcher = DensityBatcher()

    def process(self, frame: Frame) -> None:
        tracker = self._trackers.setdefault(frame.camera_id, CameraTracker())

        if frame.discontinuity:
            # Scene cut at the sandbox's recording loop point — a track
            # can't sensibly continue across a hard cut, so finalize
            # whatever was in flight now rather than let it time out.
            # The detector's own ByteTrack state is equally stale across a
            # hard cut (its Kalman-predicted motion assumes continuous
            # footage), so drop it too — a fresh instance is built lazily
            # below, giving ByteTrack a clean slate exactly like the
            # within-camera tracker gets.
            logger.info("camera %s: scene discontinuity at pts=%.0fms", frame.camera_id, frame.pts_ms)
            self._finalize_tracks(frame.camera_id, tracker.flush_all())
            self.flush_density(frame.camera_id)
            self._detectors.pop(frame.camera_id, None)

        # NOT `self._detectors.setdefault(id, self._detector_factory())` —
        # setdefault evaluates its second argument eagerly on every call
        # (Python evaluates arguments before the call), so that form would
        # construct a full YOLO model on every single frame just to discard
        # it whenever the camera already had one. Real bug, caught by
        # actually running this (see verification), not by inspection.
        if frame.camera_id not in self._detectors:
            self._detectors[frame.camera_id] = self._detector_factory()
        detector = self._detectors[frame.camera_id]
        detections = detector.detect(frame.image)
        # Aggregate sampled-frame detections in memory.  One SQLite write is
        # made when this camera enters the next configured time window.
        completed_density = self._density_batcher.add(frame.camera_id, self._clock(), detections)
        if completed_density is not None:
            self._persist_density(completed_density)
        vehicle_detections = [d for d in detections if d.label != "person"]

        for det in vehicle_detections:
            x1, y1, x2, y2 = (int(v) for v in det.bbox)
            crop = frame.image[max(y1, 0):max(y2, 0), max(x1, 0):max(x2, 0)]
            if crop.size == 0:
                continue

            attrs = extract_attributes(crop, det.label, self._make_model_classifier)
            plate_result = self._read_plate(crop)

            tracker.update(
                bbox=det.bbox,
                pts_ms=frame.pts_ms,
                vehicle_type=det.label,
                detection_confidence=det.confidence,
                attrs=attrs,
                plate_result=plate_result,
                crop=crop,
                external_track_id=det.track_id,
            )

        self._finalize_tracks(frame.camera_id, tracker.pop_expired(frame.pts_ms))

    def _persist_density(self, batch: PendingDensity) -> None:
        density_session = SessionLocal()
        try:
            self._ensure_camera_registered(density_session, batch.camera_id)
            record_batched_counts(density_session, batch)
            density_session.commit()
        except Exception:
            density_session.rollback()
            logger.exception("camera %s: density aggregation failed", batch.camera_id)
        finally:
            density_session.close()

    def flush_density(self, camera_id: str) -> None:
        """Flush a camera's partial window on a discontinuity/shutdown."""
        pending_density = self._density_batcher.flush_camera(camera_id)
        if pending_density is not None:
            self._persist_density(pending_density)

    def _read_plate(self, vehicle_crop):
        """vehicle crop -> locate plate region -> enhance -> OCR. Running
        OCR on the whole vehicle crop (bumper/badges/background) produces
        far more false positives than localizing the plate region first."""
        plate_bbox = self._plate_detector.locate(vehicle_crop)
        if plate_bbox is None:
            return None
        plate_crop = crop_plate(vehicle_crop, plate_bbox)
        if plate_crop.size == 0:
            return None
        enhanced = enhance_plate_crop(plate_crop)
        return self._plate_reader.read(enhanced)

    def _finalize_tracks(self, camera_id: str, tracks: list[Track]) -> None:
        if not tracks:
            return

        session = SessionLocal()
        try:
            self._ensure_camera_registered(session, camera_id)
            # SessionLocal is autoflush=False (db/session.py), so a
            # just-added-but-not-yet-flushed CameraRegistry row (brand new
            # camera's first batch) would NOT be found by session.get()
            # below — pending objects only join the identity map on flush,
            # unlike already-persistent ones. flush() (not commit — no
            # need to end the transaction yet) makes it visible without
            # waiting for the loop's own per-track commits.
            session.flush()
            # Fetched once per batch (same camera_id for every track here),
            # not per-track and not re-fetched again below for anomaly
            # detection — an N+1 that was harmless at pilot scale but no
            # reason to repeat, same reasoning as _merged_camera_view's own
            # batch-fetch fix in routes_cameras.py.
            camera_row = session.get(CameraRegistry, camera_id)

            for track in tracks:
                plate, plate_confidence = track.consensus_plate()

                # Low-confidence read suppression (Flock-inspired, see
                # RESEARCH_EXISTING_SYSTEMS.md): a plate whose fused
                # confidence is below threshold is treated as UNREAD for
                # identity purposes — better to log the vehicle anonymously
                # (by appearance/attributes) than to spawn a false plate
                # identity or, worse, a false watchlist alert from a
                # misread. The vehicle is never dropped; only the shaky
                # plate string is withheld. Verified this path: the sighting
                # still persists and still resolves an identity by appearance.
                if plate is not None and (plate_confidence or 0.0) < config.PLATE_MIN_CONFIDENCE:
                    logger.info(
                        "camera %s: suppressing low-confidence plate read %s (%.2f < %.2f)",
                        camera_id, plate, plate_confidence or 0.0, config.PLATE_MIN_CONFIDENCE,
                    )
                    plate, plate_confidence = None, None

                attrs = track.best_attrs
                dwell_time_s, speed_px_per_s, direction_deg = track.motion_attributes()
                speed_kmh = calibrated_speed_kmh(
                    camera_row.homography_json if camera_row else None,
                    track.first_bbox,
                    track.bbox,
                    track.last_pts_ms - track.first_pts_ms,
                )
                embedding = (
                    self._reid_encoder.encode(track.best_crop)
                    if track.best_crop is not None
                    else np.zeros(EMBEDDING_DIM, dtype=np.float32)
                )

                observed_at = self._clock()
                identity, link_info = identity_resolver.resolve(
                    session,
                    plate=plate,
                    plate_confidence=plate_confidence,
                    embedding=embedding,
                    observed_at=observed_at,
                    camera_id=camera_id,
                )

                event = VehicleEvent(
                    identity_id=identity.id,
                    link_method=link_info.method,
                    link_score=link_info.score,
                    link_time_gap_s=link_info.time_gap_s,
                    # `plate`/`plate_confidence` are this sighting's OWN read
                    # only — null if this camera couldn't read it, even if
                    # the identity is otherwise resolved via another camera.
                    # That's what makes "was the plate actually read here"
                    # answerable per-event; query by identity_id (not by
                    # this field) to get the full cross-camera history.
                    plate=plate,
                    plate_confidence=plate_confidence,
                    camera_id=camera_id,
                    # Explicit, not the column default — must be the SAME
                    # value identity resolution just used above, or the
                    # displayed/persisted timestamp silently diverges from
                    # the timestamp the merge decision was actually made on.
                    # Real bug, caught by actually looking at the rendered
                    # UI, not just the resolver's own PASS/FAIL: the demo's
                    # injected simulated clock made identity resolution
                    # correct, but VehicleEvent still fell back to real
                    # wall-clock time, so the Vehicle Intelligence timeline
                    # showed sightings 1-2 seconds apart with "not a direct
                    # drive" warnings, contradicting the correct merge that
                    # had just happened.
                    observed_at=observed_at,
                    pts_ms=track.last_pts_ms,
                    confidence=max(track.detection_confidences) if track.detection_confidences else None,
                    vehicle_type=attrs.vehicle_type if attrs else track.vehicle_type,
                    color=attrs.color if attrs else None,
                    color_confidence=attrs.color_confidence if attrs else None,
                    width_px=attrs.width_px if attrs else None,
                    height_px=attrs.height_px if attrs else None,
                    aspect_ratio=attrs.aspect_ratio if attrs else None,
                    make_model=attrs.make_model if attrs else None,
                    make_model_confidence=attrs.make_model_confidence if attrs else None,
                    dwell_time_s=dwell_time_s,
                    speed_px_per_s=speed_px_per_s,
                    direction_deg=direction_deg,
                    speed_kmh=speed_kmh,
                    bbox_x1=track.bbox[0], bbox_y1=track.bbox[1],
                    bbox_x2=track.bbox[2], bbox_y2=track.bbox[3],
                )
                session.add(event)
                session.commit()

                event.crop_path = self._save_crop(event.id, track.best_crop)
                if event.crop_path:
                    # Hash the bytes that were just written, before anything
                    # else can touch the file, and stamp what produced them.
                    # Deliberately after the write and in the same commit as
                    # crop_path: a hash stored for a path that failed to
                    # write would be a provenance record for a file that
                    # never existed.
                    absolute_crop = os.path.join(config.CROPS_DIR, event.crop_path)
                    event.crop_sha256 = evidence_integrity.sha256_file(absolute_crop)
                    if event.crop_sha256:
                        event.crop_hashed_at = dt.datetime.utcnow()
                        event.production_stamp = evidence_integrity.production_stamp(
                            detector=self._detectors.get(camera_id),
                            plate_detector=self._plate_detector,
                            plate_reader=self._plate_reader,
                            reid_encoder=self._reid_encoder,
                        )
                session.commit()

                # Gate on THIS event's own evidence class, not identity.plate:
                # identity.plate can be set from a DIFFERENT, earlier camera's
                # read, so checking it here would raise a plate-matched alert
                # off a sighting that never read a plate itself (a LEAD_ONLY
                # appearance link riding on another sighting's confirmed
                # plate). Only a sighting that read and validated its own
                # plate (CONFIRMED) may trigger a watchlist alert — see
                # evidence_class.py and DECISION_REVIEW_2026-09-11.md.
                sighting_class = evclass.classify(event.plate, event.link_method)
                if sighting_class == evclass.CONFIRMED:
                    watchlist_service.raise_alert_if_matched(
                        session,
                        event.plate,
                        camera_id,
                        event.id,
                        evidence_class=sighting_class,
                        evidence_class_reason=evclass.describe(sighting_class, event.link_method),
                    )

                raise_anomaly_alerts(session, camera_row, event, identity)
        finally:
            session.close()

    @staticmethod
    def _save_crop(event_id: int, crop: "np.ndarray | None") -> "str | None":
        """Best-effort: evidence is a nice-to-have, never worth crashing the
        pipeline over. Returns the relative path stored on the event, or
        None if there was nothing to save or the write failed."""
        if crop is None or crop.size == 0:
            return None
        try:
            os.makedirs(config.CROPS_DIR, exist_ok=True)
            filename = f"{event_id}.jpg"
            path = os.path.join(config.CROPS_DIR, filename)
            ok = cv2.imwrite(path, crop)
            return filename if ok else None
        except Exception as exc:
            logger.warning("failed to save evidence crop for event %s: %s", event_id, exc)
            return None

    @staticmethod
    def _ensure_camera_registered(session, camera_id: str) -> None:
        if session.get(CameraRegistry, camera_id) is None:
            session.add(CameraRegistry(id=camera_id))
            session.commit()
