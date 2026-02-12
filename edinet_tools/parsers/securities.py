"""
Parser for Securities Reports (Doc Type 120).

Extracts financial data, share information, and business descriptions
from 有価証券報告書 filings.

PROCESSING PHILOSOPHY: Store raw XBRL values faithfully. No interpretation.
- Financial values in yen
- Ratios as decimals (0.086 = 8.6%)
- Downstream consumers determine meaning
"""
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from typing import Any, Optional

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
    get_context_patterns,
    extract_financial,
    parse_percentage,
    parse_int,
    parse_date,
)


# XBRL Element ID mappings for Doc 120 (Securities Reports)
# Validated against jpcrp_cor, jppfs_cor, jpdei_cor taxonomies
ELEMENT_MAP = {
    # === DEI Elements (Identification) ===
    'edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'company_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'company_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'fiscal_year_start': 'jpdei_cor:CurrentFiscalYearStartDateDEI',
    'fiscal_year_end': 'jpdei_cor:CurrentFiscalYearEndDateDEI',
    'accounting_standard': 'jpdei_cor:AccountingStandardsDEI',
    'is_consolidated': 'jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',

    # === SummaryOfBusinessResults Elements ===
    'net_sales_summary': 'jpcrp_cor:NetSalesSummaryOfBusinessResults',
    'ordinary_income_summary': 'jpcrp_cor:OrdinaryIncomeLossSummaryOfBusinessResults',
    'net_income_summary': 'jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults',
    'total_assets_summary': 'jpcrp_cor:TotalAssetsSummaryOfBusinessResults',
    'net_assets_summary': 'jpcrp_cor:NetAssetsSummaryOfBusinessResults',
    'net_assets_per_share': 'jpcrp_cor:NetAssetsPerShareSummaryOfBusinessResults',
    'earnings_per_share': 'jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
    'equity_ratio': 'jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults',
    'roe': 'jpcrp_cor:RateOfReturnOnEquitySummaryOfBusinessResults',
    'operating_cf_summary': 'jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults',
    'investing_cf_summary': 'jpcrp_cor:NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults',
    'financing_cf_summary': 'jpcrp_cor:NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults',

    # === Financial Statement Elements (Fallback) ===
    'net_sales_fs': 'jppfs_cor:NetSales',
    'operating_income_fs': 'jppfs_cor:OperatingIncome',
    'ordinary_income_fs': 'jppfs_cor:OrdinaryIncome',
    'net_income_fs': 'jppfs_cor:ProfitLoss',
    'total_assets_fs': 'jppfs_cor:Assets',
    'net_assets_fs': 'jppfs_cor:NetAssets',
    'total_liabilities_fs': 'jppfs_cor:Liabilities',

    # === Balance Sheet - Debt Details ===
    'short_term_loans_payable': 'jppfs_cor:ShortTermLoansPayable',
    'long_term_loans_payable': 'jppfs_cor:LongTermLoansPayable',
    'bonds_payable': 'jppfs_cor:BondsPayable',
    'current_portion_long_term_loans_payable': 'jppfs_cor:CurrentPortionOfLongTermLoansPayable',
    'lease_obligations_current': 'jppfs_cor:LeaseObligationsCL',
    'lease_obligations_noncurrent': 'jppfs_cor:LeaseObligationsNCL',
    'commercial_paper': 'jppfs_cor:CommercialPaper',

    # === Cash Flow Statement Elements (Fallback for companies without Summary section) ===
    'operating_cf_cfs': 'jpcrp_cor:CashFlowsFromOperatingActivities',
    'investing_cf_cfs': 'jpcrp_cor:CashFlowsFromInvestmentActivities',
    'financing_cf_cfs': 'jpcrp_cor:CashFlowsFromFinancingActivities',

    # === IFRS Cash Flow Elements (for IFRS companies like airlines) ===
    'operating_cf_ifrs_summary': 'jpcrp_cor:CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults',
    'investing_cf_ifrs_summary': 'jpcrp_cor:CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults',
    'financing_cf_ifrs_summary': 'jpcrp_cor:CashFlowsFromUsedInFinancingActivitiesIFRSSummaryOfBusinessResults',
    'operating_cf_ifrs': 'jpigp_cor:NetCashProvidedByUsedInOperatingActivitiesIFRS',
    'investing_cf_ifrs': 'jpigp_cor:NetCashProvidedByUsedInInvestingActivitiesIFRS',
    'financing_cf_ifrs': 'jpigp_cor:NetCashProvidedByUsedInFinancingActivitiesIFRS',

    # === Employment ===
    'num_employees': 'jpcrp_cor:NumberOfEmployees',
}

