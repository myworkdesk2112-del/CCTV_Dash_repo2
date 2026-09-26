# Three-lens code review — findings and fix tracker

Generated 2026-09-04 by three parallel review passes (software engineering,
ML engineering, security engineering) over the post-identity-fix codebase.
Excludes anything already logged as a deliberate, documented gap in
`HLD.md` §10 — this file is for things those reviews found that weren't
already known. All items below marked DONE were fixed AND verified at
real runtime (not just import/syntax checks) — see each entry for how.

**Status: 15 of 17 findings fixed and verified (updated 2026-09-05 — the
full plate-localizer fix is now done, see ML-1 below, which also gained a
second real fix the same day — a two-line-plate/homoglyph bug in
`anpr.py` — after finding a genuinely ANPR-suitable camera among the 30
sandbox cameras). ML-4 is now materially advanced (real plate reads
achieved, not just a localization-only fix) but not fully closed — no
formal precision/recall table, and cross-frame consensus-voting
consistency is a new, separate open item (see `HLD.md` §3). ML-3 still
needs real labeled same-vehicle pairs — see `CODEX_HANDOFF_PROMPT.md`;
the deadline moved to 15 Sep (was 7 Sep), so there may now be time to do
this in-session rather than handing it off.**

## Tier 1 — fix before any external demo (all done)

- [x] `SEC-1` Sandbox RTSP/WHEP login credentials (`email:password@`,
  embedded by `catalogue.py:66-67`) were exposed to `viewer`-role API keys
  via `GET /cameras` / `GET /cameras/{id}` (`routes_cameras.py`'s
  `_merged_camera_view`). **Fix:** `rtsp_url`/`whep_url` now null unless
  caller is admin — the frontend never reads either field, only
  `hls_url` via the authenticated proxy. **Verified:** real HTTP call
  with a viewer key returns null for both fields on all 30 cameras; an
  admin key gets the real values.
- [x] `SEC-3` `GET /admin/audit-log` only required `investigator` role
  despite the `/admin` prefix — any investigator could read every other
  investigator's/department's search purposes and case IDs
  (`routes_admin.py:46-50`). **Fix:** scoped to the caller's own `user_id`
  unless admin (preserves the Investigations screen's intended use by
  investigator-role accounts, rather than a hard admin-only lock).
  **Verified:** real HTTP calls — an investigator key sees only its own
  logged query; an admin key sees all users' rows.
- [x] `ML-1` The live-wired plate localizer was `StubPlateDetector`
  (`plate_detector.py:29-42`), a fixed 20-80%×55-95% geometric crop of the
  vehicle bbox — confirmed wired via `main.py:98` (`plate_detector=`
  never overridden). **Verified directly:** extracted the exact
  plate-region crop from 3 real saved sandbox vehicle crops (a car + two
  motorcycles) and looked at all three — every one shows side
  panel/engine/seat, never a plate, because these cameras' overview angle
  never presents the front/rear face the heuristic assumes.
  **Fix (2026-09-05, full model fix, not just documentation):** confirmed
  at N=466 (`scripts/real_anpr_scan.py` against all 30 live sandbox
  cameras, no compositing — same 0-reads outcome as N=4). Accepted the
  AGPL-3.0 licensing decision (project owner's explicit call, re-checked
  MIT/permissive alternatives first — none cleared the safe-format +
  credible-publisher bar `morsetechlab` does) and wired
  `YoloPlateDetector` (morsetechlab/yolov11-license-plate-detection ONNX)
  into `main.py` as the default. **Verified:** re-ran the real localizer
  offline against the 62 saved real crops from the scan — it correctly
  finds cam01's actual plate region (a real ~25×16px patch at the
  vehicle's lower-left corner) that the stub totally missed. OCR read
  count is still 0/62 — the plate is too small/low-resolution at this
  camera's distance to read regardless of localization correctness, a
  separate, now-measured limitation (see `HLD.md` §3). Also caught a real
  false positive during this verification: the vehicle detector
  misclassified a "GUJARAT POLICE" signboard as a vehicle on cam02; the
  plate-region localizer then fired on the signboard's text banner, but
  `anpr.py`'s `PLATE_PATTERN` regex correctly rejected the resulting
  non-plate-format OCR candidate before it could reach identity resolution
  or a false alert. Also found and fixed a real dependency conflict during
  this work: loading the ONNX weights the first time triggers ultralytics'
  auto-update, silently bumping `protobuf` to a version that breaks
  paddlepaddle 2.6.2 — fixed by pinning `onnx==1.14.1`/
  `onnxruntime==1.17.3`/`protobuf==3.20.2` in `requirements-ml.txt`.

