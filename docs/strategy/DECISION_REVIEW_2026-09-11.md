# Sentinel — Decision-Quality Review, 11 September 2026

Independent review commissioned against an explicit instruction not to praise the
project, not to treat documentation as proof, not to assume Gujarat lacks a
capability, and not to benchmark against generic hackathon projects.

Evidence labels used throughout:
`[OFFICIAL GOVERNMENT]` `[ACADEMIC PAPER]` `[NEWS]` `[VENDOR CLAIM]`
`[OPEN-SOURCE REPOSITORY]` `[PROJECT CODE]` `[PROJECT TEST]` `[INFERENCE]`

Source material: the VISWAS Phase-II RFP (`2023118171112882.pdf`), the live
`sentinel.db` (12,257 events accumulated from real sandbox footage), the
project's own test suite, and five parallel external research passes.

---

## A. EXECUTIVE VERDICT

**Sentinel is a competent, honest, well-governed engineering submission built on
a research architecture that is eight years old, whose single claimed
differentiator cannot currently be demonstrated on real data.**

Three findings dominate everything else in this report.

**A1 — The core differentiator has no ground truth and is running almost
entirely on the weakest component in the system.** [PROJECT CODE / PROJECT TEST]

Queried directly against `sentinel.db`:

| Measurement | Value |
|---|---|
| Total vehicle events | 12,257 |
| Cameras contributing events | 24 |
| Events carrying **any** plate string | **6** |
| Plates observed at **more than one** camera | **0** |
| Cross-camera links by `appearance_match` | **11,992 (97.8%)** |
| Cross-camera links by `plate_upgrade` | 4 |
| Largest identity, by camera count | **17 cameras** |
| Identities spanning ≥5 cameras | 67 |
| Appearance `link_score` min / mean / max | 0.80 / 0.915 / 1.00 |

The appearance encoder producing 97.8% of those links is a 48-dimensional HSV
histogram plus grayscale template, measured by our own
`calibrate_embedding_threshold.py` at a **41.87% false-positive rate** at the
0.80 threshold [PROJECT TEST]. Independently, the academic literature places
hand-crafted colour features at ~9–12 mAP on VeRi-776 against >90 mAP for modern
transformer Re-ID [ACADEMIC PAPER, §H]. Our own measurement and the published
literature agree.

An identity spanning 17 cameras, built on a signal with a 41.87% false-positive
rate and zero plate corroboration, is not a tracked vehicle. It is an artefact.

**Correction (verified after first draft):** an earlier version of this review
stated that `GJ01RP6128` — the headline result — "is not in the database" and
flagged it as a P0 blocker. **That was wrong, and the claim is withdrawn.** The
plate is backed by a real scan artefact at
`backend/data/anpr_scan/20260905T112430Z/report.json` [PROJECT TEST]: 30 cameras
scanned, 687 vehicle detections, 76 plate localisations, 7 pattern-valid reads —
of which `cam06` produced `GJ01RP6128` at confidence 0.890, 0.874, 0.888 and
0.925, plus the J→U homoglyph variant `GU01RP6128` at 0.851. That is precisely
the five-vote case the consensus logic was documented as being run against. It
is absent from `sentinel.db` only because `scripts/real_anpr_scan.py` is an
**offline** scan that writes to `data/anpr_scan/`, not through the live ingest
path. The headline claim is sound and should be kept.

The six plates that exist *in the live DB* are `cam03 GJ01AB1234` (a synthetic
demo plate), three from `cam21`, `cam06 GJ32B2040` (confidence 0.52), and
`cam07 GJ27ED1763`.

This correction does **not** affect A1's central finding: the offline scan
produced plate reads at a *single* camera, so it still provides **no evidence of
the same plate at two cameras**, and the cross-camera claim remains
unsubstantiated.

**We cannot today demonstrate cross-camera vehicle identity resolution on real
footage even once.**

**A2 — The architecture is published prior art, not an invention.**
[ACADEMIC PAPER]

"Plate-first, appearance-second, spatio-temporally gated, with retroactive
identity upgrade" is **PROVID** (Liu et al., *IEEE TMM* 20(3), 2018) — coarse
appearance filter → plate verification → spatio-temporal refinement, framed as
"coarse-to-fine in feature space, near-to-distant in physical space". The
geo-feasibility gate is Shen et al. (*ICCV* 2017) and the camera-link-model line
from the AI City Challenge (2019–20). Every element is standard practice in
competitive multi-target multi-camera tracking. A jury member with a CV
background will recognise it.

**A3 — Gujarat already does more than our documents assume.** [OFFICIAL
GOVERNMENT / NEWS]

TRINETRA/NETRAM today runs ANPR, RLVD, speed, wrong-way, crowd density,
unattended object, camera tampering, intrusion, behavioural pattern analysis,
e-challan, and — per the CP Vadodara on record — *"ANPR enables vehicle tracking
across jurisdictions"*. VAHAN, SARATHI, Virtual Courts and Cyber Treasury are
integrated **since Phase-I**. 10,000 body-worn cameras and ~19 drone systems are
already federated into the i3C. The RFP's Annexure-G names **Videonetics** as
the incumbent supplying VMS, ANPR, RLVD, e-challan **and a Vehicle Tracking
System**.

Our `ORGANIZER_BRIEFING.md` §3 describes TRINETRA as a "viewing-only platform".
That is contradicted by official sources and would be the single most damaging
sentence in the room.

**What survives all three findings** — and it is real, and it is enough to build
a credible submission on:

1. A CAG of India 2025 performance audit says, officially, that ANPR's failure
   in India is **integration and data flow, not detection** — a 3.8% forwarding
   rate that "defeats the intended purpose of using ANPR cameras" [OFFICIAL
   GOVERNMENT]. That is the problem Sentinel is actually shaped for.
2. **Evidentiary provenance per link** (`link_method` / `link_score` /
   `link_time_gap_s`, OBSERVED vs INFERRED) — no published paper and no product
   datasheet we could find does this. It is a systems/governance contribution,
   not an algorithmic one, and it is the only defensible novelty claim.
3. **§63 Bharatiya Sakshya Adhiniyam evidence certification** — a statutory,
   India-only requirement since 1 July 2024 that no ANPR/VMS vendor markets, and
   that Sentinel is 80% architecturally prepared for and 0% implemented against.

**Verdict:** as submitted today, Sentinel is a strong *governance and
interoperability* submission mis-positioned as an *AI tracking* submission. The
pivot is achievable in the remaining time. The tracking claims are not.

---

## B. WHAT GUJARAT ALREADY HAS

