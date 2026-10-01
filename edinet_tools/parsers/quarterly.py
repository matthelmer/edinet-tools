"""
Parser for Quarterly Reports (Doc Type 140).

Extracts quarterly financial data from 四半期報告書 filings.

IMPORTANT: Income statement data is year-to-date cumulative, not quarterly-only.
- Q1 report: First 3 months of fiscal year
- Q2 report: First 6 months (cumulative)
- Q3 report: First 9 months (cumulative)
"""
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, timedelta
from typing import Any, Optional

from . import securities as _securities
from ._standard_policy import (
    IFRS,
    JGAAP,
    USGAAP,
    FieldPolicy,
    close_legacy,
    own_standard_stage,
    with_own_standard_first,
)
from .base import ParsedReport
from .extraction import (
    Tier,
    resolve_tiers,
    get_dei,
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
    parse_percentage,
    parse_date,
)


# XBRL Element ID mappings for Doc 140 (Quarterly Reports)
ELEMENT_MAP = {
    # === DEI Elements (Identification) ===
    'edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'company_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'fiscal_year_end': 'jpdei_cor:CurrentFiscalYearEndDateDEI',
    'filing_date': 'jpcrp_cor:FilingDateCoverPage',
    'is_consolidated': 'jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',

    # === Income Statement Elements (YTD Cumulative) ===
    'net_sales': 'jppfs_cor:NetSales',
    'operating_income': 'jppfs_cor:OperatingIncome',
    'ordinary_income': 'jppfs_cor:OrdinaryIncome',
    'net_income': 'jppfs_cor:ProfitLossAttributableToOwnersOfParent',

    # === Balance Sheet Elements (Point-in-Time) ===
    'total_assets': 'jppfs_cor:Assets',
    'net_assets': 'jppfs_cor:NetAssets',
    'total_liabilities': 'jppfs_cor:Liabilities',

    # === Cash Flow Elements (YTD Cumulative) ===
    'operating_cf': 'jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults',
    'investing_cf': 'jpcrp_cor:NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults',
    'financing_cf': 'jpcrp_cor:NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults',

    # === Per Share Metrics ===
    'eps_basic': 'jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',

    # === Key Ratios ===
    'equity_ratio': 'jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults',
}

# Read beside ELEMENT_MAP, not in it: an ELEMENT_MAP element leaves
# unmapped_fields, and this DEI fact has always been there.
_ACCOUNTING_STANDARD_DEI = 'jpdei_cor:AccountingStandardsDEI'

# IFRS fallback elements
IFRS_FALLBACK_MAP = {
    'jppfs_cor:NetSales': 'jpigp_cor:RevenueIFRS',
    'jppfs_cor:OperatingIncome': 'jpigp_cor:OperatingProfitLossIFRS',
    'jppfs_cor:ProfitLossAttributableToOwnersOfParent': 'jpigp_cor:ProfitLossAttributableToOwnersOfParentIFRS',
    'jppfs_cor:Assets': 'jpigp_cor:AssetsIFRS',
    'jppfs_cor:NetAssets': 'jpigp_cor:EquityIFRS',
    'jppfs_cor:Liabilities': 'jpigp_cor:LiabilitiesIFRS',
}


def _chain(key: str):
    """ELEMENT_MAP[key] plus its IFRS_FALLBACK_MAP fallback as ONE tier's
    element chain (extract_financial's primary-plus-fallback, declarative)."""
    element_id = ELEMENT_MAP[key]
    fallback = IFRS_FALLBACK_MAP.get(element_id)
    if not fallback:
        return element_id
    return (element_id, fallback)


# ---------------------------------------------------------------------------
# Standard-selection policy (see _standard_policy for the contract)
#
# Every financial field reads the filing's declared standard first
# (AccountingStandardsDEI): one stage per standard at the head of the field's
# table, built from the legacy table's elements of that standard. A missing
# own fact follows the field's declared fallback: 'legacy' serves the legacy
# table; 'none' closes it to that standard. IFRS and US-GAAP filers never read
# the J-GAAP operating or ordinary profit (no fallback to another standard's
# figure), and owners' equity is never read for a J-GAAP filer (J-GAAP states
# no owners-only figure).
#
# The legacy tables: each field's 0.8 tier (one element with at most one IFRS
# fallback), unchanged, plus the other standards' elements as tiers scoped to
# their own standard. A scoped tier never serves a filing of another standard,
# nor one that declares none, so the legacy order for a J-GAAP or undeclared
# filing is the 0.8 tier. The 0.8 tier comes first, so its own-standard
# element keeps its place in the own stage: a value 0.8 already read on the
# declared standard does not move (a filing whose highlights table and
# statements disagree keeps the statements' figure). Periods are unchanged:
# duration fields read CurrentYTDDuration (and the prior_ fields
# Prior1YTDDuration), instant fields CurrentQuarterInstant; the context rule
# is get_context_patterns.
# ---------------------------------------------------------------------------

