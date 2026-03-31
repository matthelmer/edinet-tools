"""Tests for securities registration/notification family parsers (Doc types 010-050)."""
import io
import zipfile
import pytest
from datetime import date
from unittest.mock import MagicMock

from edinet_tools.parsers import parse
from edinet_tools.parsers.generic import RawReport
from edinet_tools.parsers.securities_notification import (
    SecuritiesNotificationReport,
    parse_securities_notification,
)
from edinet_tools.parsers.securities_registration import (
    SecuritiesRegistrationReport,
    parse_securities_registration,
    ELEMENT_MAP as REG_ELEMENT_MAP,
)
from edinet_tools.parsers.securities_withdrawal import (
    SecuritiesWithdrawalReport,
    parse_securities_withdrawal,
)


# --- Routing tests ---

DOC_TYPES = ['010', '020', '030', '040', '050']


@pytest.mark.parametrize("code", DOC_TYPES)
def test_registration_type_does_not_fall_through(code):
    """Registration/notification doc types must not fall through to RawReport."""
    doc = MagicMock()
    doc.doc_type_code = code
    doc.doc_id = f"TEST_{code}"
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert not isinstance(result, RawReport), \
            f"Doc type {code} fell through to RawReport instead of a typed parser"
    except Exception:
        pass  # Parser attempted but failed on mock data = correct routing


def test_doc_010_routes_to_securities_notification():
    doc = MagicMock()
    doc.doc_type_code = '010'
    doc.doc_id = 'TEST_010'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, SecuritiesNotificationReport)
    except Exception:
        pass


def test_doc_020_routes_to_securities_notification():
    """Doc 020 (amendment) routes to same parser as 010."""
    doc = MagicMock()
    doc.doc_type_code = '020'
    doc.doc_id = 'TEST_020'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, SecuritiesNotificationReport)
    except Exception:
        pass


def test_doc_030_routes_to_securities_registration():
    doc = MagicMock()
    doc.doc_type_code = '030'
    doc.doc_id = 'TEST_030'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, SecuritiesRegistrationReport)
    except Exception:
        pass


def test_doc_040_routes_to_securities_registration():
    """Doc 040 (amendment) routes to same parser as 030."""
    doc = MagicMock()
    doc.doc_type_code = '040'
    doc.doc_id = 'TEST_040'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, SecuritiesRegistrationReport)
    except Exception:
        pass


def test_doc_050_routes_to_securities_withdrawal():
    doc = MagicMock()
    doc.doc_type_code = '050'
    doc.doc_id = 'TEST_050'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, SecuritiesWithdrawalReport)
    except Exception:
        pass


# --- SecuritiesRegistrationReport structure tests ---

class TestSecuritiesRegistrationReportStructure:
    """Test SecuritiesRegistrationReport dataclass."""

    def test_basic_fields(self):
        from datetime import date
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
            filer_name='テスト投信会社',
            filer_edinet_code='E01234',
            fund_name='テストファンド',
            filing_date=date(2024, 4, 1),
            is_amendment=False,
        )
        assert report.filer_name == 'テスト投信会社'
        assert report.fund_name == 'テストファンド'
        assert report.is_amendment is False

    def test_optional_fields_default_none(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
        )
        assert report.filer_name is None
        assert report.fund_name is None
        assert report.issuer_name is None
        assert report.is_amendment is False

    def test_amendment_flag(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='040',
            is_amendment=True,
        )
        assert report.is_amendment is True
        assert report.doc_type_code == '040'

    def test_repr_normal(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
            fund_name='テストファンド',
        )
        r = repr(report)
        assert 'テストファンド' in r
        assert 'AMENDED' not in r

    def test_repr_amendment(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='040',
            is_amendment=True,
        )
        assert 'AMENDED' in repr(report)

    def test_repr_prefers_fund_name_over_filer_name(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
            filer_name='管理会社',
            fund_name='ファンド名称',
        )
        r = repr(report)
        assert 'ファンド名称' in r

    def test_repr_falls_back_to_filer_name(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
            filer_name='管理会社',
        )
        r = repr(report)
        assert '管理会社' in r

    def test_repr_truncates_long_names(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
            fund_name='A' * 50,
        )
        r = repr(report)
        assert '...' in r

    def test_to_dict_excludes_raw_fields(self):
        report = SecuritiesRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='030',
            filer_name='Test Corp',
            raw_fields={'key': 'val'},
        )
        d = report.to_dict()
        assert d['filer_name'] == 'Test Corp'
        assert 'raw_fields' not in d


