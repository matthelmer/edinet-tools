"""Own-standard selection on verbatim filings.

Each fixture is a full, unfiltered CSV of a real annual report that tags two
standards' highlights tables for the same year. The expected value of every
asserted field is read out of the fixture itself, by element and context: no
hand-copied numbers. Each pairing is also checked to be a real contest (the
other standard's fact is filed and differs), so a pass means the declared
standard won, not that only one source existed.
"""

from decimal import Decimal

import pytest

from edinet_tools.parsers.securities import parse_securities_report
from tests.conftest import load_securities_fixture

CYD, PYD, CYI = "CurrentYearDuration", "Prior1YearDuration", "CurrentYearInstant"
JC = "jpcrp_cor:"
PER_SHARE = {"earnings_per_share", "net_assets_per_share", "equity_ratio", "roe"}


def _fact(csv_files, element, context):
    values = {
        r["値"]
        for f in csv_files
        for r in f["data"]
        if r["要素ID"] == element and r["コンテキストID"] == context
    }
    assert len(values) == 1, (element, context, values)
    return values.pop()


def _typed(field, raw):
    return Decimal(raw) if field in PER_SHARE else int(raw)


def _parse(name):
    cf = load_securities_fixture(name)
    return cf, parse_securities_report(csv_files=cf, doc_id=name, doc_type_code="120")


# (field, own-standard element, other-standard element, context)
AIR_WATER = [
    (
        "net_income_owners",
        JC + "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults",
        JC + "ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
        CYD,
    ),
    (
        "prior_net_income_owners",
        JC + "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults",
        JC + "ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
        PYD,
    ),
    (
        "earnings_per_share",
        JC + "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults",
        JC + "BasicEarningsLossPerShareSummaryOfBusinessResults",
        CYD,
    ),
    (
        "net_sales",
        JC + "RevenueIFRSSummaryOfBusinessResults",
        JC + "NetSalesSummaryOfBusinessResults",
        CYD,
    ),
    (
        "prior_net_sales",
        JC + "RevenueIFRSSummaryOfBusinessResults",
        JC + "NetSalesSummaryOfBusinessResults",
        PYD,
    ),
    (
        "operating_cash_flow",
        JC + "CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults",
        JC + "NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults",
        CYD,
    ),
    (
        "investing_cash_flow",
        JC + "CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults",
        JC + "NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults",
        CYD,
    ),
    (
        "financing_cash_flow",
        JC + "CashFlowsFromUsedInFinancingActivitiesIFRSSummaryOfBusinessResults",
        JC + "NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults",
        CYD,
    ),
    (
        "roe",
        JC + "RateOfReturnOnEquityIFRSSummaryOfBusinessResults",
        JC + "RateOfReturnOnEquitySummaryOfBusinessResults",
        CYD,
    ),
    (
        "net_assets_per_share",
        JC + "EquityToAssetRatioIFRSSummaryOfBusinessResults",
        JC + "NetAssetsPerShareSummaryOfBusinessResults",
        CYI,
    ),
]


@pytest.mark.parametrize("field,own,other,context", AIR_WATER, ids=[p[0] for p in AIR_WATER])
def test_air_water_first_ifrs_year_reads_the_ifrs_facts(field, own, other, context):
    """Air Water, FY March 2020 (S100J7LZ), its first IFRS year: the filing
    tags the IFRS and the J-GAAP highlights for the same year. Every field
    reads the IFRS fact."""
    cf, r = _parse("airwater_fy2020_ifrs_transition")
    assert r.accounting_standard == "IFRS"
    expected, rival = _fact(cf, own, context), _fact(cf, other, context)
    assert _typed(field, expected) != _typed(field, rival)
    assert getattr(r, field) == _typed(field, expected)
    assert r.source_elements[field] == own


def test_air_water_profit_and_eps_come_from_the_same_table():
    """The pairing that motivated the fix: owners' profit and basic EPS for
    the same year and context both come from the IFRS table (0.8.x returned
    the J-GAAP figures for both in the generic fields, beside an IFRS
    ifrs_summary_basic_eps)."""
    cf, r = _parse("airwater_fy2020_ifrs_transition")
    ni = JC + "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults"
    eps = JC + "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults"
    assert r.net_income_owners == int(_fact(cf, ni, CYD))
    assert r.earnings_per_share == Decimal(_fact(cf, eps, CYD))


