# Model 1 Migration Scope — Code Map for Phase 1 (PostgreSQL + PostGIS)

**Status update (2026-09-17): LIVE/REAL VERIFIED against actual
PostgreSQL — see §8 and §9.** A real PostgreSQL 16.4 instance was stood
up in this environment without admin rights (EnterpriseDB's binaries-only
ZIP distribution, `initdb`/`pg_ctl` run as a plain user process on a
custom port — no Docker, no Chocolatey, no elevation) and the full
migration path was run and verified against it for real: `init_db()`
(full schema + the additive-migration `ALTER TABLE` path, deliberately
forced by dropping columns first, not just a fresh `create_all`),
`migrate_model1_to_postgres.py`'s actual data copy, and the entire live
FastAPI application (onboarding, maintenance toggle, gap-analysis, CSV
and PDF export, audit trail) hit end-to-end through a running server
backed by that Postgres instance. See §9 for exact commands and results.

This document originally mapped the code involved without changing
anything. That mapping (§§1–7) is unchanged and still accurate; §8
describes what was implemented, §9 what was verified against real
Postgres.
exactly which files, tables, and columns Phase 1 of
`PRODUCTION_MIGRATION_PLAN.md` (SQLite → PostgreSQL/PostGIS) touches for
**Model 1 (Central CCTV Registry & GIS)** specifically. Written so the
migration has a concrete checklist instead of "migrate the database" as
one vague step. Not to be implemented before the hackathon submission
(28 Sept 2026) / Grand Finale (12–13 Oct 2026) — see
`PRODUCTION_MIGRATION_PLAN.md` §0.

## 1. What "Model 1" owns vs. what it shares

`CameraRegistry` is Model 1's own table, but it's read by almost every
other module as shared reference data (a camera's location, department,
health). This matters for migration risk: Model 1's *own* code (registry
CRUD, GIS, gap-analysis, onboarding audit) can be migrated and tested as
one unit, but a schema/dialect change to `camera_registry` has a much
wider blast radius than Model 1's feature code alone. Both are listed
below, kept clearly separate.

## 2. Database layer (the actual migration surface)

### `backend/app/db/models.py`
Two tables are Model 1's own:

- **`CameraRegistry`** (`camera_registry`) — the registry/GIS row itself.
  Columns as of this session: `id`, `department`, `location_name`,
  `latitude`, `longitude`, `vendor`, `codec`, `camera_type`,
  `onboarded_at`, `last_seen_live_at`, `is_healthy`,
  `analytics_degraded`, `last_analytics_success_at`,
  `is_restricted_zone`, `expected_direction_deg`, `install_date`,
  `coverage_radius_m`, `source_system`, `snapshot_image_url`.
  **`latitude`/`longitude` are the PostGIS payoff column** — Phase 1
  step 4 replaces these two `Float` columns with a real `geometry(Point)`
  column once the data-copy is verified.
- **`CameraAuditLog`** (`camera_audit_log`) — onboarding/edit audit
  trail. `id`, `camera_id`, `user_id`, `action`, `created_at`. No
  geo/dialect-specific concerns; a plain-copy table.

### `backend/app/db/session.py`
- `_ADDITIVE_MIGRATIONS` (lines ~40–63) — the hand-rolled migration list
  this project uses instead of Alembic. Every `camera_registry` entry
  here (`camera_type`, `is_restricted_zone`, `expected_direction_deg`,
  `install_date`, `coverage_radius_m`, `analytics_degraded`,
  `last_analytics_success_at`, `source_system`, `snapshot_image_url`)
  is one Alembic revision to write, in the same order, once Alembic
  replaces this mechanism.
- `_check_models_match_db()` — the runtime guard that currently catches a
  missed SQLite migration entry. Needs an equivalent (or Alembic's own
  `alembic check`) once Postgres is the target, so this safety net isn't
  silently lost in the migration.
- `init_db()` — creates tables via `Base.metadata.create_all` today;
  Alembic replaces this for anything past the first migration.

