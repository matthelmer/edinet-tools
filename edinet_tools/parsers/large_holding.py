"""
Parser for Large Shareholding Reports (Doc Type 350).

Extracts ownership information, filer details, and target company data
from 大量保有報告書 filings.

PROCESSING PHILOSOPHY: Store raw XBRL values faithfully. No interpretation.
- Percentages stored as decimals (0.0967 = 9.67%)
- Text fields stored as-is
- Downstream consumers determine meaning
"""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from typing import Any

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
    parse_percentage,
    parse_int,
    parse_date,
)


# XBRL Element ID mappings for Doc 350 (Large Holding Reports)
# Validated against jplvh_cor taxonomy
ELEMENT_MAP = {
    # Report Type
    'report_indication': 'jplvh_cor:DocumentTitleCoverPage',

    # Filer Information
    'filer_edinet_code': 'jplvh_cor:EDINETCodeDEI',
    'filer_name_alt1': 'jplvh_cor:Name',
    'filer_name_alt2': 'jplvh_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jplvh_cor:FilerNameInEnglishDEI',
    'filer_address': 'jplvh_cor:ResidentialAddressOrAddressOfRegisteredHeadquarter',
    'filer_business': 'jplvh_cor:DescriptionOfBusiness',
    'filer_type': 'jplvh_cor:IndividualOrCorporation',

    # Target Company
    'target_company': 'jplvh_cor:NameOfIssuer',
    'target_ticker': 'jplvh_cor:SecurityCodeOfIssuer',

    # Ownership Data
    'shares_held': 'jplvh_cor:TotalNumberOfStocksEtcHeld',
    'ownership_pct': 'jplvh_cor:HoldingRatioOfShareCertificatesEtc',
    'prior_ownership_pct': 'jplvh_cor:HoldingRatioOfShareCertificatesEtcPerLastReport',
    'shares_outstanding': 'jplvh_cor:TotalNumberOfOutstandingStocksEtc',

    # Purpose & Intent
    'purpose': 'jplvh_cor:PurposeOfHolding',
    'important_proposal': 'jplvh_cor:ActOfMakingImportantProposalEtc',

    # Change Context
    'change_reason': 'jplvh_cor:ReasonForFilingChangeReportCoverPage',

    # Dates
    'filing_date': 'jplvh_cor:FilingDateCoverPage',
    'trigger_date': 'jplvh_cor:DateWhenFilingRequirementAroseCoverPage',
    'base_date': 'jplvh_cor:BaseDate',

    # Funding
    'acquisition_fund_own': 'jplvh_cor:AmountOfOwnFund',
    'acquisition_fund_borrowing': 'jplvh_cor:TotalAmountOfBorrowings',
    'acquisition_fund_other': 'jplvh_cor:TotalAmountFromOtherSources',
    'acquisition_fund_total': 'jplvh_cor:TotalAmountOfFundingForAcquisition',
}


@dataclass
class LargeHoldingReport(ParsedReport):
    """Parsed Large Shareholding Report (Doc 350)."""

    # Report context
    report_indication: str | None = None
    change_reason: str | None = None

    # Filer (who's reporting)
    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    filer_address: str | None = None
    filer_type: str | None = None  # "法人" or "個人"
    filer_business: str | None = None

    # Target (company being held)
    target_company: str | None = None
    target_ticker: str | None = None

    # Ownership
    shares_held: int | None = None
    ownership_pct: Decimal | None = None
    prior_ownership_pct: Decimal | None = None
    ownership_change: Decimal | None = None
    shares_outstanding: int | None = None

    # Intent (raw text, no interpretation)
    purpose: str | None = None
    important_proposal: str | None = None

    # Dates
    filing_date: date | None = None
    trigger_date: date | None = None
    base_date: date | None = None

    # Funding
    acquisition_fund_own: int | None = None
    acquisition_fund_borrowing: int | None = None
    acquisition_fund_other: int | None = None
    acquisition_fund_total: int | None = None

    @property
    def filer(self):
        """Resolve filer to Entity if possible."""
        if self.filer_edinet_code:
            from edinet_tools.entity import entity_by_edinet_code
            return entity_by_edinet_code(self.filer_edinet_code)
        return None

    @property
    def target(self):
        """Resolve target to Entity if possible."""
        if self.target_ticker:
            from edinet_tools.entity import entity_by_ticker
            # Strip .T suffix if present for lookup
            ticker = self.target_ticker.replace('.T', '')[:4]
            return entity_by_ticker(ticker)
        return None

    @property
    def ownership_percentage(self) -> float | None:
        """Ownership as a percentage (e.g., 9.67 for 9.67%)."""
        if self.ownership_pct is not None:
            return float(self.ownership_pct * 100)
        return None

    def __repr__(self) -> str:
        filer = self.filer_name or 'Unknown'
        if len(filer) > 20:
            filer = filer[:17] + '...'
        target = self.target_company or 'Unknown'
        if len(target) > 20:
            target = target[:17] + '...'
        if self.ownership_pct is not None:
            pct = f'{float(self.ownership_pct * 100):.2f}%'
        else:
            pct = '?%'
        return f"LargeHoldingReport(filer='{filer}', target='{target}', ownership={pct})"


