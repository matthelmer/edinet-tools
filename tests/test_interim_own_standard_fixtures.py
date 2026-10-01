"""Own-standard selection on verbatim quarterly and semi-annual filings.

Each fixture is a full, unfiltered CSV of a real filing (tests/fixtures/
quarterly, tests/fixtures/semi_annual). The expected value of every asserted
field is read out of the fixture itself, by element and context: no
hand-copied numbers. A replacement also checks that the other standard's fact
is filed at the same context and differs, so a pass means the declared
standard won, not that only one source existed. Every value's recorded
element and context are asserted too.
"""

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.quarterly import parse_quarterly_report
from edinet_tools.parsers.semi_annual import parse_semi_annual_report
from tests.conftest import load_quarterly_fixture, load_semi_annual_fixture

C, G, J = "jpcrp_cor:", "jpigp_cor:", "jppfs_cor:"
SB = "SummaryOfBusinessResults"
NC = "_NonConsolidatedMember"
CYD, PYD, CQI = "CurrentYTDDuration", "Prior1YTDDuration", "CurrentQuarterInstant"
ID, II = "InterimDuration", "InterimInstant"
DECIMAL = {"eps_basic_ytd", "equity_ratio", "earnings_per_share"}

FIXTURES = {
    # Doc 140, Q2 FY Feb 2022, IFRS, parent-only: tags the J-GAAP statements
    # beside the IFRS ones at the same _NonConsolidatedMember contexts.
    "baycurrent": ("quarterly", "baycurrent_s100mhaz_ifrs_parent_only", "140"),
    # Doc 140, Q1 FY Mar 2022, IFRS, consolidated: only IFRS figures.
    "panasonic": ("quarterly", "panasonic_s100m4n0_ifrs", "140"),
    # Doc 140, Q3 FY Dec 2023, J-GAAP (control).
    "kokuyo_q": ("quarterly", "kokuyo_s100s4mr_jgaap", "140"),
    # Doc 150 (quarterly amendment), Q1 FY Jun 2020, IFRS, consolidated.
    "technopro": ("quarterly", "technopro_s100hu96_ifrs_amendment", "150"),
    # Doc 160, half year to 2025-09-30, US GAAP.
    "komatsu": ("semi_annual", "komatsu_s100x2fp_usgaap", "160"),
    # Doc 160, half year to 2025-10-31, IFRS, parent-only, both standards tagged.
    "cyber": ("semi_annual", "cybersolutions_s100x8ur_ifrs_parent_only", "160"),
    # Doc 160, half year to 2026-06-30, IFRS, consolidated.
    "kao": ("semi_annual", "kao_s100yv2r_ifrs", "160"),
    # Doc 160, half year to 2026-06-30, J-GAAP (control).
    "kokuyo_s": ("semi_annual", "kokuyo_s100yucy_jgaap", "160"),
    # Doc 170 (semi-annual amendment), half year to 2025-09-30, IFRS.
    "airwater": ("semi_annual", "airwater_s100ythm_ifrs_amendment", "170"),
}


def _load(key):
    subdir, name, doc_type = FIXTURES[key]
    if subdir == "quarterly":
        cf = load_quarterly_fixture(name)
        return cf, parse_quarterly_report(csv_files=cf, doc_id=name, doc_type_code=doc_type)
    cf = load_semi_annual_fixture(name)
    return cf, parse_semi_annual_report(csv_files=cf, doc_id=name, doc_type_code=doc_type)


_CACHE = {}


def _parsed(key):
    if key not in _CACHE:
        _CACHE[key] = _load(key)
    return _CACHE[key]


def _fact(cf, element, context):
    values = {
        r["値"]
        for f in cf
        for r in f["data"]
        if r["要素ID"] == element and r["コンテキストID"] == context
    }
    assert len(values) <= 1, (element, context, values)
    return values.pop() if values else None


def _typed(field, raw):
    return Decimal(raw) if field in DECIMAL else int(raw)


def _assert_own(key, field, element, context):
    cf, r = _parsed(key)
    raw = _fact(cf, element, context)
    assert raw is not None, (key, element, context)
    assert getattr(r, field) == _typed(field, raw)
    assert r.source_elements[field] == element
    assert r.source_contexts[field] == context


