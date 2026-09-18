# Sentinel — Gujarat Police Innovation Challenge 2026

Read these files before doing anything substantial in a new session:

1. `docs/hackathon/HACKATHON_DETAILS.md` — challenge rules and acceptance criteria.
2. `docs/strategy/STRATEGY.md` — current architecture and scope decisions.
3. `docs/strategy/DECISION_REVIEW_2026-09-11.md` — latest evidence-based correction to the project strategy, if present in the repo.
4. `sentinel-solution/docs/HLD.md` — current technical design.
5. `docs/hackathon/TASKS.md` — current execution status.

Do not re-derive these from memory. Re-read them because they may change.

This is the primary instruction file for AI coding agents working on this repository. If another agent file points here, keep this file as the single source of operational instructions.

---

## 1. Project definition — current position

Sentinel is a submission for the Gujarat Police Innovation Challenge 2026.

The project is **not** positioned as:

- a replacement for VISWAS / TRINETRA / NETRAM,
- a new VMS,
- a new ANPR product,
- a claim that Gujarat Police cannot already track vehicles,
- a claim that appearance-based cross-camera Re-ID is a novel invention.

The current product position is:

> **Sentinel is a vendor-neutral interoperability, accountability, and evidence-readiness layer over existing departmental CCTV/VMS/ANPR systems.**

Its job is to make existing camera infrastructure easier to register, integrate, health-check, search, audit, investigate, and govern without forcing departments to replace their current systems.

The strongest current product story is:

> Gujarat already has cameras, VMS and ANPR. Sentinel adds a common operational layer that makes multi-system data interoperable, camera fitness measurable, AI-derived links explainable, searches purpose-bound, and evidence packages auditable.

Do not drift back to the old headline:

> "Sentinel tracks vehicles across cameras even when ANPR fails."

That is not currently supported strongly enough by real ground-truth evidence.

---

## 2. Deadline and priority mindset

**Phase 1 submission deadline: 15 September 2026.**

Grand Finale / event: 22–23 September 2026.

Remaining time is scarce. Optimize for:

1. mandatory compliance,
2. finished demos,
3. defensible claims,
4. a small number of high-value India-specific additions,
5. reliable end-to-end behavior.

Do not optimize for feature count.

---

## 3. Mandatory hackathon outcomes

### Model 1 — mandatory base

Model 1 must remain strong and demoable:

- camera registry,
- manual/bulk/API onboarding,
- GIS mapping,
- camera metadata,
- department ownership,
- camera health,
- last-seen / availability status,
- coverage/gap analysis,
- role-based access control,
- sample data,
- registry API documentation.

### Model 2 — chosen operational model

Model 2 must demonstrate:

- direct integration with departmental systems through RTSP / ONVIF / APIs,
- unified viewing without replacing departmental systems,
- **at least two genuinely different systems/sources** in the unified viewer if the organizer interprets the requirement literally,
- ANPR demonstration,
- ANPR/vehicle metadata generation,
- searchable vehicle movement records,
- event tagging,
- configurable multi-camera video wall,
- watchlist correlation,
- automated alerts,
- system independence.

### Live evaluation scenario

Expect a scenario where the organizers provide a registration number and expect:

- vehicle identification/tracing,
- timestamped location-wise movement history,
- watchlist cross-reference,
- automatic alerts,
- evidence of integration quality,
- analytics quality,
- interoperability,
- performance/scalability reasoning.

### Mandatory submission artifacts

Do not lose track of:

- presentation,
- HLD / technical proposal,
- own-feed demo video,
- government-feed demo / recording / report where access is available,
- scalability strategy,
- accessible links / credentials / reports.

Bonus features never compensate for a mandatory requirement that is missing.

---

## 4. Critical strategic decisions

### 4.1 Keep ANPR, but demote it from the innovation story

ANPR remains necessary because Model 2 asks for an ANPR demonstration and vehicle metadata/search.

Keep this minimal, honest pipeline:

`camera -> vehicle detection -> plate localisation -> OCR/ANPR -> validation -> event -> search/watchlist/alert`

Do not spend the remaining hackathon time trying to create a new ANPR research contribution.

### 4.2 Keep ByteTrack for within-camera tracking only

ByteTrack is useful for:

- maintaining a track inside one camera,
- associating repeated OCR attempts with one detected vehicle,
- temporal consensus.

Do not present ByteTrack as cross-camera tracking.

### 4.3 Vehicle attributes remain useful, but as metadata/search clues

Keep useful attributes such as:

- colour,
- vehicle type,
- plate fragments,
- timestamps,
- camera/location.

Use them for:

- investigator filtering,
- narrowing search results,
- supporting context.

Do not treat colour/type/appearance alone as proof that two detections are the same physical vehicle.

### 4.4 Appearance-based cross-camera correlation is experimental

Current appearance-only identity resolution must be treated as **LEAD ONLY** unless a stronger evidence path is added and validated.

Never present an appearance-only link as a confirmed vehicle identity.

If retained in the UI, label it clearly and expose:

- link method,
- link score,
- time gap,
- geo feasibility,
- evidence class.

A LEAD ONLY result must not be exportable as confirmed evidence.

### 4.5 Do not claim novelty for commodity components

Do not call the following innovations:

- YOLO,
- PaddleOCR,
- ByteTrack,
- ANPR,
- RTSP,
- ONVIF,
- HLS,
- React,
- FastAPI,
- GIS mapping,
- video walls,
- watchlists,
- basic vehicle route history,
- generic VMS federation,
- basic spatio-temporal gating,
- fuzzy/homoglyph correction.

If innovation is claimed, it must be in the system behavior, governance, interoperability, evidence handling, or India-specific operational workflow.

---

## 5. Current strongest differentiators

Preserve and strengthen these areas.

### 5.1 Per-link evidentiary provenance

Every inferred cross-camera link should preserve the reason at decision time where applicable:

- `link_method`,
- `link_score`,
- `link_time_gap_s`,
- relevant geo/time feasibility information.

The investigator must be able to see **why** a link exists.

### 5.2 Explicit evidence classes

Use a confidence/evidence hierarchy in the product:

- **CONFIRMED** — plate-supported or otherwise directly evidenced.
- **PROBABLE** — multiple supporting signals but still requires investigator verification.
- **LEAD ONLY** — appearance/inference only; not evidence.

Do not allow a UI label, API response, export, or alert to silently convert inference into fact.

### 5.3 Purpose-bound and audited investigation

Preserve:

- required purpose,
- required case ID where already designed,
- RBAC,
- object-level authorization,
- audit trail,
- retention enforcement.

Purpose capture is an audit/governance control, not a guarantee that misuse cannot occur.

### 5.4 Open normalized event model

A common vendor-neutral event schema is strategically valuable.

The schema should be able to normalize data from:

- existing ANPR systems,
- RTSP/ONVIF camera analytics,
- departmental VMS APIs,
- future vendors.

Do not require a department to replace its current system in order to participate.

---

## 6. Highest-value additions before judging

Build only after P0 submission blockers are under control.

### Priority A — finish mandatory proof first

1. Finish the required own-feed demo video.
2. Remove inaccurate organizer-facing claims.
3. Ensure the Model 2 "two different systems" requirement is either demonstrated or explicitly clarified with the organizer.
4. Re-run all relevant tests before claiming a baseline.
5. Ensure all submission links and reports are accessible.

### Priority B — India-specific evidence integrity

Implement an **evidence-integrity / BSA §63-oriented export path**.

Important wording:

- call it "§63-oriented" or "§63-ready evidence package" until a legal expert validates compliance,
- do not promise automatic court admissibility.

Target capability:

- SHA-256 hash at evidence write time,
- immutable/stored hash reference,
- camera/device identity,
- owning department,
- event timestamp,
- model/software version stamps,
- production-method summary,
- purpose and case ID,
- audit entries for access/export,
- printable/exportable certificate package with Part A/Part B signature placeholders if appropriate.

Do not recompute the hash only at export and pretend that proves write-time integrity.

### Priority C — camera ANPR-suitability scoring

Add a camera readiness assessment that can classify a camera approximately as:

- CAPABLE,
- MARGINAL,
- UNSUITABLE,

based on measurable factors such as:

- plate pixel width/height,
- view angle where inferable,
- blur,
- glare/low light,
- repeated OCR success/failure,
- resolution,
- distance/zoom proxy where available.

The output should include a remediation recommendation where possible:

- re-angle,
- zoom,
- reposition,
- change lens,
- use a dedicated ANPR camera,
- mark analytics unsupported.

Do not hide poor ANPR results. Convert them into an operational camera-fitness finding.

### Priority D — confidence-tier enforcement

Make CONFIRMED / PROBABLE / LEAD ONLY visible and enforceable.

Examples:

- LEAD ONLY cannot be exported as confirmed evidence.
- Alerts based only on weak inference must be clearly differentiated.
- Direct plate confirmation must not be downgraded or overridden by appearance heuristics.

### Priority E — integration-loss / data-flow dashboard

Where technically feasible with real project data, expose a funnel such as:

`detections -> validated events -> normalized events -> forwarded -> accepted -> watchlist checks -> alerts`

The purpose is to make interoperability failures measurable.

Do not fabricate counts if the underlying stages are not actually instrumented.

---

## 7. What not to build before submission

Do not spend remaining time on:

- a new Re-ID model,
- new appearance embeddings unless explicitly required,
- convoy/associate analysis,
- more anomaly types,
- face recognition,
- fingerprint integration,
- cloning VAHAN/SARATHI integrations,
- replacing the incumbent VMS,
- building a new VMS,
- deploying Kafka / Redis / MediaMTX / Kubernetes just to match reference stacks,
- a superficial 80,000-camera load test,
- broad 26-department fake data population,
- large refactors unrelated to the submission path.

Do not silently expand scope because a paper or competitor has a feature.

---

## 8. Claims that are forbidden unless re-verified

Do not say:

