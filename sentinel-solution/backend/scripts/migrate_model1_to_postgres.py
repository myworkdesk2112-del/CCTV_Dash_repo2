"""Model 1 data migration: copy `camera_registry` and `camera_audit_log`
from the pilot's SQLite database into a PostgreSQL target.

Status: IMPLEMENTED, UNVERIFIED — written against SQLAlchemy 2.0's
documented Core API and this project's actual schema, but not yet run
against a real PostgreSQL instance (none was available in this
environment — see PRODUCTION_MIGRATION_PLAN.md Phase 1 and
MODEL1_MIGRATION_SCOPE.md). Run this against a real target and read the
verification output before trusting it operationally.

Scope, deliberately: Model 1 only (`camera_registry`, `camera_audit_log`),
per this session's task. Every other table (`vehicle_event`,
`vehicle_identity`, `alert`, `federated_event`, `api_key_entry`, ...)
needs the same treatment before a full cutover — this script does not
attempt that, and does not create rows in any table outside these two.

What this does NOT do (by design, matching CLAUDE.md's evidence/DB
safety rules):
  - It never modifies or deletes anything in the SOURCE (SQLite) database
    — read-only against the source, full stop.
  - It never drops or truncates anything in the TARGET — if a target
    table already has rows, this script refuses to proceed rather than
    guessing whether it's safe to overwrite real data.
  - It copies rows exactly as they are, including primary keys — no
    re-numbering, no dropped columns, no reinterpreted values.

Usage (from `sentinel-solution/backend/`):
    python -m scripts.migrate_model1_to_postgres \\
        --source sqlite:///./sentinel.db \\
        --target postgresql://user:pass@host:5432/sentinel

`--source` defaults to this project's real `DATABASE_URL` default
(sqlite:///./sentinel.db) if omitted. `--target` is required — there is
no default production Postgres URL to guess, deliberately.
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import MetaData, Table, create_engine, select

from app.db.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinel.migrate_model1")

# Parent-before-child order: camera_audit_log rows carry a camera_id that
# logically refers to camera_registry (no formal ForeignKey is declared in
# db/models.py today, so this is a convention to preserve, not a DB-enforced
# constraint this script must satisfy to avoid an error) — copying the
# registry first keeps the data in the order a real FK migration would need.
MODEL1_TABLES = ["camera_registry", "camera_audit_log"]


def _reflect_table(metadata: MetaData, engine, table_name: str) -> Table:
    return Table(table_name, metadata, autoload_with=engine)


def _copy_table(source_engine, target_engine, table_name: str) -> tuple[int, int]:
    source_meta = MetaData()
    target_meta = MetaData()
    source_table = _reflect_table(source_meta, source_engine, table_name)
    target_table = _reflect_table(target_meta, target_engine, table_name)

    with target_engine.connect() as target_conn:
        # rowcount on a plain SELECT isn't reliable on every DBAPI — count
        # explicitly rather than trusting it.
        existing_count = len(target_conn.execute(select(target_table)).fetchall())
        if existing_count > 0:
            raise RuntimeError(
                f"target table '{table_name}' already has {existing_count} row(s) — "
                "refusing to copy into a non-empty table. This script never truncates "
                "or overwrites; clear it yourself first if that's really intended."
            )

    with source_engine.connect() as source_conn:
        rows = source_conn.execute(select(source_table)).mappings().all()

    if not rows:
        logger.info("source table '%s' is empty — nothing to copy", table_name)
        return 0, 0

    with target_engine.begin() as target_conn:
        target_conn.execute(target_table.insert(), [dict(row) for row in rows])

    with target_engine.connect() as verify_conn:
        copied_count = len(verify_conn.execute(select(target_table)).fetchall())

    return len(rows), copied_count


def run(source_url: str, target_url: str) -> bool:
    if not target_url.startswith("postgresql"):
        logger.warning(
            "target URL doesn't look like a PostgreSQL URL (%s) — this script isn't "
            "specific to Postgres, but that's the whole point of this migration.",
            target_url,
        )

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    # Create ONLY the two Model 1 tables on the target if they don't already
    # exist — deliberately not the full Base.metadata (every other table is
    # out of scope for this migration, see module docstring). Safe/idempotent:
    # create_all only creates missing tables, never touches an existing one.
    model1_tables = [Base.metadata.tables[name] for name in MODEL1_TABLES]
    Base.metadata.create_all(target_engine, tables=model1_tables)

    all_ok = True
    for table_name in MODEL1_TABLES:
        logger.info("copying '%s': %s -> %s", table_name, source_url, target_url)
        try:
            source_count, target_count = _copy_table(source_engine, target_engine, table_name)
        except Exception:
            logger.exception("failed copying table '%s'", table_name)
            all_ok = False
            continue

        if source_count != target_count:
            logger.error(
                "row-count mismatch on '%s': read %d from source, %d present in target after copy",
                table_name, source_count, target_count,
            )
            all_ok = False
        else:
            logger.info("'%s': %d row(s) verified in target", table_name, target_count)

    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="sqlite:///./sentinel.db", help="Source database URL (default: the pilot's real sentinel.db)")
    parser.add_argument("--target", required=True, help="Target PostgreSQL URL (no default — must be explicit)")
    args = parser.parse_args()

    ok = run(args.source, args.target)
    if not ok:
        logger.error("Model 1 migration finished WITH ERRORS — see above. Nothing was rolled back automatically; inspect the target database before using it.")
        return 1
    logger.info("Model 1 migration completed: camera_registry and camera_audit_log copied and row-count verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