# (fixture, field, own-standard element, context, the other standard's element)
REPLACED = [
    ("baycurrent", "revenue_ytd", C + "RevenueIFRS" + SB, CYD + NC, J + "NetSales"),
    ("baycurrent", "prior_revenue_ytd", C + "RevenueIFRS" + SB, PYD + NC, J + "NetSales"),
    (
        "baycurrent",
        "operating_profit_ytd",
        G + "OperatingProfitLossIFRS",
        CYD + NC,
        J + "OperatingIncome",
    ),
    (
        "baycurrent",
        "prior_operating_profit_ytd",
        G + "OperatingProfitLossIFRS",
        PYD + NC,
        J + "OperatingIncome",
    ),
    ("baycurrent", "total_assets", C + "TotalAssetsIFRS" + SB, CQI + NC, J + "Assets"),
    ("baycurrent", "net_assets", G + "EquityIFRS", CQI + NC, J + "NetAssets"),
    ("baycurrent", "total_liabilities", G + "LiabilitiesIFRS", CQI + NC, J + "Liabilities"),
    (
        "baycurrent",
        "operating_cash_flow_ytd",
        C + "CashFlowsFromUsedInOperatingActivitiesIFRS" + SB,
        CYD + NC,
        C + "NetCashProvidedByUsedInOperatingActivities" + SB,
    ),
    (
        "baycurrent",
        "financing_cash_flow_ytd",
        C + "CashFlowsFromUsedInFinancingActivitiesIFRS" + SB,
        CYD + NC,
        C + "NetCashProvidedByUsedInFinancingActivities" + SB,
    ),
    (
        "baycurrent",
        "eps_basic_ytd",
        C + "BasicEarningsLossPerShareIFRS" + SB,
        CYD + NC,
        C + "BasicEarningsLossPerShare" + SB,
    ),
    (
        "baycurrent",
        "profit_before_tax",
        C + "ProfitLossBeforeTaxIFRS" + SB,
        CYD + NC,
        J + "IncomeBeforeIncomeTaxes",
    ),
    ("cyber", "total_assets", G + "AssetsIFRS", II + NC, J + "Assets"),
    ("cyber", "current_assets", G + "CurrentAssetsIFRS", II + NC, J + "CurrentAssets"),
    ("cyber", "total_liabilities", G + "LiabilitiesIFRS", II + NC, J + "Liabilities"),
    (
        "cyber",
        "current_liabilities",
        G + "TotalCurrentLiabilitiesIFRS",
        II + NC,
        J + "CurrentLiabilities",
    ),
    ("cyber", "net_assets", G + "EquityIFRS", II + NC, J + "NetAssets"),
    ("cyber", "operating_income", G + "OperatingProfitLossIFRS", ID + NC, J + "OperatingIncome"),
    ("cyber", "ordinary_income", G + "ProfitLossBeforeTaxIFRS", ID + NC, J + "OrdinaryIncome"),
    ("cyber", "profit_loss", G + "ProfitLossIFRS", ID + NC, J + "ProfitLoss"),
    (
        "cyber",
        "profit_before_tax",
        C + "ProfitLossBeforeTaxIFRS" + SB,
        ID + NC,
        J + "IncomeBeforeIncomeTaxes",
    ),
    (
        "cyber",
        "earnings_per_share",
        C + "BasicEarningsLossPerShareIFRS" + SB,
        ID + NC,
        C + "BasicEarningsLossPerShare" + SB,
    ),
    (
        "cyber",
        "operating_cash_flow",
        C + "CashFlowsFromUsedInOperatingActivitiesIFRS" + SB,
        ID + NC,
        C + "NetCashProvidedByUsedInOperatingActivities" + SB,
    ),
    (
        "cyber",
        "financing_cash_flow",
        C + "CashFlowsFromUsedInFinancingActivitiesIFRS" + SB,
        ID + NC,
        C + "NetCashProvidedByUsedInFinancingActivities" + SB,
    ),
]


