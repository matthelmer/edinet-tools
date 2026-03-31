"""
Parser for Large Shareholding Change Report filings (Doc Types 370/380).

変更報告書 — filed when a holder of 5%+ of a company's shares changes their
position by 1% or more (or when certain other material changes occur in their
holding status), as required under the Financial Instruments and Exchange Act.

Doc 370: Large shareholding change report (変更報告書)
Doc 380: Large shareholding change report amendment (変更報告書の訂正報告書)

Note: In practice, change reports (変更報告書) appear to file under doc type
350, not 370. Zero filings have been observed for doc type 370 in the EDINET
API. This parser exists for completeness — if a 370 filing ever appears, it
will be captured with typed routing rather than falling to parse_raw.
"""
from dataclasses import dataclass

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
)


# Common DEI elements available across all filing types.
# Enrich this map after inspecting real Doc 370 filings if they emerge.
ELEMENT_MAP = {
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',
}


@dataclass
class LargeHoldingChangeReport(ParsedReport):
    """
    Parsed Large Shareholding Change Report filing (Doc 370/380).

    Filed when a 5%+ shareholder's position changes by 1% or more.
    In practice, change reports appear to route through doc type 350 rather
    than 370. Use raw_fields and text_blocks to explore any XBRL elements
    if a real filing is ever encountered.
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
        amended = ' [AMENDED]' if self.is_amendment else ''
        return f"LargeHoldingChangeReport(filer='{name}'{amended})"


def parse_large_holding_change(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> LargeHoldingChangeReport:
    """
    Parse a Large Shareholding Change Report filing (Doc 370/380).

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        LargeHoldingChangeReport with extracted DEI fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return LargeHoldingChangeReport(
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

    return LargeHoldingChangeReport(
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
