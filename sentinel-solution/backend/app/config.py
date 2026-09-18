"""Central configuration. Values are read from environment variables with
sane defaults so the service runs against the sandbox out of the box.

Per the Integrator's Guide, HLS and RTSP/WHEP are served from *different*
hosts: HLS rides the CDN (password-protected, works anywhere); RTSP/WHEP
carry raw TCP/UDP media that the CDN cannot proxy, so they're served
directly from the public static IP (or a dedicated non-proxied subdomain).
"""
import os

# CDN host — serves HLS + the camera catalogue, behind the access password
# issued by the Control Room "Request Feed Access" form.
CDN_HOST = os.environ.get("SENTINEL_CDN_HOST", "cctv.corp8.cloud")

# Public static IP (or dedicated non-proxied subdomain, e.g. stream.corp8.cloud)
# serving RTSP/WHEP directly — no Tailscale/device registration required.
STREAM_HOST = os.environ.get("SENTINEL_STREAM_HOST", "103.250.160.189")

CATALOGUE_URL = os.environ.get(
    "SENTINEL_CATALOGUE_URL", f"https://{CDN_HOST}/cameras.json"
)
RTSP_PORT = int(os.environ.get("SENTINEL_RTSP_PORT", "8554"))
WHEP_PORT = int(os.environ.get("SENTINEL_WHEP_PORT", "8889"))
WHEP_UDP_PORT = int(os.environ.get("SENTINEL_WHEP_UDP_PORT", "8189"))

# Access password issued by the Control Room registration form. Required for
# the CDN host (HLS + catalogue); sent as a bearer token / cookie depending
# on what the portal's auth flow turns out to expect — adjust
# `catalogue.py`'s request headers once you've inspected a real 401 response.
SENTINEL_ACCESS_TOKEN = os.environ.get("SENTINEL_ACCESS_TOKEN", "")

# The CDN login form (/auth/login) requires BOTH an email and the access
# password — sending password alone gets a silent 200 re-render of the login
# form, not an error, so this is easy to miss without inspecting the page.
SENTINEL_ACCESS_EMAIL = os.environ.get("SENTINEL_ACCESS_EMAIL", "")

# Reconnect policy (guide §3: start ~2s, cap ~30s, exponential backoff)
RECONNECT_INITIAL_DELAY_S = float(os.environ.get("RECONNECT_INITIAL_DELAY_S", "2"))
RECONNECT_MAX_DELAY_S = float(os.environ.get("RECONNECT_MAX_DELAY_S", "30"))
RECONNECT_BACKOFF_FACTOR = float(os.environ.get("RECONNECT_BACKOFF_FACTOR", "2"))
# OpenCV's FFmpeg backend otherwise permits a stalled RTSP socket to block
# VideoCapture.read() indefinitely, preventing the reconnect loop from ever
# running.  FFmpeg expects this value in microseconds.
RTSP_READ_TIMEOUT_US = int(os.environ.get("SENTINEL_RTSP_READ_TIMEOUT_US", "5000000"))

# How often to refresh the camera catalogue (ids/availability can change).
CATALOGUE_REFRESH_INTERVAL_S = float(os.environ.get("CATALOGUE_REFRESH_INTERVAL_S", "60"))

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./sentinel.db")

# CORS: defaults to the known Vite dev origins, not "*". Found by security
# review 2026-09-04 — a wildcard on a backend holding police investigative
# data is overly permissive; low-severity on its own today (the custom
# X-Sentinel-API-Key header isn't auto-attached cross-origin by browsers,
# so this wasn't an open door), but combined with any future credentialed
# auth it would be. Override with a comma-separated list for a real
# deployment's actual frontend origin(s).
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "SENTINEL_CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Evidence crops: the highest-confidence detection image for each sighting,
# saved to disk so the Vehicle Intelligence / Evidence UI can show a real
# image instead of a placeholder. Purged alongside their VehicleEvent row by
# the retention sweep (see db/retention.py).
CROPS_DIR = os.environ.get("SENTINEL_CROPS_DIR", "./data/crops")

# Analytics sampling — process every Nth frame per camera to keep CPU/GPU load
# bounded across many simultaneous cameras. Tune per hardware.
ANALYTICS_FRAME_STRIDE = int(os.environ.get("ANALYTICS_FRAME_STRIDE", "5"))

