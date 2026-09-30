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
}
# Facts per package (PublicDoc), equal to the CSV's row count and the instance's.
FACT_COUNTS = {"S100Y4NW": 121, "S100Y8GB": 275, "S100YRDM": 369, "S100YD3H": 369, "S100YWE2": 365}


def type1(doc):
    return (FIXTURES / f"{doc}_type1.zip").read_bytes()


# --- (a) inline vs instance ------------------------------------------------------------------


def fact_key(f):
    value = normalize_space(f.value) if f.html is not None else f.value
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


def compare(csv_value, xbrl_value, path, diffs):
    """Record every difference as (path, kind); kind 'other' is a parity failure."""
    if is_dataclass(csv_value) and type(csv_value) is type(xbrl_value):
        # walk every field: == would skip fields declared compare=False (JointHolder.text_blocks)
        for f in fields(csv_value):
            compare(
                getattr(csv_value, f.name), getattr(xbrl_value, f.name), f"{path}.{f.name}", diffs
            )
        return
    if isinstance(csv_value, str) and isinstance(xbrl_value, str):
        if csv_value == xbrl_value:
            return
        a, b = normalize_space(csv_value), normalize_space(xbrl_value)
        if a == b:
            diffs.append((path, "whitespace"))
        elif len(csv_value) >= CSV_LIMIT and len(b) > len(a) and b.startswith(a):
            diffs.append((path, "beyond_30000"))
        else:
            diffs.append((path, "other"))
        return
    if isinstance(csv_value, dict) and isinstance(xbrl_value, dict):
        if set(csv_value) != set(xbrl_value):
            diffs.append((path + ".keys", "other"))
        for k in set(csv_value) & set(xbrl_value):
            compare(csv_value[k], xbrl_value[k], f"{path}[{k}]", diffs)
        return
    if isinstance(csv_value, list) and isinstance(xbrl_value, list):
        if len(csv_value) != len(xbrl_value):
            diffs.append((path + ".len", "other"))
            return
        for i, (a, b) in enumerate(zip(csv_value, xbrl_value)):
            compare(a, b, f"{path}[{i}]", diffs)
        return
    # containers are walked above (== on a list of dataclasses would skip compare=False fields)
    if csv_value == xbrl_value and type(csv_value) is type(xbrl_value):
        return
    diffs.append((path, "other"))


def report_diffs(doc, source="ixbrl"):
    csv_files = extract_csv_from_zip((FIXTURES / f"{doc}_type5.zip").read_bytes())
    csv_report = _parser_for(DOCS[doc])(csv_files=csv_files, doc_id=doc, doc_type_code=DOCS[doc])
    xbrl_report = parse_xbrl(type1(doc), DOCS[doc], doc_id=doc, source=source)
    diffs = []
    for f in fields(csv_report):
        a, b = getattr(csv_report, f.name), getattr(xbrl_report, f.name)
        if f.name == "source_files":
            a = [n[: -len(".csv")] + ".xbrl" for n in a]
        if f.name == "raw_facts":
            # facts compared as a multiset: document order may differ between sources
            def by_key(facts):
                return sorted(facts, key=lambda x: (x.element_id, x.context_id, str(x.unit_id)))

            a, b = by_key(a), by_key(b)
        compare(a, b, f.name, diffs)
    return csv_report, xbrl_report, diffs


@pytest.mark.parametrize("doc", DOCS)
@pytest.mark.parametrize("source", ["ixbrl", "instance"])
def test_csv_and_xbrl_reports_differ_only_by_the_documented_improvements(doc, source):
    _csv, _xbrl, diffs = report_diffs(doc, source)
    kinds = collections.Counter(kind for _path, kind in diffs)
    others = [path for path, kind in diffs if kind == "other"]
    assert not others, others
    assert set(kinds) <= {"whitespace", "beyond_30000"}


def test_the_comparison_catches_a_real_difference():
    """Guard against a comparison that passes everything."""
    from dataclasses import replace

    csv_report, xbrl_report, _diffs = report_diffs("S100YRDM")
    assert len(fields(csv_report)) > 30
    altered = replace(xbrl_report, ownership_pct=Decimal("0.5"))
    diffs = []
    compare(csv_report.ownership_pct, altered.ownership_pct, "ownership_pct", diffs)
    assert diffs == [("ownership_pct", "other")]
    diffs = []
    compare("90,0000.29", "90,000\t0.29x", "t", diffs)
    assert diffs == [("t", "other")]


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
