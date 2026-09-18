from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class VehicleIdentity(Base):
    """A vehicle's identity across cameras — the thing movement history is
    actually built from, NOT the plate string directly.

    Starts anonymous (plate=None) if ANPR fails on first sighting, carrying
    only an appearance embedding. Gets upgraded to a real plate the moment
    ANY sighting linked to it produces a confident plate read — at which
    point every earlier anonymous sighting becomes part of that vehicle's
    plate history retroactively. See identity.py for the resolution logic
    and STRATEGY.md's "plate-first, appearance-second" principle.
    """

    __tablename__ = "vehicle_identity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # unique (not just indexed): each camera runs on its own thread, and two
    # cameras can finalize a sighting of the same plate within the same
    # processing window. Without a DB-enforced constraint, a check-then-insert
    # race can create two VehicleIdentity rows for one physical vehicle,
    # silently splitting its cross-camera history (see identity.py's
    # IntegrityError handling, which relies on this constraint existing).
    # NULL stays non-unique in SQLite/Postgres, so anonymous identities
    # (plate=None) are unaffected.
    plate = Column(String, unique=True, index=True, nullable=True)  # null until upgraded
    plate_confidence = Column(Float, nullable=True)
    embedding_json = Column(String, nullable=True)  # latest appearance embedding, as JSON floats
    first_seen_at = Column(DateTime, default=dt.datetime.utcnow)
    last_seen_at = Column(DateTime, default=dt.datetime.utcnow)
    # Which camera produced the most recent sighting — needed by
    # identity.py's geo-feasibility gate on appearance-only matches. Real
    # bug found by running the pipeline against continuous live sandbox
    # traffic (not synthetic data): without this, an identity drifted
    # across ~100 unrelated real vehicles across the state within 15
    # minutes, purely on colour-histogram similarity, because nothing
    # checked whether the candidate's last-known camera was even
    # physically reachable from the new sighting's camera.
    last_camera_id = Column(String, nullable=True)

    def set_embedding(self, embedding) -> None:
        self.embedding_json = json.dumps([round(float(x), 5) for x in embedding])

    def get_embedding(self):
        import numpy as np  # local import to avoid a hard numpy dep at module load

        if not self.embedding_json:
            return None
        return np.array(json.loads(self.embedding_json), dtype=np.float32)


