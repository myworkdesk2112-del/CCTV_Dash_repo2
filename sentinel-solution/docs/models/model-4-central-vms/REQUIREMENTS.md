# Model 4 — Requirements Coverage

## Scoped pilot capability slice (2026-09-13)

This does not change Model 4's statewide roadmap status. The following are
small pilot capabilities, not deployed statewide infrastructure:

| Capability | Evidence status | Boundary |
|---|---|---|
| Sampled-frame vehicle/person counts | **AUTOMATED-TEST VERIFIED** | `CameraDensityWindow` and `GET /admin/density`; raw detector counts, not unique persons or crowd-size estimates |
| Hot/warm/cold metadata | **IMPLEMENTED, UNVERIFIED** | `VehicleEvent.storage_tier` and dynamic age classification; no S3/Ceph/object storage |
| Central pilot rollup | **AUTOMATED-TEST VERIFIED** | `GET /admin/central-rollup` reads existing pilot DB data; not a statewide deployment |
| Pilot DR runbook | **IMPLEMENTED, UNVERIFIED** | SQLite backup/restore procedure in `DR_RUNBOOK.md`; multi-region failover remains a DESIGN TARGET |

Every bullet below is copied from the official challenge problem
statement's Model 4 section (`docs/hackathon/HACKATHON_DETAILS.md` §7,
plus Q20–Q22). **Model 4 is design/roadmap-only and will not be built
this hackathon** — status below is "roadmap" everywhere, never "done."
This mirrors how `docs/hackathon/REQUIREMENTS_COVERAGE.md` already frames
Model 3/4 as "documented roadmap, not built," extended here into a
per-requirement breakdown.

Official spec text:

> Fully consolidated statewide platform with centralised monitoring,
> recording, storage, and AI analytics.

## Key functional features

| Requirement | Roadmap status | Notes |
|---|---|---|
| Centralised ingestion | Roadmap, extends existing pilot | Same `StreamManager`/catalogue-discovery pattern already built for 30 cameras, scaled per `SCALABILITY.md` §2's edge-tier GPU sizing (~20 cameras/GPU) |
| Tiered storage (hot/warm/cold) | Roadmap, already specced | `SCALABILITY.md` §4 defines the tiers and retention windows; this doc doesn't redefine them |
| ANPR | Roadmap, direct extension of built capability | Already real and verified at pilot scale (Model 2) — scaling is a compute/GPU-count problem, not an unsolved capability |
| Face recognition | **Deliberately excluded from any committed roadmap** | See `ARCHITECTURE.md`'s "Why FRS is out" — NIST FRVT demographic-disparity findings + Delhi Police FRS precedent + DPDP Act's regulatory gap. A documented seam (`Protocol`-based, matching the existing stub/real pattern), not a commitment |
| Crowd/vehicle counting | Roadmap | Straightforward detection-count aggregation on top of the existing YOLOv8 detector — no new ML capability needed |
| Anomaly detection | Roadmap, direct extension of built capability | Extends `analytics/anomaly.py`'s existing wrong-way/restricted-zone detectors; calibration caveats already noted in Model 2's `RESEARCH.md` apply at any scale |
| Vehicle tracking | Roadmap, direct extension of built capability | Cross-camera identity resolution already real at pilot scale (Model 2) |
| Database integration readiness | Roadmap, design-only | "Query, don't copy" federated-lookup principle already stated in `HLD.md`; VAHAN/SARTHI/eGujCop/AFIS/NAFIS access depends on those departments' own grants, outside our control |
| Redundancy/disaster recovery/RBAC | Roadmap (RBAC partially real today) | RBAC is genuinely real and enforced at pilot scale already (department-scoped, role-based, audited); statewide redundancy/DR posture is described in `ARCHITECTURE.md`, not built or tested |

## Expected deliverables

| Deliverable | Roadmap status | Notes |
|---|---|---|
| Working prototype using multi-department feeds | **Not attempted at Model 4 scale** | Multi-department feeds ARE demonstrated at pilot scale (Model 1/2, 5 departments in the sandbox) — that's the honest ceiling of what this submission claims as "working," not a statewide prototype |
| ANPR and vehicle-tracking demo | Already delivered at pilot scale | Same real demo evidence cited in Model 2's `REQUIREMENTS.md` — not re-demonstrated at Model 4 scale since no Model 4 infrastructure exists |
| Scalability/load-test report for ~80,000 cameras | Delivered as a *sizing report*, not a *load test* | `SCALABILITY.md` — real capacity/bandwidth/cost arithmetic, explicitly not a load test against real infrastructure that doesn't exist. Don't conflate "we sized it" with "we tested it at that scale" |
| Disaster-recovery design | Delivered as design | `ARCHITECTURE.md`'s DR posture section, inheriting `SCALABILITY.md` §4/§5's tier definitions |
| Security architecture document | Delivered as design (2026-09-17) | `SECURITY_ARCHITECTURE.md` — real, cited Indian regulatory grounding (CERT-In's 2022 directions, MeitY/STQC empanelment and the PPO'24/CRO'24 CCTV-hardware mandate, DPDP Act 2023 §17's law-enforcement provisions), alongside `HLD.md`'s existing pilot-scale RBAC/security sections. A design/roadmap document, not a compliance claim or audit |

## What "roadmap-only" means, stated plainly

Nothing in this table should be read as built, tested, or demonstrated at
Model 4 scale. Every roadmap item that isn't FRS is a *scale* extension
of something already real and working at pilot scale (Model 1/2) — the
honest claim is "the architecture and the core capability already work;
scaling it is a compute/infrastructure investment, not an unsolved
engineering problem," except for FRS, which is excluded on legal/ethical
grounds regardless of scale, and live government-DB integration, which
depends on external access grants this team cannot obtain unilaterally.
