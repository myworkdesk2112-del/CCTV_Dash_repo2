# Model 4 — Research Notes

External research grounding `ARCHITECTURE.md` and `REQUIREMENTS.md`.
Compiled 2026-09-11. This is roadmap research for a platform that will
not be built this hackathon — the bar here is credibility to a technical
jury (Gujarat Police leadership + NFSU/DA-IICT academic partners), not
buildability this week.

## Real reference precedent: existing Indian statewide/city platforms

- **Ahmedabad Smart City's Command and Control Centre (Paldi)**,
  operational since 2018, is real and independently verified: roughly
  **6,000 CCTV cameras installed since 2015 under the Smart City and
  Nirbhaya projects combined**, including **1,600 cameras covering the
  city's 130 major traffic junctions**, centrally monitored from Paldi
  (deshgujarat.com, 2018 launch coverage; local reporting on the
  network's growth). This is a real, named, in-state precedent — Model
  4's roadmap should frame itself as *integrating with and extending*
  infrastructure like this rather than proposing a fictional greenfield
  80,000-camera build with no anchor in what Gujarat already operates.
  **Correction (2026-09-11, independently re-verified):** an earlier
  draft of this document cited a more granular breakdown (2,117 cameras
  in 2017 + 300 under Nirbhaya + a 106-camera 2026 expansion) and a ₹8
  crore cost figure — neither could be independently confirmed against a
  credible source and both are removed; only the ~6,000-total and
  1,600-junction-camera figures above are kept, since both were verified
  this pass.
- **Bengaluru's Safe City programme** is a comparable second Indian
  reference point (3,400+ cameras planned; a 7,000-camera contract with
  Honeywell was cited in earlier reporting) — cited generally as
  supporting precedent, not as a source of specific current numbers we
  can't independently verify.
- Statewide/citywide platforms like **China's Skynet/Sharp Eyes** and
  **NYC/Chicago's Domain Awareness System** are widely reported at a
  general level but their current specifics weren't independently
  re-verified this pass — cited as "widely-documented" category
  precedent for the concept of a statewide surveillance/analytics
  platform, not as a source of numbers to reuse here.

## Technology stack — real products, tied to `SCALABILITY.md`'s existing tiers

- **NVIDIA Metropolis / DeepStream** is the concrete, named production
  successor to today's in-process YOLOv8 pipeline: DeepStream provides
  GPU-accelerated multi-stream decode + batched inference, and Metropolis
  is NVIDIA's vertical stack (including Triton for model serving and
  Fleet Command for edge orchestration) explicitly marketed for
  smart-city/public-safety deployments. This is the real technology
  precedent behind the spec's "GPU analytics" line.
- **Triton Inference Server** specifically is the credible upgrade from
  "one Python process calls YOLOv8 per stream" to a decoupled, batched
  inference tier that can serve many camera streams' requests
  efficiently — worth naming explicitly rather than leaving "GPU
  analytics" abstract.
- **Kubernetes + NVIDIA GPU Operator** is the standard real pattern for
  autoscaling GPU-analytics pods; this doc names it rather than inventing
  a custom orchestration design.
- **Kafka partitioned by `camera_id`** for ordered per-camera event
  streams is the standard fleet-scale pattern, and matches where
  `SCALABILITY.md` §6 (step 3, regional rollout) already introduces
  Kafka — Model 4 doesn't re-derive this, it inherits it.
- **TimescaleDB over plain PostgreSQL** is justified once full statewide
  retention volume makes time-range queries with continuous aggregates
  worthwhile. `SCALABILITY.md` §4 already names TimescaleDB for the warm
  tier; Model 4's addition is that at the *full statewide* volume beyond
  that tier, TimescaleDB (or an equivalent time-series extension) becomes
  necessary rather than optional.

## Face Recognition — the specific, checkable evidence base

This is deliberately more specific than "FRS has bias/privacy concerns"
— the two citations below are checkable, not paraphrased vaguely:

- **NIST Interagency Report 8280 ("Face Recognition Vendor Test (FRVT)
  Part 3: Demographic Effects", December 2019, nvlpubs.nist.gov/nistpubs/
  ir/2019/nist.ir.8280.pdf)** tested nearly 200 algorithms from nearly 100
  developers across 18M+ images of 8M+ people, and found **widespread,
  statistically significant false-positive-rate differentials across
  demographic groups, occurring even in pristine (high-quality) images**
  — the report states these false-positive effects are far larger than
  false-negative effects, with within-group false-positive-rate variation
  reaching a factor of up to **7,200×** under some algorithm/threshold/
  dataset combinations. **Correction (2026-09-11, independently
  re-verified):** an earlier draft cited a specific "10×–100×" figure and
  named "Asian and African-American faces" and "African-American women"
  as the specific highest-risk groups for 1:1 and 1:N matching
  respectively — neither the specific multiplier nor those specific
  demographic-group claims could be independently confirmed against the
  primary source in this pass, so both are removed. The confirmed,
  citable finding is the broader one above (widespread differentials,
  factor-of-7,200× within-group variation) — it's sufficient on its own
  to ground the "don't build this without further study" conclusion
  without needing the unconfirmed specifics.
- **Delhi Police's FRS deployment** is a directly relevant domestic
  cautionary case, independently confirmed this pass: Delhi Police told
  the Delhi High Court in 2018 that its own facial-recognition system's
  accuracy was **2%** and "not good" (per Outlook India, Deccan Herald,
  National Herald reporting); an Internet Freedom Foundation RTI later
  found Delhi Police treats an **80% similarity score** as sufficient
  grounds to pursue a suspect as a "positive" match (internetfreedom.in,
  medianama.com) — a threshold drawing comparisons to the ACLU's
  widely-cited 2018 test in which Amazon Rekognition produced 28 false
  matches against sitting US Congress members. The same RTI reporting
  confirms Delhi Police **had not analysed how the system could impact
  privacy** (supporting the "no privacy impact assessment" claim), and
  subsequent reporting through 2026 (e.g. techtimes.com coverage of
  student-protester scanning) documents continued use beyond the
  system's original stated purpose. **Correction:** an earlier draft
  said "accuracy around 1–2% in 2018–2019 trials" — the specifically
  confirmed figure is **2%**, from the 2018 Delhi High Court statement;
  softened to avoid implying a precision the source doesn't support.
- **DPDP Act 2023** treats biometric data as personal data requiring
  consent and purpose limitation, but there is no India-specific statute
  governing police FRT use specifically — deployment today rests on
  general policing powers and the IT Act. This is a regulatory *gap*, not
  a green light: building FRS into a committed architecture ahead of
  clear statutory authorization is a real legal-exposure decision for
  whichever department eventually operates it, not a purely technical
  one.

## Disaster recovery — realistic pattern, not aspirational

Active-active replication of raw video at petabyte scale is not the
realistic ask (cost-prohibitive, and no public-safety system reviewed
here claims it) — the realistic, citable pattern is active-passive for
the control/database tier (RTO in minutes, near-zero RPO via
synchronous/semi-synchronous replication) plus tiered lifecycle
replication for storage (hot/warm cross-zone, cold/archive cross-region
with an hours-scale RPO), which is consistent with — not a redefinition
of — `SCALABILITY.md` §4's existing hot/warm/cold tiers.

## Phased rollout — inherits `SCALABILITY.md` §6, does not redefine it

`SCALABILITY.md` §6 already specifies: Pilot (~30 cameras, SQLite,
single-node, this submission) → District pilot (PostgreSQL, one edge GPU
unit) → Regional rollout (multiple districts, Kafka introduced) →
Statewide (~80,000 cameras, all 26 departments, full edge-unit fleet).
Model 4 **is** that statewide tier — this document doesn't propose a
different rollout shape, it fills in what analytics/governance decisions
apply once that tier is reached (FRS excluded, crowd-counting/anomaly
detection included, DR posture as above).