| Capability | Status | Evidence |
|---|---|---|
| 7,078 cameras / 1,192 junctions / 41 cities (Phase-I) | **VERIFIED EXISTING** | RFP Annexure-B [OFFICIAL GOVERNMENT]; DeshGujarat 2023 [NEWS] |
| 34 NETRAM district C&C + TRINETRA state C&C | **VERIFIED EXISTING** | RFP §1.3 [OFFICIAL GOVERNMENT] |
| ~10,500 cameras across Surat + Vadodara + 52 municipalities + 80 inter-state entry/exit | **VERIFIED EXISTING (in rollout)** | DeshGujarat, ANI [NEWS] — **scope caveat: the RFP we hold covers only the 1,853-camera Surat+Vadodara slice** |
| ANPR (>90% standard/HSRP, 75% non-standard, @120 km/h) | **VERIFIED EXISTING** | RFP spec [OFFICIAL GOVERNMENT] |
| RLVD, speed violation, e-challan | **VERIFIED EXISTING** | RFP Annexure-G, Videonetics [OFFICIAL GOVERNMENT] |
| **Vehicle Tracking System** | **VERIFIED EXISTING** | RFP Annexure-G names it explicitly [OFFICIAL GOVERNMENT] |
| Cross-jurisdiction plate-based vehicle tracing | **VERIFIED EXISTING** | CP Vadodara on record [NEWS]; RFP §3.2.4.2(i) cross-junction investigative search [OFFICIAL GOVERNMENT] |
| Wrong-way, crowd density, unattended object, tampering, intrusion, behavioural analytics | **VERIFIED EXISTING** | Official interview [NEWS] |
| VAHAN / SARATHI / Virtual Courts / Cyber Treasury integration | **VERIFIED EXISTING since Phase-I** | RFP §3.1.3; NIC e-Challan [OFFICIAL GOVERNMENT] |
| 10,000 body-worn cameras (1,000 live), ~19 drone systems in i3C | **VERIFIED EXISTING** | PIB [OFFICIAL GOVERNMENT] |
| Outcomes: 6,200+ cases detected, ₹13.99 cr recovered, road accidents −29% | **VERIFIED** | MyGov [OFFICIAL GOVERNMENT] |
| ONVIF Profile S, G **and** T | **MANDATED** for Phase-II | RFP [OFFICIAL GOVERNMENT] |
| GB/T 28181 | **BANNED**; NDAA + cyber-security certification required | RFP [OFFICIAL GOVERNMENT] |
| **Appearance-based Re-ID when the plate is unreadable** | **NOT FOUND IN PUBLIC EVIDENCE** | Videonetics' own ANPR material claims attribute extraction but makes no cross-camera Re-ID claim [VENDOR CLAIM] |
| **Non-police departments (Health, GSRTC, Panchayat, Municipal) federated into TRINETRA** | **NOT FOUND IN PUBLIC EVIDENCE** — the hackathon's own framing implies not | [NEWS] |
| **Automated (vs operator-driven) trajectory assembly** | **PROBABLE BUT NOT PUBLICLY VERIFIED** | — |

One official anecdote is worth quoting in full because it defines the real gap:
MyGov's own VISWAS success story describes *"NETRAM staff successfully detected
the offender's black Scorpio car and ascertained their escape route"*
[OFFICIAL GOVERNMENT]. The vehicle was identified by **colour and model, by
humans, manually** — the attribute-fallback case, solved by staring at screens.

**Do not tell this jury that Gujarat cannot track vehicles.** Tell them that when
the plate fails, a human currently does it by eye, and that is what is slow.

---

## C. THE REAL PROBLEM

From the organisers' own framing [NEWS, *Open The Magazine*]:

> "Gujarat has the eyes. The hackathon must build the brain."
>
> "Different departments use different vendors, networks, software and
> video-management systems. One camera may spot a suspicious vehicle, another
> may record it five kilometres away, but the systems may struggle to connect
> those sightings quickly."
>
> "The winning solution must make these technological islands communicate
> without demanding that Gujarat replace every camera or rebuild its
> surveillance infrastructure from scratch."

Corroborated independently by the **CAG of India 2025 performance audit**
[OFFICIAL GOVERNMENT], which found ANPR cameras usable for only five violation
types and unusable for fitness/permit/PUC/insurance/tax violations *"due to the
lack of integration of ITMS software of ANPR cameras with Vahan 4.0"*, with a
**3.8% forwarding rate** that "defeats the intended purpose of using ANPR
cameras", and Delhi e-challan data showing "data inconsistencies, deficient
input control and lack of data integrity" — 1,65,861 challans worth ₹58.02 crore
never forwarded to court.

And by **CAG Report No. 4 of 2018** on Delhi Police [OFFICIAL GOVERNMENT]:
functioning cameras *"abysmally low"*, 31–44% defunct, ₹42.94 crore on an
incomplete project.

**The problem is not detection. It is integration, data flow, camera health, and
the evidentiary usability of what gets detected.** Every one of those is a
software/governance problem, and every one of them is something Sentinel is
better positioned to address than to address vehicle Re-ID.

---

## D. EXACT HACKATHON REQUIREMENTS

Per `docs/hackathon/HACKATHON_DETAILS.md`:

| # | Requirement | Mandatory? |
|---|---|---|
| Model 1 | Camera registry + GIS mapping + health monitoring + gap analysis across 26 departments | **Yes** |
| Model 2 | Unified viewing platform — feed aggregation, multi-camera grid, search, analytics | Yes (chosen) |
| Model 3 | VMS federation / interoperability between independent systems | Optional |
| — | Working prototype, demo video, technical proposal, presentation | **Yes** |
| — | Deadline 15 Sep 2026; Grand Finale 22–23 Sep 2026 | — |

Note what is **not** asked for: state-of-the-art re-identification accuracy,
novel ML research, or 80,000-camera throughput at submission. The rubric rewards
interoperability, coverage, and demonstrable working software.

---

## E. WHAT SENTINEL ACTUALLY IMPLEMENTED

Classification: **A** = fully working, verified on real data · **B** = working,
verified only on synthetic/mocked input · **C** = implemented, unverified ·
**D** = partially implemented · **E** = stub with honest no-op · **F** = claimed
in docs, absent from code.

### Model 1 — Registry / GIS / Health / Gap analysis

| Item | Class | Evidence |
|---|---|---|
| `CameraRegistry` model, onboarding, audit trail | **A** | 30 cameras onboarded in `sentinel.db` [PROJECT CODE] |
| GIS map + coverage-radius layer | **A** | frontend verified running [PROJECT CODE] |
| Health monitoring from real RTSP worker state (`_sync_camera_health`) | **A** | `main.py:143` — reflects real connection state, not a stub |
| Gap analysis incl. ageing-infrastructure flag | **A** | `routes_cameras.py` gap-analysis |
| GPS coverage | **D** | **22 of 30 cameras have coordinates** [PROJECT CODE] |
| 26-department scope | **D** | schema supports `department`; only sandbox cameras exist |

### Model 2 — Unified viewing + analytics

