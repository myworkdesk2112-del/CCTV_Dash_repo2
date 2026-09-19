# Sentinel Solution Scaffold — Model 1 + Model 2

Backend scaffold for the Gujarat Police Innovation Challenge 2026 ("Sentinel").
Implements **Model 1 (Centralised CCTV Registry & GIS Foundation, mandatory)**
paired with **Model 2 (Unified Viewing & Metadata Analytics)** — direct
RTSP/catalogue integration, no middleware layer, per the problem statement.

Full challenge details: `../docs/hackathon/HACKATHON_DETAILS.md`. Submission documents:
`docs/HLD.md` (Technical Proposal) and `docs/SCALABILITY.md` (Plan for Scale).

## Architecture

```
backend/app/
  config.py              # env-driven config, placeholder <host>
  catalogue.py            # polls cctv.corp8.cloud/cameras.json, never hardcodes camera URLs
  streaming/
    rtsp_client.py         # per-camera worker: TCP-forced RTSP, PTS timing,
                            # reconnect w/ backoff, discontinuity detection
    manager.py              # opens/closes workers to match live catalogue
  analytics/
    detector.py             # pluggable vehicle detector (stub + YOLOv8 seam)
    plate_detector.py        # vehicle crop -> plate region -> enhance (stub
                              # heuristic crop + CLAHE, real YOLO plate seam)
    anpr.py                   # pluggable plate reader (stub + PaddleOCR seam)
    attributes.py               # colour/type/dimensions — always captured,
                                 # the fallback identifier when ANPR fails
    reid.py                       # appearance embedding (working colour-
                                   # histogram encoder + FastReID seam) —
                                   # what carries identity when ANPR fails
    tracker.py                      # real ByteTrack (via ultralytics), one
                                     # persistent tracker per camera, with
                                     # IOU-overlap fallback — groups
                                     # detections across sampled frames into
                                     # one sighting
    identity.py                       # cross-camera identity resolution:
                                       # anonymous tracks upgraded to a plate
                                       # the moment ANY sighting reads one
    geo.py                            # geo-temporal route reconstruction:
                                       # OBSERVED sightings + honestly-labelled
                                       # INFERRED camera-less segments (haversine
                                       # distance + time feasibility)
    pipeline.py                         # frame -> detect -> plate region ->
                                         # enhance -> OCR -> tracker (temporal
                                         # fusion) -> Re-ID -> identity ->
                                         # persist -> alert
  watchlist/
    service.py                # in-memory watchlist cache + alert emission
  db/
    models.py                  # CameraRegistry, VehicleEvent, Watchlist, Alert
    session.py                  # SQLAlchemy engine/session (SQLite by default)
  api/
    routes_cameras.py            # Model 1: registry listing
    routes_vehicle.py             # GET /vehicle/{plate}/history — the core
                                   # evaluation ask: timestamped movement history
    routes_watchlist.py            # add/list watchlist entries
    routes_alerts.py                # live alert feed
  main.py                          # wires it all together, FastAPI app
```

## Why it's built this way

Every rule in the sandbox integration guide (`../docs/hackathon/HACKATHON_DETAILS.md` §13)
is encoded directly in `streaming/rtsp_client.py`:

- RTSP is forced over TCP (`OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`).
- Timing never touches `CAP_PROP_FPS` or wall-clock arrival — every frame
  carries its `pts_ms` from `CAP_PROP_POS_MSEC`, so downstream trackers can
  compute correct velocities/dwell times.
- Reconnects use exponential backoff (2s → 30s cap), never a tight loop.
- A short run of read failures is treated as a normal decoder warning
  (H.264/H.265 IDR wait), not an immediate disconnect.
- PTS going backward is flagged as a `discontinuity` (the sandbox's
  recording loop point) so re-identification/tracking state can be reset
  instead of producing garbage across the cut.
- Cameras are discovered exclusively from `https://cctv.corp8.cloud/cameras.json`,
  polled on an interval, and workers are opened/closed to match — nothing is
  hardcoded, and idle cameras aren't held open ("pace your load").
