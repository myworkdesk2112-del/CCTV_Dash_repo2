# Research Prompt — for ChatGPT / DeepSeek

Paste everything below into each tool. Ask both, compare answers, and use disagreements between them as a signal for where the real design tradeoffs are.

---

## Context

I'm competing in the **Gujarat Police Innovation Challenge 2026 ("Sentinel")** — a hackathon run by Gujarat Police (Home Department, Government of India) with a ₹51,00,000 prize pool. The goal is to design and build a real, production-deployable system, not just a demo. Submission deadline: 28 September 2026 (as of 2026-09-17; this is a historical research prompt and the date has moved twice since it was originally written — see `docs/hackathon/HACKATHON_DETAILS.md` for the current authoritative date).

## The problem we're solving

Gujarat's **26 government departments** each operate independent CCTV infrastructure — roughly **80,000 cameras** statewide, spanning:
- Mixed analog and IP-based cameras from many different vendors
- Incompatible VMS (Video Management System) platforms, no shared protocol
- Geographic dispersion of ~1,000 km across the state
- Storage retention limited to 7–15+ days, on a mix of cloud and local infrastructure
- No unified way to search, monitor, or cross-reference footage with law-enforcement databases

**The ask:** design a secure, scalable, interoperable, vendor-neutral platform that:
1. Integrates these heterogeneous CCTV systems into one platform (via a metadata registry + one or more of: direct unified viewing, VMS federation middleware, or a fully centralized VMS)
2. Cross-references live video feeds against government databases (vehicle registration, driver licensing, crime records, fingerprint/biometric databases) to auto-generate real-time alerts (e.g. stolen vehicle spotted, wanted person detected)
3. Supports AI video analytics: ANPR (automatic number plate recognition), face recognition, vehicle/crowd counting, anomaly detection, cross-camera vehicle tracking with full timestamped movement history
4. Scales toward the full ~80,000-camera target, not just the ~50-camera pilot used for evaluation
5. Must be built primarily on **open-source technologies**

**Live evaluation test case:** onboard ~50 heterogeneous camera feeds, track one designated vehicle by plate number across the network, produce a complete timestamped location-wise movement history, and demonstrate an automated alert firing when a plate matches a watchlist (stolen vehicles, wanted/missing persons, blacklisted vehicles).

## What we've already decided / built (for context, don't re-derive this)

We're building on **Model 1 (mandatory centralized CCTV registry + GIS mapping) + Model 2 (unified viewing via direct RTSP/ONVIF/API integration, no middleware)**. Current backend scaffold (Python/FastAPI): camera catalogue polling, a resilient per-camera RTSP consumer (forces TCP, drives all timing off PTS not wall-clock or reported FPS, exponential-backoff reconnect, tolerates scene-loop discontinuities), pluggable vehicle-detection and ANPR interfaces (currently stubbed, not yet wired to real models), SQLite/Postgres-backed vehicle-event log, and a watchlist/alerting service.

## What we need from you

### Step 1 — Research first, before proposing anything

Before suggesting any solution, do real research and report what you find:

1. **Search GitHub** for existing open-source projects that solve pieces of this problem: unified/federated VMS platforms, multi-camera vehicle re-identification and tracking, open-source ANPR (especially for Indian plate formats), CCTV camera registries with GIS mapping, video analytics pipelines built on RTSP/ONVIF at scale (hundreds–thousands of cameras). Name specific repos, their star count/activity level, and what specifically they get right or wrong for this use case.
2. **Research how real police forces and government bodies have solved this same problem** — e.g. UK's National Strategy for Police AI/ANPR network (Police National Computer + ANPR), Singapore's Police Cameras / Smart Nation surveillance network, China's Skynet/Sharp Eyes program, US city-level real-time crime centers (NYPD Domain Awareness System, Detroit Project Green Light, Chicago's OEMC), EU camera-network interoperability standards, India's own Safe City projects (e.g. Hyderabad, Delhi NETRA, existing state-level CCTV integration efforts in other Indian states). What architecture did each choose (centralized vs. federated), what AI analytics did they deploy, and what publicly known failures or criticisms did each face (accuracy, scaling, privacy/legal challenges, vendor lock-in)?
3. **Research relevant standards bodies and technical standards**: ONVIF (camera interoperability standard), OpenCV/GStreamer ecosystem conventions, NIEM or similar law-enforcement data-exchange standards, any Indian government standards for Safe City / CCTV integration (MeitY guidelines, BIS standards, Digital India / Smart City Mission specs), and India's data protection law (DPDP Act 2023) as it applies to biometric/surveillance data.
4. **Research open-source AI models** specifically relevant here: current best open-source ANPR models for Indian plates, open-source face recognition suitable for law enforcement use (accuracy, bias/fairness track record), multi-object tracking/re-identification models that work across non-overlapping camera views, and anomaly detection approaches used in production video analytics.

Cite what you find — real project names, real deployment names, real standards — not generic categories.

### Step 2 — Then propose solution directions

Based only on what the research in Step 1 actually surfaced, propose **2–4 distinct architectural directions** we could take (not just one "best" answer). For each direction, cover:
- Core architecture (what's centralized vs. federated vs. edge)
- Which specific open-source components/models it would reuse from your research, and why
- How it handles the ~80,000-camera scale target, not just the 50-camera pilot
- Tradeoffs: cost, implementation complexity/time given a ~1-week build window, interoperability with the 26 departments' existing heterogeneous VMS, and legal/privacy exposure under India's DPDP Act
- What would make this direction stand out to a jury versus what every other team is likely to submit (given the mandatory Model 1 + choice of Model 2/3/4)

### Step 3 — Flag disagreements explicitly

If your answer would differ from what a well-informed engineer might expect, say so and say why. We're specifically trying to surface non-obvious insights and prior art we haven't considered yet — don't just validate the direction we've already described above.

---

*Full challenge details are in `HACKATHON_DETAILS.md` in this project if you need to reference exact prize/phase/model specifics — otherwise the summary above is sufficient context.*
