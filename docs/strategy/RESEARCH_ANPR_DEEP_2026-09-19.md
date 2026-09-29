# Research: ANPR Deep Dive — Indian Plate Reality, Model Stack, and Analytics Beyond ANPR

Synthesized **2026-09-19** from a focused research pass on ANPR, extended
mid-pass to cover *"additional reliable analytics beyond the mandatory ANPR
requirement"*.

This does not repeat `DECISION_REVIEW_2026-09-11.md` §H (the ≥120 px / ≥20 px
vendor thresholds, Indian ANPR ~82%, the weighbridge 95.82% figure, two/three-
line plate misalignment). It goes after what that pass did not cover: **Indian
plate formats and HSRP**, **the licence-safe model path**, **ground-truth
datasets**, **failure attribution**, and **which non-ANPR analytics are still
open versus already shipped by the incumbent**.

Evidence labels, per `DECISION_REVIEW_2026-09-11.md`:
`[OFFICIAL GOVERNMENT]` `[NEWS]` `[VENDOR CLAIM]` `[ACADEMIC PAPER]`
`[TRADE PRESS]` `[PROJECT CODE]` `[PROJECT TEST]` `[INFERENCE]`
`[UNVERIFIED CLAIM]` `[NOT ESTABLISHED]`

---

## A. EXECUTIVE VERDICT

**A1 — CONFIRMED DEFECT (FIXED same day, 2026-09-19 — see `TASKS.md`):
Sentinel could not read Bharat-series (BH) plates at all.** `[PROJECT TEST]`
The finding and reproduction are kept below as written, because the *way* this
was found matters: nothing was failing. No test broke, no error was logged,
and both the watchlist and search paths reported success. MoRTH notified the BH series on **26 Aug 2021**,
registrations opened **15 Sep 2021** `[NEWS]`. Format is `YYBH####XX` —
**it starts with digits**. Sentinel's `PLATE_PATTERN`
(`[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4}`) requires two leading letters, so
every BH plate fails validation *and* the homoglyph fallback. Reproduced:

```
GJ01AB1234   standard Gujarat       fullmatch=True   via_homoglyph=GJ01AB1234
23BH1234AA   Bharat (BH) series     fullmatch=False  via_homoglyph=None
22BH5678CD   Bharat (BH) series     fullmatch=False  via_homoglyph=None
```

Consequence: a BH-series vehicle is **silently invisible to the entire
evidence chain** — OCR may read it perfectly, validation discards it, the
sighting is logged anonymously, it can never be CONFIRMED, never match a
watchlist, never raise an alert, never be exported as evidence. This is a
correctness bug against a **mandatory** hackathon requirement, not a
nice-to-have. **P1 — fixed 2026-09-19**: `PLATE_PATTERN` is now an alternation
of a state-series and a BH-series component, with the I/O exclusion encoded.
Verified through the real `AnalyticsPipeline`: a misread `Z3BH1Z34AA` recovers
to `23BH1234AA`, persists as CONFIRMED and raises a watchlist alert.

**A2 — HSRP changes the framing of ANPR failure.** India's High Security
Registration Plate is *designed for machine reading*: retro-reflective
sheeting specifically so ANPR reads in low light, plus a laser-etched unique
10-digit code and hot-stamped Ashoka Chakra hologram `[NEWS]`. Where HSRP is
fitted and the camera meets the vendor geometry, a failed read is
**increasingly attributable to the plate, not the pipeline**. That inverts the
usual defensive posture — see §C.

**A3 — The obvious "add more analytics" ideas are all incumbent parity.**
Videonetics — named in the VISWAS Phase-II RFP Annexure-G as the incumbent
`[OFFICIAL GOVERNMENT]` — already ships ANPR, RLVD, over-speeding, stop-line,
**no-helmet**, **triple riding**, driver-on-call, no-seat-belt and wrong-way:
"14 incidents and 8 violation types", 150,000 events/day in Bhopal
`[VENDOR CLAIM]`. Building helmet or triple-riding detection would be
duplicating the incumbent and claiming it as innovation — exactly what
CLAUDE.md §4.5/§28.3 forbids.

