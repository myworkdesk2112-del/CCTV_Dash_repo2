"""Regression coverage for the government-database query scaffold
(VAHAN/SARTHI/eGujCop/CCTNS). No real endpoint exists to test against —
these tests lock in the fail-closed contract: unconfigured, always, and
never a fabricated result."""
from __future__ import annotations

import pytest

from app.analytics.govt_db_adapters import (
    ADAPTERS,
    CctnsAdapter,
    EGujCopAdapter,
    GovtDbUnavailable,
    SarathiAdapter,
    VahanAdapter,
    status_report,
)


@pytest.mark.parametrize("adapter_cls,expected_name", [
    (VahanAdapter, "VAHAN"),
    (SarathiAdapter, "SARTHI"),
    (EGujCopAdapter, "eGujCop"),
    (CctnsAdapter, "CCTNS/AFIS/NAFIS"),
])
def test_every_adapter_reports_unconfigured(adapter_cls, expected_name):
    adapter = adapter_cls()
    assert adapter.system_name == expected_name
    assert adapter.is_configured() is False


@pytest.mark.parametrize("adapter_cls", [VahanAdapter, SarathiAdapter, EGujCopAdapter, CctnsAdapter])
def test_querying_an_unconfigured_adapter_raises_not_a_fake_result(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(GovtDbUnavailable):
        adapter.query("GJ19BR3000")


def test_status_report_covers_all_four_systems_and_none_are_configured():
    rows = status_report()
    names = {row["system"] for row in rows}
    assert names == {"VAHAN", "SARTHI", "eGujCop", "CCTNS/AFIS/NAFIS"}
    assert all(row["configured"] is False for row in rows)
    assert all("does not have" in row["note"] for row in rows)


def test_adapters_registry_matches_status_report():
    assert len(ADAPTERS) == 4
    assert {a.system_name for a in ADAPTERS.values()} == {
        row["system"] for row in status_report()
    }
