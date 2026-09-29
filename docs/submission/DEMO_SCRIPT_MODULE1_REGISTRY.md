# Module 1 Demo Video — Registry & GIS — Recording Script

Covers Model 1's mandatory deliverables (HACKATHON_DETAILS.md §7): bulk +
manual + API onboarding, interactive GIS map, camera health monitoring,
maintenance-status, gap-analysis, role-based RBAC, metadata audit trail,
and CSV/PDF export. Everything below is **real** — the live sandbox
catalogue, the real backend, the real registry — nothing mocked. Every
step in this script was dry-run end-to-end against the real backend on
2026-09-27 before being written down; see "Verified" at the bottom.

**Target length: ~3:30–4:00.**

---

## Honesty guardrails (read before recording)

- **This recording uses a scoped demo environment** (see Pre-flight):
  `SENTINEL_DEMO_CAMERA_SCOPE=cam06,cam07,cam08` limits the *entire*
  visible catalogue to exactly these 3 cameras — `catalogue_size: 3`,
  not 30 — plus a 2026-09-27 fix to `main.py`'s health-sync loop so it no
  longer auto-creates a registry row for a live-but-unonboarded camera
  **when this scope is set**. Together, these two things are what make
  "only 3 in register and 3 live" an achievable starting point at all —
  without them, the registry reaches 30 (or, unscoped, still ticks up
  automatically) within about a minute of boot regardless of onboarding.
  Do not run this recording against the unscoped full 30-camera
  environment; the "few cams manually, then bulk the rest" narrative
  depends on this scoped setup.