**A4 — One genuine analytics gap survives that test.** Nothing found in any
vendor's published capability list performs **plate-failure attribution**:
separating *"this camera cannot read plates"* from *"this vehicle has no
readable plate"*. The second is a ₹5,000 MV Act §177 offence that Delhi is
currently enforcing **by patrolling on foot** `[NEWS]`. Sentinel is unusually
well placed here because it is the only system in this research that already
measures per-camera ANPR fitness — and that measurement is the precondition
for the attribution. See §G3.

---

## B. INDIAN PLATE REALITY

### B1. Formats the pipeline must accept

| Format | Example | Sentinel today | Label |
|---|---|---|---|
| Standard state series | `GJ01AB1234` | ✅ accepted | `[PROJECT TEST]` |
| Delhi 4-part | `DL1CAB1234` | ✅ accepted | `[PROJECT TEST]` |
| Two-wheeler / two-line | `GJ05AV6417` | ✅ accepted (line-joining fix, `anpr.py`) | `[PROJECT TEST]` |
| **Bharat series** | `23BH1234AA`, `25BH0123C` | ✅ accepted **since the 2026-09-19 fix** (was ❌ — see A1) | `[PROJECT TEST]` |

BH format is `YYBH####XX`: `YY` = last two digits of registration year, `BH` =
Bharat, `####` = four digits, `XX` = letters A–Z **excluding I and O** `[NEWS]`.

> **Correction, made while implementing this (2026-09-19).** An earlier draft
> of this document claimed the I/O exclusion was a "free accuracy gain —
> always resolvable toward the digit". That is wrong, and the error is worth
> recording. The trailing group is a *letter* position, so an OCR'd `0` or `1`
> there cannot simply be flipped to `O` or `I` — those letters are illegal in
> BH plates, so there is no safe resolution and the read is genuinely
> unrecoverable. What the exclusion actually buys is the **opposite and
> narrower** benefit, which is still worth having: it stops the homoglyph
> search from *inventing* a plate that could never legally exist. That is
> pinned by `test_homoglyph_search_will_not_invent_an_illegal_bh_plate`.
>
> The real accuracy opportunity is the broader one `_best_pattern_match`'s own
> docstring already confesses — **positional** digit-vs-letter knowledge,
> which applies to both formats. Logged as a separate task in §H, not bundled
> into the bug fix.

### B2. HSRP — what it guarantees, and what it does not

`[NEWS]` throughout; no BIS/IS standard number was located (see §B3).

- 1 mm aluminium, stated as conforming to **AIS 159/2019 or ISO 7591**
- **Laser-etched permanent 10-digit unique identification number**
- **Retro-reflective sheeting with "IND" lettering — explicitly to help ANPR
  read the plate in low light**
- Chromium **Ashoka Chakra hologram**, hot-stamped, anti-counterfeit
- **Non-reusable snap locks** that break on removal attempt
- Third registration sticker on the windscreen (colour-coded by fuel type)

**What this does NOT mean:** HSRP is mandated but **not universally fitted**.
Karnataka reported only ~35.5 lakh of ~2 crore vehicles had HSRP as a deadline
approached `[NEWS]` — under 20%. Any claim that "Indian plates are standardised
and therefore machine-readable" is false in the field and must not be made.

`[NOT ESTABLISHED]` — Gujarat's current HSRP fitment rate. Worth an RTI or an
organizer question; it directly bounds achievable ANPR accuracy statewide.

### B3. Standards gap

`[NOT ESTABLISHED]` — **no BIS/IS standard number for ANPR camera
specification was found.** MoRTH runs the "One Nation One Challan" e-challan
programme and ANPR feeds it `[NEWS]`, but a searchable published technical
standard for the *camera* side (minimum plate pixel width, angle, illumination)
did not surface.

This is strategically interesting rather than a dead end: **the absence of a
published Indian camera-fitness standard is the gap Sentinel's ANPR-readiness
scoring sits in.** The ≥120 px / ≥20 px figures the scorer uses remain a
four-vendor convergent **`[VENDOR CLAIM]`** and must keep being labelled that
way (as `anpr_suitability.thresholds()` already does).

