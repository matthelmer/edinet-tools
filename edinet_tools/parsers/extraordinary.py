"""
Parser for Extraordinary Reports (Doc Type 180).

Extracts event information and filer details from 臨時報告書 filings.
These are event-driven disclosures filed when significant corporate events occur.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
    parse_date,
)


# XBRL Element ID mappings for Doc 180 (Extraordinary Reports)
# Note: Doc 180 has TWO namespaces:
#   - jpsps-esr_cor: Fund reports
#   - jpcrp-esr_cor: Corporate reports
ELEMENT_MAP = {
    # === DEI Elements (Common) ===
    'edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'fund_code': 'jpdei_cor:FundCodeDEI',
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'fund_name': 'jpdei_cor:FundNameInJapaneseDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',

    # === Cover Page - Fund namespace ===
    'document_title_fund': 'jpsps-esr_cor:DocumentTitleCoverPage',
    'filing_date_fund': 'jpsps-esr_cor:FilingDateCoverPage',
    'issuer_name': 'jpsps-esr_cor:IssuerNameCoverPage',
    'representative_fund': 'jpsps-esr_cor:TitleAndNameOfRepresentativeCoverPage',
    'address_fund': 'jpsps-esr_cor:AddressOfRegisteredHeadquarterCoverPage',

    # === Cover Page - Corporate namespace ===
    'document_title_corp': 'jpcrp-esr_cor:DocumentTitleCoverPage',
    'filing_date_corp': 'jpcrp-esr_cor:FilingDateCoverPage',
    'company_name': 'jpcrp-esr_cor:CompanyNameCoverPage',
    'company_name_en': 'jpcrp-esr_cor:CompanyNameInEnglishCoverPage',
    'representative_corp': 'jpcrp-esr_cor:TitleAndNameOfRepresentativeCoverPage',
    'address_corp': 'jpcrp-esr_cor:AddressOfRegisteredHeadquarterCoverPage',

    # === Report Content - Fund namespace ===
    'reason_fund': 'jpsps-esr_cor:ReasonForFilingTextBlock',

    # === Report Content - Corporate namespace ===
    'reason_corp': 'jpcrp-esr_cor:ReasonForFilingTextBlock',
    'financial_impact': 'jpcrp-esr_cor:EventWithSignificantEffectsOnFinancialPositionBusinessPerformanceAndCashFlowsTextBlock',
    'shareholder_meeting': 'jpcrp-esr_cor:ResolutionOfShareholdersMeetingTextBlock',
    'major_shareholder_change': 'jpcrp-esr_cor:ChangesInMajorShareholderTextBlock',
}

# Event type detection keywords
EVENT_KEYWORDS = {
    'trust_termination': ['信託終了', '信託契約の終了', '繰上償還'],
    'merger': ['合併', '統合', '吸収合併'],
    'trust_change': ['信託約款', '約款変更', '運用方針の変更'],
    'dissolution': ['解散', '清算'],
    'material_change': ['重要な変更', '重要事項'],
}


@dataclass
class ExtraordinaryReport(ParsedReport):
    """Parsed Extraordinary Report (Doc 180)."""

    # Identification
    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    ticker: str | None = None
    fund_code: str | None = None
    fund_name: str | None = None

    # Cover page
    document_title: str | None = None
    filing_date: date | None = None
    representative: str | None = None
    address: str | None = None

    # Content
    reason_for_filing: str | None = None
    event_type: str | None = None  # Derived from reason text

    @property
    def is_fund(self) -> bool:
        """Check if this is a fund report (vs corporate)."""
        return bool(self.fund_code or self.fund_name)

    @property
    def filer(self):
        """Resolve filer to Entity if possible."""
        if self.filer_edinet_code:
            from edinet_tools.entity import entity_by_edinet_code
            return entity_by_edinet_code(self.filer_edinet_code)
        return None

    def __repr__(self) -> str:
        filer = self.filer_name or self.fund_name or 'Unknown'
        if len(filer) > 25:
            filer = filer[:22] + '...'
        event = self.event_type or 'unknown'
        return f"ExtraordinaryReport(filer='{filer}', event='{event}')"


def _classify_event_type(reason_text: Optional[str]) -> str:
    """Classify the event type based on reason for filing text."""
    if not reason_text:
        return 'unknown'

    for event_type, keywords in EVENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in reason_text:
                return event_type

    return 'other'


def parse_extraordinary_report(document) -> ExtraordinaryReport:
    """
    Parse an Extraordinary Report document.

    Args:
        document: Document object with fetch() method

    Returns:
        ExtraordinaryReport with extracted fields
    """
    zip_bytes = document.fetch()
    csv_files = extract_csv_from_zip(zip_bytes)

    if not csv_files:
        return ExtraordinaryReport(
            doc_id=document.doc_id,
            doc_type_code=document.doc_type_code,
            source_files=[],
            raw_fields={},
            unmapped_fields={},
            text_blocks={},
        )

    source_files = [f['filename'] for f in csv_files]

    # Helper to get value
    def get(key: str, context: list[str] | None = None) -> str | None:
        return extract_value(csv_files, ELEMENT_MAP.get(key, ''), context_patterns=context)

    # Extract DEI elements
    edinet_code = get('edinet_code', ['FilingDateInstant'])
    filer_name = get('filer_name', ['FilingDateInstant'])
    filer_name_en = get('filer_name_en', ['FilingDateInstant'])
    fund_code = get('fund_code', ['FilingDateInstant'])
    fund_name = get('fund_name', ['FilingDateInstant'])
    security_code = get('security_code', ['FilingDateInstant'])

    # Try cover page names if DEI filer name not found
    if not filer_name:
        filer_name = get('issuer_name') or get('company_name')

    # Format ticker
    ticker = None
    if security_code and security_code != '－':
        ticker = f"{security_code.strip()[:4]}.T"

    # Extract filing date - try both namespaces
    filing_date_str = get('filing_date_fund') or get('filing_date_corp')
    filing_date = parse_date(filing_date_str)

    # Extract document title - try both namespaces
    document_title = get('document_title_fund') or get('document_title_corp')

    # Extract representative - try both namespaces
    representative = get('representative_fund') or get('representative_corp')

    # Extract address - try both namespaces
    address = get('address_fund') or get('address_corp')

    # Extract reason for filing - try both namespaces
    reason_for_filing = get('reason_fund') or get('reason_corp')

    # Classify event type
    event_type = _classify_event_type(reason_for_filing)

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return ExtraordinaryReport(
        doc_id=document.doc_id,
        doc_type_code=document.doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,

        # Identification
        filer_name=filer_name or document.filer_name,
        filer_name_en=filer_name_en,
        filer_edinet_code=edinet_code or document.filer_edinet_code,
        ticker=ticker,
        fund_code=fund_code,
        fund_name=fund_name,

        # Cover page
        document_title=document_title,
        filing_date=filing_date,
        representative=representative,
        address=address,

        # Content
        reason_for_filing=reason_for_filing,
        event_type=event_type,
    )
