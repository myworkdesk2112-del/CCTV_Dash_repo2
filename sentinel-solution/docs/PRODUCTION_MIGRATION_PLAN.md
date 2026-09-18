# Production Migration Plan

**Status: DESIGN TARGET — not started, not to be attempted before the
hackathon submission (28 September 2026) or the Grand Finale (12–13
October 2026).** This document exists so "go to production" has a
concrete, reasoned plan behind it, not so the plan gets built under
demo-deadline pressure. See `CLAUDE.md` §7/§27: adding Docker/Kafka/
Redis/Kubernetes/Postgres/CI "to match reference stacks" before the
submission deadline is an explicit do-not-build item, precisely because a
half-migrated stack is worse than the current working pilot.

Distinct from `SCALABILITY.md`: that document argues the *statewide,
80,000-camera* scaling story for organizer evaluation. This document is
the concrete engineering path from "hackathon pilot, SQLite, one process,
demo shortcuts" to "a real deployment a department could actually run,"
independent of statewide scale. Read both; they answer different
questions.

## 0. Preconditions before starting any of this

- Hackathon submission is in, Grand Finale is done, and there is no live
  demo left to risk breaking.
- A named person owns each phase below (this is not a solo weekend
  project once Phase 2 starts).
- Every phase ends with the existing 162-test backend suite (plus new
  tests for that phase) passing, and a rollback plan if it doesn't.

## 1. Current pilot shortcuts, named honestly

These are the actual gaps between "hackathon pilot" and "production,"
gathered from `REVIEW_FINDINGS.md`, `MODULE_GAP_ANALYSIS.md`, and this
session's backend review (`codereview.md`):

| Area | Pilot state | Production gap |
|---|---|---|
| Database | SQLite, hand-rolled additive migrations in `db/session.py`, no Alembic | PostgreSQL + PostGIS, proper migration tooling, replica/backup story |
| Auth | Single static API key per header (`X-Sentinel-API-Key`), stored in browser `localStorage` (`frontend/src/api.js`) | Session-based auth (httpOnly cookie + CSRF), key rotation, no long-lived secret sitting in JS-readable storage — flagged as `SEC-4` in `REVIEW_FINDINGS.md`, deliberately deferred |
| Deployment | Single Python process (`python -m app.main`), no containers, no orchestration | Containerized services, CI-built images, a real deploy pipeline |
| Event bus | Polled `FederatedEvent` table (Model 3), 60–120s poll intervals | Kafka/RabbitMQ or equivalent for near-real-time federation at scale (already the documented Model 3 target, not built) |
| Streaming worker robustness | `RtspCameraWorker.stop()`'s thread join can linger up to ~30s if stuck inside a blocking `cv2.VideoCapture` open against an unreachable host (`SWE-6`, `REVIEW_FINDINGS.md` Tier 3 — bounded, not a leak, but not hardened) | Per-camera worker isolation (subprocess or container) so a stuck open can be hard-killed, not just outlived |
| ML licensing | Plate localizer uses `morsetechlab/yolov11-license-plate-detection`, **AGPL-3.0** — accepted for the pilot (`HLD.md` §10) | Needs a real make/no-make call before procurement: stay AGPL (viral-copyleft implications for a government deployment) or fund/find a permissively-licensed replacement and re-validate accuracy |
| ML validation | No held-out precision/recall table; `EMBEDDING_SIMILARITY_THRESHOLD=0.80` has no empirical basis (`ML-3`/`ML-4`, still open in `REVIEW_FINDINGS.md`) | Labeled real-footage evaluation set, measured precision/recall, a justified similarity threshold |
| Secrets | Sandbox access token/email, ONVIF credentials, DB URL all read from plain env vars (`config.py`) | Secrets manager (Vault/cloud KMS/sealed secrets), not `.env` files on a host |
| Observability | `logging.basicConfig` to stdout, no metrics/tracing | Structured logs shipped somewhere queryable, metrics (Prometheus-style) on stream health/analytics-degraded/queue depth, alerting |
| CI | None | Lint + test on every PR at minimum; ML-stack test run is a separate, slower concern (GPU or accept a slow CPU fallback) |