_C, _G, _J = 'jpcrp_cor:', 'jpigp_cor:', 'jppfs_cor:'
_SB = 'SummaryOfBusinessResults'
_JG, _IFRS, _US = JGAAP, IFRS, USGAAP


def _own(element, standard):
    return Tier(element, standards=(standard,))


# Custom-namespace consolidated IFRS revenue / operating profit (filer-local
# elements); bare period only, so a parent figure can never win.
_REVENUE_SUFFIX = Tier(('SalesRevenuesIFRS', 'TotalNetRevenuesIFRS', 'RevenueIFRS' + _SB),
                       standards=(_IFRS,), suffix_match=True)
_OPERATING_SUFFIX = Tier(('OperatingProfitLossIFRS' + _SB, 'OperatingIncomeIFRS' + _SB,
                          'OperatingIncomeLossIFRS' + _SB, 'OperatingProfitIFRS' + _SB),
                         standards=(_IFRS,), suffix_match=True)


def _cash_flow_legacy(key, kind):
    return (
        Tier(_chain(key)),
        _own(_C + f'CashFlowsFromUsedIn{kind}ActivitiesIFRS' + _SB, _IFRS),
        _own(_G + f'NetCashProvidedByUsedIn{kind}ActivitiesIFRS', _IFRS),
        _own(_C + f'CashFlowsFromUsedIn{kind}ActivitiesUSGAAP' + _SB, _US),
    )


_YTD_LEGACY = {
    'revenue_ytd': (
        Tier(_chain('net_sales')),
        _own(_C + 'RevenueIFRS' + _SB, _IFRS),
        _own(_C + 'RevenuesUSGAAP' + _SB, _US),
        _own((_G + 'Revenue2IFRS', _G + 'NetSalesIFRS'), _IFRS),
        _REVENUE_SUFFIX,
    ),
    'operating_profit_ytd': (
        Tier(_chain('operating_income')),
        _own(_C + 'OperatingProfitLossIFRS' + _SB, _IFRS),
        _own(_C + 'OperatingIncomeLossUSGAAP' + _SB, _US),
        _OPERATING_SUFFIX,
    ),
    'ordinary_profit_ytd': (Tier(_chain('ordinary_income')),),
    'net_income_ytd': (
        Tier(_chain('net_income')),
        _own(_C + 'ProfitLossAttributableToOwnersOfParentIFRS' + _SB, _IFRS),
        _own(_C + 'NetIncomeLossAttributableToOwnersOfParentUSGAAP' + _SB, _US),
    ),
}
# Current period only (no prior_ read).
_YTD_CURRENT_LEGACY = {
    'profit_before_tax': _securities._PROFIT_BEFORE_TAX_LEGACY,
}
_CF_LEGACY = {
    'operating_cash_flow_ytd': _cash_flow_legacy('operating_cf', 'Operating'),
    'investing_cash_flow_ytd': _cash_flow_legacy('investing_cf', 'Investing'),
    'financing_cash_flow_ytd': _cash_flow_legacy('financing_cf', 'Financing'),
}
_INSTANT_LEGACY = {
    'total_assets': (
        Tier(_chain('total_assets')),
        _own(_C + 'TotalAssetsIFRS' + _SB, _IFRS),
        _own(_C + 'TotalAssetsUSGAAP' + _SB, _US),
    ),
    'net_assets': (
        Tier(_chain('net_assets')),
        _own(_C + 'EquityIncludingPortionAttributableToNonControllingInterestUSGAAP' + _SB, _US),
    ),
    'net_assets_owners': _securities._INSTANT_LEGACY['net_assets_owners'],
    'total_liabilities': (Tier(_chain('total_liabilities')),),
}
# Per-share and ratio ('string' mode; the caller parses). EPS keeps its
# null-marker skipping (coerce); the equity ratio keeps its legacy
# first-non-empty-raw-string read (a marker parses to None). The IFRS ratio
# element is the real ratio, never EquityToAssetRatioIFRS... (per-share
# equity in yen, a taxonomy misnomer).
_EPS_LEGACY = (
    Tier(ELEMENT_MAP['eps_basic']),
    _own(_C + 'BasicEarningsLossPerShareIFRS' + _SB, _IFRS),
    _own(_C + 'BasicEarningsLossPerShareUSGAAP' + _SB, _US),
)
_EQUITY_RATIO_LEGACY = (
    Tier(ELEMENT_MAP['equity_ratio']),
    _own(_C + 'RatioOfOwnersEquityToGrossAssetsIFRS' + _SB, _IFRS),
    _own(_C + 'EquityToAssetRatioUSGAAP' + _SB, _US),
)