### `backend/app/config.py`
- `DATABASE_URL` (line ~50) — the only line that changes to point at
  Postgres; everything else in this file is unrelated to Model 1's
  migration.

## 3. Model 1's own feature code (registry, GIS, onboarding, gap-analysis)

### `backend/app/api/routes_cameras.py` — the whole Model 1 API surface
Every endpoint here queries `CameraRegistry` directly and needs
re-testing against Postgres, not just re-pointing:

| Endpoint | What it does with `CameraRegistry` |
|---|---|
| `GET /cameras` | List/search/filter (department, camera_type, is_healthy, live, free-text `q`) — department-scoped |
| `GET /cameras/gap-analysis` | Aggregates unregistered/offline/missing-department/missing-GPS/unhealthy/ageing cameras |
| `GET /cameras/gap-analysis/export.pdf` | Same data, rendered via `reportlab` |
| `POST /cameras` | Single onboard/update, writes `CameraAuditLog` |
| `POST /cameras/bulk` | Batch onboard/update, same audit trail per row |
| `GET /cameras/{id}/audit-log` | Reads `CameraAuditLog` for one camera |
| `GET /cameras/export.csv` | Department-scoped CSV export, never emits `rtsp_url`/`whep_url` |
| `GET /cameras/{id}` | Single camera detail |
| `GET /cameras/{id}/last-detection`, `/stats` | Cross-reads `VehicleEvent` — Model 2 data joined against Model 1's registry, not Model 1 alone |

