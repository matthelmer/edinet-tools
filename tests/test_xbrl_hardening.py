"""Review fixes on the XBRL readers: strict dates, zero with sign, one text rule for unescaped
text blocks, conflicting ids, DTD/entity refusal, zip size caps, one source vocabulary."""

import io
import zipfile
from pathlib import Path

import pytest

from edinet_tools.parsers import _xbrl_model, parse_xbrl
from edinet_tools.parsers.extraction import extract_rows_from_package
from edinet_tools.parsers.ixbrl import (
    UnsupportedInlineXBRL,
    read_inline_xbrl,
    read_inline_xbrl_package,
)
from edinet_tools.parsers.xbrl_instance import read_instance, read_instance_package
from tests.test_ixbrl_reader import RESOURCES, ixdoc, one
from tests.test_xbrl_instance_reader import INSTANCE

FIXTURES = Path(__file__).parent / "fixtures" / "xbrl"


def facts_of(body, **kw):
    return read_inline_xbrl({"a_ixbrl.htm": ixdoc(body, **kw)}).facts


# 1. dateyearmonthdaycjk requires a four-digit year


def test_cjk_date_with_a_two_digit_year_is_refused():
    with pytest.raises(UnsupportedInlineXBRL, match="dateyearmonthdaycjk"):
        facts_of(
            '<ix:nonNumeric name="x:D" contextRef="FilingDateInstant"'
            ' format="ixt:dateyearmonthdaycjk">26年5月18日</ix:nonNumeric>'
        )


# 5. sign="-" on zero


def test_negative_sign_on_zero_reads_zero():
    f = one(
        facts_of(
            '<ix:nonFraction name="x:N" contextRef="CurrentYearDuration" unitRef="JPY"'
            ' decimals="-3" scale="3" sign="-" format="ixt:numdotdecimal">0</ix:nonFraction>'
        ),
        "x:N",
    )
    assert f.value == "0"


# 3. an unescaped multi-line text block reads the same from both readers

PLAIN_BLOCK = "第一行\n      第二行 続き &amp; 末尾\n"


def test_unescaped_text_block_has_one_plain_text_rule():
    inline = one(
        facts_of(
            '<ix:nonNumeric name="x:NotesTextBlock" contextRef="FilingDateInstant">'
            f"{PLAIN_BLOCK}</ix:nonNumeric>"
        ),
        "x:NotesTextBlock",
    )
    instance_doc = INSTANCE.replace(
        b"<link:footnoteLink",
        f'<x:NotesTextBlock contextRef="CurrentYearDuration">{PLAIN_BLOCK}</x:NotesTextBlock>'
        "<link:footnoteLink".encode("utf-8"),
    )
    instance = one(read_instance(instance_doc).facts, "x:NotesTextBlock")
    assert inline.value == instance.value == "第一行 第二行 続き & 末尾"


# 4. duplicate ids with differing definitions


def _context(cid, instant):
    return (
        f'<xbrli:context id="{cid}"><xbrli:entity>'
        '<xbrli:identifier scheme="s">E1-000</xbrli:identifier></xbrli:entity>'
        f"<xbrli:period><xbrli:instant>{instant}</xbrli:instant></xbrli:period></xbrli:context>"
    )


def _header(extra):
    return RESOURCES.replace("</ix:resources>", extra + "</ix:resources>")


def test_same_context_defined_twice_identically_is_fine():
    doc2 = ixdoc("", header=_header(""))
    r = read_inline_xbrl({"0101_a_ixbrl.htm": ixdoc(""), "0102_b_ixbrl.htm": doc2})
    assert r.contexts["FilingDateInstant"].instant == "2026-07-24"


def test_same_context_id_with_a_different_definition_fails_loudly():
    other = ixdoc(
        "",
        header="<ix:header><ix:resources>"
        + _context("FilingDateInstant", "2020-01-01")
        + "</ix:resources></ix:header>",
    )
    with pytest.raises(UnsupportedInlineXBRL, match="FilingDateInstant"):
        read_inline_xbrl({"0101_a_ixbrl.htm": ixdoc(""), "0102_b_ixbrl.htm": other})


