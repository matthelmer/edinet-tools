"""
Tests for InternalControlReport parser (Doc 235/236).

Covers field-level extraction from mock XBRL CSV data, amendment detection,
text block capture, and the parse() router.
"""
import io
import zipfile
import pytest
from datetime import date
from unittest.mock import Mock

from edinet_tools.parsers import parse
from edinet_tools.parsers.internal_control import (
    InternalControlReport,
    parse_internal_control,
    ELEMENT_MAP,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv_row(element_id: str, context_id: str, value: str) -> str:
    """Return one tab-separated CSV line in EDINET format (9 columns)."""
    return f"{element_id}\tlabel\t{context_id}\t0\t連結\t期間\t\t\t{value}"


def _make_zip(rows: list[str]) -> bytes:
    """Wrap CSV rows into a UTF-16LE encoded ZIP as EDINET produces."""
    content = '\n'.join(rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('XBRL_TO_CSV/test.csv', content.encode('utf-16le'))
    return buf.getvalue()


def _make_doc(doc_id: str = 'S100TEST', doc_type: str = '235', rows: list[str] | None = None) -> Mock:
    doc = Mock()
    doc.doc_id = doc_id
    doc.doc_type_code = doc_type
    doc.filer_name = ''
    doc.filer_edinet_code = ''
    doc.fetch.return_value = _make_zip(rows) if rows is not None else b''
    return doc


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

class TestInternalControlRouting:
    """parse() must route doc 235/236 to InternalControlReport."""

    def test_doc_235_routes_to_internal_control(self):
        doc = _make_doc(doc_type='235')
        result = parse(doc)
        assert isinstance(result, InternalControlReport)

    def test_doc_236_routes_to_internal_control(self):
        doc = _make_doc(doc_type='236')
        result = parse(doc)
        assert isinstance(result, InternalControlReport)


# ---------------------------------------------------------------------------
# Empty-document behaviour
# ---------------------------------------------------------------------------

class TestEmptyDocument:
    def test_empty_zip_returns_empty_report(self):
        doc = _make_doc(rows=None)
        report = parse_internal_control(doc)
        assert isinstance(report, InternalControlReport)
        assert report.doc_id == 'S100TEST'
        assert report.company_name is None
        assert report.filing_date is None
        assert report.is_amendment is False
        assert report.source_files == []


# ---------------------------------------------------------------------------
# Field-level extraction from mock CSV
# ---------------------------------------------------------------------------

class TestFieldExtraction:
    """Prove that ELEMENT_MAP keys correctly map to dataclass fields."""

    def test_extracts_company_name(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['company_name'], 'FilingDateInstant', 'テスト株式会社'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.company_name == 'テスト株式会社'

    def test_extracts_filing_date(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['filing_date'], 'FilingDateInstant', '2025-06-20'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.filing_date == date(2025, 6, 20)

    def test_extracts_representative(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['representative'], 'FilingDateInstant', '代表取締役社長 山田 太郎'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.representative == '代表取締役社長 山田 太郎'

    def test_extracts_cfo(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['cfo'], 'FilingDateInstant', '取締役CFO 田中 花子'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.cfo == '取締役CFO 田中 花子'

    def test_extracts_filer_edinet_code(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['filer_edinet_code'], 'FilingDateInstant', 'E01234'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.filer_edinet_code == 'E01234'

    def test_extracts_security_code(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['security_code'], 'FilingDateInstant', '4321'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.security_code == '4321'

    def test_company_name_falls_back_to_filer_name(self):
        """When company_name is absent, company_name falls back to DEI filer_name."""
        rows = [
            _make_csv_row(ELEMENT_MAP['filer_name'], 'FilingDateInstant', 'DEI Filer Corp'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        # company_name should fall back to filer_name
        assert report.company_name == 'DEI Filer Corp'
        assert report.filer_name == 'DEI Filer Corp'

    def test_all_cover_page_fields_extracted_together(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['company_name'], 'FilingDateInstant', 'サンプル株式会社'),
            _make_csv_row(ELEMENT_MAP['filing_date'], 'FilingDateInstant', '2025-06-30'),
            _make_csv_row(ELEMENT_MAP['representative'], 'FilingDateInstant', '代表取締役 佐藤 一郎'),
            _make_csv_row(ELEMENT_MAP['cfo'], 'FilingDateInstant', 'CFO 鈴木 次郎'),
            _make_csv_row(ELEMENT_MAP['filer_edinet_code'], 'FilingDateInstant', 'E09999'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.company_name == 'サンプル株式会社'
        assert report.filing_date == date(2025, 6, 30)
        assert report.representative == '代表取締役 佐藤 一郎'
        assert report.cfo == 'CFO 鈴木 次郎'
        assert report.filer_edinet_code == 'E09999'


# ---------------------------------------------------------------------------
# Text block capture
# ---------------------------------------------------------------------------

class TestTextBlockCapture:
    """ResultOfEvaluationTextBlock and others must land in text_blocks."""

    def test_evaluation_result_text_block_captured(self):
        rows = [
            _make_csv_row(
                ELEMENT_MAP['evaluation_result_text'],
                'FilingDateInstant',
                '当社の内部統制は有効であると評価した。',
            ),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        # Should be captured in the structured field
        assert report.evaluation_result_text == '当社の内部統制は有効であると評価した。'
        # Must also appear in text_blocks (categorize_elements picks up TextBlocks)
        assert 'ResultOfEvaluationTextBlock' in report.text_blocks

    def test_scope_and_procedures_text_block_captured(self):
        rows = [
            _make_csv_row(
                ELEMENT_MAP['scope_and_procedures_text'],
                'FilingDateInstant',
                '評価の範囲、基準日及び評価手続きについて...',
            ),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert 'ScopeDateAndProceduresForEvaluationTextBlock' in report.text_blocks

    def test_unmapped_text_block_still_captured(self):
        """Any TextBlock element is captured even if not in ELEMENT_MAP."""
        rows = [
            _make_csv_row(
                'jpctl_cor:SomeOtherTextBlock',
                'FilingDateInstant',
                'その他の情報。',
            ),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert 'SomeOtherTextBlock' in report.text_blocks


# ---------------------------------------------------------------------------
# Amendment detection
# ---------------------------------------------------------------------------

class TestAmendmentDetection:
    def test_amendment_flag_true(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['amendment_flag'], 'FilingDateInstant', 'true'),
        ]
        doc = _make_doc(doc_type='236', rows=rows)
        report = parse_internal_control(doc)
        assert report.is_amendment is True

    def test_amendment_flag_false(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['amendment_flag'], 'FilingDateInstant', 'false'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.is_amendment is False

    def test_amendment_flag_absent_defaults_false(self):
        rows = [
            _make_csv_row(ELEMENT_MAP['company_name'], 'FilingDateInstant', 'テスト'),
        ]
        report = parse_internal_control(_make_doc(rows=rows))
        assert report.is_amendment is False


# ---------------------------------------------------------------------------
# Dataclass and repr
# ---------------------------------------------------------------------------

class TestInternalControlReportDataclass:
    def test_defaults_all_none(self):
        report = InternalControlReport(doc_id='X', doc_type_code='235')
        assert report.company_name is None
        assert report.filing_date is None
        assert report.representative is None
        assert report.cfo is None
        assert report.evaluation_result_text is None
        assert report.is_amendment is False

    def test_repr_normal(self):
        report = InternalControlReport(
            doc_id='X',
            doc_type_code='235',
            company_name='テスト株式会社',
        )
        r = repr(report)
        assert 'InternalControlReport' in r
        assert 'テスト' in r
        assert 'AMENDED' not in r

    def test_repr_amendment(self):
        report = InternalControlReport(
            doc_id='X',
            doc_type_code='236',
            company_name='テスト',
            is_amendment=True,
        )
        assert 'AMENDED' in repr(report)

    def test_repr_truncates_long_name(self):
        report = InternalControlReport(
            doc_id='X',
            doc_type_code='235',
            company_name='A' * 50,
        )
        assert '...' in repr(report)

    def test_to_dict_excludes_raw_fields(self):
        report = InternalControlReport(
            doc_id='X',
            doc_type_code='235',
            company_name='テスト',
            raw_fields={'k': 'v'},
            unmapped_fields={'u': 'v'},
        )
        d = report.to_dict()
        assert d['company_name'] == 'テスト'
        assert 'raw_fields' not in d
        assert 'unmapped_fields' not in d

    def test_fields_list_contains_expected_keys(self):
        report = InternalControlReport(doc_id='X', doc_type_code='235')
        f = report.fields()
        for key in ['company_name', 'filing_date', 'representative', 'cfo',
                    'evaluation_result_text', 'is_amendment']:
            assert key in f, f"Expected field '{key}' in fields()"


# ---------------------------------------------------------------------------
# ELEMENT_MAP sanity checks
# ---------------------------------------------------------------------------

class TestElementMap:
    def test_required_keys_present(self):
        required = [
            'filer_name', 'filer_edinet_code', 'amendment_flag',
            'company_name', 'filing_date', 'representative', 'cfo',
            'evaluation_result_text',
        ]
        for key in required:
            assert key in ELEMENT_MAP, f"Missing required ELEMENT_MAP key: {key}"

    def test_all_values_are_namespaced(self):
        for key, elem_id in ELEMENT_MAP.items():
            assert ':' in elem_id, f"Element '{key}' missing namespace prefix: {elem_id}"

    def test_dei_keys_use_jpdei_namespace(self):
        for key in ('filer_name', 'filer_edinet_code', 'security_code', 'amendment_flag'):
            assert ELEMENT_MAP[key].startswith('jpdei_cor:'), (
                f"DEI key '{key}' should use jpdei_cor namespace"
            )

    def test_cover_page_keys_use_jpctl_namespace(self):
        for key in ('company_name', 'filing_date', 'representative', 'cfo'):
            assert ELEMENT_MAP[key].startswith('jpctl_cor:'), (
                f"Cover page key '{key}' should use jpctl_cor namespace"
            )