- RTSP/WHEP are opened directly against the public IP (`103.250.160.189`),
  not the CDN host — the CDN only fronts HLS + the catalogue, since it can't
  proxy raw TCP/UDP media. See `HACKATHON_DETAILS.md` §13a for the full,
  authoritative endpoint spec.

## Running locally

**Windows one-shot:** run `setup.bat` from the repository root instead of the
steps below — it creates `backend/.venv`, installs into it (never the global
interpreter), seeds `.env` from `.env.example` without overwriting an existing
one, runs the test suite as an install check, and installs frontend deps.
`setup.bat --with-ml` adds the real YOLOv8/PaddleOCR stack; `setup.bat
--backend` skips the frontend. Safe to re-run.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt

# Optional but recommended: real YOLOv8 detection + real PaddleOCR ANPR.
# Without this, main.py falls back to the honest no-op stubs (loud warning
# at startup, no detections/plates ever produced) — the service still runs.
pip install -r requirements-ml.txt

# Fill in the real sandbox host + access token once granted
cp ../.env.example ../.env
# edit ../.env, then export into the shell, e.g.:
set SENTINEL_CDN_HOST=cctv.corp8.cloud
set SENTINEL_STREAM_HOST=103.250.160.189
set SENTINEL_ACCESS_TOKEN=<password from Control Room "Request Feed Access">

python -m app.main
```

**Never `pip install` this project's dependencies into a shared/global
Python environment** (e.g. an IDE's or agent's own venv) — `ultralytics`
(torch) and `paddleocr` (paddlepaddle) pull in large, version-sensitive
dependency trees (numpy, protobuf, opencv variants) that will silently
downgrade packages another tool relies on. Always use this project's own
`backend/.venv`.

Every endpoint except `/health` requires an `X-Sentinel-API-Key` header
(see "RBAC" below). On first startup with no keys in the DB, a bootstrap
admin key is minted and logged once — copy it from the startup log.

Then:
- `GET http://localhost:8000/health` — active camera workers + catalogue size (no auth)
- `GET http://localhost:8000/cameras` — Model 1 registry view (viewer+)
- `GET http://localhost:8000/cameras/gap-analysis` — Model 1 gap-analysis report (investigator+)
- `POST http://localhost:8000/cameras` / `/cameras/bulk` — onboarding (admin)
- `GET http://localhost:8000/vehicle/GJ01AB1234/history?purpose=...` — movement history (investigator+)
- `POST http://localhost:8000/watchlist` `{"plate": "GJ01AB1234", "reason": "stolen"}` (admin)
- `GET http://localhost:8000/alerts` — live alert feed (investigator+)
- `POST http://localhost:8000/auth/api-keys` — provision a key for another role (admin)
- `GET http://localhost:8000/evidence/event/{id}/verify` — recompute the stored
  crop's SHA-256 and compare it to the hash taken at write time (viewer+;
  deliberately **not** gated on evidence class — checking whether an image was
  altered is an integrity question, and an investigator assessing a LEAD_ONLY
  lead is entitled to the answer)
- `GET http://localhost:8000/evidence/event/{id}/package?purpose=...` — the
  §63-oriented provenance package: write-time hash, production method
  (which detector/OCR actually ran), device and owning department, and the
  access/export audit trail (investigator+, **CONFIRMED tier only**)
- `GET http://localhost:8000/evidence/event/{id}/certificate.pdf?purpose=...` —
  the same package as a printable Part A/Part B form (investigator+,
  CONFIRMED only)

## RBAC

Model 1 explicitly lists "department-wise RBAC" as a required deliverable,
not a bonus. `api/auth.py` implements a real (if minimal) role system: an
API key hashes to a row in `ApiKeyEntry` mapping to one of `viewer` <
`investigator` < `admin`. Every route declares the minimum role it accepts
via `Depends(require_role(...))`; a request with a missing or wrong-role
key gets a real 401/403, not a logged-and-allowed pass-through. Purpose-
bound audit logging (`AuditLog.user_id`) now comes from the authenticated
key, not a client-supplied string — an earlier version trusted a
self-reported `user_id`, which made the audit trail spoofable; that's
fixed. Provision more keys via `POST /auth/api-keys` (admin-only).

