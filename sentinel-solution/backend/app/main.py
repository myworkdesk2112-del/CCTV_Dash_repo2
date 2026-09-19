from __future__ import annotations

import datetime as dt
import logging
import os
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .analytics.anpr import PaddleOcrPlateReader, StubPlateReader
from .analytics.detector import StubVehicleDetector, YoloVehicleDetector
from .analytics.pipeline import AnalyticsPipeline
from .analytics.federation import (
    DemoPartnerVmsAdapter,
    NycOpenDataAdapter,
    SentinelAdapter,
    ingest_all,
)
from .analytics.plate_detector import StubPlateDetector, YoloPlateDetector
from .api import (
    routes_admin,
    routes_alerts,
    routes_auth,
    routes_cameras,
    routes_evidence,
    routes_federation,
    routes_stream,
    routes_vehicle,
    routes_watchlist,
    session_auth,
)
from .api.auth import ensure_default_admin_key
from .api.rate_limit import RateLimitMiddleware
from .catalogue import catalogue
from . import external_camera_source
from .db.models import CameraRegistry
from .db.retention import purge_expired
from .db.session import SessionLocal, init_db
from .streaming.manager import StreamManager
from .watchlist.service import watchlist_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinel.main")

app = FastAPI(title="Sentinel — Unified CCTV Viewing & Analytics (Model 1 + 2)")
# Added before CORSMiddleware so CORS ends up outermost (Starlette wraps in
# reverse add order) — a 429 from the rate limiter still needs CORS headers
# for a browser caller to see it as a 429, not a CORS failure.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    # `Location` isn't on the CORS-safelisted response-header list, so
    # without this the browser silently can't read it — the frontend's
    # WHEP client (LiveView.jsx) needs it from the POST /live/{id}/whep
    # response to know where to send the session teardown DELETE.
    expose_headers=["Location"],
    # Required for the frontend's session cookie (api/session_auth.py,
    # SEC-4) to be sent/received cross-origin at all — the browser
    # silently drops Set-Cookie/Cookie on a cross-origin fetch()/XHR
    # without this, even with credentials: "include" on the client side.
    # Safe with a wildcard-free CORS_ALLOWED_ORIGINS (already the case,
    # see config.py) — the spec forbids combining this with
    # allow_origins=["*"], which this project already avoided per SWE-3.
    allow_credentials=True,
)

app.include_router(routes_auth.router)
app.include_router(session_auth.router)
app.include_router(routes_cameras.router)
app.include_router(routes_vehicle.router)
app.include_router(routes_watchlist.router)
app.include_router(routes_alerts.router)
app.include_router(routes_stream.router)
app.include_router(routes_admin.router)
app.include_router(routes_federation.router)
app.include_router(routes_evidence.router)

def _build_detector():
    """Real YOLOv8 vehicle detector if ultralytics + weights are available
    (see analytics/detector.py); falls back to the honest no-op stub
    otherwise, loudly, rather than silently pretending detection works."""
    try:
        return YoloVehicleDetector(weights=config.YOLO_WEIGHTS)
    except Exception as exc:  # noqa: BLE001 — ultralytics missing, weights unreachable, etc.
        logger.warning(
            "YOLOv8 detector unavailable (%s) — falling back to StubVehicleDetector "
            "(no detections will be produced). Run `pip install ultralytics` in a "
            "venv to enable real detection.",
            exc,
        )
        return StubVehicleDetector()


def _build_plate_detector():
    """Real trained plate localizer if the (separately downloaded) ONNX
    weights are present — see config.PLATE_DETECTOR_WEIGHTS. Falls back to
    StubPlateDetector's heuristic crop otherwise, loudly, same honest-
    fallback pattern as the detector/OCR builders above."""
    if not os.path.exists(config.PLATE_DETECTOR_WEIGHTS):
        logger.warning(
            "Plate localizer weights not found at %s — falling back to StubPlateDetector's "
            "heuristic crop (see config.PLATE_DETECTOR_WEIGHTS for the download command).",
            config.PLATE_DETECTOR_WEIGHTS,
        )
        return StubPlateDetector()
    try:
        return YoloPlateDetector(weights=config.PLATE_DETECTOR_WEIGHTS)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Plate localizer unavailable (%s) — falling back to StubPlateDetector's heuristic crop.",
            exc,
        )
        return StubPlateDetector()