---

## C. FAILURE ATTRIBUTION — THE STRATEGIC INSIGHT

Today the pipeline collapses three very different failures into one
"no plate read" outcome:

| Real cause | Correct owner | Correct action |
|---|---|---|
| Plate too few pixels / bad angle | **Department (optics)** | Re-lens, re-angle, dedicated ANPR camera |
| Plate absent, obscured, tampered, non-HSRP, hand-painted | **Vehicle owner** | MV Act §177 challan, ₹5,000 |
| Plate fine, camera fine, model weak | **Vendor (us)** | Model upgrade |

Sentinel already computes the first bucket (`anpr_suitability.py`, built
2026-09-19). The **second bucket is derivable from data already persisted**
and nothing in the research does it:

> If `plate_localiser` found a region, the region's width **clears** the
> vendor threshold, the camera's measured read rate is otherwise **CAPABLE**,
> and OCR still returned nothing across the whole track —
> **the plate is the problem, not the camera.**

That is a defensible, evidence-labelled, India-specific finding that turns a
pipeline failure into an enforcement output. It requires **no new model**, only
a join across columns the 2026-09-19 work already added
(`plate_region_w_px`, `plate_localiser`, `plate_ocr_attempts`,
`plate_ocr_reads`).

**Wording discipline:** this must ship as `PROBABLE` / an investigative flag
for human confirmation, never as an auto-issued challan. A false "defective
plate" finding is a ₹5,000 accusation against a citizen. `[INFERENCE]`

---

## D. MODEL STACK AND LICENSING

### D1. The AGPL problem, restated with a concrete exit

`[VENDOR CLAIM]` Ultralytics YOLO models are **AGPL-3.0 by default**;
AGPL requires releasing the source of the application built on it, **including
networked services**. Closed-source commercial use needs a paid Ultralytics
licence. This is already flagged in CLAUDE.md §16 and `HLD.md` §10 and applies
to both `YOLO_WEIGHTS` and the morsetechlab plate localiser.

Concrete licence-safe option found this pass: **LibreYOLO**, described as an
**MIT-licensed**, drop-in Ultralytics alternative wrapping **YOLOX, RTMDet,
RF-DETR, D-FINE, DEIM and RT-DETR** behind one API `[VENDOR CLAIM]`.

⚠ **`[NOT ESTABLISHED]`** — LibreYOLO's maintenance status, real API
compatibility, and whether its wrapped weights are themselves permissively
licensed were **not verified**. The claim comes from the project's own site.
Do not put this in organizer-facing material as a solved procurement path.
Per CLAUDE.md §24.13, it needs the full dependency check before adoption, and
per §16 **no model swap before submission** — a swap invalidates every prior
measurement.

**Recommended posture for the submission:** keep the current stack, and state
the licensing position honestly in procurement terms — *"current pilot stack
includes AGPL-3.0 components; a permissively-licensed production path exists
(RF-DETR / D-FINE / RT-DETR family) and requires re-validation."* That is
procurement literacy, which §16 explicitly asks for, and costs nothing.

### D2. OCR direction

`[ACADEMIC PAPER]` **Layout-Independent License Plate Recognition via
Integrated Vision and Language Models** (Shabaninia, Asadi-zeydabadi,
Nezamabadi-pour; arXiv 2510.10533, submitted 12 Oct 2025). Two-stage: detector,
then a recognition stage jointly optimising **visual and linguistic cues**,
giving character identification and **post-OCR refinement in one process** —
"without explicit heuristic corrections or manual layout classification."
Evaluated on IR-LPR, UFPR-ALPR and AOLP.

**Why this matters to us specifically:** Sentinel's `_best_pattern_match()`
homoglyph search and its top-to-bottom line-joining are *exactly* the "explicit
heuristic corrections" and "manual layout classification" this line of work
replaces. The paper is directional validation that the problem is real and the
heuristics are the known-weak solution — **not** a reason to swap anything
before the deadline.

⚠ No Indian dataset in its evaluation; no accuracy percentage available from
the abstract. Do not cite a number.

