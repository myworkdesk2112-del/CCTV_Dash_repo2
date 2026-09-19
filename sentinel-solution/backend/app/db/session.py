from __future__ import annotations

import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from .. import config
from .models import Base

logger = logging.getLogger("sentinel.db")

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
)


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Bounded writer contention for the pilot's concurrent camera workers."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


if config.DATABASE_URL.startswith("sqlite"):
    event.listen(engine, "connect", _configure_sqlite_connection)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Columns added after the initial schema shipped. `create_all` only creates
# MISSING TABLES — it never alters an existing one — so an already-created DB
# would be missing these and queries referencing them would fail with
# "no such column". This project has no migration framework (Alembic), so
# this is a minimal, idempotent, additive migration: add the column only if
# it isn't already present. Additive-only by design — it never drops or
# rewrites data. (table, column, SQL column definition)
#
# Column-definition strings are written to be dialect-portable across
# SQLite and PostgreSQL (Model 1 production migration, 2026-09-17):
# "DATETIME" is not a real PostgreSQL type (only "TIMESTAMP" is), so every
# entry uses "TIMESTAMP" instead — SQLite accepts it too, resolving to the
# same NUMERIC type affinity DATETIME would have (SQLite's type affinity is
# substring-matched, not a strict type system, and doesn't affect how
# SQLAlchemy serializes datetimes at the ORM layer either way). Likewise a
# boolean default is written as "DEFAULT FALSE", not "DEFAULT 0" — Postgres
# has no implicit integer-to-boolean cast in a DEFAULT clause (removed in
# PG 8.3), while SQLite has accepted the TRUE/FALSE keywords since 3.23
# (2018), so this is portable both ways. NOT verified against a live
# Postgres instance yet — see PRODUCTION_MIGRATION_PLAN.md Phase 1;
# re-run this file's logic against a real Postgres DB before relying on it.
_ADDITIVE_MIGRATIONS = [
    ("alert", "status", "VARCHAR DEFAULT 'new' NOT NULL"),
    ("alert", "status_updated_by", "VARCHAR"),
    ("alert", "status_updated_at", "TIMESTAMP"),
    ("vehicle_event", "crop_path", "VARCHAR"),
    ("vehicle_event", "bbox_x1", "FLOAT"),
    ("vehicle_event", "bbox_y1", "FLOAT"),
    ("vehicle_event", "bbox_x2", "FLOAT"),
    ("vehicle_event", "bbox_y2", "FLOAT"),
    ("vehicle_identity", "last_camera_id", "VARCHAR"),
    ("camera_registry", "camera_type", "VARCHAR"),
    ("camera_registry", "is_restricted_zone", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("camera_registry", "expected_direction_deg", "FLOAT"),
    ("alert", "alert_type", "VARCHAR DEFAULT 'watchlist' NOT NULL"),
    ("camera_registry", "install_date", "TIMESTAMP"),
    ("camera_registry", "coverage_radius_m", "FLOAT"),
    ("vehicle_event", "ingested_at", "TIMESTAMP"),
    ("vehicle_event", "storage_tier", "VARCHAR"),
    ("alert", "evidence_class", "VARCHAR"),
    ("alert", "evidence_class_reason", "VARCHAR"),
    ("camera_registry", "analytics_degraded", "BOOLEAN"),
    ("camera_registry", "last_analytics_success_at", "TIMESTAMP"),
    ("camera_registry", "source_system", "VARCHAR"),
    ("camera_registry", "snapshot_image_url", "VARCHAR"),
    ("camera_registry", "under_maintenance", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("camera_registry", "maintenance_reason", "VARCHAR"),
    ("camera_registry", "maintenance_until", "TIMESTAMP"),
    ("camera_registry", "homography_json", "VARCHAR"),
    ("camera_registry", "homography_calibrated_at", "TIMESTAMP"),
    ("camera_registry", "homography_reference_note", "VARCHAR"),
    ("vehicle_event", "speed_kmh", "FLOAT"),
    ("camera_registry", "deregistered", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("camera_registry", "deregistered_reason", "VARCHAR"),
    ("camera_registry", "deregistered_at", "TIMESTAMP"),
    ("vehicle_event", "crop_sha256", "VARCHAR"),
    ("vehicle_event", "crop_hashed_at", "TIMESTAMP"),
    ("vehicle_event", "production_stamp", "VARCHAR"),
]


def _apply_additive_migrations() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, coldef in _ADDITIVE_MIGRATIONS:
            if table not in existing_tables:
                continue  # create_all will build it fresh, with all columns
            cols = {c["name"] for c in inspector.get_columns(table)}
            if column in cols:
                continue
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {coldef}'))
            logger.info("migrated: added %s.%s", table, column)


def _ensure_vehicle_identity_plate_unique(existing_tables: set) -> None:
    """`vehicle_identity.plate` gained a UNIQUE constraint after this project
    already had DBs in the wild with duplicate-plate identity rows (the
    check-then-insert race in identity.py, now fixed there too — see its
    IntegrityError handling, which depends on this constraint existing).
    `create_all` only builds the constraint for brand-new tables, so an
    already-existing `vehicle_identity` table needs its duplicates merged
    before the unique index can be created, or the index creation itself
    would fail against corrupted data.
    """
    if "vehicle_identity" not in existing_tables:
        return  # fresh table from create_all already has the constraint
    inspector = inspect(engine)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("vehicle_identity")}
    if "ix_vehicle_identity_plate_unique" in existing_indexes:
        return
    with engine.begin() as conn:
        dupes = conn.execute(text(
            "SELECT plate, MIN(id) FROM vehicle_identity "
            "WHERE plate IS NOT NULL GROUP BY plate HAVING COUNT(*) > 1"
        )).fetchall()
        for plate, keep_id in dupes:
            identity_columns = (
                "plate_confidence", "embedding_json", "first_seen_at", "last_seen_at", "last_camera_id"
            )
            select_columns = ", ".join(("id",) + identity_columns)
            identities = conn.execute(
                text(f"SELECT {select_columns} FROM vehicle_identity WHERE plate = :plate ORDER BY id"),
                {"plate": plate},
            ).mappings().all()
            keeper = next(row for row in identities if row["id"] == keep_id)
            duplicates = [row for row in identities if row["id"] != keep_id]
            dup_ids = [row["id"] for row in duplicates]
            if not dup_ids:
                continue

            # This runs against accumulated databases, not just a clean
            # install.  Preserve any richer non-null data that happened to
            # land on a duplicate row.  Where two rows disagree, keep the
            # deterministic MIN(id) keeper but make the discarded value loud
            # in the startup log rather than silently losing it.
            #
            # first_seen_at/last_seen_at are NOT arbitrary fields with an
            # ambiguous "right" value like embedding_json — they always have
            # a genuinely correct merged value (MIN and MAX respectively
            # across every duplicate), and both columns default to
            # utcnow() so they are essentially always non-null. A generic
            # "keep the keeper's value if non-null, else absorb" rule would
            # never fire for them and would silently leave the keeper's
            # (earliest-created, MIN id) possibly-stale last_seen_at in
            # place even when a duplicate proves the vehicle was seen much
            # more recently. last_camera_id travels with last_seen_at: it
            # should name the camera that produced whichever row is
            # actually the most recent sighting, not be absorbed
            # independently of that.
            all_rows = [keeper] + duplicates
            merged_first_seen_at = min(
                (row["first_seen_at"] for row in all_rows if row["first_seen_at"] is not None), default=None
            )
            most_recent_row = max(
                (row for row in all_rows if row["last_seen_at"] is not None),
                key=lambda row: row["last_seen_at"],
                default=None,
            )

            absorbed: dict[str, object] = {}
            if merged_first_seen_at is not None and merged_first_seen_at != keeper["first_seen_at"]:
                absorbed["first_seen_at"] = merged_first_seen_at
            if most_recent_row is not None and most_recent_row["last_seen_at"] != keeper["last_seen_at"]:
                absorbed["last_seen_at"] = most_recent_row["last_seen_at"]
                if most_recent_row["last_camera_id"] is not None:
                    absorbed["last_camera_id"] = most_recent_row["last_camera_id"]

            remaining_columns = tuple(
                c for c in identity_columns if c not in ("first_seen_at", "last_seen_at", "last_camera_id")
            )
            for duplicate in duplicates:
                for column in remaining_columns:
                    keep_value = absorbed.get(column, keeper[column])
                    duplicate_value = duplicate[column]
                    if keep_value is None and duplicate_value is not None:
                        absorbed[column] = duplicate_value
                    elif keep_value is not None and duplicate_value is not None and keep_value != duplicate_value:
                        logger.warning(
                            "duplicate vehicle_identity merge conflict for plate %s, id=%s field=%s: "
                            "keeping %r; discarded id=%s value %r",
                            plate, keep_id, column, keep_value, duplicate["id"], duplicate_value,
                        )
            if absorbed:
                assignments = ", ".join(f"{column} = :{column}" for column in absorbed)
                conn.execute(
                    text(f"UPDATE vehicle_identity SET {assignments} WHERE id = :keep_id"),
                    {**absorbed, "keep_id": keep_id},
                )
            placeholders = ", ".join(str(i) for i in dup_ids)  # ids only, not user input
            conn.execute(text(
                f"UPDATE vehicle_event SET identity_id = :keep_id WHERE identity_id IN ({placeholders})"
            ), {"keep_id": keep_id})
            conn.execute(text(f"DELETE FROM vehicle_identity WHERE id IN ({placeholders})"))
            logger.warning(
                "merged %d duplicate vehicle_identity row(s) for plate %s into id=%s "
                "(pre-existing DB corrupted by the identity-resolution race, now fixed)",
                len(dup_ids), plate, keep_id,
            )
        conn.execute(text(
            "CREATE UNIQUE INDEX ix_vehicle_identity_plate_unique "
            "ON vehicle_identity(plate) WHERE plate IS NOT NULL"
        ))


def _check_models_match_db() -> None:
    """Every new model column needs a matching entry in
    `_ADDITIVE_MIGRATIONS`, and nothing enforced that until now — a missed
    entry only surfaced as a runtime "no such column" error against an
    already-existing DB, potentially long after the column was added.
    Found by software-engineering review 2026-09-04. Runs AFTER migrations
    are applied, so this only fires on a genuine miss, not a column this
    same startup just added. Loud (raises) rather than silent, since the
    alternative is exactly the silent-landmine failure mode being fixed."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # create_all just built this table fresh, in full
        db_columns = {c["name"] for c in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in db_columns:
                missing.append(f"{table_name}.{column.name}")
    if missing:
        raise RuntimeError(
            "Model/DB schema mismatch after migrations ran — these columns "
            f"exist on the model but not in the database: {', '.join(missing)}. "
            "Add a matching entry to _ADDITIVE_MIGRATIONS in db/session.py."
        )


def init_db() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    Base.metadata.create_all(engine)
    _apply_additive_migrations()
    _ensure_vehicle_identity_plate_unique(existing_tables)
    _check_models_match_db()