def _build_plate_reader():
    """Real PaddleOCR plate reader if paddleocr/paddlepaddle are available
    (see analytics/anpr.py); falls back to the honest no-op stub otherwise."""
    try:
        return PaddleOcrPlateReader()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "PaddleOCR reader unavailable (%s) — falling back to StubPlateReader "
            "(no plates will ever be read). Run `pip install paddleocr==2.9.1 "
            "paddlepaddle==2.6.2` in a venv to enable real ANPR.",
            exc,
        )
        return StubPlateReader()


# ORDER MATTERS: build a detector (imports torch, via ultralytics) BEFORE
# the plate reader (imports paddlepaddle). Verified empirically on Windows —
# importing paddleocr/paddlepaddle first corrupts torch's DLL loading
# (`OSError: ... torch\lib\shm.dll ...`) when torch is imported afterward in
# the same process; the reverse order works fine. This isn't Python argument
# evaluation order being relied on implicitly — these are separate
# statements specifically so the required order stays visible and can't be
# silently broken by refactoring the AnalyticsPipeline(...) call below.
#
# This eager instance's construction still matters (forces torch to import
# before paddle) but the instance itself would normally be discarded —
# AnalyticsPipeline builds its own detector PER CAMERA (see pipeline.py)
# because YoloVehicleDetector carries persistent ByteTrack state
# (persist=True) that must not be shared across concurrent camera streams.
# Its class name IS kept (not the instance) so /health can report whether
# the running system is on real models or stub fallback.
_detector_probe = _build_detector()
_plate_reader = _build_plate_reader()
_plate_detector_instance = _build_plate_detector()

ANALYTICS_COMPONENT_STATUS = {
    "vehicle_detector": type(_detector_probe).__name__,
    "plate_detector": type(_plate_detector_instance).__name__,
    "plate_reader": type(_plate_reader).__name__,
}

pipeline = AnalyticsPipeline(
    detector_factory=_build_detector, plate_reader=_plate_reader, plate_detector=_plate_detector_instance
)
stream_manager = StreamManager(catalogue, on_frame=pipeline.process)


def _sync_camera_health() -> None:
    """Model 1's 'health monitoring' deliverable: reflect each onboarded
    camera's real connection state (from the RTSP worker, not a stub) into
    CameraRegistry so /cameras and /cameras/gap-analysis report it."""
    snapshot = stream_manager.health_snapshot()
    session = SessionLocal()
    try:
        now = time.time()
        for cam_id, status in snapshot.items():
            registry = session.get(CameraRegistry, cam_id)
            if registry is None:
                registry = CameraRegistry(id=cam_id)
                session.add(registry)
            stale = status["last_frame_at"] is None or (now - status["last_frame_at"]) > routes_cameras.HEALTH_STALE_S
            registry.is_healthy = status["connected"] and not stale
            if status["last_frame_at"] is not None:
                registry.last_seen_live_at = dt.datetime.utcfromtimestamp(status["last_frame_at"])
            # A connected, non-stale stream can still be feeding a broken
            # analytics pipeline (found 2026-09-13: torch/torchvision ABI
            # mismatch failed every detection call while the stream stayed
            # perfectly healthy) — surface that separately rather than
            # letting stream connectivity alone say "ok".
            registry.analytics_degraded = status["analytics_degraded"]
            if status["last_analytics_success_at"] is not None:
                registry.last_analytics_success_at = dt.datetime.utcfromtimestamp(
                    status["last_analytics_success_at"]
                )
        # Cameras that were live before but have no active worker anymore
        # (dropped from the catalogue) are unhealthy, not silently unknown.
        active_ids = set(snapshot.keys())
        for registry in session.query(CameraRegistry).all():
            if registry.id not in active_ids and registry.is_healthy:
                registry.is_healthy = False
        session.commit()
    finally:
        session.close()