- "TRINETRA is viewing-only."
- "Gujarat does not already have ANPR."
- "Gujarat does not already have vehicle tracking."
- "VAHAN/SARATHI integration is new for Gujarat."
- "wrong-way detection is our differentiator."
- "cross-camera vehicle identity resolution is proven on real footage."
- "appearance links are confirmed identities."
- "80,000-camera scalability is proven."
- "our ANPR accuracy is X%" unless measured on a defined dataset and reproduced.
- "§63 compliant" unless legally reviewed and the implementation actually satisfies the required process.

Where evidence is incomplete, use wording such as:

- "implemented, not yet field-validated",
- "architecture target",
- "project-reported result",
- "not found in public documentation",
- "experimental lead",
- "designed to support".

Honesty is a competitive advantage in this project.

---

## 9. Architecture direction

Do not perform a large structural rewrite.

The desired product flow is:

```text
Existing departmental systems
  - VMS A
  - VMS B
  - RTSP cameras
  - ONVIF cameras
  - existing ANPR metadata
        |
        v
Sentinel integration + normalization layer
        |
        +--> Camera Registry / GIS / Health / Gap Analysis
        |
        +--> Unified Viewer / Video Wall
        |
        +--> Selective analytics when required
        |       - vehicle detection
        |       - ANPR
        |       - attributes as metadata
        |
        +--> Normalized events
                |
                +--> Search / Investigation Timeline
                +--> Watchlist / Alerts
                +--> Confidence tier / provenance
                +--> Audit / Retention
                +--> Evidence integrity / §63-oriented export
                +--> Integration-loss observability
```

At scale, keep the architecture edge/regional/central in principle.

Do not claim that the pilot currently runs the statewide infrastructure.

---

## 10. Model 2 two-system rule

Treat this as an acceptance-critical question.

A single catalogue or gateway exposing many camera streams is not automatically proof of "two different systems".

Prefer a demo where Sentinel directly consumes two independently operated sources, for example:

- organizer/government source + independent ONVIF/RTSP source,
- VMS/API source A + ONVIF/RTSP source B,
- two genuinely different departmental/VMS systems if access exists.

If this cannot be demonstrated, obtain organizer clarification rather than relabeling one source as two systems.

Model 3 federation does not automatically satisfy Model 2 direct-integration acceptance.

---

## 11. UI principles

The UI should look like an operational government system, not an AI demo gallery.

Primary areas should converge toward:

- State / Operations Overview,
- Live Network / Video Wall,
- Camera Intelligence,
- Vehicle / Investigation Search,
- Watchlists / Alerts,
- Evidence,
- Governance / Audit / Compliance,
- Integrations / System Health.

Important UI behavior:

- state -> district -> department -> camera drill-down,
- server-side pagination/filtering for large camera lists,
- map clustering at statewide scale,
- on-demand video rather than attempting to stream every camera,
- CONFIRMED / PROBABLE / LEAD ONLY must be visually distinct,
- OBSERVED vs INFERRED must never look identical,
- LEAD ONLY export is disabled,
- model/stub/runtime health must be visible,
- camera ANPR readiness should be visible in registry/GIS/health views.

---

## 12. Existing repository structure

- `docs/hackathon/HACKATHON_DETAILS.md` — full rules and evaluation requirements.
- `docs/hackathon/REQUIREMENTS_COVERAGE.md` — requirement coverage matrix.
- `docs/hackathon/TASKS.md` — living task list.
- `docs/strategy/STRATEGY.md` — architecture/scope decision record.
- `docs/strategy/RESEARCH_EXISTING_SYSTEMS.md` — existing-system research.
- `docs/strategy/COMPETITIVE_TEARDOWN.md` — competitor analysis.
- `docs/submission/` — organizer-facing material.
- `docs/assets/` — presentation/screenshots/submission assets.
- `sentinel-solution/` — actual application.
- `sentinel-solution/docs/HLD.md` — technical design.
- `sentinel-solution/docs/SCALABILITY.md` — scale strategy.
- `sentinel-solution/docs/REVIEW_FINDINGS.md` — technical review findings.
- `sentinel-solution/docs/PRODUCTION_MIGRATION_PLAN.md` — the concrete,
  phased path from "hackathon pilot" to "a real deployment a department
  could run," explicitly **not** to be executed before the submission
  deadline (see §7/§27/§31 below) unless the user has explicitly
  overridden that, as happened 2026-09-18 (see the next file).
- `sentinel-solution/docs/PRODUCTION_READINESS.md` — added 2026-09-18:
  the honest gap-by-gap status table for that migration plan's
  scaffolds (pgvector Re-ID search, Kafka federation bus, OIDC auth,
  Docker/Kubernetes/CI artifacts). Everything in it is labeled `DESIGN
  TARGET` or `IMPLEMENTED, UNVERIFIED` — this environment has no
  Docker/kubectl/cloud access, so none of it has been deployed or
  tested against real infrastructure. Read this before claiming any
  production-hardening item is "done."
- `infra/` — the actual Docker/Kubernetes/nginx artifacts
  `PRODUCTION_READINESS.md` describes. See `infra/README.md` for the
  verification checklist before trusting any of it.