## 2. Phase plan

### Phase 1 — Data layer (PostgreSQL + PostGIS)

**Progress (2026-09-17, Model 1 only): steps 1–3 below are done and
LIVE/REAL VERIFIED against actual PostgreSQL 16.4 — see
`MODEL1_MIGRATION_SCOPE.md` §§8–9.** A real Postgres instance was run in
this environment without admin rights (EnterpriseDB's no-installer ZIP
distribution), and the full application was started against it and
driven through Model 1's entire API live (onboarding, the new
maintenance-status endpoint, gap-analysis, CSV/PDF export, audit trail).
The additive-migration `ALTER TABLE` dialect fix was also proven for
real, not just reasoned about, by dropping columns and confirming
`init_db()` correctly re-added them with the right Postgres types/defaults.
Step 4 (the PostGIS geometry-column rewrite) is not started — see below.

1. Stand up Postgres + PostGIS locally, adopt Alembic (replacing the
   hand-rolled `_ADDITIVE_MIGRATIONS` list in `db/session.py` — that
   mechanism was a deliberate, documented hackathon-scope choice per
   `CLAUDE.md` §13, not an oversight, so this is an explicit, approved
   supersession, not a silent one).
2. Write a one-time data-migration script: read every table out of the
   real `sentinel.db`, write it into Postgres, verify row counts and spot
   checks match. **The real accumulated pilot database is valuable
   evidence data — this must be a copy, never a destructive move**, per
   `CLAUDE.md` §15.7/§24.3.
