"""The rows adapter: XBRL facts as the rows EDINET's CSV gives, so every parser reads them.

Row keys are the CSV's columns (項目名 is '' — item names come from taxonomy label files, which
the reader does not read) plus html, decimals, scale, sign, nil, period_start, period_end,
instant and source. On every fixture the rows carry the CSV's element IDs, context IDs and unit
IDs, fact for fact.
"""

import collections
from pathlib import Path

import pytest

from edinet_tools.parsers._xbrl_model import normalize_space
from edinet_tools.parsers.extraction import extract_csv_from_zip, extract_rows_from_package

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"
DOCS = ["S100Y4NW", "S100Y8GB", "S100YRDM", "S100YD3H", "S100YWE2"]
CSV_LIMIT = 30000  # EDINET's CSV cuts every value at this many characters

CSV_COLUMNS = [
    "要素ID",
    "項目名",
    "コンテキストID",
    "相対年度",
    "連結・個別",
    "期間・時点",
    "ユニットID",
    "単位",
    "値",
]
EXTRA = [
    "html",
    "decimals",
    "scale",
    "sign",
    "nil",
    "period_start",
    "period_end",
    "instant",
    "source",
]


def package(doc, kind):
    return (FIXTURES / f"{doc}_type{kind}.zip").read_bytes()


def csv_rows(doc):
    return [
        r
        for f in extract_csv_from_zip(package(doc, 5))
        for r in f["data"]
        if r["要素ID"] != "要素ID"
    ]


def xbrl_rows(doc, source):
    return [r for f in extract_rows_from_package(package(doc, 1), source=source) for r in f["data"]]


@pytest.mark.parametrize("source", ["ixbrl", "instance"])
def test_rows_have_the_csv_columns_and_the_xbrl_extras(source):
    files = extract_rows_from_package(package("S100YRDM", 1), source=source)
    assert [f["filename"] for f in files] == [
        "jplvh010000-lvh-001_E36104-000_2026-07-10_01_2026-07-24.xbrl"
    ]
    row = files[0]["data"][0]
    assert list(row) == CSV_COLUMNS + EXTRA
    assert row["項目名"] == "" and row["source"] == source


def test_a_holder_row_carries_its_real_date_unit_and_precision():
    rows = xbrl_rows("S100YRDM", "ixbrl")
    held = [
        r
        for r in rows
        if r["要素ID"] == "jplvh_cor:TotalNumberOfStocksEtcHeld"
        and r["コンテキストID"].endswith("FilerLargeVolumeHolder3Member")
    ][0]
    assert held["値"] == "6190300"
    assert (held["ユニットID"], held["decimals"], held["instant"]) == ("shares", "0", "2026-07-24")
    assert held["期間・時点"] == "時点" and held["period_start"] is None


def test_a_duration_row_carries_both_dates():
    rows = xbrl_rows("S100YWE2", "ixbrl")
    r = [r for r in rows if r["コンテキストID"] == "InterimDuration" and r["ユニットID"] == "JPY"][
        0
    ]
    assert (r["period_start"], r["period_end"], r["期間・時点"]) == (
        "2026-01-01",
        "2026-06-30",
        "期間",
    )


def test_nil_reads_as_the_csv_writes_it():
    rows = xbrl_rows("S100YRDM", "ixbrl")
    nils = [r for r in rows if r["nil"]]
    assert nils and all(r["値"] == "－" for r in nils)


def test_a_fact_without_a_unit_reads_as_the_csv_writes_it():
    rows = xbrl_rows("S100YRDM", "ixbrl")
    r = [r for r in rows if r["要素ID"] == "jplvh_cor:NameCoverPage"][0]
    assert (r["ユニットID"], r["単位"]) == ("－", "－")


def test_text_sections_keep_html():
    rows = xbrl_rows("S100Y4NW", "ixbrl")
    r = [r for r in rows if r["要素ID"] == "jptoo-ton_cor:PurposesOfPurchaseEtcTextBlock"][0]
    assert r["html"].lstrip().startswith("<h3>") and "売買する可能性" in r["値"]
    assert len(r["値"]) > CSV_LIMIT


def test_plain_strings_follow_the_csvs_rule_for_no_break_spaces_and_line_breaks():
    """EDINET's CSV writes a no-break space as a space and drops line breaks in a plain string
    (all 41 such differences on the fixtures); the rows do the same, so names compare equal.
    The reader's fact keeps the value as filed."""
    rows = xbrl_rows("S100YRDM", "ixbrl")
    r = [r for r in rows if r["要素ID"] == "jplvh_cor:NameCoverPage"][0]
    assert r["値"] == (
        "ニッポン・アクティブ・バリュー・ファンド（NIPPON ACTIVE VALUE FUND PLC）"
        "取締役会会長\u3000ローズマリー・モーガン（Rosemary Morgan）"
    )
    rows = xbrl_rows("S100Y8GB", "ixbrl")
    r = [r for r in rows if r["要素ID"] == "jpdei_cor:FilerNameInJapaneseDEI"][0]
    assert r["値"] == "株式会社シティインデックスファースト代表取締役\u3000福島啓修"


def key(r):
    return (r["要素ID"], r["コンテキストID"], r["ユニットID"])


@pytest.mark.parametrize("doc", DOCS)
@pytest.mark.parametrize("source", ["ixbrl", "instance"])
def test_every_fixture_has_the_csvs_element_context_and_unit_ids(doc, source):
    assert collections.Counter(map(key, xbrl_rows(doc, source))) == collections.Counter(
        map(key, csv_rows(doc))
    )


@pytest.mark.parametrize("doc", DOCS)
@pytest.mark.parametrize("source", ["ixbrl", "instance"])
def test_every_fixture_value_equals_the_csvs(doc, source):
    """Exact for every value but text sections; text sections equal after whitespace is
    removed, and where the CSV cut the text at 30,000 characters the CSV's is a prefix."""
    csv_by_key = collections.defaultdict(list)
    for r in csv_rows(doc):
        csv_by_key[key(r)].append(r["値"])
    for r in xbrl_rows(doc, source):
        expected = csv_by_key[key(r)].pop(0)
        if r["html"] is None:
            assert r["値"] == expected, key(r)
            continue
        mine, theirs = normalize_space(r["値"]), normalize_space(expected)
        if len(expected) >= CSV_LIMIT:
            assert len(mine) > len(theirs) and mine.startswith(theirs), key(r)
        else:
            assert mine == theirs, key(r)


def test_unknown_source_is_refused():
    with pytest.raises(ValueError, match="source"):
        extract_rows_from_package(package("S100YRDM", 1), source="pdf")