- `.github/workflows/` — CI workflow definitions (untested — never
  triggered by a real GitHub Actions runner from this environment).

When a referenced path differs in the actual repository, find the current file instead of inventing a replacement path.

---

## 13. Stack and tooling

Keep the repository conventions unless explicitly told otherwise.

### Backend

- Python 3.11
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- plain `pip`
- checked-in `.venv` pattern already used by the repository

### Database

- SQLite for the current pilot
- `DATABASE_URL` may support PostgreSQL later
- no Alembic
- additive migrations live in the existing migration mechanism in `app/db/session.py`
- preserve existing table naming conventions

### Frontend

- React 19 + Vite
- JavaScript/JSX, not TypeScript
- oxlint
- no silent Prettier/ESLint/TypeScript migration

### API

Follow existing flat non-versioned prefixes and route conventions.
Do not introduce `/api/v1/...` unless explicitly requested.

### Infrastructure

Do not add Docker, Compose, Kafka, Redis, Kubernetes, CI, or new infrastructure simply because a reference architecture mentions it.

---

## 14. Build and test commands

Use the repository's existing commands and only claim success when actually executed.

```bash
# Backend tests
cd sentinel-solution/backend
.venv/Scripts/python.exe -m pytest tests -v
# POSIX equivalent if applicable:
# .venv/bin/python -m pytest tests -v

# Backend run
cd sentinel-solution/backend
.venv/Scripts/python.exe -m app.main

# Frontend lint
cd sentinel-solution/frontend
npm run lint

# Frontend build
npm run build

# Frontend dev
npm run dev
```

Do not assume the previously reported test count still passes after code changes. Re-run it.

Never claim a test/build/lint/runtime path passed if it was not actually run successfully.

---

## 15. Coding rules specific to this project

### 15.1 Real/stub pattern

Preserve the existing pattern:

- protocol/interface,
- honest stub/no-op where required,
- real implementation,
- explicit runtime health state.

A stub must never generate fake success data.

### 15.2 Runtime verification over syntax checks

Every meaningful pipeline change requires a real execution path, including the failure mode.

Examples:

- plate misread,
- OCR returns garbage,
- camera drops/reconnects,
- evidence file missing,
- duplicate watchlist entry,
- stale alert,
- bad ONVIF response,
- unauthorized cross-department access.

### 15.3 Camera timing

For camera/stream code preserve existing project timing rules:

- force RTSP over TCP where required,
- use PTS for within-stream timing,
- do not derive motion timing from guessed FPS/wall-clock,
- reconnect with backoff,
- reset state on stream discontinuity where appropriate,
- do not assume uniform frame rate/resolution.

### 15.4 External/AI input is untrusted

Validate:

- API input,
- uploads,
- filenames,
- remote catalogue/API data,
- ANPR/OCR text,
- model output,
- redirect URLs,
- stream metadata.

Keep plate-format validation before watchlist/identity use.

### 15.5 Camera credentials

Never expose raw RTSP/WHEP credentials to the frontend or logs.

Admin-only raw fields stay admin-only.
The browser should consume proxied/safe URLs only.

### 15.6 Authorization

Enforce access at the object/resource level, not only by role.

Cross-department access must be explicit and auditable.

### 15.7 Database migrations

Use the existing additive-migration system.
Do not drop/recreate the real `sentinel.db` to simplify development.

The database contains accumulated pilot evidence and must be treated as valuable state.

### 15.8 No fabricated evidence

Never generate fake plate reads, fake metrics, fake camera health, fake alerts, or fake cross-camera proof to improve the demo.

Synthetic test data is acceptable only when clearly labeled synthetic.

---

## 16. Licensing and procurement awareness

The current inference path may include AGPL-licensed components.

Do not ignore or hide this.

Rules:

- do not introduce additional AGPL dependencies without explicit approval,
- do not silently perform a rushed detector/model swap before submission,
- if proposing a license-safe path, prefer Apache-2.0/MIT options where technically credible,
- if a swap is executed, re-run validation because prior measurements no longer transfer automatically,
- organizer-facing documentation must distinguish current stack from recommended production/procurement stack.

The objective is procurement literacy, not pretending licensing risk does not exist.

---

## 17. Evidence / legal wording

Electronic-evidence features are high-value but legally sensitive.

Use conservative wording:

- "§63-oriented evidence package",
- "designed to support §63 evidence preparation",
- "hash and provenance package for legal review".

Do not say:

- "court admissible",
- "legally compliant",
- "guaranteed evidence",

unless qualified legal review confirms the exact implementation and operating procedure.

---

## 18. Scope discipline

Before implementing a new idea:

1. Check `HACKATHON_DETAILS.md`.
2. Check `STRATEGY.md`.
3. Check the latest decision review if present.
4. Check `TASKS.md`.
5. Ask whether the feature helps a mandatory criterion, the live demo, or one of the approved high-value additions.

If not, do not build it now.

Prefer the smallest complete vertical slice over broad partial coverage.

