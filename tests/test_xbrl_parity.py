"""Parity on every fixture package, the proof the XBRL sources can replace the CSV.

(a) inline vs instance: every fact equal: element, context, unit, value, decimals, nil (a text
    section's value compared after whitespace is removed; its plain text comes from differently
    serialized HTML).
(b) CSV vs inline: every field of the parsed report equal, except the documented improvements:
    - 'whitespace': equal once whitespace is removed (a text section's cell tabs and line
      breaks, where the CSV runs cells together);
    - 'beyond_30000': the CSV value was cut at 30,000 characters and, whitespace removed, is a
      strict prefix of the inline value.
    Per-holder sections and holder share counts are the same on both sources since the holder
    parser reads by element ID, so they show no difference here.
"""

import collections
import sys
from dataclasses import fields, is_dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers._xbrl_model import normalize_space
from edinet_tools.parsers.extraction import extract_csv_from_zip
from edinet_tools.parsers.ixbrl import read_inline_xbrl_package
from edinet_tools.parsers.xbrl_instance import read_instance_package
from edinet_tools.parsers import _parser_for

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"
CSV_LIMIT = 30000
DOCS = {
    "S100Y4NW": "240",
    "S100Y8GB": "350",
    "S100YRDM": "350",
    "S100YD3H": "350",
    "S100YWE2": "160",
    # three filings in one package (fund + two series), same context ids defined per filing
    "S100YO5B": "040",
    # a fund's annual report: angle-bracket text the CSV mangles; a CSV cut that reads short
    "S100YOXP": "120",
}
# Facts per package (PublicDoc), equal to the CSV's row count and the instance's.
FACT_COUNTS = {
    "S100Y4NW": 121,
    "S100Y8GB": 275,
    "S100YRDM": 369,
    "S100YD3H": 369,
    "S100YWE2": 365,
    "S100YO5B": 261,
    "S100YOXP": 159,
}


def type1(doc):
    return (FIXTURES / f"{doc}_type1.zip").read_bytes()


# --- (a) inline vs instance ------------------------------------------------------------------


def fact_key(f):
    # a text section compares with whitespace removed; the instance cannot tell an unescaped
    # text block from an escaped one, so a ...TextBlock counts as text on both sides
    text = f.html is not None or "TextBlock" in f.element_id
    value = normalize_space(f.value) if text else f.value
    return (f.element_id, f.context_id, f.unit_id, f.decimals, f.nil, value)


@pytest.mark.parametrize("doc", DOCS)
def test_inline_and_instance_facts_are_equal(doc):
    inline = read_inline_xbrl_package(type1(doc))
    instance = read_instance_package(type1(doc))
    assert len(inline.facts) == len(instance.facts) == FACT_COUNTS[doc]
    assert collections.Counter(map(fact_key, inline.facts)) == collections.Counter(
        map(fact_key, instance.facts)
    )
    # Every escaped (HTML) section inline is a text block in the instance. The instance cannot
    # tell an escaped section from a plain one, so it treats every ...TextBlock as HTML; EDINET
    # files some text blocks unescaped (S100YRDM's InformationAboutJointHoldersTextBlock:
    # "該当事項なし"), and there the plain value is the same on both sides (asserted above).
    inline_html = collections.Counter(
        (f.element_id, f.context_id) for f in inline.facts if f.html is not None
    )
    instance_html = collections.Counter(
        (f.element_id, f.context_id) for f in instance.facts if f.html is not None
    )
    assert not inline_html - instance_html


@pytest.mark.parametrize("doc", DOCS)
def test_inline_and_instance_contexts_are_equal(doc):
    inline = read_inline_xbrl_package(type1(doc))
    instance = read_instance_package(type1(doc))
    assert inline.contexts == instance.contexts
    assert inline.units == instance.units


# --- (b) CSV vs inline -----------------------------------------------------------------------


MAX_ANGLE_DROP = 100