**Department-scoped access control — done 2026-09-05.** `api/auth.py`'s
`department_scope()`: a non-admin key tied to a department (`ApiKeyEntry.
department`) only sees that department's cameras (`GET /cameras`, `GET
/cameras/{id}`, `GET /cameras/export.csv`, `GET /cameras/gap-analysis` all
consistently scoped); admin keys and keys with no department set stay
unrestricted. Deliberately does **not** scope vehicle search/movement
history — cross-department correlation is this project's core
differentiator (STRATEGY.md), and restricting an investigator's plate
search to their own department's cameras would defeat exactly the feature
that makes cross-department vehicle tracking possible. Verified with 5 new
pytest tests (`tests/test_rbac_department_scope.py`) and real HTTP calls
across two department-scoped keys.

## ANPR failure does not mean tracking failure

Core design principle (see STRATEGY.md): a vehicle is never discarded just
because a plate can't be read on any given camera.

```
Camera detects vehicle -> plate unreadable
        v
Vehicle logged anyway: colour + type + dimensions + appearance embedding
        v
Cross-camera identity resolver (identity.py) matches it by appearance to
the same vehicle at the next camera (or the previous one)
        v
The moment ANY camera along the route reads the plate, the WHOLE chain —
including the earlier anonymous sightings — resolves to that plate
```

Verified end-to-end with a real (non-mocked) run: two cameras with
deliberately unreadable plates, a third where ANPR succeeds — all three
sightings correctly merge into one `VehicleIdentity`, and
`GET /vehicle/{plate}/history` returns all three, including the two
anonymous ones, not just the one where OCR worked.

`GET /vehicle/search-by-attributes` is the fallback when a plate is *never*
read anywhere: search by colour + vehicle type + partial plate instead.

## Real models are wired in (with honest fallback)

`main.py` now constructs `YoloVehicleDetector` (pretrained COCO
`yolov8n.pt`, auto-downloaded) and `PaddleOcrPlateReader` (pinned
`paddleocr==2.9.1`) by default, falling back to the no-op stubs — loudly,
via a startup warning naming the missing dependency — if `requirements-ml.txt`
isn't installed. Verified end-to-end (not just import-checked): a real
composited frame (real YOLO detection + a pasted synthetic plate) round-trips
through detect → locate plate → enhance → OCR → tracker fusion → identity →
persist with the actual read plate text and >0.5 confidence; a genuinely
blank plate region correctly produces `plate=None` with the vehicle still
logged by attributes, not silently dropped.

Two real bugs were caught and fixed by that verification, not by inspection:
- `main.py` referenced a nonexistent `config.SENTINEL_HOST` — the app
  couldn't start at all before this was fixed.
- `anpr.py` crashed (`TypeError: 'NoneType' object is not iterable`) when
  PaddleOCR finds no text at all, because it returns `[None]` for that
  image, not `[]]` — only surfaces when a real plate is genuinely
  unreadable, which is exactly the case STRATEGY.md's "ANPR failure ≠
  tracking failure" principle depends on working correctly.

**Windows-specific**: build the YOLO detector before the PaddleOCR reader
in the same process — see `main.py`'s `_detector`/`_plate_reader` comment
and `requirements-ml.txt` for why (a real, reproduced DLL-loading conflict
between torch and paddlepaddle, not theoretical).

- **`analytics/detector.py`** — `YoloVehicleDetector` needs no fine-tuning:
  COCO's `car`/`truck`/`bus`/`motorcycle`/`person` classes are exactly what's
  needed, verified against a real photo.
- **`analytics/anpr.py`** — `PaddleOcrPlateReader` reads clean/synthetic
  plate text with >99% confidence when preprocessing (localization +
  enhancement) puts a legible crop in front of it. **Real Indian-plate
  accuracy now measured, not just untested (2026-09-05):** against a real
  close-range sandbox camera (`cam06`), 8/13 real frames of one vehicle's
  track produced a pattern-valid plate read, after fixing a real bug where
  two-line plates (state+RTO on one line, series+number on the next —
  common on two/three-wheelers) were never joined before pattern-matching
  (`_ambiguous_variants`/`_best_pattern_match`, with bounded homoglyph
  correction for OCR's 0/O, 5/S, 1/I, 8/B, 2/Z confusion). See `HLD.md` §3
  for the full writeup, including the still-open gap: `tracker.py`'s
  exact-string consensus voting doesn't yet reconcile the frame-to-frame
  character variance into one confident final read.
- **`analytics/plate_detector.py`** — `StubPlateDetector`'s crude heuristic
  crop (lower-middle third of the vehicle) has been replaced with a real
  trained localizer, `YoloPlateDetector` (morsetechlab YOLOv11 ONNX
  weights, AGPL-3.0 — an accepted, documented licensing decision, see
  `HLD.md` §10), wired into `main.py` as the default as of 2026-09-05.
- **`analytics/reid.py`** — `ColorHistogramEncoder` is real and working
  (not a stub) but not state-of-the-art. `FastReIdEncoder` (pretrained on
  VeRi-776) is the documented upgrade if training/deployment time allows.
- **`analytics/attributes.py`** — `StubMakeModelClassifier` always returns
  `None`. No open-source model classifies Indian-market vehicle make/model
  out of the box (closest public datasets are US/China-market); left as an
  honest gap rather than a fake result.
- **GIS mapping (Model 1)** — `CameraRegistry` has `latitude`/`longitude`
  columns; the `frontend/` app renders them on a Leaflet map. The catalogue
  itself doesn't return coordinates (see `catalogue.py`'s `CameraInfo.from_api`),
  so real cameras need either manual onboarding (`POST /cameras`, or the
  "Registry Ops" tab's form) or the bulk-import API. `scripts/
  onboard_from_catalogue.py` bulk-tags real sandbox cameras by
  keyword-inferred department — **not yet run against the real sandbox**
  (no access token configured in this environment); review its output
  before trusting the department assignments.
- **Live view is HLS only, not WHEP** — `frontend/src/components/LiveView.jsx`
  plays a camera's feed via a new backend proxy (`api/routes_stream.py`)
  that relays the CDN's password-gated HLS through the session
  `catalogue.py` already holds, since a browser can't hold that session
  cookie itself. WHEP (lower-latency WebRTC preview) is NOT wired up — it
  needs a full RTCPeerConnection/SDP offer-answer client, which wasn't built
  this pass. HLS-via-proxy is the working path; don't claim WHEP preview
  works.
- **Within-camera tracking now uses real ByteTrack** (bonus criterion) —
  `analytics/detector.py`'s `YoloVehicleDetector` calls Ultralytics'
  built-in `model.track(tracker="bytetrack.yaml")`, one persistent
  instance per camera (ByteTrack's Kalman-filter state isn't safe to share
  across concurrent streams). Verified end-to-end: stable track IDs across
  repeated frames, correct per-camera isolation, correct reset on scene
  discontinuity. IOU-overlap matching remains as the fallback when no
  track_id is available (stub detector, or a detection ByteTrack hasn't
  confirmed yet). **Cross-camera** correlation is still plate-first +
  appearance-second (`identity.py`) — deliberately not motion-based, since
  disjoint camera views don't share a common motion model for a Kalman
  filter to predict across.

## Frontend

`frontend/` is a Vite + React app (`npm install && npm run dev`, reads
`VITE_API_BASE` from `.env`, defaults to `http://localhost:8000`). Covers:

- **API key bar** (top of every tab) — paste your `X-Sentinel-API-Key`;
  shows your resolved user/role from `GET /auth/whoami` once set.
- **Map & Registry tab** — Leaflet map of onboarded cameras (Model 1 GIS,
  health-colour-coded), camera list, and a live HLS view for the selected
  camera.
- **Vehicle Tracking tab** — purpose-bound plate search (audit-logged
  against your authenticated key), a movement-history timeline, and the
  "why was this vehicle linked?" explainability panel (plate confidence +
  Re-ID similarity + temporal consistency → a heuristic fused score — see
  `link_method`/`link_score` on `VehicleEvent` and `_explain_link()` in
  `routes_vehicle.py`).
- **Watchlist tab** — add/list watchlist entries, live-polled alert feed
  with a **governed alert lifecycle** (`new → acknowledged → resolved`, plus
  `dismissed` for false positives): the UI only offers server-sanctioned
  transitions, colour-codes by state, and shows who last acted on each alert.
  See `docs/HLD.md` §6 and `../docs/strategy/COMPETITIVE_TEARDOWN.md` §A for why (entity-
  lifecycle pattern; false-positive dismissal as a first-class auditable
  action).
- **Registry Ops tab** — manual camera onboarding form (Model 1's
  "manual onboarding demo" deliverable, now also capturing `camera_type`/
  `is_restricted_zone`/`expected_direction_deg`) and the gap-analysis report
  (Model 1's "gap-analysis report" deliverable), both admin/investigator-gated.
- **Camera Grid tab (added 2026-09-05)** — Model 2's "configurable video
  wall" bonus deliverable: up to 9 simultaneous live HLS tiles, each its
  own independently-isolated player (`CameraGridView.jsx`, reuses
  `LiveView.jsx` per tile). Verified visually against the real live
  sandbox — see "Known issues" below for an unrelated HLS-proxy 502 found
  during that verification.
- **Alerts tab** now badges each alert's `alert_type` (`watchlist` |
  `wrong_way` | `stopped_restricted_zone`, added 2026-09-05 — see
  `analytics/anomaly.py`), not just the watchlist match it originally
  only supported.

