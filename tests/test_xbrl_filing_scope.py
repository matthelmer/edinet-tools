"""Definitions are scoped per filing: a package can hold several filings (an investment trust's
fund and each series, S100YO5B), each an inline set plus an instance of its own, that define the
same context IDs differently (entity G14704-000 / -001 / -002). A fact resolves against its own
filing's definitions; a conflict inside one filing is still refused. EDINET's CSV gives one file
per filing, and so do the rows."""

import collections
from pathlib import Path

import pytest

from edinet_tools.parsers._xbrl_model import normalize_space
from edinet_tools.parsers.extraction import extract_csv_from_zip, extract_rows_from_package
from edinet_tools.parsers.ixbrl import read_inline_xbrl_package
from edinet_tools.parsers.xbrl_instance import read_instance_package

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"
CSV_LIMIT = 30000
FILINGS = [
    f"jpsps040000-srs-001_G14704-{n}_2026-05-15_02_2026-08-14.xbrl" for n in ("000", "001", "002")
]


def pkg(kind):
    return (FIXTURES / f"S100YO5B_type{kind}.zip").read_bytes()


def conflicting_ids(facts):
    seen = collections.defaultdict(list)
    for contexts in facts.contexts_by_filing.values():
        for cid, ctx in contexts.items():
            if ctx not in seen[cid]:
                seen[cid].append(ctx)
    return {cid for cid, defs in seen.items() if len(defs) > 1}


@pytest.mark.parametrize("reader", [read_inline_xbrl_package, read_instance_package])
def test_each_filing_keeps_its_own_definitions(reader):
    r = reader(pkg(1))
    assert sorted(r.contexts_by_filing) == FILINGS
    clash = conflicting_ids(r)
    assert clash, "the fixture defines the same context id differently per filing"
    cid = sorted(clash)[0]
    entities = {f: r.contexts_by_filing[f][cid].entity for f in FILINGS[1:]}
    assert entities == {FILINGS[1]: "G14704-001", FILINGS[2]: "G14704-002"}
    # the package-wide view holds only ids every filing defines the same way
    assert not clash & set(r.contexts)
    # every fact resolves in its own filing
    for f in r.facts:
        assert f.context_id in r.contexts_by_filing[f.filing]


def test_inline_and_instance_agree_filing_by_filing():
    a, b = read_inline_xbrl_package(pkg(1)), read_instance_package(pkg(1))

    def key(f):
        text = f.html is not None or "TextBlock" in f.element_id
        v = normalize_space(f.value) if text else f.value
        return (f.filing, f.element_id, f.context_id, f.unit_id, f.decimals, f.nil, v)

    assert collections.Counter(map(key, a.facts)) == collections.Counter(map(key, b.facts))
    assert a.contexts_by_filing == b.contexts_by_filing
    assert a.units_by_filing == b.units_by_filing


@pytest.mark.parametrize("source", ["xbrl", "instance"])
def test_rows_are_one_file_per_filing_and_match_the_csv(source):
    csv = {
        f["filename"][: -len(".csv")] + ".xbrl": [r for r in f["data"] if r["要素ID"] != "要素ID"]
        for f in extract_csv_from_zip(pkg(5))
    }
    rows = {f["filename"]: f["data"] for f in extract_rows_from_package(pkg(1), source=source)}
    assert sorted(rows) == sorted(csv) == FILINGS

    def ids(r):
        return (r["要素ID"], r["コンテキストID"], r["ユニットID"])

    for filing in FILINGS:
        assert collections.Counter(map(ids, rows[filing])) == collections.Counter(
            map(ids, csv[filing])
        )
        expected = collections.defaultdict(list)
        for r in csv[filing]:
            expected[ids(r)].append(r["値"])
        for r in rows[filing]:
            theirs = expected[ids(r)].pop(0)
            if r["html"] is None and "TextBlock" not in r["要素ID"]:
                assert r["値"] == theirs, ids(r)
            else:
                mine, csv_text = normalize_space(r["値"]), normalize_space(theirs)
                if len(theirs) >= CSV_LIMIT:
                    assert mine.startswith(csv_text), ids(r)
                else:
                    assert mine == csv_text, ids(r)
    # the rows carry the right entity's dates for a clashing id: resolved per filing
    by_filing = read_inline_xbrl_package(pkg(1)).contexts_by_filing
    for filing in FILINGS:
        for r in rows[filing]:
            ctx = by_filing[filing][r["コンテキストID"]]
            assert (r["instant"], r["period_start"]) == (ctx.instant, ctx.period_start)
