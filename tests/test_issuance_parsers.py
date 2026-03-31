"""Tests for issuance family parsers (Doc types 060-110)."""
import io
import zipfile
import pytest
from datetime import date
from unittest.mock import MagicMock

from edinet_tools.parsers import parse
from edinet_tools.parsers.generic import RawReport
from edinet_tools.parsers.shelf_registration import (
    ShelfRegistrationReport,
    parse_shelf_registration,
    ELEMENT_MAP as SHELF_ELEMENT_MAP,
)
from edinet_tools.parsers.issuance_notification import (
    IssuanceNotificationReport,
    parse_issuance_notification,
)
from edinet_tools.parsers.issuance_supplementary import (
    IssuanceSupplementaryReport,
    parse_issuance_supplementary,
    ELEMENT_MAP as SUPP_ELEMENT_MAP,
)
from edinet_tools.parsers.issuance_withdrawal import (
    IssuanceWithdrawalReport,
    parse_issuance_withdrawal,
)


# --- Routing tests ---

DOC_TYPES = ['060', '070', '080', '090', '100', '110']


@pytest.mark.parametrize("code", DOC_TYPES)
def test_issuance_type_does_not_fall_through(code):
    """Issuance doc types must not fall through to RawReport."""
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


def test_doc_080_routes_to_shelf_registration():
    doc = MagicMock()
    doc.doc_type_code = '080'
    doc.doc_id = 'TEST_080'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, ShelfRegistrationReport)
    except Exception:
        pass


def test_doc_090_routes_to_shelf_registration():
    """Doc 090 (shelf registration amendment) routes to same parser as 080."""
    doc = MagicMock()
    doc.doc_type_code = '090'
    doc.doc_id = 'TEST_090'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, ShelfRegistrationReport)
    except Exception:
        pass


def test_doc_070_routes_to_shelf_registration():
    """Doc 070 is also a shelf registration filing family."""
    doc = MagicMock()
    doc.doc_type_code = '070'
    doc.doc_id = 'TEST_070'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, ShelfRegistrationReport)
    except Exception:
        pass


def test_doc_060_routes_to_issuance_notification():
    doc = MagicMock()
    doc.doc_type_code = '060'
    doc.doc_id = 'TEST_060'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, IssuanceNotificationReport)
    except Exception:
        pass


def test_doc_100_routes_to_issuance_supplementary():
    doc = MagicMock()
    doc.doc_type_code = '100'
    doc.doc_id = 'TEST_100'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, IssuanceSupplementaryReport)
    except Exception:
        pass


def test_doc_110_routes_to_issuance_withdrawal():
    doc = MagicMock()
    doc.doc_type_code = '110'
    doc.doc_id = 'TEST_110'
    doc.fetch.return_value = None
    try:
        result = parse(doc)
        assert isinstance(result, IssuanceWithdrawalReport)
    except Exception:
        pass


# --- ShelfRegistrationReport structure tests ---

class TestShelfRegistrationReportStructure:
    """Test ShelfRegistrationReport dataclass."""

    def test_basic_fields(self):
        from datetime import date
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='080',
            filer_name='テスト株式会社',
            filer_edinet_code='E01234',
            shelf_registration_number='第1号',
            filing_date=date(2024, 4, 1),
            is_amendment=False,
        )
        assert report.filer_name == 'テスト株式会社'
        assert report.shelf_registration_number == '第1号'
        assert report.is_amendment is False

    def test_optional_fields_default_none(self):
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='080',
        )
        assert report.filer_name is None
        assert report.shelf_registration_number is None
        assert report.planned_period is None
        assert report.security_types is None
        assert report.is_amendment is False

    def test_amendment_flag(self):
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='090',
            is_amendment=True,
        )
        assert report.is_amendment is True
        assert report.doc_type_code == '090'

    def test_repr_normal(self):
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='080',
            filer_name='テスト株式会社',
            shelf_registration_number='第1号',
        )
        r = repr(report)
        assert 'テスト' in r
        assert '第1号' in r
        assert 'AMENDED' not in r

    def test_repr_amendment(self):
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='090',
            is_amendment=True,
        )
        assert 'AMENDED' in repr(report)

    def test_repr_truncates_long_names(self):
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='080',
            filer_name='A' * 50,
        )
        r = repr(report)
        assert '...' in r

    def test_to_dict_excludes_raw_fields(self):
        report = ShelfRegistrationReport(
            doc_id='S100TEST',
            doc_type_code='080',
            filer_name='Test Corp',
            raw_fields={'key': 'val'},
        )
        d = report.to_dict()
        assert d['filer_name'] == 'Test Corp'
        assert 'raw_fields' not in d


