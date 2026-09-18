# Infrastructure — production-hardening artifacts

**Status: DESIGN TARGET — none of this has been deployed or tested.**
This machine has no Docker, no `kubectl`, no Helm, and no cloud
credentials (checked 2026-09-18 — `which docker kubectl helm` all fail).
Every file under this directory is a real, reviewable configuration
written against `docs/PRODUCTION_MIGRATION_PLAN.md`'s phase plan, not a
verified deployment. Do not present anything here as "tested" or
"working" — per `CLAUDE.md` §15.2/§24.15, that requires an actual
execution, which did not happen.

See `sentinel-solution/docs/PRODUCTION_READINESS.md` for the full
gap-by-gap status table this directory implements.

## Contents

- `docker/Dockerfile.backend`, `docker/Dockerfile.frontend` — container
  images for Phase 2 of the migration plan.
- `docker-compose.production.yml` — a local production-like stack
  (backend + frontend + PostgreSQL, optional Kafka profile). Untested —
  needs Docker installed to even attempt.
- `k8s/` — Kubernetes manifests for Phase 2/5 (horizontal scaling,
  container orchestration). Untested — needs a real cluster.
- `nginx/nginx.conf.example` — TLS-terminating reverse proxy in front of
  the frontend static build + backend API, for Phase 7's "TLS for every
  network hop" requirement.

## Before trusting any of this in a real deployment

1. Actually install Docker and run `docker compose -f
   docker-compose.production.yml up` against a throwaway environment.
2. Fix whatever breaks — untested YAML/Dockerfiles routinely have real
   bugs (wrong paths, missing build args, port mismatches).
3. Test RTSP/ONVIF networking specifically — `PRODUCTION_MIGRATION_PLAN.md`
   Phase 2 §2 already flags this as the real risk (multicast WS-Discovery
   does not cross a default Docker bridge network).
4. Re-run the full backend test suite against the containerized stack,
   not just locally.
5. Only then update this file's status from DESIGN TARGET to something
   stronger, and say exactly what was verified.
