# Model 2 — Requirements Coverage

Every bullet below is copied from the official challenge problem
statement's Model 2 section (`docs/hackathon/HACKATHON_DETAILS.md` §7),
then marked against real, verified code — not a self-assessment from
memory. Verified 2026-09-11, cross-checked against
`docs/hackathon/REQUIREMENTS_COVERAGE.md` §B.

Official spec text:

> Aggregates departmental feeds through a single interface without
> replacing existing infrastructure. Connects directly to departmental
> systems via RTSP/ONVIF/APIs — no middleware layer.

## Key functional features

| Requirement | Status | Evidence |
|---|---|---|
| Feed aggregation via RTSP/ONVIF/APIs | ✅ **Built, including real ONVIF discovery** | Direct RTSP `StreamManager` per camera, HLS-via-authenticated-proxy for the frontend (`routes_stream.py`); **ONVIF discovery is now real code**, not just a cited target — `streaming/onvif_discovery.py` implements WS-Discovery probe + Media `GetProfiles`/`GetStreamUri`, tried first when `SENTINEL_ONVIF_ENABLED=true` and falling back to the sandbox's direct-RTSP catalogue when no ONVIF device answers (the sandbox's own actual state — plain RTSP, no ONVIF endpoint, §13a). Verified against mocked WS-Discovery/SOAP exchanges (14 tests), not a live ONVIF device — no such device is reachable from this environment to test against for real |
| ANPR-based metadata generation | ✅ **Built, verified end-to-end on real footage, reproduced 2026-09-26** | YOLOv8 detect → real trained `YoloPlateDetector` (YOLOv11) localizer → PaddleOCR → `PLATE_PATTERN` validation gate → `consensus_plate()` temporal fusion. A previously-captured example (`GJ01RP6128`, 4/5 samples) didn't reproduce across 5 fresh scans on 2026-09-26, but a 6th did — `GJ19BR3000` on `cam06`, 6/6 samples, confidence 0.917–0.977, visually confirmed against the saved image — not a promising OCR string in isolation, the real accept-path. See `HLD.md` §3 and `docs/hackathon/REQUIREMENTS_COVERAGE.md` for the full 6-run sequence |
| Event tagging + camera-wise indexing | ✅ **Built** | `VehicleEvent` row per sighting: camera_id, plate, timestamp (`pts_ms`/`observed_at`), confidence, vehicle attributes, evidence crop — indexed and queryable by camera/plate/time |
| Searchable vehicle-movement records | ✅ **Built** | `GET /vehicle/{plate}/history` (full timeline, observed+inferred), `GET /vehicle/search-by-attributes` (color/type/etc.), `GET /vehicle/recent` |
| Configurable video walls | ✅ **Built** | `CameraGridView.jsx` — up to 9 simultaneous, independently-isolated live HLS tiles |
| Automated alerts | ✅ **Built** | Watchlist match → governed `Alert` lifecycle (new→acknowledged→resolved/dismissed); plus named anomaly alerts (wrong-way, stopped-in-restricted-zone via `analytics/anomaly.py`, opt-in per camera, built on existing motion/direction data) |

## Expected deliverables

| Deliverable | Status | Evidence |
|---|---|---|
| Unified viewer connecting ≥2 different systems | ✅ **Built and verified 2026-09-13** | System A: the Gujarat sandbox (live RTSP/HLS, ANPR-processed). System B: Caltrans District 3's real, independently-operated, public CCTV API (`https://cwwp2.dot.ca.gov/data/d3/cctv/cctvStatusD03.json`, no API key) — `app/external_camera_source.py` polls it, upserts into `CameraRegistry` with `source_system="caltrans_d3_public_api"`, and the frontend's `CameraGridView`/`SnapshotView` render it alongside live sandbox tiles, honestly labelled "EXTERNAL SOURCE — periodic snapshot, not live video" (it's a refreshed still image, not continuous video — not overclaimed as such). Live-verified against the real endpoint: 6 real Sacramento-area cameras (`ext-caltrans-1`..) fetched with real coordinates and live snapshot URLs. Off by default (`SENTINEL_EXTERNAL_CAMERA_SOURCE_ENABLED=false`) — enable for the demo. See `IMPLEMENTATION_PLAN.md`. |
| ANPR demonstration | ✅ **Built, verified** | Same real-footage evidence as above; `demo_end_to_end.py` + `DEMO_SCRIPT_OWN_FEED.md` |
| Searchable metadata dashboard | ✅ **Built** | `VehicleIntelligence.jsx`/`SearchView.jsx`/`VehicleTimeline.jsx` — attribute search, movement timeline with explainability (`link_method`/`link_score`/`link_time_gap_s` surfaced in the UI) |
| Architecture note confirming departmental system independence | ✅ **Built** | `HLD.md` §3 — direct-connect, no middleware; existing VMS keep running unaffected |

## What's still honestly open

**"≥2 different systems" is now closed** (2026-09-13) — see the table
above. One caveat carried forward honestly: System B (Caltrans D3) is a
camera/imagery-only integration — no ANPR/analytics run on it, and it's
a snapshot feed (~60s refresh), not continuous video. That's disclosed
in the UI badge, not hidden.

The related test-case item "onboard ~50 heterogeneous cameras" (§C) is
still 🟡: 30 real Gujarat sandbox cameras are onboarded and live, not 50,
and the shortfall is sandbox camera count, not onboarding-pipeline
capacity (Model 1's bulk/API onboarding already handles arbitrary count;
the 6 Caltrans cameras are a second-system proof, not a count-padding
device, and are excluded from that Gujarat-specific count on purpose).

One architectural honesty note carried over from `ARCHITECTURE.md`: the
cross-camera identity-resolution embedding is a simpler HSV-histogram +
grayscale-template comparison, not a FastReID/OSNet deep embedding. It's
real and it's the stated differentiator (explainable link score, not a
black box), but it's a genuinely weaker signal than a production Re-ID
model — documented, not hidden. See `RESEARCH.md`.