_LEGACY_TABLES = {
    **{name: (t,) for name, t in _YTD_LEGACY.items()},
    **{name: (t,) for name, t in _YTD_CURRENT_LEGACY.items()},
    **{name: (t,) for name, t in _CF_LEGACY.items()},
    **{name: (t,) for name, t in _INSTANT_LEGACY.items()},
    'eps_basic_ytd': (_EPS_LEGACY,),
    'equity_ratio': (_EQUITY_RATIO_LEGACY,),
}

_ALL = (_JG, _IFRS, _US)
_LEGACY = 'legacy'
# IFRS and US-GAAP filers never read the J-GAAP figure (the 0.7.1 gate).
_JGAAP_ONLY_FALLBACK = {_JG: 'legacy', _IFRS: 'none', _US: 'none'}

_STANDARD_POLICY = {
    'revenue_ytd': FieldPolicy('Revenue: net sales / IFRS revenue / US-GAAP revenues '
                               '(year to date)', _ALL, _LEGACY),
    'operating_profit_ytd': FieldPolicy('Operating profit (year to date); no J-GAAP '
                                        'figure for IFRS or US-GAAP filers', _ALL,
                                        _JGAAP_ONLY_FALLBACK),
    'ordinary_profit_ytd': FieldPolicy('Ordinary profit (J-GAAP only; blank for IFRS and '
                                       'US-GAAP filers)', (_JG,),
                                       {_JG: 'n/a', _IFRS: 'none', _US: 'none'}),
    'net_income_ytd': FieldPolicy('Profit attributable to owners of parent (year to date)',
                                  _ALL, _LEGACY),
    'profit_before_tax': FieldPolicy('Profit before income taxes (year to date)', _ALL,
                                     'none'),
    'total_assets': FieldPolicy('Total assets', _ALL, _LEGACY),
    'net_assets': FieldPolicy('Net assets / total equity including non-controlling '
                              'interests', _ALL, _LEGACY),
    'net_assets_owners': FieldPolicy('Equity attributable to owners of parent (no J-GAAP '
                                     'element)', (_IFRS, _US),
                                     {s: 'none' for s in _ALL}),
    'total_liabilities': FieldPolicy('Total liabilities (FS)', (_JG, _IFRS), _LEGACY),
    'operating_cash_flow_ytd': FieldPolicy('Cash flows from operating activities', _ALL,
                                           _LEGACY),
    'investing_cash_flow_ytd': FieldPolicy('Cash flows from investing activities', _ALL,
                                           _LEGACY),
    'financing_cash_flow_ytd': FieldPolicy('Cash flows from financing activities', _ALL,
                                           _LEGACY),
    'eps_basic_ytd': FieldPolicy('Basic earnings per share (year to date)', _ALL, _LEGACY),
    'equity_ratio': FieldPolicy('Equity-to-assets ratio (owners basis)', _ALL, _LEGACY),
}


def _resolved(tables):
    return {name: with_own_standard_first(t, _STANDARD_POLICY[name]) for name, t in tables.items()}


# Resolved tables: own-standard stage, then the legacy table (closed where the
# fallback is 'none').
_YTD_TIERS = _resolved(_YTD_LEGACY)
_YTD_CURRENT_TIERS = _resolved(_YTD_CURRENT_LEGACY)
_CF_TIERS = _resolved(_CF_LEGACY)
_INSTANT_TIERS = _resolved(_INSTANT_LEGACY)
# Per-share and ratio: the own stage is resolved with coerce semantics (a
# marker-valued own fact falls through), then the legacy scan.
_EPS_OWN = own_standard_stage(_EPS_LEGACY, _STANDARD_POLICY['eps_basic_ytd'])
_EPS_REST = close_legacy(_EPS_LEGACY, _STANDARD_POLICY['eps_basic_ytd'])
_EQUITY_RATIO_OWN = own_standard_stage(_EQUITY_RATIO_LEGACY, _STANDARD_POLICY['equity_ratio'])
_EQUITY_RATIO_REST = close_legacy(_EQUITY_RATIO_LEGACY, _STANDARD_POLICY['equity_ratio'])