**Second, independent ML-1-adjacent bug found and fixed, 2026-09-05
(same day, later).** With the localizer fixed, real footage still
produced 0 plate reads — until reviewing all 30 sandbox cameras (per
direct organizer guidance to use "any clearly-visible sandbox camera")
surfaced `cam06`, a genuinely close-range, ANPR-suitable camera. Testing
against it found a SECOND real bug, this time in `anpr.py`: the vehicle's
plate is a two-line format (state+RTO on one line, series+number on the
next — common on two/three-wheelers), and `read()` only ever
pattern-matched each PaddleOCR-detected line individually, so a two-line
plate could structurally never fullmatch on either line alone. **Fix:**
`read()` now also concatenates all detected lines (sorted top-to-bottom
by bounding-box y) into one joined candidate, with bounded, symmetric
homoglyph correction for OCR's 0/O, 5/S, 1/I, 8/B, 2/Z confusion
(`_ambiguous_variants`/`_best_pattern_match`). **Verified:** individual
-frame pattern-valid reads on `cam06`'s real vehicle track went from 0/13
to 8/13; `tests/test_anpr.py` (5 new tests) plus the full existing 37
-test suite and `demo_end_to_end.py` all still pass. **Honestly still
open:** the 8 reads aren't character-for-character consistent across
frames, and `tracker.py`'s exact-string `consensus_plate()` vote-share
lands below the 0.5 confidence floor as a result — see `HLD.md` §3.

## Tier 2 — worth fixing, all done

- [x] `SEC-2` Bootstrap admin key was logged in cleartext via
  `logger.warning` (`auth.py:85-88`) — a permanent plaintext credential
  in any shipped log history. **Fix:** `print()` directly, bypassing the
  logging framework entirely.
- [x] `SWE-1` N+1 queries: `routes_cameras.py`'s `_merged_camera_view`
  (one `session.get()` per camera) and three call sites in
  `routes_vehicle.py` (`recent_detections`, `vehicle_history`,
  `search_by_attributes`). Harmless at 30 cameras, undercuts the
  80k-camera scalability story. **Fix:** batch-fetch cameras into a dict
  once per request (`_cameras_by_id()` helper); `_merged_camera_view` now
  takes an already-fetched registry row instead of fetching its own,
  which also fixed a redundant double-fetch `get_camera` was doing.
  **Verified:** real HTTP calls to `/vehicle/recent` and `/cameras` after
  the refactor return identical, complete data (location/department/etc.)
  as before.
- [x] `SWE-3` CORS wide open (`main.py:37`, `allow_origins=["*"]`) on a
  backend holding police investigative data. **Fix:** new
  `config.CORS_ALLOWED_ORIGINS`, defaulting to the known Vite dev origins,
  overridable via `SENTINEL_CORS_ALLOWED_ORIGINS`. **Verified:** real HTTP
  calls — an `Origin: http://evil.example.com` request gets no
  `Access-Control-Allow-Origin` header back; `http://localhost:5173` does.