---

## E. GROUND TRUTH — THE PROJECT'S LARGEST UNRESOLVED GAP

`DECISION_REVIEW_2026-09-11.md` A1 records that the core differentiator has no
ground truth. Labelled Indian ANPR datasets **do exist** and were not
previously catalogued here:

| Dataset | Content | Label |
|---|---|---|
| **VisionPlate ANPR** (IEEE DataPort) | Indian vehicle classification + plate detection + OCR; explicitly targets *"unconstrained, noisy, chaotic"* Indian traffic, commercial-vehicle morphology, sensor noise, motion blur, **hand-painted non-standard fonts**; YOLOv8-format bounding boxes | `[VENDOR CLAIM]` |
| **Indian License Plate Recognition Dataset (YOLO & OCR)** (IEEE DataPort) | Stylised hand-painted fonts, **multi-line square formats**, physical obstruction (**flower garlands, ropes**), severe paint degradation | `[VENDOR CLAIM]` |
| **Dataclusterlabs Indian Number Plates** (HuggingFace) | Real-world Indian plates, mobile capture, urban + rural | `[VENDOR CLAIM]` |
| **UFPR-ALPR** (Brazilian) | 4,500 images, motorcycles/cars/public transport; widely-used benchmark | `[ACADEMIC PAPER]` |

**Why this is the highest-value item in this document after A1:** an honest,
reproducible accuracy figure on a named public Indian dataset would convert
CLAUDE.md §8's forbidden claim *"our ANPR accuracy is X%"* into a **permitted**
one — *"X% on VisionPlate ANPR, measured on <date> with <script>, project-
reported"*. That is the difference between an unciteable demo and a defensible
result.

⚠ Licence, access terms and download size for each were **not checked**.
IEEE DataPort commonly requires a subscription. Verify before planning around
these. **Post-submission work** — CLAUDE.md §7 forbids starting a validation
campaign now.

---

## F. FIELD ACCURACY — WHAT IS AND IS NOT EVIDENCE

| Claim | Label | Usable? |
|---|---|---|
| Flock: **71% misread** of 1,427 stolen/felony alerts, Roseville CA, attributed to camera angle/placement | `[NEWS]` — already in `RESEARCH_EXISTING_SYSTEMS.md` | ✅ Yes, dated and citable |
| CAG of India: **3.8% forwarding rate**, Delhi 1,65,861 challans never reaching court | `[OFFICIAL GOVERNMENT]` — already in `DECISION_REVIEW` §I | ✅ Yes, strongest available |
| Delhi defective-number-plate bookings: **16,859 in 2024 vs 4,363 in 2023 (+286%)** | `[NEWS]` (Tribune India) | ✅ Yes — supports §G3 |
| Penalty ₹5,000 first offence, doubled on repeat, MV Act §177; impounding for repeat offenders | `[NEWS]` | ✅ Yes |
| Karnataka: AI cameras on Bengaluru highways with **high false-positive rates** prompting scrutiny of all plate anomalies | `[NEWS]`, non-specific | ⚠ Directional only — no figure |
| *"90% of wrong challans are ANPR misreads (O/0, 8/B)"* | **`[UNVERIFIED CLAIM]`** | ❌ **DO NOT USE** |
| *"RTI revealed per-camera error rates leading to mass challan cancellation"* | **`[UNVERIFIED CLAIM]`** | ❌ **DO NOT USE** |

**On the two rejected claims:** both appeared in search summaries and were
attractive — the first is a direct endorsement of `anpr.py`'s homoglyph table,
the second of the new ANPR-readiness scoring. Fetching the primary source
showed the article cites **no percentage, no official source, and no systematic
data**; its per-camera-error-rate example is a single illustrative anecdote
("confidence 54% against a state SOP threshold of 80%"). They are recorded here
**as rejected** so a future pass does not rediscover and believe them.

The underlying *mechanism* remains well-supported independently: O/0 and 8/B
confusion is documented in this project's own real cam06 evidence
(`anpr.py` comments, 2026-09-05), and per-camera placement-driven failure is
documented by the Flock/Roseville finding.