Do not perform unrelated refactors, dependency upgrades, renames, or architectural cleanup under deadline pressure.

---

## 19. Git rules

The repository uses:

`branch -> implementation -> tests -> PR -> self-review -> merge`

Rules:

- only create branches, commits, pushes, PRs, merges, tags, or releases when the user explicitly asks,
- branch names: `feature/<short-description>`, `fix/<short-description>`, `docs/<short-description>`,
- use logical commits,
- never force-push,
- never amend published commits,
- never delete unmerged work without confirmation,
- never commit secrets, `.env`, `sentinel.db`, model weights, demo output, minted keys, or generated junk,
- self-review the complete diff before calling work ready.

---

## 20. Completion checklist

Before saying a task is complete:

- [ ] Requirement is clearly identified.
- [ ] Mandatory hackathon behavior was not broken.
- [ ] Existing architecture and conventions were followed.
- [ ] Security/privacy implications were checked.
- [ ] Evidence tier behavior is correct where relevant.
- [ ] LEAD ONLY cannot silently become confirmed evidence.
- [ ] Database changes use additive migrations.
- [ ] Relevant backend tests were added/updated and actually run.
- [ ] Frontend lint was run for frontend changes.
- [ ] Frontend build was run when applicable.
- [ ] Runtime behavior was exercised end-to-end.
- [ ] No secrets or raw camera credentials were exposed.
- [ ] API compatibility with frontend callers was preserved.
- [ ] Docs were updated when behavior/config/API changed.
- [ ] Organizer-facing claims match what is actually implemented and measured.
- [ ] The complete diff was self-reviewed.

When finishing, report:

1. what changed,
2. tests actually run,
3. API/database/config impact,
4. demo impact,
5. remaining human/legal/organizer validation.

---

## 21. Immediate project action order

Unless the user explicitly reprioritizes, the current order is:

### P0 — submission survival

1. Finish the own-feed demo video.
2. Fix incorrect organizer-facing claims, especially claims that understate existing Gujarat capabilities.
3. Revalidate/remove any headline ANPR result that does not exist in the current database/evidence.
4. Confirm or demonstrate the Model 2 two-system requirement.
5. Verify all mandatory submission artifacts and links.

### P1 — strongest new value

6. Implement evidence hash-at-write + model/software version stamping.
7. Implement §63-oriented evidence package export with tests and conservative wording.
8. Implement camera ANPR-suitability scoring and surface it on GIS/registry/health views.
9. Implement CONFIRMED / PROBABLE / LEAD ONLY enforcement in UI/API/export paths.

### P2 — operational differentiation

10. Add an integration-loss/data-flow dashboard using real instrumented stages only.
11. Tighten normalized cross-vendor event schema/documentation.
12. Polish system health and real-vs-stub visibility.
13. Rehearse the jury workflow and re-record the demo if needed.

### Deferred

- Re-ID model improvement,
- additional anomaly models,
- full production license-stack swap,
- full statewide infrastructure deployment,
- superficial 80k-camera load testing,
- face recognition,
- convoy analysis,
- new VMS implementation.

---

## 22. Default jury narrative

When the implementation and evidence support it, the default narrative is:

> **Gujarat already has cameras, VMS and ANPR. Sentinel does not replace them. It provides an open operational layer that makes heterogeneous systems interoperable, tells departments whether a camera is actually fit for analytics, records why an AI-derived link was made, refuses to present weak inference as fact, and packages evidence with provenance and auditability for downstream legal review.**

Every demo feature should support that story.

---

## 23. Agent operating protocol — mandatory execution loop

These rules exist to keep an AI coding agent focused under hackathon time pressure.
They apply to every non-trivial code, documentation, configuration, data, or UI change.

### 23.1 Source-of-truth hierarchy

When information conflicts, use this order and report the conflict instead of silently choosing:

1. **Official hackathon rules / organizer clarification** — defines what must be delivered.
2. **`docs/strategy/STRATEGY.md` + latest decision review** — defines the currently approved product direction and scope.
3. **Running code, database state, and tests actually executed** — defines what is implemented/proven.
4. **`docs/hackathon/TASKS.md`** — defines planned/current work status, but may lag code.
5. **HLD/README/submission docs** — describe intended/current behavior and must be corrected if stale.
6. **Comments, old prompts, archived files, screenshots, prior chat memory** — lowest authority.

Never let stale prose override current runtime evidence.
Never let current code override an explicit mandatory hackathon requirement.

### 23.2 Start every task with a preflight

Before editing anything:

1. Read the files required at the top of this `CLAUDE.md`.
2. Run `git status --short` and note existing user changes.
3. Identify the exact requirement being changed.
4. State the acceptance criteria in one short checklist.
5. Locate the current implementation and relevant tests before proposing new files.
6. Check whether the task is P0/P1/P2/Deferred in this file or `TASKS.md`.
7. Check whether the task changes an organizer-facing claim, evidence classification, DB schema, external integration, license posture, or security boundary.
8. If it conflicts with the current strategy, stop and tell the user before implementing.

Do not begin a broad repository exploration after you already have enough context to make the requested targeted change.

