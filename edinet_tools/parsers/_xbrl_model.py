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

import html
import io
import re
import zipfile
import zlib
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
    # The filing (target instance) the fact belongs to, named as its .xbrl instance; set by the
    # package readers. Its context and unit resolve in contexts_by_filing[filing].
    filing: str = ""


@dataclass
class XbrlFacts:
    """Facts plus their definitions.

    A package can hold several filings (an investment trust's fund and each series), each an
    inline set and an instance of its own, and they may define the same context ID differently
    (S100YO5B: entity G14704-000 / -001 / -002). Definitions are scoped per filing:
    `contexts_by_filing` / `units_by_filing` / `footnotes_by_filing` hold each filing's own, and
    a fact resolves in its own filing's. `contexts` / `units` / `footnotes` are the package-wide
    view: the IDs every filing that defines them defines identically (an ID defined differently
    in two filings is only in the per-filing maps). Inside one filing a conflicting redefinition
    is refused."""

    facts: list = field(default_factory=list)
    contexts: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    footnotes: dict = field(default_factory=dict)
    source_files: list = field(default_factory=list)
    contexts_by_filing: dict = field(default_factory=dict)
    units_by_filing: dict = field(default_factory=dict)
    footnotes_by_filing: dict = field(default_factory=dict)


def add_filing(merged: XbrlFacts, part: XbrlFacts, filing: str) -> None:
    """Add one filing's facts and definitions to a package-level XbrlFacts, then rebuild the
    package-wide view (an ID stays there only while every filing defines it identically)."""
    from dataclasses import replace

    if filing in merged.contexts_by_filing:
        raise UnsupportedInlineXBRL(f"filing {filing!r} appears twice in the package")
    merged.facts.extend(replace(f, filing=filing) for f in part.facts)
    merged.contexts_by_filing[filing] = dict(part.contexts)
    merged.units_by_filing[filing] = dict(part.units)
    merged.footnotes_by_filing[filing] = dict(part.footnotes)
    for attr in ("contexts", "units", "footnotes"):
        agreed: dict = {}
        clashed: set = set()
        for defs in getattr(merged, attr + "_by_filing").values():
            for k, v in defs.items():
                if k in clashed:
                    continue
                if k in agreed and agreed[k] != v:
                    del agreed[k]
                    clashed.add(k)
                else:
                    agreed[k] = v
        setattr(merged, attr, agreed)


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


def plain_text_block_value(text: str) -> str:
    """The value of a text block filed as plain (unescaped) text: read as an HTML text node by
    `html_to_text`, so the inline reader (which knows it is unescaped) and the instance reader
    (which cannot tell, and reads every ...TextBlock as HTML) give the same text."""
    return html_to_text(html.escape(text, quote=False))


# --- sources ---------------------------------------------------------------------------------

# One vocabulary: 'xbrl' is the filing's inline XBRL; 'ixbrl' is accepted as its alias;
# 'instance' is the .xbrl instance EDINET generates beside it.
XBRL_SOURCES = ("xbrl", "instance")
_SOURCE_ALIASES = {"xbrl": "xbrl", "ixbrl": "xbrl", "instance": "instance"}


def normalize_source(source: str) -> str:
    try:
        return _SOURCE_ALIASES[source]
    except (KeyError, TypeError):
        raise ValueError(
            f"source must be 'xbrl' (alias 'ixbrl') or 'instance', not {source!r}"
        ) from None


# --- safety ------------------------------------------------------------------------------------

# Uncompressed-size caps for what a reader takes out of a package. A member's declared
# ZipInfo.file_size is checked first, but a forged header can lie, so every member is also
# read through zf.open() in READ_CHUNK_BYTES pieces and the bytes that actually arrive are
# counted against both caps; nothing is inflated beyond one chunk past a cap.
MAX_MEMBER_BYTES = 200 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024

_DTD_RE = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def refuse_dtd(data: bytes, name: str) -> None:
    """Refuse a document that carries a DOCTYPE or ENTITY declaration, before it is parsed
    (entity expansion is the classic XML bomb; EDINET's documents carry neither)."""
    candidates = [data]
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        candidates.append(data.decode("utf-16", errors="replace").encode("utf-8"))
    if b"\x00" in data:
        # UTF-16 (or UTF-32) without a BOM, which expat detects on its own: the ASCII of a
        # declaration survives with its NUL bytes removed.
        candidates.append(data.replace(b"\x00", b""))
    for c in candidates:
        m = _DTD_RE.search(c)
        if m:
            kind = m.group(1).decode("ascii").upper()
            raise UnsupportedInlineXBRL(f"{name}: a {kind} declaration is refused")


def _read_capped(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: list) -> bytes:
    """One member, read in bounded chunks; budget[0] is what the package may still inflate."""
    parts = []
    size = 0
    try:
        with zf.open(info) as f:
            while True:
                chunk = f.read(READ_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                budget[0] -= len(chunk)
                if size > MAX_MEMBER_BYTES:
                    raise UnsupportedInlineXBRL(
                        f"{info.filename}: too large (over {MAX_MEMBER_BYTES} bytes uncompressed)"
                    )
                if budget[0] < 0:
                    raise UnsupportedInlineXBRL(
                        f"package too large (over {MAX_TOTAL_BYTES} bytes uncompressed)"
                    )
                parts.append(chunk)
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as e:
        raise UnsupportedInlineXBRL(f"{info.filename}: corrupt zip member ({e})") from None
    return b"".join(parts)


def read_package_members(zip_bytes: bytes, wanted) -> tuple:
    """(namelist, {name: bytes}) for the members `wanted(name)` selects, opening the zip once.
    Declared sizes are checked against MAX_MEMBER_BYTES / MAX_TOTAL_BYTES before anything is
    read, and the bytes that actually arrive are counted against both as they are read."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise UnsupportedInlineXBRL(f"not a readable zip ({e})") from None
    with zf:
        infos = [i for i in zf.infolist() if "__MACOSX" not in i.filename and wanted(i.filename)]
        total = 0
        for info in infos:
            if info.file_size > MAX_MEMBER_BYTES:
                raise UnsupportedInlineXBRL(
                    f"{info.filename}: too large ({info.file_size} bytes uncompressed; "
                    f"limit {MAX_MEMBER_BYTES})"
                )
            total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise UnsupportedInlineXBRL(
                f"package too large ({total} bytes uncompressed; limit {MAX_TOTAL_BYTES})"
            )
        budget = [MAX_TOTAL_BYTES]
        return zf.namelist(), {i.filename: _read_capped(zf, i, budget) for i in infos}


def put_unique(mapping: dict, key, value, what: str) -> None:
    """mapping[key] = value, refusing a second definition that differs from the first."""
    if key in mapping and mapping[key] != value:
        raise UnsupportedInlineXBRL(f"{what} {key!r} is defined twice, differently")
    mapping[key] = value