def csv_drops_angle_text(csv_norm: str, xbrl_norm: str) -> bool:
    """EDINET's CSV conversion mangles literal text in angle brackets inside a text section,
    as if it were a tag. Per "<", followed by non-ASCII text, it drops the whole "<...>"
    segment ("<取締役会>", S100Z59P) or only the "<" ("<参考情報：...>", S100YOXP; an unclosed
    "<―――損益", S100YSD1; S100YNQE does both in one section), and the same for a "<" followed
    by a digit or by ">" ("<77>" and the empty legend "<>", S100Z488; "<0565>", S100TD9S). True only when the CSV text is the XBRL
    text with such edits and nothing else changed; a "<" followed by an ASCII letter (a real
    HTML tag) is never excused."""
    if csv_norm == xbrl_norm or "<" not in xbrl_norm:
        return False
    # frontier: {(i in xbrl, j in csv)} states reached; advance through xbrl
    states = {(0, 0)}
    n, m = len(xbrl_norm), len(csv_norm)
    done = False
    seen = set()
    while states:
        nxt = set()
        for i, j in states:
            if (i, j) in seen:
                continue
            seen.add((i, j))
            if i == n:
                done = done or j == m
                continue
            ch = xbrl_norm[i]
            if j < m and csv_norm[j] == ch:
                nxt.add((i + 1, j + 1))
            if ch == "<" and i + 1 < n and (ord(xbrl_norm[i + 1]) > 127 or xbrl_norm[i + 1].isdigit() or xbrl_norm[i + 1] == ">"):
                nxt.add((i + 1, j))  # the "<" alone dropped
                close = xbrl_norm.find(">", i + 1)
                start = i + 1
                # a whole segment is excused only up to 100 characters (corpus maximum: 92)
                if (
                    close != -1
                    and close + 1 - i <= MAX_ANGLE_DROP
                    and "<" not in xbrl_norm[start:close]
                ):
                    nxt.add((close + 1, j))  # the whole segment dropped
        states = nxt
    return done


def csv_was_cut(csv_value: str) -> bool:
    """EDINET cuts a CSV value at 30,000 characters counted BEFORE it decodes entity
    references; the reader decodes them (`&amp;` -> `&`), so a cut value can read shorter
    (S100YOXP: 29,908 characters with 23 ampersands)."""
    return len(csv_value) >= 29000 and len(csv_value) + 4 * csv_value.count("&") >= CSV_LIMIT


def _csv_dash(value):
    return isinstance(value, str) and value.strip() in ("－", "-")


def compare_sections(csv_sections, xbrl_sections, nil, path, diffs):
    """A holder's (or a context's) text sections. A section the CSV shows as 「－」 and the
    XBRL marks xsi:nil is left out of the XBRL sections by design: kind 'nil_section'."""
    for k in set(csv_sections) - set(xbrl_sections):
        kind = "nil_section" if k in nil and _csv_dash(csv_sections[k]) else "other"
        diffs.append((f"{path}[{k}]", kind))
    for k in set(xbrl_sections) - set(csv_sections):
        diffs.append((f"{path}[{k}]", "other"))
    for k in set(csv_sections) & set(xbrl_sections):
        compare(csv_sections[k], xbrl_sections[k], f"{path}[{k}]", diffs, True)


