"""Owns one RtspCameraWorker per active camera and wires frames into analytics.

- Reconciles workers against the live catalogue (open only what's live;
  close what's gone — "pace your load").
- Applies ANALYTICS_FRAME_STRIDE so heavy per-frame inference doesn't have
  to run on every frame of every camera.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

from .. import config
from ..catalogue import CatalogueClient
from .rtsp_client import Frame, RtspCameraWorker

logger = logging.getLogger("sentinel.stream-manager")

FrameSink = "callable(Frame) -> None"

# Real incident found 2026-09-13: a torch/torchvision ABI mismatch made
# EVERY analytics call raise, while the RTSP read itself kept succeeding —
# /health and CameraRegistry.is_healthy reported "ok" with 30 workers up
# the entire time, because that signal only reflects stream connectivity
# (see rtsp_client.py's connected/last_frame_at), not whether the
# analytics pipeline is actually producing output. This many consecutive
# analytics failures on one camera (each call is one stride-gated frame,
# so this is a real span of wall-clock time, not one bad frame) flips
# that camera to "analytics degraded" in health_snapshot() below.
ANALYTICS_DEGRADED_ERROR_THRESHOLD = 5


class _CameraAnalyticsHealth:
    __slots__ = ("last_success_at", "last_error_at", "consecutive_errors")

    def __init__(self) -> None:
        self.last_success_at: Optional[float] = None
        self.last_error_at: Optional[float] = None
        self.consecutive_errors: int = 0


class StreamManager:
    def __init__(self, catalogue: CatalogueClient, on_frame):
        self._catalogue = catalogue
        self._on_frame_downstream = on_frame
        self._workers: Dict[str, RtspCameraWorker] = {}
        self._frame_counters: Dict[str, int] = {}
        self._analytics_health: Dict[str, _CameraAnalyticsHealth] = {}
        self._lock = threading.RLock()

    def _handle_frame(self, frame: Frame) -> None:
        with self._lock:
            n = self._frame_counters.get(frame.camera_id, 0) + 1
            self._frame_counters[frame.camera_id] = n
        if n % config.ANALYTICS_FRAME_STRIDE != 0:
            return

        health = self._analytics_health.setdefault(frame.camera_id, _CameraAnalyticsHealth())
        try:
            self._on_frame_downstream(frame)
        except Exception:
            health.last_error_at = time.time()
            health.consecutive_errors += 1
            raise  # rtsp_client's worker loop logs it; re-raise, don't swallow here
        else:
            health.last_success_at = time.time()
            health.consecutive_errors = 0

    def reconcile(self) -> None:
        """Call after every catalogue refresh."""
        live_cameras = {cid: cam for cid, cam in self._catalogue.cameras.items() if cam.live}

        with self._lock:
            current_ids = set(self._workers.keys())
            live_ids = set(live_cameras.keys())
            to_start = [live_cameras[cam_id] for cam_id in live_ids - current_ids]
            to_stop = [(cam_id, self._workers.pop(cam_id)) for cam_id in current_ids - live_ids]

        # worker.start()/stop() happen OUTSIDE the lock: stop() joins the
        # worker's thread (up to 5s), which that same thread's frame
        # callback (_handle_frame) needs this SAME lock to complete — held
        # across the join, a batch of simultaneous camera drops would
        # stall _handle_frame for every OTHER camera too, not just the
        # ones being stopped, for up to N*5s. Found by
        # software-engineering review 2026-09-04. The dict mutations above
        # (the only part that actually needs the lock) already happened.
        for cam in to_start:
            worker = RtspCameraWorker(cam.id, cam.rtsp_url, self._handle_frame)
            worker.start()
            with self._lock:
                self._workers[cam.id] = worker
            logger.info("started worker for camera %s (%s)", cam.id, cam.location)
        for cam_id, worker in to_stop:
            worker.stop()
            # Only pop these AFTER stop() has joined the worker thread: doing
            # it earlier (while the thread could still be mid-callback into
            # _handle_frame) let that in-flight call's setdefault() silently
            # resurrect the entry with no future reconcile() left to clean it
            # up again — a real bug found by re-review 2026-09-17.
            with self._lock:
                self._frame_counters.pop(cam_id, None)
                self._analytics_health.pop(cam_id, None)
            logger.info("stopped worker for camera %s (no longer live)", cam_id)

    def stop_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            worker.stop()

    @property
    def active_camera_ids(self):
        with self._lock:
            return list(self._workers.keys())

    def health_snapshot(self) -> Dict[str, dict]:
        """Per-camera connection AND analytics health — feeds the Model 1
        'health monitoring' deliverable (see main.py's health-sync loop and
        api/routes_cameras.py's gap-analysis endpoint). `connected`/
        `last_frame_at` reflect the RTSP stream only; `analytics_degraded`
        reflects whether the analytics pipeline itself is actually
        succeeding on that stream's frames — the two can and did (found
        2026-09-13) diverge."""
        with self._lock:
            return {
                cam_id: {
                    "connected": w.connected,
                    "last_frame_at": w.last_frame_at,
                    "analytics_degraded": (
                        self._analytics_health[cam_id].consecutive_errors >= ANALYTICS_DEGRADED_ERROR_THRESHOLD
                        if cam_id in self._analytics_health
                        else False
                    ),
                    "last_analytics_success_at": (
                        self._analytics_health[cam_id].last_success_at if cam_id in self._analytics_health else None
                    ),
                }
                for cam_id, w in self._workers.items()
            }
