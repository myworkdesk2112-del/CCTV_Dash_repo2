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
choice" section); Model 4 remains documented roadmap, not built.

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
| ANPR-based metadata generation | ✅ **Real-footage ANPR verified fully end-to-end 2026-09-05** — a real car's real plate (`GJ01RP6128`) read correctly through the ACTUAL production consensus-vote logic (confidence 0.81, clears the 0.5 floor), confirmed against the saved image, not assumed | YOLOv8 → real trained plate localizer (`YoloPlateDetector`/morsetechlab YOLOv11, AGPL-3.0 risk accepted) → PaddleOCR (multi-line-plate joining + homoglyph correction, fixed 2026-09-05) → regex validate → temporal fusion. **Full 30-camera re-scan with both fixes in place:** 687 real vehicle detections, 76 localizations, **7 pattern-valid reads**, all on `cam06` (found via organizer guidance to use a visible sandbox camera). One car's plate read correctly 4/5 times (0.85–0.92 confidence each) — ran the REAL `tracker.py` consensus-vote logic against these exact 5 votes and confirmed it produces `("GJ01RP6128", 0.81)`, comfortably above `PLATE_MIN_CONFIDENCE=0.5`. **This is not a promising OCR string — it's the live pipeline's actual accept-path, verified.** A second vehicle's plate had split 1-vote-each under the old exact-string consensus algorithm — **fixed 2026-09-10**: `tracker.py`'s `consensus_plate()` now votes per character position instead of per whole string, so a single-character misread no longer creates a competing candidate that dilutes the correct plate's vote share (see `HLD.md` §3 and TASKS.md's P1 for the before/after). |
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
| 1. Solution Presentation (PPT/PDF) | ✅ Done (v2) | `Sentinel_Solution_Presentation.pptx` (20 slides) — v2 redesign 2026-09-04: real flowchart-shape diagrams with connector arrows (not text-box rectangles), Bahnschrift/Segoe UI type pairing, ~50% less text per slide, a references/sources slide. `Sentinel_Solution_Presentation_v1.pptx` kept as fallback. Built from and consistent with HLD.md/SCALABILITY.md; every slide visually verified via real PowerPoint COM export-to-PNG, not just python-pptx round-trip (a real bug — Python 3 true-division producing float EMU values, which corrupted the file for real PowerPoint despite python-pptx reading it back fine — was caught this way and fixed). Regenerate via `deck-build/build_deck_v2.py`. |
| 2. Technical Proposal / HLD | ✅ Done | `HLD.md` (verified against real runtime) |
| 3. Demo video — own feed (2–3 min, **must be a working backend**, no mockups) | 🟡 In progress, newly de-risked | Browser-flow footage + real-YOLOv8 montage already captured; terminal proof shot/captions/ffmpeg concat still outstanding. **Organizer guidance received 2026-09-05** (their core team, relayed by the user): for this demo, using any clearly-visible real sandbox camera is fine/expected — no longer required to be literally "our own feed." `cam06` (a real, close-range, front-facing camera found today) is now real plate-detection evidence for this video: 8/13 real frames produced a pattern-valid plate read after today's OCR fix, a stronger and more honest demo beat than the synthetic-composite plan. |
| 4. Live demo — govt feed + output report (plates + timestamps) | ⛔ Externally blocked | **Organizer guidance received 2026-09-05:** the hackathon's own sandbox is still being fixed on their end for this test case — treat as blocked on them, not on us; don't force this recording against a sandbox the organizers themselves say isn't ready. Revisit once they signal it's fixed. |
| Plan for Scale (compute/GPU/bandwidth/storage/HA-DR/cost) | ✅ Done | `SCALABILITY.md` |

## F. Common Evaluation Areas (§A) — how we'd score today

| Area | Our standing |
|---|---|
| 01 Successful test case (govt feed) | 🟢 **Core capability proven** — externally blocked only on the organizers' own sandbox fix for a full live demo session (see E4); the underlying capability (track a designated vehicle by registration number on real footage) is verified working, not just plausible |
| 02 Solution presentation | ✅ Done (v2, see §E1), content refreshed 2026-09-05 for today's findings |
| 03 Solution architecture | ✅ Strong — HLD/SCALABILITY, verified, honest gaps |
| 04 Working platform & demonstration | 🟡 Own-feed video in progress, strongly de-risked by a real verified plate read; govt-feed demo externally blocked |
| 05 Video analytics output | ✅ Verified on our own controlled scenario AND on real sandbox footage — a real plate (`GJ01RP6128`) read correctly through the actual production pipeline logic |
| 06 Scalability & PoC readiness | 🟡 8/11 required items documented in `SCALABILITY.md`; backup/encryption/network-segmentation missing (found + fixed 2026-09-05, see below) |
| 07 Submission completeness | 🟡 Docs done; own-feed video near-complete; govt-feed video is the one real remaining gap |

## G. Bonus Consideration (§B) — we hit most

- ✅ Innovative hybrid architecture (Model 1+2 built and mandatory; Model 3 also genuinely built, see §C; Model 4 documented roadmap)
- ✅ Advanced cross-camera vehicle tracking / correlation (our core)
- ✅ Analytics beyond ANPR (dwell / speed / direction; attribute search)
- ✅ Edge-processing / bandwidth-optimisation story (SCALABILITY.md)
- ✅ Cybersecurity / privacy / auditability / RBAC (real, not checklist)
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