---

## G. ANALYTICS BEYOND ANPR

### G1. Already incumbent parity — DO NOT BUILD, DO NOT CLAIM

`[OFFICIAL GOVERNMENT]` (`DECISION_REVIEW` A3) + `[VENDOR CLAIM]` (Videonetics):

TRINETRA/NETRAM today runs ANPR, **RLVD, speed, wrong-way, crowd density,
unattended object, camera tampering, intrusion, behavioural pattern analysis**,
e-challan. Videonetics adds **no-helmet, triple riding, stop-line,
driver-on-call, no-seat-belt** — 8 violation types, 14 incident types,
150,000 events/day at Bhopal across 23 junctions.

**Helmet detection and triple-riding detection are the two ideas most likely to
be proposed next, and both are shipped by the incumbent.** Academic work exists
(Frontiers in AI 2025, NVIDIA TAO + YOLOv8 for Indian smart-city helmet
violation; Springer 2025 for triple-riding) `[ACADEMIC PAPER]`, which makes them
look tractable — but tractable and *differentiating* are different questions.

### G2. Already built in Sentinel — strengthen, don't extend

Wrong-way and stopped-in-restricted-zone (`anomaly.py`), dwell, image-plane
speed/direction, homography-calibrated km/h, density windows, storage tiers,
and ANPR-suitability. Per CLAUDE.md §7, **"more anomaly types" is explicitly
deferred.**

### G3. The one open gap — plate-failure attribution

Not found in any vendor capability list surveyed in this document or in
`RESEARCH_LLM_SURVEILLANCE_2026.md`. `[NOT ESTABLISHED]` that no vendor does it
— only that none publishes it.

**Capability:** classify each unread-plate sighting as
`CAMERA_UNFIT` / `PLATE_UNREADABLE` / `INCONCLUSIVE`, using the camera-fitness
verdict as the discriminator (§C).

**Why it is the right one for this project:**
- Uses only columns already persisted — **no new model, no new dependency, no
  AGPL exposure**
- Enforcement-actionable under an existing statute with an existing penalty
- Directly serves CLAUDE.md §6 Priority C: *"Do not hide poor ANPR results.
  Convert them into an operational camera-fitness finding."* This is the
  second half of that sentence
- Complements rather than duplicates the incumbent
- Demos in one screen alongside ANPR Readiness

**Hard constraints:** `PROBABLE` tier at most; never auto-challan; never
exportable as confirmed evidence; must state that obstruction, weather, glare
and motion blur are unmeasured confounders.

### G4. Rejected for this project

