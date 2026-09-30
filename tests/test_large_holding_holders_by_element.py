"""Joint holders read by element ID in the holder's context (0.9.0), on both sources.

The holder parser used to key fields on the CSV's item-name column (項目名), which the XBRL
does not carry, and read a holder's share count from the 本文 (main-clause) line only, so a
holder reporting under Item 2 (discretionary accounts; Dalton Investments on S100YRDM) had
None. It now reads `TotalNumberOfStocksEtcHeld` in the holder's context. Text sections carried
by a holder's context are kept per holder instead of the last holder's overwriting the others.
"""

from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.extraction import extract_csv_from_zip
from edinet_tools.parsers.large_holding import parse_large_holding

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"
TRADES = (
    "DetailsOfAcquisitionsAndDisposalsOfStocksEtcIssuedByIssuerOfSaidStocksEtcDuringLast60Days"
    "IfCategorizedAsShortTermLargeVolumeTransferTextBlock"
)


def parsed(doc, source):
    if source == "csv":
        files = extract_csv_from_zip((FIXTURES / f"{doc}_type5.zip").read_bytes())
        return parse_large_holding(csv_files=files, doc_id=doc, doc_type_code="350")
    return parse_xbrl((FIXTURES / f"{doc}_type1.zip").read_bytes(), "350", source=source)


SOURCES = ["csv", "ixbrl", "instance"]


@pytest.mark.parametrize("source", SOURCES)
def test_s100yrdm_three_share_counts_including_dalton_under_item_2(source):
    r = parsed("S100YRDM", source)
    assert [h.shares_held for h in r.joint_holders] == [3269300, 1250000, 6190300]
    assert sum(h.shares_held for h in r.joint_holders) == r.shares_held == 10709600
    # all three hold only stock: shares equal the 総数 total
    assert [h.total_held for h in r.joint_holders] == [3269300, 1250000, 6190300]
    assert r.total_held == 10709600
    assert (
        r.joint_holders[2].name_jp
        == "ダルトン・インベストメンツ・インク（Dalton Investments, Inc.）"
    )
    assert [h.edinet_code for h in r.joint_holders] == ["E36104", "E36950", "E39237"]


@pytest.mark.parametrize("source", SOURCES)
def test_s100yd3h_dalton_share_count(source):
    r = parsed("S100YD3H", source)
    assert all(h.shares_held is not None for h in r.joint_holders)


H1 = "FilingDateInstant_jplvh010000-lvh_E99999-000FilerLargeVolumeHolder1Member"
H2 = "FilingDateInstant_jplvh010000-lvh_E99999-000FilerLargeVolumeHolder2Member"
STOCK = "jplvh_cor:StocksOrInvestmentSecuritiesEtcArticle27233"
WARRANTS_MAIN = "jplvh_cor:SubscriptionRightsToSharesArticle27233MainClause"
TOTAL = "jplvh_cor:TotalNumberOfStocksEtcHeld"


def _lh(rows):
    data = [{"要素ID": e, "項目名": "", "コンテキストID": c, "値": v} for e, c, v in rows]
    return parse_large_holding(
        csv_files=[{"filename": "x", "data": data}], doc_id="X", doc_type_code="350"
    )


def test_holder_fields_are_keyed_by_element_not_item_name():
    """The XBRL rows carry no item name; the holder parser must not need one."""
    r = _lh(
        [
            ("jplvh_cor:Name", H1, "甲株式会社"),
            ("jplvh_cor:EDINETCodeDEI", H1, "E1"),
            (STOCK + "MainClause", H1, "1000"),
            (WARRANTS_MAIN, H1, "200"),
            (TOTAL, H1, "1200"),
        ]
    )
    (h,) = r.joint_holders
    assert (h.name_jp, h.edinet_code, h.warrants_held) == ("甲株式会社", "E1", 200)


def test_shares_held_counts_stock_only_and_total_held_includes_warrants():
    """shares_held is the stock lines (本文 + 第1号 + 第2号); total_held is 総数, which
    includes potential shares (warrants, convertibles)."""
    r = _lh(
        [
            (STOCK + "MainClause", H1, "1000"),
            (STOCK + "Item1", H1, "－"),
            (STOCK + "Item2", H1, "300"),
            (WARRANTS_MAIN, H1, "200"),
            (TOTAL, H1, "1500"),
            (STOCK + "MainClause", H2, "400"),
            (TOTAL, H2, "400"),
            # group (un-dimensioned) rows
            (STOCK + "MainClause", "FilingDateInstant", "1400"),
            (STOCK + "Item2", "FilingDateInstant", "300"),
            (TOTAL, "FilingDateInstant", "1900"),
        ]
    )
    h1, h2 = r.joint_holders
    assert (h1.shares_held, h1.total_held, h1.warrants_held) == (1300, 1500, 200)
    assert h1.shares_held < h1.total_held
    assert (h2.shares_held, h2.total_held) == (400, 400)
    assert (r.shares_held, r.total_held) == (1700, 1900)


def test_shares_held_is_none_when_no_stock_line_is_filed():
    """No stock line, no share count: the total is never used in its place."""
    r = _lh([(TOTAL, H1, "1200")])
    assert r.joint_holders[0].shares_held is None and r.joint_holders[0].total_held == 1200
    assert r.shares_held is None and r.total_held == 1200


def test_japanese_dei_name_is_preferred_over_the_plain_name_row():
    ctx = "FilingDateInstant_jplvh010000-lvh_E99999-000FilerLargeVolumeHolder1Member"
    rows = [
        {"要素ID": "jplvh_cor:Name", "コンテキストID": ctx, "値": "plain"},
        {"要素ID": "jplvh_cor:FilerNameInJapaneseDEI", "コンテキストID": ctx, "値": "dei"},
    ]
    r = parse_large_holding(
        csv_files=[{"filename": "x", "data": rows}], doc_id="X", doc_type_code="350"
    )
    assert r.joint_holders[0].name_jp == "dei"


@pytest.mark.parametrize("source", SOURCES)
def test_s100y8gb_each_holder_keeps_its_own_trading_table(source):
    r = parsed("S100Y8GB", source)
    first, second = r.joint_holders
    assert "31,100" in first.text_blocks[TRADES] and "216,800" not in first.text_blocks[TRADES]
    assert "216,800" in second.text_blocks[TRADES] and "31,100" not in second.text_blocks[TRADES]
    by_ctx = r.text_blocks_by_context
    assert len([c for c in by_ctx if TRADES in by_ctx[c]]) == 2
    # text_blocks keeps its meaning: one value per element (the last), for compatibility
    assert r.text_blocks[TRADES] == second.text_blocks[TRADES]


@pytest.mark.parametrize("source", ["ixbrl", "instance"])
def test_s100y8gb_trading_table_cells_are_separated(source):
    first = parsed("S100Y8GB", source).joint_holders[0]
    assert "令和8年5月19日\t株券\t90,000\t0.29\t市場内\t処分" in first.text_blocks[TRADES]


def test_joint_holders_stay_hashable():
    r = parsed("S100Y8GB", "csv")
    assert len({h for h in r.joint_holders}) == 2