def parse_large_holding(document) -> LargeHoldingReport:
    """
    Parse a Large Shareholding Report document.

    Args:
        document: Document object with fetch() method

    Returns:
        LargeHoldingReport with extracted fields
    """
    # Fetch and extract CSV data
    zip_bytes = document.fetch()
    csv_files = extract_csv_from_zip(zip_bytes)

    if not csv_files:
        # Return minimal report if extraction failed
        return LargeHoldingReport(
            doc_id=document.doc_id,
            doc_type_code=document.doc_type_code,
            source_files=[],
            raw_fields={},
            unmapped_fields={},
            text_blocks={},
        )

    # Get source filenames
    source_files = [f['filename'] for f in csv_files]

    # Extract values using element map
    def get(key: str, last: bool = False) -> str | None:
        return extract_value(csv_files, ELEMENT_MAP.get(key, ''), get_last=last)

    # Filer name (try multiple element IDs)
    filer_name = get('filer_name_alt1') or get('filer_name_alt2') or document.filer_name

    # Target ticker (normalize to 4-digit + .T format)
    target_ticker_raw = get('target_ticker')
    target_ticker = None
    if target_ticker_raw:
        ticker_digits = target_ticker_raw.strip()[:4]
        target_ticker = f"{ticker_digits}.T"

    # Ownership percentages (get last occurrence for joint filings)
    ownership_pct = parse_percentage(get('ownership_pct', last=True))
    prior_ownership_pct = parse_percentage(get('prior_ownership_pct'))

    # Calculate ownership change
    ownership_change = None
    if ownership_pct is not None and prior_ownership_pct is not None:
        ownership_change = ownership_pct - prior_ownership_pct

    # Dates
    filing_date = parse_date(get('filing_date'))
    if not filing_date and document.filing_datetime:
        filing_date = document.filing_datetime.date()

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return LargeHoldingReport(
        doc_id=document.doc_id,
        doc_type_code=document.doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,

        # Report context
        report_indication=get('report_indication'),
        change_reason=get('change_reason'),

        # Filer
        filer_name=filer_name,
        filer_name_en=get('filer_name_en'),
        filer_edinet_code=get('filer_edinet_code') or document.filer_edinet_code,
        filer_address=get('filer_address'),
        filer_type=get('filer_type'),
        filer_business=get('filer_business'),

        # Target
        target_company=get('target_company'),
        target_ticker=target_ticker,

        # Ownership
        shares_held=parse_int(get('shares_held', last=True)),
        ownership_pct=ownership_pct,
        prior_ownership_pct=prior_ownership_pct,
        ownership_change=ownership_change,
        shares_outstanding=parse_int(get('shares_outstanding')),

        # Purpose & Intent
        purpose=get('purpose'),
        important_proposal=get('important_proposal'),

        # Dates
        filing_date=filing_date,
        trigger_date=parse_date(get('trigger_date')),
        base_date=parse_date(get('base_date')),

        # Funding
        acquisition_fund_own=parse_int(get('acquisition_fund_own')),
        acquisition_fund_borrowing=parse_int(get('acquisition_fund_borrowing')),
        acquisition_fund_other=parse_int(get('acquisition_fund_other')),
        acquisition_fund_total=parse_int(get('acquisition_fund_total')),
    )