@dataclass
class QuarterlyReport(ParsedReport):
    """Parsed Quarterly Report (Doc 140)."""

    # Identification
    filer_name: str | None = None
    filer_edinet_code: str | None = None
    ticker: str | None = None
    # AccountingStandardsDEI as declared ('Japan GAAP', 'IFRS', 'US GAAP'),
    # whitespace-stripped; None when the filing declares none.
    accounting_standard: str | None = None
    is_consolidated: bool | None = None

    # Period
    fiscal_year_end: date | None = None
    quarter_number: int | None = None  # 1, 2, or 3
    filing_date: date | None = None

    # Income Statement (Current YTD)
    revenue_ytd: int | None = None
    operating_profit_ytd: int | None = None
    ordinary_profit_ytd: int | None = None
    net_income_ytd: int | None = None
    # Profit before income taxes (total basis, pre-tax): J-GAAP
    # 税金等調整前四半期純利益, IFRS / US-GAAP profit before tax. A filing that
    # declares a standard reads that standard's figure only (honest None when
    # it does not tag it); a filing that declares none reads the legacy order
    # (J-GAAP FS, IFRS highlights then FS, US-GAAP highlights).
    profit_before_tax: int | None = None

    # Income Statement (Prior Year YTD)
    prior_revenue_ytd: int | None = None
    prior_operating_profit_ytd: int | None = None
    prior_ordinary_profit_ytd: int | None = None
    prior_net_income_ytd: int | None = None

    # Balance Sheet
    total_assets: int | None = None
    net_assets: int | None = None
    # Equity attributable to owners of parent (IFRS / US GAAP). None for
    # J-GAAP filers by design: J-GAAP states no owners-only figure.
    net_assets_owners: int | None = None
    total_liabilities: int | None = None

    # Cash Flow
    operating_cash_flow_ytd: int | None = None
    investing_cash_flow_ytd: int | None = None
    financing_cash_flow_ytd: int | None = None

    # Per-Share
    eps_basic_ytd: Decimal | None = None

    # Ratios
    equity_ratio: Decimal | None = None

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
        q = f"Q{self.quarter_number}" if self.quarter_number else 'Q?'
        fy = self.fiscal_year_end.year if self.fiscal_year_end else '?'
        return f"QuarterlyReport(filer='{filer}', {q} FY{fy})"


def _decimal_or_none(value):
    try:
        return Decimal(value)
    except ArithmeticError:
        return None


def _derive_quarter_number(filing_date: date, fiscal_year_end: date) -> Optional[int]:
    """
    Derive quarter number (1, 2, or 3) from filing date and fiscal year end.

    Japanese companies typically file quarterly reports 45 days after quarter end.
    For a March fiscal year end (common in Japan):
        - Q1 (Apr-Jun): Filed Jul-Aug, 3-5 months from FY start
        - Q2 (Jul-Sep): Filed Oct-Nov, 6-8 months from FY start
        - Q3 (Oct-Dec): Filed Jan-Feb, 9-11 months from FY start

    Returns None if filing date doesn't match expected quarterly timing
    (e.g., annual reports filed after fiscal year end).
    """
    # Calculate fiscal year start (day after prior year end).
    # Subtract one year, keeping month/day; Feb 29 clamps to Feb 28 when the
    # prior year isn't a leap year (date.replace raises ValueError there),
    # matching dateutil.relativedelta's default clamping behavior. date +
    # timedelta(days=1) handles month/year rollover for the "+1 day" step
    # without needing a calendar-aware library.
    try:
        prior_year_end = fiscal_year_end.replace(year=fiscal_year_end.year - 1)
    except ValueError:
        prior_year_end = fiscal_year_end.replace(year=fiscal_year_end.year - 1, day=28)
    fiscal_year_start = prior_year_end + timedelta(days=1)

    # Calculate months from fiscal year start to filing date
    months_from_start = (filing_date.year - fiscal_year_start.year) * 12 + \
                       (filing_date.month - fiscal_year_start.month)

    # Map to quarter (filing typically happens 1-2 months after quarter end)
    if 3 <= months_from_start <= 5:
        return 1
    elif 6 <= months_from_start <= 8:
        return 2
    elif 9 <= months_from_start <= 11:
        return 3
    else:
        return None


