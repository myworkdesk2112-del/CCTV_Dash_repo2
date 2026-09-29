# Government-Feed Demo Video — Recording Script

Satisfies **Submission Requirement #4 / Q31 / Q33** — "government-feed
demonstration with output report" (screen-recorded video **plus** an
output report showing detected vehicles/plates with timestamps). Mock-ups
are explicitly disallowed (Q32) — everything below must be the real
backend against the real sandbox, not a re-run of the own-feed
composited scenario.

**Target length: 2–3 min**, per Q31. This is a *separate* recording from
`DEMO_SCRIPT_OWN_FEED.md` — do not reuse that footage here.

---

## Honesty guardrails (read before recording)

- **This is the government feed** — per `HACKATHON_DETAILS.md` §12, the
  hackathon's own sandbox ("~12 hours of CCTV footage from 30+ cameras
  across 5 departments... real footage, no synthetic data... served as
  simulated live video") IS the Phase 1 government-provided feed. Don't
  frame this as "waiting on organizer access" — that framing was
  retracted 2026-09-12 (`TASKS.md`) after being independently verified as
  stale. Say plainly on camera: "this is the organizer-provided sandbox
  feed," not "our own footage."
- **Do NOT lead with `GJ01RP6128` — use `GJ19BR3000` instead (updated
  2026-09-26).** The `GJ01RP6128` capture is three weeks old and did not
  reproduce across 5 fresh real scans that day. A 6th scan then produced
  a new real, visually-confirmed read: **`cam06`, `GJ19BR3000`, 6/6
  consecutive samples, confidence 0.917–0.977** — see `HLD.md` §3's
  2026-09-26 correction and `REQUIREMENTS_COVERAGE.md`'s "ANPR-based
  metadata generation" row for the full sequence. Before scripting this
  shot: run `scripts/real_anpr_scan.py` again close to record time to
  confirm `GJ19BR3000` (or any fresh real read) is still catchable —
  the sandbox's looped recording means traffic timing shifts. If nothing
  turns up on the day, fall back to the honest framing below rather than
  asserting a read that wasn't actually captured in that session.
  The consensus-vote code itself is still validly tested
  (`test_consensus_plate_real_cam06_vehicle_clears_confidence_gate`) — that
  locks in "given these votes, the logic is correct," not "this read
  happens live and now."
- **Do NOT claim**: a specific aggregate ANPR accuracy percentage unless
  you re-state the exact measurement basis from `HLD.md` §3 (dataset,
  camera count, method) in the same breath — a bare "X% accurate" claim
  without that context is a forbidden claim per this repo's `CLAUDE.md`
  §8. Do not claim face recognition or any biometric capability — not
  built, not in scope.
- **The output report is mandatory, not optional** — Q33 requires it
  explicitly. Generate and show it on screen (Shot 5 below); don't just
  narrate that reports exist.

---

## Pre-flight (do this before you hit record)

From `sentinel-solution/backend`, real `.venv` with `requirements-ml.txt`
installed (paddleocr confirmed installed on this machine as of
2026-09-13 — verify again on whichever machine actually records):

```bash
# 0. Re-confirm the headline plate is still catchable before touching
#    anything else — sandbox traffic varies by which part of the looped
#    recording you land on (per TASKS.md, re-run this close to record
#    time, not just once days earlier).
python scripts/real_anpr_scan.py --camera cam06 --duration 40
#    -> look for GJ19BR3000 (or any fresh pattern-valid read) in the
#       output before proceeding. If nothing turns up, plan to use the
#       Shot 3 fallback narration and don't force a claim.

# 1. Start the backend against the REAL sandbox (needs real sandbox
#    credentials set — SENTINEL_ACCESS_EMAIL / SENTINEL_ACCESS_TOKEN),
#    with the second, independent unified-viewer source enabled so the
#    Model 2 "≥2 different systems" requirement is visible on screen.
SENTINEL_EXTERNAL_CAMERA_SOURCE_ENABLED=true python -m app.main   # http://localhost:8000
#    -> note the bootstrap admin API key printed on first run.

# 2. Start the frontend (separate terminal).
cd ../frontend && npm run dev          # http://localhost:5173
```