# Pretrained COCO weights — good enough for car/truck/bus/motorcycle/person
# out of the box (see analytics/detector.py); no fine-tuning needed for
# vehicle-class detection, unlike plate OCR.
YOLO_WEIGHTS = os.environ.get("SENTINEL_YOLO_WEIGHTS", "yolov8n.pt")

# Real trained plate localizer (analytics/plate_detector.py's
# YoloPlateDetector) — morsetechlab/yolov11-license-plate-detection, ONNX
# weights, AGPL-3.0 (accepted decision, see HLD.md §10). Not auto-downloaded
# like YOLO_WEIGHTS (not on the ultralytics hub) — fetch once with:
#   curl -sL -o weights/license-plate-finetune-v1n.onnx \
#     https://huggingface.co/morsetechlab/yolov11-license-plate-detection/resolve/main/license-plate-finetune-v1n.onnx
# If the file isn't present, main.py falls back to StubPlateDetector's
# heuristic crop, loudly, same honest-fallback pattern as the other models.
PLATE_DETECTOR_WEIGHTS = os.environ.get(
    "SENTINEL_PLATE_DETECTOR_WEIGHTS", "weights/license-plate-finetune-v1n.onnx"
)

# Low-confidence plate-read suppression (see analytics/pipeline.py): a fused
# plate confidence below this is treated as UNREAD — the vehicle is still
# logged anonymously by appearance/attributes, but the shaky plate string is
# withheld rather than spawning a false identity or false watchlist alert.
# 0.5 is a conservative default; tune against real footage.
PLATE_MIN_CONFIDENCE = float(os.environ.get("SENTINEL_PLATE_MIN_CONFIDENCE", "0.5"))

# Data-retention window (DPDP storage-limitation, see db/retention.py). Vehicle
# events/identities/alerts older than this are purged. Modelled on the UK
# National ANPR system's 12-month default (see RESEARCH_EXISTING_SYSTEMS.md);
# default here is shorter for a pilot. Audit logs are kept LONGER (see below)
# — the accountability trail should outlive the personal data it describes.
RETENTION_DAYS = int(os.environ.get("SENTINEL_RETENTION_DAYS", "30"))
AUDIT_RETENTION_DAYS = int(os.environ.get("SENTINEL_AUDIT_RETENTION_DAYS", "365"))
# Model 4 pilot metadata only: these classify event age for operator views;
# they do not provision warm/cold storage or override retention enforcement.
STORAGE_HOT_DAYS = int(os.environ.get("SENTINEL_STORAGE_HOT_DAYS", "15"))
STORAGE_WARM_DAYS = int(os.environ.get("SENTINEL_STORAGE_WARM_DAYS", "365"))
ANALYTICS_DENSITY_WINDOW_S = int(os.environ.get("SENTINEL_ANALYTICS_DENSITY_WINDOW_S", "60"))
# How often the purge job runs, in seconds (default 6h).
RETENTION_SWEEP_INTERVAL_S = float(os.environ.get("SENTINEL_RETENTION_SWEEP_INTERVAL_S", str(6 * 3600)))

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Model 1's gap-analysis "ageing-infrastructure" flag: a camera whose
# CameraRegistry.install_date is older than this many years is surfaced as
# "ageing" (routes_cameras.py's gap-analysis). 5 years is a common
# CCTV-hardware refresh-cycle assumption, not a Gujarat-Police-specified
# figure — override via env if a real departmental policy differs.
CAMERA_AGEING_THRESHOLD_YEARS = float(os.environ.get("SENTINEL_CAMERA_AGEING_THRESHOLD_YEARS", "5"))

# Named-anomaly-alert thresholds (see analytics/anomaly.py). Image-plane
# metrics only (no camera calibration — see VehicleEvent.direction_deg's
# docstring), so these are relative/tunable-per-deployment, not physical
# units with a universal "correct" value.
#
# A track's average direction must differ from the camera's configured
# expected_direction_deg by at least this many degrees to count as
# wrong-way (120, not 180, because within-camera direction estimates are
# noisy over a short track — requiring a near-exact opposite would miss
# real wrong-way vehicles that don't drive in a perfectly straight line).
WRONG_WAY_ANGLE_THRESHOLD_DEG = float(os.environ.get("SENTINEL_WRONG_WAY_ANGLE_THRESHOLD_DEG", "120"))
# Below this image-plane speed (px/s), a track is "basically stationary" —
# direction is meaningless noise at that point, not evidence of wrong-way
# travel, so wrong-way checks are skipped rather than flagging parked cars.
WRONG_WAY_MIN_SPEED_PX_S = float(os.environ.get("SENTINEL_WRONG_WAY_MIN_SPEED_PX_S", "3"))
# A track's dwell_time_s must exceed this, in a camera flagged
# is_restricted_zone, to raise a stopped-in-restricted-zone alert.
STOPPED_ZONE_DWELL_THRESHOLD_S = float(os.environ.get("SENTINEL_STOPPED_ZONE_DWELL_THRESHOLD_S", "30"))