- [x] `ML-2` Color attribute extraction (`attributes.py`) nearest
  -neighbored raw RGB pixel medians against fixed reference points —
  lighting-sensitive by construction (shadow reads grey, sodium-vapor
  reads yellow/orange). **Fix:** HSV, saturation-gated (achromatic family
  classified by brightness alone, chromatic family by hue), with V
  normalized against the crop's own brightness range. **Verified:** a
  real runtime test reproducing both named failure modes, plus baseline
  cases and an "don't over-correct a real orange car" case — all 8 pass.
  Two honest, disclosed remaining limitations found while testing (see
  `attributes.py`'s docstring): a strong colour cast can still cross the
  saturation gate, and white/silver can blur into each other under the
  same normalization that fixes the shadow case.
- [x] `ML-5` `consensus_plate()`'s vote-share (`tracker.py:99-108`) is a
  reasonable heuristic but uncalibrated, yet the UI rendered it as "plate
  read (100%)" — reads as a calibrated probability when it isn't one.
  **Fix:** relabeled to "consensus strength" in `VehicleTimeline.jsx`,
  `ExplainabilityPanel.jsx`, and `EvidenceView.jsx`.
- [x] `SWE-5` No sync check between SQLAlchemy models and
  `_ADDITIVE_MIGRATIONS` (`db/session.py`) — a missed migration entry only
  surfaced as a runtime "no such column" error against an existing DB.
  **Fix:** `_check_models_match_db()`, runs after migrations, raises
  loudly on any mismatch. **Verified:** stays silent against the real,
  correctly-migrated `sentinel.db`; raises correctly against a
  deliberately desynced column added to an already-existing table.
- [x] `SWE-2` Lock-ordering hazard in `streaming/manager.py` —
  `reconcile()`/`stop_all()` called `worker.stop()` (joins thread, up to
  5s) while holding `self._lock`, which the frame callback and
  `health_snapshot()` also need. **Fix:** released the lock before
  worker.start()/stop(), keeping only dict bookkeeping under it.
  **Verified with real threads** against unreachable RTSP URLs:
  `stop_all()` still takes its expected ~N×5s (bounded by each worker's
  join timeout — cv2's own RTSP connect attempt can block up to ~30s
  against an unreachable host, a separate pre-existing issue, see SWE-6
  below), but a concurrent `health_snapshot()` poller completed 597 calls
  with a max 0.05s gap during that entire window — confirmed no longer
  lock-starved.
- [x] `SEC-doc` A stale "possible SSRF gap" note in `README.md`'s "Known
  issues" list (not `HLD.md`, which already correctly documents the fix).
  **Verified independently:** the host-allowlist check on the client
  -supplied segment URL (`routes_stream.py:77-79`) AND
  `catalogue.py`'s `authenticated_get` using `allow_redirects=False`
  (never follows a redirect to another host at all) both close this.
  Removed the stale README entry.
- [x] `SEC-5` `purpose` field on investigator queries was unvalidated free
  text — nothing stopped `purpose=""` from satisfying the DPDP
  purpose-bound-query claim. **Fix:** `Query(..., min_length=8)` on all
  three `purpose` parameters in `routes_vehicle.py`. **Verified:** real
  HTTP calls — empty and 1-character purposes get 422, a genuine purpose
  gets 200.
- [x] `SEC-6` `routes_vehicle.py`'s module docstring claimed "every lookup
  is purpose-bound and logged," overclaiming relative to the intentional,
  already-documented `GET /vehicle/recent` exception. **Fix:** corrected
  the docstring wording.

## Tier 3 — lower priority / hardening for later (not attempted)

- [ ] `SWE-6` (found while verifying SWE-2's fix, not from the original
  three reviews) `RtspCameraWorker.stop()`'s `.join(timeout=5)` can return
  due to the timeout, not because the thread actually exited — if stuck
  inside `cv2.VideoCapture`'s blocking open call against an unreachable
  host (FFmpeg's own timeout there is ~30s, not interruptible by the
  `self._stop` flag), the thread lingers up to ~30s after `stop()`
  returns before it notices `_stop` and exits on its own. Not a permanent
  leak, bounded, but worth a timeout on the `cv2.VideoCapture` open call
  itself if this needs tightening later.
- [ ] `SEC-4` API key stored in `localStorage` (`api.js:2-11`) —
  persistent and JS-readable; acceptable for a hackathon demo, revisit
  for real production (httpOnly cookie + CSRF protection).
- [x] `SWE-4` Zero automated tests anywhere in the backend. The three
  modules with the worst risk profile (`identity.py`, `tracker.py`,
  `geo.py`) have each had a real bug caught only by manual testing in
  this project's history — no regression net against reintroducing one.
  **Fix (2026-09-04):** `backend/tests/` — a pytest suite (32 tests, all
  green) covering exactly those failure modes: identity's geo-feasibility
  gate (geo-infeasible appearance match rejected into a new identity;
  geo-feasible linked; direct plate re-read continues regardless of
  feasibility — no gate on plate evidence; plate-upgrade retro-links an
  existing anonymous identity; 60-min association window; 0.80 similarity
  floor; missing-GPS doesn't over-reject), tracker's ByteTrack id-handoff
  fork (frame-1 IOU track is claimed, not duplicated) plus consensus-plate
  vote-share behavior, and geo's non-positive-elapsed-time guard +
  plausible/implausible/unknown segment classification. Self-contained
  (in-memory SQLite, no camera/ML deps); run from `backend/` with
  `python -m pytest tests -v` (see `backend/README.md`).

## Deferred — needs more than a quick fix

These need either real labeled data, a licensing/model decision, or
meaningful implementation time. Don't attempt under demo-video time
pressure — see `CODEX_HANDOFF_PROMPT.md` for a self-contained brief if
picked up later (by Codex, another session, or a teammate).

- `ML-3` `EMBEDDING_SIMILARITY_THRESHOLD = 0.80` (`identity.py`) has no
  empirical basis — gates a weak color-histogram signal with no measured
  false-positive rate. Needs ~20-30 labeled same/different-vehicle crop
  pairs from real sandbox footage and an actual ROC curve to justify a
  number.
- `ML-4` No held-out evaluation anywhere (only N=4 real frames + synthetic
  pass/fail checks). Needs a labeled real-footage sample (even 20-30
  frames) with reported precision/recall.
~~`ML-1-full-fix`~~ — **done 2026-09-05**, see Tier 1's `ML-1` entry above.

## 2026-09-26 security review — department-boundary bypasses

A fresh security pass found that department-level scoping could be crossed
through several side doors. Each of the five below was first reproduced
against the unfixed route code (in-memory DB, real route functions), then
fixed. Status: **AUTOMATED-TEST VERIFIED** — `tests/test_security_review_20260926.py`
(33 tests; 25 of them fail against the pre-fix route files, all pass after),
plus the updated `test_vehicle_crop_rbac.py`, `test_vehicle_search.py` and
`test_auth.py`. Not yet exercised against the live sandbox CDN.

- `SEC-26-1` DONE — `/live/{id}/seg?u=` checked only the host, and every
  sandbox camera shares one CDN host, so a viewer scoped to cam01 could
  pull another department's cam02 (or any CDN path) through our
  authenticated session. Now scheme + host + the camera's own directory
  prefix must match and dot-segments are refused (`routes_stream.py`).
- `SEC-26-2` DONE — cross-department results from `/vehicle/{plate}/history`
  and `/vehicle/search-by-attributes` now write an explicit
  `cross-department access:` audit row naming the other department(s).
  Attribute search with no filter (previously a 200-plate bulk dump) or a
  partial plate under 3 characters is refused with 400. A cross-department
  crop read now requires a stated purpose (8+ chars) instead of silently
  defaulting to `"unspecified"`.
- `SEC-26-3` DONE — a department-scoped investigator could acknowledge or
  dismiss (terminal) another department's alert. Now 404, same as the
  list view that already hid it (`routes_alerts.py`).
- `SEC-26-4` DONE — `POST /auth/api-keys` minted an unrestricted key when
  `department` was left blank. Viewer/investigator keys now require one;
  only admin may be unscoped. Viewers can no longer fetch evidence crops
  (investigator+). **Keys minted before this fix with no department keep
  their unrestricted scope** — audit `GET /auth/api-keys` and re-mint them.
- `SEC-26-5` DONE — `sentinel.db-wal` / `-shm` / `-journal` added to
  `.gitignore` (they hold uncheckpointed pilot rows).

Still open from the same review (not fixed): no API-key revocation/expiry;
watchlist writes have no attribution; the rate limiter can be bypassed by
rotating junk key headers; the write-time SHA-256 sits in the same mutable
row as the crop path (detects accidental alteration, not insider tampering
— there is no HMAC/signature/external anchor); production compose uses
host networking with the API on `0.0.0.0` over plain HTTP; the backend
container runs as root.
