# Model 4 — Security Architecture Document

**Status: DESIGN TARGET, roadmap-only** — same status as every other
Model 4 document in this folder. This fills the gap
`REQUIREMENTS.md` named explicitly: "a dedicated statewide security
architecture document doesn't exist separately... would be net-new work
if requested." Compiled 2026-09-17 from real, cited Indian regulatory
sources — not generic "security best practices." Nothing here is a claim
of current compliance; it is a design target grounded in what a
statewide Indian government law-enforcement platform would actually be
required to satisfy, so that the jury sees a credible answer, not an
invented one.

Per `CLAUDE.md`'s conservative-wording rule: nothing in this document
should be read as "certified," "compliant," or "audited." Use
"designed to support X" throughout, and treat every citation's confidence
note as load-bearing — a wrong regulatory claim to a Gujarat Police/NFSU
jury is worse than an honest gap.

## 1. Incident reporting and logging — CERT-In Cyber Security Directions (28 April 2022)

Issued under IT Act 2000 §70B. Directly applicable to a government-operated
platform like Model 4:

- **6-hour incident reporting**: specified cyber incidents (data breach/
  leak, unauthorized access, critical-system compromise, defacement, and
  others) must be reported to CERT-In within 6 hours of the organisation
  becoming aware of them.
- **180-day log retention, within Indian jurisdiction**: ICT system logs
  must be retained for 180 days and be producible to CERT-In on request.

**Design implication for Model 4**: the pilot's existing audit-log
mechanism (`AuditLog`/`CameraAuditLog`, already real at pilot scale) is
the right shape, but a statewide deployment would need an explicit
180-day retention floor on system/security logs specifically (distinct
from `RETENTION_DAYS`'s DPDP-driven *personal-data* retention window,
which is intentionally shorter) and a defined internal escalation path
that can hit CERT-In's 6-hour reporting clock.

**Confidence**: verified — consistent across multiple independent legal
summaries of the primary directive (Lexology, Internet Society, Trilegal's
published PDF of the directions).

## 2. Hosting and procurement — MeitY / GI Cloud (MeghRaj), STQC empanelment, PPO'24/CRO'24

- **GI Cloud (MeghRaj) / STQC cloud empanelment**: if Model 4's central
  tier is cloud-hosted rather than fully on-prem, MeitY-empanelled
  providers are required to host data within India and hold ISO
  27001/27017/27018/20000 certification.