Note: this list (and the tab names above) predates a later frontend
rebuild referenced elsewhere in this project's docs/memory (Sidebar now
uses names like "Live Map"/"Vehicle Intelligence") — re-check
`frontend/src/components/Sidebar.jsx`'s `NAV` array for the current,
authoritative tab list rather than trusting this paragraph's naming.

The explainability data (`link_method`, `link_score`, `link_time_gap_s`) is
captured at resolve-time in `analytics/identity.py`'s `LinkInfo`, because it
can't be reconstructed after the fact — `VehicleIdentity` only ever keeps
its *latest* embedding, not a history of what it looked like at each past
match decision.

## Sandbox access — confirmed working 2026-09-04

Resolved, not just "configured": CDN login succeeds, `cameras.json` returns
all 30 real cameras, and a live RTSP connection to real `cam01` over TCP
returns actual decoded frames with PTS. It was never an access problem —
`catalogue.py` had two bugs (missing `email` field on CDN login; RTSP/WHEP
URLs not carrying the `email:password@` credentials the sandbox now
requires), both fixed. See `HACKATHON_DETAILS.md` §13a and
`REQUIREMENTS_COVERAGE.md`'s "Sandbox access — RESOLVED" section for detail.

## Known issues found in the 2026-09-04 code review — fixed

- **ByteTrack id-handoff forked every vehicle into two disconnected
  tracks.** `box.id` is `None` on a detection's first frame and only
  becomes a real id from frame 2 onward; the tracker's external-id branch
  never checked for the frame-1 IOU-fallback track, so it always created a
  second track instead of claiming the first. Fired on every vehicle once
  the real detector was wired in. Fixed in `analytics/tracker.py`.
- **Cross-camera identity race.** No DB constraint stopped two camera
  threads from creating two `VehicleIdentity` rows for the same plate
  within the same processing window, silently splitting a vehicle's
  history. Fixed: `VehicleIdentity.plate` is now a partial-unique DB
  constraint (NULLs excluded), `identity.py` catches the conflict and
  re-resolves onto the winning row, and `db/session.py` migrates/dedupes
  any pre-existing corrupted rows in an already-created DB.
- **CDN login couldn't detect a wrong/expired password.** `_login()`
  checked `resp.headers.get("location")` after `requests` had already
  followed the redirect, so the header was always empty and a failed login
  looked identical to a successful one. Fixed with `allow_redirects=False`.

## Known issues found in the 2026-09-04 code review — not yet fixed

