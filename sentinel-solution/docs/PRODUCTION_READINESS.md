# Production Readiness — status table and artifact map

**Written 2026-09-18, at the user's explicit request to pursue full
production hardening despite the 2026-09-28 submission deadline (see
`CLAUDE.md` §7/§27's normal guidance against this, and the conversation
where this was confirmed after two explicit warnings).** This document
is the honest scorecard for that work: for every gap
`PRODUCTION_MIGRATION_PLAN.md` and `SCALABILITY.md` already named,
where's the artifact, and what's its real verification status.

**Environment constraint, checked this session:** this machine has no
Docker, no `kubectl`, no Helm, and no cloud credentials (`which docker
kubectl helm` all fail). Nothing below that needs those could be
deployed or tested here. Every such item is labeled `DESIGN TARGET` and
must be actually run somewhere with real infrastructure before any
stronger claim is made — see `infra/README.md`'s explicit checklist.

Status vocabulary matches `CLAUDE.md` §26:
- **LIVE/REAL VERIFIED** — observed on real permitted runtime input.
- **AUTOMATED-TEST VERIFIED** — tests passed, not field evidence.
- **IMPLEMENTED, UNVERIFIED** — code exists, no sufficient execution proof.
- **DESIGN TARGET** — documentation/architecture only.

## Gap-by-gap status

| Gap (from `PRODUCTION_MIGRATION_PLAN.md`/`SCALABILITY.md`) | Artifact | Status |
|---|---|---|
| Database: SQLite → PostgreSQL + PostGIS | Already done for Model 1, see `MODEL1_MIGRATION_SCOPE.md` §§8–9 | **LIVE/REAL VERIFIED** (pre-existing, not new this session) |
| Re-ID candidate search at scale (brute-force → ANN) | `backend/app/analytics/vector_search.py` — pgvector HNSW index + cosine-distance query, `is_available()` capability check, NOT wired into `identity.py`'s default resolve path | **IMPLEMENTED, UNVERIFIED** — no pgvector instance in this environment; module imports cleanly and full 199-test suite still passes with it present, but its actual query path was never executed against a real Postgres |
| Event bus: polled table → Kafka | `backend/app/analytics/kafka_bus.py` — `FederationEventProducer`/`FederationEventConsumer`, lazy-imports `kafka-python`, NOT wired into `main.py`'s default `federation_ingest_loop` | **IMPLEMENTED, UNVERIFIED** — no Kafka broker in this environment; never connected to a real broker |
| Auth: static API key → SSO/OIDC | `backend/app/api/sso_oidc.py` — `get_principal_oidc()` dependency, additive to `auth.py`'s existing `get_principal`, disabled by default | **IMPLEMENTED, UNVERIFIED** — no real OIDC provider configured/reachable; JWKS fetch and signature verification paths have never executed against a live issuer |
| Auth: `localStorage` API key → httpOnly cookie + CSRF (`SEC-4`) | `backend/app/api/session_auth.py` (`SessionToken` model, `POST /auth/session/{login,logout}`, double-submit CSRF, wired into the retention sweep) merged into `auth.get_principal` itself (header key checked first, session cookie as fallback) — so **every existing real route** (`require_role`/`get_principal`-based) now accepts either, with zero route-level changes. Frontend (`api.js`, `Topbar.jsx`, `LiveView.jsx`) migrated to cookies: `localStorage`/`X-Sentinel-API-Key` removed entirely from the frontend, replaced with `credentials: "include"` + a CSRF header read from a non-httpOnly cookie | **AUTOMATED-TEST VERIFIED (backend)** — 16 tests in `tests/test_session_auth.py`, including 6 that exercise the merged fallback through `auth.require_role` on synthetic routes standing in for real ones (proves the *production* dependency chain, not just the isolated module). Full suite 222/222. **Frontend: IMPLEMENTED, UNVERIFIED** — this environment's Node (v22.11.0) is below the `>=22.12.0` oxlint/rolldown/vite native-binding requirement; the winget upgrade to 22.23.2 was attempted but the UAC elevation prompt cannot reach this session's desktop, so it could not be completed here. Per the user's explicit decision (2026-09-18b), `npm run lint`/`npm run build` and an in-browser click-through of sign-in/sign-out/live-view will be run on a different machine instead. The JSX was self-reviewed line-by-line here (checked: no raw unauthenticated `<img src>`/`<video src>` paths — `eventCropUrl`/`hlsUrl`/`whepUrl` all route through credentialed fetch/XHR paths, confirmed by grepping every usage site) — that is not a substitute for an actual lint/build/browser verification, which remains the next required step before this is trusted |
| DR: manual `sqlite3 .backup` shell command → automated backup/verify/restore | `backend/scripts/backup_restore_sqlite.py` | **AUTOMATED-TEST VERIFIED** (2026-09-18b) — 7 real tests (`tests/test_backup_restore.py`) against real on-disk SQLite files: online backup API, SHA-256 manifest, retention pruning, corrupted-file rejection, restore-refuses-to-overwrite, restored copy is independently verified working. Still explicitly not multi-region/HA — see `DR_RUNBOOK.md`'s "Not implemented" section, unchanged |
| Containerization | `infra/docker/Dockerfile.backend`, `Dockerfile.frontend`, `infra/docker-compose.production.yml` | **DESIGN TARGET** — never built (`docker build`/`docker compose up` not run; no Docker here) |
| Kubernetes orchestration | `infra/k8s/*.yaml` (namespace, configmap, secret template, backend deployment+service+HPA, postgres statefulset, TLS ingress) | **DESIGN TARGET** — YAML syntax validated with PyYAML this session (all 7 files parse), never applied to a real cluster |
| TLS everywhere | `infra/nginx/nginx.conf.example` | **DESIGN TARGET** — template only, certificate paths/hostname are placeholders |
| CI/CD | `.github/workflows/backend-ci.yml`, `frontend-ci.yml` | **DESIGN TARGET** — YAML syntax validated with PyYAML, never actually triggered by a GitHub Actions runner |
| Streaming worker robustness (`SWE-6`, per-camera process isolation) | Not built this session — still open, see below | **NOT IMPLEMENTED** (unchanged) |
| ML licensing (AGPL-3.0 plate localizer) decision | Not a coding task — still an open procurement/legal decision, unchanged | **NOT IMPLEMENTED** (unchanged) |
| ML validation (`ML-3`/`ML-4` precision/recall) | Not built this session — needs real labeled data, unchanged | **NOT IMPLEMENTED** (unchanged) |
| Secrets management | `infra/k8s/secret.example.yaml` documents the interface; explicitly recommends External Secrets Operator / Vault over a bare k8s Secret | **DESIGN TARGET** — no secrets manager wired up, this is a placeholder/interface doc |
| Govt-DB query integration (VAHAN/SARTHI/eGujCop/CCTNS-AFIS-NAFIS), 2026-09-28 | `backend/app/analytics/govt_db_adapters.py`, `GET /admin/govt-db-status` | **IMPLEMENTED, UNVERIFIED, and cannot go further in this environment** — this is the integration *point* (Protocol interface, fail-closed `GovtDbUnavailable`, per-system status endpoint), not a working integration. Unlike the OIDC/Kafka/pgvector scaffolds above, there is no sandbox or test credential for any of these systems available anywhere — real access requires an actual government-to-government integration agreement, which no amount of code changes. 10 tests, full suite 357/357, HTTP-exercised (`GET /admin/govt-db-status` → 200, all four systems report `configured: false`) |
| Observability (metrics/tracing) | Not built this session — still open, see below | **NOT IMPLEMENTED** (unchanged) |