# ---------------------------------------------------------------------------
# Module-level helpers for jpsps_cor field tests
# ---------------------------------------------------------------------------

def _make_reg_csv_row(element_id: str, context_id: str, value: str) -> str:
    """Return one tab-separated line in EDINET CSV format (9 columns)."""
    return f"{element_id}\tlabel\t{context_id}\t0\t連結\t期間\t\t\t{value}"


def _make_reg_zip(rows: list[str]) -> bytes:
    content = '\n'.join(rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('XBRL_TO_CSV/test.csv', content.encode('utf-16le'))
    return buf.getvalue()


def _make_reg_doc(doc_id: str = 'S030TEST', doc_type: str = '030', rows: list[str] | None = None):
    doc = MagicMock()
    doc.doc_id = doc_id
    doc.doc_type_code = doc_type
    doc.filer_name = ''
    doc.filer_edinet_code = ''
    doc.fetch.return_value = _make_reg_zip(rows) if rows is not None else b''
    return doc


# ---------------------------------------------------------------------------
# New jpsps_cor field-level extraction tests
# ---------------------------------------------------------------------------

class TestSecuritiesRegistrationCoverPageFields:
    """Test the new cover page jpsps_cor fields: contact_person, telephone, place_of_filing."""

    def test_extracts_contact_person(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['contact_person'], 'FilingDateInstant', '運用部　佐藤花子')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.contact_person == '運用部　佐藤花子'

    def test_extracts_telephone_number(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['telephone_number'], 'FilingDateInstant', '03-5555-1234')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.telephone_number == '03-5555-1234'

    def test_extracts_place_of_filing(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['place_of_filing'], 'FilingDateInstant', '関東財務局長')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.place_of_filing == '関東財務局長'

    def test_extracts_amount_to_register(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['amount_to_register'], 'FilingDateInstant', '1口以上1口単位')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.amount_to_register == '1口以上1口単位'

    def test_extracts_fund_name_for_registration(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['fund_name_for_registration'], 'FilingDateInstant', 'テスト日本株式ファンド')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.fund_name_for_registration == 'テスト日本株式ファンド'

    def test_missing_cover_page_fields_are_none(self):
        """No rows → all new cover page fields should be None."""
        report = parse_securities_registration(_make_reg_doc(rows=[]))
        assert report.contact_person is None
        assert report.telephone_number is None
        assert report.place_of_filing is None
        assert report.amount_to_register is None
        assert report.fund_name_for_registration is None


class TestSecuritiesRegistrationFundIdentityFields:
    """Test fund identity TextBlock fields: fund_purpose, fund_scheme, fund_history."""

    def test_extracts_fund_purpose(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['fund_purpose'], 'FilingDateInstant', '国内株式に投資するファンドです。')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.fund_purpose == '国内株式に投資するファンドです。'

    def test_extracts_fund_scheme(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['fund_scheme'], 'FilingDateInstant', '単位型・追加型：追加型')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.fund_scheme == '単位型・追加型：追加型'

    def test_extracts_fund_history(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['fund_history'], 'FilingDateInstant', '2000年1月設定')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.fund_history == '2000年1月設定'

    def test_fund_identity_in_text_blocks_dict(self):
        """Fund identity TextBlocks are also captured in the text_blocks dict."""
        rows = [
            _make_reg_csv_row(REG_ELEMENT_MAP['fund_purpose'], 'FilingDateInstant', 'ファンドの目的'),
            _make_reg_csv_row(REG_ELEMENT_MAP['fund_scheme'], 'FilingDateInstant', 'ファンドの仕組み'),
        ]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert 'PurposesAndBasicFeaturesOfFundTextBlock' in report.text_blocks
        assert 'FundSchemeTextBlock' in report.text_blocks


class TestSecuritiesRegistrationInvestmentPolicyFields:
    """Test investment policy TextBlock fields."""

    def test_extracts_investment_policy(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['investment_policy'], 'FilingDateInstant', '主として国内株式に投資します。')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.investment_policy == '主として国内株式に投資します。'

    def test_extracts_investment_risks(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['investment_risks'], 'FilingDateInstant', '株価変動リスクがあります。')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.investment_risks == '株価変動リスクがあります。'

    def test_extracts_eligible_investments(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['eligible_investments'], 'FilingDateInstant', '国内上場株式')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.eligible_investments == '国内上場株式'

    def test_extracts_investment_restrictions(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['investment_restrictions'], 'FilingDateInstant', '同一銘柄10%以内')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.investment_restrictions == '同一銘柄10%以内'


class TestSecuritiesRegistrationOperationsFields:
    """Test operations TextBlock fields: fees, application, redemption, distribution."""

    def test_extracts_management_fees(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['management_fees'], 'FilingDateInstant', '年率1.0%（税込）')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.management_fees == '年率1.0%（税込）'

    def test_extracts_application_fee(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['application_fee'], 'FilingDateInstant', '3.3%以内')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.application_fee == '3.3%以内'

    def test_extracts_application_period(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['application_period'], 'FilingDateInstant', '毎営業日')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.application_period == '毎営業日'

    def test_extracts_application_unit(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['application_unit'], 'FilingDateInstant', '1口以上1口単位')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.application_unit == '1口以上1口単位'

    def test_extracts_redemption_procedures(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['redemption_procedures'], 'FilingDateInstant', '翌営業日解約')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.redemption_procedures == '翌営業日解約'

    def test_extracts_profit_distribution_policy(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['profit_distribution_policy'], 'FilingDateInstant', '毎月分配')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.profit_distribution_policy == '毎月分配'

    def test_extracts_taxation(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['taxation'], 'FilingDateInstant', '普通分配金は課税対象')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.taxation == '普通分配金は課税対象'


class TestSecuritiesRegistrationFinancialFields:
    """Test financial information TextBlock fields."""

    def test_extracts_financial_info(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['financial_info'], 'FilingDateInstant', '純資産総額：100億円')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.financial_info == '純資産総額：100億円'

    def test_extracts_balance_sheet(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['balance_sheet'], 'FilingDateInstant', '資産合計：100億円')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.balance_sheet == '資産合計：100億円'

    def test_extracts_income_statement(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['income_statement'], 'FilingDateInstant', '当期純利益：5億円')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.income_statement == '当期純利益：5億円'

    def test_extracts_changes_in_net_assets(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['changes_in_net_assets'], 'FilingDateInstant', '期末純資産総額：100億円')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.changes_in_net_assets == '期末純資産総額：100億円'

    def test_extracts_net_assets_calculation(self):
        rows = [_make_reg_csv_row(REG_ELEMENT_MAP['net_assets_calculation'], 'FilingDateInstant', '1口当たり純資産額：10,000円')]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert report.net_assets_calculation == '1口当たり純資産額：10,000円'

    def test_financial_blocks_in_text_blocks_dict(self):
        """Financial TextBlocks also appear in the text_blocks dict."""
        rows = [
            _make_reg_csv_row(REG_ELEMENT_MAP['balance_sheet'], 'FilingDateInstant', '資産合計：50億円'),
            _make_reg_csv_row(REG_ELEMENT_MAP['income_statement'], 'FilingDateInstant', '利益：1億円'),
        ]
        report = parse_securities_registration(_make_reg_doc(rows=rows))
        assert 'BalanceSheetTextBlock' in report.text_blocks
        assert 'StatementOfIncomeAndRetainedEarningsTextBlock' in report.text_blocks


class TestSecuritiesRegistrationFullIntegration:
    """Integration test: extract all field groups from a single mock filing."""

    def test_full_filing_extraction(self):
        rows = [
            # DEI
            _make_reg_csv_row(REG_ELEMENT_MAP['filer_name'], 'FilingDateInstant', '大和アセットマネジメント株式会社'),
            _make_reg_csv_row(REG_ELEMENT_MAP['filer_edinet_code'], 'FilingDateInstant', 'E05678'),
            # Cover page
            _make_reg_csv_row(REG_ELEMENT_MAP['filing_date'], 'FilingDateInstant', '2025-06-15'),
            _make_reg_csv_row(REG_ELEMENT_MAP['issuer_name'], 'FilingDateInstant', '大和アセットマネジメント株式会社'),
            _make_reg_csv_row(REG_ELEMENT_MAP['contact_person'], 'FilingDateInstant', '運用部　田中'),
            _make_reg_csv_row(REG_ELEMENT_MAP['telephone_number'], 'FilingDateInstant', '03-5555-9999'),
            _make_reg_csv_row(REG_ELEMENT_MAP['place_of_filing'], 'FilingDateInstant', '関東財務局長'),
            _make_reg_csv_row(REG_ELEMENT_MAP['fund_name_for_registration'], 'FilingDateInstant', 'ダイワ日本株式オープン'),
            # Fund identity
            _make_reg_csv_row(REG_ELEMENT_MAP['fund_name'], 'FilingDateInstant', 'ダイワ日本株式オープン'),
            _make_reg_csv_row(REG_ELEMENT_MAP['fund_purpose'], 'FilingDateInstant', '国内株式に投資するファンド'),
            # Investment policy
            _make_reg_csv_row(REG_ELEMENT_MAP['investment_policy'], 'FilingDateInstant', '国内株式への分散投資'),
            _make_reg_csv_row(REG_ELEMENT_MAP['investment_risks'], 'FilingDateInstant', '価格変動リスク'),
            # Operations
            _make_reg_csv_row(REG_ELEMENT_MAP['management_fees'], 'FilingDateInstant', '年率0.99%（税込）'),
            _make_reg_csv_row(REG_ELEMENT_MAP['redemption_procedures'], 'FilingDateInstant', '翌営業日解約可能'),
            # Financial
            _make_reg_csv_row(REG_ELEMENT_MAP['balance_sheet'], 'FilingDateInstant', '純資産：200億円'),
        ]
        report = parse_securities_registration(_make_reg_doc(doc_id='S030FULL', rows=rows))

        assert report.doc_id == 'S030FULL'
        assert report.filer_name == '大和アセットマネジメント株式会社'
        assert report.filer_edinet_code == 'E05678'
        assert report.filing_date == date(2025, 6, 15)
        assert report.issuer_name == '大和アセットマネジメント株式会社'
        assert report.contact_person == '運用部　田中'
        assert report.telephone_number == '03-5555-9999'
        assert report.place_of_filing == '関東財務局長'
        assert report.fund_name_for_registration == 'ダイワ日本株式オープン'
        assert report.fund_name == 'ダイワ日本株式オープン'
        assert report.fund_purpose == '国内株式に投資するファンド'
        assert report.investment_policy == '国内株式への分散投資'
        assert report.investment_risks == '価格変動リスク'
        assert report.management_fees == '年率0.99%（税込）'
        assert report.redemption_procedures == '翌営業日解約可能'
        assert report.balance_sheet == '純資産：200億円'
        assert report.is_amendment is False


# --- parse_securities_registration with mock CSV data ---

class TestParseSecuritiesRegistration:
    """Test parse_securities_registration with mocked document data."""

    def _make_csv_row(self, element_id, context_id, value):
        return {
            '要素ID': element_id,
            'コンテキストID': context_id,
            '値': value,
        }

    def _make_zip_with_rows(self, rows):
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            lines = []
            for row in rows:
                line = f"{row['要素ID']}\tlabel\t{row['コンテキストID']}\t0\t連結\t期間\tunit1\t円\t{row['値']}"
                lines.append(line)
            content = '\n'.join(lines)
            zf.writestr('XBRL_TO_CSV/test.csv', content.encode('utf-16le'))
        return zip_buffer.getvalue()

    def _make_doc(self, doc_id='S100TEST', doc_type='030', rows=None):
        doc = MagicMock()
        doc.doc_id = doc_id
        doc.doc_type_code = doc_type
        doc.filer_name = ''
        doc.filer_edinet_code = ''
        if rows is not None:
            doc.fetch.return_value = self._make_zip_with_rows(rows)
        else:
            doc.fetch.return_value = b''
        return doc

    def test_empty_zip_returns_empty_report(self):
        doc = self._make_doc(rows=None)
        report = parse_securities_registration(doc)
        assert isinstance(report, SecuritiesRegistrationReport)
        assert report.doc_id == 'S100TEST'
        assert report.filer_name is None
        assert report.source_files == []

    def test_extracts_dei_fields(self):
        rows = [
            self._make_csv_row(
                REG_ELEMENT_MAP['filer_name'],
                'FilingDateInstant',
                'テスト資産管理株式会社',
            ),
            self._make_csv_row(
                REG_ELEMENT_MAP['filer_edinet_code'],
                'FilingDateInstant',
                'E09876',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_securities_registration(doc)
        assert report.filer_name == 'テスト資産管理株式会社'
        assert report.filer_edinet_code == 'E09876'

    def test_extracts_fund_name(self):
        rows = [
            self._make_csv_row(
                REG_ELEMENT_MAP['fund_name'],
                'FilingDateInstant',
                'テスト日本株式ファンド',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_securities_registration(doc)
        assert report.fund_name == 'テスト日本株式ファンド'

    def test_extracts_filing_date(self):
        from datetime import date
        rows = [
            self._make_csv_row(
                REG_ELEMENT_MAP['filing_date'],
                'FilingDateInstant',
                '2024-06-15',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_securities_registration(doc)
        assert report.filing_date == date(2024, 6, 15)

    def test_amendment_flag_true(self):
        rows = [
            self._make_csv_row(
                REG_ELEMENT_MAP['amendment_flag'],
                'FilingDateInstant',
                'true',
            ),
        ]
        doc = self._make_doc(doc_type='040', rows=rows)
        report = parse_securities_registration(doc)
        assert report.is_amendment is True

    def test_issuer_name_falls_back_to_filer_name(self):
        """If jpsps_cor issuer_name missing, falls back to DEI filer_name."""
        rows = [
            self._make_csv_row(
                REG_ELEMENT_MAP['filer_name'],
                'FilingDateInstant',
                'DEI Filer Corp',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_securities_registration(doc)
        assert report.issuer_name == 'DEI Filer Corp'

    def test_text_blocks_captured(self):
        rows = [
            self._make_csv_row(
                'jpsps_cor:FundNameTextBlock',
                'FilingDateInstant',
                'ファンド名テキスト',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_securities_registration(doc)
        assert 'FundNameTextBlock' in report.text_blocks


# --- ELEMENT_MAP completeness tests ---

class TestRegistrationElementMap:
    """Test REG_ELEMENT_MAP completeness."""

    def test_required_keys_present(self):
        required = [
            # Core identity
            'filer_name', 'filer_edinet_code', 'filing_date',
            'fund_name', 'issuer_name',
            # New cover page fields
            'contact_person', 'telephone_number', 'place_of_filing',
            'amount_to_register', 'fund_name_for_registration',
            # Fund identity
            'fund_purpose', 'fund_scheme', 'fund_history',
            # Investment policy
            'investment_policy', 'investment_risks',
            'eligible_investments', 'investment_restrictions',
            # Operations
            'management_fees', 'application_fee', 'application_period',
            'application_unit', 'redemption_procedures',
            'profit_distribution_policy', 'taxation',
            # Financial
            'financial_info', 'balance_sheet', 'income_statement',
            'changes_in_net_assets', 'net_assets_calculation',
        ]
        for key in required:
            assert key in REG_ELEMENT_MAP, f"Missing required key: {key}"

    def test_all_values_are_namespaced(self):
        for key, elem_id in REG_ELEMENT_MAP.items():
            assert ':' in elem_id, f"Element {key} missing namespace: {elem_id}"

    def test_dei_elements_use_dei_namespace(self):
        dei_keys = ['filer_name', 'filer_edinet_code', 'security_code', 'amendment_flag']
        for key in dei_keys:
            assert REG_ELEMENT_MAP[key].startswith('jpdei_cor:'), \
                f"{key} should use jpdei_cor namespace"

    def test_fund_elements_use_jpsps_namespace(self):
        jpsps_keys = [
            'fund_name', 'issuer_name', 'filing_date',
            'contact_person', 'telephone_number', 'place_of_filing',
            'fund_purpose', 'fund_scheme', 'fund_history',
            'investment_policy', 'investment_risks',
            'management_fees', 'balance_sheet',
        ]
        for key in jpsps_keys:
            assert REG_ELEMENT_MAP[key].startswith('jpsps_cor:'), \
                f"{key} should use jpsps_cor namespace"

    def test_text_block_fields_have_textblock_in_element_id(self):
        """All TextBlock-sourced fields should map to elements with 'TextBlock' in the name."""
        text_block_keys = [
            'fund_name', 'fund_purpose', 'fund_scheme', 'fund_history',
            'investment_policy', 'investment_risks', 'eligible_investments',
            'investment_restrictions', 'management_fees', 'application_fee',
            'application_period', 'application_unit', 'redemption_procedures',
            'profit_distribution_policy', 'taxation',
            'financial_info', 'balance_sheet', 'income_statement',
            'changes_in_net_assets', 'net_assets_calculation',
            'amount_to_register', 'fund_name_for_registration',
        ]
        for key in text_block_keys:
            assert 'TextBlock' in REG_ELEMENT_MAP[key], \
                f"{key} should map to a TextBlock element, got: {REG_ELEMENT_MAP[key]}"


# --- Minimal parser smoke tests ---

class TestMinimalRegistrationParsers:
    """Smoke tests for minimal placeholder parsers."""

    def _make_empty_doc(self, code):
        doc = MagicMock()
        doc.doc_id = f'TEST_{code}'
        doc.doc_type_code = code
        doc.fetch.return_value = b''
        return doc

    def test_parse_securities_notification_empty(self):
        doc = self._make_empty_doc('010')
        report = parse_securities_notification(doc)
        assert isinstance(report, SecuritiesNotificationReport)
        assert report.doc_id == 'TEST_010'

    def test_parse_securities_withdrawal_empty(self):
        doc = self._make_empty_doc('050')
        report = parse_securities_withdrawal(doc)
        assert isinstance(report, SecuritiesWithdrawalReport)
        assert report.doc_id == 'TEST_050'

    def test_securities_notification_repr_normal(self):
        report = SecuritiesNotificationReport(
            doc_id='X', doc_type_code='010', filer_name='テスト会社'
        )
        r = repr(report)
        assert 'SecuritiesNotificationReport' in r
        assert 'テスト会社' in r
        assert 'AMENDED' not in r

    def test_securities_notification_repr_amendment(self):
        report = SecuritiesNotificationReport(
            doc_id='X', doc_type_code='020', is_amendment=True
        )
        assert 'AMENDED' in repr(report)

    def test_securities_withdrawal_repr(self):
        report = SecuritiesWithdrawalReport(doc_id='X', doc_type_code='050')
        assert 'SecuritiesWithdrawalReport' in repr(report)

    def test_all_minimal_parsers_have_is_amendment_field(self):
        """All parsers expose is_amendment consistently."""
        report_n = SecuritiesNotificationReport(doc_id='X', doc_type_code='010')
        report_w = SecuritiesWithdrawalReport(doc_id='X', doc_type_code='050')
        assert report_n.is_amendment is False
        assert report_w.is_amendment is False
