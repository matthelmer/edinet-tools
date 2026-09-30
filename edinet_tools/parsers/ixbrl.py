"""Read facts from a filing's inline XBRL (the `*_ixbrl.htm` files of an EDINET type=1 package).

Standard library only (`xml.etree`). Implements the Inline XBRL rules EDINET uses, and refuses
the rest by name:

- `ix:header` / `ix:hidden` / `ix:references` / `ix:resources` (contexts and units; the
  schema reference is not read).
- `ix:nonFraction`: `scale`, `sign="-"`, `decimals`, `xsi:nil`, `format` (see `_FORMATS`).
- `ix:nonNumeric`: plain (the concatenated text) or `escape="true"` (a text section: `html` kept
  as filed, `value` the plain text with cell tabs); nested ix tags contribute their text;
  `ix:exclude` content is removed; `continuedAt` chains through `ix:continuation`, across the
  package's documents. A `...TextBlock` filed unescaped reads by `plain_text_block_value`, the
  rule the instance reader shares.
- `ix:footnote`: kept in `XbrlFacts.footnotes` (id -> text) and on each citing fact's
  `footnote_refs`. Not rows: EDINET's CSV carries no footnotes, and in the instance they sit in
  a footnote link, not among the facts.

Anything else in the ix namespace, a transform format outside `_FORMATS`, an attribute the
reader does not interpret (`target`, `tupleRef`, `order`, `precision`, ...), a context or unit
that is not defined, or displayed text that does not fit its format raises
`UnsupportedInlineXBRL` naming it. Never a silent guess.

EDINET's documents declare Inline XBRL 1.0 (`http://www.xbrl.org/2008/inlineXBRL`) and the
2011-07-31 transformation registry; 1.1 (`.../2013/inlineXBRL`) is read by the same rules.
`ix:continuation` / `continuedAt` are Inline XBRL 1.1 features; under the 1.0 namespace they are
accepted as a lenient extension (no EDINET filing seen uses them).

Safety: a document with a DOCTYPE or ENTITY declaration is refused before parsing, and package
members are size-capped before they are read (`_xbrl_model.read_package_members`). Contexts,
units and footnotes are scoped per filing (see XbrlFacts); defined twice inside one filing's
documents, they must be defined identically.
"""

from __future__ import annotations

import html
import io
import posixpath
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from ._xbrl_model import (
    _VOID_TAGS,
    UnsupportedInlineXBRL,
    XbrlContext,
    XbrlFact,
    XbrlFacts,
    add_filing,
    html_to_text,
    plain_text_block_value,
    put_unique,
    read_package_members,
    refuse_dtd,
)

__all__ = [
    "UnsupportedInlineXBRL",
    "read_inline_xbrl",
    "read_inline_xbrl_package",
    "inline_documents_in_package",
]

IX_NAMESPACES = frozenset(
    {"http://www.xbrl.org/2008/inlineXBRL", "http://www.xbrl.org/2013/inlineXBRL"}
)
IXT_2011 = "http://www.xbrl.org/inlineXBRL/transformation/2011-07-31"
XHTML = "http://www.w3.org/1999/xhtml"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XML_NS = "http://www.w3.org/XML/1998/namespace"

_IX_ELEMENTS = frozenset(
    {"header", "hidden", "references", "resources", "nonNumeric", "nonFraction", "footnote",
     "exclude", "continuation"}
)  # fmt: skip
_COMMON_ATTRS = {"name", "contextRef", "id", "footnoteRefs", "format", f"{{{XSI}}}nil"}
_ALLOWED_ATTRS = {
    "nonFraction": _COMMON_ATTRS | {"unitRef", "decimals", "scale", "sign"},
    "nonNumeric": _COMMON_ATTRS | {"escape", "continuedAt"},
    "continuation": {"id", "continuedAt"},
    "footnote": {"footnoteID", "id", "arcrole", "footnoteLinkRole", "footnoteRole", "title",
                 f"{{{XML_NS}}}lang"},
    "exclude": set(), "header": set(), "hidden": set(), "references": set(), "resources": set(),
}  # fmt: skip

_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
# TR 2011-07-31 numdotdecimal: groups of three separated by comma, space or no-break space,
# optional decimal fraction after a dot.
_NUMDOTDECIMAL_RE = re.compile(r"^[0-9]{1,3}(?:[,  ]?[0-9]{3})*(?:\.[0-9]+)?$")
_PLAIN_DECIMAL_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_DATE_CJK_RE = re.compile(r"^([0-9]{4})\s*年\s*([0-9]{1,2})\s*月\s*([0-9]{1,2})\s*日$")
_DATE_ERA_RE = re.compile(
    r"^(明治|大正|昭和|平成|令和)\s*([0-9]{1,2}|元)\s*年\s*([0-9]{1,2})\s*月\s*([0-9]{1,2})\s*日$"
)
# First Gregorian year of each era (era year 1 = 元年).
_ERAS = {"明治": 1868, "大正": 1912, "昭和": 1926, "平成": 1989, "令和": 2019}


