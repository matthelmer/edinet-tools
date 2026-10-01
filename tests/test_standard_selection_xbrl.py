"""Own-standard selection reads the same from the filing's XBRL as from the CSV.

S100YRSR: Cyber Solutions, annual report for the year to April 2026, IFRS,
a parent-only filer tagging the J-GAAP highlights table beside the IFRS one. type=1 package
(trimmed to its inline XBRL and instance members) and type=5 CSV, both as
EDINET serves them (tests/fixtures/xbrl/SOURCES.txt).
"""

from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.extraction import extract_csv_from_zip, extract_value
from edinet_tools.parsers.securities import parse_securities_report

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"
DOC = "S100YRSR"
# A parent-only filer (no consolidated statements): every fact sits at the
# _NonConsolidatedMember context.
NC = "_NonConsolidatedMember"
CYD, PYD, CYI = "CurrentYearDuration" + NC, "Prior1YearDuration" + NC, "CurrentYearInstant" + NC

# Fields where the filing tags a J-GAAP fact that differs from the IFRS one,
# with the J-GAAP element and the context.
CONTESTED = [
    ("ordinary_income", "jpcrp_cor:OrdinaryIncomeLossSummaryOfBusinessResults", CYD),
    ("prior_ordinary_income", "jpcrp_cor:OrdinaryIncomeLossSummaryOfBusinessResults", PYD),
    (
        "operating_cash_flow",
        "jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults",
        CYD,
    ),
    ("total_assets", "jpcrp_cor:TotalAssetsSummaryOfBusinessResults", CYI),
    ("earnings_per_share", "jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults", CYD),
]


def _is_ifrs(element_id):
    local = element_id.rpartition(":")[2]
    return local.endswith("IFRS") or "IFRSSummaryOfBusinessResults" in local


@pytest.fixture(scope="module")
def parsed():
    t1 = (FIXTURES / f"{DOC}_type1.zip").read_bytes()
    t5 = (FIXTURES / f"{DOC}_type5.zip").read_bytes()
    csv_files = extract_csv_from_zip(t5)
    return {
        "csv_files": csv_files,
        "csv": parse_securities_report(csv_files=csv_files, doc_id=DOC, doc_type_code="120"),
        "xbrl": parse_xbrl(t1, "120", source="xbrl", doc_id=DOC),
        "instance": parse_xbrl(t1, "120", source="instance", doc_id=DOC),
    }


@pytest.mark.parametrize("source", ["xbrl", "instance"])
@pytest.mark.parametrize("field,jgaap,context", CONTESTED, ids=[c[0] for c in CONTESTED])
def test_each_source_reads_the_ifrs_fact(parsed, source, field, jgaap, context):
    csv, other = parsed["csv"], parsed[source]
    assert csv.accounting_standard == other.accounting_standard == "IFRS"
    assert csv.is_consolidated is False
    rival = extract_value(parsed["csv_files"], jgaap, context_patterns=[context])
    assert rival is not None and str(getattr(csv, field)) != rival.replace(",", "")
    assert getattr(other, field) == getattr(csv, field)
    assert _is_ifrs(csv.source_elements[field])


@pytest.mark.parametrize("source", ["xbrl", "instance"])
def test_source_elements_are_the_same_from_every_source(parsed, source):
    assert parsed[source].source_elements == parsed["csv"].source_elements
