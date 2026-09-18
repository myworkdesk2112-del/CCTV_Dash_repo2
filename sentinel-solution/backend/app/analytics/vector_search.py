"""Production hardening scaffold — approximate-nearest-neighbor (ANN)
candidate search for cross-camera Re-ID at scale.

**Status: IMPLEMENTED, UNVERIFIED.** Written 2026-09-18 per
`docs/PRODUCTION_MIGRATION_PLAN.md`'s Phase 1 gap and
`docs/SCALABILITY.md` §2's "Re-ID similarity search at scale" section,
which names brute-force nearest-neighbor search as intractable past
pilot scale but says it was "not built this week." This module is that
build — but it has NOT been run against a real pgvector-enabled Postgres
instance in this environment (no such instance exists here; see the
project's production-hardening review, 2026-09-18). Treat every claim
below as a design implemented in code, not a verified deployment.

**Deliberately NOT wired into `identity.py`'s default resolve path.**
`identity.py._best_match`'s brute-force `cosine_similarity` loop is the
pilot's validated, tested behavior (32+ regression tests, including the
41.87%-false-positive-rate finding in `CODEX_HANDOFF_PROMPT.md`'s ML-3).
Swapping the candidate-retrieval strategy changes which candidates are
even considered before the existing threshold/geo-feasibility gates run,
which is exactly the kind of change `CLAUDE.md` §24.14 says must be
re-validated from scratch, not assumed equivalent. This module is an
opt-in alternative a future session can wire in deliberately, once a
real pgvector instance exists to validate against.

Only activates when:
  - `config.VECTOR_SEARCH_ENABLED` is true, AND
  - `config.DATABASE_URL` is a `postgresql://` URL, AND
  - the `pgvector` Postgres extension is actually installed in that DB
    (checked at call time, not assumed).

Falls back to `NotImplementedError` with a clear message otherwise —
per this repo's stub/real pattern (`CLAUDE.md` §15.1), never a silent
no-op that pretends to have searched.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .. import config

logger = logging.getLogger(__name__)

# Same dimensionality as `analytics/reid.py`'s ColorHistogramEncoder output —
# this module indexes whatever embedding identity.py already produces, it
# does not change the encoder itself (that's `ML-3`/`ML-4`'s separate,
# still-open gap).
EMBEDDING_COLUMN = "embedding_vector"
EMBEDDING_TABLE = "vehicle_identity"
HNSW_INDEX_NAME = "vehicle_identity_embedding_hnsw_idx"


@dataclass
class AnnCandidate:
    identity_id: int
    plate: Optional[str]
    distance: float  # pgvector cosine distance (0 = identical, 2 = opposite)

    @property
    def similarity(self) -> float:
        """Convert pgvector's cosine *distance* to the same [-1, 1] cosine
        *similarity* scale `identity.py`'s existing threshold uses, so a
        caller can apply `EMBEDDING_SIMILARITY_THRESHOLD` unchanged."""
        return 1.0 - self.distance


class PgVectorUnavailable(RuntimeError):
    """Raised when vector search is requested but the environment can't
    actually support it (wrong DB, extension missing, disabled by config).
    Never silently falls back to a different, unrequested search strategy —
    the caller decides what to do (e.g. use identity.py's existing
    brute-force path) rather than this module guessing."""


def is_available(db: Session) -> bool:
    """Real capability check, not a config-only guess: config must enable
    it AND the connected database must actually be Postgres with the
    pgvector extension present. Never assumes based on `DATABASE_URL`
    alone — a Postgres instance without `CREATE EXTENSION vector` run
    would otherwise silently fail deeper in `query_candidates`."""
    if not config.VECTOR_SEARCH_ENABLED:
        return False
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return False
    try:
        row = db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).first()
        return row is not None
    except Exception:
        logger.exception("pgvector availability check failed")
        return False


def ensure_schema(engine: Engine) -> None:
    """One-time additive migration: adds the vector column + HNSW index.
    Idempotent (IF NOT EXISTS throughout) so it's safe to call on every
    startup, same discipline as `db/session.py`'s existing
    `_ADDITIVE_MIGRATIONS`. Must only be called against a real Postgres
    engine with pgvector already `CREATE EXTENSION`-ed — raises rather
    than silently no-op-ing against SQLite, since a caller invoking this
    directly is explicitly opting into the Postgres-only path.

    NOT called automatically by `db/session.py.init_db()` — this is a
    deliberate production-migration step (Phase 1 of
    `PRODUCTION_MIGRATION_PLAN.md`), not part of the pilot's default
    SQLite startup path.
    """
    if engine.dialect.name != "postgresql":
        raise PgVectorUnavailable(
            f"ensure_schema requires a postgresql engine, got {engine.dialect.name!r}"
        )
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text(
                f"ALTER TABLE {EMBEDDING_TABLE} "
                f"ADD COLUMN IF NOT EXISTS {EMBEDDING_COLUMN} vector(512)"
            )
        )
        # HNSW (Hierarchical Navigable Small World) — the standard
        # approximate-NN index pgvector supports for sub-second search at
        # the billion-row scale SCALABILITY.md §2 describes; exact-search
        # IVFFlat would need periodic re-training as data grows, HNSW does
        # not. `vector_cosine_ops` matches `AnnCandidate.similarity`'s
        # cosine-distance assumption above.
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {HNSW_INDEX_NAME} "
                f"ON {EMBEDDING_TABLE} USING hnsw ({EMBEDDING_COLUMN} vector_cosine_ops)"
            )
        )
    logger.info("vector_search.ensure_schema: pgvector column + HNSW index ensured")


def query_candidates(
    db: Session,
    embedding: Sequence[float],
    *,
    camera_ids: Optional[Sequence[str]] = None,
    limit: int = 20,
) -> List[AnnCandidate]:
    """Bounded ANN lookup — the "candidate filtering before similarity
    search, not after" strategy `SCALABILITY.md` §2 names as the fix for
    brute-force search not scaling. `camera_ids` should be pre-narrowed by
    the caller's own geo/time feasibility gate (`analytics/geo.py`), same
    principle as the existing `identity.py._geo_feasible` check — this
    function only does the nearest-neighbor part, not the feasibility
    reasoning, so identity.py's validated feasibility logic would still
    apply on top of whatever this returns if it were ever wired in.

    Raises `PgVectorUnavailable` rather than silently returning an empty
    list when the backend isn't actually usable — an empty result must
    mean "no similar vehicles found," never "search didn't run."
    """
    if not is_available(db):
        raise PgVectorUnavailable(
            "pgvector backend requested but not available in this database "
            "(check config.VECTOR_SEARCH_ENABLED, DATABASE_URL dialect, and "
            "that `CREATE EXTENSION vector` has been run)"
        )
    vector_literal = "[" + ",".join(f"{float(x):.6f}" for x in embedding) + "]"
    camera_filter = ""
    params = {"vector_literal": vector_literal, "limit": limit}
    if camera_ids:
        camera_filter = "AND last_seen_camera_id = ANY(:camera_ids)"
        params["camera_ids"] = list(camera_ids)
    rows = db.execute(
        text(
            f"""
            SELECT id, plate, {EMBEDDING_COLUMN} <=> :vector_literal AS distance
            FROM {EMBEDDING_TABLE}
            WHERE {EMBEDDING_COLUMN} IS NOT NULL {camera_filter}
            ORDER BY distance ASC
            LIMIT :limit
            """
        ),
        params,
    ).fetchall()
    return [AnnCandidate(identity_id=r.id, plate=r.plate, distance=float(r.distance)) for r in rows]
