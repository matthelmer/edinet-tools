"""Which currency a monetary field holds.

Some filers tag their figures in a foreign currency: beside the yen figures (Beat Holdings,
semi-annual S100YW89, every statement fact twice, USD and JPY, at the same context) or as
their reporting currency (MODEC, semi-annual S100YUQZ: the statements in USD only, the
highlights table in USD and JPY). The rule for every monetary field of the securities,
quarterly and semi-annual reports:

    when a JPY fact and a fact in another unit exist for the same element and context, the
    JPY fact is read; when only another unit exists, it is read, and `units` records its unit
    id (field -> unit id, beside source_elements / source_contexts) for every monetary field
    that holds a value.

Expected values are read out of the fixtures by element, context and unit: no hand-copied
numbers.
"""

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.extraction import Tier, resolve_tiers
from edinet_tools.parsers.quarterly import parse_quarterly_report
from edinet_tools.parsers.securities import parse_securities_report
from edinet_tools.parsers.semi_annual import parse_semi_annual_report
from tests.conftest import (
    load_quarterly_fixture,
    load_securities_fixture,
    load_semi_annual_fixture,
)

XBRL = Path(__file__).parent / "fixtures" / "xbrl"
PER_SHARE = {
    "earnings_per_share",
    "eps_basic_ytd",
    "net_assets_per_share",
    "ifrs_summary_basic_eps",
    "ifrs_summary_bps",
}
UNITLESS = {"equity_ratio", "roe", "ifrs_summary_roe", "num_employees"}
NON_MONETARY = PER_SHARE | UNITLESS


def _units_at(csv_files, element, context):
    """{unit id: value} for the rows of `element` at `context`."""
    out = {}
    for f in csv_files:
        for row in f["data"]:
            if row["要素ID"] == element and row["コンテキストID"] == context:
                out.setdefault(row["ユニットID"], row["値"])
    return out


def _monetary(report):
    return {
        name: getattr(report, name)
        for name in report.source_elements
        if name not in NON_MONETARY and getattr(report, name) is not None
    }


def _recorded(report):
    """The fields `units` covers: every monetary and per-share field holding a value."""
    return {
        name
        for name in report.source_elements
        if name not in UNITLESS and getattr(report, name) is not None
    }


def _beat():
    cf = load_semi_annual_fixture("beat_s100yw89_jpy_and_usd")
    return cf, parse_semi_annual_report(csv_files=cf, doc_id="S100YW89", doc_type_code="160")


def _modec():
    cf = load_semi_annual_fixture("modec_s100yuqz_usd")
    return cf, parse_semi_annual_report(csv_files=cf, doc_id="S100YUQZ", doc_type_code="160")


# ---------------------------------------------------------------------------
# Both JPY and a foreign unit: JPY is read
# ---------------------------------------------------------------------------


def test_beat_reads_the_yen_fact_where_dollars_are_filed_first():
    cf, r = _beat()
    fields = _monetary(r)
    assert len(fields) == 14
    for name, value in fields.items():
        at = _units_at(cf, r.source_elements[name], r.source_contexts[name])
        # both units filed at the field's element and context, and they differ
        assert set(at) == {"JPY", "USD"}, name
        assert at["JPY"] != at["USD"], name
        assert value == int(at["JPY"]), name
        assert r.units[name] == "JPY", name


def test_beat_profit_is_the_yen_figure():
    cf, r = _beat()
    at = _units_at(cf, "jppfs_cor:ProfitLoss", "InterimDuration")
    assert r.profit_loss == int(at["JPY"]) == -343000000
    assert int(at["USD"]) == -2111000


def test_modec_highlights_filed_in_both_units_read_the_yen_figure():
    cf, r = _modec()
    at = _units_at(cf, r.source_elements["net_sales"], r.source_contexts["net_sales"])
    assert set(at) == {"JPY", "USD"}
    assert r.net_sales == int(at["JPY"])
    assert r.units["net_sales"] == "JPY"


# ---------------------------------------------------------------------------
# Only a foreign unit: the value is read and its unit recorded
# ---------------------------------------------------------------------------


def test_modec_statements_filed_only_in_dollars_are_read_and_marked():
    cf, r = _modec()
    at = _units_at(cf, r.source_elements["total_assets"], r.source_contexts["total_assets"])
    assert set(at) == {"USD"}
    assert r.total_assets == int(at["USD"])
    assert r.units["total_assets"] == "USD"


def test_every_monetary_value_carries_the_unit_it_was_read_in():
    cf, r = _modec()
    fields = _monetary(r)
    assert set(r.units) == _recorded(r)
    for name, value in fields.items():
        at = _units_at(cf, r.source_elements[name], r.source_contexts[name])
        assert value == int(at[r.units[name]]), name
        assert r.units[name] == ("JPY" if "JPY" in at else "USD"), name


