# Sentinel — Scalability Strategy (Plan for Scale)

**Submission deliverable per HACKATHON_DETAILS.md §9.5.** Covers
central/regional/edge compute, GPU/accelerator sizing, network bandwidth
planning, storage tiers, load balancing/HA/DR, and a rough cost estimate
for scaling from this submission's ~30-camera pilot to the ~80,000-camera
statewide target. Numbers here are engineering estimates for planning
purposes, not vendor quotes — labeled as such throughout.

## 1. Why full central video ingestion is not the plan

80,000 cameras × ~2 Mbps average bitrate ≈ **160 Gbps sustained** ingress,
≈ **1.7 PB/day** of raw video if centralized. That is not a credible
target for any team at hackathon scale, and pretending otherwise in a
scalability document would be the least credible thing we could submit to
a technical jury. The architecture instead centralizes **structured
events**, not frames:

```
Per camera: ~1 vehicle event/sec peak (urban junction) × ~1 KB/event (plate,
timestamp, camera_id, embedding, confidence) ≈ 1 KB/s/camera

80,000 cameras × 1 KB/s ≈ 80 MB/s ≈ 640 Mbps sustained event-plane traffic
```

That's a **~250x reduction** versus raw video (160,000 Mbps ÷ 640 Mbps —
corrected 2026-09-11 from an earlier "three orders of magnitude"/~1000x
claim, which was arithmetically wrong; independently recomputed during a
project review), and it's still what makes a Kafka/PostgreSQL-based event
plane a realistic central tier even at full scale. Video itself stays
regional/local — see §3. Note the 640 Mbps side is itself an
underestimate for planning purposes: it excludes JSON/protocol overhead,
evidence-crop transmission, and replica-write traffic, so the real
achievable reduction in production is likely somewhat less than 250x, not
more.

**MEASURED, this pilot, 2026-09-28** (`scripts/measure_bandwidth_reduction.py`,
real timed RTSP captures + real `vehicle_event` rows from the accumulated
`sentinel.db` — not the assumed figures above): a real 10-second capture
of 3 real live sandbox cameras averaged **497.4 kbps** actual RTSP
bitrate — lower than the ~2 Mbps assumption used for the statewide
projection above, though this is one real sandbox's encoder settings, not
necessarily representative of departmental camera configurations
statewide. Against that same pilot's real structured-event traffic — a
real 108-byte average `vehicle_event` payload at a real measured
**0.0456 events/sec** on the one live camera with actual traffic history
— the real measured compression ratio is **~12,624x**, well above the
250x planning figure above. **Do not use 12,624x as the statewide
number**: it is inflated by this pilot's genuinely low real traffic
density (roughly one detected vehicle every 22 seconds); a busy urban
junction generating closer to the "~1 vehicle/sec peak" figure assumed
above would show a real ratio much closer to that ~250x planning
estimate. Treat 640 Mbps/~250x as the operative statewide planning
number; treat 497.4 kbps and 12,624x as **LIVE/REAL VERIFIED** evidence
that the underlying architectural principle (structured events cost
orders of magnitude less than raw video) is real and measured on this
pilot, not merely assumed. Raw artifact:
`sentinel-solution/backend/data/bandwidth_measurement/20260928T163729Z.json`.

## 2. Compute tiers

| Tier | Role | Sizing basis |
|---|---|---|
| **Edge** (per camera cluster / NVR site) | RTSP ingestion, frame sampling, YOLOv8 + PaddleOCR inference, within-camera tracking | 1 GPU (e.g. T4-class) comfortably handles ~15–25 concurrent camera streams at `ANALYTICS_FRAME_STRIDE=5` sampling with YOLOv8n + PaddleOCR (mobile-scale models chosen specifically for this — see STRATEGY.md) |
| **Regional** (per district/NETRAM-equivalent) | Cross-camera Re-ID within the region, regional event aggregation, regional media fabric (MediaMTX/go2rtc) for selective live relay | Scales with camera count per district; Gujarat's existing 34 NETRAM centres are a natural regional boundary to align with, not duplicate |
| **Central** (state-level, TRINETRA-equivalent) | Cross-region identity correlation, watchlist matching, RBAC/audit, GIS registry, public-facing dashboards | Horizontally scaled API + DB tier; this submission's FastAPI + SQLAlchemy code is the same code that runs here, pointed at PostgreSQL instead of SQLite |

