"""End-to-end extraction tests for all parsers using synthetic EDINET CSV data.

Each test creates a realistic ZIP with EDINET-format CSV rows, passes it through
the full parser pipeline, and verifies extracted field values. This catches
regressions in element IDs, context patterns, type conversions, and fallback logic.
"""
import io
import zipfile
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock


def make_csv_row(element_id, context_id, value):
    """Create a single EDINET CSV row dict."""
    return {'要素ID': element_id, 'コンテキストID': context_id, '値': value}


def make_zip_with_rows(rows):
    """Create a ZIP containing a CSV with the given rows in EDINET format."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        lines = []
        for row in rows:
            line = f"{row['要素ID']}\tlabel\t{row['コンテキストID']}\t0\t連結\t期間\tunit1\t円\t{row['値']}"
            lines.append(line)
        content = '\n'.join(lines)
        zf.writestr('XBRL_TO_CSV/test.csv', content.encode('utf-16le'))
    return zip_buffer.getvalue()


def make_mock_doc(doc_id='S100TEST', doc_type='120', rows=None, filer_name='', filer_edinet_code=''):
    """Create a mock Document for parser tests."""
    doc = MagicMock()
    doc.doc_id = doc_id
    doc.doc_type_code = doc_type
    doc.filer_name = filer_name
    doc.filer_edinet_code = filer_edinet_code
    if rows is not None:
        doc.fetch.return_value = make_zip_with_rows(rows)
    else:
        doc.fetch.return_value = b''
    return doc

from edinet_tools.parsers.securities import parse_securities_report, SecuritiesReport
from edinet_tools.parsers.quarterly import parse_quarterly_report, QuarterlyReport
from edinet_tools.parsers.large_holding import parse_large_holding, LargeHoldingReport
from edinet_tools.parsers.treasury_stock import parse_treasury_stock_report, TreasuryStockReport
from edinet_tools.parsers.extraordinary import parse_extraordinary_report, ExtraordinaryReport
from edinet_tools.parsers.semi_annual import parse_semi_annual_report, SemiAnnualReport


# =====================================================================
# Securities Report (Doc 120)
# =====================================================================

class TestSecuritiesExtraction:
    """End-to-end extraction tests for parse_securities_report."""

    def _base_rows(self):
        """Minimal viable securities report CSV rows."""
        return [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:SecurityCodeDEI', 'FilingDateInstant', '24770'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト株式会社'),
            make_csv_row('jpdei_cor:FilerNameInEnglishDEI', 'FilingDateInstant', 'Test Corp'),
            make_csv_row('jpdei_cor:CurrentFiscalYearStartDateDEI', 'FilingDateInstant', '2024-04-01'),
            make_csv_row('jpdei_cor:CurrentFiscalYearEndDateDEI', 'FilingDateInstant', '2025-03-31'),
            make_csv_row('jpdei_cor:AccountingStandardsDEI', 'FilingDateInstant', 'Japan GAAP'),
            make_csv_row('jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI', 'FilingDateInstant', 'true'),
            # Summary financials
            make_csv_row('jpcrp_cor:NetSalesSummaryOfBusinessResults', 'CurrentYearDuration', '50000000000'),
            make_csv_row('jpcrp_cor:OrdinaryIncomeLossSummaryOfBusinessResults', 'CurrentYearDuration', '5000000000'),
            make_csv_row('jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults', 'CurrentYearDuration', '3000000000'),
            make_csv_row('jpcrp_cor:TotalAssetsSummaryOfBusinessResults', 'CurrentYearInstant', '100000000000'),
            make_csv_row('jpcrp_cor:NetAssetsSummaryOfBusinessResults', 'CurrentYearInstant', '40000000000'),
            # Operating income via FS
            make_csv_row('jppfs_cor:OperatingIncome', 'CurrentYearDuration', '4500000000'),
            # Cash flow
            make_csv_row('jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults', 'CurrentYearDuration', '6000000000'),
            make_csv_row('jpcrp_cor:NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults', 'CurrentYearDuration', '-2000000000'),
            make_csv_row('jpcrp_cor:NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults', 'CurrentYearDuration', '-1000000000'),
            # Per-share
            make_csv_row('jpcrp_cor:NetAssetsPerShareSummaryOfBusinessResults', 'CurrentYearInstant', '2345.67'),
            make_csv_row('jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults', 'CurrentYearDuration', '123.45'),
            # Ratios
            make_csv_row('jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults', 'CurrentYearInstant', '40.0'),
            make_csv_row('jpcrp_cor:RateOfReturnOnEquitySummaryOfBusinessResults', 'CurrentYearDuration', '8.5'),
            # Employees
            make_csv_row('jpcrp_cor:NumberOfEmployees', 'CurrentYearInstant', '5000'),
        ]

    def test_full_extraction(self):
        doc = make_mock_doc('S100SEC', '120', self._base_rows())
        r = parse_securities_report(doc)

        assert isinstance(r, SecuritiesReport)
        assert r.filer_edinet_code == 'E05123'
        assert r.ticker == '2477.T'
        assert r.filer_name == 'テスト株式会社'
        assert r.filer_name_en == 'Test Corp'
        assert r.accounting_standard == 'Japan GAAP'
        assert r.is_consolidated is True
        assert r.fiscal_year_start == date(2024, 4, 1)
        assert r.fiscal_year_end == date(2025, 3, 31)

        # Financials
        assert r.net_sales == 50000000000
        assert r.operating_income == 4500000000
        assert r.ordinary_income == 5000000000
        assert r.net_income == 3000000000
        assert r.total_assets == 100000000000
        assert r.net_assets == 40000000000

        # Cash flow
        assert r.operating_cash_flow == 6000000000
        assert r.investing_cash_flow == -2000000000
        assert r.financing_cash_flow == -1000000000

        # Per-share (Decimal)
        assert r.net_assets_per_share == Decimal('2345.67')
        assert r.earnings_per_share == Decimal('123.45')

        # Ratios (stored as raw percentage value, not divided by 100)
        assert r.equity_ratio == Decimal('40.0')
        assert r.roe == Decimal('8.5')

        # Employees
        assert r.num_employees == 5000

    def test_empty_zip(self):
        doc = make_mock_doc('S100EMPTY', '120', rows=None)
        r = parse_securities_report(doc)
        assert isinstance(r, SecuritiesReport)
        assert r.filer_name is None
        assert r.net_sales is None

    def test_csv_files_param(self):
        """Verify csv_files= parameter path (used by corpjapan)."""
        from edinet_tools.parsers.extraction import extract_csv_from_zip
        rows = self._base_rows()
        zip_bytes = make_zip_with_rows(rows)
        csv_files = extract_csv_from_zip(zip_bytes)

        r = parse_securities_report(csv_files=csv_files, doc_id='S100CSV', doc_type_code='120')
        assert r.filer_edinet_code == 'E05123'
        assert r.net_sales == 50000000000

    def test_ifrs_cash_flow_fallback(self):
        """When J-GAAP summary CF is missing, should fall back to IFRS summary."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E99999'),
            make_csv_row('jpdei_cor:SecurityCodeDEI', 'FilingDateInstant', '12340'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'IFRS社'),
            make_csv_row('jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI', 'FilingDateInstant', 'true'),
            # No J-GAAP summary CF — use IFRS summary
            make_csv_row('jpcrp_cor:CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults', 'CurrentYearDuration', '7000000000'),
            make_csv_row('jpcrp_cor:CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults', 'CurrentYearDuration', '-3000000000'),
        ]
        doc = make_mock_doc('S100IFRS', '120', rows)
        r = parse_securities_report(doc)

        assert r.operating_cash_flow == 7000000000
        assert r.investing_cash_flow == -3000000000

    def test_is_consolidated_default_true(self):
        """When is_consolidated DEI element is absent, default to True."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E11111'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト'),
        ]
        doc = make_mock_doc('S100DEF', '120', rows)
        r = parse_securities_report(doc)
        assert r.is_consolidated is True


# =====================================================================
# Quarterly Report (Doc 140)
# =====================================================================

class TestQuarterlyExtraction:
    """End-to-end extraction tests for parse_quarterly_report."""

    def _base_rows(self):
        return [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:SecurityCodeDEI', 'FilingDateInstant', '24770'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト株式会社'),
            make_csv_row('jpdei_cor:CurrentFiscalYearEndDateDEI', 'FilingDateInstant', '2025-03-31'),
            make_csv_row('jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI', 'FilingDateInstant', 'true'),
            # Filing date (needed for quarter derivation)
            make_csv_row('jpcrp_cor:FilingDateCoverPage', 'FilingDateInstant', '2024-11-14'),
            # YTD income
            make_csv_row('jppfs_cor:NetSales', 'CurrentYTDDuration', '25000000000'),
            make_csv_row('jppfs_cor:OperatingIncome', 'CurrentYTDDuration', '2500000000'),
            make_csv_row('jppfs_cor:OrdinaryIncome', 'CurrentYTDDuration', '2600000000'),
            make_csv_row('jppfs_cor:ProfitLossAttributableToOwnersOfParent', 'CurrentYTDDuration', '1500000000'),
            # Balance sheet
            make_csv_row('jppfs_cor:Assets', 'CurrentQuarterInstant', '90000000000'),
            make_csv_row('jppfs_cor:NetAssets', 'CurrentQuarterInstant', '38000000000'),
            make_csv_row('jppfs_cor:Liabilities', 'CurrentQuarterInstant', '52000000000'),
            # Cash flow
            make_csv_row('jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults', 'CurrentYTDDuration', '4000000000'),
            # EPS
            make_csv_row('jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults', 'CurrentYTDDuration', '75.50'),
            # Equity ratio
            make_csv_row('jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults', 'CurrentQuarterInstant', '42.2'),
        ]

    def test_full_extraction(self):
        doc = make_mock_doc('S100QTR', '140', self._base_rows())
        r = parse_quarterly_report(doc)

        assert isinstance(r, QuarterlyReport)
        assert r.filer_edinet_code == 'E05123'
        assert r.ticker == '2477.T'
        assert r.fiscal_year_end == date(2025, 3, 31)
        assert r.filing_date == date(2024, 11, 14)
        assert r.is_consolidated is True

        # Q2 filing: Nov 2024, fiscal year starts Apr 2024 → 7 months from start
        assert r.quarter_number == 2

        assert r.revenue_ytd == 25000000000
        assert r.operating_profit_ytd == 2500000000
        assert r.ordinary_profit_ytd == 2600000000
        assert r.net_income_ytd == 1500000000
        assert r.total_assets == 90000000000
        assert r.operating_cash_flow_ytd == 4000000000
        assert r.eps_basic_ytd == Decimal('75.50')
        assert r.equity_ratio == Decimal('42.2')

    def test_empty_zip(self):
        doc = make_mock_doc('S100EMPTY', '140', rows=None)
        r = parse_quarterly_report(doc)
        assert isinstance(r, QuarterlyReport)
        assert r.revenue_ytd is None

    def test_quarter_number_q1(self):
        """Q1 filing: ~4 months from fiscal year start."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト'),
            make_csv_row('jpdei_cor:CurrentFiscalYearEndDateDEI', 'FilingDateInstant', '2025-03-31'),
            make_csv_row('jpcrp_cor:FilingDateCoverPage', 'FilingDateInstant', '2024-08-14'),
        ]
        doc = make_mock_doc('S100Q1', '140', rows)
        r = parse_quarterly_report(doc)
        assert r.quarter_number == 1


