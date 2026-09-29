# Requirements Coverage — Official Problem Statement → Our Status

Mapped 2026-09-03 against the **official** Sentinel problem statement (pasted
in full by the user; consistent with `HACKATHON_DETAILS.md`, incl. the
₹51,00,000 prize pool). Status labels are honest and code-verified where
claimed:

- ✅ **Done** — built and exercised end-to-end against real code
- 🟡 **Partial** — core built, a piece is stubbed/unproven
- ⛔ **Not started** — required, no work yet
- 🔵 **Deliberate scope-out** — intentionally not built, reason stated
- 📄 **Doc/asset task** — no engineering, just needs producing/exporting

Deadline: **2026-09-28** (Phase 1, updated 2026-09-17 — was 2026-09-15,
confirmed via the live sentinel.gujarat.gov.in homepage; event moved to
12–13 Oct 2026. Prior history: originally 2026-09-07, moved to 2026-09-15
as of 2026-09-05 — this date has moved twice, re-check the live site before
relying on it). We are a **Model 1 + Model 2 hybrid**, with Model 3 (VMS
Federation) now also genuinely built as extra hybrid-architecture scope
(**revised 2026-09-11** — see section C below and `STRATEGY.md`'s "Model
choice" section). **Updated 2026-09-19:** Model 4 is no longer purely a
documented roadmap — a scoped **Model 4 pilot slice** (density
aggregation, storage-tier metadata, central pilot rollup, camera
ANPR-suitability scoring; see the Model 4 rows in section C) was built
and merged 2026-09-13, AUTOMATED-TEST VERIFIED. It is **not** the full
state-level central VMS/command-centre platform — Kafka, Kubernetes,
Triton, TimescaleDB, S3, and real government-DB integration remain
deliberately out of scope and undeployed.

---

## A. Model 1 — Central CCTV Registry & GIS (mandatory foundation)

| Official deliverable | Status | Where |
|---|---|---|
| Registry portal with GIS map view | ✅ Done | React + Leaflet, health-colour-coded (`frontend/`, Model 1 tab) |
| Bulk + manual + API onboarding | ✅ Done | `POST /cameras`, `/cameras/bulk`, Registry Ops form |
| Camera health / maintenance-status monitoring | ✅ Done | `is_healthy`/`last_seen_live_at` from real RTSP worker state is real and done. **2026-09-13**: `is_healthy` was found to only reflect stream connectivity — a live torch/torchvision bug made analytics fail 100% while `is_healthy` stayed "ok". Added a separate `analytics_degraded`/`last_analytics_success_at` signal (`GET /cameras`, `/health`) so this can no longer be silently masked. **2026-09-17**: closed the remaining "maintenance status" gap flagged 2026-09-11 — `CameraRegistry.under_maintenance`/`maintenance_reason`/`maintenance_until`, admin-only `POST /cameras/{id}/maintenance`, and gap-analysis now separates an intentionally-offline camera (`under_maintenance` category) from a genuinely unhealthy one, instead of reporting both the same way. LIVE/REAL VERIFIED against a running server (SQLite) and against real PostgreSQL (see `sentinel-solution/docs/MODEL1_MIGRATION_SCOPE.md` §9); AUTOMATED-TEST VERIFIED via 2 new pytest cases. |
| Gap-analysis report for uncovered/ageing zones | ✅ Done | `GET /cameras/gap-analysis` + `GET /cameras/gap-analysis/export.pdf`; real sample PDF at `docs/assets/sample_gap_analysis_report.pdf`, generated against the live sandbox catalogue 2026-09-10 |
| Role-based search/filter/export + metadata audit trail | ✅ Done | RBAC ✅; **department-scoped RBAC done 2026-09-05** (`api/auth.py`'s `department_scope`); **CSV export done 2026-09-05** (`GET /cameras/export.csv`); **backend search/filter query params done 2026-09-10** (`GET /cameras?department=&camera_type=&is_healthy=&live=&q=`, previously client-side-only/nonexistent); **camera-onboarding audit trail done 2026-09-10** (`CameraAuditLog` model, `GET /cameras/{id}/audit-log`, admin-only, records onboard vs. update per camera) |
| Sample onboarded camera-metadata dataset | ✅ Done | 30 real sandbox cameras onboarded and confirmed live 2026-09-05 (`catalogue_size: 30`, all workers connected) |
| `camera_type` field (PTZ/dome/fixed) | ✅ Done 2026-09-05 | `CameraRegistry.camera_type`, onboarding form + API + CSV export + JSON view |
| Coverage-radius map layer, ageing-infrastructure tracking | ✅ Done 2026-09-10 | `CameraRegistry.install_date`/`coverage_radius_m` (additive migration); `MapView.jsx` renders a coverage-radius `Circle` per camera and a dashed marker outline for cameras installed more than `SENTINEL_CAMERA_AGEING_THRESHOLD_YEARS` (default 5) ago; gap-analysis JSON/PDF report `ageing`/`missing_install_date` alongside the existing gap categories |
| CSV/report export endpoint | ✅ Done 2026-09-05 | `GET /cameras/export.csv`, department-scoped, never emits rtsp/whep credentials |
| Registry API documentation | ✅ Done (auto) | FastAPI OpenAPI at `/docs` — reference it in the submission |

## B. Model 2 — Unified Viewing & Metadata Analytics (mandatory pair)

| Official deliverable | Status | Where |
|---|---|---|
| Unified viewer connected to ≥2 different systems | ✅ Built, verified 2026-09-13 | System A: Gujarat sandbox (live RTSP/HLS, ANPR-processed). System B: Caltrans District 3's real, independently-operated, public CCTV API (`app/external_camera_source.py`, no API key, live-verified — 6 real Sacramento-area cameras fetched from `cwwp2.dot.ca.gov`), rendered as honestly-labelled periodic-snapshot tiles in the same `CameraGridView` as live sandbox feeds. Off by default (`SENTINEL_EXTERNAL_CAMERA_SOURCE_ENABLED=false`), enable for the demo. Real ONVIF discovery also exists (`streaming/onvif_discovery.py`, WS-Discovery + Media GetStreamUri, `SENTINEL_ONVIF_ENABLED`) as a second ingestion path for the Gujarat sandbox itself, verified only against mocked exchanges (14 tests) — no live ONVIF device reachable to test against. See `sentinel-solution/docs/models/model-2-unified-viewing/`. |
| ANPR-based metadata generation | ✅ **Real plate read reproduced 2026-09-26 (a 6th scan) — `GJ19BR3000`, `cam06`, 6/6 consecutive samples, confidence 0.92–0.98** | YOLOv8 → real trained plate localizer (`YoloPlateDetector`/morsetechlab YOLOv11, AGPL-3.0 risk accepted) → PaddleOCR (multi-line-plate joining + homoglyph correction, fixed 2026-09-05) → regex validate → temporal fusion. **Three real scans run 2026-09-26, all against the live sandbox, none synthetic:** (1) `weights/license-plate-finetune-v1n.onnx` was initially absent (never committed) — ran 30 cameras with `StubPlateDetector`'s heuristic fallback: 435 real vehicle detections, 0 reads, crops confirmed by eye to land on empty background, not plates. (2) Weights restored (user download, after two of my own fetch attempts were blocked by this session's sandbox and needed a user-added permission rule; also had to pin `protobuf>=6.31.1` for `onnxruntime`/`onnx` and force `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` for PaddlePaddle, since the two packages want incompatible protobuf ranges) — re-ran 30 cameras with the **real trained localizer**: 484 detections, 61 genuine localizations (12.6%, a believable number vs. the stub's fake 100%), still **0 reads**. Opened crops by eye: `cam01` found a real plate twice but it's night footage, too small/blurred to read; `cam18` and `cam06` boxed a windshield and a brand badge respectively — false positives, no plate present. (3) Focused 3-minute run on `cam06` alone (the camera the 2026-09-05 claim is attributed to, after confirming the sandbox's own rate-limit/cooldown — a real 403 hit after run 2 — had cleared): 9 vehicles, 1 localization (the "ATUL" badge, not a plate), 0 reads. **Across all three runs: 928 real vehicle detections, 497 localization attempts, 0 pattern-valid plate reads.** The `GJ01RP6128` claim cannot currently be reproduced with the same weights/code this environment has. Possible causes, not yet distinguished: a different, more favorable moment in the sandbox's looped recording than these sampling windows landed on; a threshold/preprocessing difference from 2026-09-05 that regressed since; or the original result needs re-scrutiny. **Do not re-quote `GJ01RP6128`** — a different vehicle/plate at that camera, superseded below. **(4) Fifth scan (5 cameras with real traffic, 60s each): 1,057 detections, 31 localizations, 0 reads — still nothing.** **(5) Sixth scan, all 30 cameras, 40s each: 21/30 opened, 1,209 detections, 118 localizations, and finally 7 pattern-valid reads — `cam06` alone produced `GJ19BR3000` on 6 of 6 consecutive samples (frames 5–30), confidence 0.917–0.977, plus `cam16` produced one read (`ZO26O613`, confidence 0.99, unconfirmed by eye — no crop was saved for it, unlike `cam06`'s).** Opened `cam06`'s saved crop directly (`data/anpr_scan/20260926T150303Z/cam06/f5_v1_platecrop.jpg`) — a black Mahindra SUV, clean front plate, visually matches `GJ19BR3000` exactly. **This is a real, reproduced, end-to-end plate read on live sandbox footage, obtained today, use this as the new headline result — not `GJ01RP6128`.** The consensus-vote logic (`tracker.py`'s per-character-position voting, 2026-09-10) applies cleanly here since all 6 votes agree exactly (no divergent OCR variants to reconcile), so this particular case doesn't exercise the per-character-voting refinement, but does confirm the full pipeline (detect → localize → OCR → pattern-validate → temporal fusion) working end to end on fresh, non-synthetic footage. Total across all six scans today: 3,670 real vehicle detections, 677 localization attempts, 7 pattern-valid reads (1 vehicle producing 6 of them). |
| Event tagging + camera-wise indexing | ✅ Done | `VehicleEvent` per sighting, indexed by camera/plate/time |
| Searchable vehicle-movement records | ✅ Done | `GET /vehicle/{plate}/history`, `/vehicle/search-by-attributes` |
| Multi-camera grid / video walls | ✅ Done 2026-09-05 | `CameraGridView.jsx` — up to 9 simultaneous live HLS tiles, each independently isolated; verified visually against the real sandbox |
| Alerts for tagged events / vehicles of interest | ✅ Done (watchlist + named anomaly alerts) | Watchlist engine + governed alert lifecycle; **named anomaly alerts (wrong-way / stopped-in-restricted-zone) done 2026-09-05** (`analytics/anomaly.py`), opt-in per camera, built on existing motion data |
| Architecture note: existing dept systems unaffected | ✅ Done | HLD §3 (direct-connect, no middleware, VMS keep running) |

## C. Model 3 — VMS Federation & Middleware Integration (built 2026-09-11, beyond the mandatory Model 1+2 pair)

Not part of the mandatory Model 1+2 hybrid submission — built as extra
hybrid-architecture bonus scope per the user's 2026-09-10 decision (see
`docs/strategy/STRATEGY.md`'s "Model choice" section), sequenced after
Model 1/2 fully closed out. See
`sentinel-solution/docs/models/model-3-vms-federation/` for full docs.

| Official deliverable | Status | Where |
|---|---|---|
| Adapter/plugin architecture for multiple vendors | ✅ Done | `VMSAdapter` Protocol + `NormalizedEvent` dataclass (`analytics/federation.py`); two real adapters, `SentinelAdapter` and `NycOpenDataAdapter` |
| Model 4 pilot density aggregation | AUTOMATED-TEST VERIFIED | `CameraDensityWindow` persists actual sampled-frame detector counts; `GET /admin/density` labels them as non-unique raw detections, not crowd-size estimates |
| Model 4 storage-tier metadata | IMPLEMENTED, UNVERIFIED | `VehicleEvent.storage_tier` plus age-based API classification; no object storage backend is deployed |
| Model 4 central pilot rollup | AUTOMATED-TEST VERIFIED | `GET /admin/central-rollup` combines actual registry, health, alert and federation data; it explicitly is not a statewide deployment |
| Model 4 govt-DB query integration surface (VAHAN/SARTHI/eGujCop/CCTNS-AFIS-NAFIS) | IMPLEMENTED, UNVERIFIED, hard-blocked beyond this — added 2026-09-28 at explicit user request to attempt the full Model 4 build | `analytics/govt_db_adapters.py`, `GET /admin/govt-db-status`. This is the integration *point* (Protocol interface, fails closed with `GovtDbUnavailable`, reports `configured: false` for all four systems), not a working integration — none of these systems has ever offered this project a sandbox or test credential; real access requires a government-to-government integration agreement that no engineering session can substitute for. 10 new tests, full suite 357/357, endpoint HTTP-exercised (200, all four systems correctly report unconfigured) |
| Metadata exchange bus | ✅ Done, deliberately scoped down | Polled `FederatedEvent` table, not Kafka/RabbitMQ — pilot-scale decision, see `RESEARCH.md` |
| Event-correlation engine | ✅ Done — **now verified end-to-end on the live DB, not just in unit tests** | `GET /federation/correlations` — cross-source plate correlation within a configurable time window, reusing Model 2's `link_score` explainability vocabulary. **2026-09-11:** added System C (`demo_partner_vms`), a clearly-labelled synthetic source replaying partner sightings of plates Sentinel really read, because Systems A and B share no plates by construction and the join path could otherwise never run against real data. Live run: 1,105 events / 3 sources / **4 correlations** (gaps 47/128/212/284 s), one deliberate +900 s row correctly rejected by the window gate. Every such correlation carries `involves_synthetic_source: true` and prints `SYNTHETIC` in the PDF's Basis column |
| Unified event-correlation dashboard | ✅ Done | `FederationDashboard.jsx` |
| Working middleware federating ≥2 systems | ✅ Done — **honestly, 1 real Gujarat system + 1 real independent public dataset**, not 2 government VMS platforms | System A = Sentinel's own real Model 1/2 stack; System B = NYC Open Data's real "Open Parking and Camera Violations" dataset (`data.cityofnewyork.us`) — a real 2,000-row slice, not fabricated, but not a second departmental VMS either (none was available). Zero real plate overlap by construction (different countries), empirically confirmed: the real sample report (`docs/assets/sample_federation_report.pdf`) shows 0 correlated plates against 1,100 real federated events — the honestly-predicted outcome |
| Adapter architecture documentation | ✅ Done | `sentinel-solution/docs/models/model-3-vms-federation/ARCHITECTURE.md`, `REQUIREMENTS.md`, `RESEARCH.md` |
| Sample federated analytics report | ✅ Done | `docs/assets/sample_federation_report.pdf`, regenerated 2026-09-11 against the live DB — now shows 4 populated correlations, each marked `SYNTHETIC` in the Basis column, rather than the previous empty table |

## D. Mandatory Test Case (§ Test Scenario)

| Requirement | Status | Notes |
|---|---|---|
| Onboard ~50 heterogeneous cameras | 🟡 Partial | Onboarding pipeline ✅; **sandbox access confirmed live 2026-09-04** (30 real cameras returned, not yet all onboarded into the registry) |
| Identify/trace a designated vehicle by **registration number** | ✅ Done | Core path, verified end-to-end |
| Complete **timestamped, location-wise** route/movement history | ✅ Done | `/vehicle/{plate}/history` — per-camera timeline **+ geo-temporal route reconstruction**: OBSERVED sightings interleaved with honestly-labelled INFERRED camera-less segments (`analytics/geo.py`), rendered in the timeline UI. Directly targets the "advanced cross-camera correlation" bonus. |
| Cross-reference live feeds vs **representative watchlist** | ✅ Done | Own watchlist (allowed) + real-time alert on match |
| Automated **real-time alert** on match | ✅ Done | Alert row → polled UI, governed lifecycle |
| Cross-camera continuity when plate unreadable | ✅ Done (our differentiator) | Appearance-second identity resolution, retroactive plate upgrade |

## E. Submission Documents (all mandatory)

| Deliverable | Status | Notes |
|---|---|---|
| 1. Solution Presentation (PPT/PDF) | ✅ Done (v3) | `Sentinel_Solution_Presentation.pptx` (**21 slides**) — **regenerate via `deck-build/build_deck_v3.py`** (v3 repositioning pass 2026-09-11 per `DECISION_REVIEW_2026-09-11.md`; layout/overflow fixes, Model 4 pilot card, evidence-integrity governance cards and the §63 red→amber correction added 2026-09-19). Every slide re-rendered and visually checked via LibreOffice + PyMuPDF, and the deck passes the pptx structural validator. Historical note on v2 below. v2 redesign 2026-09-04: real flowchart-shape diagrams with connector arrows (not text-box rectangles), Bahnschrift/Segoe UI type pairing, ~50% less text per slide, a references/sources slide. `Sentinel_Solution_Presentation_v1.pptx` kept as fallback. Built from and consistent with HLD.md/SCALABILITY.md; every slide visually verified via real PowerPoint COM export-to-PNG, not just python-pptx round-trip (a real bug — Python 3 true-division producing float EMU values, which corrupted the file for real PowerPoint despite python-pptx reading it back fine — was caught this way and fixed). Regenerate via `deck-build/build_deck_v2.py`. |
| 2. Technical Proposal / HLD | ✅ Done | `HLD.md` (verified against real runtime) |
| 3. Demo video — own feed (2–3 min, **must be a working backend**, no mockups) | ✅ **Recorded 2026-09-28** (user-reported; not independently verified by this agent — see caveat below) | Link: <https://drive.google.com/file/d/1q3iwi6t7YKMPP405uBZyMaHIsTCUEYTe/view?usp=drive_link>. This agent cannot open/play a Drive link from this environment, so the on-screen content (does it show `GJ19BR3000`/`cam06`, the terminal proof shot, captions, per `DEMO_SCRIPT_OWN_FEED.md`) and link accessibility to organizers are unconfirmed — needs one human watch-through before the deadline. |
| 4. Live demo — govt feed + output report (plates + timestamps) | ✅ **Recorded 2026-09-28** (user-reported; not independently verified by this agent — see caveat below) | Link: <https://drive.google.com/file/d/1CF0ERX-ZqiYPoCCmkkACkZPoXBKcaSWM/view?usp=sharing>. Same caveat: content against `DEMO_SCRIPT_GOVERNMENT_FEED.md`'s shot list (incl. the two-system unified-viewer shot) and Drive sharing permissions are unconfirmed by this agent. |
| Plan for Scale (compute/GPU/bandwidth/storage/HA-DR/cost) | ✅ Done | `SCALABILITY.md` |

## F. Common Evaluation Areas (§A) — how we'd score today

| Area | Our standing |
|---|---|
| 01 Successful test case (govt feed) | ✅ **Recording done 2026-09-28** (see E4) — user-reported, content not independently verified by this agent. The underlying capability (track a designated vehicle by registration number on real footage) is verified working, not just plausible |
| 02 Solution presentation | ✅ Done — **`docs/assets/Sentinel_Solution_Presentation.pptx` now regenerated via `sentinel-solution/deck-build/build_deck_v4.py`** (2026-09-28, 17 concise slides, same visual system as v3 but rewritten as an executive pitch — v3's dense hedged-prose style read as an engineering log per user feedback). `build_deck_v3.py` kept in the repo but no longer the canonical generator. A separate from-scratch 20-slide web deck also exists (2026-09-28 Artifact link) |
| 03 Solution architecture | ✅ Strong — HLD/SCALABILITY, verified, honest gaps |
| 04 Working platform & demonstration | ✅ Both demo videos recorded 2026-09-28 (see E3/E4) — user-reported, still needs a human watch-through against each shot-list script before submission |
| 05 Video analytics output | ✅ **Re-verified 2026-09-26 with a fresh real read.** After 5 scans with 0 reads (928+1,057 detections, see §B), a 6th scan (all 30 cameras, 40s each) produced 7 pattern-valid reads — `cam06` read `GJ19BR3000` on 6/6 consecutive samples (0.92–0.98 confidence), visually confirmed against the saved crop. Use this as the current headline, not `GJ01RP6128`. The local `sentinel.db` still has 0 `vehicle_event` rows — this evidence exists only in the scan artefact (`data/anpr_scan/20260926T150303Z/`), not the live database, until the real pipeline is run persisting to it (see `scripts/demo_end_to_end.py`/`SENTINEL_DEMO_PERSIST=1`). |
| 06 Scalability & PoC readiness | 🟡 8/11 required items documented in `SCALABILITY.md`; backup/encryption/network-segmentation missing (found + fixed 2026-09-05, see below) |
| 07 Submission completeness | 🟡 Docs done; both demo videos recorded 2026-09-28 (E3/E4, user-reported, pending a human watch-through against their shot-list scripts); PDF Technical Proposal export (`docs/submission/Sentinel_Technical_Proposal_HLD.pdf`) and a second presentation deck also produced 2026-09-28 |

## G. Bonus Consideration (§B) — updated 2026-09-19 against `DECISION_REVIEW_2026-09-11.md`

- ✅ Innovative hybrid architecture — Model 1+2 built and mandatory; Model 3 genuinely built (§C); Model 4 is a real, tested **pilot slice** (density aggregation, storage tiers, central rollup, ANPR-suitability scoring — merged 2026-09-13), not the full statewide central VMS
- ✅ Camera ANPR-suitability scoring, surfaced as an operator screen — extended 2026-09-19 from read-history-only to **read history + plate-pixel geometry**: `pipeline.py` now persists the localised plate region's source-frame width/height, the localiser class that produced it, and per-track OCR attempt/read counts (5 additive columns); `analytics/anpr_suitability.py` scores both measures against the ≥120 px / 100 px-floor **vendor** figures from `DECISION_REVIEW_2026-09-11.md` §H; `GET /cameras/anpr-readiness` + `AnprReadinessView.jsx` show the verdict beside stream health, with both reasons, the measurement basis, the stated thresholds **and their provenance**, and the explicit list of factors nothing measures. A heuristic plate region can rule ANPR out but never rule it in (reported `INCONCLUSIVE`), and a demonstrated read rate is never overridden by a geometric estimate. **AUTOMATED-TEST VERIFIED + runtime-verified** — 17 tests, plus a real `AnalyticsPipeline` run that stored a 54×28 px region from a 90 px-wide vehicle and reached UNSUITABLE with the geometric reason, plus HTTP exercise of the endpoint. **Not** field-verified: geometry is NULL for all pre-2026-09-19 rows, and no real camera footage was processed in this environment.
- ⚠️ **Advanced cross-camera vehicle tracking / correlation — reframe, do not claim as proven.** 11,992 of 12,251 cross-camera links (97.8%) rest on an appearance-only signal measured at a **41.87% false-positive rate** on real confirmed-different-vehicle pairs, and zero plates repeat across cameras in the real database to validate against (`DECISION_REVIEW_2026-09-11.md`). Per that review: *"Do not demo cross-camera vehicle tracking as a capability... demo the governance around cross-camera linking instead."* What we can actually claim: explainable evidence-tiered linking (CONFIRMED/PROBABLE/LEAD ONLY) that refuses to present a weak appearance match as a tracked vehicle — that governance layer is real and demonstrated.
- ✅ Analytics beyond ANPR (dwell / speed / direction; attribute search)
- 🟡 Edge-processing / bandwidth-optimisation — real architectural principle (`SCALABILITY.md`'s 640 Mbps vs. 160 Gbps structured-events story), extended **2026-09-28 with a real measurement**: `scripts/measure_bandwidth_reduction.py` did a real timed RTSP capture of 3 real live sandbox cameras (avg. measured 497.4 kbps) against real `vehicle_event` rows in the accumulated `sentinel.db` (real 108-byte events at 0.0456/sec on the one live camera with traffic history) — a real, **LIVE/REAL VERIFIED** ~12,624x reduction on this pilot's actual (low) traffic. Still 🟡, not ✅: that ratio is inflated by this pilot's low real traffic density and is explicitly **not** the number to cite for statewide planning — `SCALABILITY.md`'s ~250x stays the operative planning figure, not a proven result at 80,000-camera scale
- ✅ Cybersecurity / privacy / auditability / RBAC (real, not checklist) — strengthened 2026-09-19 with **write-time evidence integrity**: `analytics/evidence_integrity.py` SHA-256-hashes each evidence crop immediately after `cv2.imwrite` returns and stamps the concrete detector/plate-detector/OCR class names in force (so the real-vs-stub seam is on the record, which config alone cannot show), plus a §63-oriented provenance package and printable Part A/Part B certificate (`api/routes_evidence.py`). Export is gated to CONFIRMED only, purpose-bound, and audit-logged before the artefact is produced. **AUTOMATED-TEST VERIFIED** — 27 tests including one that drives the real `AnalyticsPipeline` and one asserting a post-write edit is reported as `HASH_MISMATCH`; the additive migration was separately run against a simulated pre-change DB (columns added, existing rows preserved, NULL not fabricated, idempotent). **UI control wired 2026-09-19** (`EvidenceExportView.jsx`) and exercised over real HTTP — 409 for LEAD_ONLY, 422 for a sub-8-character purpose, 200 + a real 5,756-byte PDF for CONFIRMED. **Not** field-verified: never run against the real accumulated `sentinel.db`, wording not legally reviewed.
- ✅ Operational dashboards, automated alerts, health monitoring, APIs

---

## Deliberate scope-outs (stated, not hidden) — the honest tensions

| Item | Where the problem mentions it | Our decision |
|---|---|---|
| **Facial Recognition (FRS)** | HLD deliverable #4 (as an *example* tech "such as… proposed by the team"); Model 4 feature | 🔵 **Out** — DPDP risk + NIST-documented demographic bias; **not** in the mandatory vehicle test case (§Test Scenario). Frame as a deliberate, defensible governance choice; note the FRS *seam* could be added under Model 4 if a department mandates it. |
| **Person tracking / missing-person / unidentified-body** | Background DB list; watchlist examples | 🔵 Mostly out — we're vehicle-first. Watchlist supports person-type entries by plate/vehicle association, but no person Re-ID / soft-biometrics. |
| **Live govt-DB integration** (VAHAN/SARTHI/eGujCop/AFIS/NAFIS) | Background; Model 4 "integration readiness" | 🔵 Design-only ("query, don't copy"). Local representative watchlist is what the test case actually requires — that's built. |
| ~~VMS federation middleware (Model 3)~~ | Model 3 | **No longer a scope-out — built 2026-09-11, see §C.** This row previously said a half-built federation bus was worse than an honest documented path; the user later decided (2026-09-10) to build a real minimal slice instead, which shipped the next day. |
| ~~Multi-camera grid / video wall~~ | Model 2 feature | **No longer a scope-out — built 2026-09-05** (`CameraGridView.jsx`, see §B). This row was stale — found while reconciling this document 2026-09-11. |

---

## Sandbox access — RESOLVED 2026-09-04 (was blocker #1)

**Not an access problem — two code bugs.** The sandbox account/token were
always valid. `catalogue.py`'s CDN login only sent `password`, but
`/auth/login` requires **both** `email` and `password`; the missing field
made every login attempt silently fail while `_login()`'s broken
success-check (following redirects before checking status) reported it as
succeeding anyway. Separately, RTSP/WHEP were updated to require
`email:password@` embedded in the URL (percent-encoded `@`), which the
catalogue's URL builder didn't do at all. Both fixed in `catalogue.py`; see
`HACKATHON_DETAILS.md` §13a for the corrected auth flow. **Verified
end-to-end against the real sandbox 2026-09-04:** CDN login succeeds,
`cameras.json` returns all 30 real cameras, and a live RTSP connection to
real `cam01` over TCP returned actual decoded frames (1080×1920) with PTS
timestamps.

Also found and fixed the same day (see `sentinel-solution/README.md`'s
"Known issues, fixed" for detail): a ByteTrack id-handoff bug that forked
every vehicle into two disconnected tracks once the real detector was
wired in, and a cross-camera identity race that could create duplicate
`VehicleIdentity` rows for one plate under concurrent camera threads (now
DB-constrained + handled).

## The remaining priority order (updated 2026-09-05 — deadline moved to 15 Sep, ~10 extra days)

~~Run a real ANPR scan against the live sandbox's actual real footage~~ —
**done 2026-09-05, answer superseded same day by more data.** Initial
answer (based on 2-3 wide-overview cameras): real plates unreadable at
these camera distances. **Corrected after reviewing all 30 cameras per
organizer guidance:** `cam06` is a genuinely close-range, ANPR-suitable
camera; combined with a second real bug fix (multi-line plate joining in
`anpr.py`), real plate reads are now achieved on 8/13 real frames. See
`HLD.md` §3 for the full, corrected writeup — don't cite the older
"camera-placement limitation" framing without reading the correction.

~~Fix the plate localizer~~ — **done 2026-09-05.** AGPL-3.0 risk accepted
(project owner's explicit decision); `YoloPlateDetector` wired into
`main.py` as the default plate detector. Combined with the `anpr.py`
multi-line/homoglyph fix above, this DID materially change the
real-footage OCR-read outcome on a good camera (`cam06`) — see the
corrected note above.

1. **Finish the own-feed demo video** (D3) — now include `cam06`'s real plate-detection result (8/13 frames) as the headline evidence, per organizer guidance to use a visible sandbox camera. Still need the terminal "it's real" proof shot, captions, and final `ffmpeg` concatenation.
2. **Government-feed demo video (D4) is externally blocked** — organizers are still fixing their own sandbox for this. Don't spend more time forcing it; check back periodically.
3. **Close the 3 documentation discussion points** (see `MODULE_GAP_ANALYSIS.md`): multi-vendor claim wording ("designed for" vs. "demonstrated with"), private/commercial CCTV coverage (currently zero mention), external-DB-integration honesty (VAHAN/SARTHI/etc. — confirm HLD states this is design-only, not working).
4. With the extra runway, revisit `CODEX_HANDOFF_PROMPT.md`'s deferred ML-3 (empirical Re-ID threshold) and consider a per-character/position-weighted consensus-voting upgrade to `tracker.py`'s `consensus_plate()` — the new gap `HLD.md` §3 identifies (exact-string voting splits votes below the confidence floor on noisy real footage).
~~4. Nice-to-have: multi-camera grid, camera_type+CSV export, named anomaly alerts, department-scoped RBAC~~ — **all done 2026-09-05**, see `MODULE_GAP_ANALYSIS.md`.

~~5. HLS proxy 502 (found while verifying the camera grid)~~ — **root-caused
and fixed 2026-09-05.** The CDN gates HLS endpoints behind a User-Agent
check; `requests`' default UA got a 403 "browser required". Fixed by
setting a real browser UA on `catalogue.py`'s session. Verified against 5
real cameras + a real fetched video segment. This was silently blocking
BOTH the new camera grid AND the pre-existing single-camera live view —
good news for the government-feed demo video, which depends on this path.

~~Build the Solution Presentation (D1)~~ — **done, 2026-09-04.**

**New capability added 2026-09-05:** `scripts/demo_multi_watchlist.py` — 5 independent real-video-frame feeds, each its own department/camera/plate, cross-referenced against 5 different watchlist categories (stolen, blacklisted, suspect_vehicle, robbery_case, hit_and_run), each producing its own correctly-typed alert. Verified end-to-end. Good additional evidence for F05 (video analytics output) and the "additional reliable analytics" bonus criterion.

**Bottom line (updated 2026-09-05, third pass, same day):** the
*engineering* for the mandatory Model 1 + Model 2 test case is done,
verified against our own controlled scenario, AND now verified with a
**real, correct plate read on real sandbox footage, confirmed through the
actual production consensus-vote logic** (`GJ01RP6128`, confidence 0.81) —
not a promising OCR string, the real accept-path. The single biggest
unknown from earlier today is fully resolved, not just narrowed. What
remains: E3 (own-feed video) is a finishing task, not a risk, and now has
a genuine real-footage headline result to lead with; E4 (government-feed
video) is **externally blocked** on the organizers' own sandbox fix,
confirmed directly by their core team — not something more engineering
time here can unblock. The next-most-valuable engineering work, if time
allows, is the consensus-voting refinement (exact-string → per-character)
for harder cases (two-line plates) — the single-line car-plate case this
session verified already works correctly as-is.

> **2026-09-26 correction to the above:** both "resolved" claims in this
> paragraph were stale, and the story has since moved again. The sandbox
> is not externally blocked (re-verified live 2026-09-26 — see §E4). The
> specific `GJ01RP6128` read did not reproduce across 5 real scans that
> day — but a 6th scan did produce a fresh, visually-confirmed real read
> (`GJ19BR3000`, `cam06`, 6/6 samples, 0.92–0.98 confidence). See §B's
> "ANPR-based metadata generation" row for the full sequence. Treat this
> paragraph as a historical log entry, not current status — use
> `GJ19BR3000`, not `GJ01RP6128`, if citing a specific plate.