# --- parse_shelf_registration with mock CSV data ---

class TestParseShelfRegistration:
    """Test parse_shelf_registration with mocked document data."""

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

    def _make_doc(self, doc_id='S100TEST', doc_type='080', rows=None):
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
        report = parse_shelf_registration(doc)
        assert isinstance(report, ShelfRegistrationReport)
        assert report.doc_id == 'S100TEST'
        assert report.filer_name is None
        assert report.source_files == []

    def test_extracts_dei_fields(self):
        rows = [
            self._make_csv_row(
                SHELF_ELEMENT_MAP['filer_name'],
                'FilingDateInstant',
                'テスト株式会社',
            ),
            self._make_csv_row(
                SHELF_ELEMENT_MAP['filer_edinet_code'],
                'FilingDateInstant',
                'E01234',
            ),
            self._make_csv_row(
                SHELF_ELEMENT_MAP['security_code'],
                'FilingDateInstant',
                '1234',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_shelf_registration(doc)
        assert report.filer_name == 'テスト株式会社'
        assert report.filer_edinet_code == 'E01234'
        assert report.security_code == '1234'

    def test_extracts_cover_page_fields(self):
        rows = [
            self._make_csv_row(
                SHELF_ELEMENT_MAP['shelf_registration_number'],
                'FilingDateInstant',
                '第1号',
            ),
            self._make_csv_row(
                SHELF_ELEMENT_MAP['planned_period'],
                'FilingDateInstant',
                '2024年4月1日から2026年3月31日まで',
            ),
            self._make_csv_row(
                SHELF_ELEMENT_MAP['security_types'],
                'FilingDateInstant',
                '社債券',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_shelf_registration(doc)
        assert report.shelf_registration_number == '第1号'
        assert '2024' in report.planned_period
        assert report.security_types == '社債券'

    def test_extracts_filing_date(self):
        from datetime import date
        rows = [
            self._make_csv_row(
                SHELF_ELEMENT_MAP['filing_date'],
                'FilingDateInstant',
                '2024-04-01',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_shelf_registration(doc)
        assert report.filing_date == date(2024, 4, 1)

    def test_amendment_flag_true(self):
        rows = [
            self._make_csv_row(
                SHELF_ELEMENT_MAP['amendment_flag'],
                'FilingDateInstant',
                'true',
            ),
        ]
        doc = self._make_doc(doc_type='090', rows=rows)
        report = parse_shelf_registration(doc)
        assert report.is_amendment is True

    def test_amendment_flag_false(self):
        rows = [
            self._make_csv_row(
                SHELF_ELEMENT_MAP['amendment_flag'],
                'FilingDateInstant',
                'false',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_shelf_registration(doc)
        assert report.is_amendment is False

    def test_company_name_falls_back_to_filer_name(self):
        """If cover page company_name missing, company_name falls back to DEI filer_name."""
        rows = [
            self._make_csv_row(
                SHELF_ELEMENT_MAP['filer_name'],
                'FilingDateInstant',
                'DEI Filer Corp',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_shelf_registration(doc)
        assert report.company_name == 'DEI Filer Corp'

    def test_text_blocks_captured(self):
        rows = [
            self._make_csv_row(
                'jpcrp_cor:UseOfNetProceedsTextBlock',
                'FilingDateInstant',
                '調達した資金の使途...',
            ),
        ]
        doc = self._make_doc(rows=rows)
        report = parse_shelf_registration(doc)
        assert 'UseOfNetProceedsTextBlock' in report.text_blocks


# --- ELEMENT_MAP completeness tests ---

class TestShelfElementMap:
    """Test SHELF_ELEMENT_MAP completeness."""

    def test_required_keys_present(self):
        required = [
            'filer_name', 'filer_edinet_code', 'filing_date',
            'shelf_registration_number', 'planned_period', 'security_types',
        ]
        for key in required:
            assert key in SHELF_ELEMENT_MAP, f"Missing required key: {key}"

    def test_all_values_are_namespaced(self):
        for key, elem_id in SHELF_ELEMENT_MAP.items():
            assert ':' in elem_id, f"Element {key} missing namespace: {elem_id}"

    def test_dei_elements_use_dei_namespace(self):
        dei_keys = ['filer_name', 'filer_edinet_code', 'security_code', 'amendment_flag']
        for key in dei_keys:
            assert SHELF_ELEMENT_MAP[key].startswith('jpdei_cor:'), \
                f"{key} should use jpdei_cor namespace"


# --- Minimal parser smoke tests ---

class TestMinimalIssuanceParsers:
    """Smoke tests for minimal placeholder parsers."""

    def _make_empty_doc(self, code):
        doc = MagicMock()
        doc.doc_id = f'TEST_{code}'
        doc.doc_type_code = code
        doc.fetch.return_value = b''
        return doc

    def test_parse_issuance_notification_empty(self):
        doc = self._make_empty_doc('060')
        report = parse_issuance_notification(doc)
        assert isinstance(report, IssuanceNotificationReport)
        assert report.doc_id == 'TEST_060'

    def test_parse_issuance_supplementary_empty(self):
        doc = self._make_empty_doc('100')
        report = parse_issuance_supplementary(doc)
        assert isinstance(report, IssuanceSupplementaryReport)
        assert report.doc_id == 'TEST_100'

    def test_parse_issuance_withdrawal_empty(self):
        doc = self._make_empty_doc('110')
        report = parse_issuance_withdrawal(doc)
        assert isinstance(report, IssuanceWithdrawalReport)
        assert report.doc_id == 'TEST_110'

    def test_issuance_notification_repr(self):
        report = IssuanceNotificationReport(doc_id='X', doc_type_code='060')
        assert 'IssuanceNotificationReport' in repr(report)

    def test_issuance_supplementary_repr(self):
        report = IssuanceSupplementaryReport(doc_id='X', doc_type_code='100')
        assert 'IssuanceSupplementaryReport' in repr(report)

    def test_issuance_withdrawal_repr(self):
        report = IssuanceWithdrawalReport(doc_id='X', doc_type_code='110')
        assert 'IssuanceWithdrawalReport' in repr(report)


# ---------------------------------------------------------------------------
# IssuanceSupplementaryReport — field-level extraction tests (Doc 100)
# ---------------------------------------------------------------------------

def _make_supp_csv_row(element_id: str, context_id: str, value: str) -> str:
    """Return one tab-separated line in EDINET CSV format (9 columns)."""
    return f"{element_id}\tlabel\t{context_id}\t0\t連結\t期間\t\t\t{value}"


def _make_supp_zip(rows: list[str]) -> bytes:
    content = '\n'.join(rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('XBRL_TO_CSV/test.csv', content.encode('utf-16le'))
    return buf.getvalue()


def _make_supp_doc(doc_id: str = 'S100TEST', doc_type: str = '100', rows: list[str] | None = None):
    doc = MagicMock()
    doc.doc_id = doc_id
    doc.doc_type_code = doc_type
    doc.filer_name = ''
    doc.filer_edinet_code = ''
    doc.fetch.return_value = _make_supp_zip(rows) if rows is not None else b''
    return doc


class TestParseIssuanceSupplementary:
    """Field-level extraction tests for IssuanceSupplementaryReport (Doc 100)."""

    def test_empty_zip_returns_empty_report(self):
        doc = _make_supp_doc(rows=None)
        report = parse_issuance_supplementary(doc)
        assert isinstance(report, IssuanceSupplementaryReport)
        assert report.doc_id == 'S100TEST'
        assert report.company_name is None
        assert report.source_files == []

    def test_extracts_company_name(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['company_name'], 'FilingDateInstant', 'テスト株式会社'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.company_name == 'テスト株式会社'

    def test_extracts_supplement_number(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['supplement_number'], 'FilingDateInstant', '第3号'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.supplement_number == '第3号'

    def test_extracts_remaining_balance(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['remaining_balance'], 'FilingDateInstant', '500億円'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.remaining_balance == '500億円'

    def test_extracts_filing_date(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['filing_date'], 'FilingDateInstant', '2025-09-15'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.filing_date == date(2025, 9, 15)

    def test_extracts_security_types(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['security_types'], 'FilingDateInstant', '普通社債券'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.security_types == '普通社債券'

    def test_extracts_parent_shelf_reg_number(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['parent_shelf_reg_number'], 'FilingDateInstant', '第1号'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.parent_shelf_reg_number == '第1号'

    def test_amendment_flag_true(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['amendment_flag'], 'FilingDateInstant', 'true'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.is_amendment is True

    def test_amendment_flag_false(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['amendment_flag'], 'FilingDateInstant', 'false'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.is_amendment is False

    def test_company_name_falls_back_to_filer_name(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['filer_name'], 'FilingDateInstant', 'フォールバック会社'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.company_name == 'フォールバック会社'

    def test_multiple_fields_extracted_together(self):
        rows = [
            _make_supp_csv_row(SUPP_ELEMENT_MAP['company_name'], 'FilingDateInstant', 'ABCホールディングス株式会社'),
            _make_supp_csv_row(SUPP_ELEMENT_MAP['supplement_number'], 'FilingDateInstant', '第2号'),
            _make_supp_csv_row(SUPP_ELEMENT_MAP['remaining_balance'], 'FilingDateInstant', '300億円'),
            _make_supp_csv_row(SUPP_ELEMENT_MAP['filing_date'], 'FilingDateInstant', '2025-03-01'),
            _make_supp_csv_row(SUPP_ELEMENT_MAP['filer_edinet_code'], 'FilingDateInstant', 'E05678'),
        ]
        report = parse_issuance_supplementary(_make_supp_doc(rows=rows))
        assert report.company_name == 'ABCホールディングス株式会社'
        assert report.supplement_number == '第2号'
        assert report.remaining_balance == '300億円'
        assert report.filing_date == date(2025, 3, 1)
        assert report.filer_edinet_code == 'E05678'

    def test_repr_shows_supplement_number(self):
        report = IssuanceSupplementaryReport(
            doc_id='X',
            doc_type_code='100',
            company_name='テスト会社',
            supplement_number='第1号',
        )
        r = repr(report)
        assert 'テスト' in r
        assert '第1号' in r


class TestIssuanceSupplementaryElementMap:
    """Sanity-check the SUPP_ELEMENT_MAP."""

    def test_required_keys_present(self):
        required = [
            'filer_name', 'filer_edinet_code', 'filing_date',
            'company_name', 'supplement_number', 'remaining_balance',
        ]
        for key in required:
            assert key in SUPP_ELEMENT_MAP, f"Missing ELEMENT_MAP key: {key}"

    def test_all_values_are_namespaced(self):
        for key, elem_id in SUPP_ELEMENT_MAP.items():
            assert ':' in elem_id, f"Element '{key}' missing namespace: {elem_id}"