**The gap-analysis and coverage-radius logic is where SQLite → PostGIS
actually changes the code, not just the connection string**: today,
distance/coverage checks that touch `latitude`/`longitude` do their own
math in Python (see §4's `geo.py` note) rather than a spatial query.
Moving to a real PostGIS `geometry` column is what Phase 1 step 4 of the
migration plan is for — re-examine every place `CameraRegistry.latitude`/
`.longitude` is read once that column changes shape.

### `backend/app/api/auth.py`
- `department_scope()` — not a DB concern itself, but every Model 1 query
  above filters through it (`CameraRegistry.department == department`).
  Needs no dialect changes, just re-verification once the underlying
  table is on Postgres (existing `tests/test_rbac_department_scope.py`
  should be re-run as-is).

### `backend/app/main.py`
- `_sync_camera_health()` (Model 1's health-monitoring deliverable) reads
  the live `StreamManager` snapshot and writes `is_healthy`,
  `last_seen_live_at`, `analytics_degraded`, `last_analytics_success_at`
  back onto `CameraRegistry` rows on a timer. Pure ORM read/write, no
  raw SQL — should port without change, but is high-value to include in
  the Phase 1 test pass since it's the most frequently-written path onto
  this table.

## 4. Code that reads `CameraRegistry` as shared data (not Model 1's own logic, but affected)

These don't need to change for the migration, but every one of them is a
real query against the table being migrated, so they belong in the
Phase 1 regression test list:

| File | What it reads from `CameraRegistry` |
|---|---|
| `api/routes_stream.py` | Department scoping for the HLS live-view proxy (`_scoped_camera_or_404`) |
| `api/routes_vehicle.py` | Batched camera lookup (`_cameras_by_id`) to attach `location_name` to vehicle events; `rank_candidate_cameras` reads every camera's lat/lon |
| `api/routes_admin.py` | Reads camera rows for admin-level reporting (density/rollup views) |
| `api/routes_alerts.py` | Attaches camera context to alert rows |
| `analytics/anomaly.py` | Reads `is_restricted_zone`/`expected_direction_deg` per camera to decide whether to run wrong-way/restricted-zone checks |
| `analytics/identity.py` | Geo-feasibility gate reads camera lat/lon via `analytics/geo.py` — **this is the other real PostGIS beneficiary**, cross-camera appearance-match feasibility currently computed in Python (haversine), a candidate to push into a spatial query once geometry columns exist |
| `analytics/pipeline.py` | Camera registration lookups during frame processing |
| `streaming/manager.py` | Does not query the DB directly, but its `health_snapshot()` output is what `main.py` writes back onto this table — listed for completeness |
| `external_camera_source.py` | Upserts Model 2's second-system (Caltrans) cameras into this same table with `source_system` set — registry-only, never touches streaming |

`analytics/geo.py` itself has no direct DB dependency (it takes
already-fetched `CameraRegistry` objects as plain Python arguments), but
it's the actual haversine-distance logic that a PostGIS migration would
eventually want to replace with real spatial queries — named here because
it's the concrete "why PostGIS, not just Postgres" answer for Model 1.

## 5. Frontend (Model 1 UI — no DB change, but needs regression testing against the new backend)

| File | Model 1 feature |
|---|---|
| `frontend/src/components/MapView.jsx` | GIS map, coverage-radius circles, ageing-marker outlines |
| `frontend/src/components/LiveMapView.jsx` | Live health-colour-coded map view |
| `frontend/src/components/CameraList.jsx` | Registry list/search/filter UI |
| `frontend/src/components/CameraDetailPanel.jsx` | Single-camera detail view |
| `frontend/src/components/CameraHealthView.jsx` | Health/analytics-degraded status display |
| `frontend/src/components/CameraNetworkView.jsx` | Network/topology-style camera view |
| `frontend/src/components/CoverageGapsView.jsx` | Gap-analysis UI |
| `frontend/src/components/GapAnalysisPanel.jsx` | Gap-analysis report panel |
| `frontend/src/components/OnboardCameraForm.jsx` | Manual onboarding form |
| `frontend/src/components/BulkOnboardForm.jsx` | Bulk onboarding form |

None of these call the database directly — they all go through
`routes_cameras.py`'s API, so they need re-testing (existing Playwright/
manual verification), not code changes, once Phase 1 lands.

## 6. Test coverage already in place for this surface

- `tests/test_camera_registry_model1.py` — onboarding, re-onboard audit
  ordering tie-break.
- `tests/test_rbac_department_scope.py` — department-scoped registry
  access (5 tests).
- `tests/test_gap_analysis_pdf.py` — gap-analysis PDF export, including
  the empty-department-breakdown edge case.
- `tests/test_geo.py` — `rank_candidate_cameras`/feasibility logic that
  reads `CameraRegistry` lat/lon.

All four suites are the concrete "did the migration actually work"
check for Phase 1 — they should pass unchanged against Postgres before
touching the PostGIS geometry-column step, and be extended (not
replaced) once `latitude`/`longitude` become a real `geometry` column.

## 7. Suggested migration order for Model 1 specifically

1. `CameraAuditLog` first — no geo columns, simplest possible proof the
   Postgres connection/ORM layer works end-to-end (write + read back).
2. `CameraRegistry` as-is (still plain `Float` lat/lon) — get every
   endpoint in §3 and every reader in §4 green against Postgres before
   changing column types.
3. Only then, the PostGIS `geometry(Point)` migration for
   `latitude`/`longitude` — update `routes_cameras.py`'s gap-analysis
   distance checks and `analytics/geo.py`'s haversine math to use spatial
   queries, re-run `tests/test_geo.py` and `tests/test_gap_analysis_pdf.py`.

## 8. What's actually implemented now (2026-09-17)

Steps 1–2 of §7's order are code-complete:

- **`backend/app/db/session.py`** — `_ADDITIVE_MIGRATIONS`'s column-type
  strings are now dialect-portable: `DATETIME` (not a real PostgreSQL
  type) replaced with `TIMESTAMP` everywhere, and
  `is_restricted_zone`'s `BOOLEAN DEFAULT 0 NOT NULL` (Postgres has no
  implicit integer→boolean cast in a `DEFAULT` clause) replaced with
  `BOOLEAN DEFAULT FALSE NOT NULL`. Both forms are valid SQLite too, so
  this is a strict widening of dialect support, not a behavior change on
  the pilot's current SQLite target — confirmed by the full 162-test
  backend suite still passing unchanged.