### 23.3 One task, one objective

A task should have one primary outcome.

Do not combine, unless technically inseparable:

- feature work + unrelated refactor,
- bug fix + dependency upgrade,
- UI redesign + backend rewrite,
- docs correction + architecture migration,
- test cleanup + new feature,
- formatting the whole repository + a focused code change.

If unrelated improvements are discovered, record them in `TASKS.md` only when useful; do not implement them opportunistically.

### 23.4 Plan before implementation

For a non-trivial change, state internally or to the user as appropriate:

- requirement,
- files likely to change,
- API/DB/config impact,
- security/privacy/evidence impact,
- test plan,
- rollback/failure risk.

Prefer modifying existing seams over creating parallel abstractions.

### 23.5 Implementation sequence

Use this sequence unless there is a strong reason not to:

1. reproduce/inspect current behavior,
2. add or update the smallest relevant test,
3. make the minimal implementation change,
4. run targeted tests,
5. exercise the runtime path,
6. run the broader relevant suite,
7. update docs/status,
8. inspect `git diff`,
9. report what is proven and what is not.

Do not mark a task complete because code "looks correct".

---

## 24. Expanded coding rules

### 24.1 Minimal-diff rule

Prefer the smallest correct patch.

Do not:

- rewrite a module merely to make it cleaner,
- rename working APIs without a requirement,
- move files for aesthetics,
- replace libraries because another library is more fashionable,
- convert JavaScript to TypeScript,
- introduce frameworks or architectural layers for future possibilities,
- perform repository-wide formatting during a functional task.

Large refactors require explicit user approval.

### 24.2 Preserve public contracts

Treat existing API response fields, status codes, query parameters, component props, DB columns, and stored event semantics as contracts.

Before changing one:

- find all backend callers,
- find all frontend callers,
- check tests and docs,
- preserve backwards compatibility where practical,
- document any intentional breaking change.

Never silently rename a field because the new name seems better.

### 24.3 Database safety

For any schema change:

- modify the SQLAlchemy model,
- add the matching additive migration in the existing migration mechanism,
- test startup against an existing database,
- preserve accumulated `sentinel.db` data,
- use nullable/default-compatible additions where possible,
- never solve a migration problem by deleting/recreating the database.

Do not drop columns/tables or rewrite stored evidence without explicit approval and a migration plan.

### 24.4 Evidence data is append-sensitive

For evidence/provenance records:

- preserve original timestamps,
- preserve original hashes,
- preserve original model/software version information,
- do not overwrite the reason a prior link/decision was made with a later value,
- store decision-time provenance before mutable identity state changes,
- distinguish corrections/amendments from original evidence.

If a field is needed for legal/audit traceability, prefer append-only history over destructive update.

### 24.5 No demo-only lies

Never hard-code or fake:

- a known plate number,
- a successful watchlist hit,
- camera health,
- an alert,
- a model confidence,
- a cross-camera path,
- an evidence hash,
- a timestamp,
- an integration success count,
- a system/source label,
- a production metric.

Synthetic fixtures are allowed only in tests or clearly labelled demo/test mode.

Do not weaken validation thresholds merely to make one demo sample pass without documenting and justifying the change.

### 24.6 Experimental features must be isolated

Anything not validated enough for operational use must be clearly marked in code/API/UI as experimental when exposed.

Examples:

- appearance-only cross-camera Re-ID,
- heuristic camera suitability components without validated thresholds,
- prototype legal/evidence export paths pending legal review,
- mocked-only ONVIF behaviors.

Experimental outputs must not silently feed confirmed evidence or high-severity alerts.

### 24.7 Error handling

Do not swallow exceptions with broad `except Exception: pass` or convert failures into fake success.

For recoverable external failures:

- log a safe error,
- return/record an explicit degraded state,
- retry only where bounded/backoff behavior is appropriate,
- preserve enough context for diagnosis without exposing secrets.

For programmer errors/invariants, fail clearly rather than silently continuing with corrupted state.

### 24.8 Logging rules

Logs should help operate the system without becoming a privacy/security leak.

Never log:

- passwords,
- API keys,
- raw credential-bearing RTSP/WHEP URLs,
- cookies/session tokens,
- complete sensitive evidence payloads unless the design explicitly requires it,
- unnecessary personal data.

Prefer stable IDs and structured context:

- `camera_id`,
- `department_id`,
- `event_id`,
- `case_id` where authorized,
- integration/source name,
- safe error category.

### 24.9 Timestamp rules

Do not mix timing concepts.

- stream-relative motion/tracking timing: use the existing PTS-based rules,
- system/audit/evidence timestamps: use a consistent timezone-aware representation,
- cross-camera comparison: use the documented common event-time authority,
- do not assume arrival time equals capture time,
- preserve source timestamp and ingest timestamp separately if/when the schema supports both.

Never fabricate ordering across cameras from per-stream PTS alone.

### 24.10 URL / stream / SSRF safety

Any backend feature that fetches remote URLs, playlists, redirects, snapshots, or streams must:

- validate schemes,
- enforce allowlists or trusted source policy where applicable,
- handle redirects safely,
- prevent credential leakage,
- avoid exposing internal network targets,
- preserve the existing HLS proxy security boundary.

Do not add generic "fetch arbitrary URL" endpoints.

### 24.11 Frontend truthfulness

The frontend must not display a capability as healthy/active merely because a component exists in code.

Where relevant show runtime state such as:

- real model vs stub,
- connected vs reconnecting,
- tested vs unverified integration,
- CONFIRMED / PROBABLE / LEAD ONLY,
- OBSERVED / INFERRED,
- last successful event time,
- unavailable/degraded dependency.

A polished UI must not conceal degraded backend state.

### 24.12 Scale-aware frontend rules

Do not design client behavior that assumes all statewide data fits in the browser.

For camera/event lists and maps prefer:

- server-side filtering,
- server-side pagination,
- map clustering,
- bounded result windows,
- explicit time ranges,
- on-demand video playback,
- drill-down state -> district -> department -> camera.

Do not fetch/render tens of thousands of full camera/event records merely to filter them client-side.

### 24.13 Dependency policy

Before adding any new runtime dependency:

1. verify it solves a current approved requirement,
2. check maintenance/activity,
3. check license,
4. check platform support,
5. check package size/runtime impact,
6. prefer an existing dependency when it already solves the need,
7. pin/version it consistently with the repo,
8. document config/operational impact,
9. re-run affected tests.

Do not add AGPL/copyleft inference dependencies without explicit approval and documented procurement implications.

### 24.14 ML/model changes

Any model or preprocessing change must be treated as a behavior change.

Record:

- model name/version/checksum where practical,
- preprocessing change,
- threshold change,
- dataset/sample used for validation,
- before/after measurements if available.

Do not carry accuracy claims from an old model to a new model.
Do not call a confidence score a calibrated probability unless calibration was actually performed.

### 24.15 Test quality

Tests must validate behavior, not implementation trivia.

Prefer tests for:

- acceptance criteria,
- bad input,
- duplicate input,
- authorization boundaries,
- external failure/degraded mode,
- idempotency where applicable,
- evidence tier transitions,
- retention/deletion behavior,
- API compatibility.

Do not delete or weaken a failing test simply because the feature changed; update it only when the requirement intentionally changed.

### 24.16 Security changes require explicit review

For changes touching auth, RBAC, credentials, evidence access, audit logs, external URLs, uploads, or admin endpoints, explicitly check:

- authentication,
- authorization,
- object-level scope,
- input validation,
- secret exposure,
- auditability,
- retention/privacy impact,
- error information leakage.

Security regressions are submission blockers.

---

## 25. Expanded Git and worktree rules

These rules are mandatory because the repository may contain uncommitted user work and real accumulated pilot data.

### 25.1 Never destroy user work

Never run destructive history/worktree commands without explicit user approval, including:

- `git reset --hard`,
- `git clean -fd` / `git clean -fdx`,
- `git checkout -- <file>` on user-modified files,
- `git restore --source=...` over user changes,
- `git rebase` on shared/published work,
- `git push --force` / `--force-with-lease`,
- deleting branches with unmerged work.

If the worktree is dirty, inspect it and work around unrelated changes rather than overwriting them.

### 25.2 Always inspect status before and after

At the start of implementation run:

```bash
git status --short
```

Before reporting completion run at minimum:

```bash
git status --short
git diff --stat
git diff
```

Use `git diff --staged` as well if the user explicitly asked you to stage/commit.

### 25.3 Do not perform Git mutations without permission

Unless the user explicitly asks, do **not**:

- create/switch a branch,
- stage files,
- commit,
- push,
- create a PR,
- merge,
- tag,
- create a release,
- delete branches.

Code editing itself does not imply permission to commit or push.

### 25.4 Branching when authorized

When explicitly authorized to create a branch:

- branch from the intended current base,
- verify the base first,
- use `feature/<short-description>`, `fix/<short-description>`, or `docs/<short-description>`,
- avoid branch names that imply an issue number when no issue exists,
- do not mix unrelated tasks in one branch.

### 25.5 Staging when authorized

Prefer staging explicit files over `git add .`.

Before any broad stage operation, verify that none of these are included:

- `.env`,
- `sentinel.db`,
- model weights (`*.pt`, `*.onnx`, etc.),
- credentials/cookies,
- generated evidence,
- demo output,
- large temporary media,
- local IDE/cache files,
- minted API keys.

If a secret is accidentally staged, unstage it and notify the user; do not commit it and then rely on deleting it later.

### 25.6 Commit rules when authorized

Commits should be small enough to review and complete enough to build/test.

Good examples:

- `fix: prevent lead-only evidence export`
- `feature: add camera ANPR suitability score`
- `docs: correct existing VISWAS capability claims`

Do not use vague commits such as `changes`, `updates`, `fix stuff`, or one giant commit covering several unrelated outcomes.

Never claim tests in a commit message/PR description unless they were actually run.

### 25.7 PR rules when authorized