def compare(csv_value, xbrl_value, path, diffs, text=False):
    """Record every difference as (path, kind); kind 'other' is a parity failure.

    `text` marks a text-section path (a TextBlock's value, a text_blocks entry, a typed field
    read from a TextBlock): only there may values differ by whitespace, by the CSV's cut, or by
    literal angle-bracket text the CSV drops.
    Anywhere else (names, codes, dates, numbers) any difference is 'other'."""
    if type(csv_value).__name__ == "JointHolder" and type(csv_value) is type(xbrl_value):
        nil = set(xbrl_value.nil_text_blocks)
        for f in fields(csv_value):
            a, b = getattr(csv_value, f.name), getattr(xbrl_value, f.name)
            if f.name == "text_blocks":
                compare_sections(a, b, nil, f"{path}.text_blocks", diffs)
            elif f.name == "nil_text_blocks":
                # the CSV cannot tell nil from a filed dash, so it names none
                if a:
                    diffs.append((f"{path}.nil_text_blocks", "other"))
                for k in b:
                    if not _csv_dash(csv_value.text_blocks.get(k)):
                        diffs.append((f"{path}.nil_text_blocks[{k}]", "other"))
            else:
                compare(a, b, f"{path}.{f.name}", diffs, text)
        return
    if is_dataclass(csv_value) and type(csv_value) is type(xbrl_value):
        # walk every field: == would skip fields declared compare=False (JointHolder.text_blocks)
        for f in fields(csv_value):
            compare(
                getattr(csv_value, f.name),
                getattr(xbrl_value, f.name),
                f"{path}.{f.name}",
                diffs,
                text or f.name == "text_blocks",
            )
        return
    if isinstance(csv_value, str) and isinstance(xbrl_value, str):
        if csv_value == xbrl_value:
            return
        a, b = normalize_space(csv_value), normalize_space(xbrl_value)
        if text and a == b:
            diffs.append((path, "whitespace"))
        elif text and csv_was_cut(csv_value) and len(b) > len(a) and b.startswith(a):
            diffs.append((path, "beyond_30000"))
        elif text and csv_drops_angle_text(a, b):
            diffs.append((path, "csv_drops_angle_text"))
        else:
            diffs.append((path, "other"))
        return
    if isinstance(csv_value, dict) and isinstance(xbrl_value, dict):
        if set(csv_value) != set(xbrl_value):
            diffs.append((path + ".keys", "other"))
        for k in set(csv_value) & set(xbrl_value):
            compare(csv_value[k], xbrl_value[k], f"{path}[{k}]", diffs, text)
        return
    if isinstance(csv_value, list) and isinstance(xbrl_value, list):
        if len(csv_value) != len(xbrl_value):
            diffs.append((path + ".len", "other"))
            return
        for i, (a, b) in enumerate(zip(csv_value, xbrl_value)):
            compare(a, b, f"{path}[{i}]", diffs, text)
        return
    # containers are walked above (== on a list of dataclasses would skip compare=False fields)
    if csv_value == xbrl_value and type(csv_value) is type(xbrl_value):
        return
    diffs.append((path, "other"))


def text_fields(report) -> set:
    """Typed fields read from a text section: named *_text, or mapped to a *TextBlock element
    in the parser's ELEMENT_MAP."""
    element_map = getattr(sys.modules[type(report).__module__], "ELEMENT_MAP", {})
    return {f.name for f in fields(report) if f.name.endswith("_text")} | {
        k for k, v in element_map.items() if isinstance(v, str) and v.endswith("TextBlock")
    }


def diff_reports(csv_report, xbrl_report, text_elements=frozenset()):
    """Differences between the CSV and XBRL reports. A text section is a ...TextBlock element
    or an element the inline XBRL escapes (text_elements: e.g. an escaped cover-page name
    with a line break, S100YRJE); a typed field is text when it is named as one, or when its
    value is a text section's value (reason_for_filing reads one of two TextBlocks)."""

    def is_text_element(element_id):
        local = element_id.rsplit(":", 1)[-1]
        return (
            "TextBlock" in element_id
            or element_id in text_elements
            or local in {e.rsplit(":", 1)[-1] for e in text_elements}
        )

    diffs = []
    texts = text_fields(csv_report)
    text_values = {
        f.value
        for r in (csv_report, xbrl_report)
        for f in r.raw_facts
        if is_text_element(f.element_id)
    }
    for f in fields(csv_report):
        a, b = getattr(csv_report, f.name), getattr(xbrl_report, f.name)
        if f.name == "source_files":
            a = [n[: -len(".csv")] + ".xbrl" for n in a]
        if f.name == "raw_facts":
            # facts compared as a multiset (document order may differ between sources)
            def by_key(facts):
                return sorted(facts, key=lambda x: (x.element_id, x.context_id, str(x.unit_id)))

            a, b = by_key(a), by_key(b)
            if len(a) != len(b):
                diffs.append(("raw_facts.len", "other"))
                continue
            for x, y in zip(a, b):
                where = f"raw_facts[{x.element_id}@{x.context_id}]"
                compare(x, y, where, diffs, is_text_element(x.element_id))
            continue
        if f.name in ("raw_fields", "unmapped_fields", "text_blocks"):
            if set(a) != set(b):
                diffs.append((f.name + ".keys", "other"))
            for k in set(a) & set(b):
                is_text = f.name == "text_blocks" or is_text_element(k)
                compare(a[k], b[k], f"{f.name}[{k}]", diffs, is_text)
            continue
        if f.name == "text_blocks_by_context":
            nil = {k for h in xbrl_report.joint_holders for k in h.nil_text_blocks}
            for ctx in set(a) | set(b):
                compare_sections(a.get(ctx, {}), b.get(ctx, {}), nil,
                                 f"text_blocks_by_context[{ctx}]", diffs)
            continue
        is_text = (
            f.name in texts
            or f.name == "text_blocks_by_context"
            or (isinstance(a, str) and (a in text_values or b in text_values))
        )
        compare(a, b, f.name, diffs, is_text)
    return diffs