@pytest.mark.parametrize(
    "key,field,element,context,rival", REPLACED, ids=[f"{c[0]}-{c[1]}" for c in REPLACED]
)
def test_own_standard_replaces_the_other_standard(key, field, element, context, rival):
    cf, r = _parsed(key)
    other = _fact(cf, rival, context)
    assert other is not None and other != _fact(cf, element, context), (rival, context)
    _assert_own(key, field, element, context)


# (fixture, field, own-standard element, context): the field was empty or
# holds the own fact with no other standard filed.
OWN = [
    (
        "baycurrent",
        "investing_cash_flow_ytd",
        C + "CashFlowsFromUsedInInvestingActivitiesIFRS" + SB,
        CYD + NC,
    ),
    ("panasonic", "revenue_ytd", C + "RevenueIFRS" + SB, CYD),
    ("panasonic", "operating_profit_ytd", G + "OperatingProfitLossIFRS", CYD),
    ("panasonic", "net_income_ytd", C + "ProfitLossAttributableToOwnersOfParentIFRS" + SB, CYD),
    ("panasonic", "total_assets", C + "TotalAssetsIFRS" + SB, CQI),
    ("panasonic", "net_assets", G + "EquityIFRS", CQI),
    ("panasonic", "total_liabilities", G + "LiabilitiesIFRS", CQI),
    ("panasonic", "net_assets_owners", C + "EquityAttributableToOwnersOfParentIFRS" + SB, CQI),
    (
        "panasonic",
        "operating_cash_flow_ytd",
        C + "CashFlowsFromUsedInOperatingActivitiesIFRS" + SB,
        CYD,
    ),
    (
        "panasonic",
        "investing_cash_flow_ytd",
        C + "CashFlowsFromUsedInInvestingActivitiesIFRS" + SB,
        CYD,
    ),
    (
        "panasonic",
        "financing_cash_flow_ytd",
        C + "CashFlowsFromUsedInFinancingActivitiesIFRS" + SB,
        CYD,
    ),
    ("panasonic", "eps_basic_ytd", C + "BasicEarningsLossPerShareIFRS" + SB, CYD),
    ("panasonic", "equity_ratio", C + "RatioOfOwnersEquityToGrossAssetsIFRS" + SB, CQI),
    ("panasonic", "profit_before_tax", C + "ProfitLossBeforeTaxIFRS" + SB, CYD),
    ("technopro", "revenue_ytd", C + "RevenueIFRS" + SB, CYD),
    ("technopro", "prior_revenue_ytd", C + "RevenueIFRS" + SB, PYD),
    ("technopro", "operating_profit_ytd", G + "OperatingProfitLossIFRS", CYD),
    ("technopro", "net_income_ytd", C + "ProfitLossAttributableToOwnersOfParentIFRS" + SB, CYD),
    ("technopro", "total_assets", C + "TotalAssetsIFRS" + SB, CQI),
    ("technopro", "net_assets_owners", C + "EquityAttributableToOwnersOfParentIFRS" + SB, CQI),
    (
        "technopro",
        "operating_cash_flow_ytd",
        C + "CashFlowsFromUsedInOperatingActivitiesIFRS" + SB,
        CYD,
    ),
    ("technopro", "eps_basic_ytd", C + "BasicEarningsLossPerShareIFRS" + SB, CYD),
    ("technopro", "equity_ratio", C + "RatioOfOwnersEquityToGrossAssetsIFRS" + SB, CQI),
    ("technopro", "profit_before_tax", C + "ProfitLossBeforeTaxIFRS" + SB, CYD),
    ("komatsu", "total_assets", C + "TotalAssetsUSGAAP" + SB, II),
    (
        "komatsu",
        "net_assets",
        C + "EquityIncludingPortionAttributableToNonControllingInterestUSGAAP" + SB,
        II,
    ),
    ("komatsu", "net_sales", C + "RevenuesUSGAAP" + SB, ID),
    ("komatsu", "profit_before_tax", C + "ProfitLossBeforeTaxUSGAAP" + SB, ID),
    (
        "komatsu",
        "profit_attributable_to_owners",
        C + "NetIncomeLossAttributableToOwnersOfParentUSGAAP" + SB,
        ID,
    ),
    ("komatsu", "operating_cash_flow", C + "CashFlowsFromUsedInOperatingActivitiesUSGAAP" + SB, ID),
    ("komatsu", "investing_cash_flow", C + "CashFlowsFromUsedInInvestingActivitiesUSGAAP" + SB, ID),
    ("komatsu", "financing_cash_flow", C + "CashFlowsFromUsedInFinancingActivitiesUSGAAP" + SB, ID),
    ("komatsu", "earnings_per_share", C + "BasicEarningsLossPerShareUSGAAP" + SB, ID),
    ("cyber", "net_sales", C + "RevenueIFRS" + SB, ID + NC),
    (
        "cyber",
        "profit_attributable_to_owners",
        C + "ProfitLossAttributableToOwnersOfParentIFRS" + SB,
        ID + NC,
    ),
    ("kao", "current_liabilities", G + "TotalCurrentLiabilitiesIFRS", II),
    ("kao", "total_assets", C + "TotalAssetsIFRS" + SB, II),
    ("kao", "operating_income", G + "OperatingProfitLossIFRS", ID),
    ("kao", "ordinary_income", G + "ProfitLossBeforeTaxIFRS", ID),
    ("kao", "profit_loss", G + "ProfitLossIFRS", ID),
    ("kao", "net_sales", C + "RevenueIFRS" + SB, ID),
    ("kao", "profit_before_tax", C + "ProfitLossBeforeTaxIFRS" + SB, ID),
    (
        "kao",
        "profit_attributable_to_owners",
        C + "ProfitLossAttributableToOwnersOfParentIFRS" + SB,
        ID,
    ),
    ("kao", "operating_cash_flow", C + "CashFlowsFromUsedInOperatingActivitiesIFRS" + SB, ID),
    ("kao", "earnings_per_share", C + "BasicEarningsLossPerShareIFRS" + SB, ID),
    ("airwater", "current_liabilities", G + "TotalCurrentLiabilitiesIFRS", II),
    ("airwater", "total_assets", C + "TotalAssetsIFRS" + SB, II),
    ("airwater", "operating_income", G + "OperatingProfitLossIFRS", ID),
    ("airwater", "profit_loss", G + "ProfitLossIFRS", ID),
    ("airwater", "net_sales", C + "RevenueIFRS" + SB, ID),
    ("airwater", "profit_before_tax", C + "ProfitLossBeforeTaxIFRS" + SB, ID),
    ("airwater", "earnings_per_share", C + "BasicEarningsLossPerShareIFRS" + SB, ID),
]


