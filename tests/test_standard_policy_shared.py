"""The shared standard-selection machinery every financial parser uses.

- `TierHit.context_id`: the context the winning fact was read at.
- `FieldPolicy.fallback` per declared standard: `'none'` closes the legacy
  table to that standard, also for a field that only one standard tags, and
  also for a standard with no element of its own.
- `source_elements` / `source_contexts` on every report: an empty map where a
  parser records nothing ("not recorded", never "no value").
"""

import dataclasses

import pytest

from edinet_tools.parsers import base, securities
from edinet_tools.parsers._standard_policy import (
    FieldPolicy,
    fallback_for,
    with_own_standard_first,
)
from edinet_tools.parsers.extraction import Tier, resolve_tiers

JG, IFRS, US = "Japan GAAP", "IFRS", "US GAAP"
CYD = "CurrentYearDuration"
NC = "_NonConsolidatedMember"
J_ORD = "jppfs_cor:OrdinaryIncome"
I_PBT = "jpigp_cor:ProfitLossBeforeTaxIFRS"
I_EQ = "jpigp_cor:EquityAttributableToOwnersOfParentIFRS"
U_EQ = "jpcrp_cor:EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults"


def _cf(*rows):
    return [
        {
            "filename": "t.csv",
            "data": [
                {
                    "要素ID": e,
                    "項目名": "",
                    "コンテキストID": c,
                    "相対年度": "",
                    "連結・個別": "",
                    "期間・時点": "",
                    "ユニットID": "JPY",
                    "単位": "",
                    "値": v,
                }
                for e, c, v in rows
            ],
        }
    ]


# ---------------------------------------------------------------------------
# TierHit.context_id
# ---------------------------------------------------------------------------


def test_tier_hit_carries_the_bare_context():
    hit = resolve_tiers(
        _cf(("x:A", CYD, "5")), (Tier("x:A"),), standard=None, period=CYD, is_consolidated=True
    )
    assert (hit.value, hit.element_id, hit.context_id) == (5, "x:A", CYD)


def test_tier_hit_carries_the_parent_context():
    cf = _cf(("x:A", CYD, "9"), ("x:A", CYD + NC, "5"))
    hit = resolve_tiers(cf, (Tier("x:A"),), standard=None, period=CYD, is_consolidated=False)
    assert (hit.value, hit.context_id) == (5, CYD + NC)


def test_tier_hit_parent_only_filer_falls_back_to_the_bare_context():
    cf = _cf(("x:A", CYD, "9"))
    hit = resolve_tiers(cf, (Tier("x:A"),), standard=None, period=CYD, is_consolidated=False)
    assert (hit.value, hit.context_id) == (9, CYD)


def test_tier_hit_suffix_tier_reads_the_bare_period():
    cf = _cf(("filer_E1:SalesRevenuesIFRS", CYD, "7"))
    tiers = (Tier(("SalesRevenuesIFRS",), suffix_match=True),)
    hit = resolve_tiers(cf, tiers, standard=None, period=CYD, is_consolidated=False)
    assert (hit.value, hit.element_id, hit.context_id) == (7, "filer_E1:SalesRevenuesIFRS", CYD)


@pytest.mark.parametrize("coerce", [True, False])
def test_tier_hit_string_mode_carries_the_context(coerce):
    cf = _cf(("x:R", CYD + NC, "0.5"))
    hit = resolve_tiers(
        cf,
        (Tier("x:R"),),
        standard=None,
        period=CYD,
        is_consolidated=False,
        mode="string",
        coerce=coerce,
    )
    assert (hit.value, hit.context_id) == ("0.5", CYD + NC)


def test_tier_hit_context_blind_read_reports_the_row_context():
    cf = _cf(("x:A", "Prior1YearDuration", "3"))
    hit = resolve_tiers(cf, (Tier("x:A"),), standard=None, period=None, is_consolidated=True)
    assert (hit.value, hit.context_id) == (3, "Prior1YearDuration")


# ---------------------------------------------------------------------------
# Per-standard fallback
# ---------------------------------------------------------------------------


def test_fallback_for_reads_a_scalar_or_a_mapping():
    assert fallback_for(FieldPolicy("c", (JG, IFRS), "legacy"), US) == "legacy"
    p = FieldPolicy("c", (JG,), {JG: "n/a", IFRS: "none", US: "none"})
    assert fallback_for(p, JG) == "n/a"
    assert fallback_for(p, IFRS) == "none"
    # a standard the mapping does not name keeps the legacy table
    assert fallback_for(FieldPolicy("c", (JG,), {IFRS: "none"}), US) == "legacy"