def escaped_elements(zip_bytes) -> frozenset:
    """Elements the inline XBRL files as escaped HTML (text sections by the filer's own mark)."""
    return frozenset(
        f.element_id for f in read_inline_xbrl_package(zip_bytes).facts if f.html is not None
    )


def report_diffs(doc, source="xbrl"):
    csv_files = extract_csv_from_zip((FIXTURES / f"{doc}_type5.zip").read_bytes())
    csv_report = _parser_for(DOCS[doc])(csv_files=csv_files, doc_id=doc, doc_type_code=DOCS[doc])
    xbrl_report = parse_xbrl(type1(doc), DOCS[doc], doc_id=doc, source=source)
    return (
        csv_report,
        xbrl_report,
        diff_reports(csv_report, xbrl_report, escaped_elements(type1(doc))),
    )


# Exact difference counts per fixture (both XBRL sources give the same): a new difference, or
# one that disappears, fails the test instead of hiding among the allowed kinds.
EXPECTED_DIFFS = {
    "S100Y4NW": {"whitespace": 200, "beyond_30000": 4},
    "S100Y8GB": {"whitespace": 27, "nil_section": 12},
    "S100YRDM": {"whitespace": 16, "nil_section": 34},
    "S100YD3H": {"whitespace": 11, "nil_section": 36},
    "S100YWE2": {"whitespace": 94},
    "S100YO5B": {"whitespace": 207, "beyond_30000": 6},
    "S100YOXP": {"whitespace": 144, "csv_drops_angle_text": 3, "beyond_30000": 3},
}


@pytest.mark.parametrize("doc", DOCS)
@pytest.mark.parametrize("source", ["xbrl", "instance"])
def test_csv_and_xbrl_reports_differ_only_by_the_documented_improvements(doc, source):
    _csv, _xbrl, diffs = report_diffs(doc, source)
    others = [path for path, kind in diffs if kind == "other"]
    assert not others, others
    assert dict(collections.Counter(kind for _path, kind in diffs)) == EXPECTED_DIFFS[doc]


def test_the_comparison_catches_a_real_difference():
    """Guard against a comparison that passes everything."""
    from dataclasses import replace

    csv_report, xbrl_report, _diffs = report_diffs("S100YRDM")
    assert len(fields(csv_report)) > 30
    altered = replace(xbrl_report, ownership_pct=Decimal("0.5"))
    assert ("ownership_pct", "other") in diff_reports(csv_report, altered)
    diffs = []
    compare("90,0000.29", "90,000\t0.29x", "t", diffs, text=True)
    assert diffs == [("t", "other")]