def parse_quarterly_report(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> QuarterlyReport:
    """
    Parse a Quarterly Report document.

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        QuarterlyReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return QuarterlyReport(
            doc_id=doc_id,
            doc_type_code=doc_type_code,
            source_files=[],
            raw_fields={},
            unmapped_fields={},
            text_blocks={},
        )

    source_files = [f['filename'] for f in csv_files]

    # Extract DEI elements
    edinet_code = get_dei(csv_files, ELEMENT_MAP, 'edinet_code')
    company_name = get_dei(csv_files, ELEMENT_MAP, 'company_name')
    security_code = get_dei(csv_files, ELEMENT_MAP, 'security_code')
    is_consolidated_raw = get_dei(csv_files, ELEMENT_MAP, 'is_consolidated')
    is_consolidated = (is_consolidated_raw == 'true') if is_consolidated_raw else None
    # Whitespace-stripped: some filings tag the DEI value with trailing tabs.
    standard_raw = extract_value(csv_files, _ACCOUNTING_STANDARD_DEI,
                                 context_patterns=['FilingDateInstant'])
    accounting_standard = (standard_raw.strip() or None) if standard_raw else None

    # Format ticker
    ticker = None
    if security_code and security_code != '－':
        ticker = f"{security_code.strip()[:4]}.T"

    # Extract period
    fiscal_year_end = parse_date(get_dei(csv_files, ELEMENT_MAP, 'fiscal_year_end'))
    filing_date_str = extract_value(csv_files, ELEMENT_MAP['filing_date'])
    filing_date = parse_date(filing_date_str)

    # Derive quarter number
    quarter_number = None
    if filing_date and fiscal_year_end:
        quarter_number = _derive_quarter_number(filing_date, fiscal_year_end)

    # Financials: every field reads the declared standard first (see the
    # policy above); source_elements / source_contexts record the element and
    # context of every value.
    sources, contexts = {}, {}

    def fin(name, tiers, period):
        hit = resolve_tiers(csv_files, tiers, standard=accounting_standard, period=period,
                            is_consolidated=is_consolidated)
        if hit is None:
            return None
        sources[name], contexts[name] = hit.element_id, hit.context_id
        return hit.value

    fields = {}
    for name, tiers in _YTD_TIERS.items():
        fields[name] = fin(name, tiers, 'CurrentYTDDuration')
        fields[f'prior_{name}'] = fin(f'prior_{name}', tiers, 'Prior1YTDDuration')
    for name, tiers in {**_YTD_CURRENT_TIERS, **_CF_TIERS}.items():
        fields[name] = fin(name, tiers, 'CurrentYTDDuration')
    for name, tiers in _INSTANT_TIERS.items():
        fields[name] = fin(name, tiers, 'CurrentQuarterInstant')

    def per_share(name, own, rest, period, rest_coerce, parse):
        hit = resolve_tiers(csv_files, own, standard=accounting_standard, period=period,
                            is_consolidated=is_consolidated, mode='string', coerce=True)
        if hit is None:
            hit = resolve_tiers(csv_files, rest, standard=accounting_standard, period=period,
                                is_consolidated=is_consolidated, mode='string',
                                coerce=rest_coerce)
        value = parse(hit.value) if hit else None
        if value is not None:
            sources[name], contexts[name] = hit.element_id, hit.context_id
        return value

    # EPS: a marker is a missing fact (coerce); a non-numeric string is a
    # silent None (the guarded Decimal). The equity ratio's legacy scan keeps
    # its first-non-empty-raw-string read: a marker parses to None.
    eps_basic = per_share('eps_basic_ytd', _EPS_OWN, _EPS_REST, 'CurrentYTDDuration', True,
                          _decimal_or_none)
    equity_ratio = per_share('equity_ratio', _EQUITY_RATIO_OWN, _EQUITY_RATIO_REST,
                             'CurrentQuarterInstant', False, parse_percentage)

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields, raw_facts = categorize_elements(csv_files, ELEMENT_MAP)

    return QuarterlyReport(
        doc_id=doc_id,
        doc_type_code=doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,
        raw_facts=raw_facts,

        # Identification
        filer_name=company_name or getattr(document, 'filer_name', None),
        filer_edinet_code=edinet_code or getattr(document, 'filer_edinet_code', None),
        ticker=ticker,
        accounting_standard=accounting_standard,
        is_consolidated=is_consolidated,

        # Period
        fiscal_year_end=fiscal_year_end,
        quarter_number=quarter_number,
        filing_date=filing_date,

        # Financials (tier tables): income statement current + prior YTD,
        # balance sheet, cash flow
        **fields,

        # Per-Share
        eps_basic_ytd=eps_basic,

        # Ratios
        equity_ratio=equity_ratio,

        # Provenance
        source_elements=sources,
        source_contexts=contexts,
    )
