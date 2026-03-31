"""
Parser for Response to Questions Report filings (Doc Type 310/320).

Extracts data from 質問状に対する回答書 filings. These are filed by the
target company in response to questions raised during a tender offer
process — typically from a hostile bidder or concerned shareholders.

Doc 310: Original response to questions report
Doc 320: Amendment to response to questions report
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
# Domain-specific elements can be added once real Doc 310/320 filings
# have been inspected for their XBRL element names.
ELEMENT_MAP = {
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',
}


@dataclass
class QuestionResponseReport(ParsedReport):
    """
    Parsed Response to Questions Report (Doc 310/320).

    Filed by the target company in response to questions raised during
    a tender offer process. Rare filing type — only one confirmed filing
    in the database as of 2026-03.

    Key fields:
        filer_name: Name of the company filing the response
        filer_edinet_code: EDINET code of the filing company
        security_code: Securities code of the filing company
        is_amendment: Whether this is an amendment (Doc 320)

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
        return f"QuestionResponseReport(filer='{name}'{amend})"


def parse_question_response(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> QuestionResponseReport:
    """
    Parse a Response to Questions Report filing (Doc 310/320).

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        QuestionResponseReport with extracted DEI fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return QuestionResponseReport(
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

    return QuestionResponseReport(
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