# Model 3 (VMS Federation): two `FederatedEvent` rows with the same plate
# from different source_systems correlate if their observed_at timestamps
# fall within this window. 300s is a starting default for a polled,
# batch-style correlation pass (not real-time), not a spec-mandated value —
# tune per deployment. See analytics/federation.py and routes_federation.py.
FEDERATION_CORRELATION_WINDOW_S = float(os.environ.get("SENTINEL_FEDERATION_CORRELATION_WINDOW_S", "300"))

# Model 3's System B — a real, independent, public dataset (NYC Open
# Data's "Open Parking and Camera Violations"), NOT a second Gujarat
# departmental VMS (none is available to federate against — see
# docs/models/model-3-vms-federation/ARCHITECTURE.md). Path is relative to
# the backend process's working directory by default, matching this
# repo's other relative-path defaults (CROPS_DIR).
NYC_OPEN_DATA_FIXTURE_PATH = os.environ.get(
    "SENTINEL_NYC_OPEN_DATA_FIXTURE_PATH", "scripts/fixtures/nyc_open_parking_sample.csv"
)

# Model 3's System C — SYNTHETIC, hand-written partner sightings of plates
# Sentinel really read. Systems A and B share no plates (different countries),
# so without this the correlation engine can never run end-to-end against the
# live DB. Loaded under source_system="demo_partner_vms" so it is self-labelling
# everywhere it appears. Unset the var or delete the file to disable it — the
# adapter is skipped when the path doesn't exist, same as the NYC fixture. See
# scripts/fixtures/demo_partner_vms_seed.README.md.
DEMO_PARTNER_FIXTURE_PATH = os.environ.get(
    "SENTINEL_DEMO_PARTNER_FIXTURE_PATH", "scripts/fixtures/demo_partner_vms_seed.csv"
)

# How often the federation ingest loop polls both adapters (main.py). Both
# sources are re-scanned in full each poll (the NYC fixture is static, and
# Sentinel's own event volume is small at pilot scale) — ingest_all()'s
# dedup-by-key logic makes repeated full scans idempotent, so this doesn't
# create duplicate FederatedEvent rows.
FEDERATION_INGEST_INTERVAL_S = float(os.environ.get("SENTINEL_FEDERATION_INGEST_INTERVAL_S", "120"))

# Model 2's "unified viewer connecting >=2 different systems" — System B is
# Caltrans District 3's real, public, unauthenticated CCTV API (see
# external_camera_source.py). Off by default: this makes a real outbound
# network call, which must never happen implicitly during tests or a plain
# `python -m app.main` run. Enable explicitly for the two-system demo.
EXTERNAL_CAMERA_SOURCE_ENABLED = os.environ.get("SENTINEL_EXTERNAL_CAMERA_SOURCE_ENABLED", "false").lower() == "true"
EXTERNAL_CAMERA_SOURCE_URL = os.environ.get(
    "SENTINEL_EXTERNAL_CAMERA_SOURCE_URL", "https://cwwp2.dot.ca.gov/data/d3/cctv/cctvStatusD03.json"
)
# Bounded on purpose — this is a proof of direct multi-system integration
# for a Gujarat Police demo, not a real deployment onboarding all of
# Caltrans District 3's cameras.
EXTERNAL_CAMERA_SOURCE_MAX_CAMERAS = int(os.environ.get("SENTINEL_EXTERNAL_CAMERA_SOURCE_MAX_CAMERAS", "6"))
EXTERNAL_CAMERA_SOURCE_POLL_INTERVAL_S = float(os.environ.get("SENTINEL_EXTERNAL_CAMERA_SOURCE_POLL_INTERVAL_S", "300"))

# Rate limiting (api/rate_limit.py): requests per API key (or client IP)
# per 60s window, excluding /health and /live/* (high-frequency HLS
# polling). Generous default for a pilot with a handful of keys — this
# guards against runaway/abusive clients, not normal UI traffic.
RATE_LIMIT_PER_MINUTE = int(os.environ.get("SENTINEL_RATE_LIMIT_PER_MINUTE", "600"))