@app.on_event("startup")
def on_startup():
    init_db()
    session = SessionLocal()
    try:
        watchlist_service.load(session)
        ensure_default_admin_key(session)
    finally:
        session.close()

    catalogue.refresh()
    stream_manager.reconcile()
    catalogue.start_background_refresh()

    def reconcile_loop():
        while True:
            time.sleep(config.CATALOGUE_REFRESH_INTERVAL_S)
            stream_manager.reconcile()
            _sync_camera_health()

    threading.Thread(target=reconcile_loop, name="stream-reconcile", daemon=True).start()

    def retention_loop():
        # Enforce the DPDP storage-limitation retention policy on a slow
        # interval (see db/retention.py). Runs once at startup too, so a
        # long-idle deployment purges promptly on restart.
        while True:
            try:
                session = SessionLocal()
                try:
                    purge_expired(session)
                    session_auth.purge_expired_sessions(session)
                finally:
                    session.close()
            except Exception:  # noqa: BLE001 — a purge failure must not kill the loop
                logger.exception("retention purge failed")
            time.sleep(config.RETENTION_SWEEP_INTERVAL_S)

    threading.Thread(target=retention_loop, name="retention-sweep", daemon=True).start()

    def federation_ingest_loop():
        # Model 3: pull both real, independently-formatted sources into
        # FederatedEvent on a slow poll (deliberately not a message bus —
        # see docs/models/model-3-vms-federation/RESEARCH.md). A fixed
        # early `since` re-scans each source in full every poll;
        # ingest_all()'s dedup logic makes that idempotent rather than
        # duplicating rows.
        since = dt.datetime(2000, 1, 1)
        while True:
            try:
                session = SessionLocal()
                try:
                    adapters = [SentinelAdapter(session)]
                    if os.path.exists(config.NYC_OPEN_DATA_FIXTURE_PATH):
                        adapters.append(NycOpenDataAdapter(config.NYC_OPEN_DATA_FIXTURE_PATH))
                    else:
                        logger.warning(
                            "Model 3 System-B fixture not found at %s — federation will "
                            "only ingest Sentinel's own data until it's present.",
                            config.NYC_OPEN_DATA_FIXTURE_PATH,
                        )
                    if os.path.exists(config.DEMO_PARTNER_FIXTURE_PATH):
                        adapters.append(DemoPartnerVmsAdapter(config.DEMO_PARTNER_FIXTURE_PATH))
                        logger.info(
                            "Model 3 System-C (SYNTHETIC demo_partner_vms) loaded from %s — "
                            "correlations involving it demonstrate the pipeline, not a real "
                            "cross-agency sighting.",
                            config.DEMO_PARTNER_FIXTURE_PATH,
                        )
                    inserted = ingest_all(session, adapters, since)
                    if inserted:
                        logger.info("federation ingest: %d new FederatedEvent row(s)", inserted)
                finally:
                    session.close()
            except Exception:  # noqa: BLE001 — an ingest failure must not kill the loop
                logger.exception("federation ingest failed")
            time.sleep(config.FEDERATION_INGEST_INTERVAL_S)

    threading.Thread(target=federation_ingest_loop, name="federation-ingest", daemon=True).start()

    if config.EXTERNAL_CAMERA_SOURCE_ENABLED:
        def external_camera_sync_loop():
            # Model 2's "unified viewer connecting >=2 different systems" —
            # syncs Caltrans D3's real public CCTV API into CameraRegistry
            # on a slow poll. Registry-only: never touches catalogue.py, so
            # StreamManager/the ANPR pipeline never attempts to open these
            # as RTSP streams (see external_camera_source.py).
            while True:
                try:
                    session = SessionLocal()
                    try:
                        n = external_camera_source.sync_into_registry(session)
                        logger.info("external camera source sync: %d camera(s) from %s", n, external_camera_source.SOURCE_LABEL)
                    finally:
                        session.close()
                except Exception:  # noqa: BLE001 — a sync failure must not kill the loop
                    logger.exception("external camera source sync failed")
                time.sleep(config.EXTERNAL_CAMERA_SOURCE_POLL_INTERVAL_S)

        threading.Thread(target=external_camera_sync_loop, name="external-camera-sync", daemon=True).start()
    else:
        logger.info("external camera source sync disabled (SENTINEL_EXTERNAL_CAMERA_SOURCE_ENABLED=false)")

    logger.info("Sentinel backend started. CDN host=%s stream host=%s", config.CDN_HOST, config.STREAM_HOST)


@app.get("/health")
def health():
    snapshot = stream_manager.health_snapshot()
    degraded_count = sum(1 for s in snapshot.values() if s["analytics_degraded"])
    return {
        # A worker count up with zero degraded is a real "ok"; a worker
        # count up with some/all degraded means streams are connected but
        # analytics is silently failing on them (found 2026-09-13) — do
        # not collapse that distinction into a single "ok" boolean.
        "status": "ok" if degraded_count == 0 else "degraded",
        # A count, not the camera-ID list — /health is unauthenticated by
        # design (basic liveness probe), so it shouldn't hand an anonymous
        # caller the actual camera inventory.
        "active_camera_worker_count": len(stream_manager.active_camera_ids),
        "analytics_degraded_camera_count": degraded_count,
        "catalogue_size": len(catalogue.cameras),
        # Real class names, not booleans — anything starting with "Stub" is
        # the honest no-op fallback (see main.py's _build_* functions).
        "analytics_components": ANALYTICS_COMPONENT_STATUS,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=config.API_HOST, port=config.API_PORT, reload=False)