@pytest.mark.parametrize("key,field,element,context", OWN, ids=[f"{c[0]}-{c[1]}" for c in OWN])
def test_own_standard_fact(key, field, element, context):
    _assert_own(key, field, element, context)


# (fixture, field, the other standard's element filed at the context, context)
WITHHELD = [
    ("baycurrent", "ordinary_profit_ytd", J + "OrdinaryIncome", CYD + NC),
    ("baycurrent", "prior_ordinary_profit_ytd", J + "OrdinaryIncome", PYD + NC),
]


@pytest.mark.parametrize("key,field,rival,context", WITHHELD, ids=[c[1] for c in WITHHELD])
def test_declared_none_withholds_the_other_standards_fact(key, field, rival, context):
    cf, r = _parsed(key)
    assert _fact(cf, rival, context) is not None
    assert getattr(r, field) is None
    assert field not in r.source_elements and field not in r.source_contexts


@pytest.mark.parametrize(
    "key,field",
    [
        ("baycurrent", "net_assets_owners"),
        ("komatsu", "operating_income"),  # US GAAP tags no operating income here
        ("komatsu", "profit_loss"),  # nor a total-basis profit
        ("komatsu", "ordinary_income"),
        ("komatsu", "current_liabilities"),
    ],
)
def test_no_own_element_is_none(key, field):
    _cf, r = _parsed(key)
    assert getattr(r, field) is None


