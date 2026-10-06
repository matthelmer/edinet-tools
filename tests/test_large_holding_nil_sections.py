"""A holder's text section filed as xsi:nil is not a filed dash (0.9.0).

The XBRL row adapter writes a nil fact's value as 「－」 for CSV parity and marks
it nil=True. A holder's text_blocks hold only text the holder filed; the nil
sections are named in nil_text_blocks, and a holder's plain "...NA" statements
(「該当なし。」) are kept in not_applicable. The CSV cannot tell nil from a dash,
so on the CSV source a 「－」 section stays as it was.
"""
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.large_holding import parse_large_holding

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"
H1 = "FilingDateInstant_jplvh010000-lvh_E41402-000FilerLargeVolumeHolder1Member"
COLLATERAL = "SignificantContractsRelatedToSaidStocksEtcSuchAsCollateralAgreementsTextBlock"
COLLATERAL_NA = "SignificantContractsRelatedToSaidStocksEtcSuchAsCollateralAgreementsNA"


@pytest.fixture(scope="module")
def s100xq87():
    return parse_xbrl((FIXTURES / "S100XQ87_type1.zip").read_bytes(), "350", source="xbrl")


def test_nil_sections_are_named_not_stored_as_text(s100xq87):
    holders = s100xq87.joint_holders
    assert [len(h.nil_text_blocks) for h in holders] == [7, 7, 2]
    for h in holders:
        assert not set(h.nil_text_blocks) & set(h.text_blocks)
        assert "－" not in h.text_blocks.values()
    assert sum(len(h.text_blocks) for h in holders) == 22 - 16


def test_each_spc_keeps_its_not_applicable_statement(s100xq87):
    spc1, spc2, adviser = s100xq87.joint_holders
    assert spc1.not_applicable == {COLLATERAL_NA: "該当なし。"}
    assert spc2.not_applicable == {COLLATERAL_NA: "該当なし。"}
    assert adviser.not_applicable == {}
    assert COLLATERAL in spc1.nil_text_blocks


def test_the_report_level_sections_by_context_skip_nil_too(s100xq87):
    for sections in s100xq87.text_blocks_by_context.values():
        assert "－" not in sections.values()


def _rows(value, nil=None):
    row = {"要素ID": f"jplvh_cor:{COLLATERAL}", "コンテキストID": H1, "値": value}
    if nil is not None:
        row["nil"] = nil
    return [{"filename": "x.csv", "data": [row]}]


def test_a_dash_the_holder_filed_as_text_is_kept():
    [h] = parse_large_holding(csv_files=_rows("－", nil=False)).joint_holders
    assert h.text_blocks == {COLLATERAL: "－"} and h.nil_text_blocks == ()


def test_on_the_csv_source_a_dash_section_is_unchanged():
    [h] = parse_large_holding(csv_files=_rows("－")).joint_holders
    assert h.text_blocks == {COLLATERAL: "－"} and h.nil_text_blocks == ()


def test_a_nil_row_is_named_and_left_out():
    [h] = parse_large_holding(csv_files=_rows("－", nil=True)).joint_holders
    assert h.text_blocks == {} and h.nil_text_blocks == (COLLATERAL,)