- **`backend/requirements.txt`** — added `psycopg2-binary==2.9.9`, the
  driver `DATABASE_URL=postgresql://...` needs. Inert for the current
  SQLite default; only loaded when SQLAlchemy actually connects to a
  `postgresql://` URL.
- **`backend/scripts/migrate_model1_to_postgres.py`** (new) — the actual
  data-copy script for `camera_registry` + `camera_audit_log` per §7 step
  1–2: creates just those two tables on the target if missing (never the
  full schema — other tables are a separate migration), refuses to copy
  into a non-empty target table (no silent overwrite), copies every row
  and column exactly as stored, then re-queries the target to verify the
  row count matches what was read from source. Run from `backend/`:
  `python -m scripts.migrate_model1_to_postgres --target postgresql://...`
  (`--source` defaults to the pilot's real `sentinel.db`).

A Model 1 **maintenance-status** feature also landed this session
(`REQUIREMENTS_COVERAGE.md`'s one previously-named open gap): `under_maintenance`/
`maintenance_reason`/`maintenance_until` columns, a `POST
/cameras/{id}/maintenance` admin-only endpoint, and gap-analysis now
excludes an under-maintenance camera from the "unhealthy" (unexpected
failure) list, reporting it under a separate `under_maintenance` category
instead. Covered by 2 new backend tests (`test_camera_registry_model1.py`).

## 9. LIVE/REAL PostgreSQL verification (2026-09-17)

No Chocolatey/admin install was needed in the end: EnterpriseDB publishes
a binaries-only ZIP (`postgresql-16.4-1-windows-x64-binaries.zip`, no
installer), which runs as an ordinary user process via `initdb`/`pg_ctl`
on a custom port. Downloaded, extracted, initialized, and started
entirely in this session's scratch directory — nothing touched the
system outside it, and the instance was cleanly stopped afterward.

What was actually run against it, in order:

1. **`init_db()` on a fresh database** — full `Base.metadata.create_all`
   + `_apply_additive_migrations` + `_check_models_match_db()` all
   succeeded against real Postgres on the first try.
2. **The additive-migration `ALTER TABLE` path, forced for real** —
   dropped `camera_registry.install_date` (a `TIMESTAMP` column) and
   `.under_maintenance` (a `BOOLEAN DEFAULT FALSE NOT NULL` column)
   directly via `psql`, then re-ran `init_db()`. Both columns were
   correctly re-added with the right type and default — the exact
   dialect fix from §8, now proven against real Postgres, not reasoned
   about statically.
3. **`migrate_model1_to_postgres.py`, for real** — seeded a fresh SQLite
   source with representative `camera_registry`/`camera_audit_log` rows
   (including the new maintenance fields) and ran the script against the
   live Postgres target. Verified via `psql` that every field arrived
   correctly, including the boolean columns.
4. **The full application, live** — started `app.main` with
   `DATABASE_URL` pointed at this Postgres instance and drove the entire
   Model 1 API through it: onboard a camera, set/clear maintenance status,
   confirm gap-analysis correctly separates "unhealthy" from "under
   maintenance", confirm the audit trail records `maintenance_set`/
   `maintenance_cleared`, confirm CSV and PDF export both work.

**Not yet done / explicitly out of scope for this pass:**
- §7 step 3 (the PostGIS `geometry(Point)` column swap and the
  `analytics/geo.py`/gap-analysis query rewrite that goes with it) is not
  started — it's a real code change to the query logic, not just a data
  copy.
- Alembic was deliberately NOT introduced — the existing
  `_ADDITIVE_MIGRATIONS` mechanism was made dialect-portable instead,
  which is a much smaller, lower-risk change than swapping migration
  frameworks, and it's now proven to work against real Postgres without it.
- The existing `pytest` suite's fixtures hardcode `sqlite:///:memory:`
  (`tests/conftest.py`) rather than reading `DATABASE_URL` — the 164-test
  suite was NOT re-run against Postgres directly; the live-server pass in
  step 4 above is the actual Postgres proof instead. Parametrizing the
  test suite to run against both backends is a reasonable follow-up, not
  done here.