# ONVIF device discovery (streaming/onvif_discovery.py). Disabled by
# default: the sandbox exposes plain RTSP with no ONVIF endpoint, so
# probing it would just add a timeout delay to every catalogue refresh.
# catalogue.py falls back to the sandbox catalogue if no device responds.
ONVIF_DISCOVERY_ENABLED = os.environ.get("SENTINEL_ONVIF_ENABLED", "false").lower() == "true"
ONVIF_USERNAME = os.environ.get("SENTINEL_ONVIF_USERNAME", "")
ONVIF_PASSWORD = os.environ.get("SENTINEL_ONVIF_PASSWORD", "")
ONVIF_PROBE_TIMEOUT_S = float(os.environ.get("SENTINEL_ONVIF_PROBE_TIMEOUT_S", "3"))

# Recording-only scope: when set (comma-separated camera ids), restricts the
# live catalogue to just this subset — used to record the own-feed demo
# video against its actual 5-camera scenario without also surfacing the
# other real sandbox cameras this environment happens to have onboarded
# (DEMO_SCRIPT_OWN_FEED.md's guardrail: this submission must not present
# itself as a live-sandbox/all-cameras demo, that's a separate, still-
# blocked submission). Unset in normal operation — has zero effect then.
DEMO_CAMERA_SCOPE = {
    c.strip() for c in os.environ.get("SENTINEL_DEMO_CAMERA_SCOPE", "").split(",") if c.strip()
} or None

# --- Production-hardening scaffolds (2026-09-18) ---
# Everything below is IMPLEMENTED, UNVERIFIED per
# docs/PRODUCTION_MIGRATION_PLAN.md / docs/PRODUCTION_READINESS.md — no
# real Kafka broker, pgvector instance, or OIDC provider exists in this
# environment. All default OFF; the pilot's runtime behavior is
# unchanged unless a deployer explicitly opts in to each one.

# analytics/vector_search.py — pgvector ANN candidate search, an
# alternative to identity.py's brute-force cosine loop for the
# statewide-scale Re-ID problem SCALABILITY.md §2 names. Requires
# DATABASE_URL to be postgresql:// AND `CREATE EXTENSION vector` already
# run — vector_search.is_available() checks both at call time, this flag
# alone does not turn anything on.
VECTOR_SEARCH_ENABLED = os.environ.get("SENTINEL_VECTOR_SEARCH_ENABLED", "false").lower() == "true"

# analytics/kafka_bus.py — Kafka-backed alternative to Model 3's polled
# FederatedEvent table, for the "Regional rollout" phase in
# SCALABILITY.md §6. Not wired into main.py's default ingest loop.
FEDERATION_BUS_BACKEND = os.environ.get("SENTINEL_FEDERATION_BUS_BACKEND", "polled")  # "polled" | "kafka"
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("SENTINEL_KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_FEDERATION_TOPIC = os.environ.get("SENTINEL_KAFKA_FEDERATION_TOPIC", "sentinel.federation.events")
KAFKA_FEDERATION_CONSUMER_GROUP = os.environ.get("SENTINEL_KAFKA_FEDERATION_CONSUMER_GROUP", "sentinel-federation")

# api/sso_oidc.py — OIDC identity-federation, additive to auth.py's
# existing API-key model (PRODUCTION_MIGRATION_PLAN.md Phase 4). No
# route uses get_principal_oidc by default even when this is true; a
# route must explicitly depend on it.
SSO_OIDC_ENABLED = os.environ.get("SENTINEL_SSO_OIDC_ENABLED", "false").lower() == "true"
SSO_OIDC_ISSUER = os.environ.get("SENTINEL_SSO_OIDC_ISSUER", "")
SSO_OIDC_AUDIENCE = os.environ.get("SENTINEL_SSO_OIDC_AUDIENCE", "")
SSO_OIDC_JWKS_URL = os.environ.get("SENTINEL_SSO_OIDC_JWKS_URL", "")
SSO_OIDC_ROLE_CLAIM = os.environ.get("SENTINEL_SSO_OIDC_ROLE_CLAIM", "roles")
SSO_OIDC_DEPARTMENT_CLAIM = os.environ.get("SENTINEL_SSO_OIDC_DEPARTMENT_CLAIM", "department")