| Item | Class | Evidence |
|---|---|---|
| RTSP forced-TCP workers, PTS timing, backoff reconnect | **A** | `streaming/manager.py`; run against live sandbox |
| Authenticated HLS proxy, credentials never leaked to non-admin | **A** | `routes_cameras.py::_merged_camera_view` |
| Multi-camera grid | **A** | verified in browser |
| YOLOv8 vehicle detection | **A** | 12,257 real events produced |
| ByteTrack within-camera tracking | **A** | via ultralytics, `persist=True` per camera |
| **ONVIF WS-Discovery + GetStreamUri** | **B** | `streaming/onvif_discovery.py`; **14 tests against mocked SOAP only — no ONVIF device was reachable from this environment** [PROJECT TEST] |
| Plate localisation (YOLOv11 ONNX) | **A** | localises correctly even where OCR then fails |
| PaddleOCR plate reading | **D** | **6 plate strings from 12,257 events.** `cam01`: 0 reads from 62 attempts |
| `PLATE_PATTERN` validation gate | **A** | rejects non-plate OCR output |
| Position-weighted `consensus_plate()` | **C** | unit-tested; a known unmitigated case (contamination from a mis-associated track) is documented in a landed test, not fixed |
| Low-confidence suppression (`PLATE_MIN_CONFIDENCE`) | **A** | working — and is *why* only 6 plates exist |
| Appearance encoder (`ColorHistogramEncoder`, 48-dim HSV) | **A** (runs) / **F** (as a Re-ID capability) | 41.87% FPR measured [PROJECT TEST] |
| Cross-camera identity resolution | **C** | 11,992 links produced; **zero validated against ground truth** |
| Geo-feasibility (haversine) gate | **C** | implemented; cannot be shown to have prevented a real error |
| `link_method`/`link_score`/`link_time_gap_s` provenance | **A** | persisted at decision time on all 11,996 links |
| OBSERVED vs INFERRED segment typing | **A** | surfaced in the UI |
| Watchlist + governed alert lifecycle (`ALERT_TRANSITIONS`) | **A** | 6 tests |
| RBAC, department scoping, SHA-256 hashed API keys | **A** | |
| Purpose-bound audited queries (min 8 chars) | **A** | |
| DPDP retention purge **including crop files on disk** | **A** | fixed this session, 4 tests |
| Rate limiting | **A** | 5 tests |
| Named anomalies (wrong-way, stopped-in-zone) | **C** — and **duplicates an existing VISWAS capability** | `analytics/anomaly.py` |
| Make/model classification | **E** | `StubMakeModelClassifier`, honestly declared |

### Model 3 — Federation

| Item | Class |
|---|---|
| `VMSAdapter` Protocol + `NormalizedEvent` schema | **A** |
| Two real independently-formatted sources (Sentinel + NYC Open Data) | **A** |
| Polled `FederatedEvent` ingest with idempotent dedup | **A** |
| Plate-window correlation across sources | **B** — correlation logic tested; **no real second Gujarat VMS exists to federate against** |
| Federation PDF report | **A** |

### Cross-cutting

- **100/100 backend tests pass** [PROJECT TEST]. This is real and worth stating.
- **No load testing of any kind has been performed.** The 250× figure in
  `SCALABILITY.md` is arithmetic (160,000 ÷ 640 Mbps), not a measurement.
- **No demo video is finished.** This remains the P0 submission blocker.

---

## F. COMPARISON MATRIX — asked vs existing vs Sentinel

| Requirement | Gujarat today | Sentinel | Net |
|---|---|---|---|
| Camera registry across departments | Police-owned only; others not federated (unverified) | Full registry + onboarding + audit | **Additive** |
| GIS mapping | Yes (TRINETRA) | Yes + coverage radius | Parity |
| **Camera health monitoring** | CAG: 31–44% defunct elsewhere; Gujarat unknown | Real per-worker health + ageing flag | **Additive, under-sold** |
| **Gap analysis** | Not evidenced | Yes | **Additive** |
| Unified multi-camera viewing | Yes (NETRAM/TRINETRA) | Yes | Parity — do not claim |
| ANPR | Yes, >90% spec | 6 plates / 12,257 events | **We are far behind** |
| Cross-jurisdiction plate tracing | **Yes** | Yes, untested | **Parity at best** |
| Wrong-way / crowd / tamper analytics | **Yes** | Wrong-way only | **Behind — stop claiming** |
| VAHAN/SARATHI integration | **Live since Phase-I** | Design target | **Behind — reframe** |
| Appearance fallback when plate unreadable | Manual, by humans | Automated, 41.87% FPR | **Ambiguous: automated but unreliable** |
| **Per-link explainability (method/score/gap)** | Not evidenced anywhere | Yes, persisted | **Genuine gap filled** |
| **OBSERVED vs INFERRED typing** | Not evidenced anywhere | Yes | **Genuine gap filled** |
| **Purpose-bound audited query** | Not evidenced | Mandatory parameter | **Additive** |
| **Retention enforced in code** | Policy-level | Enforced, incl. files on disk | **Additive** |
| VMS federation | Vendor-internal | Open normalised schema | Additive *concept*, commodity *feature* |
| **§63 BSA evidence certificate** | Not evidenced | **None** | **Open ground, unoccupied by anyone** |
| ONVIF S/G/T | Mandated | S-class discovery only, mocked-tested | **Partial** |

---

## G. COMMODITY VS INNOVATION

**Commodity — stop describing any of these as innovation:**