# =====================================================================
# Large Holding Report (Doc 350)
# =====================================================================

class TestLargeHoldingExtraction:
    """End-to-end extraction tests for parse_large_holding."""

    def _base_rows(self):
        return [
            make_csv_row('jplvh_cor:EDINETCodeDEI', 'FilingDateInstant', 'E99001'),
            make_csv_row('jplvh_cor:Name', 'FilingDateInstant', 'アクティビスト投資'),
            make_csv_row('jplvh_cor:FilerNameInEnglishDEI', 'FilingDateInstant', 'Activist Fund'),
            make_csv_row('jplvh_cor:IndividualOrCorporation', 'FilingDateInstant', '法人'),
            make_csv_row('jplvh_cor:ResidentialAddressOrAddressOfRegisteredHeadquarter', 'FilingDateInstant', '東京都千代田区'),
            make_csv_row('jplvh_cor:DescriptionOfBusiness', 'FilingDateInstant', '投資業'),
            make_csv_row('jplvh_cor:NameOfIssuer', 'FilingDateInstant', 'ターゲット株式会社'),
            make_csv_row('jplvh_cor:SecurityCodeOfIssuer', 'FilingDateInstant', '24770'),
            make_csv_row('jplvh_cor:ListedOrOTC', 'FilingDateInstant', '上場'),
            make_csv_row('jplvh_cor:TotalNumberOfStocksEtcHeld', 'FilingDateInstant', '5,000,000'),
            make_csv_row('jplvh_cor:HoldingRatioOfShareCertificatesEtc', 'FilingDateInstant', '9.67'),
            make_csv_row('jplvh_cor:HoldingRatioOfShareCertificatesEtcPerLastReport', 'FilingDateInstant', '5.12'),
            make_csv_row('jplvh_cor:TotalNumberOfOutstandingStocksEtc', 'FilingDateInstant', '51,700,000'),
            make_csv_row('jplvh_cor:PurposeOfHolding', 'FilingDateInstant', '純投資'),
            make_csv_row('jplvh_cor:FilingDateCoverPage', 'FilingDateInstant', '2025-06-15'),
            make_csv_row('jplvh_cor:AmountOfOwnFund', 'FilingDateInstant', '500,000,000'),
            make_csv_row('jplvh_cor:TotalAmountOfFundingForAcquisition', 'FilingDateInstant', '500,000,000'),
            make_csv_row('jplvh_cor:DocumentTitleCoverPage', 'FilingDateInstant', '大量保有報告書'),
        ]

    def test_full_extraction(self):
        doc = make_mock_doc('S100LH', '350', self._base_rows())
        r = parse_large_holding(doc)

        assert isinstance(r, LargeHoldingReport)
        assert r.filer_edinet_code == 'E99001'
        assert r.filer_name == 'アクティビスト投資'
        assert r.filer_name_en == 'Activist Fund'
        assert r.filer_type == '法人'
        assert r.target_company == 'ターゲット株式会社'
        assert r.target_ticker == '2477.T'
        assert r.listed_or_otc == '上場'
        assert r.shares_held == 5000000
        assert r.shares_outstanding == 51700000
        assert r.purpose == '純投資'
        assert r.filing_date == date(2025, 6, 15)
        assert r.report_indication == '大量保有報告書'

        # Ownership percentages (stored as raw percentage value)
        assert r.ownership_pct == Decimal('9.67')
        assert r.prior_ownership_pct == Decimal('5.12')

        # Calculated change
        assert r.ownership_change == Decimal('9.67') - Decimal('5.12')

        # Funding
        assert r.acquisition_fund_own == 500000000
        assert r.acquisition_fund_total == 500000000

    def test_empty_zip(self):
        doc = make_mock_doc('S100EMPTY', '350', rows=None)
        r = parse_large_holding(doc)
        assert isinstance(r, LargeHoldingReport)
        assert r.filer_name is None

    def test_filer_name_fallback(self):
        """When primary Name element missing, should fall back to DEI FilerName."""
        rows = [
            # No jplvh_cor:Name — fall back to FilerNameInJapaneseDEI
            make_csv_row('jplvh_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'Fallback Filer'),
            make_csv_row('jplvh_cor:NameOfIssuer', 'FilingDateInstant', 'Target'),
        ]
        doc = make_mock_doc('S100FB', '350', rows)
        r = parse_large_holding(doc)
        assert r.filer_name == 'Fallback Filer'

    def test_csv_files_param(self):
        """Verify csv_files= parameter path."""
        from edinet_tools.parsers.extraction import extract_csv_from_zip
        zip_bytes = make_zip_with_rows(self._base_rows())
        csv_files = extract_csv_from_zip(zip_bytes)

        r = parse_large_holding(csv_files=csv_files, doc_id='S100CSV', doc_type_code='350')
        assert r.filer_name == 'アクティビスト投資'
        assert r.target_ticker == '2477.T'


# =====================================================================
# Treasury Stock Report (Doc 220)
# =====================================================================

class TestTreasuryStockExtraction:
    """End-to-end extraction tests for parse_treasury_stock_report."""

    def _base_rows(self):
        return [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト株式会社'),
            make_csv_row('jpdei_cor:FilerNameInEnglishDEI', 'FilingDateInstant', 'Test Corp'),
            make_csv_row('jpdei_cor:SecurityCodeDEI', 'FilingDateInstant', '24770'),
            make_csv_row('jpdei_cor:AmendmentFlagDEI', 'FilingDateInstant', 'false'),
            make_csv_row('jpcrp-sbr_cor:DocumentTitleCoverPage', 'FilingDateInstant', '自己株券買付状況報告書'),
            make_csv_row('jpcrp-sbr_cor:FilingDateCoverPage', 'FilingDateInstant', '2025-07-15'),
            make_csv_row('jpcrp-sbr_cor:TitleAndNameOfRepresentativeCoverPage', 'FilingDateInstant', '代表取締役 田中太郎'),
            make_csv_row('jpcrp-sbr_cor:AddressOfRegisteredHeadquarterCoverPage', 'FilingDateInstant', '東京都渋谷区'),
            make_csv_row('jpcrp-sbr_cor:ReportingPeriodCoverPage', 'FilingDateInstant', '2025年6月'),
            # TextBlock content
            make_csv_row('jpcrp-sbr_cor:AcquisitionsByResolutionOfShareholdersMeetingTextBlock', 'FilingDateInstant', '<p>株主総会決議による取得</p>'),
            make_csv_row('jpcrp-sbr_cor:AcquisitionsByResolutionOfBoardOfDirectorsMeetingTextBlock', 'FilingDateInstant', '<p>取締役会決議による取得</p>'),
            make_csv_row('jpcrp-sbr_cor:HoldingOfTreasurySharesTextBlock', 'FilingDateInstant', '保有自己株式数1,000,000株'),
        ]

    def test_full_extraction(self):
        doc = make_mock_doc('S100TS', '220', self._base_rows())
        r = parse_treasury_stock_report(doc)

        assert isinstance(r, TreasuryStockReport)
        assert r.filer_edinet_code == 'E05123'
        assert r.filer_name == 'テスト株式会社'
        assert r.ticker == '2477.T'
        assert r.filing_date == date(2025, 7, 15)
        assert r.representative == '代表取締役 田中太郎'
        assert r.reporting_period == '2025年6月'
        assert r.is_amendment is False

        # TextBlock content
        assert '株主総会決議' in r.by_shareholders_meeting
        assert '取締役会決議' in r.by_board_meeting
        assert r.has_shareholder_authorization is True
        assert r.has_board_authorization is True
        assert '保有自己株式数' in r.disposal_holding_text

    def test_amendment_flag(self):
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト'),
            make_csv_row('jpdei_cor:AmendmentFlagDEI', 'FilingDateInstant', 'true'),
        ]
        doc = make_mock_doc('S100AMEND', '230', rows)
        r = parse_treasury_stock_report(doc)
        assert r.is_amendment is True

    def test_empty_zip(self):
        doc = make_mock_doc('S100EMPTY', '220', rows=None)
        r = parse_treasury_stock_report(doc)
        assert isinstance(r, TreasuryStockReport)
        assert r.filer_name is None