def test_tdk_first_ifrs_year_after_us_gaap_reads_ifrs_profit_before_tax():
    """TDK, FY March 2022 (S100ODQV), its first IFRS year after US GAAP: the
    filing tags US-GAAP and IFRS profit before tax for the same years.
    ordinary_income (IFRS: profit before tax, the library's analogue) reads
    the IFRS fact for both periods."""
    cf, r = _parse("tdk_fy2022_usgaap_to_ifrs")
    assert r.accounting_standard == "IFRS"
    own = "jpigp_cor:ProfitLossBeforeTaxIFRS"
    other = JC + "ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults"
    for field, context in (("ordinary_income", CYD), ("prior_ordinary_income", PYD)):
        assert int(_fact(cf, own, context)) != int(_fact(cf, other, context))
        assert getattr(r, field) == int(_fact(cf, own, context))
        assert r.source_elements[field] == own


KIKKOMAN = [
    ("net_sales", JC + "RevenueIFRSSummaryOfBusinessResults", CYD),
    ("prior_net_sales", JC + "RevenueIFRSSummaryOfBusinessResults", PYD),
    ("ordinary_income", "jpigp_cor:ProfitLossBeforeTaxIFRS", CYD),
    ("prior_ordinary_income", "jpigp_cor:ProfitLossBeforeTaxIFRS", PYD),
    (
        "net_income_owners",
        JC + "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults",
        CYD,
    ),
    (
        "prior_net_income_owners",
        JC + "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults",
        PYD,
    ),
    (
        "operating_cash_flow",
        JC + "CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults",
        CYD,
    ),
    (
        "investing_cash_flow",
        JC + "CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults",
        CYD,
    ),
    (
        "financing_cash_flow",
        JC + "CashFlowsFromUsedInFinancingActivitiesIFRSSummaryOfBusinessResults",
        CYD,
    ),
    ("earnings_per_share", JC + "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults", CYD),
    ("roe", JC + "RateOfReturnOnEquityIFRSSummaryOfBusinessResults", CYD),
    ("net_assets_per_share", JC + "EquityToAssetRatioIFRSSummaryOfBusinessResults", CYI),
]


@pytest.mark.parametrize(
    "name", ["kikkoman_fy2021_ifrs_transition", "kikkoman_fy2021_ifrs_transition_amendment"]
)
@pytest.mark.parametrize("field,own,context", KIKKOMAN, ids=[p[0] for p in KIKKOMAN])
def test_kikkoman_original_and_amendment_read_the_ifrs_facts(name, field, own, context):
    """Kikkoman, FY March 2021, its first IFRS year: the original report
    (S100LM4K) and its amendment (S100O5PX, the one a reader of the latest
    filing sees). Both read the IFRS facts."""
    cf, r = _parse(name)
    assert r.accounting_standard == "IFRS"
    assert getattr(r, field) == _typed(field, _fact(cf, own, context))
    assert r.source_elements[field] == own


def test_kikkoman_amendment_agrees_with_the_original():
    _, original = _parse("kikkoman_fy2021_ifrs_transition")
    _, amendment = _parse("kikkoman_fy2021_ifrs_transition_amendment")
    for field, _own, _context in KIKKOMAN:
        assert getattr(amendment, field) == getattr(original, field), field


@pytest.mark.parametrize("name", ["ifrs_custom_ns_opincome", "ifrs_net_assets_fixture_2"])
@pytest.mark.parametrize(
    "field,own",
    [
        ("prior_net_sales", JC + "RevenueIFRSSummaryOfBusinessResults"),
        (
            "prior_net_income_owners",
            JC + "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults",
        ),
    ],
)
def test_existing_ifrs_fixtures_prior_year_reads_the_ifrs_table(name, field, own):
    """The two existing IFRS fixtures that also tag the J-GAAP highlights
    table for the prior year: the prior-year reads follow the declared
    standard (0.8.x returned the J-GAAP figures here)."""
    cf, r = _parse(name)
    assert getattr(r, field) == int(_fact(cf, own, PYD))
