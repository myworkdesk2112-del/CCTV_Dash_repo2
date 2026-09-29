# Model 2 — Unified Viewing & Metadata Analytics — Architecture

Ground-truthed 2026-09-11 against the real, running Sentinel backend/
frontend (not a proposal — this model is built and demoable today).

## Where Model 2 sits

Sentinel is submitted as a **Model 1 + Model 2 hybrid**. Model 2 owns
*live viewing and video analytics* — ANPR, cross-camera identity
resolution, watchlist/anomaly alerting, searchable movement history — on
top of the camera metadata Model 1 already provides
(`sentinel-solution/docs/models/model-1-registry-gis/`). Per the
hackathon's own Q19 answer, Model 2 connects **directly** to
departmental systems (no intermediate federation layer) — that's Model
3's job, deliberately out of scope until Model 1/2 close
(`docs/strategy/STRATEGY.md`'s "Model choice" section).

## Component diagram

```text
┌───────────────────────────────────────────────────────────────────┐
│ Sandbox catalogue (RTSP/HLS discovery — never hardcoded URLs)      │
└───────────────────────────┬─────────────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ StreamManager — one RTSP worker per camera                        │
│  forced TCP transport, PTS-driven timing (never CAP_PROP_FPS/     │
│  wall-clock), exponential backoff reconnect (2s→30s cap), scene-  │
│  loop discontinuity (PTS going backward) resets tracker state     │
└───────────────────────────┬─────────────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ Analytics pipeline (analytics/)                                    │
│  YOLOv8 vehicle detect → YoloPlateDetector (real trained plate     │
│  localizer, morsetechlab YOLOv11) → crop/enhance → PaddleOCR       │
│  (multi-line-plate join + homoglyph correction) → PLATE_PATTERN    │
│  regex gate → within-camera ByteTrack + temporal fusion →          │
│  position-weighted consensus_plate() vote → HSV-histogram +        │
│  grayscale-template appearance embedding → cross-camera identity   │
│  resolution (link_method/link_score/link_time_gap_s) →             │
│  anomaly.py (wrong-way / stopped-in-restricted-zone, opt-in)       │
└───────────────────────────┬─────────────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ Event store (SQLAlchemy/SQLite dev, Postgres-compatible)           │
│  VehicleIdentity, VehicleEvent, Alert, WatchlistEntry, AuditLog    │
└───────────────────────────┬─────────────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ FastAPI routes — role-scoped                                       │
│  GET  /live/{camera_id}/index.m3u8, /seg  (HLS proxy, authed)      │
│  GET  /vehicle/recent, /{plate}/history, /event/{id}/crop,         │
│       /{plate}/candidate-cameras, /search-by-attributes            │
│  GET  /alerts, POST /alerts/{id}/status, /alerts/{id}/ack          │
│  GET  /watchlist, POST /watchlist                                  │
└───────────────────────────┬─────────────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ Frontend                                                            │
│  LiveView.jsx / LiveCameraView.jsx / LiveMapView.jsx — HLS view    │
│  CameraGridView.jsx — up to 9-tile multi-camera video wall         │
│  VehicleIntelligence.jsx / VehicleTimeline.jsx / SearchView.jsx —  │
│    movement history + explainability + attribute search           │
│  AlertsPanel.jsx, WatchlistPanel.jsx — alert lifecycle + watchlist │
└───────────────────────────────────────────────────────────────────┘
```

## Data flow: from a raw RTSP frame to a searchable, alertable event

1. `StreamManager` opens one forced-TCP RTSP worker per catalogue camera;
   all timing is derived from PTS, never wall-clock or `CAP_PROP_FPS`
   (`docs/hackathon/HACKATHON_DETAILS.md` §13a timing rules).
2. Each frame runs through YOLOv8 vehicle detection, then the trained
   `YoloPlateDetector` plate localizer, then PaddleOCR — a real ML stack,
   not a stub, for detection+localization+OCR.
3. OCR output is validated against `PLATE_PATTERN` before it can ever
   spawn an identity or alert — untrusted external/AI-derived input never
   reaches identity resolution unvalidated (per this repo's coding rules).
4. Within a camera, ByteTrack + temporal fusion accumulate multiple OCR
   reads per vehicle; `tracker.py::consensus_plate()` does
   position-weighted character voting (fixed 2026-09-10 — a single
   misread character no longer splits votes against the correct plate).
5. Across cameras, an HSV-histogram + grayscale-template appearance
   embedding (cosine similarity) links sightings when the plate is
   unreadable — Sentinel's stated core differentiator versus commercial
   ANPR-only systems (`HLD.md` §1), not FastReID/OSNet (documented
   upgrade path, not built).
6. Every `VehicleEvent` records `link_method`/`link_score`/
   `link_time_gap_s` — the resolution is explainable, not a black box.
7. A plate match against `WatchlistEntry` or a real-time anomaly
   (`analytics/anomaly.py`, opt-in per camera) creates a governed
   `Alert` (new → acknowledged → resolved/dismissed), polled by
   `AlertsPanel.jsx`.
8. `GET /vehicle/{plate}/history` reconstructs a timestamped,
   location-wise route: OBSERVED sightings interleaved with honestly-
   labelled INFERRED camera-less segments (`analytics/geo.py`).

## Deviation from the suggested stack (and why)

| Suggested | Actual | Why |
|---|---|---|
| Kafka event bus | Direct DB writes, frontend polling | Pilot scale (30 cameras, single process); Kafka is a documented production-tier step in `SCALABILITY.md`, not deployed this week per `STRATEGY.md`'s scope discipline — a message queue this week would be unused infrastructure, not a demoable feature. |
| Elasticsearch | SQL queries against SQLAlchemy models | Same pilot-scale reasoning; `search-by-attributes`/`{plate}/history` are indexed SQL queries, not full-text search — sufficient at 30-camera/demo data volume. |
| PostgreSQL | SQLite | Matches Model 1's reasoning — `DATABASE_URL` is env-swappable, zero code change, per `SCALABILITY.md`. |
| Node.js/Python microservices | Single FastAPI monolith process | No operational win at this scale; a service-per-concern split adds deployment/ops overhead without a corresponding capability this pilot needs. |
| WebRTC/HLS relay | HLS via authenticated proxy only | WebRTC/WHEP low-latency preview is not implemented — HLS-via-proxy meets the live-viewing deliverable; WHEP is a documented future improvement (`HLD.md`), not a gap that blocks any Model 2 deliverable. |
| Open-source ANPR models | Real: YOLOv8 (vehicle) + trained YOLOv11 plate localizer (morsetechlab, AGPL-3.0 risk accepted) + PaddleOCR | Matches the suggestion directly — not a stub. Each stage independently verified running real inference against real sandbox footage. **2026-09-26:** the previously-cited `GJ01RP6128` read didn't reproduce across 5 fresh scans, but a 6th (`GJ19BR3000`, `cam06`, 6/6 samples, 0.917–0.977 confidence) did, visually confirmed — see `HLD.md` §3's correction note for the full sequence. |
| ONVIF/RTSP libraries | **Real ONVIF discovery implemented** (`streaming/onvif_discovery.py`, added post-hackathon-build-window as a follow-up) — WS-Discovery probe + Media `GetProfiles`/`GetStreamUri` SOAP calls, tried first on every catalogue refresh when `SENTINEL_ONVIF_ENABLED=true`; falls back to the sandbox's direct-RTSP catalogue automatically (and by default, since ONVIF is off unless explicitly enabled) when no ONVIF device answers | The sandbox itself exposes plain RTSP with no ONVIF endpoint (§13a) — enabling ONVIF against it correctly finds 0 devices and falls back, which is the expected, documented outcome, not an error. For a real departmental deployment with actual ONVIF-conformant cameras, setting `SENTINEL_ONVIF_ENABLED=true` uses the real discovery path with zero code change. **Honesty note:** verified against mocked WS-Discovery/SOAP exchanges (`tests/test_onvif_discovery.py`, 14 tests), not a live ONVIF camera — no ONVIF-conformant device is reachable from this environment or the hackathon sandbox to test against. |

No FastReID/OSNet deep-learning re-identification embedding is
implemented — the appearance-similarity signal is a simpler HSV-histogram
+ grayscale-template comparison. This is the one real architectural gap
versus a production-grade Re-ID system, and it's the reason cross-camera
identity linking is one input signal (with an explainable score), not a
sole source of truth; see `IMPLEMENTATION_PLAN.md` and `RESEARCH.md`.
