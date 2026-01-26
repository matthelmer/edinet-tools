"""
Parser for Semi-Annual Reports (Doc Type 160).

Extracts financial data from 半期報告書 filings.
Supports both corporate and fund reports with IFRS fallback.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
    parse_int,
    parse_date,
)


# XBRL Element ID mappings for Doc 160 (Semi-Annual Reports)
ELEMENT_MAP = {
    # === DEI Elements (Identification) ===
    'edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'fund_code': 'jpdei_cor:FundCodeDEI',
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'fund_name': 'jpdei_cor:FundNameInJapaneseDEI',
    'period_start': 'jpdei_cor:CurrentFiscalYearStartDateDEI',
    'period_end': 'jpdei_cor:CurrentPeriodEndDateDEI',
    'submission_date': 'jpdei_cor:DateOfSubmissionDEI',

    # === Balance Sheet Elements ===
    'assets': 'jppfs_cor:Assets',
    'current_assets': 'jppfs_cor:CurrentAssets',
    'liabilities': 'jppfs_cor:Liabilities',
    'current_liabilities': 'jppfs_cor:CurrentLiabilities',
    'net_assets': 'jppfs_cor:NetAssets',

    # === Income Statement ===
    'operating_income': 'jppfs_cor:OperatingIncome',
    'ordinary_income': 'jppfs_cor:OrdinaryIncome',
    'profit_loss': 'jppfs_cor:ProfitLoss',
}

# IFRS fallback elements
IFRS_FALLBACK_MAP = {
    'jppfs_cor:Assets': 'jpigp_cor:AssetsIFRS',
    'jppfs_cor:CurrentAssets': 'jpigp_cor:CurrentAssetsIFRS',
    'jppfs_cor:Liabilities': 'jpigp_cor:LiabilitiesIFRS',
    'jppfs_cor:CurrentLiabilities': 'jpigp_cor:CurrentLiabilitiesIFRS',
    'jppfs_cor:NetAssets': 'jpigp_cor:EquityIFRS',
    'jppfs_cor:OperatingIncome': 'jpigp_cor:OperatingProfitLossIFRS',
    'jppfs_cor:OrdinaryIncome': 'jpigp_cor:ProfitLossBeforeTaxIFRS',
    'jppfs_cor:ProfitLoss': 'jpigp_cor:ProfitLossIFRS',
}


@dataclass
class SemiAnnualReport(ParsedReport):
    """Parsed Semi-Annual Report (Doc 160)."""

    # Identification
    filer_name: str | None = None
    filer_edinet_code: str | None = None
    fund_code: str | None = None
    fund_name: str | None = None

    # Period
    period_start: date | None = None
    period_end: date | None = None
    filing_date: date | None = None

    # Balance Sheet
    total_assets: int | None = None
    current_assets: int | None = None
    total_liabilities: int | None = None
    current_liabilities: int | None = None
    net_assets: int | None = None

    # Income Statement
    operating_income: int | None = None
    ordinary_income: int | None = None
    profit_loss: int | None = None

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
        period = self.period_end.strftime('%Y-%m') if self.period_end else '?'
        return f"SemiAnnualReport(filer='{filer}', period_end={period})"


def _extract_financial(csv_files: list, element_id: str) -> Optional[int]:
    """Extract financial value with IFRS fallback."""
    value_str = extract_value(csv_files, element_id)
    if value_str:
        return parse_int(value_str)

    ifrs_element = IFRS_FALLBACK_MAP.get(element_id)
    if ifrs_element:
        value_str = extract_value(csv_files, ifrs_element)
        if value_str:
            return parse_int(value_str)

    return None


def parse_semi_annual_report(document) -> SemiAnnualReport:
    """
    Parse a Semi-Annual Report document.

    Args:
        document: Document object with fetch() method

    Returns:
        SemiAnnualReport with extracted fields
    """
    zip_bytes = document.fetch()
    csv_files = extract_csv_from_zip(zip_bytes)

    if not csv_files:
        return SemiAnnualReport(
            doc_id=document.doc_id,
            doc_type_code=document.doc_type_code,
            source_files=[],
            raw_fields={},
            unmapped_fields={},
            text_blocks={},
        )

    source_files = [f['filename'] for f in csv_files]

    # Helper to get DEI values
    def get_dei(key: str) -> str | None:
        return extract_value(csv_files, ELEMENT_MAP.get(key, ''), context_patterns=['FilingDateInstant'])

    # Extract DEI elements
    edinet_code = get_dei('edinet_code')
    filer_name = get_dei('filer_name')
    fund_code = get_dei('fund_code')
    fund_name = get_dei('fund_name')

    # Extract period
    period_start = parse_date(get_dei('period_start'))
    period_end = parse_date(get_dei('period_end'))
    filing_date = parse_date(get_dei('submission_date')) or period_end

    # Financial data
    total_assets = _extract_financial(csv_files, ELEMENT_MAP['assets'])
    current_assets = _extract_financial(csv_files, ELEMENT_MAP['current_assets'])
    total_liabilities = _extract_financial(csv_files, ELEMENT_MAP['liabilities'])
    current_liabilities = _extract_financial(csv_files, ELEMENT_MAP['current_liabilities'])
    net_assets = _extract_financial(csv_files, ELEMENT_MAP['net_assets'])
    operating_income = _extract_financial(csv_files, ELEMENT_MAP['operating_income'])
    ordinary_income = _extract_financial(csv_files, ELEMENT_MAP['ordinary_income'])
    profit_loss = _extract_financial(csv_files, ELEMENT_MAP['profit_loss'])

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return SemiAnnualReport(
        doc_id=document.doc_id,
        doc_type_code=document.doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,

        # Identification
        filer_name=filer_name or document.filer_name,
        filer_edinet_code=edinet_code or document.filer_edinet_code,
        fund_code=fund_code,
        fund_name=fund_name,

        # Period
        period_start=period_start,
        period_end=period_end,
        filing_date=filing_date,

        # Balance Sheet
        total_assets=total_assets,
        current_assets=current_assets,
        total_liabilities=total_liabilities,
        current_liabilities=current_liabilities,
        net_assets=net_assets,

        # Income Statement
        operating_income=operating_income,
        ordinary_income=ordinary_income,
        profit_loss=profit_loss,
    )
