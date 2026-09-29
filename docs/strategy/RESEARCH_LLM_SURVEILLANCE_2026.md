# Research: LLMs in Police Video Surveillance — Prior Art, Deployments, Regulation

Synthesized **2026-09-19** from a web research pass triggered by a proposal to
add an LLM to Sentinel. The question asked was deliberately blunt: *does this
product already exist, who is running it, in which country, and how?*

The answer is yes, in seven vendors and eleven Indian state police forces, and
the interesting part is not the capability — it is that three separate
regulators independently converged on governance requirements Sentinel's
architecture already satisfies.

Evidence labels used throughout, per `DECISION_REVIEW_2026-09-11.md`:
`[OFFICIAL GOVERNMENT]` `[NEWS]` `[VENDOR CLAIM]` `[ACADEMIC PAPER]`
`[TRADE PRESS]` `[INFERENCE]` `[NOT ESTABLISHED]`

**Standing caveat on this document:** every vendor capability below is a
`[VENDOR CLAIM]` or trade-press summary unless stated otherwise. None was
tested by this project. Absence of a governance feature in a vendor's public
material is recorded as `[NOT ESTABLISHED]`, **never** as evidence that the
vendor lacks it — that distinction is the same one this project demands of its
own claims (CLAUDE.md §8).

---

## A. EXECUTIVE VERDICT

**A1 — Natural-language video search is a commodity, not an innovation.**
Verkada shipped it in **May 2024**. Trade press in 2026 calls natural-language
video search *"table stakes"*. Genetec, Motorola/Avigilon, BriefCam, Hikvision
and Dahua all ship a version. A funded pure-play startup (Conntour) raised $7M
in March 2026 to do only this. Under CLAUDE.md §4.5 this **cannot be presented
as a Sentinel innovation**, and under §8 it cannot be presented as something
Indian policing lacks.

**A2 — An Indian state police force already runs LLM query over police data.**
Uttar Pradesh Police's **YAKSH**, built on Staqu's JARVIS One, has **CrimeGPT**
at its core: officers query crime data in plain language across FIRs, case
documents, faces, voice samples and CCTV. Staqu's JARVIS is deployed across
**eleven Indian state police forces**. Any pitch implying "Indian police cannot
query their systems conversationally" is false and checkable by a jury.

**A3 — The failures are all in governance, and regulation has arrived.**
California **SB 524**, the proposed **US Federal Rule of Evidence 707**, and the
**EU AI Act** (in force for high-risk law-enforcement AI from **2 Aug 2026**)
all independently require: label AI-assisted output, audit who invoked it and
on what, retain tamper-evident logs, and prove provenance. Sentinel already
implements the substantive parts of all four.

**Conclusion:** if an LLM is added, the claim is **not** "we added AI search."
It is *"NL search that cannot launder inference into evidence."* See §E.

---

## B. THE PRODUCT LANDSCAPE — WHAT ALREADY EXISTS

| Vendor | Product | Since | Capability | Label |
|---|---|---|---|---|
| **Verkada** (USA) | AI-Powered Search | **May 2024** | Freeform text over people/vehicles (*"white Tesla Model Y with tinted windows"*). A public foundation model with language+vision functionality, plus an in-house model that pre-processes and caches customer video so queries don't reprocess footage. Sold explicitly into law enforcement alongside ALPR. | `[VENDOR CLAIM]` |
| **Motorola Solutions / Avigilon** (USA/CA) | Unity, Visual Alerts, "Assist" | 2026 | LLMs turn raw security data into alerts; operators author custom alerts in natural language. "Assist" detects keywords in radio traffic (e.g. "shots fired") and pushes to nearby officers. | `[VENDOR CLAIM]` `[NEWS]` |
| **Genetec** (Canada) | Security Center semantic search | current | Operator types *"person wearing a red jacket entering through the main door"*; system returns matching clips. Moves search from metadata lookup to meaning-based query. | `[TRADE PRESS]` |
| **BriefCam** (Milestone-owned, Israel/DK) | new analytics engine + XProtect App Platform | 2026 | Generative-AI readiness cited as an explicit design goal. Already integrates with Genetec AutoVu/Synergis. | `[VENDOR CLAIM]` |
| **Hikvision** (China) | LLM-integrated products | 2020s→ | Text-prompt retrieval of footage. New-generation cameras (with Huawei) carry silicon able to run vision models **and LLMs on-device**, analysing at point of capture rather than streaming to a datacentre. | `[TRADE PRESS]` |
| **Dahua** (China) | Xinghan Vision / Multimodal / Language model series | current | Processes visual information, context and language simultaneously. | `[VENDOR CLAIM]` |
| **Conntour** (USA) | pure-play AI video search | **$7M, Mar 2026** (General Catalyst, YC) | Query camera feeds in natural language for any object, person or situation. | `[NEWS]` |