def _in_dollars(csv_files):
    """A yen filing with every JPY fact relabelled USD: a filer reporting only in dollars."""
    return [
        {
            "filename": f["filename"],
            "data": [
                {**row, "ユニットID": "USD"} if row["ユニットID"] == "JPY" else row
                for row in f["data"]
            ],
        }
        for f in csv_files
    ]


SYNTHETIC = [
    ("securities", "jgaap_control_revenue", "120", parse_securities_report),
    ("quarterly", "kokuyo_s100s4mr_jgaap", "140", parse_quarterly_report),
    ("semi_annual", "kokuyo_s100yucy_jgaap", "160", parse_semi_annual_report),
]


def _load(subdir, name):
    return {
        "securities": load_securities_fixture,
        "quarterly": load_quarterly_fixture,
        "semi_annual": load_semi_annual_fixture,
    }[subdir](name)


@pytest.mark.parametrize("subdir,name,doc_type,parse", SYNTHETIC, ids=[s[0] for s in SYNTHETIC])
def test_a_filing_only_in_dollars_reads_the_dollars_and_says_so(subdir, name, doc_type, parse):
    cf = _load(subdir, name)
    yen = parse(csv_files=cf, doc_id=name, doc_type_code=doc_type)
    usd = parse(csv_files=_in_dollars(cf), doc_id=name, doc_type_code=doc_type)
    fields = _monetary(yen)
    assert fields
    assert "net_sales" in fields or "revenue_ytd" in fields
    for field_name, value in fields.items():
        assert getattr(usd, field_name) == value, field_name
        assert usd.units[field_name] == "USD", field_name
        assert yen.units[field_name] == "JPY", field_name


def test_a_synthetic_dollar_only_net_sales():
    cf = _load("securities", "jgaap_control_revenue")
    r = parse_securities_report(csv_files=_in_dollars(cf), doc_id="x", doc_type_code="120")
    assert r.net_sales is not None
    assert r.units["net_sales"] == "USD"


# ---------------------------------------------------------------------------
# A yen filer: nothing changes but the record of the unit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subdir,name,doc_type,parse", SYNTHETIC, ids=[s[0] for s in SYNTHETIC])
def test_a_yen_filing_reads_as_before(subdir, name, doc_type, parse):
    cf = _load(subdir, name)
    r = parse(csv_files=cf, doc_id=name, doc_type_code=doc_type)
    fields = _monetary(r)
    assert set(r.units) == _recorded(r)
    for field_name, value in fields.items():
        at = _units_at(cf, r.source_elements[field_name], r.source_contexts[field_name])
        assert set(at) == {"JPY"}, field_name
        assert value == int(at["JPY"]), field_name
        assert r.units[field_name] == "JPY"
    per_share = _recorded(r) & PER_SHARE
    assert per_share
    for field_name in per_share:
        at = _units_at(cf, r.source_elements[field_name], r.source_contexts[field_name])
        assert set(at) == {"JPYPerShares"}, field_name
        assert r.units[field_name] == "JPYPerShares", field_name


def test_ratio_fields_are_not_in_units():
    _cf, r = _modec_annual()
    assert r.equity_ratio is not None
    assert not set(r.units) & UNITLESS


# ---------------------------------------------------------------------------
# Per-share figures: the same rule in JPYPerShares
# ---------------------------------------------------------------------------


def _modec_annual():
    cf = load_securities_fixture("modec_s100xu6c_usd")
    return cf, parse_securities_report(csv_files=cf, doc_id="S100XU6C", doc_type_code="120")


def test_modec_annual_eps_and_bps_read_the_yen_figure():
    cf, r = _modec_annual()
    for name in PER_SHARE - {"eps_basic_ytd"}:
        at = _units_at(cf, r.source_elements[name], r.source_contexts[name])
        assert set(at) == {"JPYPerShares", "USDPerShares"}, name
        assert getattr(r, name) == Decimal(at["JPYPerShares"]), name
        assert r.units[name] == "JPYPerShares", name
    assert r.earnings_per_share == Decimal("826.25")


def test_modec_half_year_eps_reads_the_yen_figure():
    cf, r = _modec()
    at = _units_at(
        cf, r.source_elements["earnings_per_share"], r.source_contexts["earnings_per_share"]
    )
    assert r.earnings_per_share == Decimal(at["JPYPerShares"]) == Decimal("532.37")
    assert r.units["earnings_per_share"] == "JPYPerShares"