def _single_standard_closed():
    legacy = (Tier(J_ORD),)
    return with_own_standard_first(legacy, FieldPolicy("c", (JG,), {JG: "n/a", IFRS: "none"}))


def test_single_standard_none_closes_the_legacy_table():
    tiers = _single_standard_closed()
    cf = _cf((J_ORD, CYD, "111"))
    assert resolve_tiers(cf, tiers, standard=IFRS, period=CYD, is_consolidated=True) is None


@pytest.mark.parametrize("standard", [JG, None, US])
def test_single_standard_none_moves_no_other_standard(standard):
    """J-GAAP control, no-DEI control, and a standard the mapping leaves open."""
    tiers = _single_standard_closed()
    cf = _cf((J_ORD, CYD, "111"))
    hit = resolve_tiers(cf, tiers, standard=standard, period=CYD, is_consolidated=True)
    assert hit.value == 111


def _no_own_element_closed():
    legacy = (Tier(I_EQ), Tier(U_EQ))
    policy = FieldPolicy("c", (IFRS, US), {JG: "none", IFRS: "none", US: "none"})
    return with_own_standard_first(legacy, policy)


def test_none_closes_a_standard_with_no_own_element():
    tiers = _no_own_element_closed()
    cf = _cf((I_EQ, CYD, "222"))
    assert resolve_tiers(cf, tiers, standard=JG, period=CYD, is_consolidated=True) is None


def test_none_on_a_standard_with_no_own_element_keeps_the_no_dei_order():
    tiers = _no_own_element_closed()
    cf = _cf((I_EQ, CYD, "222"))
    assert resolve_tiers(cf, tiers, standard=None, period=CYD, is_consolidated=True).value == 222
    assert resolve_tiers(cf, tiers, standard=IFRS, period=CYD, is_consolidated=True).value == 222


def test_multi_standard_mapping_closes_only_the_named_standards():
    legacy = (Tier((J_ORD, I_PBT)),)
    policy = FieldPolicy("c", (JG, IFRS), {JG: "legacy", IFRS: "legacy", US: "none"})
    tiers = with_own_standard_first(legacy, policy)
    cf = _cf((J_ORD, CYD, "111"))
    kw = dict(period=CYD, is_consolidated=True)
    assert resolve_tiers(cf, tiers, standard=US, **kw) is None
    assert resolve_tiers(cf, tiers, standard=IFRS, **kw).value == 111
    assert resolve_tiers(cf, tiers, standard=JG, **kw).value == 111
    assert resolve_tiers(cf, tiers, standard=None, **kw).value == 111


# ---------------------------------------------------------------------------
# Provenance maps on every report
# ---------------------------------------------------------------------------


def _report_classes():
    seen, todo = [], [base.ParsedReport]
    while todo:
        cls = todo.pop()
        for sub in cls.__subclasses__():
            if sub not in seen:
                seen.append(sub)
                todo.append(sub)
    return [base.ParsedReport] + seen


@pytest.mark.parametrize("cls", _report_classes(), ids=lambda c: c.__name__)
def test_every_report_has_both_provenance_maps(cls):
    names = {f.name: f for f in dataclasses.fields(cls)}
    for name in ("source_elements", "source_contexts"):
        assert name in names, (cls.__name__, name)
        assert names[name].type in (dict[str, str], "dict[str, str]")
    r = cls(doc_id="X", doc_type_code="000")
    assert r.source_elements == {} and r.source_contexts == {}


def test_securities_source_contexts_sit_beside_source_elements():
    ni_ifrs = "jpcrp_cor:ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults"
    eps_ifrs = "jpcrp_cor:BasicEarningsLossPerShareIFRSSummaryOfBusinessResults"
    cf = _cf(
        ("jpdei_cor:AccountingStandardsDEI", "FilingDateInstant", "IFRS"),
        (
            "jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI",
            "FilingDateInstant",
            "false",
        ),
        (ni_ifrs, CYD + NC, "30"),
        (eps_ifrs, CYD, "1.5"),
        (ni_ifrs, "Prior1YearDuration" + NC, "20"),
    )
    r = securities.parse_securities_report(csv_files=cf, doc_id="X", doc_type_code="120")
    assert set(r.source_contexts) == set(r.source_elements)
    assert r.source_contexts["net_income_owners"] == CYD + NC
    assert r.source_contexts["prior_net_income_owners"] == "Prior1YearDuration" + NC
    assert r.source_contexts["earnings_per_share"] == CYD
    assert r.source_contexts["ifrs_summary_basic_eps"] == CYD
