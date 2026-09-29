# Sentinel — Next Actions

Living task list. Deadline **28 September 2026** (Phase 1, updated
2026-09-17 — was 15 Sep, which was itself moved from 7 Sep on 2026-09-05),
event 12–13 October 2026 (was 22–23 Sep, was 10–11 Sep). **11 days left
as of 2026-09-17.** This date has moved twice already — re-check
https://sentinel.gujarat.gov.in/ before trusting it if this file is more
than a few days old.
Last updated **2026-09-17** (deadline/event dates corrected against the
live organizer site; see `docs/hackathon/HACKATHON_DETAILS.md` and
`REQUIREMENTS_COVERAGE.md` for the same correction). Prior 2026-09-13
reconciliation notes below are otherwise unchanged.
Cross-check against `REQUIREMENTS_COVERAGE.md` (the authoritative
deliverable-status matrix) and `sentinel-solution/README.md` ("Known
issues") before trusting this file if it's more than a day or two old.

## 2026-09-19 — Bharat-series (BH) plate support (done)

Correctness fix against a **mandatory** requirement, found by the ANPR
research pass (`docs/strategy/RESEARCH_ANPR_DEEP_2026-09-19.md` §A1), not by
a failing test — nothing was failing, which is the point.

**The defect.** `anpr.py`'s `PLATE_PATTERN` was
`[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4}` — two leading *letters*. The Bharat
series (MoRTH, notified 26 Aug 2021, registrations open 15 Sep 2021) is
`YY-BH-####-XX` and **starts with digits**, so every BH plate failed
validation *and* the homoglyph fallback:

```
GJ01AB1234   fullmatch=True    via_homoglyph=GJ01AB1234
23BH1234AA   fullmatch=False   via_homoglyph=None
```

**Why it was worse than "BH plates don't work".** `PLATE_PATTERN` is
referenced in exactly one place (`_best_pattern_match`). Every other plate
path — watchlist `add()`, vehicle search, partial-plate search — calls only
`normalize_plate()`, which uppercases and strips punctuation and performs **no
format validation**. So an officer could watchlist a BH plate and search for
it, both would report success, and neither could ever match anything, because
no BH plate could reach the database in the first place. Silent, one-
directional, no error surface anywhere.

**The fix.** `PLATE_PATTERN` is now an alternation of two named components
rather than one loosened pattern — widening the state-series regex enough to
admit BH plates would have admitted a lot of OCR noise with them. The public
name is unchanged on purpose: `evidence_class.py`, `tracker.py` and
`models.py` all describe "the PLATE_PATTERN gate" and renaming would make
three comments stale for no benefit.

```
_STATE_SERIES = [A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4}   (unchanged)
_BH_SERIES    = [0-9]{2}BH[0-9]{4}[A-HJ-NP-Z]{1,2}
```

`[A-HJ-NP-Z]` encodes the registration rule that BH trailing letters exclude
**I** and **O**, which exists precisely to avoid confusion with 1 and 0
(confirmed against Wikipedia's format table, not assumed from a blog — two
sources disagreed on whether the tail is one letter or two; it is **one or
two**). Encoding it is not cosmetic: it stops the homoglyph search from
"rescuing" a misread into a plate that could never legally exist.

**Verified:** 280/280 backend tests (273 baseline + 7 new), zero regressions.
The 7 cover both tail lengths, state-series non-regression, I/O rejection,
seven near-miss rejections (wrong year length, wrong serial length, no tail,
three-letter tail, missing BH literal), homoglyph *recovery* of a BH misread,
and homoglyph *refusal* to invent an illegal I/O plate.

Runtime-verified beyond unit tests: drove the **real `AnalyticsPipeline`**
against a throwaway DB with a reader that runs raw OCR text through the same
gate `PaddleOcrPlateReader` uses. Raw misread `Z3BH1Z34AA` (2 read as Z,
twice) was recovered to `23BH1234AA`, persisted with `evidence_class=CONFIRMED`,
and **raised a real watchlist alert** — the complete chain that was previously
impossible. Plus an end-to-end test in `test_watchlist.py` asserting gate +
evidence class + alert together, because the defect was only visible when all
three were considered at once.

**No API, DB, migration, config or dependency change.** Read-path only and not
retroactive: existing rows are untouched, consistent with the append-only
evidence stance (CLAUDE.md §24.4). A BH sighting recorded before today stayed
anonymous and stays anonymous.

**Known residual risk, pinned by a test rather than left incidental:** widening
the gate also widens what the homoglyph search can rescue. Bounded by the
existing 4-flip cap, `PLATE_MIN_CONFIDENCE`, and the narrowness of the BH
shape.

**Deliberately NOT done** (separate tasks, see the research doc §H):
positional digit-vs-letter homoglyph resolution — the limitation
`_best_pattern_match`'s own docstring already confesses — and plate-failure
attribution (`CAMERA_UNFIT` / `PLATE_UNREADABLE`). Bundling either into a bug
fix would make a regression ambiguous between two causes (CLAUDE.md §23.3).

## 2026-09-19 — ANPR Readiness screen + Evidence Export screen (done)

Closes `CLAUDE.md` §6 Priority C / §21 P1 #8, and wires §21 P1 #6–7's
already-built backend to a screen. Both were sitting behind the honest
`NotImplemented` placeholders added 2026-09-12; the Evidence Export
placeholder had additionally gone **stale and false** — it still read
"Sentinel stores evidence crops with no hash and does not stamp model or
software versions per event", which the 6efd22a commit had made untrue the
same day. That is exactly the organizer-facing drift `CLAUDE.md` §26 exists
to prevent, and it is fixed here.

### ANPR Readiness (new capability, backend + frontend)

The question is "can this camera physically produce a plate read", which is
NOT the question Camera Health answers. `cam01` streams perfectly and has
never read a plate.

- **5 additive columns** on `vehicle_event` through the existing
  `session.py` mechanism: `plate_region_w_px`, `plate_region_h_px`,
  `plate_localiser`, `plate_ocr_attempts`, `plate_ocr_reads`.
- **`pipeline.py::_read_plate` now returns `(plate_result, region)`** —
  the localised plate region's width/height in **source-frame** pixels,
  measured from the *clipped* crop and **before** `enhance_plate_crop()`
  upscales it. Interpolated pixels are not plate detail; counting them
  would inflate every camera's score. "No region found" stays `None`, not
  `(0, 0)` — a failed localisation is not a measurement of zero.
- **`tracker.py`** accumulates per-frame regions and returns their
  **median** per track (max would report the one vehicle that passed
  directly under the camera as the camera's normal framing).
- **`anpr_suitability.py` rewritten** around two independent measures:
  observed validated-plate rate, and plate-pixel geometry against the
  **≥120 px / 100 px floor** vendor figures recorded in
  `DECISION_REVIEW_2026-09-11.md` §H (Eocortex/Bosch/Axis/Plate
  Recognizer). Labelled VENDOR CLAIM in the API, not presented as a
  Sentinel measurement.
- **The epistemics are the feature.** `StubPlateDetector` returns a
  heuristic region that *contains* the plate, so its measurement is an
  **upper bound**: below the floor it is a genuine proof of incapability;
  above the threshold it proves nothing and is reported `INCONCLUSIVE`
  rather than promoted to CAPABLE. Only a model-localised plate
  (`YoloPlateDetector`) can support CAPABLE geometry.
- **Observation beats inference** (`CLAUDE.md` §4.3/§24.6): a camera
  demonstrably reading plates at ≥60% is CAPABLE regardless of what the
  geometric estimate says, and the disagreement is surfaced
  (`measures_disagree`) rather than silently resolved either way.
- **Character height stays in `unmeasured_factors`** even though region
  height is now recorded — the vendor threshold is stated against
  *character* height, and a two/three-line Indian plate carries the same
  characters at roughly half the per-line height. Conflating the two would
  be a fabricated measurement. Blur, glare, view angle, lens and distance
  remain unmeasured and are listed as such on the screen.
- **`GET /cameras/anpr-readiness`** (investigator+, department-scoped,
  excludes deregistered) returns per-camera verdicts, the fleet roll-up,
  the thresholds **and their provenance**, and the honest "not measured"
  list. `insufficient_sample` is counted separately from the MARGINAL
  total it is a subset of, so "we do not know" is not read as "we measured
  it and it was mediocre".
- **`AnprReadinessView.jsx`** shows ANPR verdict *beside* stream health —
  the "streaming fine, cannot read a plate" row is the whole point, and it
  is invisible when the two live on separate screens. Every verdict expands
  to its two reasons, the measurement basis, the frame-level OCR yield, and
  the remediation.

### Evidence Export (frontend wiring of existing backend)

`EvidenceExportView.jsx` against the existing `/evidence/event/{id}/verify`
(any class), `/package` and `/certificate.pdf`. Export buttons disable for a
non-CONFIRMED sighting **as a courtesy only** — the server's 409 gate is the
control, and the screen says so. `NO_HASH_RECORDED` is rendered neutrally,
not as a failure: the guarantee was never established, which is a different
statement from "these bytes changed".

**Verified:** 266/266 backend tests (249 baseline + 17 new), zero
regressions. Runtime, not just unit:

- Drove the **real `AnalyticsPipeline`** over synthetic frames against a
  throwaway DB — a 90 px-wide vehicle produced a stored 54×28 px region,
  `localiser=StubPlateDetector`, 6 OCR attempts / 0 reads, and the scorer
  independently reached UNSUITABLE with the geometric reason. With only one
  sighting the read-rate measure correctly **abstained** while geometry
  alone reached a verdict — the cam01 case exactly.
- Exercised every endpoint over real HTTP against a running `app.main`:
  readiness returned a `healthy=True` + `UNSUITABLE` camera alongside a
  CAPABLE one; `/verify` answered for both CONFIRMED and LEAD_ONLY;
  `/package` and `/certificate.pdf` returned **409** for LEAD_ONLY, **422**
  for a short purpose, **200** + a real 5,756-byte `%PDF-1.4` for CONFIRMED.
- **Real bug caught by the live run, not by inspection**: `api.js` rendered
  FastAPI's non-string `detail` as `[object Object]`, so the 409 gate's
  own explanation — the most important message on the screen — was
  unreadable. Fixed for both the object and array (422) shapes.
- Frontend `npm run lint` and `npm run build` both **pass**, with zero
  warnings from either new file. This is the first successful frontend
  build in this environment: the rolldown/oxlint native bindings were
  missing because Node 22.11.0 is below the `>=22.12.0` engine floor npm
  enforces. A newer Node (v22.23.2) already present at
  `~/AppData/Local/hermes/node` installs them; the `npm run lint`/`build`
  blocker recorded on 2026-09-18 is resolved by putting that on PATH.

**Deliberately NOT claimed:** the geometry columns are NULL for every row
written before today, and no real camera footage has been processed through
the new path in this environment — every geometry figure above came from
synthetic frames or seeded rows in a throwaway DB. Against the real
accumulated `sentinel.db`, expect every camera to report
`plate_pixel_width` as unmeasured until the pipeline runs again. The ≥120 px
threshold remains a **vendor claim**, not a Sentinel-validated figure.

## 2026-09-19 — write-time evidence integrity + §63-oriented export (done)

Closes `CLAUDE.md` §6 Priority B / §21 P1 #6–7, the last bonus-aligned
engineering gap (`REQUIREMENTS_COVERAGE.md` §G, "auditability"). Picked
because P0's only remaining item is the own-feed demo *recording*, which
needs a human at a screen, not code.

- **`analytics/evidence_integrity.py` (new)** — SHA-256 of the evidence
  crop, computed by `pipeline.py` immediately after `cv2.imwrite` returns
  and stored with the timestamp it was taken at. Never recomputed into
  that column: a hash refreshed at export time proves nothing about the
  bytes between capture and export, which `CLAUDE.md` §6 calls out
  explicitly. `verify_crop()` recomputes and compares, returning
  VERIFIED / HASH_MISMATCH / FILE_MISSING / NO_HASH_RECORDED — a mismatch
  is reported, never silently healed by overwriting the stored hash.
- **Production stamp** — records the concrete detector/plate-detector/
  OCR/Re-ID *class names* in force at write time, not just the configured
  weight filenames, because `StubPlateDetector` and `YoloPlateDetector`
  can run with identical config and produce completely different
  artefacts. An evidence package that can't tell a reviewer which one ran
  isn't a provenance record. `build_rev` comes from `SENTINEL_BUILD_REV`
  and reads "unknown" when the deployment doesn't supply it, rather than
  inventing a version the code can't verify about itself.
- **`api/routes_evidence.py` (new)** — `GET /evidence/event/{id}/verify`
  (viewer+, any evidence class: checking whether an image was altered is
  an integrity question, and an investigator evaluating a LEAD_ONLY lead
  is entitled to the answer), plus `/package` (JSON) and
  `/certificate.pdf` (printable Part A/Part B form), both investigator+,
  purpose-bound (8-char floor), **gated to CONFIRMED only** via the
  existing `evidence_class.EXPORTABLE_CLASSES` — PROBABLE is refused too
  — and audit-logged *before* the artefact is produced so an attempted
  export is on the record even if rendering fails. The PDF renders the
  same package the JSON returns rather than recomputing it, so the two
  can't disagree about one artefact. Legal wording lives in a single
  `legal_review_notice()` for the same reason.
- **3 additive columns** (`vehicle_event.crop_sha256`, `crop_hashed_at`,
  `production_stamp`) through the existing `session.py` mechanism.
- **Real bug caught by its own test**: the device block used
  `getattr(camera, "name", None)` — `CameraRegistry` has `location_name`,
  not `name`, so the getattr default would have shipped a silently-empty
  provenance field forever. Now reads the real columns directly, with a
  test asserting the value is actually present.

**Verified:** 249/249 backend tests pass (222 baseline + 27 new), zero
regressions. The 27 include one that drives the real `AnalyticsPipeline`
and asserts the stored hash matches an independently computed hash of the
file on disk; one that edits the file post-write and asserts
HASH_MISMATCH; one asserting legacy (pre-feature) rows report
NO_HASH_RECORDED rather than VERIFIED *or* a tamper alarm (~12,280 real
rows predate this); and 7 HTTP-layer tests via `TestClient`, which are
the only ones that actually exercise the purpose floor and the role gate
(direct function calls bypass FastAPI's `Query`/`require_role`
entirely). Separately runtime-verified: the additive migration against a
simulated pre-change DB — adds exactly the 3 columns, preserves existing
rows, leaves the new ones NULL rather than fabricating values, and is
idempotent on re-run. App boots with the router registered (3 paths in
the OpenAPI schema, 41 total).

**Deliberately NOT claimed:** never run against the real accumulated
`sentinel.db` (not present in this checkout); no frontend control is
wired, so there is no click-through demo of an export yet; the §63
wording is "§63-oriented" and has had no legal review. Deck updated
accordingly — Evaluation Readiness moves this item red→amber (not green),
and Honest Gaps now reads "built & tested, no UI control or legal review
yet" instead of "not yet built".

## 2026-09-13 (continued) — Model 2 "≥2 different systems" closed (done)

Per CLAUDE.md §10, faking or relabeling a single source was ruled out;
building a token department-VMS integration "just to check the box" was
already documented as theater (`model-2-unified-viewing/IMPLEMENTATION_PLAN.md`).
Instead: found and integrated a real, independently-operated, public
government system as System B — Caltrans District 3's public CCTV API
(`https://cwwp2.dot.ca.gov/data/d3/cctv/cctvStatusD03.json`, no API key).
`app/external_camera_source.py` (new module, ~130 lines) polls it and
upserts into `CameraRegistry` with `source_system="caltrans_d3_public_api"`,
registry-only so `StreamManager`/the ANPR pipeline never touches it as an
RTSP source. Frontend: `SnapshotView.jsx` renders it inside the existing
`CameraGridView` as a periodically-refreshed still image with an explicit
"EXTERNAL SOURCE — periodic snapshot, not live video" badge — one unified
viewer, two genuinely independent systems, each honestly labelled by real
feed type, not two lookalike tiles. Live-verified against the real
endpoint (found and fixed a real bug in the process: `fetch_raw`'s
original 10s timeout failed against the real ~850KB/13s district
payload — bumped to 30s). 4 new regression tests
(`tests/test_external_camera_source.py`); full backend suite 159/159
passing; frontend lint/build both clean. Off by default
(`SENTINEL_EXTERNAL_CAMERA_SOURCE_ENABLED=false`) — set it to `true` when
recording the demo. See `sentinel-solution/docs/models/model-2-unified-viewing/`
for the full design note.

**Still not started: the own-feed demo video (2-3 min, §9.3) — now the
single highest-priority remaining item**, see the P0 section below.

## 2026-09-13 — independent-review fixes + real live-sandbox verification (done)

Fixed, tested, and committed (4 commits, `feature/statewide-operations-nav`):

- **Evidence-tier alert bypass (BLOCKER, found by independent review)** —
  `pipeline.py` was gating watchlist alerts on `identity.plate` instead of
  the triggering event's OWN `plate`/`link_method`, so a LEAD_ONLY
  appearance-match sighting could raise an ordinary plate-matched alert if
  the same identity had been plate-confirmed by an earlier, different
  sighting. Now gates on `evidence_class.classify(event.plate,
  event.link_method) == CONFIRMED`; `Alert` persists `evidence_class`/
  `evidence_class_reason`. Idempotent backfill script run against the live
  `sentinel.db`; 2 pre-existing bad alerts correctly relabeled without
  rewriting investigator history (evidence-append-only).
- **Object-level RBAC gaps (found by independent review)** — camera
  stream (HLS playlist/segment), last-detection, vehicle-crop, and alert
  list/status/ack endpoints now enforce `department_scope()`: hard-block
  for viewer role outside the owning department, audit-and-allow for
  investigator role (preserves the intentional cross-department
  vehicle-search capability, logged to `AuditLog`).
- **Self-caught regression**: while verifying the RBAC fix, found the
  vehicle-crop endpoint had briefly gated VIEWING (not just export) on
  `evidence_class.is_exportable()` — would have 404'd 99.95% of real saved
  crops (12,274/12,280 are non-CONFIRMED). Fixed; 5 regression tests lock
  this in.
- **RTSP reconnect not resetting tracker state** — `rtsp_client.py`
  cleared `last_pts_ms` to `None` on reconnect, which silently made the
  first frame of the new connection report `discontinuity=False`, so
  `pipeline.py` never reset per-camera tracker/ByteTrack state across a
  reconnect gap. Fixed with an explicit `just_reconnected` flag.
- **ONVIF SSRF hardening** — `device.xaddr` (unauthenticated UDP
  multicast reply) and `media_xaddr` (the device's own, equally untrusted
  `GetCapabilities` response) were used directly in `requests.post()` with
  redirects enabled — a hostile/compromised device could redirect the
  backend to an internal URL. Added `_validate_onvif_address()` (rejects
  non-http(s) schemes, unresolvable hosts, loopback/link-local/multicast
  targets — covers cloud-metadata SSRF) and `allow_redirects=False`.
- **Camera health masking analytics failures (live-reproduced this
  session, see below)** — `CameraRegistry.is_healthy`/`/health` only ever
  reflected RTSP stream connectivity. Added `analytics_degraded`/
  `last_analytics_success_at` tracked at the point `pipeline.process()`
  is actually invoked (stride-gated), separate from stream connectivity,
  exposed on `GET /cameras` and `/health`.
- **Real live-sandbox verification, using the real 30-camera sandbox and
  real organizer credentials**: found and fixed a real torch/torchvision
  ABI mismatch (`torch==2.12.1` + `torchvision==0.20.1`) that made every
  analytics call fail while `/health` reported all 30 workers "ok" — the
  exact failure mode the analytics-degraded fix above now catches.
  Fixed via `pip install --upgrade torchvision` (resolved to
  `torch==2.14.0`/`torchvision==0.29.0`); re-verified real, fresh
  detection events land in `sentinel.db` against the live sandbox
  (e.g. `cam11`, 2026-09-13, `car`, confidence 0.72). Plate is still
  `None` — `paddleocr`/`paddlepaddle` are not installed in this
  environment, `StubPlateReader` honestly active.
- **New, documented, NOT-yet-fixed risk**: loading the plate-detector
  `.onnx` weights still triggers ultralytics' AutoUpdate on this
  environment, silently upgrading `onnx`/`protobuf` past the versions
  `requirements-ml.txt` pins for exactly this reason (breaks
  `paddlepaddle==2.6.2` if installed in the same venv). Attempting to
  re-pin `onnx==1.14.1` failed outright on this environment's Python 3.12
  (no prebuilt wheel, needs `cmake` to build from source) — left
  documented in `requirements-ml.txt` rather than forced under deadline
  pressure. **Before ever installing paddleocr/paddlepaddle in this same
  venv**, recreate it on Python ≤3.11 or resolve this properly.
- Rebuilt the presentation deck (`build_deck_v3.py`) around the corrected
  accountability-layer positioning with real measured evidence-tier
  counts, replacing the forbidden "ANPR failure ≠ tracking failure"
  headline.

156/156 backend tests passing after all fixes (was 131 at session start).

**Still open, not touched this session:** the demo video, Model 2's
two-system proof, PDF regeneration from the new deck, `HLD.md`/
`REQUIREMENTS_COVERAGE.md` doc sync against these fixes, sandbox
credential rotation (a real credential was pasted into a chat session
this week and should be treated as exposed), camera ANPR-suitability
scoring, §63 evidence hash-at-write, integration-loss dashboard.

## 2026-09-13 (continued) — Model 4 pilot slice + second Codex batch, tagged v0.3.0 (done)

Two further Codex batches, each reviewed and partly corrected before commit
(see commit messages on `feature/statewide-operations-nav` for full detail):

- **Model 4 pilot slice**: real sampled-frame density aggregation
  (`CameraDensityWindow`, `GET /admin/density`), storage-tier metadata
  (`VehicleEvent.storage_tier`, hot/warm/cold), a central pilot rollup
  (`GET /admin/central-rollup`), and an explicit `DeliberatelyExcludedFaceRecognizer`
  seam. Deliberately scoped — no Kafka/Kubernetes/Triton/TimescaleDB/S3/
  government-DB integration. **Caught before commit**: Codex's own
  handoff-report text had been accidentally pasted into the organizer-facing
  `docs/promast/...Technical_Proposal.md` — reverted.
- **RTSP read timeout** (`config.RTSP_READ_TIMEOUT_US`, default 5s) — a
  stalled TCP peer could previously block `cap.read()` forever, defeating
  the backoff/reconnect logic entirely.
- **Atomic identity+event commits**: `identity.py` now flushes instead of
  committing, so `pipeline.py`'s single commit covers both the identity
  mutation and its `VehicleEvent` insert — previously a crash between them
  could leave an orphaned identity mutation with no corresponding event.
- **Camera ANPR-suitability scoring** (CAPABLE/MARGINAL/UNSUITABLE) from
  real persisted plate-read history only — `analytics/anpr_suitability.py`,
  surfaced on `GET /cameras`.
- **Caught before commit**: the duplicate-identity migration's merge logic
  absorbed missing fields with a generic rule that never actually fired for
  `first_seen_at`/`last_seen_at` (always non-null via a `utcnow()` default)
  — fixed to compute the genuinely correct MIN/MAX merge instead of keeping
  the earliest-created row's possibly-stale timestamp.
- **Track-contamination guard, SQLite write batching, 3 frontend gaps** —
  see the updated P2 entries above for the contamination-guard limitation
  and the FFmpeg-timeout/Safari-HLS/map-styling/alert-polling fixes. SQLite
  now sets `PRAGMA busy_timeout=5000` + `journal_mode=WAL`, and density
  writes batch per camera/window instead of committing every frame —
  independently load-tested here (not just unit-tested): 30 concurrent
  threads × 50 commits against a real temp SQLite file, 1500/1500 writes
  succeeded, zero lock errors.

**Tagged `v0.3.0`, PR #2 opened** (`feature/statewide-operations-nav` →
`master`), not yet merged. 155/155 backend tests passing; frontend
`npm run lint`/`npm run build` clean.

**Still open:** everything listed as still-open above, unchanged — this was
supporting hardening work, not a substitute for the demo video / two-system
proof / credential rotation.

## Paused work — resume later

- [x] **Per-reference-model module docs (Model 1–4) — drafted 2026-09-11.**
      Started 2026-09-10 as a multi-agent Workflow run; that Workflow tool
      wasn't available in the session that resumed this, so the remaining
      models were drafted directly instead (research via forked
      subagents, writing via direct file edits) — same scope, different
      mechanism. All four module folders now exist under
      `sentinel-solution/docs/models/`, each with `ARCHITECTURE.md`/
      `REQUIREMENTS.md`/`RESEARCH.md`/`IMPLEMENTATION_PLAN.md`:
      - `model-1-registry-gis/` — **re-verified 2026-09-11**: all four 🟡
        gaps found in the original 2026-09-10 pass were independently
        confirmed closed by `3306db6` (ageing tracking, coverage-radius
        layer, search filters, onboarding audit trail); docs updated to
        reflect this. Also caught and fixed a stale claim in
        `REQUIREMENTS_COVERAGE.md` line 27 ("camera health/maintenance-
        status monitoring" was marked fully ✅ but maintenance-status
        beyond healthy/unhealthy was never built) — downgraded to 🟡 with
        the same caveat as the module doc, so the two docs no longer
        disagree.
      - `model-2-unified-viewing/` — ground-truthed against real code;
        no required-tier gaps against the literal spec (the one 🟡,
        "≥2 different systems," is a sandbox-availability limit, not
        missing code). Documented-but-skipped hardening items: WHEP
        low-latency live view, per-camera anomaly-detection calibration,
        FastReID/OSNet Re-ID upgrade (skipped because the sandbox lacks
        enough cross-camera repeat sightings to validate a swap, not
        because it'd be hard to wire in).
      - `model-3-vms-federation/` — real build plan (not built yet, see
        "Build Model 3" below), scoped to one real adapter (wraps our
        existing Model 1/2 stack) + one real, independent, public dataset
        as the second system (NYC's "Open Parking and Camera Violations"
        open dataset, `data.cityofnewyork.us` — **revised 2026-09-11**
        after the user rejected an initial self-authored-fixture plan; a
        research pass found and selected this real dataset instead), a
        polled `FederatedEvent` table (not Kafka), and a minimal
        correlation dashboard — ~12.5 hrs / 1.5–2 days estimated. Zero
        real cross-system plate overlap is expected by construction
        (different countries) and must be disclosed everywhere a
        correlation result is shown; any populated demo match needs one
        clearly-labeled synthetic overlay, not a blended-in real one.
      - `model-4-central-vms/` — roadmap-only, explicitly not built.
        Citations independently fact-checked and corrected 2026-09-11
        (an initial research pass's unconfirmed figures were replaced):
        Ahmedabad's Command and Control Centre (Paldi, operational since
        2018) confirmed at ~6,000 cameras including 1,600 at major
        traffic junctions (deshgujarat.com) as the realistic integration
        target rather than a fictional greenfield build; NIST FRVT Part 3
        (NISTIR 8280)'s confirmed finding of up to 7,200× within-group
        false-positive-rate variation (not the earlier unconfirmed
        "10×–100×"/specific-demographic-group claim) and Delhi Police's
        confirmed 2% accuracy figure (not "1–2%", per its own 2018 Delhi
        High Court statement) as the specific grounding for excluding
        Face Recognition from any
        committed roadmap; inherits `SCALABILITY.md` §6's phased rollout
        rather than redefining it.
      **Not yet done: user review.** Presented for feedback in this
      session before any tagging — planned tags per the original note
      (`v0.2.0`–`v0.5.0` per model) are still pending the user's go-ahead,
      since a prior approval doesn't carry forward per this repo's git
      rules.

- [x] **Build Model 3 (VMS Federation & Middleware) — built 2026-09-11.**
      Decided 2026-09-10 to sequence this after Model 1+2 closed (they had,
      per `TASKS.md`'s own tracking); user gave explicit go-ahead
      2026-09-11 and it shipped the same session. Real, tested:
      `analytics/federation.py` (`VMSAdapter` Protocol, `SentinelAdapter`
      wrapping our own real data, `NycOpenDataAdapter` parsing a real
      2,000-row slice of NYC Open Data's public "Open Parking and Camera
      Violations" dataset — downloaded live from its Socrata API, not
      fabricated), a polled `FederatedEvent` table with idempotent
      ingest (`main.py`'s `federation_ingest_loop`), a correlation engine
      (`routes_federation.py`'s `GET /federation/correlations`, reusing
      Model 2's `link_score` explainability vocabulary), a frontend
      dashboard (`FederationDashboard.jsx`), and a PDF export reusing
      Model 1's `reportlab` pattern. 15 new regression tests, full backend
      suite 70/70 passing. A real sample report
      (`docs/assets/sample_federation_report.pdf`) was generated
      end-to-end and shows **0 correlated plates** — the honestly-
      predicted outcome (zero real plate overlap between Gujarat and NYC
      vehicles, disclosed everywhere via the response's `honesty_note`),
      now empirically confirmed rather than just theorized. System B is
      real public data, not a second Gujarat departmental VMS — see
      `sentinel-solution/docs/models/model-3-vms-federation/` for the
      full design rationale, including the earlier rejected
      self-authored-fixture plan and why the user asked for a real
      dataset instead. `docs/hackathon/REQUIREMENTS_COVERAGE.md` gained a
      new §C for this (sections C–F renumbered to D–G accordingly).
      **Still open:** tagging (`v0.4.0` per the original plan) is pending
      user review of this build; a demo script/video for Model 3 doesn't
      exist yet.

## P0 — hard submission blockers

- [x] **Camera-registry auto-population — closed 2026-09-10.**
      `main.py`'s health-sync loop auto-creates a bare `CameraRegistry`
      row for any active worker, so the "empty-looking app" risk was
      already gone (confirmed 2026-09-05). Ran
      `scripts/onboard_from_catalogue.py` against the live 30-camera
      sandbox for real to close the remaining department/GIS-metadata
      gap. **Found and fixed a real regression risk first**: the script
      unconditionally overwrote `department`/`latitude`/`longitude` with
      its keyword-inference result even when that inference was `None`
      — running it as-is would have wiped the 5 already-correct manual
      department tags (cam01-05: Police/Municipal Corporation/GSRTC/
      Health/Panchayat) back to unassigned. Fixed by having the script
      fetch the current registry state first and only override a field
      when its own inference actually found something, falling back to
      the existing value otherwise. Verified end-to-end against the live
      sandbox: all 30 cameras now carry real location names from the
      catalogue; GPS coordinates populated for 22/30 (8 have no
      confident area-centroid match); department stays honestly at 7/30
      (cam01-05 preserved + cam17→GSRTC/cam19→Panchayat newly matched by
      keyword) — the other 23 real camera names (street/landmark names,
      not department-suggestive) genuinely can't be classified without
      organizer-provided ground truth or manual per-camera investigation,
      not a script bug. Full backend suite 55/55 passed after the fix.
- [x] **Record the own-feed demo video — recorded 2026-09-28 (§9.3).**
      Link: <https://drive.google.com/file/d/1q3iwi6t7YKMPP405uBZyMaHIsTCUEYTe/view?usp=drive_link>
      (Google Drive — access depends on the sharing permissions set on that
      file; confirm it's viewable by organizers before submission). Status
      is **user-reported recorded, not independently verified by this
      agent** — this environment cannot open/play a Drive link, so the
      content (does it show `GJ19BR3000`/`cam06`, the terminal proof shot,
      etc. per `DEMO_SCRIPT_OWN_FEED.md`) has not been confirmed frame by
      frame. Whoever does final QA on the submission package should watch
      it end-to-end against the script's shot list once before the
      deadline.
- [x] **Record the government-feed / live demo video — recorded
      2026-09-28 (§9.4).**
      Link: <https://drive.google.com/file/d/1CF0ERX-ZqiYPoCCmkkACkZPoXBKcaSWM/view?usp=sharing>
      Same caveat as above: **user-reported recorded, not independently
      verified by this agent** — link accessibility and actual on-screen
      content (per `DEMO_SCRIPT_GOVERNMENT_FEED.md`'s shot list, including
      the two-system unified-viewer shot) still need a human watch-through
      before submission.
- [x] Solution Presentation (PPT) — v2 done 2026-09-04.
- [x] Technical Proposal / HLD — `sentinel-solution/docs/HLD.md`
- [x] Scalability Strategy — `sentinel-solution/docs/SCALABILITY.md`
- [x] Real-footage ANPR accuracy measurement — **reopened then
      re-closed, 2026-09-26 — use the new plate, not the old one.**
      2026-09-05 work fixed two real bugs (missing close-range camera
      coverage, two-line-plate/homoglyph matching in `anpr.py`) and
      captured one real scan's OCR votes for `GJ01RP6128` at confidence
      0.81. That specific capture did not reproduce across 5 fresh scans
      2026-09-26 (928+1,057 real vehicle detections, 0 reads) — but a 6th
      scan (all 30 cameras) produced a fresh, visually-confirmed real
      read: `cam06`, `GJ19BR3000`, 6/6 consecutive samples, confidence
      0.917–0.977. The algorithmic consensus-vote fix remains validly
      locked in either way
      (`test_consensus_plate_real_cam06_vehicle_clears_confidence_gate`
      tests the code's behavior given fixed captured votes, independent
      of which live capture supplied them). **Current status: real,
      reproduced, end-to-end ANPR on live sandbox footage, demonstrated
      2026-09-26 — cite `GJ19BR3000`, not `GJ01RP6128`.** See
      `REQUIREMENTS_COVERAGE.md`'s "ANPR-based metadata generation" row
      for the full 6-scan sequence. `HLD.md` §3 has the same update.
- [x] HLS proxy 502/403 — done 2026-09-05 (CDN User-Agent gate, fixed in
      `catalogue.py`).
- [x] ANPR two-line-plate + homoglyph OCR bug — done 2026-09-05, see above.

## P1 — do before/alongside the videos if time allows

- [x] **State-code whitelist for `_STATE_SERIES` — RESEARCHED 2026-09-19,
      NOT IMPLEMENTED, needs a go/no-go decision.**

      `anpr.py`'s `_STATE_SERIES` accepts `[A-Z]{2}` for the state code, so
      any two letters pass: `XQ01AB1234` and `ZZ01AB1234` both validate as
      plates today. Restricting the position to real RTO codes cuts that
      slot from 676 combinations to 40 — roughly a 94% reduction in the
      false-positive surface at the most error-prone character positions.

      **The authoritative list was gathered 2026-09-19** (Wikipedia,
      *Vehicle registration plates of India*). 36 current codes — 28 states
      + 8 UTs:

      `AN AP AR AS BR CG CH DD DL GA GJ HP HR JH JK KA KL LA LD MH ML MN
      MP MZ NL OD PB PY RJ SK TG TN TR UK UP WB`

      **Plus 4 RETIRED codes that MUST also be accepted** — a state rename
      does not re-register existing vehicles, so these are still in traffic:

      | Retired | Became | When |
      |---|---|---|
      | `TS` | `TG` | 14 Mar 2024 — ~10 years of Telangana registrations |
      | `DN` | `DD` | 25 Jan 2020 |
      | `OR` | `OD` | 2011 (Orissa → Odisha) |
      | `UA` | `UK` | 2007 (Uttaranchal → Uttarakhand) |

      Diplomatic (`CD`/`CC`/`UN`/`IOD`) and military (broad-arrow) plates use
      different formats entirely and never match `_STATE_SERIES`.

      **Why this is NOT a free win, and why it was deferred rather than
      built.** A whitelist is *the same class of construct that caused the
      BH-series bug fixed earlier the same day* — an over-tight validator
      that silently discards valid plates. Get it wrong and the defect
      recurs for a different population, and `TS` alone would be a far
      bigger blast radius than BH ever was. Precision gain vs. the risk of
      silently eating Telangana is a bad asymmetry this close to
      submission.

      **Only implement with the lesson applied — make the failure loud:**

      1. Whitelist = 36 current **+ 4 retired**, each retired entry
         commented with its date and why it is still accepted.
      2. When a read matches the plate *shape* but carries an unrecognised
         state code, **log a WARNING naming the code**. This is the whole
         point: it converts the silent failure mode that made the BH bug
         invisible into an observable signal, so a missing code shows up in
         logs instead of quietly dropping plates.
      3. Tests: all 40 validate; `XQ`/`ZZ` rejected; the warning actually
         fires on an unrecognised code.

      **Implemented 2026-09-26, exactly as planned above, and triggered by
      a real live case, not a hypothetical.** During the 2026-09-26
      11h-`cam06` sandbox scan (interrupted early by an unrelated low-memory
      background-job reap, see below), OCR produced `FS11ICO9525` on one
      frame and the correct `GJ11CO9625` on a nearby, clearer frame of the
      same vehicle — "FS" is not a real state/UT code, exactly the false
      positive this task predicted. `anpr.py`: added `_KNOWN_STATE_CODES`
      (36 current + 4 retired, each retired code commented with its date),
      `_STATE_SERIES_RE` to distinguish a state-series match from a
      BH-series match inside `_best_pattern_match`, and a `logger.warning`
      naming the exact rejected code (once per call, on the plain candidate,
      not spammed across every homoglyph-flip variant). AUTOMATED-TEST
      VERIFIED: 5 new tests in `test_anpr.py` (all 40 codes validate, `XQ`/
      `ZZ` rejected, the warning fires and names the code, BH-series
      unaffected, the 4 retired codes individually) — full suite 319
      passed. LIVE/REAL VERIFIED: re-ran the actual `PaddleOcrPlateReader`
      against both real saved crops from the incident above —
      `GJ11CO9625` still reads correctly, `FS11ICO9525`'s frame now
      returns `None` with the warning firing exactly as designed.

      Without step 2, recommend **not doing this before submission**.
      `[NOT ESTABLISHED]` — whether re-registration after a state rename is
      ever mandatory; the conservative reading (accept retired codes) is the
      only safe one either way.

**Re-researched 2026-09-10** (4 parallel research-only passes, no code
changed yet — findings below replace the previous vague entries with
confirmed status + a concrete described fix for each).

- [x] **Stale-search race — fixed 2026-09-10.** Confirmed the race
      survived the frontend rebuild in both `VehicleIntelligence.jsx` and
      `SearchView.jsx` (`submit()` in each fired a plain `fetch` with no
      request-sequencing, so a slow first search could overwrite a faster
      second search's results). Fixed with an `AbortController` per
      submit in both components: the previous in-flight request is
      aborted before a new one starts, and `api.js`'s `vehicleHistory`/
      `searchByAttributes` now accept and forward an optional `signal`.
      Verified with `npm run build` (clean) and `npm run lint` (no new
      warnings); not click-tested in a live browser this session (no
      browser automation tool available) — worth a manual double-search
      check before the demo.
- [x] **`create_api_key` 200-vs-400 — fixed 2026-09-10.** `routes_auth.py`
      now imports `HTTPException` and raises `HTTPException(400, "role
      must be one of admin, investigator, viewer")` for an invalid role
      instead of returning `{"error": ...}` with HTTP 200. Regression
      coverage added in `tests/test_auth.py`
      (`test_invalid_role_raises_400`, `test_valid_role_creates_key`);
      full suite re-run, 45/45 passed.
- [x] **`search_by_attributes` truncation — fixed 2026-09-10.**
      `routes_vehicle.py` now runs a `count()` query alongside the
      limited fetch and returns `total_count`/`truncated: total_count >
      200` in the response; switched ordering from oldest-first
      (`asc()`) to newest-first (`desc()`) so a truncated response
      surfaces the most recent matches rather than silently dropping
      them. `SearchView.jsx` now shows "N of M total" and a truncation
      notice when applicable. Regression coverage added in
      `tests/test_vehicle_search.py`; full suite re-run, 47/47 passed.
      `npm run build`/`npm run lint` both clean, no new warnings.
- [x] **Gap-analysis PDF export — fixed 2026-09-10.** Added
      `GET /cameras/gap-analysis/export.pdf` (`routes_cameras.py`),
      reusing the same `_compute_gap_analysis` data as the existing JSON
      endpoint (no second, independently-computed report) and rendering
      via `reportlab` (added to `requirements.txt`, not previously a
      dependency) — summary table, cameras-by-department breakdown, and
      each gap category's camera-id list. Same department-scoping as the
      JSON endpoint and the CSV export. `GapAnalysisPanel.jsx` got an
      "Export PDF" button (`api.js`'s `downloadGapAnalysisPdf` — fetches
      as a blob since the API key is a custom header, not a cookie, so a
      plain `<a href>` can't authenticate). Regression coverage in
      `tests/test_gap_analysis_pdf.py` (including a real bug caught by
      the empty-department-breakdown test: `[header] + [rows] or
      [fallback]`'s `or` never fires because concatenation is always
      truthy — fixed with explicit parens before it shipped). A real
      sample PDF was generated end-to-end against the live 30-camera
      sandbox catalogue (not synthetic data) via a temporary,
      immediately-revoked admin key and saved to
      `docs/assets/sample_gap_analysis_report.pdf` for the submission.
      Full backend suite re-run, 50/50 passed; `npm run
      build`/`npm run lint` both clean.
- [x] **Doc-honesty points — closed 2026-09-10.**
      1. **Multi-vendor wording** — `docs/submission/EMAIL_DRAFT.md`
         reworded: no longer implies proven integration with
         VISWAS/NETRAM/TRINETRA, now explicit that this submission
         demonstrates the architecture against the hackathon sandbox,
         not a live connection to those systems.
      2. **Private/commercial CCTV coverage** — added a paragraph to
         `HLD.md`'s onboarding section: same onboarding flow as
         departmental cameras, tagged by owning entity, contingent on
         that entity's access grant; explicitly labeled design-only, not
         built or demonstrated.
      3. **External-DB integration honesty** — confirmed already closed,
         `HLD.md`'s "query, don't copy" principle already states this
         explicitly for VAHAN/SARTHI/eGujCop/CCTNS.
      `MODULE_GAP_ANALYSIS.md`'s discussion points section updated to
      mark all 3 resolved. Docs-only change, no code touched.
- [x] **`CODEX_HANDOFF_PROMPT.md`'s ML-3 — run for real 2026-09-10, real
      findings, threshold intentionally NOT changed.** New
      `scripts/calibrate_embedding_threshold.py` run against the actual
      accumulated `sentinel.db` (11,832 real crops). **Positive side
      (recall): still genuinely blocked** — only 6 events have both a
      crop and plate, 0 plates repeat across cameras, only 4 identity
      links were ever plate-verified (not appearance-circular) — a
      concrete number confirming the same conclusion this item already
      had, not a new gap. **Negative side (false-positive rate): a real,
      concerning finding** — 41.87% of 3,000 confirmed-different-vehicle
      real crop pairs scored ≥ the current 0.80 threshold (median
      negative-pair score 0.776, right at the threshold) —
      `ColorHistogramEncoder` is a weak discriminator on this dataset.
      **Deliberately did not raise the threshold**: doing so on
      negative-only evidence with zero positive/recall data risks
      silently breaking the system's actual documented differentiator
      (cross-camera identity continuity without a plate read) — a
      measured false-positive fix traded for an unmeasurable
      false-negative regression isn't a net improvement (confirmed via
      `advisor` before deciding). Cross-checked against the same day's
      Model 1 gap-analysis work: the demo-lead camera (`cam06`) HAS GPS
      set, so `identity.py`'s geo-feasibility gate is active and
      compensating for the weak embedding on the actual headline demo
      case; residual exposure is the ~8/30 cameras with no GPS at all,
      where the weak embedding is the only gate. Full writeup + numbers
      in `CODEX_HANDOFF_PROMPT.md`'s ML-3 section; `identity.py`'s
      `EMBEDDING_SIMILARITY_THRESHOLD` comment updated to cite this,
      not a guess. Full backend suite 55/55 passed (comment/script-only
      change, no runtime behavior changed).
- [x] **Per-character consensus voting in `tracker.py`'s
      `consensus_plate()` — done 2026-09-10.** Replaced exact-string
      majority vote with position-weighted character voting: `Track` now
      keeps raw `plate_reads` (not pre-bucketed by exact string), reads
      are grouped by length (position voting is only meaningful within
      same length — a different-length read is either a different plate
      or a dropped/added-character OCR miss, no edit-distance alignment
      attempted, per this item's documented scope), the length-group with
      the most total confidence wins, and the final plate/confidence come
      from a per-position confidence-weighted vote (ties broken by
      first-seen character, matching the old algorithm's tie-break).
      Confidence is the weakest position's vote share, which — proven by
      hand-deriving all 4 existing test cases before touching code —
      reproduces the OLD algorithm's numbers exactly whenever all reads
      share one length (all 4 pre-existing `test_consensus_plate_*` tests,
      including the real cam06 regression test, pass unchanged with
      identical confidence values). Two new tests added:
      `test_consensus_plate_position_voting_recovers_read_exact_string_voting_would_fail`
      (the actual documented gap: 5 reads with 5 DIFFERENT single-char
      misreads at 5 different positions — old algorithm sees 5 equal-vote
      candidates at 0.2 confidence each, rejected below
      `PLATE_MIN_CONFIDENCE`; new algorithm recovers the correct plate at
      0.8, clearing the gate) and
      `test_consensus_plate_different_length_reads_grouped_separately`
      (a dropped-character read doesn't get position-voted against
      correct-length reads). Full suite 55/55 passed.

## P2 — known code issues, not yet fixed (lower demo-visibility risk)

- [x] **`tracker.py`'s `consensus_plate()` can synthesize a plate string
      that matches no actual OCR read — PARTIALLY MITIGATED 2026-09-13, not
      fully closed.** Found and investigated by an independent project
      review (2026-09-11); two earlier fix attempts (a post-hoc confidence
      penalty, a plate-agreement guard) were reverted on evidence — both
      broke `test_consensus_plate_isolates_higher_vote_share`/
      `test_consensus_plate_confidence_is_vote_share_not_count`. The
      documented real fix (an appearance-embedding distance check between a
      candidate track's stored crop and a new detection's crop before
      merging, via `reid.py`) was implemented 2026-09-13:
      `CameraTracker._appearance_compatible()` rejects an IOU-fallback merge
      when `ColorHistogramEncoder` similarity is below 0.80 (identity.py's
      existing threshold). **Known limitation, documented in code**: that
      same encoder was independently measured
      (`scripts/calibrate_embedding_threshold.py`, 2026-09-10) at a 41.87%
      false-positive rate on real confirmed-different vehicle pairs, so this
      guard reliably catches only grossly dissimilar vehicles (its own test
      uses solid black vs. white crops) and will likely still miss the
      realistic same-color-class contamination case. A real fix needs a
      stronger encoder, not a threshold change on this one — not attempted.
      (`analytics/tracker.py`)

~~RTSP discontinuity detection doesn't survive a reconnect~~ — **fixed
2026-09-13**, see the new section above. (`streaming/rtsp_client.py`)
~~No FFmpeg read-timeout on `cap.read()`~~ — **fixed 2026-09-13**:
`config.RTSP_READ_TIMEOUT_US` (default 5s) via `OPENCV_FFMPEG_CAPTURE_OPTIONS`'s
`stimeout`. (`streaming/rtsp_client.py`)
~~Frontend: Safari's native-HLS path sends no API key~~ — **fixed
2026-09-13**: shows an explicit "requires Chrome/Firefox/Edge" message
instead of a silently blank player (a real fix — signed-URL/cookie auth for
Safari's native path — is out of scope, this makes the failure honest
instead of silent). (`frontend/src/components/LiveView.jsx`)
~~Frontend: map view doesn't distinguish OBSERVED vs. INFERRED route
segments~~ — **fixed 2026-09-13**: route segments and stop markers now use
the same evidence-tier styling as the Vehicle Tracking timeline panel
(solid green/amber for CONFIRMED/PROBABLE, dashed red for LEAD_ONLY); a
missing `evidence_class` fails conservative to LEAD_ONLY/INFERRED rather
than defaulting to an "OBSERVED" label. (`frontend/src/components/MapView.jsx`)
~~Frontend: alert-list polling can race a user's transition click~~ —
**fixed 2026-09-13**: pending transitions are tracked locally and a
concurrent poll response for that alert is ignored until the transition
resolves; action buttons disable while pending; a 409 (already-transitioned)
response shows a plain refresh message instead of raw backend error text.
(`frontend/src/components/AlertsPanel.jsx`)

~~VehicleIdentity history lookup uses `.first()` on a non-unique query
pattern~~ — **not actually a bug**, re-verified 2026-09-05: `vehicle_identity
.plate` has had a partial-unique DB constraint since 2026-09-04, so
`.filter(plate==...).first()` can structurally never match more than one
row. Remove from backlog.

~~Possible SSRF/credential-leak gap in the HLS proxy~~ — **already fixed**,
per `REVIEW_FINDINGS.md`'s `SEC-doc` entry (host-allowlist check +
`allow_redirects=False`) — this TASKS.md entry was stale, not a real open
item.

## P3 — nice-to-have if time remains

~~Multi-camera grid / video wall~~ — **done 2026-09-05** (`CameraGridView.jsx`).
~~Department-scoped RBAC~~ — **done 2026-09-05** (`api/auth.py`'s `department_scope`).
- [ ] WHEP low-latency preview (HLS-via-proxy is the working path; low
      priority — not required by the test case).
- [x] **Backend search/filter query params on `/cameras` — done
      2026-09-10.** Added `department`/`camera_type`/`is_healthy`/`live`
      (exact match) and `q` (case-insensitive substring on id/location)
      as optional query params on `GET /cameras`; applied after
      department-scoping so a non-admin key still can't see outside its
      own scope. No existing client-side camera-filter UI was found to
      migrate (the frontend rebuild appears to have dropped it, same as
      the old `VehicleSearch.jsx`) — left as a backend capability with
      regression coverage (`test_camera_registry_model1.py`), not wired
      to a new frontend surface, to avoid inventing UI beyond what was
      asked.
- [x] **Coverage-radius/zone GIS map layer, ageing-infrastructure
      tracking — done 2026-09-10.** Added `CameraRegistry.install_date`/
      `coverage_radius_m` (additive migration in `db/session.py`), wired
      into `CameraOnboard`/`_apply_onboard_fields`/`_merged_camera_view`/
      CSV export/`OnboardCameraForm.jsx`. `MapView.jsx` renders a
      coverage-radius `Circle` per camera with a radius set, and a
      dashed marker outline + popup note for cameras installed more than
      `SENTINEL_CAMERA_AGEING_THRESHOLD_YEARS` (config.py, default 5)
      ago. Gap-analysis JSON/PDF/`GapAnalysisPanel.jsx` all report
      `ageing`/`missing_install_date` alongside the existing categories.
- [x] **Camera-onboarding audit trail — done 2026-09-10.** New
      `CameraAuditLog` table (separate from the existing purpose-bound
      `AuditLog`, which doesn't fit a registry edit) records `onboarded`
      vs. `updated` per camera per onboard/bulk-onboard call, with
      `user_id`/`created_at`. New admin-only `GET
      /cameras/{camera_id}/audit-log`. Regression test caught a real
      ordering bug: two edits in the same test can share an identical
      `created_at` (default's resolution can tie), making `ORDER BY
      created_at DESC` nondeterministic — fixed with an `id DESC`
      tiebreak; confirmed deterministic across 5 repeated full-suite runs
      after the fix.

All three verified: real additive migration run against the actual
accumulated `sentinel.db` (not a fresh DB) — both new columns and the new
table created cleanly, no data loss. Full backend suite 53/53 passed;
`npm run build`/`npm run lint` both clean, no new warnings.

- [x] **Real ONVIF device discovery — built.** `streaming/onvif_discovery.py`:
      WS-Discovery (UDP multicast Probe/ProbeMatch) + ONVIF Media SOAP
      calls (`GetCapabilities` → `GetProfiles` → `GetStreamUri`), raw
      hand-built SOAP/XML rather than a zeep-based client (small enough
      protocol surface to avoid the heavier WSDL-parsing dependency).
      Wired into `catalogue.py`'s `CatalogueClient.refresh()` as
      ONVIF-first: tried on every refresh when `SENTINEL_ONVIF_ENABLED=true`
      (default `false`), falling back to the existing sandbox HTTP
      catalogue automatically and loudly-logged when no ONVIF device
      responds — the sandbox's actual, permanent state (§13a: plain RTSP,
      no ONVIF endpoint at all), so this is the expected fallback path,
      not an error condition. XML parsing uses `defusedxml` (new dep) to
      guard against XXE from untrusted device responses, per this repo's
      untrusted-input rule. 14 new regression tests
      (`tests/test_onvif_discovery.py`, mocked WS-Discovery/SOAP
      exchanges — no live ONVIF device is reachable from this environment
      or the sandbox to test against for real); full backend suite 84/84
      passing (70 pre-existing + 14 new), run for real in a freshly
      created `.venv` (none existed in this environment beforehand).
      **Honestly unverified against a live ONVIF-conformant camera** —
      that remains the one open gap before this could be trusted in an
      actual departmental deployment; see
      `docs/models/model-2-unified-viewing/IMPLEMENTATION_PLAN.md`'s M2-4.

- [x] **Minor hardening batch — done 2026-09-11.** `/health` now reports
      `active_camera_worker_count` (an int) instead of the raw camera-ID
      list to an unauthenticated caller; `VehicleEvent` gained a separate
      `ingested_at` column alongside `observed_at` (additive migration,
      verified against a real on-disk pre-migration DB, not just a fresh
      one); a minimal in-process rate limiter (`api/rate_limit.py`, fixed-
      window per API key/IP, no new infrastructure) now guards every route
      except `/health` and `/live/*`; `architecture.drawio` updated to
      include the Model 3 federation layer and ONVIF discovery (previously
      absent — stale relative to the actual codebase). 5 new tests
      (`test_rate_limit.py`); full backend suite 100/100 passing.

## 2026-09-12 — evidence classification audit + demo readiness (done)

**Truthful state of the evidence feature, stated explicitly per the audit
below (do not claim more than this anywhere — deck, briefing, or demo
script):**

```
Evidence classification:        IMPLEMENTED
LEAD_ONLY UI export blocking:   IMPLEMENTED
§63 evidence-package generation: NOT IMPLEMENTED
```

`evidence_class.py` audited line-by-line. One real gap found and fixed: a
whitespace-only plate string is truthy in Python, so `classify("   ", ...)`
returned CONFIRMED before this fix. Unreachable through the real pipeline
today (`anpr.py`'s `PLATE_PATTERN.fullmatch()` already rejects it), but the
function is the single gate deciding exportability and must not depend on
that upstream invariant holding forever — hardened to `plate and
plate.strip()`. 5 new boundary tests (17 total for this module), including
one that locks the classifier's signature to `(plate, link_method)` only —
structural proof a high fused UI score can never influence the class,
because the function cannot see it.

### Rule table (deterministic, exhaustive over all 4 real `link_method` values)

| plate | link_method | class | rationale |
|---|---|---|---|
| any non-blank string | any | CONFIRMED | plate already passed `PLATE_PATTERN` + `PLATE_MIN_CONFIDENCE` upstream |
| None / empty / whitespace | `plate_continuation` | PROBABLE | same within-camera track as a sighting that read the plate |
| None / empty / whitespace | `plate_upgrade` | PROBABLE | same, retroactive upgrade case |
| None / empty / whitespace | `appearance_match` | LEAD_ONLY | appearance embedding only — 41.87% FPR measured |
| None / empty / whitespace | `new_identity` | LEAD_ONLY | no plate, no link — anonymous |
| None / empty / whitespace | unrecognised/None | LEAD_ONLY | fail conservative — never upgrade on an unknown case |

Only `CONFIRMED` is in `EXPORTABLE_CLASSES`. `PROBABLE` is deliberately
excluded too.

## 2026-09-12 — jury-ready UI rework + evidence tiering (done)

**Evidence classification is now real and enforced** (`analytics/evidence_class.py`).
Derived from persisted provenance — `plate` and `link_method` — so it needs no
migration and a badge can never disagree with the row it labels:

- `CONFIRMED` — this sighting read and validated its own plate.
- `PROBABLE` — no plate here, but linked by within-camera track continuity
  from a sighting that did read one (`plate_continuation` / `plate_upgrade`).
- `LEAD_ONLY` — linked by appearance only, or standalone anonymous. Not evidence.

Only `CONFIRMED` is exportable. `PROBABLE` is deliberately excluded too: an
export is where a hedge stops being visible. `/vehicle/{plate}/history` and
`/vehicle/recent` now return `evidence_class`, `evidence_class_reason` and
`exportable_as_evidence`; the frontend disables its export control from that
field rather than re-deriving the rule. 12 new tests.

**Measured over the real database:** 6 CONFIRMED, 12,251 LEAD_ONLY out of
12,257 events — an independent reproduction of DECISION_REVIEW_2026-09-11.md's
central finding. Identity `GJ01AB1234` shows the demo shape exactly: five
sightings, one CONFIRMED (cam03, where the plate was read), four leads.

**Navigation regrouped** by operator intent (Operations / Investigations /
Camera Intelligence / Evidence / Integrations / System) instead of leaking our
internal Model 1/2/3 structure into the product.

**New screens, all real-endpoint backed:** Camera Health (operational state
only — no fabricated packet-loss/latency/uptime figures, because nothing
measures them), Coverage & Gaps, Connected Systems (states plainly that
department labels behind one gateway are *not* two systems — CLAUDE.md §10),
Watchlist & Alerts combined, User Administration (`/auth/api-keys`, minted key
shown once).

**Three destinations ship an honest "not yet implemented" screen** naming the
exact backend work required, rather than being hidden or faked: Investigation
Cases, ANPR Readiness, Evidence Export (§63). Wording throughout is
"§63-oriented", never "court admissible". *(Superseded 2026-09-19: ANPR
Readiness and Evidence Export are now built and wired — see the entry at the
top of this file. Investigation Cases remains a placeholder.)*

Verified: 119/119 backend tests, `npm run lint` (no new warnings), `npm run
build` clean, and every new endpoint exercised over real HTTP against a running
`app.main` with the real `sentinel.db`.

### Government-feed readiness, checked 2026-09-12

| Item | State |
|---|---|
| Sandbox catalogue access | **PASS** — 30 cameras, HLS + RTSP URLs present |
| HLS playback | **PASS** — cam06 playlist 200, valid `#EXTM3U`, 14,690 segments |
| Searchable event / movement history | **PASS** — verified over HTTP |
| Persisted camera ID + timestamp | **PASS** |
| Watchlist correlation + alerts | **PASS** |
| Timestamped output report | **PASS** — gap-analysis and federation PDFs |
| Real ANPR output | **PASS (historic)** — `data/anpr_scan/20260905T112430Z`, 7 reads |
| GIS mapping | **PARTIAL** — 22 of 30 cameras have coordinates; the sandbox
  catalogue supplies none, they come from our registry |
| RTSP analytics producing new events | **PASS (updated 2026-09-13)** —
  live-verified on this machine's Python 3.12 venv against the real
  sandbox: a torch/torchvision ABI mismatch was found and fixed
  (`pip install --upgrade torchvision`), real fresh detection events
  now land in `sentinel.db` (e.g. `cam11`, confidence 0.72). Plate reads
  still absent — `paddleocr`/`paddlepaddle` not installed here, honest
  `StubPlateReader` fallback active. |
| Full government-feed demo session | **RETRACTED "externally blocked"
  status — see below** |

### Government-feed blocker retraction, 2026-09-12

**The prior "externally blocked" status was stale and imprecise.** It traced
to one undated 2026-09-05 remark — "the hackathon's own sandbox is still
being fixed on their end" — with no named endpoint, no error, and no
re-check in a week. This session verified directly against the live sandbox
today: catalogue login succeeds, 30 cameras returned, and `cam06`'s HLS
playlist returns 200 with a valid `#EXTM3U` header and 14,690 segments. The
premise of the blocker does not hold today.

**Separately, and more importantly: `HACKATHON_DETAILS.md` §12 states the
sandbox itself already qualifies as "Government-Provided CCTV Feed."**
Verbatim: *"~12 hours of CCTV footage from each of 30+ cameras, across 5
departments: Health, Police, GSRTC, Panchayat, Municipal Corporation... Real
footage, no synthetic data... served as simulated live video."* §"Phase 1 –
Sandbox Round" vs "Phase 2 – Production Round" confirms this sandbox is the
intended Phase 1 government feed; a separate production environment exists
only for the 6 Grand Finale qualifiers. The project's own prior framing — a
second, distinct "government feed" recording session, gated on the
organizers — was a misreading of the spec, not a real technical blocker.

**One genuine, narrow gap found and fixed:** Q33 requires "output report
showing detected vehicles/plates with timestamps"; no such export existed
(`ReportsView.jsx` had gap-analysis, audit-log, and watchlist reports only).
Added a "Vehicle detections report" entry reusing the existing
`/vehicle/recent` endpoint and `download()` pattern — zero new backend code.

**Status: READY NOW** for everything except a fresh live-ML detection
moment, which depends on the ML runtime (being verified on a second
machine, see above) rather than on any organizer dependency.


## 2026-09-13 — scoped Model 4 pilot slice

- [x] **AUTOMATED-TEST VERIFIED:** `CameraDensityWindow` aggregates actual
      sampled-frame vehicle/person detector outputs. `GET /admin/density`
      labels them as raw detections, not unique people/vehicles or crowd size.
- [x] **IMPLEMENTED, UNVERIFIED:** `VehicleEvent.storage_tier` and dynamic
      hot/warm/cold classification expose metadata only; no object storage is deployed.
- [x] **AUTOMATED-TEST VERIFIED:** `GET /admin/central-rollup` combines real
      pilot registry, health, alert and federation data for admins.
- [x] **IMPLEMENTED, UNVERIFIED:** `DR_RUNBOOK.md` defines a SQLite
      backup/restore procedure. Multi-region DR remains a DESIGN TARGET.
- [x] `DeliberatelyExcludedFaceRecognizer` is an honest Protocol seam that
      raises rather than fabricating FRS results. FRS and government-database
      integrations remain deliberately excluded/external-access dependent.

## Deliberately not doing (see STRATEGY.md's OUT list — don't silently build these)

Face recognition, fingerprint/biometric integration, full 80k-camera
physical ingestion, a new VMS, real per-vendor VMS federation middleware,
actually deploying Kafka/MediaMTX this week.

## How to verify any fix in this list

Per this project's CLAUDE.md: don't declare a fix done from a syntax check.
Exercise it with `scripts/demo_end_to_end.py` (real models) and/or a live
request against `python -m app.main`, including the failure mode it's
supposed to handle — not just the happy path.
