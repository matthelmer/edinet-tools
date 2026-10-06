"""
Base classes for document parsers.

ParsedReport is the base class for all parsed documents.
"""
from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Any

from ._facts import Fact


@dataclass
class ParsedReport:
    """
    Base class for all parsed EDINET documents.

    Subclasses add document-type-specific fields while preserving
    access to raw data.

    Attributes:
        doc_id: EDINET document ID
        doc_type_code: Document type code (e.g., "350")
        source_files: List of CSV files parsed from the ZIP
        raw_fields: All XBRL elements by element_id (nothing lost)
        unmapped_fields: Elements not mapped to explicit fields (excluding TextBlocks)
        text_blocks: TextBlock elements by name
        extraction_flags: Validation findings (bounds withheld / identities annotated)
        source_elements: Field name -> the element its value was read from
        source_contexts: Field name -> the context that element was read at
        units: Monetary or per-share field name -> the unit id of the fact
            read ('JPY' / 'JPYPerShares', or the foreign currency a filer
            tagged it in, e.g. 'USD' / 'USDPerShares'). A fact filed in yen and
            another currency at one context is read in yen. A value read from a
            row without a unit id has no entry: the map never holds None.

    The provenance maps are filled by the parsers that record them (the
    securities, quarterly and semi-annual reports) for every field that holds
    a value (`units`: every monetary and per-share field; ratios are not in
    it); a parser that records none leaves them empty, which means
    "not recorded", never "no value".
    """
    doc_id: str
    doc_type_code: str
    source_files: list[str] = field(default_factory=list)
    raw_fields: dict[str, Any] = field(default_factory=dict)
    unmapped_fields: dict[str, Any] = field(default_factory=dict)
    text_blocks: dict[str, Any] = field(default_factory=dict)
    raw_facts: list[Fact] = field(default_factory=list)
    extraction_flags: list = field(default_factory=list)
    source_elements: dict[str, str] = field(default_factory=dict)
    source_contexts: dict[str, str] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)

    def fields(self) -> list[str]:
        """List all field names for this report type."""
        return [f.name for f in dataclass_fields(self)]

    def to_dict(self) -> dict[str, Any]:
        """Export mapped fields as a dictionary."""
        result = {}
        for f in dataclass_fields(self):
            value = getattr(self, f.name)
            # Skip complex fields that don't serialize well
            if f.name in ('raw_fields', 'unmapped_fields', 'text_blocks'):
                continue
            if f.name == 'extraction_flags':
                result[f.name] = [flag.to_dict() for flag in value]
                continue
            result[f.name] = value
        return result

    def __repr__(self) -> str:
        return f"ParsedReport(doc_id='{self.doc_id}', doc_type={self.doc_type_code})"