**Capability framing seen across the category** `[TRADE PRESS]`: older tools
offered a few dozen preset searches; language-based search allows an almost
unlimited range of enquiries. Investigators ask natural-language questions and
receive **timestamped answers with citations**.

> **Note the convergence.** "Timestamped, cited answers" is the same idea as
> Sentinel's per-link provenance — arrived at independently by the commercial
> market. That is corroboration of the design direction, not a reason to copy
> the feature.

---

## C. INDIA — DEPLOYED, AT STATE POLICE SCALE

### C1. Staqu Technologies (Gurugram) — the one that matters

| Fact | Label |
|---|---|
| **JARVIS** CCTV video+audio analytics platform, deployed across **eleven Indian state police forces** | `[VENDOR CLAIM]` `[NEWS]` |
| **UP Police — YAKSH**, powered by JARVIS One, launched at *Police Manthan 2025*, inaugurated by the Chief Minister. Multimodal: video, audio and text in one system, **operating on internal police data only** | `[NEWS]` |
| **CrimeGPT** — generative-AI interface, officers **query crime data in simple language**: criminals, patterns, gangs, past incidents. Searches span FIRs and case documents, facial recognition from photographs, voice samples, CCTV footage and textual records. Launched **March 2024** | `[NEWS]` |
| **Punjab Police — PAIS**: crime prediction, facial recognition, suspect identification, voice matching, criminal network analysis | `[NEWS]` |
| **Gurgaon Police — JARVIS ANPR**: detects vehicles with fake or suspicious plates in real time | `[NEWS]` |
| Backing database: biometric and digital identity data on **900,000+ individuals** (UP STF collaboration) | `[NEWS]` |
| Also deployed at Ram Mandir Ayodhya and IPL stadium crowd control | `[NEWS]` |
| Stated safeguard: "ground-up data verification architecture" — criminal data created at police-station level, physically verified by beat officers. **No accuracy metrics or detailed safeguard protocols published** | `[NEWS]` / `[NOT ESTABLISHED]` |

### C2. ⚠ NAME COLLISION — do not let this reach a jury

**UP Police's "Trinetra"** (Staqu's facial-recognition / speaker-identification
/ gang-analysis app, which CrimeGPT extends) is a **different system** from
**Gujarat's TRINETRA**, which `STRATEGY.md` and `DECISION_REVIEW_2026-09-11.md`
§132 record as the **state-level ICCC above 34 NETRAM district command centres**
`[OFFICIAL GOVERNMENT]` (VISWAS Phase-II RFP §1.3).

Same name. Different states, different vendors, different systems.

Conflating them would produce a confidently-worded, checkably-false statement
about the incumbent this project is positioned alongside — the exact failure
mode CLAUDE.md §8 exists to prevent. **This belongs in the forbidden-claims
list.**

`[NOT ESTABLISHED]` — whether Gujarat Police is among Staqu's eleven states.
Named deployments found were UP, Punjab and Haryana (Gurgaon). This is a real
gap; do not assume either way.

### C3. Wider Indian context

