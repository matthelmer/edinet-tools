"""XBRL facts as the rows EDINET's CSV gives, so every parser reads either source unchanged.

`extract_rows_from_package(zip_bytes, source)` returns what `extract_csv_from_zip` returns: a list
of {'filename', 'data'} with one entry per filing in the package (the auditor's left out, as the
CSV path leaves them out) and one row per fact, in document order.

Columns filled as the CSV fills them where the XBRL states it: 要素ID, コンテキストID, ユニットID
('－' when the fact has no unit, as the CSV writes it), 期間・時点 ('期間' / '時点' from the
context's period), 値 ('－' for a nil fact, as the CSV writes it). Left '' because they are labels
from taxonomy files the reader does not read: 項目名, 相対年度, 連結・個別, and 単位 for a fact
with a unit ('－' without one, as the CSV).

Added: html (a text section's HTML as filed, else None), decimals, scale, sign, nil,
period_start, period_end, instant (the context's real dates), source ('xbrl' / 'instance').

A plain string's 値 follows the CSV's rule (no-break space -> space, line breaks dropped) so
names compare equal across sources; the reader's XbrlFact keeps it as filed. A text section's 値
is its plain text with a tab between cells and a newline between rows (not the CSV's
run-together cells), and it is not cut at 30,000 characters.
"""

from __future__ import annotations

import posixpath
import re

from ._xbrl_model import (
    XBRL_SOURCES,
    UnsupportedInlineXBRL,
    XbrlFacts,
    normalize_source,
    read_package_members,
)
from .ixbrl import _is_audit, group_inline_documents, read_inline_xbrl
from .xbrl_instance import read_instance

__all__ = ["SOURCES", "extract_rows_from_package", "facts_to_rows"]

SOURCES = XBRL_SOURCES
_NIL = "－"
_LINE_BREAK_RE = re.compile(r"[\r\n]")


def _csv_plain(value: str) -> str:
    """A plain (non-text-section) string as the CSV writes it: a no-break space becomes a
    space and line breaks are dropped. Measured on the fixtures: every one of the 41 plain
    strings where the filed value and the CSV differ differs by exactly this."""
    return _LINE_BREAK_RE.sub("", value.replace("\u00a0", " "))


def facts_to_rows(facts: XbrlFacts, source: str) -> list:
    rows = []
    for f in facts.facts:
        ctx = facts.contexts[f.context_id]
        if ctx.instant:
            kind = "時点"
        elif ctx.period_start:
            kind = "期間"
        else:
            kind = ""
        rows.append(
            {
                "要素ID": f.element_id,
                "項目名": "",
                "コンテキストID": f.context_id,
                "相対年度": "",
                "連結・個別": "",
                "期間・時点": kind,
                "ユニットID": f.unit_id or _NIL,
                "単位": "" if f.unit_id else _NIL,
                "値": _NIL if f.nil else (f.value if f.html is not None else _csv_plain(f.value)),
                "html": f.html,
                "decimals": f.decimals,
                "scale": f.scale,
                "sign": f.sign,
                "nil": f.nil,
                "period_start": ctx.period_start,
                "period_end": ctx.period_end,
                "instant": ctx.instant,
                "source": source,
            }
        )
    return rows


def extract_rows_from_package(zip_bytes: bytes, source: str = "xbrl") -> list:
    """Rows from an EDINET type=1 package, in `extract_csv_from_zip`'s shape.

    source='xbrl' (alias 'ixbrl') reads the inline XBRL (what the filer submitted);
    source='instance' reads the `.xbrl` instance EDINET generates beside it. The zip is
    opened once and its members size-capped. Raises UnsupportedInlineXBRL when the package
    has no such files or uses a feature the reader does not implement."""
    source = normalize_source(source)
    if source == "xbrl":
        _names, members = read_package_members(
            zip_bytes, lambda n: n.endswith("_ixbrl.htm") and not _is_audit(n)
        )
        groups = group_inline_documents(members)
        if not groups:
            raise UnsupportedInlineXBRL("no inline XBRL (*_ixbrl.htm) in the package")
        # one entry per filing, as the CSV gives one file per instance; each filing's facts
        # resolve against its own definitions
        out = []
        for directory, filing in sorted(groups):
            facts = read_inline_xbrl(groups[(directory, filing)])
            out.append({"filename": filing, "data": facts_to_rows(facts, source)})
        return out
    _names, members = read_package_members(
        zip_bytes, lambda n: n.endswith(".xbrl") and not _is_audit(n)
    )
    if not members:
        raise UnsupportedInlineXBRL("no XBRL instance (*.xbrl) in the package")
    out = []
    for n in sorted(members):
        name = posixpath.basename(n)
        out.append(
            {"filename": name, "data": facts_to_rows(read_instance(members[n], name), source)}
        )
    return out
