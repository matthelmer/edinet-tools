"""The XBRL instance reader (edinet_tools.parsers.xbrl_instance): the `.xbrl` EDINET generates
beside the inline documents. Used as the inline reader's cross-check and as source='instance'."""

from pathlib import Path

import pytest

from edinet_tools.parsers.xbrl_instance import (
    UnsupportedInlineXBRL,
    read_instance,
    read_instance_package,
)

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"

INSTANCE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:jpcrp_cor="http://example.com/jpcrp" xmlns:x="http://example.com/x">
<link:schemaRef xlink:type="simple" xlink:href="x.xsd"/>
<xbrli:context id="CurrentYearDuration">
<xbrli:entity><xbrli:identifier scheme="s">E1-000</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate>
<xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period>
</xbrli:context>
<xbrli:context id="FilingDateInstant_H2">
<xbrli:entity><xbrli:identifier scheme="s">E1-000</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:instant>2026-07-24</xbrli:instant></xbrli:period>
<xbrli:scenario><xbrldi:explicitMember dimension="x:Axis">x:H2</xbrldi:explicitMember>
</xbrli:scenario>
</xbrli:context>
<xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
<jpcrp_cor:NetSales contextRef="CurrentYearDuration" unitRef="JPY" decimals="-3">580567000</jpcrp_cor:NetSales>
<jpcrp_cor:Loss contextRef="CurrentYearDuration" unitRef="JPY" decimals="-3">-130000</jpcrp_cor:Loss>
<x:Name contextRef="FilingDateInstant_H2">ファンド &amp; Co</x:Name>
<x:Empty contextRef="FilingDateInstant_H2" xsi:nil="true"/>
<x:TradesTextBlock contextRef="FilingDateInstant_H2">&lt;p&gt;見出し&lt;/p&gt;&lt;table&gt;&lt;tr&gt;&lt;td&gt;90,000&lt;/td&gt;&lt;td&gt;0.29&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</x:TradesTextBlock>
<link:footnoteLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link"/>
</xbrli:xbrl>
""".encode("utf-8")


def one(facts, element_id):
    found = [f for f in facts if f.element_id == element_id]
    assert len(found) == 1, found
    return found[0]


def test_numeric_facts_keep_unit_decimals_and_sign():
    r = read_instance(INSTANCE)
    f = one(r.facts, "jpcrp_cor:NetSales")
    assert (f.context_id, f.unit_id, f.decimals, f.value) == (
        "CurrentYearDuration",
        "JPY",
        "-3",
        "580567000",
    )
    assert one(r.facts, "jpcrp_cor:Loss").value == "-130000"


def test_contexts_and_units():
    r = read_instance(INSTANCE)
    assert r.contexts["CurrentYearDuration"].period_start == "2025-04-01"
    assert r.contexts["FilingDateInstant_H2"].dimensions == {"x:Axis": "x:H2"}
    assert r.units == {"JPY": "iso4217:JPY"}


def test_strings_are_unescaped_and_nil_is_none():
    r = read_instance(INSTANCE)
    assert one(r.facts, "x:Name").value == "ファンド & Co"
    e = one(r.facts, "x:Empty")
    assert e.nil is True and e.value is None


def test_text_blocks_keep_html_and_give_tabbed_text():
    f = one(read_instance(INSTANCE).facts, "x:TradesTextBlock")
    assert f.html == "<p>見出し</p><table><tr><td>90,000</td><td>0.29</td></tr></table>"
    assert f.value == "見出し\n90,000\t0.29"


def test_a_tuple_fails_loudly():
    bad = INSTANCE.replace(
        b"<link:footnoteLink",
        b'<x:Tuple><x:Inner contextRef="CurrentYearDuration">a</x:Inner></x:Tuple><link:footnoteLink',
    )
    with pytest.raises(UnsupportedInlineXBRL, match="x:Tuple"):
        read_instance(bad)


def test_a_fact_whose_context_is_missing_fails_loudly():
    bad = INSTANCE.replace(b'x:Name contextRef="FilingDateInstant_H2"', b'x:Name contextRef="Nope"')
    with pytest.raises(UnsupportedInlineXBRL, match="Nope"):
        read_instance(bad)


def test_real_package_s100yrdm():
    r = read_instance_package((FIXTURES / "S100YRDM_type1.zip").read_bytes())
    assert len(r.facts) == 369
    held = {
        f.value
        for f in r.facts
        if f.element_id == "jplvh_cor:TotalNumberOfStocksEtcHeld"
        and f.context_id.endswith("FilerLargeVolumeHolder3Member")
    }
    assert held == {"6190300"}


def test_real_package_skips_the_audit_instance():
    r = read_instance_package((FIXTURES / "S100YWE2_type1.zip").read_bytes())
    assert len(r.facts) == 365