## Vector search at Re-ID scale — the named hard technical problem, now with a candidate technology

`IMPLEMENTATION_PLAN.md` names cross-camera Re-ID similarity search at
80,000-camera volume (tens of billions of stored embeddings) as the
single hardest unresolved *technical* problem in the whole roadmap, and
previously left "a proper ANN index" unnamed. Researched 2026-09-17:

- **FAISS** (Meta, MIT) is a library, not a deployable server — used
  internally by other systems but not itself a production serving tier.
- **Milvus** (Apache-2.0, LF AI & Data project) is purpose-built for
  exactly this shape of problem: vendor/independent sources describe it
  as designed for horizontal scaling past one billion vectors, with
  multiple ANN index types (HNSW/IVF/PQ). **This is the candidate named
  for genuine statewide scale.**
- **Qdrant** (Apache-2.0, Rust, HNSW + strong metadata filtering) is a
  credible alternative at the 10–100M-vector band.
- **pgvector / pgvectorscale** (PostgreSQL License, Timescale) adds
  DiskANN-based indexing directly onto PostgreSQL — this project's
  existing database — and multiple independent 2026 comparisons rank it
  competitive up to roughly 50–100M vectors. **This is the credible
  *interim* step**: a district/regional-rollout-scale Re-ID search
  upgrade that requires no new database system, before a genuine
  statewide deployment would need to graduate to Milvus.
- All four are permissively licensed (MIT/Apache-2.0/PostgreSQL
  License) — consistent with this project's AGPL-avoidance policy
  (`CLAUDE.md` §16), no additional licensing decision needed here.

**Confidence caveat, stated honestly**: no independently-audited,
neutral third-party production case study confirming a specific
"largest known deployment size" was found for any of these — the
"past one billion vectors" and "50–100M vector" figures above are
vendor-reported/vendor-adjacent-benchmarked capability claims, not
independently verified production evidence. Cite them as engineering
sizing signal, not a proven number, exactly as `SCALABILITY.md` already
does for its own compute/bandwidth estimates.

Sources: [pgvector performance benchmarks — Instaclustr](https://www.instaclustr.com/education/vector-database/pgvector-performance-benchmark-results-and-5-ways-to-boost-performance/), [Postgres Vector Search Compared 2026](https://www.web3aiblog.com/blog/postgres-vector-search-compared-pgvector-pgvectorscale-paradedb-lantern-2026), [Postgres Won: 2026 Vector Database Guide — Statix](https://www.statix.az/blog/vector-database-selection-guide-2026-postgres-pgvector), [Best 17 Vector Databases 2026 — lakeFS](https://lakefs.io/blog/best-vector-databases/), [Comparing open source vector databases — Redis](https://redis.io/blog/best-open-source-vector-databases-comparison/), [pgvectorscale on GitHub](https://github.com/timescale/pgvectorscale), [Pgvector vs. Pinecone — Tiger Data](https://www.tigerdata.com/blog/pgvector-is-now-as-fast-as-pinecone-at-75-less-cost)

## Security architecture — see the dedicated document

A full statewide security-architecture research pass (CERT-In, MeitY/
STQC, DPDP Act §17's law-enforcement provisions, ISO 27001 in real
Indian government CCTV tenders) is written up separately in
`SECURITY_ARCHITECTURE.md` rather than duplicated here, since
`REQUIREMENTS.md` named a *dedicated* security architecture document as
the missing Model 4 deliverable.

## Caveat

Current 2026-specific figures for China's Skynet/Sharp Eyes and NYC/
Chicago's Domain Awareness System were not independently re-verified this
pass — treat those two as general category precedent only. The Ahmedabad
camera count, NIST FRVT findings, DPDP Act framing, and Delhi Police FRS
history are the load-bearing citations in this document and were checked
this session.