## What was deliberately NOT attempted this session, and why

- **`SWE-6` (per-camera worker process isolation)** — the migration plan
  itself says this "needs process-level isolation to fix properly ...
  and untestable here without a real unreachable-RTSP-host scenario."
  Nothing in this session's environment changed that.
- **Observability pipeline** — adding real Prometheus metrics/structured
  log shipping without a metrics backend to send them to would be
  exactly the kind of untested, unverifiable code this document is
  trying to avoid producing more of.
- **ML licensing/validation** — both are explicitly non-engineering
  (procurement/legal decision, real labeled dataset) per
  `PRODUCTION_MIGRATION_PLAN.md` §3's non-goals; no amount of code
  changes this session substitutes for either.

## Verified this session (real, not claimed)

- All three infra-dependent backend modules (`vector_search.py`,
  `kafka_bus.py`, `sso_oidc.py`) import cleanly with zero required new
  dependencies installed (each lazy-imports its optional package
  inside the function that needs it).
- **`session_auth.py` and `backup_restore_sqlite.py` are genuinely
  tested, not just written** — 10 + 7 = 17 new tests, all executed
  against real HTTP/cookie mechanics and real on-disk SQLite files.
- Full backend suite re-run after all additions: **216/216 passing**
  (199 baseline + 17 new), zero regressions.
- All 7 new Kubernetes manifests and 1 docker-compose file parse as
  valid YAML (`python -c "import yaml; ..."`, this session).
- Both new GitHub Actions workflow files parse as valid YAML.
- Confirmed via `which docker kubectl helm` that none of these tools
  exist in this environment — the basis for every `DESIGN TARGET` label
  above.

## Before any of this is presented as "production ready"

1. Get access to a real Docker host, build both images, and fix
   whatever build errors surface (there will be some — untested
   Dockerfiles almost always have at least a path or dependency issue).
2. Actually run `docker compose -f infra/docker-compose.production.yml
   up` against a disposable Postgres, migrate a copy of real
   `sentinel.db` data into it (never the original — see `CLAUDE.md`
   §15.7/§24.3), and re-run the full test suite against that stack.
3. Test RTSP/ONVIF connectivity through whatever container networking
   mode is actually used — the `network_mode: host` workaround in the
   compose file is unverified.
4. If pgvector/Kafka/OIDC are actually going to be used, install a real
   instance of each and exercise `vector_search.py`/`kafka_bus.py`/
   `sso_oidc.py` against it — the code compiling and importing is not
   the same as it working, and none of the "happy path" logic in these
   three files has run once end-to-end.
5. Apply the Kubernetes manifests to a real (even single-node kind/
   minikube) cluster and confirm the pods actually come up healthy.
6. Only then update the status column above from `DESIGN TARGET`/
   `IMPLEMENTED, UNVERIFIED` to something stronger — and say exactly
   what was run to earn that upgrade, per `CLAUDE.md` §26.