def test_fallback_is_recorded_as_the_other_standards_element():
    """BayCurrent tags its IFRS equity ratio only in a filer-local element;
    the legacy fallback serves the J-GAAP ratio, and the source says so."""
    _assert_own("baycurrent", "equity_ratio", C + "EquityToAssetRatio" + SB, CQI + NC)


# ---------------------------------------------------------------------------
# J-GAAP controls: unchanged fields read the J-GAAP fact; the new J-GAAP
# fields are the filing's own facts.
# ---------------------------------------------------------------------------

KOKUYO_Q = [
    ("revenue_ytd", J + "NetSales", CYD),
    ("operating_profit_ytd", J + "OperatingIncome", CYD),
    ("ordinary_profit_ytd", J + "OrdinaryIncome", CYD),
    ("net_income_ytd", J + "ProfitLossAttributableToOwnersOfParent", CYD),
    ("total_assets", J + "Assets", CQI),
    ("net_assets", J + "NetAssets", CQI),
    ("total_liabilities", J + "Liabilities", CQI),
    ("operating_cash_flow_ytd", C + "NetCashProvidedByUsedInOperatingActivities" + SB, CYD),
    ("eps_basic_ytd", C + "BasicEarningsLossPerShare" + SB, CYD),
    ("equity_ratio", C + "EquityToAssetRatio" + SB, CQI),
    ("profit_before_tax", J + "IncomeBeforeIncomeTaxes", CYD),
]
KOKUYO_S = [
    ("total_assets", J + "Assets", II),
    ("current_assets", J + "CurrentAssets", II),
    ("total_liabilities", J + "Liabilities", II),
    ("current_liabilities", J + "CurrentLiabilities", II),
    ("net_assets", J + "NetAssets", II),
    ("operating_income", J + "OperatingIncome", ID),
    ("ordinary_income", J + "OrdinaryIncome", ID),
    ("profit_loss", J + "ProfitLoss", ID),
    ("net_sales", C + "NetSales" + SB, ID),
    ("profit_before_tax", J + "IncomeBeforeIncomeTaxes", ID),
    ("profit_attributable_to_owners", C + "ProfitLossAttributableToOwnersOfParent" + SB, ID),
    ("operating_cash_flow", C + "NetCashProvidedByUsedInOperatingActivities" + SB, ID),
    ("earnings_per_share", C + "BasicEarningsLossPerShare" + SB, ID),
]


@pytest.mark.parametrize(
    "key,field,element,context",
    [("kokuyo_q", *c) for c in KOKUYO_Q] + [("kokuyo_s", *c) for c in KOKUYO_S],
    ids=[f"q-{c[0]}" for c in KOKUYO_Q] + [f"s-{c[0]}" for c in KOKUYO_S],
)
def test_jgaap_control(key, field, element, context):
    _assert_own(key, field, element, context)


def test_jgaap_quarterly_has_no_owners_equity():
    _cf, r = _parsed("kokuyo_q")
    assert r.accounting_standard == "Japan GAAP"
    assert r.net_assets_owners is None


# ---------------------------------------------------------------------------
# The filing's XBRL reads the same as its CSV
# ---------------------------------------------------------------------------

XBRL = Path(__file__).parent / "fixtures" / "xbrl"
PACKAGES = [
    ("S100MHAZ", "baycurrent"),
    ("S100M4N0", "panasonic"),
    ("S100X2FP", "komatsu"),
    ("S100YV2R", "kao"),
]
BAGS = {"raw_fields", "unmapped_fields", "text_blocks", "raw_facts", "source_files", "doc_id"}


@pytest.mark.parametrize("source", ["xbrl", "instance"])
@pytest.mark.parametrize("doc,key", PACKAGES, ids=[p[0] for p in PACKAGES])
def test_every_typed_field_reads_the_same_from_the_package(doc, key, source):
    _cf, csv = _parsed(key)
    x = parse_xbrl(
        (XBRL / f"{doc}_type1.zip").read_bytes(), FIXTURES[key][2], source=source, doc_id=doc
    )
    for f in dataclasses.fields(csv):
        if f.name not in BAGS:
            assert getattr(x, f.name) == getattr(csv, f.name), f.name
