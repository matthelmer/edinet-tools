"""What the two XBRL readers (inline and instance) produce, and the text rule they share.

Both readers return an `XbrlFacts`: every fact as filed, the contexts with their real dates and
dimensions, the units, and (inline only) the footnotes. The rows adapter in `xbrl_rows.py` turns
it into the rows the CSV path gives, so every parser reads it unchanged.

A text section (an escaped `ix:nonNumeric`, a `...TextBlock` in the instance) keeps its HTML as
filed in `html`; its `value` is the text with tags removed, a TAB between table cells and a
newline between rows and blocks (`html_to_text`). EDINET's CSV runs the cells together
("90,0000.29" for 90,000 shares at 0.29%); the tab keeps them apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

from ..exceptions import EdinetError


class UnsupportedInlineXBRL(EdinetError):
    """The filing uses an XBRL feature the reader does not implement, or breaks a rule it
    checks. Raised instead of guessing; the message names the feature."""


@dataclass(frozen=True)
class XbrlContext:
    id: str
    entity: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    instant: Optional[str] = None
    forever: bool = False
    # dimension QName -> member QName (explicit) or the member's text (typed), as written
    dimensions: dict = field(default_factory=dict)


@dataclass(frozen=True)
class XbrlFact:
    """One fact as filed. `value` is None when the fact is nil; for a text section it is the
    plain text (see module docstring) and `html` holds the HTML."""

    element_id: str
    context_id: str
    value: Optional[str]
    unit_id: Optional[str] = None
    decimals: Optional[str] = None
    scale: Optional[str] = None
    sign: Optional[str] = None
    nil: bool = False
    html: Optional[str] = None
    format: Optional[str] = None
    footnote_refs: tuple = ()
    source_file: str = ""


@dataclass
class XbrlFacts:
    facts: list = field(default_factory=list)
    contexts: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    footnotes: dict = field(default_factory=dict)
    source_files: list = field(default_factory=list)


# --- html_to_text ----------------------------------------------------------------------------

_BLOCK_TAGS = frozenset(
    {
        "p", "div", "br", "table", "tr", "li", "ul", "ol", "dl", "dt", "dd", "h1", "h2", "h3",
        "h4", "h5", "h6", "blockquote", "pre", "hr", "caption", "thead", "tbody", "tfoot",
        "section", "article", "header", "footer", "address", "center",
    }
)  # fmt: skip
_CELL_TAGS = frozenset({"td", "th"})
_SKIP_TAGS = frozenset({"script", "style"})
_VOID_TAGS = frozenset({"br", "hr", "col", "img", "meta", "link", "input", "area", "base", "wbr"})
_NL, _TAB, _SP = "\x00NL", "\x00TAB", "\x00SP"
# HTML's collapsible whitespace. U+00A0 (&#160;) is read as a space too, as the CSV does;
# U+3000 (the ideographic space) is text and is kept.
_WS_RE = re.compile(r"[ \t\n\r\f ]+")


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list = []
        self.cell_depth = 0  # open td/th elements
        self.row_cells: list = []  # per open table at cell depth 0: cells begun in the row
        self.skip = 0

    def _boundary(self, tag: str) -> None:
        self.out.append(_SP if self.cell_depth else _NL)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip += 1
            return
        if tag in _CELL_TAGS:
            if self.cell_depth == 0:
                if self.row_cells and self.row_cells[-1] > 0:
                    self.out.append(_TAB)
                if self.row_cells:
                    self.row_cells[-1] += 1
            else:
                self.out.append(_SP)
            self.cell_depth += 1
            return
        if tag == "table" and self.cell_depth == 0:
            self.row_cells.append(0)
        if tag == "tr" and self.cell_depth == 0 and self.row_cells:
            self.row_cells[-1] = 0
        if tag in _BLOCK_TAGS:
            self._boundary(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self._boundary(tag)

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if tag in _CELL_TAGS:
            self.cell_depth = max(0, self.cell_depth - 1)
            return
        if tag == "table" and self.cell_depth == 0 and self.row_cells:
            self.row_cells.pop()
        if tag in _BLOCK_TAGS:
            self._boundary(tag)

    def handle_data(self, data):
        if not self.skip:
            self.out.append(_WS_RE.sub(" ", data))


def html_to_text(markup: str) -> str:
    """Plain text of an HTML fragment: tags removed, a tab between the cells of a row, a
    newline between rows and between blocks. Runs of HTML whitespace collapse to one space
    and are trimmed at cell and line edges; empty lines are dropped. Cells of a table nested
    inside a cell are joined by a space (the tab and newline belong to the outer table)."""
    collector = _TextCollector()
    collector.feed(markup)
    collector.close()
    text = "".join(collector.out).replace(_SP, " ")
    lines = []
    for line in text.split(_NL):
        cells = [_WS_RE.sub(" ", c).strip(" ") for c in line.split(_TAB)]
        if any(cells):
            lines.append("\t".join(cells))
    return "\n".join(lines)


def normalize_space(text: Optional[str]) -> Optional[str]:
    """Every whitespace character removed: the comparison key for text between sources
    (the CSV runs cells together; the XBRL readers separate them)."""
    if text is None:
        return None
    return "".join(text.split())
