"""Production hardening scaffold — government-database query adapters
(VAHAN, SARTHI, eGujCop, CCTNS/AFIS/NAFIS), additive to the local
watchlist.

**Status: IMPLEMENTED, UNVERIFIED — and cannot become more than that in
this environment.** Written 2026-09-28 per `HLD.md` §6's stated
"query, don't copy" principle and `docs/hackathon/HACKATHON_DETAILS.md`
§8's named integration targets. Unlike the OIDC/Kafka/pgvector scaffolds
in this same module family, there is no sandbox, no test endpoint, and
no credential-issuance process for any of VAHAN, SARTHI, eGujCop, or
CCTNS/AFIS/NAFIS available to this project — these are live Indian
government law-enforcement systems that require an actual department to
request and provision access. No amount of code written here changes
that; this module is the integration POINT, not a working integration.

**Fails closed, always.** Every adapter raises `GovtDbUnavailable` when
no real base URL/credential is configured (`SENTINEL_*_ENABLED` unset,
the default) or when the configured endpoint doesn't respond as
expected. There is no synthetic/mocked "success" path that could be
mistaken for a real query result — CLAUDE.md §24.5 forbids fabricating
a government-database hit, so an unconfigured or unreachable system
degrades to an explicit error the caller must handle, never a fake
"not found" or "no match" that could be misread as a real negative
result.

**Query, don't copy.** Each adapter's contract is a single on-demand
lookup by a key already known to Sentinel (plate, DL number, FIR/case
number) — never a bulk export or a local mirror of the source system.
This keeps Sentinel an interoperability layer over these systems, not a
shadow database, matching the same principle already applied to the
local watchlist (HLD.md §6).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from .. import config

logger = logging.getLogger("sentinel.govt_db_adapters")


class GovtDbUnavailable(RuntimeError):
    """Raised whenever a government-database query cannot be honestly
    answered: not configured, or a configured endpoint failed. Never
    caught and silently converted into a fabricated "no match" — the
    caller must surface this as a degraded/unavailable state, per
    CLAUDE.md §24.7's rule against turning a failure into fake success."""


@dataclass(frozen=True)
class GovtDbQueryResult:
    system: str
    query_key: str
    found: bool
    raw_summary: Optional[str]
    source_note: str


class GovtDbAdapter(Protocol):
    """One real government system this could query. `system_name` is
    stable and used in audit-log entries; `query` never mutates the
    source system (read-only, per HLD.md §6)."""

    system_name: str

    def is_configured(self) -> bool: ...

    def query(self, key: str) -> GovtDbQueryResult: ...


class _UnconfiguredAdapter:
    """Shared behaviour for every real adapter below until a real base
    URL and credential are provided via environment configuration —
    which this project does not have for any of these systems."""

    system_name: str = "unconfigured"
    _env_flag: str = ""

    def is_configured(self) -> bool:
        return False

    def query(self, key: str) -> GovtDbQueryResult:
        raise GovtDbUnavailable(
            f"{self.system_name} is not configured in this deployment "
            f"(set {self._env_flag}=true plus its base URL/credential "
            "env vars once a real integration agreement and sandbox/"
            "production access exist). No query was made; no result — "
            "real or fabricated — exists for this lookup."
        )


class VahanAdapter(_UnconfiguredAdapter):
    """Vehicle registration lookup (Ministry of Road Transport &
    Highways' VAHAN). Real integration requires NIC/MoRTH-issued API
    access — not obtainable from this environment."""
    system_name = "VAHAN"
    _env_flag = "SENTINEL_VAHAN_ENABLED"


class SarathiAdapter(_UnconfiguredAdapter):
    """Driving-licence lookup (SARTHI). Same access model as VAHAN —
    NIC/MoRTH-issued, not obtainable here."""
    system_name = "SARTHI"
    _env_flag = "SENTINEL_SARATHI_ENABLED"


class EGujCopAdapter(_UnconfiguredAdapter):
    """Gujarat Police's own case/FIR system. Requires a Gujarat Home
    Department-issued integration agreement — a real department
    decision, not an engineering task this project can complete alone."""
    system_name = "eGujCop"
    _env_flag = "SENTINEL_EGUJCOP_ENABLED"


class CctnsAdapter(_UnconfiguredAdapter):
    """National Crime & Criminal Tracking Network & Systems
    (CCTNS) — the umbrella system AFIS/NAFIS integration would go
    through in practice. Central-government-issued access, not
    obtainable here."""
    system_name = "CCTNS/AFIS/NAFIS"
    _env_flag = "SENTINEL_CCTNS_ENABLED"


ADAPTERS: dict[str, GovtDbAdapter] = {
    "vahan": VahanAdapter(),
    "sarathi": SarathiAdapter(),
    "egujcop": EGujCopAdapter(),
    "cctns": CctnsAdapter(),
}


def status_report() -> list[dict]:
    """Honest per-system configuration status for the admin screen —
    every row is False until a real access agreement exists; this
    function cannot make one True on its own."""
    return [
        {
            "system": adapter.system_name,
            "configured": adapter.is_configured(),
            "note": (
                "Not integrated: requires a real access agreement and "
                "credentials from the owning government system, which "
                "this project does not have."
            ) if not adapter.is_configured() else "Configured (verify against a real endpoint before trusting this).",
        }
        for adapter in ADAPTERS.values()
    ]