# =====================================================================
# Extraordinary Report (Doc 180)
# =====================================================================

class TestExtraordinaryExtraction:
    """End-to-end extraction tests for parse_extraordinary_report."""

    def test_corporate_report(self):
        """Corporate extraordinary report uses jpcrp-esr_cor namespace."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト株式会社'),
            make_csv_row('jpdei_cor:SecurityCodeDEI', 'FilingDateInstant', '24770'),
            make_csv_row('jpcrp-esr_cor:DocumentTitleCoverPage', 'FilingDateInstant', '臨時報告書'),
            make_csv_row('jpcrp-esr_cor:FilingDateCoverPage', 'FilingDateInstant', '2025-08-01'),
            make_csv_row('jpcrp-esr_cor:TitleAndNameOfRepresentativeCoverPage', 'FilingDateInstant', '代表取締役 山田花子'),
            make_csv_row('jpcrp-esr_cor:ReasonForFilingTextBlock', 'FilingDateInstant', '重要な変更が発生しました'),
        ]
        doc = make_mock_doc('S100EX', '180', rows)
        r = parse_extraordinary_report(doc)

        assert isinstance(r, ExtraordinaryReport)
        assert r.filer_edinet_code == 'E05123'
        assert r.filer_name == 'テスト株式会社'
        assert r.ticker == '2477.T'
        assert r.document_title == '臨時報告書'
        assert r.filing_date == date(2025, 8, 1)
        assert r.reason_for_filing == '重要な変更が発生しました'
        assert r.event_type == 'material_change'
        assert r.is_fund is False

    def test_fund_report(self):
        """Fund extraordinary report uses jpsps-esr_cor namespace."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E77777'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テストファンド'),
            make_csv_row('jpdei_cor:FundCodeDEI', 'FilingDateInstant', 'G12345'),
            make_csv_row('jpdei_cor:FundNameInJapaneseDEI', 'FilingDateInstant', 'テスト投資信託'),
            make_csv_row('jpsps-esr_cor:DocumentTitleCoverPage', 'FilingDateInstant', '臨時報告書'),
            make_csv_row('jpsps-esr_cor:FilingDateCoverPage', 'FilingDateInstant', '2025-09-01'),
            make_csv_row('jpsps-esr_cor:ReasonForFilingTextBlock', 'FilingDateInstant', '信託終了のお知らせ'),
        ]
        doc = make_mock_doc('S100FUND', '180', rows)
        r = parse_extraordinary_report(doc)

        assert r.fund_code == 'G12345'
        assert r.fund_name == 'テスト投資信託'
        assert r.is_fund is True
        assert r.event_type == 'trust_termination'
        assert r.filing_date == date(2025, 9, 1)

    def test_event_type_classification(self):
        """Various event type keywords should be classified correctly."""
        from edinet_tools.parsers.extraordinary import _classify_event_type

        assert _classify_event_type('信託終了のお知らせ') == 'trust_termination'
        assert _classify_event_type('吸収合併のお知らせ') == 'merger'
        assert _classify_event_type('約款変更のお知らせ') == 'trust_change'
        assert _classify_event_type('解散について') == 'dissolution'
        assert _classify_event_type('重要な変更') == 'material_change'
        assert _classify_event_type('通常のお知らせ') == 'other'
        assert _classify_event_type(None) == 'unknown'

    def test_empty_zip(self):
        doc = make_mock_doc('S100EMPTY', '180', rows=None)
        r = parse_extraordinary_report(doc)
        assert isinstance(r, ExtraordinaryReport)
        assert r.filer_name is None