Face recognition (CLAUDE.md OUT, DPDP + NIST demographic bias), convoy/associate
analysis (§7 deferred), seat-belt/driver-on-call (requires in-cabin resolution
this deployment's geometry cannot support, and is incumbent parity anyway).

---

## H. RECOMMENDED ORDER

| # | Item | Priority | Effort | Rationale |
|---|---|---|---|---|
| 1 | ~~Fix BH-series plate validation + tests~~ — **DONE 2026-09-19** | **P1** | Small | Confirmed defect against a mandatory requirement (§A1). Fixed same day; see `TASKS.md`. |
| 2 | Exploit BH's I/O exclusion in homoglyph resolution | P2 | Small | Free accuracy gain, only valid in the BH branch (§B1) |
| 3 | Document licensing posture in procurement terms | P2 | Docs only | §16 asks for it; costs nothing; no swap (§D1) |
| 4 | Plate-failure attribution (`PLATE_UNREADABLE`) | P2 | Medium | The only surviving differentiator found (§G3) |
| 5 | Measure on a named public Indian dataset | **Post-submission** | Large | Converts a forbidden claim into a permitted one (§E) |
| 6 | Model/OCR stack swap | **Deferred** | Large | §16 forbids a rushed pre-submission swap (§D) |

**Do not build:** helmet, triple riding, seat-belt, red-light, stop-line — all
incumbent parity (§G1).

---

## I. SOURCES

**Indian plate formats & HSRP**
- [Vehicle registration plates of India — Wikipedia](https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_India)
- [BH / Bharat series format — BankBazaar](https://www.bankbazaar.com/driving-licence/bharat-series-number-plates.html) · [Acko](https://www.acko.com/car-guide/bh-number-plate/) · [SiliconIndia](https://www.siliconindia.com/news/general/bh-series-number-plate-format-and-key-differences-from-traditional-plates-nid-238602-cid-1.html)
- [HSRP specification & ANPR readability — Zurich Kotak](https://www.zurichkotak.com/knowledge-center/car-insurance/high-security-number-plate-in-india) · [Acko](https://www.acko.com/car-guide/high-security-number-plate/) · [BankBazaar](https://www.bankbazaar.com/driving-licence/high-security-registration-plate.html)
- [Karnataka HSRP fitment shortfall — Deccan Herald](https://www.deccanherald.com/amp/story/india%2Fkarnataka%2Fdeadline-draws-near-but-only-355-lakh-of-2-crore-vehicles-have-hsrp-3008084)

**Models, OCR, licensing**
- [Ultralytics License (AGPL-3.0)](https://www.ultralytics.com/license) · [LibreYOLO — MIT alternative](https://www.libreyolo.com/articles/best-ultralytics-alternatives) *(unverified)*
- [morsetechlab/yolov11-license-plate-detection — HuggingFace](https://huggingface.co/morsetechlab/yolov11-license-plate-detection)
- [Layout-Independent LPR via Integrated Vision and Language Models — arXiv 2510.10533](https://arxiv.org/abs/2510.10533)
- [Efficient LPR via Pseudo-Labeled Supervision with Grounding DINO and YOLOv8 — arXiv 2510.25032](https://arxiv.org/pdf/2510.25032)
- [End-to-End ANPR for Indian datasets — arXiv 2207.06657](https://arxiv.org/pdf/2207.06657)

**Datasets**
- [VisionPlate ANPR — IEEE DataPort](https://ieee-dataport.org/documents/visionplate-anpr-indian-vehicle-classification-license-plate-detection-and-ocr-dataset)
- [Indian License Plate Recognition Dataset (YOLO & OCR) — IEEE DataPort](https://ieee-dataport.org/documents/indian-license-plate-recognition-dataset-yolo-ocr)
- [Indian number plates dataset — HuggingFace](https://huggingface.co/datasets/Dataclusterlabspvtltd/indian-number-plates-dataset)
- [Indian Number Plate detection dataset — Roboflow Universe](https://universe.roboflow.com/anpr-gfpt1/indian-number-plate-bkaj2)

**Enforcement & field accuracy**
- [286% jump in defective number plate violations — Tribune India](https://www.tribuneindia.com/news/delhi/286-jump-in-defective-number-plate-violations-in-capital-629263)
- [Delhi Police on obscured plates (chilli, lemon) — ThePrint](https://theprint.in/india/remove-chilli-lemon-anything-that-hides-your-number-plate-or-be-ready-to-face-delhi-police/733366/)
- [ANPR & CCTV in India's e-challan system — Cars24](https://www.cars24.com/article/anpr-cameras-and-cctv-use-in-indian-e-challan-system/) · [ParkPlus](https://parkplus.io/blog/challan/how-anpr-echallan-system-works-in-india)
- ⚠ [righttoinformation.wiki — contest e-challan](https://righttoinformation.wiki/traffic-challan-wrongly-issued-contest-india) — **fetched and rejected**; cites no source or data for its misread-rate claims (§F)

**Analytics beyond ANPR**
- [Videonetics Traffic Management System](https://www.videonetics.com/traffic-management-system) · [Bhopal Smart City case study](https://www.videonetics.com/case-study/bhopal-case-study-designed_26thmarch-1684913675) · [Bengaluru Traffic Authority](https://www.videonetics.com/case-study/bengaluru-traffic-authority)
- [Rider helmet violation detection in Indian smart cities (NVIDIA TAO + YOLOv8) — Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1582257/full)
- [Two-wheeler rider identification and triple-riding detection — Springer](https://link.springer.com/article/10.1007/s44163-025-00263-3)