In the browser, paste the admin API key into the API-key bar. Confirm
live sandbox connectivity first (don't discover a dead session on
camera): open the Live Map / camera grid and check `cam06` shows
`is_healthy` and plays, and that the Caltrans D3 external tiles
(`ext-caltrans-*`, labelled "EXTERNAL SOURCE — periodic snapshot, not
live video") appear in the same grid.

**Recording setup:** 1920×1080, hide bookmarks/personal tabs, browser
zoom 110–125%, cursor highlighting on. Calm voiceover or on-screen
captions following the script below.

---

## Shot-by-shot

### SHOT 1 — Frame the feed honestly (0:00–0:20) · *browser, camera list/registry*

**On screen:** the camera registry showing all 30 onboarded sandbox
cameras, department tags visible (Police, Municipal Corporation, GSRTC,
Health, Panchayat).

**Narration:**
> "This is Sentinel connected to the hackathon's own government-provided
> CCTV sandbox — real footage from 30-plus cameras across five Gujarat
> departments, not our own recorded footage. Everything from here is the
> live backend against this real feed."

### SHOT 2 — Live connection proof + unified two-system viewer (0:20–0:55) · *Live Network / camera grid*

**On screen:** `cam06`'s live HLS tile actually playing (real motion),
health status visible as connected/healthy, **in the same grid as** at
least one Caltrans District 3 tile (`ext-caltrans-*`), showing its
"EXTERNAL SOURCE — periodic snapshot, not live video" badge clearly.

**Narration:**
> "Here's camera 6, streaming live from the sandbox over RTSP, proxied
> through our authenticated HLS pipeline — real video, playing right
> now, not a recording of a recording. And in the same unified viewer,
> alongside it: a live camera feed from a second, completely
> independent, real government system — Caltrans District 3's own
> public traffic-camera network in California. We're not replacing
> either department's system — we're viewing both through one screen.
> This tile is honestly labelled as a periodic snapshot, not continuous
> video, because that's what its source actually provides — we don't
> overclaim what an external system gives us."

### SHOT 3 — Real ANPR on this feed (0:55–1:35) · *ANPR/vehicle detail for cam06, or terminal tailing detection logs*

**On screen:** either (a) the camera detail / last-detection panel for
`cam06` showing a real accepted plate read, or (b) a terminal tailing
`sentinel.db` inserts / backend logs as a real detection lands, timestamp
visible.

**Narration — use only if a fresh real read is confirmed at record time
(current candidate: `GJ19BR3000`, `cam06`, 6/6 samples at 0.917–0.977
confidence, captured 2026-09-26 — re-confirm it's still catchable before
recording; otherwise use the fallback line below):**
> "This vehicle's plate, GJ19BR3000, was read correctly on six of six
> passes and accepted by our temporal consensus-vote logic at 0.98
> confidence — the real YOLOv8-plus-PaddleOCR pipeline running against
> this exact camera, not a staged frame."

**Fallback narration — use this if no fresh real plate read is confirmed
by record time:**
> "You're watching the real detection and localization pipeline running
> against live sandbox footage — vehicle detection and plate-region
> localization boxes are drawn in real time on real video. A confident
> plate read depends on a vehicle passing close enough and clearly enough
> in front of the camera during the recording window; we haven't shown a
> read we can't stand behind, so we're not claiming one here."

### SHOT 4 — Searchable movement + watchlist correlation (1:35–2:10) · *Vehicle Tracking tab*

**On screen:** search `GJ19BR3000` if it's still confirmed catchable at
record time (see SHOT 3), otherwise search whichever plate has real,
freshly-confirmed sandbox sightings that day (check beforehand — do not
assume `GJ01RP6128` still has any) — pick whichever plate has the
strongest real timeline, or fall back to demonstrating the search UI
against `/vehicle/recent`'s live feed if no plate read is available yet.
Purpose + case ID filled in. Timeline renders with real timestamps and
camera IDs.

**Narration:**
> "Given only the registration number, Sentinel returns the real,
> timestamped, camera-by-camera movement history from this live feed —
> and automatically checks it against the watchlist."

*(If this plate isn't watchlisted, say so plainly — "not currently
watchlisted" — rather than implying an alert that didn't fire.)*

### SHOT 5 — The mandatory output report (2:10–2:40) · *Reports tab*

**On screen:** open the Reports view, generate the **"Vehicle detections
report"** (reuses `GET /vehicle/recent` — camera, plate, timestamp,
evidence class per row), show the downloaded file open with real rows
visible — timestamps and camera IDs legible on screen.

**Narration:**
> "Per the submission requirement, here is the actual output report —
> every detected vehicle, its plate, the camera, and the timestamp,
> exported directly from the running system, not compiled by hand."

### SHOT 6 — Close (2:40–2:55, optional)

**On screen:** brief cut back to the camera registry or map.

**Narration:**
> "This is the same backend, the same registry, the same evidence rules
> shown in our own-feed demo — running end to end against the
> organizers' real sandbox feed."

---

## Extended cut (optional, ~3:30–4:00) — two more real bonus beats

The strict 2–3 min cut above (Shots 1–6) already covers every mandatory
Q31/Q33 beat. If a slightly longer cut is acceptable, insert these two
shots after Shot 5 (before the Shot 6 close) — both are real, wired,
built features (2026-09-19), not aspirational:

### SHOT 5a — ANPR Readiness (bonus, ~30s) · *ANPR Readiness tab*

**On screen:** the ANPR Readiness screen, showing per-camera verdicts
(CAPABLE / MARGINAL / UNSUITABLE / INCONCLUSIVE) beside stream health —
point at `cam06` (CAPABLE, with a real read-rate reason) next to a
camera that streams fine but has never produced a read.

**Narration:**
> "Streaming health and ANPR fitness are different questions — a camera
> can be perfectly healthy and still never produce a usable plate read.
> This screen tells an operator, camera by camera, which cameras can
> actually support number-plate recognition, why, and what to fix if
> not — re-angle, zoom, or reposition."

### SHOT 5b — Evidence integrity export, both gates shown (bonus, ~35s) · *Evidence Export tab*

**On screen:** pick one LEAD ONLY sighting and attempt export — show the
control disabled / the server's 409 response explaining why. Then pick
the CONFIRMED `GJ19BR3000` sighting, fill in a purpose (8+ characters)
and case ID, export, and show the real certificate PDF opening with a
SHA-256 hash and production-method stamp visible.

**Narration:**
> "Evidence export is gated by evidence tier, not by convenience — a
> lead based only on appearance can never be exported as confirmed
> evidence, the system refuses it outright. A confirmed plate read can
> be exported as a §63-oriented evidence package — hashed at the moment
> it was written, stamped with exactly which model produced it, and
> logged to an audit trail before the file is even generated."

---

## Coverage check — every mandatory beat is on screen

| Q31/Q33 requirement | Shot |
|---|---|
| Government-feed demonstration (real feed, not own footage) | 1, 2 |
| Unified viewer, ≥2 independent systems (Model 2 bonus) | 2 |
| AI detection & analytics (ANPR) on that feed | 3 |
| Searchable movement / watchlist correlation | 4 |
| **Output report — detected vehicles/plates with timestamps** | 5 |
| Camera ANPR-fitness (bonus) | 5a (extended cut only) |
| Evidence-tier export enforcement (bonus) | 5b (extended cut only) |
| Fully functional backend (no mockup) | Implicit throughout — live tiles, live search, live report generation |

---

## Known gaps to disclose if asked, not to hide

- GIS coordinates: 22 of 30 sandbox cameras have coordinates (from our
  registry, not the sandbox catalogue, which supplies none) — 8 don't.
  Don't claim full statewide GIS coverage from this sandbox alone.
- The fresh live-detection moment (Shot 3) depends on the ML runtime
  actually producing a new event during the recording window — rehearse
  this beat once beforehand so you know it fires, rather than hoping live
  on the actual take. If it doesn't fire in time, fall back to showing
  the historic real scan result (`data/anpr_scan/20260905T112430Z`) and
  say plainly it's a prior real run, not this session's.
- Don't claim a specific statewide accuracy number — this sandbox is 30
  cameras, not 80,000; keep scalability claims in the HLD/scalability
  doc, not this video.

---

## Assembling the final cut (if recorded as separate clips per shot)

If each shot above was captured as its own file (`shot1.mp4`,
`shot2.mp4`, ...), concatenate losslessly with ffmpeg rather than
re-encoding, then add captions/voiceover as a final pass:

```bash
# 1. List the clips in order, one per line, matching the shot sequence
#    used for this cut (strict 2-3 min: shots 1-6; extended cut:
#    1,2,3,4,5,5a,5b,6).
cat > concat_list.txt <<'EOF'
file 'shot1.mp4'
file 'shot2.mp4'
file 'shot3.mp4'
file 'shot4.mp4'
file 'shot5.mp4'
file 'shot6.mp4'
EOF

# 2. Concatenate without re-encoding (fast, no quality loss) — only
#    works if all clips share the same codec/resolution/framerate.
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy government_feed_raw.mp4

# 3. If clips differ in codec/framerate (e.g. mixed screen-recorder
#    output), re-encode instead:
ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -crf 18 -preset slow \
  -c:a aac -b:a 192k government_feed_raw.mp4

# 4. Burn in captions from an .srt file (optional, if not narrating live):
ffmpeg -i government_feed_raw.mp4 -vf subtitles=captions.srt \
  -c:a copy government_feed_final.mp4

# 5. Sanity-check duration matches the target before submitting.
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 \
  government_feed_final.mp4
```