# =====================================================================
# Semi-Annual Report (Doc 160)
# =====================================================================

class TestSemiAnnualExtraction:
    """End-to-end extraction tests for parse_semi_annual_report."""

    def _base_rows(self):
        return [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト株式会社'),
            make_csv_row('jpdei_cor:CurrentFiscalYearStartDateDEI', 'FilingDateInstant', '2024-04-01'),
            make_csv_row('jpdei_cor:CurrentPeriodEndDateDEI', 'FilingDateInstant', '2024-09-30'),
            make_csv_row('jpdei_cor:DateOfSubmissionDEI', 'FilingDateInstant', '2024-12-25'),
            # Financials (no context filtering in semi_annual parser)
            make_csv_row('jppfs_cor:Assets', 'CurrentQuarterInstant', '80000000000'),
            make_csv_row('jppfs_cor:CurrentAssets', 'CurrentQuarterInstant', '30000000000'),
            make_csv_row('jppfs_cor:Liabilities', 'CurrentQuarterInstant', '45000000000'),
            make_csv_row('jppfs_cor:NetAssets', 'CurrentQuarterInstant', '35000000000'),
            make_csv_row('jppfs_cor:OperatingIncome', 'CurrentYTDDuration', '2000000000'),
            make_csv_row('jppfs_cor:OrdinaryIncome', 'CurrentYTDDuration', '2100000000'),
            make_csv_row('jppfs_cor:ProfitLoss', 'CurrentYTDDuration', '1200000000'),
        ]

    def test_full_extraction(self):
        doc = make_mock_doc('S100SA', '160', self._base_rows())
        r = parse_semi_annual_report(doc)

        assert isinstance(r, SemiAnnualReport)
        assert r.filer_edinet_code == 'E05123'
        assert r.filer_name == 'テスト株式会社'
        assert r.period_start == date(2024, 4, 1)
        assert r.period_end == date(2024, 9, 30)
        assert r.filing_date == date(2024, 12, 25)

        assert r.total_assets == 80000000000
        assert r.current_assets == 30000000000
        assert r.total_liabilities == 45000000000
        assert r.net_assets == 35000000000
        assert r.operating_income == 2000000000
        assert r.ordinary_income == 2100000000
        assert r.profit_loss == 1200000000
        assert r.is_fund is False

    def test_fund_report(self):
        """Fund semi-annual report should set is_fund=True."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E77777'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト投信'),
            make_csv_row('jpdei_cor:FundCodeDEI', 'FilingDateInstant', 'G12345'),
            make_csv_row('jpdei_cor:FundNameInJapaneseDEI', 'FilingDateInstant', 'テストファンド'),
        ]
        doc = make_mock_doc('S100FUND', '160', rows)
        r = parse_semi_annual_report(doc)
        assert r.is_fund is True
        assert r.fund_code == 'G12345'

    def test_ifrs_fallback(self):
        """When J-GAAP element missing, should fall back to IFRS."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E88888'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'IFRS社'),
            # No J-GAAP Assets — should fall back to IFRS
            make_csv_row('jpigp_cor:AssetsIFRS', 'CurrentQuarterInstant', '99000000000'),
        ]
        doc = make_mock_doc('S100IFRS', '160', rows)
        r = parse_semi_annual_report(doc)
        assert r.total_assets == 99000000000

    def test_empty_zip(self):
        doc = make_mock_doc('S100EMPTY', '160', rows=None)
        r = parse_semi_annual_report(doc)
        assert isinstance(r, SemiAnnualReport)
        assert r.total_assets is None

    def test_filing_date_fallback_to_period_end(self):
        """When submission_date missing, filing_date should fall back to period_end."""
        rows = [
            make_csv_row('jpdei_cor:EDINETCodeDEI', 'FilingDateInstant', 'E05123'),
            make_csv_row('jpdei_cor:FilerNameInJapaneseDEI', 'FilingDateInstant', 'テスト'),
            make_csv_row('jpdei_cor:CurrentPeriodEndDateDEI', 'FilingDateInstant', '2024-09-30'),
            # No submission_date
        ]
        doc = make_mock_doc('S100FB', '160', rows)
        r = parse_semi_annual_report(doc)
        assert r.filing_date == date(2024, 9, 30)