def _local(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        ns, _, local = tag[1:].partition("}")
        return ns, local
    return "", tag


def _iso_date(y: int, m: int, d: int, fmt: str, shown: str) -> str:
    from datetime import date

    try:
        return date(y, m, d).isoformat()
    except ValueError:
        raise UnsupportedInlineXBRL(f"{fmt}: {shown!r} is not a real date") from None


def _t_numdotdecimal(shown: str) -> str:
    s = shown.strip()
    if not _NUMDOTDECIMAL_RE.match(s):
        raise UnsupportedInlineXBRL(f"ixt:numdotdecimal: {shown!r} does not fit the format")
    return re.sub(r"[,  ]", "", s)


def _t_dateyearmonthdaycjk(shown: str) -> str:
    m = _DATE_CJK_RE.match(shown.strip().translate(_DIGITS))
    if not m:
        raise UnsupportedInlineXBRL(f"ixt:dateyearmonthdaycjk: {shown!r} does not fit the format")
    y, mo, d = (int(g) for g in m.groups())
    return _iso_date(y, mo, d, "ixt:dateyearmonthdaycjk", shown)


def _t_dateerayearmonthdayjp(shown: str) -> str:
    m = _DATE_ERA_RE.match(shown.strip().translate(_DIGITS))
    if not m:
        raise UnsupportedInlineXBRL(f"ixt:dateerayearmonthdayjp: {shown!r} does not fit the format")
    era, year, mo, d = m.groups()
    y = _ERAS[era] + (1 if year == "元" else int(year)) - 1
    return _iso_date(y, int(mo), int(d), "ixt:dateerayearmonthdayjp", shown)


# (namespace, local name) -> (applies to, transform). Only formats verified against EDINET
# filings and their instance documents are here.
_FORMATS = {
    (IXT_2011, "numdotdecimal"): ("nonFraction", _t_numdotdecimal),
    (IXT_2011, "dateyearmonthdaycjk"): ("nonNumeric", _t_dateyearmonthdaycjk),
    (IXT_2011, "dateerayearmonthdayjp"): ("nonNumeric", _t_dateerayearmonthdayjp),
}


class _Doc:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self.nsmap: dict = {}
        refuse_dtd(data, name)
        events = ET.iterparse(io.BytesIO(data), events=("start-ns",))
        for _event, (prefix, uri) in events:
            if prefix in self.nsmap and self.nsmap[prefix] != uri:
                raise UnsupportedInlineXBRL(
                    f"{name}: prefix {prefix!r} is bound to two namespaces; QName values "
                    "cannot be resolved"
                )
            self.nsmap[prefix] = uri
        self.root = events.root

    def resolve(self, qname: str, what: str) -> tuple[str, str]:
        prefix, sep, local = qname.partition(":")
        if not sep:
            prefix, local = "", qname
        if prefix not in self.nsmap:
            raise UnsupportedInlineXBRL(f"{self.name}: {what} {qname!r} uses an undeclared prefix")
        return self.nsmap[prefix], local


class _Reader:
    def __init__(self, documents: dict):
        self.docs = [_Doc(name, data) for name, data in sorted(documents.items())]
        self.result = XbrlFacts(source_files=[d.name for d in self.docs])
        self.continuations: dict = {}  # id -> (doc, element)

    # -- validation ------------------------------------------------------------------------

    def _check(self, doc: _Doc, el: ET.Element, local: str) -> None:
        if local not in _IX_ELEMENTS:
            raise UnsupportedInlineXBRL(f"{doc.name}: ix:{local} is not implemented")
        allowed = _ALLOWED_ATTRS[local]
        for attr in el.attrib:
            if attr not in allowed:
                shown = attr.replace(f"{{{XSI}}}", "xsi:").replace(f"{{{XML_NS}}}", "xml:")
                raise UnsupportedInlineXBRL(
                    f"{doc.name}: attribute {shown!r} on ix:{local} is not implemented"
                )

    # -- resources -------------------------------------------------------------------------

    def _read_resources(self, doc: _Doc, resources: ET.Element) -> None:
        for el in resources:
            ns, local = _local(el.tag)
            if ns == XBRLI and local == "context":
                ctx = read_context(el)
                put_unique(self.result.contexts, ctx.id, ctx, f"{doc.name}: context")
            elif ns == XBRLI and local == "unit":
                put_unique(self.result.units, el.get("id"), read_unit(el), f"{doc.name}: unit")
            elif ns == "http://www.xbrl.org/2003/linkbase" and local in ("roleRef", "arcroleRef"):
                continue
            else:
                raise UnsupportedInlineXBRL(
                    f"{doc.name}: {el.tag} in ix:resources is not implemented"
                )

    # -- facts -----------------------------------------------------------------------------

    def _text(self, el: ET.Element) -> str:
        """Text content of el with ix:exclude subtrees removed (nested facts contribute)."""
        parts = [el.text or ""]
        for child in el:
            ns, local = _local(child.tag)
            if not (ns in IX_NAMESPACES and local == "exclude"):
                parts.append(self._text(child))
            parts.append(child.tail or "")
        return "".join(parts)

    def _html(self, doc: _Doc, el: ET.Element) -> str:
        """Serialization of el's content as XHTML, ix wrappers stripped, ix:exclude removed."""
        parts = [html.escape(el.text or "", quote=False)]
        for child in el:
            parts.append(self._html_element(doc, child))
            parts.append(html.escape(child.tail or "", quote=False))
        return "".join(parts)

    def _html_element(self, doc: _Doc, el: ET.Element) -> str:
        ns, local = _local(el.tag)
        if ns in IX_NAMESPACES:
            if local == "exclude":
                return ""
            return self._html(doc, el)
        if ns != XHTML:
            raise UnsupportedInlineXBRL(f"{doc.name}: element {el.tag} inside a text section")
        attrs = []
        for k, v in el.attrib.items():
            if k.startswith(f"{{{XML_NS}}}"):
                k = "xml:" + k.split("}", 1)[1]
            elif k.startswith("{"):
                raise UnsupportedInlineXBRL(f"{doc.name}: attribute {k} inside a text section")
            attrs.append(f' {k}="{html.escape(v, quote=True)}"')
        if local in _VOID_TAGS and not len(el) and not el.text:
            return f"<{local}{''.join(attrs)} />"
        return f"<{local}{''.join(attrs)}>{self._html(doc, el)}</{local}>"

    def _chain(self, doc: _Doc, el: ET.Element) -> list:
        """[(doc, element)] for el and every ix:continuation it continues at."""
        out = [(doc, el)]
        seen = set()
        nxt = el.get("continuedAt")
        while nxt:
            if nxt in seen:
                raise UnsupportedInlineXBRL(f"{doc.name}: continuation cycle at {nxt!r}")
            seen.add(nxt)
            if nxt not in self.continuations:
                raise UnsupportedInlineXBRL(
                    f"{doc.name}: continuedAt {nxt!r} has no ix:continuation"
                )
            cdoc, cel = self.continuations[nxt]
            out.append((cdoc, cel))
            nxt = cel.get("continuedAt")
        return out

    def _fact(self, doc: _Doc, el: ET.Element, local: str) -> XbrlFact:
        name = el.get("name")
        ctx = el.get("contextRef")
        if not name or not ctx:
            raise UnsupportedInlineXBRL(f"{doc.name}: ix:{local} without name or contextRef")
        doc.resolve(name, "name")
        if ctx not in self.result.contexts:
            raise UnsupportedInlineXBRL(f"{doc.name}: contextRef {ctx!r} is not defined")
        nil = el.get(f"{{{XSI}}}nil") in ("true", "1")
        fmt = el.get("format")
        transform = None
        if fmt:
            key = doc.resolve(fmt, "format")
            if key not in _FORMATS:
                raise UnsupportedInlineXBRL(f"{doc.name}: format {fmt!r} is not implemented")
            applies, transform = _FORMATS[key]
            if applies != local:
                raise UnsupportedInlineXBRL(f"{doc.name}: format {fmt!r} on ix:{local}")
        refs = tuple((el.get("footnoteRefs") or "").split())
        common = dict(
            element_id=name,
            context_id=ctx,
            nil=nil,
            format=fmt,
            footnote_refs=refs,
            source_file=doc.name,
        )
        if local == "nonFraction":
            unit = el.get("unitRef")
            if unit not in self.result.units:
                raise UnsupportedInlineXBRL(f"{doc.name}: unitRef {unit!r} is not defined")
            sign, scale = el.get("sign"), el.get("scale")
            if sign not in (None, "-"):
                raise UnsupportedInlineXBRL(f"{doc.name}: sign {sign!r} is not implemented")
            common.update(unit_id=unit, decimals=el.get("decimals"), scale=scale, sign=sign)
            if nil:
                if len(el) or (el.text or "").strip():
                    raise UnsupportedInlineXBRL(
                        f"{doc.name}: nil ix:nonFraction {name} has content"
                    )
                return XbrlFact(value=None, **common)
            if len(el):
                raise UnsupportedInlineXBRL(
                    f"{doc.name}: ix:nonFraction {name} has child elements (nested nonFraction "
                    "is not implemented)"
                )
            shown = el.text or ""
            if transform:
                digits = transform(shown)
            else:
                digits = shown.strip()
                if not _PLAIN_DECIMAL_RE.match(digits):
                    raise UnsupportedInlineXBRL(
                        f"{doc.name}: ix:nonFraction {name} {shown!r} has no format and is not "
                        "a plain decimal"
                    )
            try:
                number = Decimal(digits)
                if scale:
                    number = number.scaleb(int(scale))
            except (InvalidOperation, ValueError):
                raise UnsupportedInlineXBRL(f"{doc.name}: scale {scale!r} on {name}") from None
            value = format(number, "f")
            if sign == "-":
                # a zero shown with sign="-" reads "-0", as EDINET's instance and CSV write it
                value = "-" + value
            return XbrlFact(value=value, **common)

        # nonNumeric
        escape = el.get("escape")
        if escape not in (None, "true", "false", "1", "0"):
            raise UnsupportedInlineXBRL(f"{doc.name}: escape {escape!r} on {name}")
        escaped = escape in ("true", "1")
        if nil:
            if len(el) or (el.text or "").strip() or el.get("continuedAt"):
                raise UnsupportedInlineXBRL(f"{doc.name}: nil ix:nonNumeric {name} has content")
            return XbrlFact(value=None, **common)
        chain = self._chain(doc, el)
        if escaped and not transform:
            markup = "".join(self._html(d, e) for d, e in chain)
            return XbrlFact(value=html_to_text(markup), html=markup, **common)
        # plain, or escaped with a format: the transform reads the element's text (Inline XBRL
        # permits format on any nonNumeric; S100YRJE's escaped FilingDateCoverPage carries one)
        text = "".join(self._text(e) for _d, e in chain)
        if transform:
            text = transform(text)
        elif name.rpartition(":")[2].endswith("TextBlock"):
            text = plain_text_block_value(text)
        return XbrlFact(value=text, **common)

    # -- driver ----------------------------------------------------------------------------

    def read(self) -> XbrlFacts:
        # Pass 1: validate every ix element; collect resources, continuations, footnotes.
        fact_elements = []
        for doc in self.docs:
            for el in doc.root.iter():
                if not isinstance(el.tag, str):
                    continue
                ns, local = _local(el.tag)
                if ns not in IX_NAMESPACES:
                    continue
                self._check(doc, el, local)
                if local == "resources":
                    self._read_resources(doc, el)
                elif local == "continuation":
                    cid = el.get("id")
                    if not cid or cid in self.continuations:
                        raise UnsupportedInlineXBRL(f"{doc.name}: ix:continuation id {cid!r}")
                    self.continuations[cid] = (doc, el)
                elif local == "footnote":
                    fid = el.get("footnoteID") or el.get("id")
                    if not fid:
                        raise UnsupportedInlineXBRL(f"{doc.name}: ix:footnote without an id")
                    put_unique(self.result.footnotes, fid, self._text(el), f"{doc.name}: footnote")
                elif local in ("nonFraction", "nonNumeric"):
                    fact_elements.append((doc, el, local))
        # Pass 2: facts, in document order.
        for doc, el, local in fact_elements:
            self.result.facts.append(self._fact(doc, el, local))
        for f in self.result.facts:
            for ref in f.footnote_refs:
                if ref not in self.result.footnotes:
                    raise UnsupportedInlineXBRL(
                        f"footnoteRefs {ref!r} on {f.element_id} is not defined"
                    )
        return self.result


def read_context(el: ET.Element) -> XbrlContext:
    """An `xbrli:context` element as an XbrlContext (shared with the instance reader)."""
    cid = el.get("id")
    entity = start = end = instant = None
    forever = False
    dims: dict = {}
    for sub in el.iter():
        ns, local = _local(sub.tag)
        text = (sub.text or "").strip()
        if ns == XBRLI and local == "identifier":
            entity = text
        elif ns == XBRLI and local == "startDate":
            start = text
        elif ns == XBRLI and local == "endDate":
            end = text
        elif ns == XBRLI and local == "instant":
            instant = text
        elif ns == XBRLI and local == "forever":
            forever = True
        elif ns == XBRLDI and local == "explicitMember":
            dims[sub.get("dimension")] = text
        elif ns == XBRLDI and local == "typedMember":
            dims[sub.get("dimension")] = "".join(sub.itertext()).strip()
    if not (instant or (start and end) or forever):
        raise UnsupportedInlineXBRL(f"context {cid!r} has no period")
    return XbrlContext(
        id=cid,
        entity=entity,
        period_start=start,
        period_end=end,
        instant=instant,
        forever=forever,
        dimensions=dims,
    )


def read_unit(el: ET.Element) -> str:
    """An `xbrli:unit` as text: 'iso4217:JPY', or 'iso4217:JPY/xbrli:shares' for a divide."""

    def measures(parent: ET.Element) -> str:
        return "*".join((m.text or "").strip() for m in parent.findall(f"{{{XBRLI}}}measure"))

    divide = el.find(f"{{{XBRLI}}}divide")
    if divide is None:
        return measures(el)
    num = divide.find(f"{{{XBRLI}}}unitNumerator")
    den = divide.find(f"{{{XBRLI}}}unitDenominator")
    if num is None or den is None:
        raise UnsupportedInlineXBRL(f"unit {el.get('id')!r}: divide without numerator/denominator")
    return f"{measures(num)}/{measures(den)}"


def read_inline_xbrl(documents: dict) -> XbrlFacts:
    """Facts from a set of inline XBRL documents forming one filing: {file name: bytes}.
    Documents are read in file-name order (EDINET numbers them), so a continuation may sit in
    a later document than the fact it continues."""
    if not documents:
        raise UnsupportedInlineXBRL("no inline XBRL documents given")
    return _Reader(documents).read()


def _is_audit(name: str) -> bool:
    parts = name.split("/")
    return "AuditDoc" in parts or parts[-1].startswith("jpaud")


def inline_documents_in_package(zip_bytes: bytes, include_audit: bool = False) -> dict:
    """{(directory, filing): {file name: bytes}} of the package's `*_ixbrl.htm` files. The auditor's
    documents (XBRL/AuditDoc, `jpaud*`) are left out unless asked for, as the CSV path leaves
    out `jpaud*.csv`."""
    _names, members = read_package_members(
        zip_bytes,
        lambda n: n.endswith("_ixbrl.htm") and (include_audit or not _is_audit(n)),
    )
    return group_inline_documents(members)


# EDINET names each inline document <order>_<kind>_<stem>_ixbrl.htm (kind: header, honbun,
# bsdata, pldata, ...); every document of one filing shares the stem of its instance, <stem>.xbrl.
_IXBRL_NAME_RE = re.compile(r"^\d+_[A-Za-z]+_(.+)_ixbrl\.htm$")


def filing_of(name: str) -> str:
    """The filing an inline document belongs to, named as its instance: '<stem>.xbrl'."""
    base = posixpath.basename(name)
    m = _IXBRL_NAME_RE.match(base)
    stem = m.group(1) if m else base[: -len("_ixbrl.htm")]
    return stem + ".xbrl"


def group_inline_documents(members: dict) -> dict:
    """{(directory, filing): {file name: bytes}} from {path: bytes} of `*_ixbrl.htm` members.
    One group per filing: a directory may hold several (a fund and each of its series)."""
    groups: dict = {}
    for name, data in members.items():
        key = (posixpath.dirname(name), filing_of(name))
        groups.setdefault(key, {})[posixpath.basename(name)] = data
    return groups


def read_inline_xbrl_package(zip_bytes: bytes, include_audit: bool = False) -> XbrlFacts:
    """Facts from every inline XBRL filing of an EDINET type=1 package (PublicDoc; AuditDoc
    only with include_audit). Each filing's documents are read as one set against its own
    definitions (see XbrlFacts); the filings' facts are concatenated, each tagged `filing`."""
    groups = inline_documents_in_package(zip_bytes, include_audit=include_audit)
    if not groups:
        raise UnsupportedInlineXBRL("no inline XBRL (*_ixbrl.htm) in the package")
    merged = XbrlFacts()
    for directory, filing in sorted(groups):
        part = read_inline_xbrl(groups[(directory, filing)])
        part.facts = [_with_source(f, f"{directory}/{f.source_file}") for f in part.facts]
        add_filing(merged, part, filing)
        merged.source_files.extend(f"{directory}/{n}" for n in part.source_files)
    return merged


def _with_source(fact: XbrlFact, source: str) -> XbrlFact:
    from dataclasses import replace

    return replace(fact, source_file=source)
