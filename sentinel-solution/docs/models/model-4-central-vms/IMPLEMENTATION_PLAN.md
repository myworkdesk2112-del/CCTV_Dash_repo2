# Model 4 — Implementation Plan

**This is a roadmap, not a build plan.** Unlike Model 1/2/3's
implementation plans in this folder tree, nothing below has an effort
estimate meant to be started this hackathon — Model 4 is out of scope
per `docs/strategy/STRATEGY.md`'s OUT list (full 80,000-camera ingestion
explicitly named). This document's purpose is to show the jury a credible
"what happens after the pilot succeeds" story, and to make explicit which
Model 4 items are pure scale-up of already-working code versus items that
need a policy/legal decision before any code is written.

## Phase inheritance from `SCALABILITY.md` §6

Model 4 doesn't define its own rollout — it **is** the terminal phase of
the rollout `SCALABILITY.md` already specifies:

1. Pilot (~30 cameras, SQLite, single-node) — **this submission, done.**
2. District pilot (PostgreSQL, one edge GPU unit) — next phase, not
   started.
3. Regional rollout (multiple districts, Kafka introduced) — not
   started.
4. **Statewide (~80,000 cameras, all 26 departments) — this is Model 4.**
   Not started, not scheduled, no date attached.

## What's pure scale-up (no new engineering decision needed)

These already work at pilot scale (Model 1/2) and need infrastructure
investment, not new capability design, to reach statewide scale:

- ANPR, cross-camera vehicle tracking, watchlist alerting, GIS
  visualization, gap-analysis reporting.
- Anomaly detection (wrong-way, restricted-zone) — same caveat as at
  pilot scale: uncalibrated image-plane units unless per-camera
  homography calibration (Model 2's `IMPLEMENTATION_PLAN.md` M2-2) is
  done first, which itself doesn't require statewide scale to matter.
- RBAC/audit — already real at pilot scale; statewide scale mainly
  changes deployment topology (per-district admin scoping, not new
  authorization logic).

## What needs a decision before any code exists

- **Face Recognition.** Not a scale question — a legal/policy one. Per
  `RESEARCH.md`, this needs a specific department mandate plus a clear
  statutory framework (DPDP Act currently leaves police FRT use
  under-regulated, not clearly authorized) before it belongs on any
  committed roadmap, regardless of scale. If that mandate ever exists,
  the seam is the same `Protocol`-based stub/real pattern already used
  for `analytics/detector.py` — a `FaceDetector` interface with an honest
  stub until a real, bias-audited model is selected and legally cleared.
- **VAHAN/SARTHI/eGujCop/AFIS/NAFIS integration.** Not a scale question —
  an access-grant one. Requires those departments' own API/data-sharing
  agreements; nothing in Sentinel's own architecture blocks it (the
  "query, don't copy" federated-lookup pattern in `HLD.md` is already the
  right shape), but there's no path to building this without external
  cooperation this team doesn't control.
- **Crowd counting.** Lower-stakes than FRS but still a genuinely new
  requirement definition question — "crowd density" needs a defined
  threshold/use-case (e.g. event-safety monitoring vs. protest
  monitoring) before it's built, since the same detection-count
  aggregation could serve very different, differently-sensitive purposes
  depending on deployment context.

## Realistic sequencing if this were ever greenlit

1. **District pilot** (one NETRAM-equivalent district, PostgreSQL swap —
   already zero-code-change per `DATABASE_URL`'s env-based design) proves
   the scale-up path works before any statewide commitment.
2. **Regional rollout** introduces Kafka and validates the Re-ID
   similarity-search-at-scale problem `SCALABILITY.md` §2 names as an
   explicitly unsolved problem at 80,000-camera volume (tens of billions
   of embeddings) — this needs a real vector-search solution that the
   pilot's linear-scan approach doesn't require yet. **Named 2026-09-17**
   (see `RESEARCH.md`): pgvectorscale (PostgreSQL License, DiskANN-based,
   no new database system) as the district/regional-scale interim step,
   graduating to Milvus (Apache-2.0, designed for billion-scale ANN
   search) at genuine statewide volume — both permissively licensed, no
   AGPL conflict with `CLAUDE.md` §16's policy. Flag this as the single
   hardest unresolved *technical* problem in the whole roadmap, separate
   from the FRS/integration *policy* questions above — naming a
   candidate technology doesn't resolve it; it's still unbuilt and
   unvalidated at real volume.
3. **Statewide (Model 4)** adds Triton/DeepStream inference serving,
   Kubernetes GPU orchestration, TimescaleDB, and the DR posture in
   `ARCHITECTURE.md` — by this point FRS/crowd-counting/govt-DB questions
   need to already be resolved, not decided in-flight.

## What this document is not

Not a commitment to build any of this. Not a claim that Sentinel today
handles 80,000 cameras, statewide storage, or any Model 4 analytic beyond
what Model 1/2 already demonstrate at pilot scale. If asked in a jury
Q&A, the honest answer is: "the core capability is proven at pilot scale;
scaling it is a real infrastructure investment with one named hard
technical problem (Re-ID search at scale) and two named policy decisions
(FRS, live government-DB access) still open — here's the credible path,
not a claim it's already walked."