# IFRS fallback elements (jpigp_cor namespace)
IFRS_FALLBACK_MAP = {
    'jppfs_cor:NetSales': 'jpigp_cor:RevenueIFRS',
    'jppfs_cor:OperatingIncome': 'jpigp_cor:OperatingProfitLossIFRS',
    'jppfs_cor:OrdinaryIncome': 'jpigp_cor:ProfitLossBeforeTaxIFRS',
    'jppfs_cor:ProfitLoss': 'jpigp_cor:ProfitLossIFRS',
    'jppfs_cor:Assets': 'jpigp_cor:AssetsIFRS',
    'jppfs_cor:NetAssets': 'jpigp_cor:EquityIFRS',
    'jppfs_cor:Liabilities': 'jpigp_cor:LiabilitiesIFRS',
    # Debt elements
    'jppfs_cor:ShortTermLoansPayable': 'jpigp_cor:ShortTermBorrowingsIFRS',
    'jppfs_cor:LongTermLoansPayable': 'jpigp_cor:LongTermBorrowingsIFRS',
    'jppfs_cor:BondsPayable': 'jpigp_cor:BondsPayableIFRS',
}


@dataclass
class SecuritiesReport(ParsedReport):
    """Parsed Securities Report (Doc 120)."""

    # Identification
    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    ticker: str | None = None
    accounting_standard: str | None = None
    is_consolidated: bool | None = None

    # Period
    fiscal_year_start: date | None = None
    fiscal_year_end: date | None = None

    # Income Statement (Current Year)
    net_sales: int | None = None
    operating_income: int | None = None
    ordinary_income: int | None = None
    net_income: int | None = None

    # Income Statement (Prior Year)
    prior_net_sales: int | None = None
    prior_operating_income: int | None = None
    prior_ordinary_income: int | None = None
    prior_net_income: int | None = None

    # Balance Sheet
    total_assets: int | None = None
    net_assets: int | None = None
    total_liabilities: int | None = None

    # Balance Sheet - Debt Details
    short_term_loans_payable: int | None = None
    long_term_loans_payable: int | None = None
    bonds_payable: int | None = None
    current_portion_long_term_loans_payable: int | None = None
    lease_obligations_current: int | None = None
    lease_obligations_noncurrent: int | None = None
    commercial_paper: int | None = None

    # Cash Flow
    operating_cash_flow: int | None = None
    investing_cash_flow: int | None = None
    financing_cash_flow: int | None = None

    # Per-Share Metrics
    net_assets_per_share: Decimal | None = None
    earnings_per_share: Decimal | None = None

    # Ratios
    equity_ratio: Decimal | None = None
    roe: Decimal | None = None

    # Employment
    num_employees: int | None = None

    @property
    def filer(self):
        """Resolve filer to Entity if possible."""
        if self.filer_edinet_code:
            from edinet_tools.entity import entity_by_edinet_code
            return entity_by_edinet_code(self.filer_edinet_code)
        return None

    def __repr__(self) -> str:
        filer = self.filer_name or 'Unknown'
        if len(filer) > 25:
            filer = filer[:22] + '...'
        fy = self.fiscal_year_end.strftime('%Y-%m') if self.fiscal_year_end else '?'
        return f"SecuritiesReport(filer='{filer}', fy_end={fy})"


def _coalesce(*values):
    """Return the first non-None value."""
    for v in values:
        if v is not None:
            return v
    return None