3. Re-run the full backend test suite against Postgres (swap
   `DATABASE_URL`, nothing else) — this is the actual test of whether the
   SQLAlchemy layer was written portably. Fix any dialect-specific
   assumption that surfaces (e.g., SQLite's permissive typing).
4. Only after 1–3 are green: migrate `CameraRegistry.lat`/`lon` to a real
   PostGIS geometry column, updating the gap-analysis/coverage-radius
   queries that currently do their own haversine math in Python
   (`analytics/geo.py`) to use PostGIS operators — this is where the real
   payoff of PostGIS shows up, not just "a bigger SQLite."

### Phase 2 — Containerization

1. `Dockerfile` for the backend (Python 3.11, pinned `requirements.txt` +
   `requirements-ml.txt`), one for the frontend (static build served
   behind a real web server, not Vite's dev server).
2. `docker-compose.yml` for a local production-like stack: backend,
   frontend, Postgres. **RTSP/ONVIF networking is the real risk here** —
   host cameras are reached over the host's network, not a Docker bridge
   network, by default. Plan for `network_mode: host` (Linux-only,
   simplest) or an explicit macvlan/bridge setup with tested UDP/TCP
   passthrough for RTSP (port 8554) and ONVIF discovery (WS-Discovery is
   multicast — it does not cross a default bridge network without extra
   configuration). Test this against a real camera before trusting it.
3. GPU passthrough for the YOLOv8/PaddleOCR stack if deployed with GPU
   acceleration — `nvidia-container-toolkit`, verified against the actual
   target hardware, not assumed.

### Phase 3 — CI/CD

1. Lint + backend test suite (`pytest`) on every PR — fast, no GPU
   needed, matches what's already run manually today.
2. A separate, slower ML-validation job (real detector/OCR/tracker
   integration tests) — CPU-only is acceptable if slow; don't block every
   PR on it.
3. Build + push Docker images on merge to a release branch; deploy is a
   manual/approved step, not automatic, given this handles police
   investigative data.

### Phase 4 — Auth hardening (SEC-4)

This is the one item here that's a genuine **architecture change**, not
just infrastructure — flagged per `CLAUDE.md` §27 as requiring explicit
review before implementation, same as it would if attempted now.

1. Replace the static `X-Sentinel-API-Key` + `localStorage` pattern with
   session-based auth: login endpoint issues an httpOnly, `Secure`,
   `SameSite=Strict` cookie; every mutating request requires a CSRF token
   pulled from a non-httpOnly cookie/meta tag (double-submit pattern) or
   equivalent.
2. Decide up front whether departmental users authenticate against a
   real identity provider (SSO/LDAP/existing Gujarat Police credential
   system) rather than a Sentinel-local user table — this is a real
   product decision, not just an implementation detail, and changes the
   shape of `ApiKeyEntry`/`Principal` significantly.
3. Re-run every existing RBAC/department-scope test against the new auth
   mechanism; add session-fixation/CSRF-bypass tests that didn't need to
   exist under the old header-key model.

### Phase 5 — Streaming worker robustness (SWE-6)

1. Move each `RtspCameraWorker` into its own OS process (not just a
   thread) so a stuck blocking `cv2.VideoCapture` open can be hard-killed
   by the supervisor without waiting out FFmpeg's own ~30s internal
   timeout.
2. This is also the natural point to implement real horizontal scaling —
   workers distributed across multiple machines behind a shared
   catalogue/registry, rather than one process owning every camera —
   which `SCALABILITY.md` already argues for at statewide scale but the
   pilot doesn't need at ~30 cameras.

### Phase 6 — ML licensing and validation

1. Get an explicit answer (legal/procurement, not engineering) on whether
   AGPL-3.0 in the plate-localizer path is acceptable for a real
   government deployment. If not, source or fund a permissively-licensed
   replacement and **re-validate accuracy from scratch** — per
   `CLAUDE.md` §16/§24.14, a swapped model's accuracy claims never
   transfer from the old model.
2. Build the labeled real-footage evaluation set `ML-3`/`ML-4` in
   `REVIEW_FINDINGS.md` call for; report actual precision/recall; justify
   `EMBEDDING_SIMILARITY_THRESHOLD` empirically instead of as a
   hand-picked default.
3. **Candidate ANPR accuracy upgrade (proposed 2026-09-18, not started,
   not approved for pre-submission work — see `CLAUDE.md` §4.1/§7/§31):**
   an external suggestion (OpenCode) proposed replacing the current
   `StubPlateDetector`/`PaddleOCR` path with a four-stage pipeline —
   Indian-plate-fine-tuned YOLOv8/11 localizer, an STN/TPN perspective
   rectifier, a CRNN or transformer recognizer trained on
   CCPD/UFPR-ALPR + synthetic Gujarat plates, and a temporal-fusion
   (attention-over-track) consensus step in place of `consensus_plate()`'s
   position-wise voting. It targets today's known weaknesses honestly:
   heuristic bottom-30% plate cropping, no perspective correction, and
   single-frame OCR consensus. Before picking this up:
   - `ultralytics` (YOLOv8/11) is AGPL-3.0 by default — needs the same
     legal/procurement sign-off as item 1 above, or a permissively
     licensed detector instead.
   - No labeled Indian-plate training set or GPU training loop exists
     in this repo yet; the "expected accuracy gains" numbers in the
     original suggestion are illustrative, not measured — per
     `CLAUDE.md` §24.14, no accuracy claim may be made until validated
     on a defined dataset.
   - This is exactly the kind of "new ANPR research contribution" and
     "new Re-ID/embedding" work `CLAUDE.md` §4.1/§7 says not to start
     before submission; only pick it up as part of a real post-hackathon
     production hardening pass, and re-run this file's Phase 6 process
     (legal sign-off, then real precision/recall) rather than trusting
     the proposal's numbers.

### Phase 7 — Secrets and observability

1. Move `SENTINEL_ACCESS_TOKEN`/`SENTINEL_ACCESS_EMAIL`, ONVIF
   credentials, and the database URL out of plain environment variables
   into a secrets manager appropriate to the deployment target.
2. Structured logging shipped to a queryable store; metrics on
   `analytics_degraded` count, stream reconnect rate, federation
   ingest lag, retention-purge outcomes; alerting on sustained
   degradation (the existing `/health` distinction between "connected"
   and "analytics degraded," found the hard way on 2026-09-13, is exactly
   the signal to alert on).

## 3. Explicit non-goals for this plan

Per `CLAUDE.md` §7/§28, this plan does not include, and should not grow
to include without a fresh explicit decision:

- Face recognition, convoy/associate analysis, a new Re-ID model.
- Replacing the incumbent departmental VMS/building a new VMS.
- Cloning VAHAN/SARTHI integrations without real access/authorization.
- A real 80,000-camera load test (that stays a documented projection in
  `SCALABILITY.md`, not an actual test run, until statewide deployment is
  actually being planned).

## 4. What changed this session (2026-09-17)

Nothing in this plan was implemented today. What *was* done today,
separately, under the agreed "harden what exists, don't touch
infrastructure before the deadline" scope:

- A full backend bug-fix pass — see `codereview.md` (9 real bugs fixed,
  162/162 tests passing, no architecture change).
- This document.

The two items in the gap table above that are genuine hardening
candidates but were deliberately **not** attempted today —
`SWE-6` (bounded RTSP worker stop) and `SEC-4` (auth mechanism) — are
carried into Phases 4 and 5 above rather than rushed now: `SWE-6` needs
process-level isolation to fix properly (a bigger change than a quick
patch, and untestable here without a real unreachable-RTSP-host
scenario), and `SEC-4` is an auth architecture change that needs the
same explicit sign-off this plan itself required.

## 5. What changed 2026-09-18 — user explicitly requested full production
   rearchitecture despite the deadline

Per an explicit user decision (confirmed after two rounds of warning
about the 2026-09-28 deadline and this environment's lack of Docker/
Kubernetes/cloud access — see `docs/PRODUCTION_READINESS.md` for the
full record), real Phase 1/2/3/4/7 artifacts were written this session:

- Phase 1: `backend/app/analytics/vector_search.py` (pgvector ANN
  candidate search, not wired into `identity.py`'s default path).
- Phase 2: `infra/docker/Dockerfile.{backend,frontend}`,
  `infra/docker-compose.production.yml`, `infra/k8s/*.yaml`.
- Phase 3: `.github/workflows/{backend,frontend}-ci.yml`.
- Phase 4 (partial — the OIDC mechanism only, not the cookie/CSRF
  replacement of the API-key header, which is the harder, riskier half
  of this phase): `backend/app/api/sso_oidc.py`, additive to the
  existing `auth.py`.
- Phase 7 (partial — TLS template + secrets-manager interface doc, not
  a real observability pipeline): `infra/nginx/nginx.conf.example`,
  `infra/k8s/secret.example.yaml`.
- Also (Model 3's regional-scale event bus, not in this plan's original
  phase list but named in `SCALABILITY.md` §6): `backend/app/analytics/
  kafka_bus.py`.

**All of it is `DESIGN TARGET` or `IMPLEMENTED, UNVERIFIED`** — see
`PRODUCTION_READINESS.md` for the gap-by-gap table and exactly what was
and wasn't verified. Nothing here changed the pilot's actual runtime
behavior: all new backend modules are lazy-imported and feature-flagged
off by default, and the full 199-test backend suite was re-run after
adding them with zero regressions. Not attempted: `SEC-4`'s actual
cookie/CSRF auth replacement, `SWE-6`'s process isolation, any real ML
validation, and anything requiring an actual Docker/Kubernetes/Kafka/
pgvector/OIDC instance to exercise for real — none of that
infrastructure exists in this environment.