def test_same_unit_id_with_a_different_definition_fails_loudly():
    other = ixdoc(
        "",
        header='<ix:header><ix:resources><xbrli:unit id="JPY"><xbrli:measure>iso4217:USD'
        "</xbrli:measure></xbrli:unit></ix:resources></ix:header>",
    )
    with pytest.raises(UnsupportedInlineXBRL, match="JPY"):
        read_inline_xbrl({"0101_a_ixbrl.htm": ixdoc(""), "0102_b_ixbrl.htm": other})


def test_same_footnote_id_with_different_text_fails_loudly():
    fn = '<ix:footnote footnoteID="fn1">{}</ix:footnote>'
    with pytest.raises(UnsupportedInlineXBRL, match="fn1"):
        read_inline_xbrl(
            {
                "0101_a_ixbrl.htm": ixdoc(fn.format("一")),
                "0102_b_ixbrl.htm": ixdoc(fn.format("二")),
            }
        )


def _package(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_audit_documents_that_redefine_a_context_fail_when_included():
    audit = ixdoc(
        "",
        header="<ix:header><ix:resources>"
        + _context("FilingDateInstant", "2020-01-01")
        + "</ix:resources></ix:header>",
    )
    pkg = _package(
        {
            "XBRL/PublicDoc/0101010_honbun_x_ixbrl.htm": ixdoc(""),
            "XBRL/AuditDoc/jpaud-x_ixbrl.htm": audit,
        }
    )
    assert read_inline_xbrl_package(pkg).contexts["FilingDateInstant"].instant == "2026-07-24"
    with pytest.raises(UnsupportedInlineXBRL, match="FilingDateInstant"):
        read_inline_xbrl_package(pkg, include_audit=True)


def test_real_package_with_audit_included_still_reads():
    r = read_inline_xbrl_package((FIXTURES / "S100YWE2_type1.zip").read_bytes(), include_audit=True)
    assert len(r.facts) == 369


# 7. DTD / entity declarations and zip size caps

DTD = b'<?xml version="1.0"?>\n<!DOCTYPE html [<!ENTITY x "boom">]>\n<html/>'


def test_inline_document_with_a_doctype_is_refused():
    with pytest.raises(UnsupportedInlineXBRL, match="DOCTYPE"):
        read_inline_xbrl({"a_ixbrl.htm": DTD})


def test_instance_with_an_entity_declaration_is_refused():
    bad = INSTANCE.replace(b"<xbrli:xbrl", b'<!ENTITY x "y">\n<xbrli:xbrl', 1)
    with pytest.raises(UnsupportedInlineXBRL, match="ENTITY"):
        read_instance(bad)


def test_utf16_doctype_is_refused_too():
    with pytest.raises(UnsupportedInlineXBRL, match="DOCTYPE"):
        read_inline_xbrl({"a_ixbrl.htm": DTD.decode().encode("utf-16")})


def test_member_over_the_size_cap_is_refused(monkeypatch):
    monkeypatch.setattr(_xbrl_model, "MAX_MEMBER_BYTES", 1000)
    pkg = (FIXTURES / "S100YRDM_type1.zip").read_bytes()
    with pytest.raises(UnsupportedInlineXBRL, match="too large"):
        read_inline_xbrl_package(pkg)
    with pytest.raises(UnsupportedInlineXBRL, match="too large"):
        read_instance_package(pkg)


def test_package_over_the_total_cap_is_refused(monkeypatch):
    monkeypatch.setattr(_xbrl_model, "MAX_TOTAL_BYTES", 50_000)
    pkg = (FIXTURES / "S100YRDM_type1.zip").read_bytes()
    with pytest.raises(UnsupportedInlineXBRL, match="too large"):
        extract_rows_from_package(pkg)


# 9. one source vocabulary: 'xbrl' (inline) and 'instance'; 'ixbrl' an alias of 'xbrl'


def test_source_vocabulary():
    pkg = (FIXTURES / "S100YRDM_type1.zip").read_bytes()
    a = extract_rows_from_package(pkg, source="xbrl")
    b = extract_rows_from_package(pkg, source="ixbrl")
    assert a == b and a[0]["data"][0]["source"] == "xbrl"
    assert extract_rows_from_package(pkg)[0]["data"][0]["source"] == "xbrl"
    assert parse_xbrl(pkg, "350", source="xbrl").shares_held == 10709600
    assert parse_xbrl(pkg, "350", source="ixbrl").shares_held == 10709600
    with pytest.raises(ValueError, match="source"):
        parse_xbrl(pkg, "350", source="csv")
