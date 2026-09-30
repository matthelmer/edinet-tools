"""Read facts from an XBRL instance document (the `.xbrl` in an EDINET type=1 package).

Standard library only (`xml.etree`). The instance is what EDINET generates from the inline
documents; this reader is the inline reader's cross-check and `source='instance'` for a package
without inline files. Facts are the root's children that carry a `contextRef`; element IDs are
written with the instance's own prefixes. A `...TextBlock` value is escaped HTML: `html` keeps it
and `value` is its plain text by the same rule as the inline reader (`html_to_text`). The instance
cannot tell a text block filed unescaped from an escaped one; for plain text the two rules give
the same value (`plain_text_block_value`), and only `html` differs (None inline). The reverse
also holds: an element escaped in the inline XBRL whose name does not end in TextBlock
(S100YWY3, `...:NoteRegardingResearchAndDevelopments`) comes back from this reader as the raw
HTML string, where the inline reader gives its plain text. Prefer source='xbrl'.
A document with a DOCTYPE or ENTITY declaration is refused before parsing; package members are
size-capped. Definitions are scoped per instance file, one filing each (see XbrlFacts); defined
twice inside one file, a context or unit must be defined identically.

Tuples, and any root child other than a fact, a context, a unit, the schema reference, role
references or a footnote link, raise `UnsupportedInlineXBRL`. Footnote links are not read (the
CSV carries no footnotes).
"""

from __future__ import annotations

import io
import posixpath
import xml.etree.ElementTree as ET

from ._xbrl_model import (
    UnsupportedInlineXBRL,
    XbrlFact,
    XbrlFacts,
    html_to_text,
    add_filing,
    put_unique,
    read_package_members,
    refuse_dtd,
)
from .ixbrl import XBRLI, XSI, _is_audit, _local, read_context, read_unit

__all__ = ["UnsupportedInlineXBRL", "read_instance", "read_instance_package"]

LINK = "http://www.xbrl.org/2003/linkbase"
_LINK_CHILDREN = frozenset({"schemaRef", "roleRef", "arcroleRef", "footnoteLink", "linkbaseRef"})


def read_instance(data: bytes, name: str = "") -> XbrlFacts:
    """Facts, contexts and units of one XBRL instance document."""
    refuse_dtd(data, name or "instance")
    prefixes: dict = {}
    events = ET.iterparse(io.BytesIO(data), events=("start-ns",))
    for _event, (prefix, uri) in events:
        if prefixes.get(uri, prefix) != prefix:
            raise UnsupportedInlineXBRL(
                f"{name}: namespace {uri} is bound to two prefixes; element IDs are ambiguous"
            )
        prefixes[uri] = prefix
    root = events.root
    result = XbrlFacts(source_files=[name] if name else [])

    fact_elements = []
    for el in root:
        ns, local = _local(el.tag)
        if ns == XBRLI and local == "context":
            ctx = read_context(el)
            put_unique(result.contexts, ctx.id, ctx, f"{name}: context")
        elif ns == XBRLI and local == "unit":
            put_unique(result.units, el.get("id"), read_unit(el), f"{name}: unit")
        elif ns == LINK and local in _LINK_CHILDREN:
            continue
        elif el.get("contextRef") is not None:
            fact_elements.append(el)
        else:
            qname = f"{prefixes.get(ns, ns)}:{local}"
            raise UnsupportedInlineXBRL(f"{name}: {qname} (a tuple or unknown element)")

    for el in fact_elements:
        ns, local = _local(el.tag)
        element_id = f"{prefixes[ns]}:{local}" if prefixes.get(ns) else local
        ctx = el.get("contextRef")
        if ctx not in result.contexts:
            raise UnsupportedInlineXBRL(f"{name}: contextRef {ctx!r} is not defined")
        unit = el.get("unitRef")
        if unit is not None and unit not in result.units:
            raise UnsupportedInlineXBRL(f"{name}: unitRef {unit!r} is not defined")
        if len(el):
            raise UnsupportedInlineXBRL(f"{name}: {element_id} has child elements")
        nil = el.get(f"{{{XSI}}}nil") in ("true", "1")
        common = dict(
            element_id=element_id,
            context_id=ctx,
            unit_id=unit,
            decimals=el.get("decimals"),
            nil=nil,
            source_file=name,
        )
        if nil:
            result.facts.append(XbrlFact(value=None, **common))
        elif local.endswith("TextBlock"):
            markup = el.text or ""
            result.facts.append(XbrlFact(value=html_to_text(markup), html=markup, **common))
        else:
            text = el.text or ""
            result.facts.append(XbrlFact(value=text.strip() if unit else text, **common))
    return result


def read_instance_package(zip_bytes: bytes, include_audit: bool = False) -> XbrlFacts:
    """Facts from every `.xbrl` instance of an EDINET type=1 package (the auditor's left out
    unless asked for, as the CSV path leaves out `jpaud*.csv`), concatenated in path order."""
    _names, members = read_package_members(
        zip_bytes, lambda n: n.endswith(".xbrl") and (include_audit or not _is_audit(n))
    )
    if not members:
        raise UnsupportedInlineXBRL("no XBRL instance (*.xbrl) in the package")
    merged = XbrlFacts()
    for n in sorted(members):
        part = read_instance(members[n], name=posixpath.basename(n))
        add_filing(merged, part, posixpath.basename(n))
        merged.source_files.append(n)
    return merged