class CameraRegistry(Base):
    """Model 1: Centralised CCTV Registry & GIS Mapping — metadata inventory,
    independent of whether a live stream is currently open for this camera."""

    __tablename__ = "camera_registry"

    id = Column(String, primary_key=True)  # matches catalogue camera id
    department = Column(String, nullable=True)
    location_name = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    vendor = Column(String, nullable=True)
    codec = Column(String, nullable=True)
    # PTZ / dome / fixed / bullet — Model 1's GIS map has no camera-type layer
    # without this (found in MODULE_GAP_ANALYSIS.md 2026-09-05). Free text,
    # not an enum: the catalogue/onboarding source doesn't constrain values
    # and rejecting an unrecognized vendor's own classification would be
    # worse than storing it as-is.
    camera_type = Column(String, nullable=True)
    onboarded_at = Column(DateTime, default=dt.datetime.utcnow)
    last_seen_live_at = Column(DateTime, nullable=True)
    # No default: a freshly-onboarded camera hasn't been confirmed live yet,
    # so its health is genuinely unknown — defaulting to True would claim a
    # health status we have no evidence for. Only main.py's health-sync loop
    # (backed by the real RTSP worker's connection state) ever sets this.
    is_healthy = Column(Boolean, nullable=True, default=None)
    # Separate from is_healthy on purpose (found 2026-09-13): is_healthy
    # only reflects RTSP stream connectivity. A real torch/torchvision ABI
    # mismatch made the analytics pipeline fail on every frame while the
    # stream itself stayed connected the whole time, so is_healthy alone
    # can mask a camera that is receiving frames but producing zero
    # detections. See streaming/manager.py's ANALYTICS_DEGRADED_ERROR_THRESHOLD.
    analytics_degraded = Column(Boolean, nullable=True, default=None)
    last_analytics_success_at = Column(DateTime, nullable=True)

    # Maintenance status (Model 1 deliverable — REQUIREMENTS_COVERAGE.md
    # flagged this as the one open gap in "health/maintenance-status
    # monitoring": is_healthy/analytics_degraded describe OBSERVED stream/
    # analytics state, not a human decision that a camera is deliberately
    # offline for servicing. Without this, a camera pulled down for repair
    # looks identical to one that's actually broken/failed — see
    # routes_cameras.py's gap-analysis, which now excludes an
    # under_maintenance camera from the "unhealthy" (unexpected-failure)
    # list rather than reporting it as a real gap. Set only via
    # POST /cameras/{id}/maintenance (admin-only), never inferred.
    under_maintenance = Column(Boolean, nullable=False, default=False)
    maintenance_reason = Column(String, nullable=True)
    maintenance_until = Column(DateTime, nullable=True)

    # Deregistration — distinct from under_maintenance (temporary, expected
    # to come back) and from actually deleting the row (never done: this
    # camera's id may already be the camera_id on real VehicleEvent/Alert
    # evidence rows, and CLAUDE.md's evidence-preservation stance forbids
    # dropping/rewriting that — see db/session.py's migration comments on
    # treating sentinel.db as valuable state). Deregistering a camera means
    # "no longer an active part of this deployment" (decommissioned,
    # returned to the vendor, department opted out) while keeping its
    # registry row, audit trail, and any historical events/alerts intact
    # and queryable. Re-registering (POST /cameras/{id}/register) clears
    # this back to active without needing a fresh onboard call. Set only
    # via POST /cameras/{id}/deregister|register (admin-only), never
    # inferred from health/liveness signals.
    deregistered = Column(Boolean, nullable=False, default=False)
    deregistered_reason = Column(String, nullable=True)
    deregistered_at = Column(DateTime, nullable=True)

    # Named-anomaly-alert config (see analytics/anomaly.py). Both opt-in,
    # per-camera, set at onboarding time — a camera with neither set never
    # produces anomaly alerts, only watchlist ones, same as before this
    # feature existed.
    is_restricted_zone = Column(Boolean, nullable=False, default=False)
    # Image-plane direction (0=right, 90=down, 180=left, 270=up, same
    # convention as VehicleEvent.direction_deg) that a vehicle moving WITH
    # traffic flow at this camera should point — NOT a compass bearing, see
    # VehicleEvent.direction_deg's docstring for why. Null = wrong-way
    # detection disabled for this camera (no ground truth to compare against).
    expected_direction_deg = Column(Float, nullable=True)

    # Ageing-infrastructure tracking (Model 1 deliverable, found missing in
    # MODULE_GAP_ANALYSIS.md 2026-09-05 — "no install-date field"). Nullable:
    # the catalogue/onboarding source has no install-date of its own, so this
    # is only ever populated when a human enters it (manual onboarding form
    # or a bulk-edit), same honesty stance as camera_type above.
    install_date = Column(DateTime, nullable=True)
    # GIS map coverage-radius layer (Model 1 deliverable — "Coverage-radius/
    # zone GIS map layer" was point-markers-only before this). Metres,
    # nullable: an un-set radius means "unknown," not "zero coverage" — the
    # map renders no circle for it rather than a misleading dot-sized one.
    coverage_radius_m = Column(Float, nullable=True)

    # Homography calibration (analytics/calibration.py) — turns
    # VehicleEvent.speed_px_per_s's honest image-plane number into a real
    # km/h for investigators, WITHOUT changing the anomaly thresholds in
    # config.py (those stay tuned in px/s terms; see anomaly.py). NULL
    # until an admin submits >=4 real surveyed point correspondences via
    # POST /cameras/{id}/calibration — never fabricated, never inferred
    # from image content. A 3x3 JSON matrix, not raw point pairs: the
    # points themselves aren't needed at inference time, only the fitted
    # transform.
    homography_json = Column(String, nullable=True)
    homography_calibrated_at = Column(DateTime, nullable=True)
    # Free text describing how/against what reference the survey points
    # were measured (e.g. "IRC 086:2018 3.5m lane width, 4-point manual
    # survey 2026-09-18") — shown to investigators alongside speed_kmh so a
    # calibrated speed is never presented without its provenance.
    homography_reference_note = Column(String, nullable=True)

    # Model 2's "unified viewer connecting >=2 different systems" —
    # NULL means this row is a real Gujarat sandbox camera; a non-null
    # value (e.g. "caltrans_d3_public_api") marks it as onboarded from a
    # genuinely independent external system (see external_camera_source.py).
    # StreamManager/the ANPR pipeline only ever reads from catalogue.py's
    # CatalogueClient, never from this column, so an external row can never
    # be mistaken for a live RTSP-analyzable Gujarat camera.
    source_system = Column(String, nullable=True)
    # Direct image URL for an external, snapshot-only (not continuous
    # video) source. The frontend must render this as a periodically-
    # refreshed still image with an explicit "external / snapshot" label,
    # never inside the same live-HLS <video> tile used for sandbox cameras
    # (CLAUDE.md 24.11 — a polished UI must not conceal a truthful
    # distinction in feed type).
    snapshot_image_url = Column(String, nullable=True)