- **RTSP discontinuity detection doesn't survive a reconnect.**
  `last_pts_ms` resets to `None` on every reconnect, so if the sandbox's
  recording loop point triggers a full reconnect (rather than a smooth
  PTS-backward moment inside one open connection), the scene cut goes
  undetected and downstream tracking/identity state isn't reset.
- **No FFmpeg read timeout on `cap.read()`.** A stalled TCP session can
  block forever instead of returning `ok=False`, which would prevent the
  (correctly-implemented) reconnect/backoff logic from ever triggering.
- **Frontend: Safari's native-HLS path sends no API key and fails
  silently** (no error banner) — only the hls.js path attaches auth headers.
- **Frontend: the map view doesn't distinguish OBSERVED vs. INFERRED route
  segments** the way the Vehicle Tracking timeline does — same route drawn
  as one uniform line regardless of link confidence.
- **Frontend: alert-list polling can race a user's own transition click**
  and briefly revert a just-acknowledged alert, causing a confusing
  `409 illegal transition` on a second click.
- Two endpoints (`routes_auth.py` create key, `routes_cameras.py` get
  camera) return `{"error": ...}` with HTTP 200 instead of a proper 400/404.
~~HLS proxy 502s for several real cameras' segments~~ — **root-caused and
  fixed 2026-09-05.** Not a session/credential/per-camera issue at all: the
  CDN gates the HLS playlist/segment endpoints (not `/cameras.json` or
  `/auth/login`) behind a User-Agent check — `requests`' default UA
  (`python-requests/x.x`) got a 403 with a `"browser required"` plain-text
  body. `routes_stream.py`'s clean-502-on-failure behavior was already
  correct and not the bug; the actual upstream error was masked earlier
  only because a diagnostic `curl -o /dev/null` discarded the response
  body that would have shown the real reason immediately. **Fix:**
  `catalogue.py`'s `CatalogueClient` now sets a real browser `User-Agent`
  on its whole `requests.Session` at construction, applying to every
  request (login, catalogue, HLS playlist, HLS segment) for consistency.
  **Verified against the real live sandbox:** all 5 previously-failing
  cameras tested (`cam01`, `cam02`, `cam03`, `cam17`, `cam30`) now return
  real HLS playlists, and a real 268KB `.ts` video segment was
  successfully fetched end-to-end through the proxy.

## Not yet built (deliverables still required for submission)

This section previously said the PPT and demo videos hadn't been started
at all — stale as of 2026-09-05; see `../docs/hackathon/TASKS.md` and
`../docs/hackathon/REQUIREMENTS_COVERAGE.md` for the authoritative, current status
instead of trusting the list below without cross-checking.

- Demo video — own feed: browser-flow footage + real-detection montage
  captured; terminal proof shot, captions, ffmpeg concatenation still
  outstanding. Per direct organizer guidance (2026-09-05), a real,
  clearly-visible sandbox camera (`cam06`) is fine to use for this video —
  no longer needs to be literally "our own feed."
- Demo video — government feed: **externally blocked**, per the same
  organizer guidance — their core team is still fixing the sandbox for
  this specific test case. Not something more engineering time here can
  unblock; revisit once they signal it's ready.
- Real-world Indian-plate OCR accuracy — **measured 2026-09-05** (was
  "not started"): 8/13 real frames on `cam06` produce a pattern-valid
  read after fixing the multi-line-plate + homoglyph bug in `anpr.py`.
  Cross-frame consensus-voting consistency remains open (see `HLD.md` §3).
- WHEP low-latency live preview (HLS-via-proxy is the working live-view path)
- Confirming real camera GIS/department data via `scripts/onboard_from_catalogue.py`
  against the live sandbox (script exists, not yet run against the now-working access)

`docs/HLD.md` (Technical Proposal) and `docs/SCALABILITY.md` (Plan for Scale)
are done, derived from this actual implementation plus `STRATEGY.md`. The
Solution Presentation (`../docs/assets/Sentinel_Solution_Presentation.pptx`) is also
done (v2, 2026-09-04) — a content refresh for today's findings is planned,
see `../docs/hackathon/TASKS.md`.
