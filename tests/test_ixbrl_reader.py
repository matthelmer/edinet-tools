"""The inline XBRL reader (edinet_tools.parsers.ixbrl).

Synthetic documents exercise every rule the reader implements (continuation,
exclude, nil, sign, scale, the three date/number transforms, escaped text
sections, hidden facts, footnotes) and every rule it refuses (an ix element
or transform format it does not implement fails loudly, naming it). The real
fixtures under tests/fixtures/xbrl prove it on filed packages.
"""

import io
import zipfile
from pathlib import Path

import pytest

from edinet_tools.parsers.ixbrl import (
    UnsupportedInlineXBRL,
    read_inline_xbrl,
    read_inline_xbrl_package,
)

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"

IX10 = "http://www.xbrl.org/2008/inlineXBRL"
IX11 = "http://www.xbrl.org/2013/inlineXBRL"

ENTITY = (
    "<xbrli:entity>"
    '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E99999-000</xbrli:identifier>'
    "</xbrli:entity>"
)

RESOURCES = f"""
<ix:header>
<ix:hidden>
<ix:nonNumeric contextRef="FilingDateInstant" name="jpdei_cor:EDINETCodeDEI">E99999</ix:nonNumeric>
</ix:hidden>
<ix:references><link:schemaRef xlink:type="simple" xlink:href="x.xsd"/></ix:references>
<ix:resources>
<xbrli:context id="FilingDateInstant">
{ENTITY}
<xbrli:period><xbrli:instant>2026-07-24</xbrli:instant></xbrli:period>
</xbrli:context>
<xbrli:context id="CurrentYearDuration">
{ENTITY}
<xbrli:period>
<xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate>
</xbrli:period>
</xbrli:context>
<xbrli:context id="FilingDateInstant_Holder2Member">
{ENTITY}
<xbrli:period><xbrli:instant>2026-07-24</xbrli:instant></xbrli:period>
<xbrli:scenario>
<xbrldi:explicitMember dimension="jplvh_cor:FilersLargeVolumeHoldersAxis">
x:Holder2Member</xbrldi:explicitMember>
</xbrli:scenario>
</xbrli:context>
<xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
<xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
<xbrli:unit id="JPYPerShares"><xbrli:divide>
<xbrli:unitNumerator><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unitNumerator>
<xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>
</xbrli:divide></xbrli:unit>
</ix:resources>
</ix:header>
"""


def ixdoc(body: str, header: str = RESOURCES, ix: str = IX10) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="{ix}"
 xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2011-07-31"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:jpdei_cor="http://example.com/jpdei" xmlns:jplvh_cor="http://example.com/jplvh"
 xmlns:x="http://example.com/x">