class VehicleEvent(Base):
    """One sighting of a vehicle at a camera/time — the raw material for
    cross-camera movement history (Model 2).

    `plate` is nullable: when ANPR can't produce a confident read (bad
    angle, glare, motion blur), the vehicle is still logged by its visual
    attributes (colour, type, dimensions) so it isn't invisible to
    investigators — see routes_vehicle.py's search-by-attributes fallback.
    """

    __tablename__ = "vehicle_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identity_id = Column(Integer, ForeignKey("vehicle_identity.id"), nullable=False)
    plate = Column(String, index=True, nullable=True)
    plate_confidence = Column(Float, nullable=True)
    camera_id = Column(String, ForeignKey("camera_registry.id"), nullable=False)
    pts_ms = Column(Float, nullable=False)  # stream-relative PTS, not wall clock
    observed_at = Column(DateTime, default=dt.datetime.utcnow)  # wall clock for display only
    # Separate from observed_at so a future queued/batched ingestion path
    # (SCALABILITY.md's regional event bus) can tell "seen at" apart from
    # "landed in this DB" — the two coincide today (row is written
    # immediately after resolution) but the column already exists for when
    # they don't. Matches FederatedEvent's observed_at/ingested_at split.
    ingested_at = Column(DateTime, default=dt.datetime.utcnow)
    # Pilot metadata only. The API recomputes the current tier from age so a
    # row cannot remain "hot" forever; this stored initial value preserves
    # what was assigned when the event entered Sentinel.
    storage_tier = Column(String, nullable=True, default="hot")
    confidence = Column(Float, nullable=True)  # detector confidence

    vehicle_type = Column(String, nullable=True)  # car / truck / bus / motorcycle
    color = Column(String, nullable=True)
    color_confidence = Column(Float, nullable=True)
    width_px = Column(Integer, nullable=True)
    height_px = Column(Integer, nullable=True)
    aspect_ratio = Column(Float, nullable=True)
    make_model = Column(String, nullable=True)  # usually null — see attributes.py
    make_model_confidence = Column(Float, nullable=True)

    # Motion attributes derived from the within-camera track's bbox path over
    # PTS (see tracker.py) — the "analytics beyond ANPR" beat, inspired by
    # BriefCam's searchable speed/dwell/direction (see
    # ../../RESEARCH_EXISTING_SYSTEMS.md). IMPORTANT: these are IMAGE-PLANE
    # metrics — pixels/second and screen-space direction — NOT calibrated
    # real-world km/h or compass bearing. Without per-camera homography
    # calibration (out of scope), they're relative indicators (is this
    # vehicle moving fast? stopped? which way across frame?), useful for
    # "stopped in restricted zone" / "wrong-way" style filters but not a
    # speeding ticket. Named *_px_per_s / *_deg to keep that honest.
    dwell_time_s = Column(Float, nullable=True)  # how long the vehicle was tracked in this camera's view
    speed_px_per_s = Column(Float, nullable=True)  # bbox-centre displacement / elapsed PTS
    direction_deg = Column(Float, nullable=True)  # 0=right, 90=down, 180=left, 270=up (image coords)
    # Real-world speed (analytics/calibration.py), NOT derived from
    # speed_px_per_s by a unit conversion — recomputed from the same bbox
    # centres through the camera's homography. NULL for every event unless
    # CameraRegistry.homography_json was already set for this camera_id at
    # finalize time (most events, for the foreseeable pilot — most cameras
    # are never surveyed). Never backfilled retroactively if a camera gets
    # calibrated later, matching this project's append-only evidence stance
    # (CLAUDE.md 24.4): a later calibration only affects events after it.
    speed_kmh = Column(Float, nullable=True)

    # How THIS sighting got attached to its identity_id — the raw material
    # for the "why was this vehicle linked?" explainability panel. Captured
    # at resolve-time in identity.py because the match decision (embedding
    # similarity against whichever identity was live at that moment) can't
    # be reconstructed later: VehicleIdentity only keeps its latest
    # embedding, not a history of what it looked like at each past match.
    link_method = Column(String, nullable=True)
    # "new_identity" | "plate_continuation" | "plate_upgrade" | "appearance_match"
    link_score = Column(Float, nullable=True)  # cosine similarity, only set for appearance_match
    link_time_gap_s = Column(Float, nullable=True)  # seconds since the identity's previous sighting

    # Evidence: the highest-confidence detection crop for this sighting,
    # saved to disk at finalize time (see pipeline.py), plus the bbox it was
    # taken from (image-plane pixel coords, NOT geo coords) so a UI can draw
    # the detection box over the crop. Nullable: older rows predate this
    # column and simply have no stored evidence image.
    crop_path = Column(String, nullable=True)
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)
    bbox_x2 = Column(Float, nullable=True)
    bbox_y2 = Column(Float, nullable=True)

    camera = relationship("CameraRegistry")
    identity = relationship("VehicleIdentity")


