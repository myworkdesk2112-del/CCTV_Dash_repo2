# Sentinel — Organizer Briefing: Planning, Architecture, and Why It's Better Than What Gujarat Already Runs

Generated 2026-09-05 in response to organizer questions (relayed via email/
conversation) about scalability, DB/watchlist handling, and how Sentinel
compares to Gujarat's existing CCTV infrastructure. Synthesized from
`STRATEGY.md`, `HLD.md`, `SCALABILITY.md`, and `RESEARCH_EXISTING_SYSTEMS.md`
— nothing here is invented fresh; see those files for the underlying detail
and citations. See `EMAIL_DRAFT.md` for a condensed, send-ready version.

---

## 1. What Sentinel Is

Sentinel is **not** a from-scratch CCTV command platform. Gujarat Police
already operates VISWAS/NETRAM/TRINETRA — publicly reported at 7,000+
cameras, 34 district NETRAM command centres feeding a state-level
TRINETRA ICCC, integrated with VAHAN/SARTHI, with Phase-II reportedly
adding ~10,500 more cameras (figures per Gujarat Home Department public
communications, not independently verified by this team). Pitching a
new platform on top of that would invite (and deserve) the question "what
did you actually invent?"

**Sentinel is an open, vendor-neutral interoperability and intelligence
layer** that sits *above* existing departmental CCTV/VMS infrastructure —
including TRINETRA/NETRAM — registering cameras, normalizing heterogeneous
feeds into one canonical event model, correlating vehicle observations
across cameras and departments, and (as a **design target, not built** —
see `HLD.md` §6's "query, don't copy" principle) connecting those events to
authorized government databases (VAHAN, CCTNS, eGujCop) — **without
requiring any department to replace what they already run.**

**The genuine, defensible contribution** is not detection or ANPR — those
are already shipped commercially in India (Staqu JARVIS, Videonetics,
Vehant, Innefu). It's the **open, explainable vehicle-identity-resolution
layer**: a persistent vehicle entity built from uncertain observations
(plate-OCR confidence + appearance + temporal feasibility + recency), with
an explainable link trail, that degrades gracefully to attribute tracking
the moment a plate can't be read — then upgrades retroactively the instant
any camera along the route reads it.

---

## 2. Architecture

**Model 1 + Model 2 hybrid** (per the hackathon's own rules — combining
suitable elements from two or more reference models is the sanctioned
"hybrid/customized architecture" path, not a fallback):

- **Model 1 (mandatory):** centralized camera registry + GIS mapping,
  health monitoring, bulk/manual/API onboarding, gap-analysis reporting,
  role-based access control — now including department-scoped RBAC (an
  investigator in one department can't see another department's cameras).
- **Model 2:** direct unified viewing (RTSP ingestion, HLS relay for
  browser playback) + AI-powered metadata analytics (ANPR, cross-camera
  vehicle tracking, watchlist alerting) — no middleware VMS replacement.
- **Model 3/4 (federation → central AI platform):** documented as the
  production roadmap, deliberately **not** claimed as built this week. A
  half-built federation bus would be worse than an honest documented path.

**Pipeline:** `RTSP ingest → YOLOv8 vehicle detection → trained plate
localizer (YOLOv11) → PaddleOCR → temporal fusion across frames →
ByteTrack (within-camera) → cross-camera identity resolution (plate-first,
appearance-second) → watchlist/named-anomaly alerts → governed alert
lifecycle`

**Key principle:** centralize *metadata/events/identity/GIS/governance* —
never every raw video frame. The math: 80,000 cameras × ~2 Mbps ≈ 160 Gbps
sustained / ~1.7 PB per day if raw video were centralized — not credible
for anyone. Structured events (plate, timestamp, camera ID, confidence —
~1 KB each) reduce this to ~640 Mbps statewide, a ~250x cut, which is
what makes a real central event plane (Kafka/PostgreSQL) achievable at
full scale.

**Scaling path (same codebase at every stage, not a rebuild):** pilot
(~30 cameras, single node, SQLite, this submission) → district pilot
(PostgreSQL, one edge GPU unit) → regional rollout (Kafka event bus, async
regional→central replication so a regional outage doesn't kill central
watchlist/RBAC) → statewide (all 26 departments, ~80,000 cameras,
horizontally scaled central tier).

**Watchlist handling:** a real DB table (`WatchlistEntry`), mirrored into
an in-memory cache so the hot path (every ANPR read, on every camera)
never hits the DB per lookup. Matches raise an `Alert` through a governed
lifecycle (`new → acknowledged → resolved/dismissed`), with dedup logic so
one lingering vehicle doesn't spam duplicate alerts.

**DB connection handling:** per-request SQLAlchemy sessions (FastAPI
dependency injection), SQLite `check_same_thread=False` for concurrent
camera-worker threads at pilot scale, PostgreSQL primary/replica with
automated failover at production scale, hand-rolled additive schema
migrations (no data loss on upgrade), and a partial-unique DB constraint
preventing a real race condition (two camera threads creating duplicate
identities for one plate) that was found and fixed during development.

---

## 3. Why This Is Better Than What Gujarat Already Runs

Gujarat's existing TRINETRA/NETRAM/VISWAS is a **command-and-control/
viewing platform** — it aggregates feeds and gives operators eyes on
cameras. What it does **not** do (and what Sentinel adds as a layer on
top, not a replacement):

1. **Cross-department vehicle identity resolution** — a plate seen at a
   Police camera, then an unrelated Municipal Corporation camera, then a
   GSRTC camera, gets tied into *one* timestamped, location-wise movement
   history — even across departments that don't share a VMS today. This
   is the specific mandatory test-case capability (§Test Scenario) that a
   viewing-only platform doesn't provide.
2. **ANPR failure ≠ tracking failure** — an unreadable plate doesn't drop
   the vehicle. It's tracked by appearance/colour/type, and the *entire*
   prior anonymous chain resolves to a plate retroactively the moment any
   camera reads it. Verified end-to-end, including against real sandbox
   footage.
3. **Explainability, not a black box** — every cross-camera link carries
   a `link_method` + `link_score` (plate confidence, Re-ID similarity,
   temporal consistency), surfaced to the investigator as "why was this
   vehicle linked?" — a defensible evidentiary trail, not just an AI
   assertion.
4. **Purpose-bound, audited queries by design** — every plate lookup
   carries user/purpose/case_id, logged, with a retention policy modelled
   on real precedent (UK's National ANPR Service default). This is a
   designed-in DPDP obligation, not a checklist afterthought.
5. **Named, measurable anomaly detection** (wrong-way vehicle,
   stopped-in-restricted-zone) built on real per-track motion data already
   being captured — not a generic "AI flagged something" alert.
6. **Vendor-neutral, ONVIF/RTSP-based** — doesn't lock any department into
   one VMS vendor, and doesn't require replacing TRINETRA/NETRAM to adopt
   it.

**In short:** Gujarat already has the eyes (TRINETRA/NETRAM/VISWAS).
Sentinel is the piece that makes those eyes talk to each other across
departments, with an explainable, auditable trail — the capability gap
the mandatory test case is actually built to surface.

---

## 4. Why This Is Deployable in the Real World, Not Just a Demo

- **Real, not synthetic, validation of each pipeline stage:** real YOLOv8
  vehicle detection, a real trained plate localizer, and real PaddleOCR
  have each been run against actual live government sandbox footage
  (not synthetic/composited frames), fixing two real bugs found this way
  (a plate-localization geometry issue, and a two-line-plate
  OCR-matching issue). An earlier captured example (`GJ01RP6128`, 4/5
  samples, confidence 0.81) demonstrated the accept-path once; a fresh
  sampling pass on 2026-09-26 produced a **new, independently reproduced
  real read** — `GJ19BR3000`, 6 of 6 consecutive samples, confidence
  0.917–0.977, visually confirmed against the saved image — after 5
  earlier attempts that day found no legible plate. **Honest status:**
  the pipeline is proven working end to end, twice now, on two different
  vehicles; a given sampling window is not guaranteed to include a close,
  legible plate (sandbox traffic varies by loop position), so a fresh
  read is reconfirmed close to demo time rather than assumed permanent.
  If asked, say plainly that this is a live capability that's been
  demonstrated repeatedly, not a guarantee that any single sampling
  attempt will always succeed.
- **Real-world precedent that this architecture scales:**
  - The **UK's National ANPR Service** consolidated 44 disparate systems
    across 36 police forces and 5 vendors into one central service (BAE
    Systems, live Feb 2019) ([BAE Systems](https://www.baesystems.com/en/cybersecurity/feature/transforming-nationwide-automatic-number-plate-recognition-anpr),
    [NASPLE v2.1, gov.uk](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/936912/NASPLE_Version_2.1_November_2020.pdf))
    — the same district→region→central integration challenge Gujarat's 26
    departments face, proof this is a multi-year national-program
    pattern, not a hackathon guess.
  - Gujarat's own **ICCC/Safe City network** (including Gandhinagar, this
    hackathon's venue) already runs the same city→state→national tiering,
    linked to the national CCTNS criminal database.
  - At the extreme end, hierarchical local→provincial→national camera
    integration is proven to scale to hundreds of millions of cameras
    (China's Skynet/Sharp Eyes —
    [CSET/Georgetown](https://cset.georgetown.edu/article/chinas-sharp-eyes-program-aims-to-surveil-100-of-public-space/),
    [IPVM](https://ipvm.com/reports/sharpeyes)) — cited strictly as an
    architecture-scale precedent, **not** a governance model, since
    Sentinel deliberately builds in the retention limits, audit logging,
    and no-face-recognition safeguards that system lacks.
- **Honest, not overclaimed:** every gap (WHEP low-latency preview,
  road-network routing, cross-frame OCR consensus voting, full
  80k-camera physical ingestion) is documented as a gap, not hidden —
  this is deliberate, because a government/police jury evaluation
  punishes false claims harder than visible gaps.
- **Governance built in from day one:** hashed API keys, RBAC (including
  department scoping), audit logging, retention limits, and a deliberate
  exclusion of face recognition (DPDP risk + NIST-documented demographic
  bias) — all real, running code, not a slide.

---

## Follow-up: formalizing the new precedent citations

The UK-NASPLE and India-ICCC precedents above are already cited in
`RESEARCH_EXISTING_SYSTEMS.md` §5/§6. The China Skynet/Sharp Eyes
precedent is new to this briefing and not yet written into that file —
if it should become part of the permanent submission docs (e.g. cited in
`HLD.md`'s scalability section), add it there as a new numbered section
following that file's existing per-precedent table format, with the
explicit "architecture-scale precedent, not governance model" caveat
preserved.
