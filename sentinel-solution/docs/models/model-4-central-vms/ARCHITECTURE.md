# Model 4 — Central VMS Model — Architecture

## Scoped pilot capability slice (2026-09-13)

`GET /admin/density` persists sampled-frame vehicle/person detector counts;
these are raw detector outputs, not crowd-size estimates. `GET /admin/central-rollup`
combines actual pilot registry, health, alert and federation data for admins.
Event hot/warm/cold classification is metadata only and does not move data to
S3/Ceph. `DR_RUNBOOK.md` documents an isolated SQLite backup/restore drill.

These are pilot features, not statewide infrastructure. Kafka, Kubernetes,
Triton, TimescaleDB, S3/Ceph, FRS and live government-database integration
remain explicit roadmap/excluded items.

**Design/roadmap only — not built, not planned to be built this
hackathon.** Per `docs/strategy/STRATEGY.md`'s OUT list, a full
80,000-camera central platform is explicitly out of the time budget. This
document exists so the submission can credibly discuss the statewide
end-state a jury will ask about, without ever implying it's running
today. Cross-references `sentinel-solution/docs/SCALABILITY.md` rather
than restating its numbers — that document is the authoritative scale
plan; this one adds Model 4-specific architecture (FRS/crowd-counting/
govt-DB-integration scope, DR posture) that `SCALABILITY.md` doesn't
cover in depth.

## What Model 4 actually is, per the spec

> "Central VMS and AI Platform" providing centralized monitoring,
> recording, storage, and advanced AI analytics across departments
> (Q20). Infrastructure: scalable storage, high-bandwidth connectivity,
> centralized compute, redundancy, cybersecurity controls, large-scale
> ingestion (Q21). Analytics: ANPR, face recognition, crowd/vehicle
> counting, anomaly detection, statewide tracking, plus VAHAN/SARTHI/
> eGujCop/AFIS/NAFIS integration (Q22).

This is the "statewide" tier of the same rollout `SCALABILITY.md` §6
already describes — Model 4 is not a separate system from what Sentinel
would become at full scale, it's the end state of the same pilot,
described here with the analytics-scope and governance detail
`SCALABILITY.md` deliberately left out (that document is about compute/
storage/network sizing, not which analytics to build or which are
excluded and why).

## Where Sentinel already sits relative to Model 4

Gujarat already operates a real precedent at meaningful scale: Ahmedabad
Smart City's Command and Control Centre at Paldi (operational since 2018)
centrally monitors roughly 6,000 CCTV cameras installed since 2015 under
the Smart City and Nirbhaya projects combined, including 1,600 cameras
covering the city's 130 major traffic junctions specifically — figures
independently verified 2026-09-11 (deshgujarat.com and local reporting;
a more granular per-project breakdown and a cost figure in an earlier
draft of this document couldn't be confirmed and were removed, see
`RESEARCH.md`). Bengaluru's Safe City programme is a comparable second
Indian reference point (3,400+ cameras planned, with a 7,000-camera
contract cited in earlier reporting, not independently re-verified). **Model 4's realistic path is integrating with and
extending existing command-centre infrastructure like Ahmedabad's, not
proposing a fictional greenfield statewide platform built from nothing.**
This is a more credible framing for a Gujarat Police jury than an
abstract 80,000-camera design with no anchor in what already exists.

## Component architecture (target, statewide tier)

Builds directly on `SCALABILITY.md`'s tiers — edge (per-camera-cluster
inference), regional (per-district aggregation, aligned to Gujarat's
existing 34 NETRAM centres), central (statewide). Model 4 adds:

