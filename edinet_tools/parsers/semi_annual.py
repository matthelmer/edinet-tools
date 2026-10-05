"""
Parser for Semi-Annual Reports (Doc Type 160/170).

Extracts financial data from 半期報告書 filings.
Supports both corporate and fund reports with IFRS fallback.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

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
    PREFERRED_PER_SHARE_UNIT,
    resolve_tiers,
    get_dei,
    extract_csv_from_zip,
    categorize_elements,
    parse_date,
    parse_decimal,
)
from .validation import Bound, Identity, apply_validation


# XBRL Element ID mappings for Doc 160 (Semi-Annual Reports)
ELEMENT_MAP = {
    # === DEI Elements (Identification) ===
    'edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'fund_code': 'jpdei_cor:FundCodeDEI',
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'fund_name': 'jpdei_cor:FundNameInJapaneseDEI',
    'period_start': 'jpdei_cor:CurrentFiscalYearStartDateDEI',
    'period_end': 'jpdei_cor:CurrentPeriodEndDateDEI',
    'filing_date': 'jpcrp_cor:FilingDateCoverPage',
    'fund_filing_date': 'jpsps_cor:FilingDateCoverPage',
    'submission_date': 'jpdei_cor:DateOfSubmissionDEI',
    'accounting_standard': 'jpdei_cor:AccountingStandardsDEI',
    'is_consolidated': 'jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',

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
    # The IFRS taxonomy's current-liabilities total is TotalCurrentLiabilitiesIFRS
    # (there is no CurrentLiabilitiesIFRS element), as in the annual map.
    'jppfs_cor:CurrentLiabilities': 'jpigp_cor:TotalCurrentLiabilitiesIFRS',
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
    accounting_standard: str | None = None
    is_consolidated: bool | None = None

    # Period
    period_start: date | None = None
    period_end: date | None = None
    # Stated cover date, which may be the original report's date in an
    # amendment; use Document/list metadata for the document's submission.
    filing_date: date | None = None

    # Balance Sheet
    total_assets: int | None = None
    current_assets: int | None = None
    total_liabilities: int | None = None
    current_liabilities: int | None = None
    net_assets: int | None = None

    # Income Statement
    # net_sales: revenue on the declared standard, the annual report's
    # sources (J-GAAP net sales, banks' and insurers' 経常収益, brokers'
    # 営業収益; IFRS revenue; US-GAAP revenues). Not a fund's operating
    # revenue (OperatingRevenueFND), which this parser does not read.
    net_sales: int | None = None
    operating_income: int | None = None
    # ordinary_income: 経常利益 for J-GAAP filers; IFRS has no ordinary-income
    # concept, so for IFRS filers it holds profit before tax as the analogue
    # (ProfitLossBeforeTaxIFRS). profit_before_tax is the same concept under
    # its own name, for every standard.
    ordinary_income: int | None = None
    profit_before_tax: int | None = None
    profit_loss: int | None = None
    profit_attributable_to_owners: int | None = None

    # Cash Flow (the half year, the highlights table first, then the
    # statement), each on the declared standard.
    operating_cash_flow: int | None = None
    investing_cash_flow: int | None = None
    financing_cash_flow: int | None = None

    # Per-Share: basic EPS for the half year, on the declared standard (a
    # null marker is a missing fact).
    earnings_per_share: Decimal | None = None

    @property
    def filer(self):
        """Resolve filer to Entity via the FSA registry.

        The Entity exposes `entity_type` (an `EntityType` enum:
        FUND_ISSUER, LISTED_COMPANY, UNLISTED_COMPANY, INDIVIDUAL,
        UNKNOWN), classified from the FSA registry — prefer it over any
        XBRL-derived inference. Note FUND_ISSUER means "appears in the
        fund registry's issuer column" (trust banks qualify), not "is a
        fund"; corroborate before treating an issuer as a fund itself.

        Returns None when filer_edinet_code is not set, or when the entity
        is not in the registry (honest unknown).
        """
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


def _filing_date(csv_files: list) -> date | None:
    """Read a stated submission date; the financial period is not evidence.

    In an amendment this can be the original report's date; actual document
    submission comes from Document/list metadata, not this field.
    Cover pages carry the date in real EDINET filings. Retain support for
    the legacy DEI field when supplied, but do not choose between conflicting
    valid dates, including duplicates spread across files in a fund package.
    """
    elements = {ELEMENT_MAP[key] for key in
                ('filing_date', 'fund_filing_date', 'submission_date')}
    dates = {
        parsed
        for csv_file in csv_files
        for row in csv_file.get('data', [])
        if row.get('要素ID') in elements
        and row.get('コンテキストID') == 'FilingDateInstant'
        if (parsed := parse_date(row.get('値'))) is not None
    }
    return next(iter(dates)) if len(dates) == 1 else None


def _chain(key: str):
    """ELEMENT_MAP[key] plus its IFRS_FALLBACK_MAP fallback as ONE tier's
    element chain."""
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
# the J-GAAP operating income; a US-GAAP filer never reads another standard's
# total-basis profit (US GAAP tags none).
#
# The existing fields' legacy tables: the field's 0.8 tier (one element with
# at most one IFRS fallback), unchanged, plus the other standards' elements as
# tiers scoped to their own standard (a scoped tier never serves a filing of
# another standard, nor one that declares none). The 0.8 tier comes first, so
# its own-standard element keeps its place in the own stage: a value 0.8
# already read on the declared standard does not move (a filing whose
# highlights table and statements disagree keeps the statements' figure). The
# new fields reuse the annual parser's tables and policies: the same concepts,
# the same elements, read at this document's period token. Periods: balance-
# sheet fields read the document's current instant token, the others its
# current duration token (detect_period_tokens); the context rule is
# get_context_patterns.
# ---------------------------------------------------------------------------

_C, _G = 'jpcrp_cor:', 'jpigp_cor:'
_SB = 'SummaryOfBusinessResults'
_JG, _IFRS, _US = JGAAP, IFRS, USGAAP
_ALL = (_JG, _IFRS, _US)


def _own(element, standard):
    return Tier(element, standards=(standard,))


_INSTANT_LEGACY = {
    'total_assets': (
        Tier(_chain('assets')),
        _own(_C + 'TotalAssetsIFRS' + _SB, _IFRS),
        _own(_C + 'TotalAssetsUSGAAP' + _SB, _US),
    ),
    'current_assets': (Tier(_chain('current_assets')),),
    'total_liabilities': (Tier(_chain('liabilities')),),
    'current_liabilities': (Tier(_chain('current_liabilities')),),
    'net_assets': (
        Tier(_chain('net_assets')),
        _own(_C + 'EquityIncludingPortionAttributableToNonControllingInterestUSGAAP' + _SB, _US),
    ),
}
_DURATION_LEGACY = {
    'net_sales': _securities._DURATION_LEGACY['net_sales'],
    'operating_income': (
        Tier(_chain('operating_income')),
        _own(_C + 'OperatingProfitLossIFRS' + _SB, _IFRS),
        _own(_C + 'OperatingIncomeLossUSGAAP' + _SB, _US),
        Tier(('OperatingProfitLossIFRS' + _SB, 'OperatingIncomeIFRS' + _SB,
              'OperatingIncomeLossIFRS' + _SB, 'OperatingProfitIFRS' + _SB),
             standards=(_IFRS,), suffix_match=True),
    ),
    'ordinary_income': (Tier(_chain('ordinary_income')),),
    'profit_before_tax': _securities._PROFIT_BEFORE_TAX_LEGACY,
    'profit_loss': (Tier(_chain('profit_loss')),),
    'profit_attributable_to_owners': _securities._DURATION_LEGACY['net_income_owners'],
    'operating_cash_flow': _securities._DURATION_LEGACY['operating_cash_flow'],
    'investing_cash_flow': _securities._DURATION_LEGACY['investing_cash_flow'],
    'financing_cash_flow': _securities._DURATION_LEGACY['financing_cash_flow'],
}
_EPS_LEGACY = _securities._EPS_LEGACY

_LEGACY_TABLES = {
    **{name: (t,) for name, t in _INSTANT_LEGACY.items()},
    **{name: (t,) for name, t in _DURATION_LEGACY.items()},
    'earnings_per_share': (_EPS_LEGACY,),
}

_LEGACY = 'legacy'
_annual = _securities._STANDARD_POLICY
_STANDARD_POLICY = {
    'total_assets': FieldPolicy('Total assets', _ALL, _LEGACY),
    'current_assets': FieldPolicy('Current assets (FS)', (_JG, _IFRS), _LEGACY),
    'total_liabilities': FieldPolicy('Total liabilities (FS)', (_JG, _IFRS), _LEGACY),
    'current_liabilities': FieldPolicy('Current liabilities (FS)', (_JG, _IFRS), _LEGACY),
    'net_assets': FieldPolicy('Net assets / total equity including non-controlling '
                              'interests', _ALL, _LEGACY),
    'net_sales': _annual['net_sales'],
    # IFRS and US-GAAP filers never read the J-GAAP figure (the 0.7.1 gate).
    'operating_income': FieldPolicy('Operating profit; no J-GAAP figure for IFRS or '
                                    'US-GAAP filers', _ALL,
                                    {_JG: 'legacy', _IFRS: 'none', _US: 'none'}),
    'ordinary_income': FieldPolicy('Ordinary income; IFRS profit before tax as the '
                                   'analogue', (_JG, _IFRS),
                                   {_JG: 'n/a', _IFRS: 'legacy', _US: 'legacy'}),
    'profit_before_tax': FieldPolicy('Profit before income taxes', _ALL, 'none'),
    # US GAAP tags no total-basis profit: honest None, never the J-GAAP line.
    'profit_loss': FieldPolicy('Profit including non-controlling interests', (_JG, _IFRS),
                               {_JG: 'legacy', _IFRS: 'legacy', _US: 'none'}),
    'profit_attributable_to_owners': _annual['net_income_owners'],
    'operating_cash_flow': _annual['operating_cash_flow'],
    'investing_cash_flow': _annual['investing_cash_flow'],
    'financing_cash_flow': _annual['financing_cash_flow'],
    'earnings_per_share': _annual['earnings_per_share'],
}

# Resolved tables: own-standard stage, then the legacy table (closed where the
# fallback is 'none'). EPS resolves its own stage with coerce semantics, then
# the legacy scan.
_INSTANT_FIELD_TIERS = {name: with_own_standard_first(t, _STANDARD_POLICY[name])
                        for name, t in _INSTANT_LEGACY.items()}
_DURATION_FIELD_TIERS = {name: with_own_standard_first(t, _STANDARD_POLICY[name])
                         for name, t in _DURATION_LEGACY.items()}
_EPS_OWN = own_standard_stage(_EPS_LEGACY, _STANDARD_POLICY['earnings_per_share'])
_EPS_REST = close_legacy(_EPS_LEGACY, _STANDARD_POLICY['earnings_per_share'])


def detect_period_tokens(csv_files: list) -> tuple[str, str]:
    """Doc-level period-token regime: (instant_token, duration_token).

    Two vocabularies coexist in the corpus: the -ssr taxonomy's
    `InterimInstant`/`InterimDuration` (funds always; banks/特定事業会社
    throughout; corporates from FY2025) and the FY2024 transitional -q2r
    taxonomy's `CurrentQuarterInstant`/`CurrentYTDDuration`. Rule
    (corpus-validated, unambiguous on every sampled document): prefer the
    Interim* vocabulary if ANY context id in the filing contains 'Interim'
    (current or prior period -- both signal the same regime), else fall
    back to CurrentQuarter*/CurrentYTD*.

    Public (not `_`-prefixed): the period token is a primitive both this
    parser and any caller extracting doc-type-specific elements not in
    ELEMENT_MAP (e.g. a fund's FND balance-sheet elements) need to resolve
    the same way -- one regime-detection implementation, not a re-derived
    copy per caller.
    """
    for csv_file in csv_files or []:
        for row in csv_file.get('data', []) or []:
            if 'Interim' in (row.get('コンテキストID', '') or ''):
                return 'InterimInstant', 'InterimDuration'
    return 'CurrentQuarterInstant', 'CurrentYTDDuration'


def _net_assets_le_total_assets(na, ta):
    return na <= ta


def _current_le_total_liabilities(cl, tl):
    return cl <= tl


# Modest structural bounds + identities (v0.8.0 stage-5 Task 9), matching
# the securities-report exemplar's shape: bounds withhold an impossible
# value (never a claim about what's typical); identities annotate a
# cross-field inconsistency without emptying either operand.
SEMI_ANNUAL_BOUNDS = [
    Bound(field='total_assets', min_value=0),
    Bound(field='total_liabilities', min_value=0),
    Bound(field='current_liabilities', min_value=0),
]

SEMI_ANNUAL_IDENTITIES = [
    Identity(name='identity:net_assets<=total_assets',
             operands=('net_assets', 'total_assets'),
             check=_net_assets_le_total_assets),
    Identity(name='identity:current_liabilities<=total_liabilities',
             operands=('current_liabilities', 'total_liabilities'),
             check=_current_le_total_liabilities),
]


def parse_semi_annual_report(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> SemiAnnualReport:
    """
    Parse a Semi-Annual Report document.

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        SemiAnnualReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return SemiAnnualReport(
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
    filer_name = get_dei(csv_files, ELEMENT_MAP, 'filer_name')
    fund_code = get_dei(csv_files, ELEMENT_MAP, 'fund_code')
    fund_name = get_dei(csv_files, ELEMENT_MAP, 'fund_name')

    # Whitespace-stripped: a handful of real filings tag this DEI value with
    # trailing tab/whitespace noise ('Japan GAAP' + stray tabs) -- strip
    # defensively so it matches a standards tuple downstream.
    accounting_standard_raw = get_dei(csv_files, ELEMENT_MAP, 'accounting_standard')
    accounting_standard = (accounting_standard_raw.strip()
                           if accounting_standard_raw else None)
    is_consolidated_raw = get_dei(csv_files, ELEMENT_MAP, 'is_consolidated')
    is_consolidated = (is_consolidated_raw == 'true') if is_consolidated_raw else None

    # Extract period
    period_start = parse_date(get_dei(csv_files, ELEMENT_MAP, 'period_start'))
    period_end = parse_date(get_dei(csv_files, ELEMENT_MAP, 'period_end'))
    filing_date = _filing_date(csv_files)

    # Financial data from the tier tables — context-aware (v0.8.0 stage-5
    # Task 9): per-document period-token regime + strict bare-context-only
    # reads when consolidated (OKWAVE rule — see detect_period_tokens and
    # get_context_patterns).
    instant_period, duration_period = detect_period_tokens(csv_files)

    sources, contexts, units = {}, {}, {}

    def fin(name, tiers, period):
        hit = resolve_tiers(csv_files, tiers, standard=accounting_standard,
                            period=period, is_consolidated=is_consolidated)
        if hit is None:
            return None
        sources[name], contexts[name] = hit.element_id, hit.context_id
        units[name] = hit.unit_id
        return hit.value

    values = {name: fin(name, tiers, instant_period)
              for name, tiers in _INSTANT_FIELD_TIERS.items()}
    values.update({name: fin(name, tiers, duration_period)
                   for name, tiers in _DURATION_FIELD_TIERS.items()})

    eps_hit = resolve_tiers(csv_files, _EPS_OWN, standard=accounting_standard,
                            period=duration_period, is_consolidated=is_consolidated,
                            mode='string', coerce=True, prefer_unit=PREFERRED_PER_SHARE_UNIT)
    if eps_hit is None:
        eps_hit = resolve_tiers(csv_files, _EPS_REST, standard=accounting_standard,
                                period=duration_period, is_consolidated=is_consolidated,
                                mode='string', coerce=True,
                                prefer_unit=PREFERRED_PER_SHARE_UNIT)
    values['earnings_per_share'] = parse_decimal(eps_hit.value) if eps_hit else None
    if values['earnings_per_share'] is not None:
        sources['earnings_per_share'] = eps_hit.element_id
        contexts['earnings_per_share'] = eps_hit.context_id
        units['earnings_per_share'] = eps_hit.unit_id

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields, raw_facts = categorize_elements(csv_files, ELEMENT_MAP)

    report = SemiAnnualReport(
        doc_id=doc_id,
        doc_type_code=doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,
        raw_facts=raw_facts,

        # Identification
        filer_name=filer_name or getattr(document, 'filer_name', None),
        filer_edinet_code=edinet_code or getattr(document, 'filer_edinet_code', None),
        fund_code=fund_code,
        fund_name=fund_name,
        accounting_standard=accounting_standard,
        is_consolidated=is_consolidated,

        # Period
        period_start=period_start,
        period_end=period_end,
        filing_date=filing_date,

        # Financials (balance sheet, income statement, cash flow, per-share)
        **values,

        # Provenance
        source_elements=sources,
        source_contexts=contexts,
        # a row without a unit id has no entry (never None)
        units={k: u for k, u in units.items() if u is not None},
    )
    apply_validation(report, SEMI_ANNUAL_BOUNDS, SEMI_ANNUAL_IDENTITIES)
    return report