def parse_securities_report(document) -> SecuritiesReport:
    """
    Parse a Securities Report document.

    Args:
        document: Document object with fetch() method

    Returns:
        SecuritiesReport with extracted fields
    """
    # Fetch and extract CSV data
    zip_bytes = document.fetch()
    csv_files = extract_csv_from_zip(zip_bytes)

    if not csv_files:
        return SecuritiesReport(
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
    company_name = get_dei('company_name')
    security_code = get_dei('security_code')
    accounting_standard = get_dei('accounting_standard')
    is_consolidated_raw = get_dei('is_consolidated')
    is_consolidated = is_consolidated_raw == 'true' if is_consolidated_raw else True

    # Format ticker
    ticker = None
    if security_code and security_code != '－':
        ticker = f"{security_code.strip()[:4]}.T"

    # Extract period
    fiscal_year_start = parse_date(get_dei('fiscal_year_start'))
    fiscal_year_end = parse_date(get_dei('fiscal_year_end'))

    # Helper for financial extraction
    def get_fin(key: str, period: str) -> int | None:
        element_id = ELEMENT_MAP.get(key, '')
        if not element_id:
            return None
        return extract_financial(csv_files, element_id, period, is_consolidated, IFRS_FALLBACK_MAP)

    # Try summary elements first, then fall back to FS elements
    net_sales = _coalesce(
        get_fin('net_sales_summary', 'CurrentYearDuration'),
        get_fin('net_sales_fs', 'CurrentYearDuration'),
    )
    operating_income = get_fin('operating_income_fs', 'CurrentYearDuration')
    ordinary_income = _coalesce(
        get_fin('ordinary_income_summary', 'CurrentYearDuration'),
        get_fin('ordinary_income_fs', 'CurrentYearDuration'),
    )
    net_income = _coalesce(
        get_fin('net_income_summary', 'CurrentYearDuration'),
        get_fin('net_income_fs', 'CurrentYearDuration'),
    )

    # Prior year
    prior_net_sales = _coalesce(
        get_fin('net_sales_summary', 'Prior1YearDuration'),
        get_fin('net_sales_fs', 'Prior1YearDuration'),
    )
    prior_operating_income = get_fin('operating_income_fs', 'Prior1YearDuration')
    prior_ordinary_income = _coalesce(
        get_fin('ordinary_income_summary', 'Prior1YearDuration'),
        get_fin('ordinary_income_fs', 'Prior1YearDuration'),
    )
    prior_net_income = _coalesce(
        get_fin('net_income_summary', 'Prior1YearDuration'),
        get_fin('net_income_fs', 'Prior1YearDuration'),
    )

    # Balance sheet
    total_assets = _coalesce(
        get_fin('total_assets_summary', 'CurrentYearInstant'),
        get_fin('total_assets_fs', 'CurrentYearInstant'),
    )
    net_assets = _coalesce(
        get_fin('net_assets_summary', 'CurrentYearInstant'),
        get_fin('net_assets_fs', 'CurrentYearInstant'),
    )
    total_liabilities = get_fin('total_liabilities_fs', 'CurrentYearInstant')

    # Debt details
    short_term_loans_payable = get_fin('short_term_loans_payable', 'CurrentYearInstant')
    long_term_loans_payable = get_fin('long_term_loans_payable', 'CurrentYearInstant')
    bonds_payable = get_fin('bonds_payable', 'CurrentYearInstant')
    current_portion_ltd = get_fin('current_portion_long_term_loans_payable', 'CurrentYearInstant')
    lease_obligations_current = get_fin('lease_obligations_current', 'CurrentYearInstant')
    lease_obligations_noncurrent = get_fin('lease_obligations_noncurrent', 'CurrentYearInstant')
    commercial_paper = get_fin('commercial_paper', 'CurrentYearInstant')

    # Cash flow - Multi-tier fallback:
    # 1. Japan GAAP Summary (jpcrp_cor)
    # 2. IFRS Summary (jpcrp_cor with IFRS suffix)
    # 3. Japan GAAP detailed statement (jppfs_cor)
    # 4. IFRS detailed statement (jpigp_cor)
    operating_cf = _coalesce(
        get_fin('operating_cf_summary', 'CurrentYearDuration'),
        get_fin('operating_cf_ifrs_summary', 'CurrentYearDuration'),
        get_fin('operating_cf_cfs', 'CurrentYearDuration'),
        get_fin('operating_cf_ifrs', 'CurrentYearDuration'),
    )

    investing_cf = _coalesce(
        get_fin('investing_cf_summary', 'CurrentYearDuration'),
        get_fin('investing_cf_ifrs_summary', 'CurrentYearDuration'),
        get_fin('investing_cf_cfs', 'CurrentYearDuration'),
        get_fin('investing_cf_ifrs', 'CurrentYearDuration'),
    )

    financing_cf = _coalesce(
        get_fin('financing_cf_summary', 'CurrentYearDuration'),
        get_fin('financing_cf_ifrs_summary', 'CurrentYearDuration'),
        get_fin('financing_cf_cfs', 'CurrentYearDuration'),
        get_fin('financing_cf_ifrs', 'CurrentYearDuration'),
    )

    # Per-share metrics
    patterns = get_context_patterns(is_consolidated, 'CurrentYearInstant')
    nav_str = extract_value(csv_files, ELEMENT_MAP['net_assets_per_share'], context_patterns=patterns)
    net_assets_per_share = Decimal(nav_str) if nav_str else None

    patterns = get_context_patterns(is_consolidated, 'CurrentYearDuration')
    eps_str = extract_value(csv_files, ELEMENT_MAP['earnings_per_share'], context_patterns=patterns)
    earnings_per_share = Decimal(eps_str) if eps_str else None

    # Ratios
    patterns = get_context_patterns(is_consolidated, 'CurrentYearInstant')
    equity_str = extract_value(csv_files, ELEMENT_MAP['equity_ratio'], context_patterns=patterns)
    equity_ratio = parse_percentage(equity_str)

    patterns = get_context_patterns(is_consolidated, 'CurrentYearDuration')
    roe_str = extract_value(csv_files, ELEMENT_MAP['roe'], context_patterns=patterns)
    roe = parse_percentage(roe_str)

    # Employment
    num_employees = get_fin('num_employees', 'CurrentYearInstant')

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return SecuritiesReport(
        doc_id=document.doc_id,
        doc_type_code=document.doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,

        # Identification
        filer_name=company_name or document.filer_name,
        filer_name_en=get_dei('company_name_en'),
        filer_edinet_code=edinet_code or document.filer_edinet_code,
        ticker=ticker,
        accounting_standard=accounting_standard,
        is_consolidated=is_consolidated,

        # Period
        fiscal_year_start=fiscal_year_start,
        fiscal_year_end=fiscal_year_end,

        # Income Statement (Current)
        net_sales=net_sales,
        operating_income=operating_income,
        ordinary_income=ordinary_income,
        net_income=net_income,

        # Income Statement (Prior)
        prior_net_sales=prior_net_sales,
        prior_operating_income=prior_operating_income,
        prior_ordinary_income=prior_ordinary_income,
        prior_net_income=prior_net_income,

        # Balance Sheet
        total_assets=total_assets,
        net_assets=net_assets,
        total_liabilities=total_liabilities,

        # Balance Sheet - Debt Details
        short_term_loans_payable=short_term_loans_payable,
        long_term_loans_payable=long_term_loans_payable,
        bonds_payable=bonds_payable,
        current_portion_long_term_loans_payable=current_portion_ltd,
        lease_obligations_current=lease_obligations_current,
        lease_obligations_noncurrent=lease_obligations_noncurrent,
        commercial_paper=commercial_paper,

        # Cash Flow
        operating_cash_flow=operating_cf,
        investing_cash_flow=investing_cf,
        financing_cash_flow=financing_cf,

        # Per-Share
        net_assets_per_share=net_assets_per_share,
        earnings_per_share=earnings_per_share,

        # Ratios
        equity_ratio=equity_ratio,
        roe=roe,

        # Employment
        num_employees=num_employees,
    )
