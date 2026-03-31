"""
Parser for Tender Offer Withdrawal filings (Doc Type 260).

Extracts data from 公開買付撤回届出書 filings. These are filed when an
acquirer withdraws a previously announced tender offer before it closes.
Withdrawals require regulatory approval and disclosure of the reason.

Doc 260: Tender offer withdrawal notification
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
# Domain-specific elements (jptoo-twn_cor namespace) can be added once
# real Doc 260 filings have been inspected for their XBRL element names.
ELEMENT_MAP = {
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',
}


@dataclass
class TenderOfferWithdrawalReport(ParsedReport):
    """
    Parsed Tender Offer Withdrawal filing (Doc 260).

    Filed when an acquirer withdraws a tender offer. No confirmed filings
    exist in the database as of 2026-03, but the doc type is part of the
    standard EDINET tender offer family (240-340).

    Key fields:
        filer_name: Name of the acquirer withdrawing the offer
        filer_edinet_code: EDINET code of the acquirer
        security_code: Securities code of the target company
        is_amendment: Always False for Doc 260 (no amendment type exists)

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
        return f"TenderOfferWithdrawalReport(filer='{name}')"


def parse_tender_offer_withdrawal(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> TenderOfferWithdrawalReport:
    """
    Parse a Tender Offer Withdrawal filing (Doc 260).

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        TenderOfferWithdrawalReport with extracted DEI fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return TenderOfferWithdrawalReport(
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

    return TenderOfferWithdrawalReport(
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