class CameraDensityWindow(Base):
    """Real sampled-frame object counts for one camera/time bucket.

    Counts are detector outputs, not unique people/vehicles or a crowd-size
    estimate.  That distinction is deliberate: no crowd-density threshold or
    biometric identification is inferred by this pilot capability.
    """

    __tablename__ = "camera_density_window"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String, ForeignKey("camera_registry.id"), nullable=False, index=True)
    window_started_at = Column(DateTime, nullable=False, index=True)
    window_seconds = Column(Integer, nullable=False)
    sampled_frames = Column(Integer, nullable=False, default=0)
    vehicle_detections = Column(Integer, nullable=False, default=0)
    person_detections = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)


class WatchlistEntry(Base):
    """Stolen vehicles / blacklisted plates for cross-referencing."""

    __tablename__ = "watchlist_entry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate = Column(String, unique=True, index=True, nullable=False)
    reason = Column(String, nullable=False)  # "stolen", "wanted", "blacklisted", ...
    added_at = Column(DateTime, default=dt.datetime.utcnow)


class AuditLog(Base):
    """Every investigative query is purpose-bound and logged — DPDP-oriented
    governance: who queried what, for which case, and why."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    purpose = Column(String, nullable=False)  # e.g. "stolen_vehicle_investigation"
    case_id = Column(String, nullable=True)
    query = Column(String, nullable=False)  # e.g. the plate searched
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class CameraAuditLog(Base):
    """Model 1's registry deliverable includes an audit trail — the
    existing `AuditLog` is purpose-bound investigative *queries*
    (vehicle-search), a different concept from "who onboarded/edited which
    camera's metadata." Found missing entirely in TASKS.md's P3 list
    (2026-09-05). Separate table rather than overloading AuditLog's
    purpose/case_id columns, which don't apply to a registry edit."""

    __tablename__ = "camera_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # "onboarded" | "updated"
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class FederatedEvent(Base):
    """Model 3: normalized landing zone for events pulled from any
    `VMSAdapter` (see analytics/federation.py) — the "metadata exchange
    bus" deliverable, implemented as a polled table rather than Kafka/
    RabbitMQ (deliberate pilot-scale decision, see
    docs/models/model-3-vms-federation/RESEARCH.md). `source_system`
    distinguishes Sentinel's own real data ("sentinel") from the real,
    independent NYC Open Data public dataset ("nyc_open_data") used as
    Model 3's second federated source — NOT a second Gujarat departmental
    VMS, see federation.py's module docstring for the honesty caveat.
    """

    __tablename__ = "federated_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_system = Column(String, nullable=False, index=True)
    plate = Column(String, nullable=False, index=True)
    observed_at = Column(DateTime, nullable=False)
    camera_id = Column(String, nullable=False)
    raw_payload_json = Column(String, nullable=True)
    ingested_at = Column(DateTime, default=dt.datetime.utcnow)


class ApiKeyEntry(Base):
    """Model 1 explicitly requires 'department-wise RBAC' as a deliverable,
    not a bonus — this is the minimal real implementation of that: an API
    key maps to a user + a role, and routes declare which roles they accept
    (see api/auth.py). Not a stub: keys actually gate access below.

    Keys are stored hashed (sha256) so the DB file itself doesn't hand out
    working credentials if it leaks — matches the project's "purpose-bound
    audited queries" governance story actually having teeth.
    """

    __tablename__ = "api_key"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "admin" | "investigator" | "viewer"
    department = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class SessionToken(Base):
    """Production-hardening addition (2026-09-18, `SEC-4` in
    `docs/REVIEW_FINDINGS.md` / Phase 4 of
    `docs/PRODUCTION_MIGRATION_PLAN.md`) — an httpOnly-cookie session,
    additive to `ApiKeyEntry`'s header-key model, not a replacement.
    `api/auth.py`'s `get_principal` and every existing route/test are
    unchanged; this is a second, opt-in authentication path
    (`api/session_auth.py`).

    Mints from an already-valid API key (`POST /auth/session/login`), so
    it inherits that key's user_id/role/department rather than
    duplicating the "who is this" decision in two places. Stored hashed,
    same discipline as `ApiKeyEntry.key_hash` — a DB leak must not hand
    out a working session any more than it hands out a working API key.
    """

    __tablename__ = "session_token"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_hash = Column(String, unique=True, index=True, nullable=False)
    csrf_token = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    department = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