- **Public Procurement Order 2024 (PPO'24) + Customer Requirement Order
  2024 (CRO'24)**, gazetted 9 April 2024: mandates **STQC "Essential
  Requirements" (ER) certification for CCTV cameras** sold in or
  procured by the Indian government — covering hardware security,
  firmware integrity, and supply-chain transparency, with compliance
  deadlines running through 2025/2026.

**Design implication for Model 4**: this is a real, camera-hardware-level
procurement constraint, not just a software-stack concern — a statewide
rollout's camera procurement (not just Sentinel's own code) would need to
specify STQC-ER-certified hardware. Worth stating explicitly in any
procurement-facing version of this document, since it's the kind of
requirement a technical software team might otherwise miss entirely.

**Confidence**: verified for the empanelment/hosting requirement (AWS's
own MeitY-compliance page, Opsio); verified for PPO'24/CRO'24's existence
and STQC-ER mandate (multiple 2026 industry-compliance writeups); the
specific compliance deadline dates should be re-checked against the
actual gazette notification before being quoted as final in any
organizer-facing document, since secondary sources vary slightly on exact
dates.

## 3. DPDP Act 2023 §17 — law-enforcement processing and government exemption

- §17 exempts a Data Fiduciary from most of the Act's obligations when
  processing is necessary for prevention, detection, investigation, or
  prosecution of an offence — this covers police and investigative use of
  a platform like Model 4.
- Separately, §17 allows the Central Government to exempt any state
  instrumentality from all or part of the Act by Gazette notification, on
  grounds including sovereignty, security, and public order — **without
  requiring Parliamentary approval**.

**This is a regulatory gap, not a green light** — consistent with how
`RESEARCH.md` already frames the FRT regulatory gap for face recognition.
A Model 4 platform operating under a §17 exemption still needs its own
internal purpose-limitation, audit, and retention discipline (the same
CONFIRMED/PROBABLE/LEAD ONLY evidence-tier discipline and purpose-bound
query logging already real in this codebase) — the exemption removes
*external statutory* pressure to do so, it doesn't remove the operational
need.

**Confidence**: verified across independent secondary sources (the
statute text itself plus MediaNama's analysis) — not independently
cross-checked against the Gazette notification mechanism in practice.

## 4. Standards referenced in real Indian government CCTV/VMS tenders

Real government CCTV RFPs commonly require bidders to hold **ISO 9001 +
ISO 27001** certification (sometimes ISO 20000). STQC-ER certification
(§2 above) is separately described in industry material as aligning with
ISO 27001, OWASP ASVS 4.0 Level 2, and the NIST Cybersecurity Framework.

**Design implication for Model 4**: a real statewide procurement would
likely require the operating entity (not just camera vendors) to hold ISO
27001 certification for the platform itself. This is a governance/
certification commitment, not a code change — noted here as a target,
not something this project can self-certify.

**Confidence**: the ISO 27001 tender requirement is well-evidenced from
real tender language patterns; the NIST-CSF alignment claim traces to
vendor-marketing-adjacent sources, not a primary government document —
cite it as "commonly described as aligned with," never as an official
mandate.

## 5. Encryption at rest/in transit and network segmentation

**No standalone, specific Indian government directive was found**
mandating encryption/segmentation for a system like this, beyond what
the three sources above already imply:

- **STQC-ER** (§2): camera-hardware-level requirements including
  encrypted storage and network authentication.
- **MeitY/GI Cloud empanelment** (§2): ISO 27017/27018 (cloud security/
  privacy) if cloud-hosted.
- **CERT-In directions** (§1): logging and incident-response posture.

**Design target, stated honestly as inherited rather than independently
mandated**: TLS for every hop (already the pattern this pilot follows for
its HLS proxy and API), disk encryption for the video/evidence storage
tier, and department-segmented network access at the edge (already
named in `SCALABILITY.md` §5) — these are good-practice defaults this
project would implement regardless, not a claim that a specific Indian
statute names them as mandatory in these exact terms.

## 6. What this document is not

Not a compliance claim. Not a claim that Sentinel today satisfies any of
CERT-In's directions, STQC-ER, or ISO 27001 — none of that applies at
pilot scale, and none of it has been reviewed by qualified legal/
compliance counsel. This is a roadmap document naming the *real*
regulatory landscape a statewide deployment would need to navigate, so
that a jury Q&A about "security architecture" gets a grounded answer
instead of a generic one or an invented one.

## Sources

- CERT-In Cyber Security Directions, 28 April 2022: [Lexology summary](https://www.lexology.com/library/detail.aspx?g=899f3b94-c31f-4983-868f-5ee5abbf78c8), [Internet Society brief](https://www.internetsociety.org/resources/doc/2022/internet-impact-brief-india-cert-in-cybersecurity-directions-2022/), [Trilegal's published PDF of the directions](https://trilegal.com/wp-content/uploads/2022/05/2022-CERT-In-Directions-on-Reporting-Cyber-Incidents-1.pdf)
- MeitY GI Cloud / STQC empanelment: [Opsio](https://opsiocloud.com/in/knowledge-base/meity-empanelled-cloud-providers-india/), [AWS's MeitY compliance page](https://aws.amazon.com/compliance/MeitY/)
- PPO'24/CRO'24 STQC-ER CCTV mandate: [velvu.in](https://www.velvu.in/blog/cctv-new-rule-2026-india-stqc-certification), [modernext.in](https://modernext.in/blog/stqc-certification-cctv-2026-compliance/)
- DPDP Act 2023 §17: [dpdpa.com, §17 text](https://www.dpdpa.com/dpdpa2023/chapter-4/section17.html), [MediaNama analysis](https://www.medianama.com/2023/08/223-dpdp-bill-2023-government-exemptions-3/)
