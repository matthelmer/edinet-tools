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


SOURCES = ["csv", "xbrl", "instance"]


@pytest.mark.parametrize("source", SOURCES)
def test_s100yrdm_three_share_counts_including_dalton_under_item_2(source):
    r = parsed("S100YRDM", source)
    assert [h.shares_held for h in r.joint_holders] == [3269300, 1250000, 6190300]
    # the group figure is the filing's own 総数 row, not a sum
    assert r.shares_held == 10709600
    # no deductions on this filing: the stock lines before deductions equal 総数
    assert [h.stock_lines_held for h in r.joint_holders] == [3269300, 1250000, 6190300]
    assert r.stock_lines_held == 10709600
    assert (
        r.joint_holders[2].name_jp
        == "ダルトン・インベストメンツ・インク（Dalton Investments, Inc.）"
    )
    assert [h.edinet_code for h in r.joint_holders] == ["E36104", "E36950", "E39237"]


@pytest.mark.parametrize("source", SOURCES)
def test_s100yd3h_dalton_share_count(source):
    r = parsed("S100YD3H", source)
    assert all(h.shares_held is not None for h in r.joint_holders)


@pytest.mark.parametrize("source", SOURCES)
def test_s100z4av_holders_split_across_the_main_clause_and_item_2(source):
    """光通信's group on 手間いらず (2477), filed 2026-09-29. Holder 1 reports 64,800 on the
    本文 line and 86,100 under Item 2; holder 2 reports 0 on the 本文 line and 21,600 under
    Item 2. Each holder's shares_held is its own 総数 row, which is also what the filing's
    breakdown table (共同保有における株券等保有割合の内訳) prints. Read from the 本文 line
    alone, holder 1 came out at 64,800, holder 2 at 0, and the five summed to 510,300
    against a filed group total of 618,000."""
    r = parsed("S100Z4AV", source)
    assert [h.edinet_code for h in r.joint_holders] == [
        "E35239", "E35629", "E41499", "E33140", "E36209"]
    assert [h.shares_held for h in r.joint_holders] == [150900, 21600, 390700, 25600, 29200]
    # a zero on the 本文 line is not a holder with nothing: holder 2 holds under Item 2
    assert r.joint_holders[1].shares_held == 21600
    # the group figure is the filing's own 総数 row; on this filing the holders' rows add up to it
    assert r.shares_held == 618000
    assert sum(h.shares_held for h in r.joint_holders) == r.shares_held
    assert str(r.ownership_pct) == "0.0954"
    # no deductions on this filing: the stock lines before deductions equal 総数
    assert [h.stock_lines_held for h in r.joint_holders] == [150900, 21600, 390700, 25600, 29200]
    assert r.stock_lines_held == 618000


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


MARGIN = "jplvh_cor:NumberOfStocksEtcToDeductAsSoldOnMarginTrading"


def test_shares_held_is_the_filed_total_after_a_margin_sale_deduction():
    """shares_held is 総数 as filed (TotalNumberOfStocksEtcHeld): the gross holding less
    shares sold on margin and less shares counted twice between joint holders.
    stock_lines_held is the stock lines before any deduction."""
    r = _lh(
        [
            (STOCK + "MainClause", H1, "1000"),
            (STOCK + "Item2", H1, "300"),
            (MARGIN, H1, "100"),
            (TOTAL, H1, "1200"),
            (STOCK + "MainClause", H2, "400"),
            (TOTAL, H2, "400"),
            (STOCK + "MainClause", "FilingDateInstant", "1400"),
            (STOCK + "Item2", "FilingDateInstant", "300"),
            (MARGIN, "FilingDateInstant", "100"),
            (TOTAL, "FilingDateInstant", "1600"),
        ]
    )
    h1, h2 = r.joint_holders
    assert (h1.shares_held, h1.stock_lines_held) == (1200, 1300)
    assert h1.stock_lines_held > h1.shares_held
    assert (h2.shares_held, h2.stock_lines_held) == (400, 400)
    assert (r.shares_held, r.stock_lines_held) == (1600, 1700)


def test_stock_lines_held_is_none_when_no_stock_line_is_filed():
    r = _lh([(TOTAL, H1, "1200")])
    assert r.joint_holders[0].shares_held == 1200 and r.joint_holders[0].stock_lines_held is None
    assert r.shares_held == 1200 and r.stock_lines_held is None


@pytest.mark.parametrize("doc", ["S100YRDM", "S100YD3H", "S100Y8GB"])
@pytest.mark.parametrize("source", SOURCES)
def test_group_shares_held_is_the_filings_own_total(doc, source):
    r = parsed(doc, source)
    filed = {
        f.value
        for f in r.raw_facts
        if f.element_id == TOTAL and f.context_id == "FilingDateInstant"
    }
    assert filed == {str(r.shares_held)}


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


@pytest.mark.parametrize("source", ["xbrl", "instance"])
def test_s100y8gb_trading_table_cells_are_separated(source):
    first = parsed("S100Y8GB", source).joint_holders[0]
    assert "令和8年5月19日\t株券\t90,000\t0.29\t市場内\t処分" in first.text_blocks[TRADES]


