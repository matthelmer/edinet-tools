"""
Parser for Exemption Application filings (Doc Type 330/340).

Extracts data from 買付け等の制限の免除申請書 filings. These are filed when
a party seeks regulatory exemption from the prohibition on separate
purchases during a tender offer period. The FSA must approve the
exemption before the purchases can proceed.

Doc 330: Original exemption application
Doc 340: Amendment to exemption application
"""
from dataclasses import dataclass
from typing import Optional

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
)


# Common DEI elements available across all filing types.
# Domain-specific elements can be added once real Doc 330/340 filings
# have been inspected for their XBRL element names.
ELEMENT_MAP = {
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',
}


@dataclass
class ExemptionApplicationReport(ParsedReport):
    """
    Parsed Exemption Application filing (Doc 330/340).

    Filed when a party seeks exemption from the separate purchase
    prohibition during a tender offer period. No confirmed filings exist
    in the database as of 2026-03, but the doc type is part of the
    standard EDINET tender offer family (240-340).

    Key fields:
        filer_name: Name of the entity applying for the exemption
        filer_edinet_code: EDINET code of the applicant
        security_code: Securities code of the target company
        is_amendment: Whether this is an amendment (Doc 340)

    Use raw_fields and text_blocks to explore available XBRL elements
    in real filings before extending this parser with domain-specific fields.
    """

    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    security_code: str | None = None
    is_amendment: bool = False

    def __repr__(self) -> str:
        name = self.filer_name or 'Unknown'
        if len(name) > 30:
            name = name[:27] + '...'
        amend = ' [AMENDED]' if self.is_amendment else ''
        return f"ExemptionApplicationReport(filer='{name}'{amend})"


def parse_exemption_application(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> ExemptionApplicationReport:
    """
    Parse an Exemption Application filing (Doc 330/340).

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        ExemptionApplicationReport with extracted DEI fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return ExemptionApplicationReport(
            doc_id=doc_id,
            doc_type_code=doc_type_code,
            source_files=[],
            raw_fields={},
            unmapped_fields={},
            text_blocks={},
        )

    source_files = [f['filename'] for f in csv_files]

    def get(key: str, context: list[str] | None = None) -> str | None:
        return extract_value(csv_files, ELEMENT_MAP.get(key, ''), context_patterns=context)

    filer_edinet_code = get('filer_edinet_code', ['FilingDateInstant'])
    filer_name = get('filer_name', ['FilingDateInstant'])
    filer_name_en = get('filer_name_en', ['FilingDateInstant'])
    security_code = get('security_code', ['FilingDateInstant'])
    amendment_flag = get('amendment_flag', ['FilingDateInstant'])
    is_amendment = amendment_flag == 'true' if amendment_flag else False

    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return ExemptionApplicationReport(
        doc_id=doc_id,
        doc_type_code=doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,
        filer_name=filer_name,
        filer_name_en=filer_name_en,
        filer_edinet_code=filer_edinet_code or getattr(document, 'filer_edinet_code', None) if document else filer_edinet_code,
        security_code=security_code,
        is_amendment=is_amendment,
    )