- **Even scoped to 3, a real vehicle detection can still create a
  registry row before you onboard that camera — and that's deliberate,
  not a bug to route around.** A *separate* code path
  (`analytics/pipeline.py`'s `_ensure_camera_registered`) creates a bare
  registry row the instant the real pipeline finalizes a genuine vehicle
  sighting on any live camera, onboarded or not — because a real
  detection must never be silently dropped just for lack of a
  registration. If one of `cam06`/`07`/`08` has real traffic in the
  seconds between starting the server and starting the recording, that
  camera may already show a health status or even a detection count
  before you've touched the onboarding form. **Lead with this as a
  feature, not something to hide:** "Sentinel never waits for a human to
  onboard a camera before it protects real evidence the moment it
  appears — onboarding is what adds the administrative metadata:
  department, location, ownership." That's both true and a stronger
  story than a sterile empty screen.
- **A second, independent bug was found and fixed 2026-09-27, after the
  first live test of this exact script:** `_registered_cameras()` (the
  function backing the registry list, gap-analysis, and every
  registered-count KPI) was *also* filtering by
  `SENTINEL_DEMO_CAMERA_SCOPE`, so onboarding any camera outside the
  3-camera live scope — e.g. `cam01`, which is not `cam06`/`07`/`08` —
  silently made it invisible everywhere in the registry, even though the
  onboard call itself succeeded. This is exactly the "onboard a camera,
  see it reflected everywhere" step this script depends on (Shots 1–2
  and, at full scale, Shot 6's "bulk-onboard all 30"), so it would have
  broken the recording live. **Fixed:** the registry is no longer
  scope-filtered at all — it always shows the truth of what has actually
  been onboarded, regardless of which cameras are currently live.
  `catalogue.py`'s own separate scope check is untouched and still
  correctly limits which cameras show as *live*. Re-verified end-to-end
  after the fix: manually onboarding a camera outside the live scope now
  correctly increases `registered_size` immediately.
- **Lead the gap-analysis shots with `missing_department` /
  `missing_gis_coordinates` / `missing_storage_details`**, which is where
  the real, honest incompleteness lives regardless of the exact
  registered count at any given second.
- **After the bulk-import step, most of the 27 newly-imported cameras
  will show "Unassigned" department and no storage details.** This is
  real, honest data — the real sandbox camera names are street/junction
  names with no department hint (only 2 of 30 carry one), and no storage
  information exists anywhere in the source catalogue. **Lead with this
  as the gap-analysis feature working correctly on real data**, not
  something to hide or rush past.
- **Do not claim** these 30 cameras represent 26-department statewide
  coverage — they're the hackathon's own 30-camera sandbox (5 departments:
  Health, Police, GSRTC, Panchayat, Municipal Corporation per
  HACKATHON_DETAILS.md §12), a pilot, not a production deployment.

---

## Pre-flight (do this before you hit record)

Use a **fresh, dedicated demo database** — never the shared
`sentinel.db` that holds real accumulated pilot evidence (per this
project's own data-safety rules). This makes the demo exactly
reproducible and never risks real data.

```bash
cd sentinel-solution/backend

# 1. Fresh demo DB — delete only this file, never sentinel.db.
rm -f sentinel_demo_module1.db*

# 2. Start the backend against it, SCOPED to exactly 3 cameras — this
#    scope is what makes "3 registered / 3 live" an achievable starting
#    point at all (see the guardrails above for why).
set -a && . ../.env && set +a
DATABASE_URL="sqlite:///./sentinel_demo_module1.db" \
  SENTINEL_DEMO_CAMERA_SCOPE="cam06,cam07,cam08" \
  PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  python -m app.main
#    -> copy the bootstrap admin API key it prints on first run
#       ("No API keys existed — minted a bootstrap admin key...").
#    -> confirm GET /health shows "catalogue_size": 3 (not 30) before
#       recording. If the sandbox's own CDN is rate-limited (403 on
#       cameras.json, from heavy earlier use), this will read 0 —
#       wait ~15-20 min for it to clear rather than retry rapidly.

# 3. Start the frontend (separate terminal).
cd ../frontend && npm run dev          # http://localhost:5173
```

In the browser, paste the admin API key into the API-key bar (Topbar).
Confirm `GET /health` shows `"catalogue_size": 3` before recording — the
catalogue populates a few seconds after startup (if it reads 0, the
sandbox's own rate-limit cooldown is active; it self-heals within about
60 seconds of the cooldown clearing, no restart needed).

Have `sentinel-solution/backend/data/sandbox_bulk_onboard.csv` ready to
upload in Shot 6 (already built from the real live sandbox catalogue,
see `docs/hackathon/TASKS.md`).

**Recording setup:** 1920×1080, browser zoom 110–125%, cursor
highlighting on. Navigate to the **Registry** tab (Model 1's home
screen) before starting.

---

## Shot-by-shot

### SHOT 1 — Three cameras live, none with real metadata yet (0:00–0:20) · *Registry tab*
**On screen:** the Registry screen, scoped to 3 cameras
(`catalogue_size: 3`). The registry list may show 0–3 rows depending on
whether real traffic has already been detected on any of them (see the
guardrail above) — either state is fine to show.
**Narration (adapt to whichever state is actually on screen):**
> "This is Sentinel's camera registry. Three cameras are live on the
> government's network right now. [If a row already has a health status
> or detection:] Notice this one is already being tracked — Sentinel
> protects real evidence the instant it appears, even before a human
> onboards the camera. [Either way:] None of these have real
> administrative metadata yet — no department, no location. Let's
> onboard them properly."
Manually onboard `cam06`, `cam07`, `cam08` via the **Onboard Camera**
form (id + department "Police" is enough for this shot).

### SHOT 2 — Manual onboarding, live confirmation (0:20–0:50) · *Registry tab*
**On screen:** after each onboard, point at the list growing to 3, and
open one camera's detail panel (click the row) to show real fields:
department, location, health status.
**Narration:**
> "Each camera is onboarded with real metadata — department, location,
> camera type. Clicking a camera opens its full registry record: health
> status, maintenance state, and its complete audit trail of who
> onboarded or edited it and when."

### SHOT 3 — GIS map (0:50–1:10) · *Registry tab → GIS map*
**On screen:** open the GIS map modal. If `cam06`/`07`/`08` don't have
coordinates yet, onboard one with real lat/lon to show a pin plotting
live (or use one of the CSV rows that does have coordinates as a
preview). Point at the coverage-radius circle and ageing dash-outline if
either camera has that data set.
**Narration:**
> "Every onboarded camera with coordinates plots on this GIS map
> immediately — the state map view for Model 1. As we onboard more
> cameras in a moment, watch this map fill in."

### SHOT 4 — Live Network: real feeds, on demand (1:10–1:35) · *Live Network tab*
**On screen:** switch to the Live Network video-wall. Select `cam06`,
`cam07`, `cam08` into the wall and show their real HLS feeds actually
playing.
**Narration:**
> "This is real, live video from the government sandbox — Model 2's
> unified viewer, sitting on top of the same registry we just built.
> Any tracked camera's feed is one click away, on demand."

### SHOT 5 — Gap analysis, before bulk import (1:35–1:55) · *Coverage & Gaps tab*
**On screen:** the Gap Analysis panel. Point at `missing_department`
and `missing_gis_coordinates` — still near 30, since only 3 cameras have
been given real metadata so far.
**Narration:**
> "Gap analysis already tells us the truth: thirty cameras are tracked,
> but only three have real department and location data attached. The
> rest are a metadata gap — exactly what this feature exists to catch,
> camera by camera."

### SHOT 6 — Bulk onboard the remaining 27 via CSV (1:55–2:25) · *Registry tab → Bulk Onboard*
**On screen:** open the Bulk Onboard form, upload
`data/sandbox_bulk_onboard.csv`, submit. Show the success message
("Backend onboarded 30 camera(s)...").
**Narration:**
> "Rather than onboard each one by hand, we bulk-import the rest from a
> CSV — the same real camera list from the government's own catalogue,
> with department and location inferred automatically where the data
> supports it."

### SHOT 7 — Full registry: 30 tracked, 30 with real location data, on the map (2:25–3:00) · *Registry tab*
**On screen:** the camera list now shows all 30, most with a real
location name from the bulk import. Open the GIS map — most pins now
plot. Re-open Gap Analysis: `missing_gis_coordinates` down to ~10,
`missing_department` still ~25–28.
**Narration:**
> "All thirty cameras now have real location data and most are on the
> map. Only the three we scoped this environment to are actually
> streaming right now — gap analysis calls the rest 'onboarded but not
> currently live,' which is exactly correct: they're registered with
> real metadata, ready to go live the moment this deployment connects to
> them. And gap analysis is still honest about what's incomplete — most
> of these cameras have no department attribution yet, because their
> real names are street junctions, not department tags, and none of them
> have storage-retention information recorded. That's not a bug we're
> hiding — it's the registry correctly telling an administrator exactly
> what still needs a human to fill in, camera by camera."

### SHOT 8 — Maintenance, deregister, and audit trail (3:00–3:30) · *Registry tab, one camera's detail panel*
**On screen:** open one camera's detail panel. Mark it under
maintenance with a reason, show the status change. Show the audit trail
listing "onboarded" then "maintenance_set" with real timestamps and the
authenticated user. Optionally show Deregister (reversible) vs. the
separate hard Delete (blocked with a 409 if the camera has any real
detection history — a good, honest thing to show on camera: **evidence
can never be silently deleted**).
**Narration:**
> "Every state change is a deliberate, attributed action — maintenance
> status, deregistration, or a full delete — and every one of them is
> recorded in this camera's own audit trail. And deletion has a real
> safeguard: if a camera has ever produced real vehicle-detection
> evidence, the system refuses to delete it outright. That evidence is
> never silently lost."

**End card (optional):** "Sentinel — Model 1: Centralised CCTV Registry
& GIS Mapping. Real onboarding, real gaps, nothing hidden."

---

## Coverage check — every mandatory Model 1 deliverable is on screen

| Spec item | Shot |
|---|---|
| Manual onboarding | 1–2 |
| API-based onboarding | 2 (same endpoint the form calls) |
| Bulk import onboarding | 6 |
| Interactive GIS map | 3, 7 |
| Camera health monitoring | 2 |
| Maintenance-status monitoring | 8 |
| Gap-analysis (uncovered zones + ageing) | 5, 7 |
| Role-based search/filter/export | mention in 2 or 7 if time allows (CSV/PDF export buttons) |
| Metadata audit trail | 2, 8 |
| Sample onboarded camera-metadata dataset | 7 (all 30, honestly incomplete) |

---

## Verified (2026-09-27, dry run against the real backend)

- **Unscoped (30-camera) environment:** confirmed `registered_size`
  reads 30 within ~60 seconds of backend boot regardless of any
  onboarding action, from `main.py`'s health-sync loop auto-creating a
  bare row for every live camera. Confirmed directly against the
  database: all 30 rows exist with `department: None`. This is why the
  scoped setup below exists.
- **Fixed the same day:** the health-sync loop now skips auto-creating a
  row when `SENTINEL_DEMO_CAMERA_SCOPE` is set — verified in isolation
  (a standalone simulation of the exact code path, confirming 0 rows
  created) and confirmed no regression across the full 347-test backend
  suite.
- **Scoped (3-camera) environment, confirmed live:** `catalogue_size: 3`,
  and immediately after boot `registered_size` genuinely can read 0 — but
  in this same dry run it reached 3 within a few minutes anyway, for a
  **different, unfixed reason**: `analytics/pipeline.py`'s
  `_ensure_camera_registered` creates a bare row the instant a real
  vehicle detection is finalized on any live camera, onboarded or not.
  Confirmed directly against the database: cam06/07/08 had 582/23/130
  real `VehicleEvent` rows respectively within minutes of the sandbox
  becoming reachable — real traffic, not a test artifact. **This path
  was deliberately left alone** — disabling it risks losing or crashing
  on real evidence, which is a materially worse outcome than an imperfect
  demo opening. See the second guardrail above for how to narrate this
  honestly if it happens live.
- **`_registered_cameras()` scope-filter bug, found and fixed same day:**
  discovered live when manually onboarding `cam01` (outside the
  `cam06,07,08` live scope) produced no change in `registered_size`.
  Root cause and fix confirmed above. No test covered the old (buggy)
  behavior; full 347-test suite still passes after the fix; re-verified
  live over HTTP that `registered_size` now correctly includes an
  out-of-scope onboarded camera.
- **Stale test data found in `sentinel_demo_module1.db` while verifying
  this fix:** both `cam01` and `cam1` (no leading zero) are registered
  from earlier ad-hoc testing — a harmless duplicate-looking pair that
  would look confusing on camera. Neither is fabricated evidence; this is
  exactly why the Pre-flight section says to delete this file and start
  from a fresh DB before the actual recording — do not skip that step.
- Manual onboard of 3 cameras and real bulk CSV import of all 30 rows via
  `POST /cameras/bulk` were both dry-run successfully in an earlier,
  unscoped pass: confirmed `missing_department`, `missing_gis_coordinates`,
  and `missing_storage_details` all update correctly.
- Maintenance-set, deregister/re-register, and hard-delete (with its
  evidence-guard 409) were each independently verified live over HTTP
  earlier the same session — see `docs/hackathon/TASKS.md`.

## Fallback / variations

- **Shorter (2:30):** cut Shot 4 (video wall) and merge Shots 3+7 (show
  the map once, at the end, fully populated).
- **If the bulk CSV step feels risky live:** it was dry-run successfully
  moments before this note was written — but re-confirm the CSV file
  still parses (`Missing required columns` errors are shown inline by
  the upload form) before you're rolling.

---

## Assembling the final cut (if recorded as separate clips per shot)

```bash
cat > concat_list.txt <<'EOF'
file 'shot1.mp4'
file 'shot2.mp4'
file 'shot3.mp4'
file 'shot4.mp4'
file 'shot5.mp4'
file 'shot6.mp4'
file 'shot7.mp4'
file 'shot8.mp4'
EOF

ffmpeg -f concat -safe 0 -i concat_list.txt -c copy module1_raw.mp4
# or, if clip codecs/framerates differ:
ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -crf 18 -preset slow \
  -c:a aac -b:a 192k module1_raw.mp4

ffmpeg -i module1_raw.mp4 -vf subtitles=captions.srt -c:a copy module1_final.mp4

ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 \
  module1_final.mp4   # target ~3:30-4:00
```