# Governed alert lifecycle (Palantir-Gotham-inspired entity lifecycle — see
# ../../COMPETITIVE_TEARDOWN.md §A). An alert is a live investigation item,
# not a fire-and-forget log line: it moves through explicit states, and only
# these transitions are allowed (enforced in routes_alerts.py, not just
# convention). "dismissed" is the false-positive terminal — a first-class
# state precisely because "AI output is a lead, not evidence" (HLD §6): an
# investigator marking a hit as a false positive is a real, auditable action,
# not an absence of one.
ALERT_STATUS_NEW = "new"
ALERT_STATUS_ACKNOWLEDGED = "acknowledged"
ALERT_STATUS_RESOLVED = "resolved"          # genuine hit, action taken
ALERT_STATUS_DISMISSED = "dismissed"        # false positive
ALERT_STATUSES = (
    ALERT_STATUS_NEW,
    ALERT_STATUS_ACKNOWLEDGED,
    ALERT_STATUS_RESOLVED,
    ALERT_STATUS_DISMISSED,
)
# from-state -> set of allowed next states. Terminal states map to empty set.
ALERT_TRANSITIONS = {
    ALERT_STATUS_NEW: {ALERT_STATUS_ACKNOWLEDGED, ALERT_STATUS_DISMISSED},
    ALERT_STATUS_ACKNOWLEDGED: {ALERT_STATUS_RESOLVED, ALERT_STATUS_DISMISSED},
    ALERT_STATUS_RESOLVED: set(),
    ALERT_STATUS_DISMISSED: set(),
}


class Alert(Base):
    """Emitted the moment a VehicleEvent's plate matches a WatchlistEntry.

    Carries a governed lifecycle `status` (see ALERT_TRANSITIONS above), not
    just a boolean — this is what makes it an investigation item an operator
    works, and is the concrete form of the "explainable, human-in-the-loop"
    intelligence layer (HLD §6). The legacy `acknowledged` boolean is kept in
    sync (True once status leaves "new") so existing clients don't break."""

    __tablename__ = "alert"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # NOT NULL by original design (watchlist alerts always have a matched
    # plate). Named-anomaly alerts (see analytics/anomaly.py) can fire on a
    # vehicle whose plate was never read at this camera — per this
    # project's "ANPR failure must not mean tracking failure" principle,
    # the vehicle is still a specific, trackable identity, so we surface it
    # as "UNREAD#<identity_id>" rather than requiring a plate the anomaly
    # logic has no way to guarantee.
    plate = Column(String, index=True, nullable=False)
    camera_id = Column(String, ForeignKey("camera_registry.id"), nullable=False)
    reason = Column(String, nullable=False)
    # "watchlist" (original, default — legacy rows predate this column) |
    # "wrong_way" | "stopped_restricted_zone". Lets the UI badge/filter
    # anomaly alerts separately from watchlist hits without overloading
    # `reason`'s free-text meaning.
    alert_type = Column(String, nullable=False, default="watchlist")
    vehicle_event_id = Column(Integer, ForeignKey("vehicle_event.id"), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
    status = Column(String, default=ALERT_STATUS_NEW, nullable=False)
    # Who moved it to its current status, and when — the accountability trail
    # for the action, mirroring AuditLog's purpose-bound logging ethos.
    status_updated_by = Column(String, nullable=True)
    status_updated_at = Column(DateTime, nullable=True)
    # Evidence class of the VehicleEvent that triggered this alert, snapshotted
    # at raise time (see analytics/evidence_class.py). Nullable: legacy alerts
    # predate this column and anomaly alerts don't carry a plate read at all.
    # Persisted rather than re-derived on read so the UI never has to trust a
    # client-side recomputation of a safety-relevant label.
    evidence_class = Column(String, nullable=True)
    evidence_class_reason = Column(String, nullable=True)

    camera = relationship("CameraRegistry")