def test_a_name_that_loses_its_spaces_is_not_a_whitespace_difference():
    """Whitespace differences are allowed on text sections only: a filer name, a holder name
    or a plain raw field that loses its spaces must fail parity."""
    from dataclasses import replace

    csv_report, xbrl_report, _diffs = report_diffs("S100YRDM")
    squeezed = "".join(csv_report.filer_name.split())
    assert squeezed != csv_report.filer_name
    assert ("filer_name", "other") in diff_reports(
        csv_report, replace(xbrl_report, filer_name=squeezed)
    )
    holders = list(xbrl_report.joint_holders)
    holders[2] = replace(holders[2], name_jp="".join(holders[2].name_jp.split()))
    assert ("joint_holders[2].name_jp", "other") in diff_reports(
        csv_report, replace(xbrl_report, joint_holders=holders)
    )
    raw = dict(xbrl_report.raw_fields)
    raw["jplvh_cor:NameCoverPage"] = "".join(raw["jplvh_cor:NameCoverPage"].split())
    assert ("raw_fields[jplvh_cor:NameCoverPage]", "other") in diff_reports(
        csv_report, replace(xbrl_report, raw_fields=raw)
    )


# --- the stories that found this ---------------------------------------------------------------


def test_s100y4nw_purpose_reads_in_full():
    csv, xbrl, diffs = report_diffs("S100Y4NW")
    assert len(csv.purpose_text) == CSV_LIMIT
    assert "売買する可能性" not in csv.purpose_text
    assert len(xbrl.purpose_text) > CSV_LIMIT and "売買する可能性" in xbrl.purpose_text
    assert ("purpose_text", "beyond_30000") in diffs


def test_s100y8gb_two_trading_tables_one_per_holder():
    _csv, xbrl, _diffs = report_diffs("S100Y8GB")
    tables = [
        v
        for h in xbrl.joint_holders
        for k, v in h.text_blocks.items()
        if k.startswith("DetailsOfAcquisitionsAndDisposals")
    ]
    assert len(tables) == 2 and tables[0] != tables[1]


def test_s100yrdm_three_share_counts():
    _csv, xbrl, _diffs = report_diffs("S100YRDM")
    assert [h.shares_held for h in xbrl.joint_holders] == [3269300, 1250000, 6190300]


def test_csv_drops_angle_text_is_narrow():
    assert csv_drops_angle_text("取締役会は", "<取締役会>取締役会は")
    assert csv_drops_angle_text("取締役会>は", "<取締役会>は")
    # an unclosed "<" before non-ASCII text (S100YSD1's scheme arrows)
    assert csv_drops_angle_text("代金―>―収益", "代金―><―収益")
    # S100YNQE mixes both edits in one section
    assert csv_drops_angle_text("【対象】共通>次の甲1>先", "【対象】<共通>次の<甲1><甲2>先")
    assert not csv_drops_angle_text("【対象】共通>次の甲1>先X", "【対象】<共通>次の<甲1><甲2>先")
    assert not csv_drops_angle_text("取締役会は", "<b>取締役会は")  # an ASCII tag never qualifies
    assert not csv_drops_angle_text("取締役会", "<取締役会>取締役会は")  # more than the brackets
    diffs = []
    compare("取締役会は", "<取締役会>取締役会は", "filer_name", diffs)  # not a text path
    assert diffs == [("filer_name", "other")]


def test_csv_drops_angle_text_that_starts_with_a_digit():
    """A tag never starts with a digit and is never empty: EDINET's CSV still drops "<77>" (a leased area in
    S100Z488's facilities table) and "<0565>" (an area code, S100TD9S's cover page)."""
    assert csv_drops_angle_text("13711542", "137<77>11542")
    assert csv_drops_angle_text("28-2121", "<0565>28-2121")
    assert csv_drops_angle_text("上記中内数は", "上記中<>内数は")  # the empty legend, S100Z488
    assert not csv_drops_angle_text("137", "137<77>11542")  # more than the brackets
    assert not csv_drops_angle_text("取締役会は", "<b>取締役会は")  # an ASCII letter is a tag


def test_angle_drop_is_capped_at_100_characters():
    seg = "<" + "取" * 98 + ">"  # 100 characters
    assert csv_drops_angle_text("前後", "前" + seg + "後")
    long_seg = "<" + "取" * 99 + ">"  # 101 characters
    assert not csv_drops_angle_text("前後", "前" + long_seg + "後")


def test_csv_was_cut_needs_a_long_value():
    assert csv_was_cut("a" * 29908 + "&" * 23)
    assert not csv_was_cut("&" * 6000)  # ampersand-dense but short: not a cut
