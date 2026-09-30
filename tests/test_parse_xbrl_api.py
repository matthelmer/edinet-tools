"""The public surface for the XBRL sources: Document.parse(source=...) and parse_xbrl()."""

from pathlib import Path

import pytest

from edinet_tools import Document
from edinet_tools.parsers import LargeHoldingReport, RawReport, parse_xbrl
from edinet_tools.parsers.generic import parse_raw
from edinet_tools.parsers.extraction import extract_rows_from_package

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"


class FakeClient:
    """Serves the fixture packages by EDINET download type and records what was asked."""

    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.calls = []

    def download_filing_raw(self, doc_id, raise_on_error=True, type=5):
        self.calls.append(type)
        return (FIXTURES / f"{doc_id}_type{type}.zip").read_bytes()


def document(doc_id="S100YRDM", code="350"):
    client = FakeClient(doc_id)
    return Document({"docID": doc_id, "docTypeCode": code}, client=client), client


def test_parse_default_is_the_csv_as_before():
    doc, client = document()
    report = doc.parse()
    assert client.calls == [5]
    assert isinstance(report, LargeHoldingReport)
    assert report.source_files[0].endswith(".csv")


@pytest.mark.parametrize("source,row_source", [("xbrl", "ixbrl"), ("instance", "instance")])
def test_parse_xbrl_sources_fetch_the_filing_type_1(source, row_source):
    doc, client = document()
    report = doc.parse(source=source)
    assert client.calls == [1]
    assert isinstance(report, LargeHoldingReport)
    assert report.doc_id == "S100YRDM" and report.doc_type_code == "350"
    assert report.source_files == ["jplvh010000-lvh-001_E36104-000_2026-07-10_01_2026-07-24.xbrl"]
    assert report.target_company is not None


def test_parse_rejects_an_unknown_source():
    doc, client = document()
    with pytest.raises(ValueError, match="source"):
        doc.parse(source="pdf")
    assert client.calls == []


def test_parse_xbrl_helper_for_a_package_already_held():
    zip_bytes = (FIXTURES / "S100YRDM_type1.zip").read_bytes()
    report = parse_xbrl(zip_bytes, "350", doc_id="S100YRDM")
    assert isinstance(report, LargeHoldingReport)
    assert report.doc_id == "S100YRDM"
    assert report.ownership_pct is not None
    assert parse_xbrl(zip_bytes, "350", source="instance").ownership_pct == report.ownership_pct


def test_parse_xbrl_falls_back_to_raw_for_types_without_a_parser():
    zip_bytes = (FIXTURES / "S100YRDM_type1.zip").read_bytes()
    report = parse_xbrl(zip_bytes, "999")
    assert isinstance(report, RawReport)
    assert report.raw_fields["jplvh_cor:TotalNumberOfStocksEtcHeld"]


def test_parse_raw_accepts_csv_files():
    rows = extract_rows_from_package((FIXTURES / "S100YRDM_type1.zip").read_bytes())
    report = parse_raw(csv_files=rows, doc_id="X", doc_type_code="999")
    assert report.doc_id == "X" and report.raw_fields