A PR description must state:

- problem/requirement,
- what changed,
- why this design was chosen,
- tests actually run and outcomes,
- API/DB/config changes,
- security/privacy/evidence impact,
- demo impact,
- remaining limitations/manual verification.

Before calling a PR ready, self-review the full diff.

### 25.8 Merge/release rules when authorized

Do not merge simply because local tests pass.

Check:

- mandatory acceptance criteria,
- docs synchronization,
- no secret/generated file inclusion,
- clean intended diff,
- known limitations disclosed.

Tags/releases must be created only from the intended merged branch and only when explicitly requested.

---

## 26. Documentation and evidence synchronization

Code, task status, HLD, and organizer-facing claims must not drift apart.

When behavior changes, update the smallest relevant set of:

- `sentinel-solution/README.md`,
- `sentinel-solution/docs/HLD.md`,
- `docs/hackathon/TASKS.md`,
- `docs/hackathon/REQUIREMENTS_COVERAGE.md`,
- organizer-facing briefing/demo material,
- scalability document if a scale assumption changed.

Use the following evidence vocabulary consistently:

- **LIVE/REAL VERIFIED** — observed on real permitted runtime input.
- **AUTOMATED-TEST VERIFIED** — tests passed, but not field evidence.
- **MOCKED/SYNTHETIC VERIFIED** — behavior verified only with controlled fake input.
- **IMPLEMENTED, UNVERIFIED** — code exists but no sufficient execution proof.
- **DESIGN TARGET** — documentation/architecture only.
- **NOT IMPLEMENTED** — absent.
- **EXTERNALLY BLOCKED** — implementation may exist, but an external dependency/access prevents validation.

Never collapse these categories into "working".

When a measured number is shown, record enough context to reproduce it:

- sample/source,
- time/date where relevant,
- metric definition,
- threshold/config,
- script/test used,
- whether it is real/synthetic/project-reported.

---

## 27. Stop-and-ask conditions

Stop implementation and ask the user before proceeding when any of these are required:

- deleting or rewriting accumulated real pilot data,
- destructive DB migration,
- architectural deviation from current strategy,
- adding a new external paid/cloud service,
- using production/government credentials not already authorized,
- changing legal/compliance claims from conservative to definitive,
- introducing AGPL/copyleft production dependencies,
- replacing the core ML stack before submission,
- changing a mandatory hackathon interpretation,
- fabricating/relabeling data to satisfy the two-system requirement,
- weakening auth/RBAC/retention/evidence controls,
- committing/pushing/merging/tagging/releasing,
- large refactor with no direct acceptance-criteria value.

If blocked by an external system, report the blocker and continue only with work that does not pretend the external validation occurred.

---

## 28. Agent anti-drift checklist

During implementation, periodically ask:

1. Does this directly help a mandatory requirement, current P0/P1 item, or approved differentiator?
2. Am I improving a real vertical slice or just increasing feature count?
3. Am I about to duplicate something Gujarat already has and call it innovation?
4. Am I turning an inference into a fact?
5. Am I adding infrastructure instead of finishing the demo?
6. Am I changing more files than necessary?
7. Am I relying on a document claim instead of runtime evidence?
8. Am I introducing a new license/security/privacy risk?
9. Can the jury see and understand the value in under two minutes?
10. Can I prove what I am about to claim?

If several answers are unfavorable, stop and re-scope before writing more code.

---

## 29. Definition of done for a feature

A feature is not done until all applicable items are true:

- acceptance criterion is satisfied,
- code is wired into the real runtime path,
- failure/degraded path is handled,
- authorization and input validation are correct,
- tests are added/updated and executed,
- frontend/backend contract is verified,
- DB migration is safe if applicable,
- user-visible state is truthful,
- docs/task status are synchronized,
- no stale organizer-facing claim remains,
- complete diff was reviewed,
- known limitations are explicitly documented.

A prototype that only works through a one-off script is not equivalent to a wired application feature.

---

## 30. Required end-of-task handoff format

At the end of every implementation task, report in this order:

### Changed
- exact behavior changed,
- primary files touched.

### Verified
- tests/commands actually run,
- runtime/manual checks actually performed,
- real vs mocked/synthetic verification clearly labelled.

### Contracts / data
- API changes,
- DB/migration changes,
- config/env changes,
- dependency/license changes.

### Security / evidence / privacy
- authorization impact,
- credential exposure check,
- evidence-tier/provenance impact,
- retention/legal-review impact.

### Still open
- external validation,
- organizer clarification,
- legal review,
- field test,
- known limitation.

### Git state
- branch name if one was explicitly authorized,
- whether changes are uncommitted/staged/committed,
- PR/release state only if explicitly requested.

Never end with only "done" or "all tests pass".

---

## 31. Current strategic guardrail in one sentence

When uncertain what to work on, optimize for this:

> **Finish and prove the mandatory multi-system workflow, then strengthen interoperability, camera readiness, evidence provenance, governance, and truthful confidence handling — do not spend scarce time trying to turn experimental appearance-based Re-ID into the project's headline.**