def test_a_dollar_only_per_share_figure_is_read_and_marked():
    cf = _load("quarterly", "kokuyo_s100s4mr_jgaap")
    usd = [
        {
            "filename": f["filename"],
            "data": [
                (
                    {**row, "ユニットID": "USDPerShares"}
                    if row["ユニットID"] == "JPYPerShares"
                    else row
                )
                for row in f["data"]
            ],
        }
        for f in cf
    ]
    yen = parse_quarterly_report(csv_files=cf, doc_id="x", doc_type_code="140")
    r = parse_quarterly_report(csv_files=usd, doc_id="x", doc_type_code="140")
    assert r.eps_basic_ytd == yen.eps_basic_ytd is not None
    assert r.units["eps_basic_ytd"] == "USDPerShares"


# ---------------------------------------------------------------------------
# The filing's XBRL carries the same unit ids as its CSV
# ---------------------------------------------------------------------------

PACKAGES = [
    (
        "S100YW89",
        _beat,
        ["instance"],
    ),  # its inline header carries a DOCTYPE, which the reader refuses
    ("S100YUQZ", _modec, ["xbrl", "instance"]),
]
CASES = [(doc, load, source) for doc, load, sources in PACKAGES for source in sources]
BAGS = {"raw_fields", "unmapped_fields", "text_blocks", "raw_facts", "source_files", "doc_id"}


@pytest.mark.parametrize("doc,load,source", CASES, ids=[f"{c[0]}-{c[2]}" for c in CASES])
def test_the_package_reads_the_same_values_and_units_as_the_csv(doc, load, source):
    _cf, csv = load()
    x = parse_xbrl((XBRL / f"{doc}_type1.zip").read_bytes(), "160", source=source, doc_id=doc)
    assert x.units == csv.units
    for f in dataclasses.fields(csv):
        if f.name not in BAGS:
            assert getattr(x, f.name) == getattr(csv, f.name), f.name


# ---------------------------------------------------------------------------
# The resolver: the rule holds for every tier kind, and only for money
# ---------------------------------------------------------------------------


def _rows(*facts):
    cols = ("要素ID", "コンテキストID", "ユニットID", "値")
    return [{"filename": "t.csv", "data": [dict(zip(cols, f)) for f in facts]}]


def test_an_element_chain_tier_reads_yen_and_keeps_the_element_order():
    cf = _rows(
        ("jppfs_cor:NetSales", "CurrentYearDuration", "USD", "10"),
        ("jppfs_cor:NetSales", "CurrentYearDuration", "JPY", "1500"),
    )
    hit = resolve_tiers(
        cf,
        (Tier("jppfs_cor:NetSales"),),
        standard="Japan GAAP",
        period="CurrentYearDuration",
        is_consolidated=True,
    )
    assert (hit.value, hit.unit_id) == (1500, "JPY")


def test_a_suffix_tier_reads_yen_per_element():
    el = "jpcrp030000-asr_E99999-000:NetSales"
    cf = _rows(
        (el, "CurrentYearDuration", "USD", "10"),
        (el, "CurrentYearDuration", "JPY", "1500"),
    )
    tiers = (Tier("NetSales", suffix_match=True),)
    hit = resolve_tiers(
        cf, tiers, standard="Japan GAAP", period="CurrentYearDuration", is_consolidated=True
    )
    assert (hit.value, hit.element_id, hit.unit_id) == (1500, el, "JPY")


def test_a_foreign_only_suffix_fact_is_read_with_its_unit():
    el = "jpcrp030000-asr_E99999-000:NetSales"
    cf = _rows((el, "CurrentYearDuration", "EUR", "10"))
    tiers = (Tier("NetSales", suffix_match=True),)
    hit = resolve_tiers(
        cf, tiers, standard="Japan GAAP", period="CurrentYearDuration", is_consolidated=True
    )
    assert (hit.value, hit.unit_id) == (10, "EUR")


def test_string_mode_without_a_preference_reads_the_first_row():
    cf = _rows(
        (
            "jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults",
            "CurrentYearDuration",
            "USDPerShares",
            "3.28",
        ),
        (
            "jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults",
            "CurrentYearDuration",
            "JPYPerShares",
            "532.37",
        ),
    )
    hit = resolve_tiers(
        cf,
        (Tier("jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults"),),
        standard="Japan GAAP",
        period="CurrentYearDuration",
        is_consolidated=True,
        mode="string",
    )
    assert (hit.value, hit.unit_id) == ("3.28", "USDPerShares")


def test_string_mode_prefers_the_unit_asked_for():
    el = "jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults"
    cf = _rows(
        (el, "CurrentYearDuration", "USDPerShares", "3.28"),
        (el, "CurrentYearDuration", "JPYPerShares", "532.37"),
    )
    hit = resolve_tiers(
        cf,
        (Tier(el),),
        standard="Japan GAAP",
        period="CurrentYearDuration",
        is_consolidated=True,
        mode="string",
        prefer_unit="JPYPerShares",
    )
    assert (hit.value, hit.unit_id) == ("532.37", "JPYPerShares")