<head><title>t</title></head>
<body><div style="display:none">{header}</div>{body}</body></html>""".encode("utf-8")


def facts_of(body: str, **kw):
    return read_inline_xbrl({"0101010_honbun_x_ixbrl.htm": ixdoc(body, **kw)}).facts


def one(facts, element_id):
    found = [f for f in facts if f.element_id == element_id]
    assert len(found) == 1, found
    return found[0]


# --- contexts, units, hidden facts ---------------------------------------------------------


def test_contexts_carry_their_real_dates_and_dimensions():
    r = read_inline_xbrl({"a_ixbrl.htm": ixdoc("")})
    fdi = r.contexts["FilingDateInstant"]
    assert fdi.instant == "2026-07-24" and fdi.period_start is None
    cyd = r.contexts["CurrentYearDuration"]
    assert (cyd.period_start, cyd.period_end, cyd.instant) == ("2025-04-01", "2026-03-31", None)
    h2 = r.contexts["FilingDateInstant_Holder2Member"]
    assert h2.dimensions == {"jplvh_cor:FilersLargeVolumeHoldersAxis": "x:Holder2Member"}


def test_units_are_read_including_a_divide():
    r = read_inline_xbrl({"a_ixbrl.htm": ixdoc("")})
    assert r.units["JPY"] == "iso4217:JPY"
    assert r.units["JPYPerShares"] == "iso4217:JPY/xbrli:shares"


def test_hidden_facts_are_facts():
    f = one(facts_of(""), "jpdei_cor:EDINETCodeDEI")
    assert (f.context_id, f.value, f.nil) == ("FilingDateInstant", "E99999", False)


# --- ix:nonFraction ------------------------------------------------------------------------


def test_nonfraction_numdotdecimal_scale_and_decimals():
    f = one(
        facts_of(
            '<ix:nonFraction name="x:NetSales" contextRef="CurrentYearDuration" unitRef="JPY"'
            ' decimals="-3" scale="3" format="ixt:numdotdecimal">1,675,916</ix:nonFraction>'
        ),
        "x:NetSales",
    )
    assert f.value == "1675916000"
    assert (f.unit_id, f.decimals, f.scale, f.sign) == ("JPY", "-3", "3", None)


def test_nonfraction_sign_minus_negates():
    f = one(
        facts_of(
            '<ix:nonFraction name="x:Loss" contextRef="CurrentYearDuration" unitRef="JPY"'
            ' decimals="-3" scale="3" sign="-" format="ixt:numdotdecimal">130</ix:nonFraction>'
        ),
        "x:Loss",
    )
    assert f.value == "-130000" and f.sign == "-"


def test_nonfraction_negative_scale_ratio():
    f = one(
        facts_of(
            '<ix:nonFraction name="x:Ratio" contextRef="FilingDateInstant" unitRef="shares"'
            ' decimals="4" scale="-2" format="ixt:numdotdecimal">10.57</ix:nonFraction>'
        ),
        "x:Ratio",
    )
    assert f.value == "0.1057"


def test_nonfraction_without_format_is_a_plain_decimal():
    f = one(
        facts_of(
            '<ix:nonFraction name="x:N" contextRef="FilingDateInstant" unitRef="shares"'
            ' decimals="0">6190300</ix:nonFraction>'
        ),
        "x:N",
    )
    assert f.value == "6190300" and f.scale is None


def test_nonfraction_nil():
    f = one(
        facts_of(
            '<ix:nonFraction name="x:N" contextRef="FilingDateInstant" unitRef="shares"'
            ' xsi:nil="true" />'
        ),
        "x:N",
    )
    assert f.nil is True and f.value is None and f.unit_id == "shares"


def test_nonfraction_text_that_does_not_fit_its_format_fails_loudly():
    with pytest.raises(UnsupportedInlineXBRL, match="numdotdecimal"):
        facts_of(
            '<ix:nonFraction name="x:N" contextRef="FilingDateInstant" unitRef="shares"'
            ' decimals="0" format="ixt:numdotdecimal">１２３</ix:nonFraction>'
        )


# --- ix:nonNumeric -------------------------------------------------------------------------


def test_nonnumeric_plain_concatenates_text_and_drops_exclude():
    f = one(
        facts_of(
            '<ix:nonNumeric name="x:Name" contextRef="FilingDateInstant">'
            "<div>ファンド（FUND&#160;PLC）</div><ix:exclude><span>1/2</span></ix:exclude>"
            "<div>会長　モーガン</div></ix:nonNumeric>"
        ),
        "x:Name",
    )
    assert f.value == "ファンド（FUND PLC）会長　モーガン"
    assert f.html is None


def test_nonnumeric_nil():
    f = one(
        facts_of('<ix:nonNumeric name="x:T" contextRef="FilingDateInstant" xsi:nil="true" />'),
        "x:T",
    )
    assert f.nil is True and f.value is None


def test_escaped_text_section_keeps_html_and_gives_tabbed_plain_text():
    body = (
        '<ix:nonNumeric name="x:TradesTextBlock" contextRef="FilingDateInstant" escape="true">'
        '<p class="h">（５）【取得又は処分の状況】</p>'
        "<table><tr><td><p>年月日</p></td><td><p>数量</p></td><td><p>割合</p></td></tr>\n"
        "<tr><td><p>令和8年5月19日</p></td><td><p>90,000</p></td><td><p>0.29</p></td></tr>"
        "</table></ix:nonNumeric>"
    )
    f = one(facts_of(body), "x:TradesTextBlock")
    assert (
        f.value == "（５）【取得又は処分の状況】\n年月日\t数量\t割合\n令和8年5月19日\t90,000\t0.29"
    )
    assert f.html.startswith('<p class="h">（５）【取得又は処分の状況】</p><table>')
    assert "<td><p>90,000</p></td>" in f.html
    assert "ix:" not in f.html


def test_escaped_text_section_strips_nested_ix_tags_but_keeps_their_text():
    body = (
        '<ix:nonNumeric name="x:BSTextBlock" contextRef="CurrentYearDuration" escape="true">'
        '<table><tr><td>現金</td><td><ix:nonFraction name="x:Cash" contextRef="CurrentYearDuration"'
        ' unitRef="JPY" decimals="-3" scale="3" format="ixt:numdotdecimal">1,675</ix:nonFraction>'
        "</td></tr></table><ix:exclude><p>除外</p></ix:exclude></ix:nonNumeric>"
    )
    facts = facts_of(body)
    tb = one(facts, "x:BSTextBlock")
    assert tb.value == "現金\t1,675"
    assert tb.html == "<table><tr><td>現金</td><td>1,675</td></tr></table>"
    assert one(facts, "x:Cash").value == "1675000"


def test_continuation_chain_is_followed_across_documents():
    doc1 = ixdoc(
        '<ix:nonNumeric name="x:PurposeTextBlock" contextRef="FilingDateInstant" escape="true"'
        ' continuedAt="c1"><p>第一段</p></ix:nonNumeric>'
        '<ix:continuation id="c1" continuedAt="c2"><p>第二段</p></ix:continuation>',
        ix=IX11,
    )
    doc2 = ixdoc(
        '<ix:continuation id="c2"><p>売買する可能性</p></ix:continuation>',
        header="",
        ix=IX11,
    )
    r = read_inline_xbrl({"0101010_a_ixbrl.htm": doc1, "0102010_b_ixbrl.htm": doc2})
    f = one(r.facts, "x:PurposeTextBlock")
    assert f.value == "第一段\n第二段\n売買する可能性"
    assert f.html == "<p>第一段</p><p>第二段</p><p>売買する可能性</p>"


def test_a_broken_continuation_chain_fails_loudly():
    doc = ixdoc(
        '<ix:nonNumeric name="x:P" contextRef="FilingDateInstant" continuedAt="nope">a'
        "</ix:nonNumeric>",
        ix=IX11,
    )
    with pytest.raises(UnsupportedInlineXBRL, match="nope"):
        read_inline_xbrl({"a_ixbrl.htm": doc})


def test_date_transform_cjk_accepts_full_width_digits():
    f = one(
        facts_of(
            '<ix:nonNumeric name="x:FilingDate" contextRef="FilingDateInstant"'
            ' format="ixt:dateyearmonthdaycjk">2026年５月18日</ix:nonNumeric>'
        ),
        "x:FilingDate",
    )
    assert f.value == "2026-05-18"


@pytest.mark.parametrize(
    "shown,iso",
    [
        ("令和8年5月27日", "2026-05-27"),
        ("平成21年2月16日", "2009-02-16"),
        ("令和元年5月1日", "2019-05-01"),
    ],
)
def test_date_transform_japanese_era(shown, iso):
    f = one(
        facts_of(
            '<ix:nonNumeric name="x:D" contextRef="FilingDateInstant"'
            f' format="ixt:dateerayearmonthdayjp">{shown}</ix:nonNumeric>'
        ),
        "x:D",
    )
    assert f.value == iso


def test_date_that_does_not_fit_its_format_fails_loudly():
    with pytest.raises(UnsupportedInlineXBRL, match="dateyearmonthdaycjk"):
        facts_of(
            '<ix:nonNumeric name="x:D" contextRef="FilingDateInstant"'
            ' format="ixt:dateyearmonthdaycjk">2026/05/18</ix:nonNumeric>'
        )


# --- footnotes -----------------------------------------------------------------------------


def test_footnotes_are_kept_beside_the_facts_that_cite_them():
    body = (
        '<ix:nonFraction name="x:Cash" contextRef="CurrentYearDuration" unitRef="JPY" decimals="0"'
        ' footnoteRefs="fn1" id="fact1">5</ix:nonFraction>'
        '<ix:footnote footnoteID="fn1" arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"'
        ' footnoteLinkRole="r" footnoteRole="http://www.xbrl.org/2003/role/footnote"'
        ' xml:lang="ja">※1 注記</ix:footnote>'
    )
    r = read_inline_xbrl({"a_ixbrl.htm": ixdoc(body)})
    assert one(r.facts, "x:Cash").footnote_refs == ("fn1",)
    assert r.footnotes == {"fn1": "※1 注記"}
    assert [f.element_id for f in r.facts].count("x:Cash") == 1


# --- refusals ------------------------------------------------------------------------------


@pytest.mark.parametrize("tag", ["tuple", "fraction", "relationship"])
def test_an_ix_element_it_does_not_implement_fails_loudly(tag):
    with pytest.raises(UnsupportedInlineXBRL, match=f"ix:{tag}"):
        facts_of(f'<ix:{tag} name="x:T" contextRef="FilingDateInstant">1</ix:{tag}>')


def test_a_transform_format_it_does_not_implement_fails_loudly():
    with pytest.raises(UnsupportedInlineXBRL, match="numcommadecimal"):
        facts_of(
            '<ix:nonFraction name="x:N" contextRef="FilingDateInstant" unitRef="JPY"'
            ' decimals="0" format="ixt:numcommadecimal">1.000</ix:nonFraction>'
        )


def test_an_attribute_it_does_not_implement_fails_loudly():
    with pytest.raises(UnsupportedInlineXBRL, match="target"):
        facts_of(
            '<ix:nonNumeric name="x:T" contextRef="FilingDateInstant" target="other">a'
            "</ix:nonNumeric>"
        )


def test_a_fact_whose_context_is_missing_fails_loudly():
    with pytest.raises(UnsupportedInlineXBRL, match="NoSuchContext"):
        facts_of('<ix:nonNumeric name="x:T" contextRef="NoSuchContext">a</ix:nonNumeric>')


# --- real packages -------------------------------------------------------------------------


def test_real_package_s100yrdm_reads_every_fact():
    r = read_inline_xbrl_package((FIXTURES / "S100YRDM_type1.zip").read_bytes())
    assert len(r.facts) == 369
    held = [
        f.value
        for f in r.facts
        if f.element_id == "jplvh_cor:TotalNumberOfStocksEtcHeld"
        and f.context_id.endswith("FilerLargeVolumeHolder3Member")
    ]
    assert set(held) == {"6190300"}


def test_package_skips_audit_documents_like_the_csv_path():
    r = read_inline_xbrl_package((FIXTURES / "S100YWE2_type1.zip").read_bytes())
    assert len(r.facts) == 365
    assert all("AuditDoc" not in f.source_file for f in r.facts)


def test_package_without_inline_files_fails_loudly():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/x.xbrl", "<x/>")
    with pytest.raises(UnsupportedInlineXBRL, match="no inline XBRL"):
        read_inline_xbrl_package(buf.getvalue())