def test_joint_holders_stay_hashable():
    r = parsed("S100Y8GB", "csv")
    assert len({h for h in r.joint_holders}) == 2


def test_stock_lines_are_every_one_the_filings_taxonomy_defines():
    """STOCK_LINE_ELEMENTS equals the set of StocksOrInvestmentSecuritiesEtc Article 27-23(3)
    elements the fixtures' presentation and definition linkbases reference (edinet-tools
    ships no jplvh taxonomy data to check against)."""
    import re
    import zipfile

    from edinet_tools.parsers.large_holding import STOCK_LINE_ELEMENTS

    found = set()
    for p in FIXTURES.glob("*_type1.zip"):
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if n.endswith(("_pre.xml", "_def.xml")):
                    found |= set(
                        re.findall(
                            r"StocksOrInvestmentSecuritiesEtcArticle27233\w+",
                            z.read(n).decode("utf-8"),
                        )
                    )
    assert found == {e.split(":")[1] for e in STOCK_LINE_ELEMENTS}
    assert len(found) == 4


def test_item_3_stock_is_counted_in_stock_lines_held():
    r = _lh(
        [
            (STOCK + "MainClause", H1, "1000"),
            (STOCK + "Item3", H1, "250"),
            (TOTAL, H1, "1250"),
            (STOCK + "MainClause", "FilingDateInstant", "1000"),
            (STOCK + "Item3", "FilingDateInstant", "250"),
            (TOTAL, "FilingDateInstant", "1250"),
        ]
    )
    assert (r.joint_holders[0].stock_lines_held, r.joint_holders[0].shares_held) == (1250, 1250)
    assert (r.stock_lines_held, r.shares_held) == (1250, 1250)


PURPOSE = "jplvh_cor:PurposeOfHolding"
PROPOSAL = "jplvh_cor:ActOfMakingImportantProposalEtc"


@pytest.mark.parametrize("source", SOURCES)
def test_s100yrdm_each_holder_states_its_own_purpose(source):
    r = parsed("S100YRDM", source)
    p1, p2, p3 = (h.purpose for h in r.joint_holders)
    assert p1.startswith("投資及び経営陣に対する経営の助言") and "ニッポン・アクティブ・バリュー・ファンド" in p1
    assert p2.startswith("投資及び経営陣に対する経営の助言") and "エヌエーブイエフ" in p2
    assert p3.startswith("提出者は、発行者の株価が過小評価されており")
    assert [h.important_proposal for h in r.joint_holders] == ["上記（2）保有目的に記載のとおり。"] * 3
    # the report-level purpose stays the primary filer's
    assert r.purpose == p1


@pytest.mark.parametrize("source", SOURCES)
def test_s100yd3h_each_holder_states_its_own_purpose(source):
    r = parsed("S100YD3H", source)
    purposes = [h.purpose for h in r.joint_holders]
    assert "ニッポン・アクティブ・バリュー・ファンド" in purposes[0]
    assert "エヌエーブイエフ" in purposes[1]
    assert purposes[2].startswith("提出者は、")
    assert len(set(purposes)) == 3


@pytest.mark.parametrize("source", SOURCES)
def test_s100y8gb_a_holder_that_states_no_purpose_gives_none(source):
    first, second = parsed("S100Y8GB", source).joint_holders
    assert first.purpose.startswith("株主価値向上に資する、資本政策及びコーポレートガバナンス")
    assert second.purpose is None  # filed as 「－」
    assert (first.important_proposal, second.important_proposal) == (None, None)  # 「該当なし」


def test_holder_purpose_is_read_in_the_holders_own_context():
    r = _lh(
        [
            (PURPOSE, H1, "  純投資  "),
            (PURPOSE, H2, "経営参加"),
            (PROPOSAL, H2, "株主提案を行う予定"),
        ]
    )
    h1, h2 = r.joint_holders
    assert (h1.purpose, h1.important_proposal) == ("純投資", None)
    assert (h2.purpose, h2.important_proposal) == ("経営参加", "株主提案を行う予定")


def test_holder_purpose_is_left_out_of_equality_and_hashing():
    from dataclasses import fields, replace

    from edinet_tools.parsers.large_holding import JointHolder

    by_name = {f.name: f for f in fields(JointHolder)}
    for name in ("purpose", "important_proposal"):
        assert not by_name[name].compare and not by_name[name].hash
    h = parsed("S100Y8GB", "csv").joint_holders[0]
    assert replace(h, purpose="x", important_proposal="y") == h


@pytest.mark.parametrize("source", SOURCES)
def test_s100mzz3_a_holder_edinet_code_filed_empty_reads_as_none(source):
    """The holder's `jplvh_cor:EDINETCodeDEI` fact is filed empty. EDINET's CSV prints 「－」
    for it; a dash is not a code, so the report's `filer_edinet_code` is None on every
    source, as the holder's own `edinet_code` already was."""
    r = parsed("S100MZZ3", source)
    assert r.filer_edinet_code is None
    assert r.joint_holders[0].edinet_code is None