| Fact | Label |
|---|---|
| **Delhi Safe City**: latest phase inaugurated **Feb 2026** by the Union Home Minister. 10,000 new + 15,000 existing cameras into a new C4I centre; real-time video analytics | `[NEWS]` |
| Delhi Police operate ~25,000 cameras with FRT, ANPR, crowd density and abandoned-object detection; FRT matching against **one million faces in 200 ms** | `[NEWS]` |
| **Greater Chennai Police**: 5,000+ AI-enabled cameras under Safe City, analytics coupled to alerts | `[NEWS]` |
| India smart-city surveillance market projected **>$4 bn by 2028** | `[TRADE PRESS]` |

---

## D. WHERE IT IS GOING WRONG — AND WHAT REGULATORS DID ABOUT IT

### D1. Documented failures

| Finding | Label |
|---|---|
| **Axon Draft One** generates police-report drafts from bodycam transcripts using **OpenAI's GPT-4** | `[NEWS]` |
| Utah case: background audio from *The Princess and the Frog* led the AI to report that **an officer turned into a frog** — the tool could not distinguish human speech from pre-recorded audio | `[NEWS]` |
| Forbes (**Jul 2026**): public records show Draft One reports **get facts wrong** | `[NEWS]` |
| **King County, WA Prosecuting Attorney's Office (2024) notified agencies it will not accept AI-assisted police reports**, citing hallucinations | `[NEWS]` |
| Consumer-grade AI enhancement tools have **never been validated for forensic use**; how often they hallucinate faces, clothing detail, hand position or weapon presence is **unknown** | `[ACADEMIC PAPER]` |

### D2. The regulatory response — all within ~18 months

| Instrument | Requirement | Label |
|---|---|---|
| **California SB 524** (signed) | AI-assisted police reports must be **labelled as AI-assisted**; agencies must keep an **audit trail identifying who used AI** and **which video/audio was used** | `[NEWS]` |
| **Proposed US FRE 707** | Machine-generated evidence subjected to **FRE 702 / *Daubert*** expert-reliability standards | `[ACADEMIC PAPER]` |
| ***State v. Puloka*** (WA, triple-homicide) | First major judicial ruling on AI-enhanced video evidence | `[ACADEMIC PAPER]` `[NEWS]` |
| **EU AI Act**, high-risk obligations live **2 Aug 2026** | Law-enforcement AI is high-risk (not banned). Requires continuous risk management, data governance, complete technical documentation, **tamper-evident logging retained ≥6 months**, deployer transparency, human oversight, cybersecurity resilience | `[OFFICIAL GOVERNMENT]` |

---

## E. MAPPING AGAINST SENTINEL

### E1. Requirements Sentinel already meets

| External requirement | Sentinel mechanism | Verification status |
|---|---|---|
| SB 524 — label AI-assisted output | `evidence_class.py` CONFIRMED / PROBABLE / LEAD_ONLY, enforced in API, UI and export | AUTOMATED-TEST VERIFIED |
| SB 524 — audit trail: who, and on what | `AuditLog` rows carrying user, purpose and case ID; evidence exports are logged **before** the artefact is produced, so an attempt is on the record even if rendering fails | AUTOMATED-TEST VERIFIED — **with the gap in E1a below** |
| EU AI Act — tamper-evident logging ≥6 months | `AUDIT_RETENTION_DAYS=365`; audit logs deliberately outlive the personal data they describe | IMPLEMENTED, UNVERIFIED (not legally assessed) |
| EU AI Act / FRE 707 — provenance of machine output | Write-time SHA-256 (`evidence_integrity.py`), `production_stamp` recording the real-vs-stub model seam, §63-oriented package | AUTOMATED-TEST VERIFIED |
| FRE 707 / *Daubert* — reliability must be statable | Per-link `link_method` / `link_score` / `link_time_gap_s`; stated thresholds with provenance on ANPR readiness | AUTOMATED-TEST VERIFIED |
| Forensic-validation gap (D1) | `anpr_suitability.py` refuses to promote an upper-bound heuristic measurement to CAPABLE; `INCONCLUSIVE` is a real verdict | AUTOMATED-TEST VERIFIED |

