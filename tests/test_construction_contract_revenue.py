"""Contractors whose only line is 完成工事高 tag their top line as
jppfs_cor:NetSalesOfCompletedConstructionContractsCNS, with the highlights figure in a
filer-local namespace and no NetSales element. Nippon Densetsu Kogyo's half-year S100UN70,
annual S100YGLL and quarterly S100SQ08 had no net_sales; they read the FS element.

Fixtures: the filings' DEI rows and every NetSales-named row, as filed.
"""
from edinet_tools.parsers.quarterly import parse_quarterly_report
from edinet_tools.parsers.securities import parse_securities_report
from edinet_tools.parsers.semi_annual import parse_semi_annual_report
from tests.conftest import (
    load_quarterly_fixture,
    load_securities_fixture,
    load_semi_annual_fixture,
)

ELEMENT = "jppfs_cor:NetSalesOfCompletedConstructionContractsCNS"


def test_half_year_reads_completed_construction_sales():
    cf = load_semi_annual_fixture("nihondensetsu_s100un70_construction")
    r = parse_semi_annual_report(csv_files=cf, doc_id="S100UN70", doc_type_code="160")
    assert r.net_sales == 75625000000
    assert r.source_elements["net_sales"] == ELEMENT
    assert r.source_contexts["net_sales"] == "CurrentYTDDuration"
    assert r.units["net_sales"] == "JPY"


def test_annual_reads_completed_construction_sales_both_years():
    cf = load_securities_fixture("nihondensetsu_s100ygll_construction")
    r = parse_securities_report(csv_files=cf, doc_id="S100YGLL", doc_type_code="120")
    assert r.net_sales == 229207000000
    assert r.source_elements["net_sales"] == ELEMENT
    assert r.prior_net_sales == 216922000000


def test_a_general_sales_total_outranks_completed_construction_sales():
    # A contractor with side businesses tags 売上高合計 as jppfs_cor:NetSales; the
    # completed-construction line is then a component and never the top line.
    cf = load_securities_fixture("nihondensetsu_s100ygll_construction")
    total = [
        {**row, "要素ID": "jppfs_cor:NetSales", "値": "300000000000"}
        for row in cf[0]["data"]
        if row["要素ID"] == ELEMENT and row["コンテキストID"] == "CurrentYearDuration"
    ]
    cf = [{"filename": cf[0]["filename"], "data": cf[0]["data"] + total}]
    r = parse_securities_report(csv_files=cf, doc_id="S100YGLL", doc_type_code="120")
    assert r.net_sales == 300000000000
    assert r.source_elements["net_sales"] == "jppfs_cor:NetSales"


def test_quarterly_reads_completed_construction_sales_both_periods():
    cf = load_quarterly_fixture("nihondensetsu_s100sq08_construction")
    r = parse_quarterly_report(csv_files=cf, doc_id="S100SQ08", doc_type_code="140")
    assert r.revenue_ytd == 117511000000
    assert r.source_elements["revenue_ytd"] == ELEMENT
    assert r.prior_revenue_ytd == 101722000000


def test_quarterly_withholds_construction_sales_beside_operating_revenue():
    # Traders Holdings (S100NH1S), a broker, files 完成工事高 of 0 for a construction
    # sideline beside its 営業収益 of ¥4,621 million; the 0 is not its top line.
    cf = load_quarterly_fixture("traders_s100nh1s_broker_construction")
    r = parse_quarterly_report(csv_files=cf, doc_id="S100NH1S", doc_type_code="140")
    assert r.prior_revenue_ytd is None
    assert r.revenue_ytd is None
    assert "prior_revenue_ytd" not in r.source_elements
