# Own-Feed Demo Video — Recording Script

Satisfies **Submission Requirement #3** ("Demonstration on Participant's Own
Feed", max 2–3 min). The rules require a **fully functional working
solution** — "Mock-ups, animations, simulated interfaces, or concept videos
without an operational backend will not be considered." This script is built
so every second shows the **real backend** (real YOLOv8 + PaddleOCR +
identity resolution + watchlist + alerts), not a mockup.

**Target length: ~2:45.** Everything below is verified working (see
`scripts/demo_end_to_end.py`, run end-to-end 2026-09-03).

---

## Honesty guardrails (read before recording)

- **Input is our own controlled footage; processing is 100% real.** The
  scenario composites a known plate onto a real vehicle image so the *same
  designated vehicle* deterministically appears at 5 cameras (a guarantee
  random road footage can't give you). Say this plainly if narrating —
  "own footage of our choice," which the rules explicitly permit. The
  detection, OCR, tracking, identity resolution, and alerting are the real
  pipeline, which is what the "no mockups" rule actually cares about.
- **Do NOT claim** live sandbox/RTSP, verified real-Indian-plate accuracy,
  or facial recognition. None are in this demo.
- **Do** emphasise the honest beats — anonymous sightings still tracked,
  INFERRED (not "tracked") route gaps, false-positive dismissal — they are
  strengths with a police jury, not weaknesses.

---

## Pre-flight (do this before you hit record)

From `sentinel-solution/backend`, in the `.venv` with `requirements-ml.txt` installed:

```bash
# 1. Populate the app's real DB with the verified scenario (runs the REAL
#    pipeline; leaves data in sentinel.db; sets realistic timestamps).
SENTINEL_DEMO_PERSIST=1 python scripts/demo_end_to_end.py
#    -> copy the bootstrap admin API key it/main.py logs, OR mint one later.

# 2. Start the backend (note the bootstrap admin key printed on first run).
python -m app.main                     # http://localhost:8000

# 3. Start the frontend (separate terminal).
cd ../frontend && npm run dev          # http://localhost:5173
```

In the browser, paste the admin API key into the API-key bar (top). Have the
designated plate ready: **`GJ01AB1234`** (watchlisted as "stolen").

**Recording setup:** 1920×1080, hide bookmarks/personal tabs, browser zoom
110–125% for legibility, cursor highlighting on if your tool has it. A calm
voiceover (or on-screen captions) tracking the script below.

---

## Shot-by-shot

### SHOT 1 — "It's real" proof (0:00–0:30)  · *terminal*
**On screen:** the terminal, mid-run of `demo_end_to_end.py`, showing
`Loading real models (YOLOv8 + PaddleOCR)...`, the 5-camera simulation lines,
then the green `PASS` verification block ending in
`ALL EVALUATION OUTPUTS VERIFIED`.
**Narration:**
> "This is Sentinel, running its real analytics pipeline — YOLOv8 detection
> and PaddleOCR number-plate recognition, not a mockup. Here it processes a
> stolen vehicle, GJ01AB1234, across five cameras from five different
> government departments, and self-verifies the evaluation outputs."

### SHOT 2 — Model 1: registry + GIS (0:30–0:55) · *browser, Map/Registry tab*
**On screen:** the Leaflet map with the 5 onboarded cameras across
Ahmedabad → Gandhinagar → Kalol, colour-coded by health; the camera list
showing department tags (Police, Municipal, GSRTC, Health, Panchayat).
**Narration:**
> "The foundation is a unified camera registry and GIS map — the mandatory
> Model 1. Cameras from five departments, onboarded with location, ownership
> and live health status, on one map. This is the common inventory every
> other capability sits on."

### SHOT 3 — The core test case: trace by plate (0:55–1:35) · *Vehicle Tracking tab*
**On screen:** type `GJ01AB1234`, purpose `stolen_vehicle_investigation`,
case ID `DEMO-01`; hit Search. The movement timeline renders 5 sightings.
Point the cursor at the **anonymous** badges vs the **plate read** badge.
**Narration:**
> "Given only the registration number, Sentinel returns the complete
> timestamped, location-wise movement history across the network. Notice the
> plate was only cleanly readable at ONE camera — the GSRTC depot. At the
> other four the plate was unreadable, yet the vehicle is still on the
> timeline, matched by appearance. That's the core design principle:
> **a failed plate read never means a lost vehicle.**"

### SHOT 4 — Geo-temporal route reconstruction (1:35–2:00) · *same timeline*
**On screen:** point at the dashed **INFERRED** connectors between sightings,
each showing distance / time / plausible speed.
**Narration:**
> "Between confirmed sightings, Sentinel reconstructs the route — but it's
> explicit about evidence. Solid markers are confirmed camera sightings.
> Dashed segments are **inferred** movement across camera blind-spots,
> labelled with distance and a plausibility check — never presented as
> something we actually saw. If a jump were too fast to be a real drive, the
> system flags it as 'not a direct drive'. For a policing tool, that honesty
> is the point."

### SHOT 5 — Explainability: "why was this linked?" (2:00–2:20) · *click a sighting*
**On screen:** the Explainability panel for an appearance-matched sighting —
link method, Re-ID similarity, temporal consistency, fused score.
**Narration:**
> "Every cross-camera link is auditable. For any sighting, Sentinel shows
> *why* it was linked — plate confidence, appearance similarity, and time
> consistency, fused into a transparency score. An investigator sees the
> reasoning, not a black box."

### SHOT 6 — Watchlist alert + governed lifecycle (2:20–2:45) · *Watchlist tab*
**On screen:** the Alerts panel with the `GJ01AB1234 · stolen` alert (status
**new**, red). Click **Acknowledge** (turns amber), then **Resolve** (green)
— or **Dismiss (false +ve)** to show that path.
**Narration:**
> "The moment a watchlisted plate is seen, Sentinel raises a real-time alert.
> But it's a governed investigation item, not a toast that vanishes — an
> officer acknowledges, then resolves it, or dismisses it as a false
> positive. Every step is recorded against the authenticated user. That's
> AI as a decision-support tool with a human always in the loop."
**End card (optional):** "Sentinel — Model 1 + 2 hybrid · open, explainable,
scalable to 80,000 cameras."

---

## Coverage check — every mandatory beat is on screen

| Rule #3 requirement | Shot |
|---|---|
| Onboarding & processing of feeds | 1 (processing) + 2 (onboarding/registry) |
| AI detection & analytics (ANPR) | 1 + 3 (plate read + attributes) |
| Correlation with a watchlist DB | 6 |
| Automatic real-time alert + visualisation | 6 |
| **Fully functional backend (no mockup)** | 1 (live pipeline run) — the whole point of leading with it |

**Bonus beats also shown:** cross-camera correlation (3), advanced route
reconstruction (4), explainability/auditability (5), governed alert
lifecycle + false-positive handling (6).

---

## Fallback / variations

- **Shorter (2:00):** merge Shots 4+5, trim Shot 1 to ~15s.
- **If you have real road footage** where you can guarantee one vehicle
  across ≥2 cameras: you can feed it instead of the composited scenario, but
  keep the controlled scenario as the reliable take — random footage rarely
  gives a clean cross-camera reappearance in a 3-minute cut.
- **Government-feed video (Submission #4)** is a *separate* recording,
  see `DEMO_SCRIPT_GOVERNMENT_FEED.md` — no longer externally blocked
  (re-verified live 2026-09-26), it just hasn't been recorded yet.

---

## Assembling the final cut (if recorded as separate clips per shot)

If each shot above was captured as its own file (`shot1.mp4`,
`shot2.mp4`, ...), concatenate losslessly with ffmpeg, then caption:

```bash
cat > concat_list.txt <<'EOF'
file 'shot1.mp4'
file 'shot2.mp4'
file 'shot3.mp4'
file 'shot4.mp4'
file 'shot5.mp4'
file 'shot6.mp4'
EOF

# Fast path — only if all clips share codec/resolution/framerate:
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy own_feed_raw.mp4

# Re-encode path — use if clips differ (e.g. mixed recorder output):
ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -crf 18 -preset slow \
  -c:a aac -b:a 192k own_feed_raw.mp4

# Optional caption burn-in from an .srt built from the Narration lines above:
ffmpeg -i own_feed_raw.mp4 -vf subtitles=captions.srt -c:a copy own_feed_final.mp4

# Confirm it lands in the ~2:45 target before submitting:
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 \
  own_feed_final.mp4
```