#### E1a. Honest gap found while writing this section

The claim "mandatory purpose **and** case ID on every lookup" was checked
against the code and is **overstated**. Actual state in `routes_vehicle.py`
(verified 2026-09-19):

- `purpose` is genuinely enforced on the search paths — `Query(...,
  min_length=8)`, so a blank or token purpose is rejected (lines 146, 324, 371).
- **`case_id` is optional everywhere** (`str | None = None`). Purpose-binding
  is real; case-binding is not mandatory.
- **`GET /vehicle/event/{id}/crop` defaults `purpose` to `"unspecified"`**
  (line 264) rather than requiring one — so the single path that serves an
  actual evidence image has the weakest purpose binding of any route.

Against SB 524's "identify the person who used AI **and the footage used**"
this is the closest thing to a real compliance gap in the codebase. It is
cheap to close and is worth closing **regardless of whether any LLM is ever
added** — it is a governance fix, not an LLM prerequisite. Logged here rather
than silently fixed, per CLAUDE.md §23.3 (one task, one objective).

`[NOT ESTABLISHED]` — whether any vendor in §B implements equivalent controls.
Their public material does not describe evidence-tier gating or purpose-bound
audit of AI queries. **This is absence of published evidence, not evidence of
absence**, and must be worded that way in any organizer-facing material.

### E2. Scope correction this research forces

An earlier in-session suggestion framed natural-language investigation search
as a **differentiator-grade** addition. §A1 and §C1 refute that: Verkada shipped
it in May 2024, and UP Police have been running conversational query over crime
data since March 2024.

**Corrected position.** If NL search is built, it is a **usability feature on a
governance platform**, benchmarked against SB 524 / FRE 707 / EU AI Act — never
claimed as novel capability, and never claimed as something Indian policing
lacks.

### E3. Design constraints, if built

1. **The LLM emits a query, never an answer.** Output is a validated filter
   struct executed by the existing `/vehicle/search-by-attributes` path — which
   already carries RBAC, department scoping, purpose binding and audit.
2. **The generated filter is always displayed.** A model error must present as
   a visibly wrong *filter*, not a confidently wrong *result*.
3. **Evidence tiers are untouched.** Results are SQL rows; CONFIRMED / PROBABLE
   / LEAD_ONLY and the LEAD_ONLY export block apply exactly as now.
4. **Only the query text leaves the machine.** No plates, no event rows, no
   case IDs in the prompt — the prompt is the investigator's phrase plus the
   camera/department vocabulary. This is what makes it shippable ahead of a
   DPDP/procurement review rather than after one.
5. **Audit-log the natural-language input alongside the generated filter**, so
   SB 524's "who used AI and on what" is answerable for AI queries too.

### E4. Explicitly out of scope

Confirmed by this research as things to keep refusing — `[NEWS]`/`[ACADEMIC
PAPER]` above document the failure mode for each:

- LLM/VLM plate OCR on crops (already assessed and declined, `HLD.md` §10)
- LLM deciding cross-camera identity links
- LLM generating or triaging alerts
- LLM-written content inside the §63 package (Axon's failure mode, and the
  reason King County refuses such documents)

---

## F. PRIORITY

**P2, behind the P0 own-feed demo recording.** CLAUDE.md §7 forbids scope
expansion before submission, and `TASKS.md` records the submission deadline as
**28 September 2026** with the event **12–13 October 2026**. A missing mandatory
artifact is not compensated by a bonus feature.

The higher-value output of this research is **not** the feature. It is §D2 +
§E1: three regulators converging on requirements this project already meets is
a defensible, citable, dated slide — and it costs nothing to build.

---

## G. SOURCES