**This submission demonstrates the edge tier's actual code path** (real
YOLOv8 + PaddleOCR, verified end-to-end — see HLD.md §5) at ~30-camera
scale, with the central-tier API/registry/RBAC layer built to the same
interface it would run at full scale, not a different mocked one.

### GPU accelerator estimate

- ~20 cameras/GPU (edge, mobile-scale models) → **80,000 / 20 ≈ 4,000 GPU-
  class edge inference units** statewide at full build-out. This is our
  own engineering estimate for this workload (YOLOv8n + PaddleOCR at
  `ANALYTICS_FRAME_STRIDE=5`), in the same range commonly cited for
  T4/L4-class GPUs running lightweight detection models at reduced frame
  rates — not independently benchmarked against a specific vendor sizing
  guide, and stated as such rather than implied to be a verified figure.
- This is why a phased rollout (§6) matters: the pilot doesn't need to
  provision for 4,000 GPUs to prove the architecture works — it proves the
  *pattern* (one edge unit's software stack, replicated), and rollout
  scales unit count with camera count, not architecture.
- **Edge fail-soft on central-link loss:** an edge unit that loses
  connectivity to the central watchlist/API must not silently stop
  alerting. Design target: each edge unit keeps a local cache of the
  active high-priority watchlist (plates only — a small, refreshable
  list), so plate-match alerting continues to function during a network
  partition; only cross-region correlation and central audit logging are
  deferred until the link recovers. Not built this week — the pilot's
  single-node deployment has no edge/central split yet for this to apply
  to — but the watchlist service's existing `check()` interface
  (`watchlist/service.py`) is already a simple enough lookup to cache this
  way without a redesign.

### Re-ID similarity search at scale — a named unsolved problem, not glossed over

At full build-out, appearance embeddings accumulate fast: ~1 vehicle
event/sec/camera peak × 80,000 cameras × 86,400 s/day ≈ **6.9 billion
events/day** statewide (arithmetic, not a claim about any external
system) if retained at the hot-tier window (§4). Brute-force
nearest-neighbor search against that store for every new detection is not
tractable at this volume. The documented approach (not built this week,
since it needs the district-scale rollout in §6 to be worth building):

- **A dedicated vector index** (`pgvector` for moderate scale, or a
  purpose-built vector DB like Milvus/Qdrant at full scale, using
  approximate-nearest-neighbor indexing such as HNSW — the standard
  technique these engines use to keep similarity search sub-second at
  billion-vector scale) — PostGIS is a spatial extension, not a
  vector-similarity engine, and is not the right tool for embedding
  search.
- **Candidate filtering before similarity search, not after:** a new
  detection only searches embeddings from (a) cameras within plausible
  travel distance/time of where it was seen (§ occlusion-handling logic
  in the proposal's design, same principle as travel-time plausibility),
  and (b) a bounded recent time window. This turns an intractable
  full-store scan into a bounded regional/temporal lookup — the same
  reason regional Re-ID matching is placed at the **regional** tier (§2's
  table), not the central tier, in this architecture.

## 3. Network bandwidth planning

- **Camera → edge:** local/regional network only, video never leaves the
  region except for the specific live-view requests an operator actively
  opens ("pace your load" — already enforced in this build's
  `StreamManager`: only cameras being actively processed/viewed have open
  connections).
- **Edge → regional → central:** structured events only (§1's ~640 Mbps
  full-scale estimate), plus on-demand selective video relay (an operator
  viewing a specific camera's live feed, or pulling a specific incident's
  clip) — not a firehose.
- **Low-bandwidth sites** (rural/border districts explicitly called out in
  the problem statement — Valsad, Dahod, Dwarka): run detection/OCR at the
  edge unconditionally so only KB-scale events cross the low-bandwidth
  link, never raw frames. This is not a future optimization — it's the
  same architecture already used for the ~30-camera pilot, just phrased at
  scale.
- **Store-and-forward for total link loss:** a low-bandwidth link can drop
  to zero, not just a low rate. Design target: an edge unit spools
  generated events to local non-volatile storage when the uplink is down
  and trickle-uploads the backlog once connectivity returns, rather than
  dropping events generated during the outage — a standard reliability
  pattern for intermittently-connected edge/IoT deployments generally, not
  specific to any one vendor. Not built this week (the pilot's single-node
  deployment has no edge/central network hop for this to apply to), and
  the actual spool size/retry policy would need real link-outage data from
  a district pilot (§6) to size correctly rather than guessed here.

## 4. Storage tiers

| Tier | Contents | Retention | Technology |
|---|---|---|---|
| Hot | Live event stream, active alerts, last N days of vehicle events | 7–15 days (matches existing departmental retention per HACKATHON_DETAILS.md §5) | PostgreSQL/PostGIS, indexed on plate + camera + timestamp |
| Warm | Historical events for investigation lookback | 90 days–1 year (case-dependent; purpose-bound queries against this tier are audit-logged the same as hot-tier queries) | Partitioned PostgreSQL tables or a columnar store (e.g. TimescaleDB) |
| Cold | Long-retention compliance archive; NOT raw video by default (see §1) — structured events + any specifically-preserved video for active cases | Per legal/case retention policy | Object storage (S3-compatible), lifecycle-tiered |

Video itself follows **each department's own existing retention** (7–15+
days, cloud or local per HACKATHON_DETAILS.md §5) — Sentinel does not take
over video storage, consistent with the "interoperability layer, not a
replacement VMS" pitch (STRATEGY.md).

**Evidential hold, not yet built:** the automated purge described above
(`db/retention.py`) must not delete a record an investigator has flagged
as active case evidence — a standard legal-hold/litigation-hold pattern in
records-management generally, not specific to this domain. Design target:
an explicit hold flag on the relevant record(s), set via a purpose-bound,
audited action (same audit mechanism already used for cross-department
queries — see HLD.md §9), that exempts it from `purge_expired()` until an
authorized user clears the hold. Not built this week; the current
retention sweep has no such override, so a real deployment should not rely
on the automated purge alone once a record is genuinely under
investigation.

## 5. Load balancing, horizontal scaling, monitoring, HA/DR

- **API tier:** stateless FastAPI instances behind a load balancer;
  horizontal scaling is adding instances, no code change required (no
  in-process state beyond the DB connection pool).
- **Stream-manager tier:** each instance's `StreamManager.reconcile()`
  logic already only opens workers for cameras assigned to it, so sharding
  is a routing decision, not a rewrite. A static camera-ID-range shard is
  the simplest version of this and is fine for the pilot, but has a real
  weakness at scale: if one instance handling a dense cluster of cameras
  fails, its cameras go dark until that instance is manually replaced.
  Design target for the district/regional rollout (§6): a container-
  orchestrated deployment (e.g. Kubernetes) where camera-to-instance
  assignment is tracked in shared state and automatically rebalanced onto
  surviving instances on failure, rather than a fixed range. Not built
  this week — the pilot's single-node deployment has only one instance, so
  there is nothing to rebalance yet.
- **Health monitoring:** already implemented for this submission's scale —
  each `RtspCameraWorker` reports `connected`/`last_frame_at`, synced into
  `CameraRegistry.is_healthy` (Model 1's health-monitoring deliverable) and
  surfaced via `GET /cameras/gap-analysis`. At full scale this feeds a
  standard metrics pipeline (Prometheus-style scrape per edge unit) rather
  than the current direct-DB-write loop — same signal, different transport.
- **HA/DR:** PostgreSQL primary/replica with automated failover; regional
  event stores replicate to the central tier asynchronously, so a regional
  outage doesn't lose central-tier watchlist/RBAC availability, only that
  region's fresh events until it recovers.
- **RBAC at scale:** the current API-key + role model
  (`ApiKeyEntry.department`) extends directly to department-scoped access
  control — a department's investigators see that department's cameras by
  default, escalating to cross-department queries only for roles
  explicitly granted it. Not built this week (single flat role set today),
  but the schema and dependency-injection pattern (`api/auth.py`) already
  supports adding the department-scope check without restructuring. A
  production statewide deployment should authenticate users against
  whatever identity-federation standard the government mandates for this
  program (e.g. an SSO/Aadhaar-linked framework) rather than this
  submission's standalone API-key model — which specific standard applies
  is an organizer/procurement decision, not specified here.
- **Edge physical/tamper risk:** an edge unit is physically reachable
  hardware (unlike a data-center server), so its threat model includes
  device theft and local tampering, not just network attacks — e.g. a
  compromised edge unit feeding fabricated detections/embeddings upstream.
  Design target: encrypted local storage on edge units and a boot-integrity
  check (standard hardening practice for physically-exposed compute, not
  specific to this project), so a tampered unit is detectable rather than
  silently trusted. Not built or hardware-selected this week — this is a
  procurement/deployment-hardware decision, not a software one.
- **Backup:** distinct from the HA/DR failover above — automated daily
  PostgreSQL base backups plus continuous WAL archiving (standard
  Postgres practice, e.g. `pgBackRest`/`WAL-G`), retained per the same
  hot/warm/cold windows as §4's live data, stored in a separate
  availability zone/region from the primary so a backup isn't lost to the
  same failure it's meant to recover from. Not built for the pilot's
  single SQLite file — a `sqlite3 .backup` cron job is the pilot-scale
  equivalent, sufficient for a ~30-camera demo, not a production
  substitute for the above.
- **Encryption:** TLS for every network hop (camera→edge stays on the
  department's own trusted network per §3; edge→regional→central and all
  operator-facing traffic run over TLS). At rest: full-disk/volume
  encryption on the database and object-storage tiers (standard cloud
  provider disk encryption, or LUKS for on-prem), plus the existing
  application-level protection already built for this submission — API
  keys are stored as SHA-256 hashes, never plaintext (`api/auth.py`), and
  the sandbox's own camera credentials are never exposed to the browser,
  only proxied server-side (`routes_stream.py`).
- **Network segmentation:** edge units sit on each department's own
  network segment (no direct internet exposure); only the structured
  event stream and the specific live-view relay traffic cross into the
  regional/central tier, through a defined gateway — the same "camera
  video never leaves its region except for an actively-opened view"
  principle as §3, extended to network topology, not just bandwidth.
  Central-tier API and database sit in their own segment, reachable only
  through the API gateway, not directly from edge/regional networks.

## 6. Phased rollout

1. **Pilot (this submission):** ~30 real sandbox cameras, single-node
   deployment, SQLite → demonstrates the full pipeline end-to-end.
2. **District pilot:** one NETRAM-equivalent district, PostgreSQL, one edge
   GPU unit, real department onboarding via the bulk-import API.
3. **Regional rollout:** multiple districts, Kafka event bus introduced
   between edge and central tiers (documented architecture already in
   HLD.md §2, not deployed this week).
4. **Statewide:** all 26 departments, ~80,000 cameras, full edge-unit
   fleet per §2's GPU estimate, central tier horizontally scaled per §5.

Each phase reuses the same codebase — the pilot's `AnalyticsPipeline`,
`IdentityResolver`, and RBAC layer are the same classes that run at
district and statewide scale, just deployed with more instances and a
different `DATABASE_URL`. Nothing in this submission is a throwaway demo
architecture that would need to be rebuilt for production.

## 7. Cost estimate (rough, for planning discussion only)

Split into capital (one-time build-out) and operational (recurring)
spend, since government audits of large infrastructure programs generally
find hardware procurement is a minority of true total cost of ownership —
licensing, support contracts, maintenance, and power/cooling recur every
year hardware doesn't. This document does not have real figures for any
of the OpEx rows; they're listed so the conversation doesn't stop at the
CapEx table alone.

**Capital expenditure (one-time build-out)**

| Item | Full-scale estimate | Basis |
|---|---|---|
| Edge GPU units | ~4,000 units (§2) | ~20 cameras/GPU |
| Central PostgreSQL cluster | Multi-TB, horizontally scaled | Hot+warm tier per §4 |
| Object storage (cold tier) | Scales with retained-case video, not full-fleet raw video | §4's default-no-raw-video policy |
| Network build-out | Regional links sized for §3's ~640 Mbps event-plane estimate, not §1's 160 Gbps raw-video figure | §1/§3 |

**Operational expenditure (recurring, not sized here)**

| Item | Basis |
|---|---|
| Hardware maintenance/replacement | Edge units are physically exposed (§5); expect a real device-failure/replacement rate, not zero |
| Network bandwidth | Ongoing regional/central link costs at §3's traffic estimate |
| Power/cooling for edge and central compute | Not sized — depends on actual site selection |
| Software licensing/support contracts | Depends on which components are self-hosted OSS vs. vendor-supported |
| Security operations (monitoring, patching, incident response) | Ongoing, not a one-time cost |

These are magnitude estimates for a planning conversation, not a
procurement-ready budget — an actual cost model needs real department
camera counts, existing NETRAM infrastructure reuse potential, and vendor
GPU/support pricing at time of procurement, none of which are available to
size precisely during this hackathon submission.