```text
┌─────────────────────────────────────────────────────────────────┐
│ Central tier (statewide)                                          │
│  - Kubernetes + NVIDIA GPU Operator: autoscaled GPU-analytics pods │
│  - Triton Inference Server: batched, decoupled inference serving  │
│    (successor to today's in-process YOLOv8 call in the pilot)     │
│  - TimescaleDB: full-retention time-series vehicle-event history  │
│    beyond SCALABILITY.md §4's warm-tier PostgreSQL/PostGIS         │
│  - S3-compatible/Ceph object storage: hot/warm/cold video lifecycle│
│    (tier definitions inherited from SCALABILITY.md §4, not redefined)│
│  - Kafka: partitioned by camera_id (per-camera ordering), matching │
│    SCALABILITY.md §6 step 3's regional-rollout introduction point  │
│  - Milvus (Apache-2.0): billion-scale ANN vector search for cross- │
│    camera Re-ID embeddings — see RESEARCH.md, named 2026-09-17 as  │
│    the candidate for the roadmap's single hardest named technical  │
│    problem (linear-scan embedding search doesn't work at this      │
│    volume). pgvectorscale (PostgreSQL License, DiskANN-based) is   │
│    the interim step at district/regional scale, requiring no new  │
│    database system before a genuine statewide deployment graduates│
│    to Milvus.                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Analytics scope at the Model 4 tier — what's roadmap vs. deliberately excluded

| Analytic | Status | Reasoning |
|---|---|---|
| ANPR, cross-camera vehicle tracking | Roadmap — direct extension of what's already built and verified in Model 1/2 | No new capability, just scale |
| Anomaly detection (wrong-way, restricted-zone, extend to crowd density) | Roadmap | Extends `analytics/anomaly.py`'s existing pattern; crowd/vehicle counting is a straightforward detection-count aggregation, not a new ML capability |
| Face Recognition (FRS) | **Deliberately excluded from any committed roadmap** | See "Why FRS is out" below — a real, cited legal/technical risk, not a capacity gap |
| VAHAN/SARTHI/eGujCop/AFIS/NAFIS integration | Roadmap, design-only ("query, don't copy") | Matches `HLD.md`'s existing principle — federated lookups against authoritative government databases, never a local copy; requires those departments' own API/access grants, outside our control to build |

## Why FRS is out — real, cited grounding, not hand-waving

Two independent, verifiable reasons, not a vague "privacy concern":

1. **NIST FRVT Part 3: Demographic Effects (NISTIR 8280, 2019)**, tested
   against nearly 200 algorithms from nearly 100 developers across 18M+
   images, found widespread, statistically significant false-positive-
   rate differentials across demographic groups — occurring even in
   pristine, high-quality images — with within-group false-positive-rate
   variation reaching a factor of up to **7,200×** under some algorithm/
   threshold/dataset combinations. (An earlier draft of this section
   cited a specific "10×–100×" figure and named specific highest-risk
   demographic groups for 1:1/1:N matching; neither could be
   independently confirmed against the primary source and both were
   removed 2026-09-11 — see `RESEARCH.md` for the correction. The
   confirmed finding above is sufficient on its own to ground this
   section's conclusion.)
2. **Delhi Police's own FRS deployment** is a direct domestic cautionary
   precedent, independently confirmed: Delhi Police told the Delhi High
   Court in 2018 its own system's accuracy was **2%** and "not good"; an
   80%-similarity threshold was later adopted by Delhi Police as
   sufficient grounds to treat a match as "positive" (a threshold
   criticized internationally, comparable to the ACLU's 2018 test where
   Amazon Rekognition produced 28 false matches against sitting US
   Congress members' faces), and Internet Freedom Foundation RTI
   findings that no privacy impact assessment or retention policy
   existed for that deployment, alongside documented mission creep
   (authorized for missing-children tracing, later used at political
   rallies and protests).

Separately, **DPDP Act 2023** treats biometric data as personal data
requiring consent and purpose-bound deletion, but has no FRT-specific
statute — police use currently rests on general policing powers and the
IT Act, which is itself a legal-risk argument (under-regulated, not
clearly authorized) rather than a green light. Given both the accuracy-
disparity evidence and the regulatory gap, FRS stays a documented,
explicitly-not-built roadmap item — not silently dropped, not built
speculatively. If a specific department mandate and legal framework
authorized it in the future, the same `Protocol`-based stub/real pattern
used throughout this codebase (`analytics/detector.py`) is the seam where
it would plug in — this is noted as a seam, not a commitment.

## Disaster recovery posture (target)

- **Control/API/database tier:** active-passive multi-region, RTO in
  minutes, RPO near-zero via synchronous/semi-synchronous replication —
  the standard pattern for public-safety-critical systems; true
  active-active isn't justified for this workload and would add
  operational complexity with no corresponding requirement.
- **Video storage tier:** not full active-active replication of raw
  footage (cost-prohibitive at petabyte scale) — instead, tiered
  lifecycle replication matching `SCALABILITY.md` §4's hot/warm/cold
  definitions: hot/warm replicated cross-zone, cold/archive replicated
  cross-region with a slower RPO measured in hours, not minutes.

See `IMPLEMENTATION_PLAN.md` for the phased rollout (inherits
`SCALABILITY.md` §6 directly), `REQUIREMENTS.md` for the literal
spec-to-status mapping, and `SECURITY_ARCHITECTURE.md` for the dedicated
security-architecture deliverable (CERT-In, MeitY/STQC, DPDP Act §17).