**Vendors / category**
- Conntour $7M raise — [TechCrunch, Mar 2026](https://techcrunch.com/2026/03/26/conntour-raises-7m-from-general-catalyst-yc-to-build-an-ai-search-engine-for-security-video-systems/)
- [Verkada — Introducing AI-Powered Search](https://www.verkada.com/blog/ai-powered-search/) · [Verkada — Law Enforcement](https://www.verkada.com/solutions/law-enforcement/)
- [Motorola Solutions combines AI, voice and video for police — GovTech](https://www.govtech.com/biz/motorola-solutions-combines-ai-voice-and-video-for-police)
- [Genetec semantic video search](https://visionplatform.ai/genetec-semantic-video-search/) · [BriefCam technology overview](https://www.briefcam.com/technology/overview/)
- [China upgrades surveillance with AI cameras and on-device LLMs](https://www.resultsense.com/news/2026-05-28-china-ai-surveillance-overhaul/) · [Hikvision — Wikipedia](https://en.wikipedia.org/wiki/Hikvision) · [Dahua AI models — CCTV Wiki](https://cctvwiki.com/en/dahuas-ai-models-tackle-key-challenges-in-video-surveillance/)
- [Natural Language Search in Video Surveillance — CheckVideo](https://www.checkvideo.com/blog-post/natural-language-search-video-surveillance/)
- [The Realities of AI Video Surveillance — Schneier on Security](https://www.schneier.com/blog/archives/2026/06/the-realities-of-ai-video-surveillance.html)

**India**
- [UP Police YAKSH / CrimeGPT — The Hans India](https://www.thehansindia.com/news/national/uttar-pradesh-polices-ai-app-yaksh-powered-by-staqus-jarvis-one-multimodal-ai-platform-1034784)
- [Staqu biometric Crime GPT — Biometric Update, Mar 2024](https://www.biometricupdate.com/202403/staqus-biometric-crime-gpt-helps-uttar-pradesh-police-take-a-byte-out-of-crime)
- [Staqu Technologies](https://www.staqu.com/) · [JARVIS across 70 UP jails — Channel Drive](https://channeldrive.in/applications/staqu-launches-jarvis-an-ai-based-video-analytics-platform-across-70-jails/)
- [Delhi Safe City — Internet Freedom Foundation](https://internetfreedom.in/delhis-safe-city-project-and-the-expansion-of-ai-enabled-surveillance/) · [The News Minute](https://www.thenewsminute.com/news/explained-delhi-polices-ai-surveillance-network-and-why-its-under-scrutiny)
- [AI & Surveillance in India roundup — SFLC.in](https://sflc.in/artificial-intelligence-and-surveillance-in-india-2025-roundup/) · [Oxford Institute of Technology and Justice — India](https://www.techandjustice.bsg.ox.ac.uk/research/india)

**Failures & regulation**
- [Axon AI reports get facts wrong — Forbes, Jul 2026](https://www.forbes.com/sites/thomasbrewster/2026/07/22/axon-says-ai-police-reports-save-time-public-records-show-they-get-facts-wrong/)
- [AI police report hallucinated an officer into a frog — TechSpot](https://www.techspot.com/news/110860-time-when-ai-police-report-hallucinated-officer-turning.html)
- [States regulating AI-written police reports — Policing Insight](https://policinginsight.com/feature/opinion/concerns-about-ai-written-police-reports-spur-states-to-regulate-the-emerging-practice/)
- [When AI Invents the Pixels / *State v. Puloka* — Criminal Legal News](https://www.criminallegalnews.org/news/2025/dec/15/when-ai-invents-the-pixels-challenging-ai-enhanced-video-evidence-in-criminal-cases/)
- [Reliability and Admissibility of AI-Generated Forensic Evidence — arXiv 2601.06048](https://arxiv.org/pdf/2601.06048)
- [EU AI Act high-level summary](https://artificialintelligenceact.eu/high-level-summary/) · [Aug 2026 compliance countdown — RAIL](https://responsibleailabs.ai/knowledge-hub/articles/eu-ai-act-august-2026-compliance)