- ANPR itself (2000s technology; spec'd in the RFP at >90%)
- YOLO detection, ByteTrack tracking (2021; and see §L, it is AGPL)
- Plate-first + appearance-second fusion (**PROVID, 2018**)
- Spatio-temporal path plausibility (**Shen et al., ICCV 2017**)
- Camera-transition-time pruning (AI City Challenge, 2019–20)
- Retroactive identity upgrade (PROVID, 2018)
- Cross-camera appearance search (BriefCam, Avigilon, Dahua AcuPick, Hikvision, Videonetics)
- VMS federation (**Genetec Security Center Federation**, **Milestone Federated Architecture + Interconnect** — both shipping for years, at city scale)
- Fuzzy/homoglyph plate matching with probable-vs-confirmed reads (**Genetec AutoVu Fuzzy Matching**, explicitly)
- Vehicles-seen-together / convoy analysis (**Motorola Vigilant "associate analysis"**)
- Attribute search by colour/type/partial plate (Hikvision 15-attribute search)
- Vehicle route-history reconstruction (Avigilon: "route or last-known location"; Staqu JARVIS: "route history across multiple gates and zones")

**Genuinely differentiated — and this is the complete list:**

1. **Per-link evidentiary provenance.** `link_method` + `link_score` +
   `link_time_gap_s` persisted *at decision time* (necessarily, because the
   identity's embedding is later overwritten and the decision becomes
   unreconstructable), surfaced to an investigator. No academic paper found. No
   vendor datasheet found. *State it as "we could not find a product that
   publishes this", never "no product does this"* — competitor internals are
   unpublished.
2. **Formal OBSERVED vs INFERRED typing of the record itself.** Competitors
   score matches; none we could verify *types the record* so that the UI
   refuses to render an inference as a fact.
3. **Geo-temporal feasibility as a hard eliminator**, with the explicit rule
   that it never overrides a confirmed plate read.
4. **Open, inspectable, vendor-neutral matching logic.** Zero research novelty;
   real procurement value in a vendor-locked estate.
5. **Purpose + case-ID as a mandatory query parameter**, with retention enforced
   in code rather than policy.

Note what all five have in common: **none of them is a computer-vision
contribution.** They are systems, governance, and evidentiary contributions.
That is what this project is actually good at, and the pitch should say so.

---

## H. ACADEMIC RESEARCH EVIDENCE

| Finding | Source | Implication |
|---|---|---|
| Progressive plate+appearance+spatiotemporal Re-ID | **PROVID**, Liu et al., IEEE TMM 20(3):645–658, 2018 [ACADEMIC PAPER] | Sentinel's pipeline, published 8 years ago |
| Visual-spatio-temporal path plausibility via chain-MRF + Path-LSTM | Shen et al., **ICCV 2017** [ACADEMIC PAPER] | Our geo-gate, formalised and stronger |
| ST cues justified because "vehicles follow traffic rules, speed limits, routes and lanes" | **DFR-ST**, Pattern Recognition, 2022 [ACADEMIC PAPER] | Academic backing for the gate's *premise* |
| Camera link model = learned transition-time distributions | AI City / arXiv 2008.09785, 2020 [ACADEMIC PAPER] | The mature form of our single global speed bound |
| MTMC benchmark: 40 cameras, 10 intersections, IDF1 metric; top entries ~85% IDF1 | **CityFlow**, CVPR 2019 [ACADEMIC PAPER] | The benchmark we are not evaluated on |
| Hand-crafted LOMO **9.64 mAP**, BOW-CN **12.20 mAP** vs TransReID/CLIP-ReID **>90 mAP** on VeRi-776 | [ACADEMIC PAPER] | **Our 48-dim HSV encoder is weaker than BOW-CN** — a 7–8× gap to SOTA |
| SOTA mAP drops substantially for vehicle types unseen in training | Generalization Limits in Vehicle Re-ID [ACADEMIC PAPER] | VeRi/CityFlow numbers do **not** transfer to auto-rickshaws, e-rickshaws, locally-bodied commercials |
| ByteTrack MOT17: MOTA 80.3 / IDF1 77.3 / HOTA 63.1 (vs DeepSORT 60.3/61.2/48.8) | [ACADEMIC PAPER] | ByteTrack is a **defensible** choice; near-linear road motion suits it |
| All named trackers are **single-camera**; Kalman+IoU is meaningless across non-overlapping views | [ACADEMIC PAPER] | Using ByteTrack contributes **nothing** to cross-camera capability |
| ANPR for Indian conditions, single + double-line plates: **~82%** | ResearchGate [ACADEMIC PAPER] | The honest comparator |
| Indian commercial-truck LPR, YOLOv7+PARSeq: **95.82%** — but a *weighbridge*, close-range, near-frontal | arXiv 2211.13194 [ACADEMIC PAPER] | **Must not** be cited as a junction-CCTV expectation |
| Indian truck plates frequently two/three-line → "major visual misalignment issues" for transformer OCR | same [ACADEMIC PAPER] | Our line-joining fix is India-specific engineering |
| Character height **≥20 px**; plate width **≥120 px** (100–150 px preferred); camera angle ≤45° | Eocortex, Bosch, Axis, Plate Recognizer [VENDOR CLAIM, convergent across four vendors] | **Converts our cam01 failure into a provable diagnosis** |
| Explainable Re-ID work exists but is **model interpretability** (attention maps), not evidentiary provenance | ICCV 2021 AMD and successors [ACADEMIC PAPER] | **No published work on per-link evidentiary provenance for policing was found** |

**The most actionable academic finding in this report:** `cam01` produced 0 OCR
reads from 62 correctly-localised plates because the plate patch is ~25×16 px,
against a convergent four-vendor requirement of ≥120×20 px. That is not "our OCR
is bad". That is **"this camera is geometrically incapable of ANPR, and we can
prove it, and we can tell the department which of their cameras are"**.

---

## I. WORLDWIDE POLICE DEPLOYMENTS

| Finding | Source | Type |
|---|---|---|
| ANPR usable for only 5 violation types; unusable for fitness/permit/PUC/insurance/tax *"due to the lack of integration of ITMS software of ANPR cameras with Vahan 4.0"*; **3.8% forwarding rate** "defeats the intended purpose"; Delhi 1,65,861 challans (₹58.02 cr) never forwarded to court, with "data inconsistencies, deficient input control and lack of data integrity" | **CAG of India, 2025 performance audit** | **[OFFICIAL GOVERNMENT]** |
| Functioning cameras "abysmally low", 31–44% defunct, ₹42.94 cr incomplete project | **CAG Report No. 4 of 2018**, Delhi Police | [OFFICIAL GOVERNMENT] |
| Randomised trial: **37% / 35% misread rates** | Vallejo PD ALPR study | [ACADEMIC PAPER] |
| **$1.9M settlement** for a wrongful ALPR-triggered stop (family held at gunpoint on a stolen-motorcycle hit against a car) | Aurora, Colorado | [NEWS/LEGAL] |
| LAPD held 320 million ALPR images with **no ALPR-specific policy** | California State Auditor 2019-118 | [OFFICIAL GOVERNMENT] |
| *"Anyone with a police email could use the system without having to explain why"* | New Zealand ANPR review | [OFFICIAL GOVERNMENT] |
| Documented Flock abuses were **recorded in the free-text reason field** — purpose capture is forensic, not preventive | US reporting | [NEWS] |
| 12-month retention, ~20 billion records, **published quarterly compliance dashboard** | UK National ANPR Service | [OFFICIAL GOVERNMENT] |
| Regulator criticism targeted **audit and logging**, not the AI | UK Biometrics & Surveillance Camera Commissioner | [OFFICIAL GOVERNMENT] |
| Singapore / Hong Kong ANPR governance frameworks | **NOT FOUND IN PUBLIC EVIDENCE** | — |

**Two lessons that should change what we build:**

1. Every documented ANPR scandal worldwide is a **governance** failure —
   unexplained access, unbounded retention, no policy, wrongful stops from
   unverified hits — not a detection failure. Our governance layer is therefore
   aimed at the *actual* historical failure mode.
2. **Free-text purpose capture does not prevent abuse** — Flock's abuses were
   dutifully typed into the reason box. Our purpose-bound query is a forensic
   control, and we should say so honestly rather than present it as prevention.
   The UK's *published quarterly compliance dashboard* is the control that
   actually bites, and it is cheap for us to copy.

---

## J. INDIAN COMPETITORS

| Vendor | What they ship | Threat to our claims |
|---|---|---|
| **Videonetics** (the Gujarat incumbent, RFP Annexure-G) | 3rd-gen VMS, ANPR, RLVD, Vehicle Tracking System, e-challan. Vadodara: 550+ cameras, ANPR at 15 junctions, non-standard plate detection, "detailed reports on vehicle movements". Claims an attribute search engine that "tracks persons across multiple cameras" [VENDOR CLAIM] | **Severe.** They are already inside the building. **Notable opening:** cross-camera *person* tracking is claimed; cross-camera *vehicle appearance* Re-ID is **not** explicitly claimed, and no explainability claim appears anywhere |
| **Vehant** (VIDES/VehiScan) | Indian-optimised OCR, stolen/hotlist detection, full violation suite, e-challan. Delhi Police 535 ANPR units, Gurugram, Patna, Noida, Bengaluru [VENDOR CLAIM] | Plate-only; no appearance Re-ID claim found |
| **Staqu (JARVIS)** | 11 state police forces; Gurugram fake-plate detection with live RTO cross-check; **"tracks vehicle route history across multiple gates and zones"**, anomaly flagging [VENDOR CLAIM] | **The closest Indian analogue to our movement-history pitch.** Context appears to be gate/estate access rather than open road networks |
| CP Plus/Prama, Matrix, Sparsh | STQC-certified camera OEMs | Procurement gate, not an analytics competitor |
| L&T Smart World, NEC India, Honeywell, Allied Digital | ICCC systems integrators | They assemble; they do not differentiate on Re-ID |

---

## K. GLOBAL COMPETITORS

| Vendor | Feature | Which Sentinel claim it rebuts |
|---|---|---|
| **Genetec Security Center Federation™** | "Joins multiple independent Security Center systems into a single virtual system", "hundreds or thousands of remote systems for city-wide surveillance", granular per-camera sharing and per-operator lookback limits [VENDOR CLAIM] | **Model 3 federation, exactly. Shipping for years.** |
| **Genetec AutoVu Fuzzy Matching** | "Even when a plate may be misread, operators are notified of potential matches"; adjustable tolerance to "limit the number of **probable reads**, relying on **complete reads** instead"; matches similar/misread characters. MLC engine claims 70% FP reduction [VENDOR CLAIM] | **Our homoglyph correction + confidence gate + probable-vs-confirmed distinction** |
| **Milestone Federated Architecture / Interconnect** | Parent-child hierarchy, unlimited federated sites, dedicated driver for fragmented remote installs [VENDOR CLAIM] | Model 3 again |
| **BriefCam Appearance Similarity** | DNN feature vectors to "instantly locate vehicles by searching for similar looking objects", multi-camera, filtered by colour/size/speed/path/dwell. Marketed explicitly as ***"A Face and License Plate Recognition Alternative"*** [VENDOR CLAIM] | **Our "ANPR failure ≠ tracking failure" core message, verbatim, as a product tagline** |
| **Avigilon / Motorola Appearance Search** | Search by description, photo, or example-in-video; "seamlessly transitioning from one site to the next"; reveals "a vehicle or individual's route or last-known location"; compiles "a powerful narrative of events" [VENDOR CLAIM] | Movement-history reconstruction + evidence packaging |
| **Motorola Vigilant VehicleManager** | Historical sightings; **common plate analysis**; **associate analysis** — "identify vehicles who have been seen together… verify a potential accomplice and getaway car" [VENDOR CLAIM] | **Pre-empts the convoy-detection idea before we build it** |
| **Plate Recognizer / ParkPow** | Explicitly optimised for **India** among 90+ countries; "dark, blurry, low-res images, tough angles"; plate + type + make/model + colour; fully on-prem on Jetson/RPi; ~$50–250/month [VENDOR CLAIM] | **"Why did you hand-build an OCR path instead of evaluating this?"** — expect this question |
| Hikvision Attribute Search (15 categories) / Dahua AcuPick 2.0 | Click-to-find-similar vehicles in camera firmware [VENDOR CLAIM] | Appearance similarity has commoditised to mid-market firmware. (Both PPO/STQC-barred from Indian government tenders — a credibility reference, not a bid rival) |
| Verkada ALPR | Hotlist, movement patterns, cross-camera context, CJIS-compliant evidence [VENDOR CLAIM] | Evidence workflow |

**Honest limit:** we could **not** verify whether BriefCam, Avigilon or Genetec
expose a *link-level reason* or an *observed-vs-inferred* distinction in their
UI. Their internals are unpublished. Say "not found in public documentation",
never "does not exist".

---

## L. OPEN-SOURCE AND LICENSING ANALYSIS

**The problem, precisely:** Sentinel runs **two AGPL-3.0 components in the
inference path** — `ultralytics` (detector + ByteTrack wrapper) and the
morsetechlab YOLOv11 plate localiser (AGPL by inheritance). AGPL §13 is
triggered by **network interaction**, not distribution. A FastAPI backend
serving detections to officers over HTTP is the paradigm §13 case. Ultralytics
states its own position without ambiguity [VENDOR CLAIM — but it is the
licensor's own interpretation, which is the one that matters]:

> "An Enterprise License is required if you want to use Ultralytics YOLO without
> open-sourcing your entire project… compliance means publicly releasing the
> complete corresponding source code for the entire derivative work."

| Component | Licence | Verdict |
|---|---|---|
| ultralytics (YOLOv8/v11) | **AGPL-3.0** | **Replace** |
| morsetechlab YOLOv11 plate ONNX | **AGPL-3.0** | **Replace** |
| BoxMOT | AGPL-3.0 | Avoid |
| OpenALPR | AGPL + proprietary, last stable **2.5.103 (Mar 2018)** | Abandoned — avoid |
| **IISc UVH-26, RT-DETRv2 / DAMO-YOLO variants** | **Apache-2.0** | **Adopt** |
| **fast-alpr / open-image-models** (ankandrew) | **MIT** | **Adopt** |
| **PaddleOCR** | Apache-2.0 | **Keep** |
| **roboflow/trackers** (clean ByteTrack/BoT-SORT) | Apache-2.0 | Adopt (replaces the ultralytics ByteTrack path) |
| FastReID | Apache-2.0, near-dormant | Conditional |

**The single highest-value finding in this section:** IISc's **UVH-26** ships
**RT-DETRv2 and DAMO-YOLO** variants alongside its YOLOv11 variants. The
YOLOv11 weights inherit AGPL; RT-DETRv2 and DAMO-YOLO do not. So **one swap**
simultaneously (a) removes the AGPL exposure, (b) replaces a COCO-generic
detector with one trained on **26,646 real Indian urban-traffic images across 14
Indian vehicle classes**, and (c) gives an *Indian-institution provenance story*
to a Gujarat Police jury.

Combined with fast-alpr/open-image-models (MIT) and PaddleOCR (Apache-2.0), the
**entire inference stack becomes Apache/MIT with zero copyleft.**

**Caveat:** swapping a detector invalidates every accuracy observation made
against the old one. Disclose the path; do not swap silently and keep quoting
old numbers.

---

## M. INDIA-SPECIFIC CHALLENGES

**M1 — ⚠️ ANPR output is not court-usable in India without a §63 certificate,
and Sentinel produces none.** This is a material capability gap that appears in
none of our documents and is the most valuable single finding in this review.

Since **1 July 2024** the Indian Evidence Act 1872 is repealed; electronic
evidence is governed by **§63, Bharatiya Sakshya Adhiniyam 2023** [OFFICIAL
GOVERNMENT — statutory text]. What §63 requires that §65B did not:

- **Dual certification** — §63(4) requires signature by "a person in charge of
  the computer… or the management" **and by an expert**. The Schedule splits
  this into **Part A (custodian)** and **Part B (expert)**.
- **A cryptographic hash of the record**, with the algorithm named, so the court
  can confirm the file was not altered after export. SHA-256 is the practical
  standard.
- **Device identity and a description of the manner in which the record was
  produced.**

What a system must therefore produce:

1. **SHA-256 computed at write time** over the crop, clip, and metadata record —
   stored alongside, never recomputed on export.
2. **Chain-of-custody log** — who accessed/exported, when, under what purpose
   and case ID. *Sentinel's purpose-bound `AuditLog` is already ~80% of this.*
3. **Device and software identification** — camera ID, owning department, and
   **the version of every model that produced the read**. *Sentinel does not
   currently stamp model versions per event.*
4. **A machine-generated production-method statement** — "detector X v1.2 →
   localiser Y → OCR Z → consensus vote, confidence 0.81".
5. **A printable §63 certificate**, Part A pre-filled from system metadata, with
   signature blocks for custodian and expert.

Effort: low (hash at write + version stamping + a `reportlab` export reusing the
existing gap-analysis/federation PDF pattern). Novelty: no commodity ANPR/VMS
vendor markets this. And it is unambiguously India-only.

**M2 — Wrong e-challans from misreads are a documented national problem.**
Reporting attributes the large majority of wrong challans to camera misreads,
citing exactly the confusions **0↔O, 1↔I, 8↔B, 5↔6** [NEWS/INDUSTRY — treat
percentages as unverified]. Delhi booked **16,859 defective-number-plate
violations in 2024, a ~286% rise** [NEWS]. Our homoglyph set targets precisely
the documented confusion pairs and our low-confidence suppression targets
precisely the documented harm. **Say this out loud with these citations** — it
reframes an internal design choice as a response to a named national failure.

**M3 — The pixel budget makes most two-wheeler ANPR physically impossible.**
Under **Rule 50, CMVR 1989**, two-wheeler rear plates are **200 mm × 100 mm**
[OFFICIAL GOVERNMENT]. A 1080p camera at ~60° HFOV covers ≈23 m at 20 m range →
≈83 px/m → a 200 mm plate spans **≈17 px** [INFERENCE, assumptions stated],
against a ≥100–150 px requirement. *Most wide-area placements cannot do
two-wheeler ANPR regardless of model quality.* This explains our own 0/62 result
better than any claim about OCR weakness.

**M4 — DPDP §17 wording in our HLD is slightly wrong.** The law-enforcement
exemption is **not self-executing**: §17(2)(a) operates via **notification in
the Official Gazette**, and security-safeguard expectations survive exemption.
Tighten to: *exemption is conditional on notification, so designing to the
substantive obligations is the prudent default.*

**M5 — Power and connectivity are an expected operating condition, officially.**
The Phase-II RFP makes the SI responsible for UPS, stabilisers and surge
protection, and treats link downtime as SLA-excusable with ISP documentary proof
[OFFICIAL GOVERNMENT, RFP §3.2.8.3, §4.1, §4.4].

**M6 — Non-standard plates persist despite HSRP**, which is why the RFP itself
sets **75% for non-standard fonts vs >90% for standard/HSRP** [OFFICIAL
GOVERNMENT].

**M7 — From 1 April 2026, no CCTV camera non-conforming to MeitY/STQC/BIS
Essential Requirements may be sold in India.** Device cybersecurity, not
metadata interoperability — relevant to procurement framing.

**M8 — There is no national video-analytics event-interchange standard.**
CCTNS/ICJS integrate criminal-justice *records*, not CCTV/ANPR video metadata.
MeitY/BIS covers *devices*. **A canonical, vendor-neutral vehicle-event schema
is genuinely unoccupied ground**, and ONVIF Profile M is the international
candidate — with S/G/T already mandated by the RFP, the standards-alignment
argument is credible.

---

## N. INNOVATION ASSESSMENT

| Claim we currently make | Honest assessment |
|---|---|
| Cross-camera vehicle identity resolution is our innovation | **No.** PROVID 2018; and ours is unvalidated and runs on a 41.87%-FPR signal |
| "ANPR failure ≠ tracking failure" is our insight | **No.** BriefCam's marketing tagline |
| Spatio-temporal gating is our innovation | **No.** ICCV 2017 |
| VMS federation is our innovation | **No.** Genetec and Milestone, at city scale, for years |
| Homoglyph/fuzzy plate correction is our innovation | **No.** Genetec AutoVu Fuzzy Matching |
| Wrong-way detection is a differentiator | **No.** Already deployed in VISWAS |
| VAHAN/SARATHI integration is our roadmap contribution | **No.** Live in Gujarat since Phase-I |
| 80,000-camera scalability is proven | **No.** Arithmetic only. **Zero load tests exist** |
| **Per-link evidentiary provenance** | **Yes** — not found in literature or datasheets |
| **OBSERVED vs INFERRED record typing** | **Yes** — narrow but real |
| **Purpose-bound, code-enforced retention and audit** | **Partly** — unusual as a *mandatory query parameter* |
| **Open, inspectable matching logic** | **Yes** — procurement value, not research value |
| **Honest degradation as designed behaviour** | **Yes** — and rare |

**Overall innovation grade: C+ as an AI system; B+ as a governance and
interoperability system.** The project's real contribution is that it is
*auditable*. Lead with that.

---

## O. NEW INNOVATION OPPORTUNITIES

1. **§63 BSA evidence certificate export** — hash-at-write, model-version
   stamping, production-method statement, printable Part A/B certificate.
2. **Camera ANPR-suitability scoring** — compute plate-pixel-width against the
   ≥120 px requirement per camera and rate each camera *incapable / marginal /
   capable* for ANPR, with a remediation recommendation (move, re-angle,
   re-lens, replace).
3. **Integration-loss dashboard** — the CAG's 3.8% forwarding rate, made
   visible: detections → validated reads → forwarded → actioned, with the drop
   at each stage attributed.
4. **Published compliance dashboard** — copy the UK NAS quarterly model: query
   counts by purpose, retention compliance, access anomalies.
5. **Canonical vehicle-event interchange schema** — publish `NormalizedEvent` as
   a proposed open standard aligned to ONVIF Profile M, and offer it to the
   department as a deliverable in its own right.
6. **Confidence-tiered investigator workflow** — CONFIRMED (plate) / PROBABLE
   (plate + geo) / LEAD ONLY (appearance), with the UI physically preventing a
   LEAD from being exported as evidence.
7. **Camera-health SLA reporting** against CAG's documented 31–44% defunct-rate
   problem.
8. Dark/low-light and monsoon degradation reporting per camera.
9. Two-wheeler-specific detection path (India-dominant, hardest ANPR case).
10. Departmental data-sharing consent ledger — who may see whose cameras, and
    the record of every cross-department access.

---

## P. RANKED TOP-5 ADDITIONS

| # | Addition | Effort | Novelty | Jury value | Risk |
|---|---|---|---|---|---|
| **1** | **§63 BSA evidence certificate** (hash-at-write + model versions + PDF) | **Low** (1–2 days) | **High** — no vendor markets it | **Very high** — statutory, India-only, demoable in 90 seconds | Low |
| **2** | **Camera ANPR-suitability scoring** with the pixel-budget arithmetic | **Low** (1 day) | Medium-high | **Very high** — turns our worst result into a department deliverable | Low |
| **3** | **Confidence-tiered workflow** (CONFIRMED / PROBABLE / LEAD ONLY) enforced in the UI | **Low** (1 day) | Medium | **High** — directly answers the Aurora $1.9M wrongful-stop failure mode | Low |
| **4** | **Integration-loss dashboard** (CAG 3.8% framing) | Medium (2 days) | Medium | **High** — quotes India's supreme audit institution back at the jury | Medium (needs a credible funnel definition) |
| **5** | **Licence-safe stack swap** (UVH-26 RT-DETRv2 + fast-alpr + PaddleOCR) | Medium-high (3+ days, needs re-validation) | Low technically, **high procurement-wise** | High | **Medium-high — invalidates existing measurements** |

**If time permits only one: #1.** If two: #1 and #2. **#5 should be *announced*
rather than *executed*** before the deadline — disclosing the AGPL problem and
the fix path is worth more than a rushed, unvalidated swap.

---

## Q. WHAT NOT TO BUILD

- **Do not build convoy/association detection** — Motorola Vigilant already
  ships "associate analysis".
- **Do not build more named anomalies** — VISWAS already has wrong-way, crowd,
  tampering, intrusion, behavioural.
- **Do not build a better appearance encoder** — you cannot close a 7–8× mAP gap
  in four days, and a better encoder without ground truth is still unvalidated.
- **Do not build face recognition** — explicitly OUT in STRATEGY.md, and it
  raises a legal surface we cannot defend.
- **Do not build VAHAN/SARATHI integration** — live since Phase-I. Federate to
  it; do not re-implement it.
- **Do not deploy Kafka, MediaMTX, Redis, or PostgreSQL** — deferred in
  SCALABILITY.md, and infrastructure is not what is being scored.
- **Do not attempt a load test** to back the 80,000-camera claim. Either drop
  the claim or state it as arithmetic. A shallow load test is worse than none.
- **Do not chase the 26-department registry breadth** with fabricated
  departmental data.

---

## R. MANDATORY GAPS (submission blockers)

| # | Gap | Severity | State |
|---|---|---|---|
| R1 | **Demo video not finished** (own-feed; government-feed externally blocked) | **P0** | Unresolved — this alone can fail the submission |
| R2 | `ORGANIZER_BRIEFING.md` §3 calls TRINETRA "viewing-only" — **contradicted by official sources** | **P0** | Unresolved |
| R3 | ~~Headline plate `GJ01RP6128` does not exist in the database~~ — **WITHDRAWN.** Verified real in `data/anpr_scan/20260905T112430Z/report.json` (4 exact reads 0.874–0.925 + 1 homoglyph variant 0.851). Absent from `sentinel.db` only because the scan is offline | ~~P0~~ **Not a defect** — reopened then re-closed 2026-09-26, see note | Closed at the time. **Reopened 2026-09-26:** the `20260905T112430Z` artefact was gone from this environment, and 5 fresh real scans against the live sandbox that day (985+1,057+485 vehicle detections across runs) produced 0 pattern-valid reads, not reproducing `GJ01RP6128`. **Re-closed the same day:** a 6th scan (all 30 cameras, 40s each) produced a new, independently-verified real read — `GJ19BR3000`, `cam06`, 6/6 samples, confidence 0.917–0.977, visually confirmed against the saved crop. Net effect: the specific 2026-09-05 capture doesn't reproduce, but the underlying capability (real, end-to-end ANPR on live sandbox footage) is reconfirmed with a fresh example. See `HLD.md` §3 and `docs/hackathon/REQUIREMENTS_COVERAGE.md`'s "ANPR-based metadata generation" row for the full 6-run sequence. Use `GJ19BR3000`, not `GJ01RP6128`, as the current citable example. |
| R4 | "~10,500 more cameras" — now citable (DeshGujarat/ANI) **but must carry the scope caveat** (Surat + Vadodara + 52 municipalities + 80 entry/exit, not the 1,853-camera RFP slice) | P1 | Fix pending |
| R5 | VAHAN/SARATHI presented as roadmap; **live since Phase-I** | P1 | Fix pending |
| R6 | Wrong-way anomaly presented as differentiator; **duplicates VISWAS** | P1 | Fix pending |
| R7 | **AGPL-3.0 in the inference path**, undisclosed in organiser-facing material | P1 | HLD discloses; briefing does not |
| R8 | **ONVIF S/G/T mandate not referenced** in Model 2 docs | P1 | Fix pending |
| R9 | No §63 BSA evidence path | P1 | See §P#1 |
| R10 | 80,000-camera scalability stated without load testing | P1 | Label as arithmetic |
| R11 | DPDP §17 exemption described as self-executing | P2 | One-sentence fix |
| R12 | 8 of 30 cameras lack GPS | P2 | Data, not code |

---

## S. REASONS TO LOSE / REASONS TO WIN

**Reasons to lose**

1. A CV-literate juror names PROVID or BriefCam and the "innovation" claim
   collapses in one question.
2. A juror asks to see cross-camera tracking on real footage and **we cannot do
   it** — 0 plates repeat across cameras.
3. A juror from the department says "we already have ANPR, VTS and wrong-way
   detection", and our briefing has just called their system "viewing-only".
4. A procurement-literate juror asks about AGPL and we have no answer.
5. No demo video.
6. "Why not just buy Plate Recognizer for $250/month?"

**Reasons to win**

1. We quote **CAG 2025** back to the jury: the national problem is integration
   and a 3.8% forwarding rate, not detection — and we built for that.
2. We are the only entrant likely to produce a **§63 BSA-compliant evidence
   certificate**.
3. We can tell a department **which of their cameras physically cannot do ANPR
   and why**, with vendor-convergent thresholds and arithmetic.
4. Our system **refuses to present an inference as a fact**, with the per-link
   reason persisted and auditable — the control that every documented ANPR
   scandal worldwide was missing.
5. **100/100 tests pass**, the stack is open and inspectable, and every stub
   honestly declares itself.
6. We disclosed our own AGPL exposure and the licence-safe Indian-institution
   replacement path — procurement literacy a jury is actively screening for.
7. We measured our own weakest component at 41.87% FPR and **published it**.

---

## T. FINAL RECOMMENDED ARCHITECTURE

No structural change. Four additions, all on existing seams:

```
RTSP/ONVIF ingest  →  detector  →  plate localiser  →  OCR  →  PLATE_PATTERN gate
                                                               │
                                                     consensus_plate()
                                                               │
                            ┌──────────────────────────────────┤
                            │                                  │
                   confidence tiering                   identity resolution
             CONFIRMED / PROBABLE / LEAD ONLY      (plate-first, geo-gated,
                     [NEW — §P#3]                   appearance = LEAD ONLY)
                            │                                  │
                            └──────────────┬───────────────────┘
                                           │
                              evidence record + SHA-256 at write
                                  + model-version stamp
                                        [NEW — §P#1]
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
          §63 BSA certificate     integration-loss          camera ANPR-
              export (PDF)          dashboard              suitability score
              [NEW — §P#1]         [NEW — §P#4]              [NEW — §P#2]
```

Everything else — registry, GIS, health, federation, RBAC, audit, retention —
stays as built.

---

## U. UI WORKFLOW

The workflow the jury should be walked through:

1. **Map** — cameras by department, health state, coverage radius, and (new)
   ANPR-suitability badge.
2. **Gap analysis** — uncovered areas, ageing hardware, cameras incapable of
   ANPR, with remediation.
3. **Search** — purpose + case ID **required before any result renders**. Show
   the jury the form refusing to proceed.
4. **Identity view** — timeline of sightings, each labelled **OBSERVED** or
   **INFERRED**, each link showing method, score and time gap.
5. **Tier enforcement** — a LEAD ONLY sighting is visually distinct and the
   "export as evidence" action is **disabled**, with the reason stated.
6. **Evidence export** — select a CONFIRMED sighting → §63 certificate PDF with
   hash, device, model versions, production method, Part A/B signature blocks.
7. **Audit** — every step above, visible in the audit log, scoped to the caller.
8. **Compliance dashboard** — queries by purpose, retention status, anomalies.

---

## V. JURY DEMO (8 minutes)

| Time | Beat | Why |
|---|---|---|
| 0:00–0:45 | "Gujarat has 7,078 cameras and ANPR that meets spec. CAG 2025 found only **3.8%** of detected violations reach enforcement, because of integration gaps. We did not build another detector." | Establishes we know the incumbent; borrows the supreme audit institution's authority |
| 0:45–2:00 | Map + gap analysis + **camera ANPR-suitability**: "these six cameras physically cannot read a plate — here is the pixel arithmetic and here is what to do about them" | Immediate, concrete department value; nobody else will do this |
| 2:00–3:00 | Purpose-bound search — show it refusing without a case ID | Governance made visible |
| 3:00–4:30 | Identity timeline: OBSERVED vs INFERRED, per-link method/score/gap. **Say plainly**: "this link is appearance-only; our own calibration puts that at a 41.87% false-positive rate, so the system labels it a lead, not evidence, and will not let you export it" | **This is the moment that wins or loses the room.** Volunteering the weakness is the differentiator |
| 4:30–6:00 | §63 BSA certificate export — hash, device, model versions, production method | Statutory, India-only, no vendor ships it |
| 6:00–7:00 | Federation: two independently-formatted sources into one normalised event stream; the schema offered as an open standard | Answers the stated hackathon problem |
| 7:00–8:00 | Honest close: what is proven, what is not, what the licence path is | Credibility |

**Do not demo cross-camera vehicle tracking as a capability.** Demo the
*governance around* cross-camera linking. We can back that; we cannot back the
other.

---

## W. POSITIONING

**Wrong (current):** "An AI system that tracks vehicles across cameras even when
the plate is unreadable."
→ Rebuttable by BriefCam's tagline, PROVID 2018, and our own database.

**Right:** **"The accountability layer for Gujarat's existing CCTV estate."**
→ Gujarat already has the eyes and the detectors. What it does not evidently
have is a layer that makes every cross-camera inference explainable, every query
purpose-bound, every camera's fitness measurable, and every detection
court-usable under §63 BSA.

---

## X. PITCHES

**One line:** *Gujarat has the eyes and the detectors. Sentinel is the layer
that makes what they see explainable, auditable, and admissible in court.*

**30 seconds:** *India's CAG found in 2025 that only 3.8% of ANPR-detected
violations reach enforcement — the failure is integration and evidentiary
usability, not detection. Sentinel is an open, vendor-neutral layer over the
existing estate: it registers and health-scores every camera across departments,
tells you which cameras physically cannot read a plate and why, records the
reason and confidence behind every cross-camera link, refuses to present an
inference as a fact, and exports a §63 Bharatiya Sakshya Adhiniyam evidence
certificate so a detection survives court.*

**2 minutes:** the 30-second version, then — (1) what already exists in VISWAS
and that we do not duplicate it; (2) the CAG finding and the integration-loss
funnel; (3) camera-suitability scoring with the pixel-budget arithmetic;
(4) OBSERVED vs INFERRED and the 41.87% measurement we published about our own
weakest component; (5) the §63 certificate; (6) the open normalised event schema
aligned to ONVIF Profile M, mandated S/G/T already supported; (7) the AGPL
disclosure and the Apache/MIT Indian-institution replacement path; (8) 100/100
tests, every stub honestly declared, nothing claimed that is not wired in.

---

## Y. BUILD PRIORITY (to 15 September)

| Day | Work |
|---|---|
| **Day 1 (P0)** | Fix R2/R3/R5/R6 in the organiser-facing docs. **Finish the demo video.** Nothing else matters until these are done |
| **Day 2** | §P#1 — hash-at-write + model-version stamping + §63 certificate PDF export, with tests |
| **Day 3** | §P#2 camera ANPR-suitability scoring + §P#3 confidence tiering enforced in the UI |
| **Day 4** | §P#4 integration-loss dashboard; R4/R7/R8/R10/R11 doc corrections; AGPL disclosure + swap path into the briefing |
| **Day 5** | Rehearse §V; re-record if needed; full self-review of the diff |

**Not in scope before the deadline:** the licence swap execution, any encoder
improvement, any new anomaly type, any load test.

---

## Z. CLOSING

### If I controlled this project from this moment until judging, I would

stop presenting Sentinel as a vehicle-tracking AI, because the database proves
we cannot demonstrate that claim, and re-position it in a single day as the
accountability and evidentiary layer over Gujarat's existing estate — then spend
the remaining days building the §63 BSA certificate export and the camera
ANPR-suitability score, finishing the demo video, and removing every sentence
that tells this jury their own system is less capable than it is.

### 5 things to KEEP

1. Per-link `link_method` / `link_score` / `link_time_gap_s`, persisted at
   decision time.
2. OBSERVED vs INFERRED record typing.
3. Purpose-bound, audited, case-ID-required queries.
4. The stub/real pattern with honest no-op fallbacks and `/health` reporting
   real class names.
5. The `PLATE_PATTERN` gate and low-confidence suppression — now backed by the
   documented national wrong-challan problem.

### 5 things to CHANGE

1. Delete "viewing-only platform" from `ORGANIZER_BRIEFING.md` §3.
2. Keep the `GJ01RP6128` headline result (verified real) but state that it comes
   from an offline scan artefact, and stop implying it demonstrates *cross-camera*
   tracking — it is a single-camera read.
3. Reframe VAHAN/SARATHI from roadmap to "already live; we federate, not
   duplicate".
4. Relabel the 80,000-camera figure as arithmetic, not proven scale.
5. Reposition appearance links in the UI from "match" to **LEAD ONLY**, with the
   41.87% figure stated.

### 5 things to BUILD AND PROVE

1. §63 BSA evidence certificate export, with a real hash verified end-to-end.
2. Camera ANPR-suitability scoring, run across all 30 onboarded cameras.
3. Confidence tiering enforced in the UI, with export blocked for LEAD ONLY.
4. The integration-loss funnel, computed from real `sentinel.db` counts.
5. The demo video.

### 5 things to STOP

1. Stop claiming cross-camera identity resolution as an innovation.
2. Stop claiming "ANPR failure ≠ tracking failure" as our insight.
3. Stop claiming VMS federation as novel.
4. Stop claiming wrong-way detection as a differentiator.
5. Stop describing anything as proven that has not been measured.

### The single most important message to give the jury

> **"Gujarat already has the cameras and the detectors. What no system here can
> yet do is tell you why it linked two sightings, prove the camera was capable
> of the read, and hand you a certificate that survives court. That is what we
> built — and where we are uncertain, our system says so out loud."**
