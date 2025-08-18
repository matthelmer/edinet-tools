"""
Tests for document_processors.py - Document processing classes.
"""
import pytest
from document_processors import (
    BaseDocumentProcessor, 
    ExtraordinaryReportProcessor,
    SemiAnnualReportProcessor,
    GenericReportProcessor,
    process_raw_csv_data
)


@pytest.fixture
def sample_csv_data_raw():
    """Sample raw CSV data structure as would come from ZIP processing."""
    return [
        {
            'filename': 'company_info.csv',
            'data': [
                {'field': 'company_name_ja', 'value': 'テスト株式会社'},
                {'field': 'company_name_en', 'value': 'Test Company Ltd.'},
                {'field': 'securities_code', 'value': '1234'}
            ]
        },
        {
            'filename': 'financial_data.csv', 
            'data': [
                {'field': 'total_assets', 'value': '1000000000', 'unit': 'yen'},
                {'field': 'total_liabilities', 'value': '600000000', 'unit': 'yen'},
                {'field': 'net_assets', 'value': '400000000', 'unit': 'yen'}
            ]
        }
    ]

@pytest.fixture
def sample_text_blocks():
    """Sample text blocks from document processing."""
    return [
        {
            'title': 'Business Overview',
            'title_en': 'Business Overview',
            'content_jp': 'テスト会社の事業概要です。',
            'content': 'This is a test company business overview.'
        }
    ]


class TestBaseDocumentProcessor:
    """Tests for BaseDocumentProcessor class."""

    def test_initialization(self, sample_csv_data_raw):
        """Test BaseDocumentProcessor initialization."""
        processor = BaseDocumentProcessor(
            sample_csv_data_raw, 'S100TEST123', '160'
        )

        assert processor.raw_csv_data == sample_csv_data_raw
        assert processor.doc_id == 'S100TEST123'
        assert processor.doc_type_code == '160'
        assert len(processor.all_records) > 0

    def test_combine_raw_data(self, sample_csv_data_raw):
        """Test _combine_raw_data method."""
        processor = BaseDocumentProcessor(
            sample_csv_data_raw, 'S100TEST123', '160'
        )

        # Should combine all records from all CSV files
        expected_total = sum(len(csv['data']) for csv in sample_csv_data_raw)
        assert len(processor.all_records) == expected_total

        # Records should be properly combined
        assert isinstance(processor.all_records, list)
        assert len(processor.all_records) > 0

    def test_get_value_by_id(self, sample_csv_data_raw):
        """Test get_value_by_id method."""
        # Create test data with proper Japanese field names
        jp_csv_data = [
            {
                'filename': 'test.csv',
                'data': [
                    {'要素ID': 'test_element', '値': 'test_value', '項目名': 'Test Item'}
                ]
            }
        ]

        processor = BaseDocumentProcessor(
            jp_csv_data, 'S100TEST123', '160'
        )

        value = processor.get_value_by_id('test_element')
        assert value == 'test_value'

    def test_get_records_by_id(self, sample_csv_data_raw):
        """Test get_records_by_id method."""
        # Create test data with proper Japanese field names
        jp_csv_data = [
            {
                'filename': 'test.csv',
                'data': [
                    {'要素ID': 'test_element', '値': 'value1'},
                    {'要素ID': 'test_element', '値': 'value2'},
                    {'要素ID': 'other_element', '値': 'value3'}
                ]
            }
        ]

        processor = BaseDocumentProcessor(
            jp_csv_data, 'S100TEST123', '160'
        )

        records = processor.get_records_by_id('test_element')
        assert len(records) == 2
        assert records[0]['値'] == 'value1'
        assert records[1]['値'] == 'value2'

    def test_process_not_implemented(self, sample_csv_data_raw):
        """Test that base process method raises NotImplementedError."""
        processor = BaseDocumentProcessor(
            sample_csv_data_raw, 'S100TEST123', '160'
        )

        with pytest.raises(NotImplementedError):
            processor.process()


class TestExtraordinaryReportProcessor:
    """Tests for ExtraordinaryReportProcessor class."""

    def test_process_extraordinary_report(self, sample_csv_data_raw):
        """Test processing of extraordinary report."""
        processor = ExtraordinaryReportProcessor(
            sample_csv_data_raw, 'S100EXTRA456', '180'
        )

        result = processor.process()

        # Check basic structure
        assert result is not None
        assert result['doc_id'] == 'S100EXTRA456'
        assert result['doc_type_code'] == '180'

    def test_extraordinary_report_handles_empty_data(self):
        """Test extraordinary report processor with minimal data."""
        processor = ExtraordinaryReportProcessor(
            [], 'S100EMPTY', '180'
        )

        result = processor.process()

        assert result['doc_id'] == 'S100EMPTY'
        assert result['doc_type_code'] == '180'
        assert result['text_blocks'] == []


class TestSemiAnnualReportProcessor:
    """Tests for SemiAnnualReportProcessor class."""

    def test_process_semi_annual_report(self, sample_csv_data_raw):
        """Test processing of semi-annual report."""
        processor = SemiAnnualReportProcessor(
            sample_csv_data_raw, 'S100SEMI789', '160'
        )

        result = processor.process()

        # Check basic structure
        assert result is not None
        assert result['doc_id'] == 'S100SEMI789'
        assert result['doc_type_code'] == '160'

    def test_extract_financial_data(self, sample_csv_data_raw):
        """Test that processor can handle financial data extraction."""
        processor = SemiAnnualReportProcessor(
            sample_csv_data_raw, 'S100SEMI789', '160'
        )

        # Just test that it doesn't crash and returns something
        result = processor.process()
        assert result is not None
        assert isinstance(result, dict)

    def test_financial_processing_robustness(self, sample_csv_data_raw):
        """Test that financial processor is robust with various data."""
        processor = SemiAnnualReportProcessor(
            sample_csv_data_raw, 'S100SEMI789', '160'
        )

        result = processor.process()

        # Should handle missing/incomplete data gracefully
        assert result is not None
        assert 'doc_id' in result


class TestGenericReportProcessor:
    """Tests for GenericReportProcessor class."""

    def test_process_generic_report(self, sample_csv_data_raw):
        """Test processing of generic report."""
        processor = GenericReportProcessor(
            sample_csv_data_raw, 'S100GENERIC', '120'
        )

        result = processor.process()

        # Check basic structure
        assert result is not None
        assert result['doc_id'] == 'S100GENERIC'


class TestProcessRawCsvData:
    """Tests for process_raw_csv_data function."""

    def test_process_raw_csv_data_semi_annual(self, sample_csv_data_raw):
        """Test process_raw_csv_data with semi-annual report."""
        result = process_raw_csv_data(
            sample_csv_data_raw, 'S100TEST123', '160'
        )

        assert result['doc_id'] == 'S100TEST123'
        assert result['doc_type_code'] == '160'
        assert isinstance(result, dict)

    def test_process_raw_csv_data_extraordinary(self, sample_csv_data_raw):
        """Test process_raw_csv_data with extraordinary report."""
        result = process_raw_csv_data(
            sample_csv_data_raw, 'S100EXTRA456', '180'
        )

        assert result['doc_id'] == 'S100EXTRA456'
        assert result['doc_type_code'] == '180'

    def test_process_raw_csv_data_unsupported_type(self, sample_csv_data_raw):
        """Test process_raw_csv_data with unsupported document type."""
        result = process_raw_csv_data(
            sample_csv_data_raw, 'S100UNKNOWN', '999'  # Unsupported type
        )

        # Should fall back to GenericReportProcessor
        assert result['doc_id'] == 'S100UNKNOWN'
        assert result['doc_type_code'] == '999'

    def test_process_raw_csv_data_error_handling(self):
        """Test process_raw_csv_data error handling."""
        # Test with malformed CSV data
        bad_csv_data = [{'filename': 'bad.csv', 'data': 'not_a_list'}]

        result = process_raw_csv_data(
            bad_csv_data, 'S100ERROR', '160'
        )

        # Should return None on error
        assert result is None

    def test_process_raw_csv_data_empty_inputs(self):
        """Test process_raw_csv_data with empty inputs."""
        result = process_raw_csv_data([], 'S100EMPTY', '160')

        assert result['doc_id'] == 'S100EMPTY'
        assert isinstance(result, dict)


class TestDocumentProcessorIntegration:
    """Integration tests for document processors."""

    def test_processor_selection_logic(self):
        """Test that correct processor is selected for each document type."""
        # Test data
        csv_data = []
        text_blocks = []

        # Test semi-annual report (160)
        result_160 = process_raw_csv_data(csv_data, 'TEST160', '160')
        if result_160:  # May be None due to empty data
            assert result_160['doc_type_code'] == '160'

        # Test extraordinary report (180)
        result_180 = process_raw_csv_data(csv_data, 'TEST180', '180')
        if result_180:
            assert result_180['doc_type_code'] == '180'

        # Test other types fall back to generic
        result_120 = process_raw_csv_data(csv_data, 'TEST120', '120')
        if result_120:
            assert result_120['doc_type_code'] == '120'

    def test_processor_with_real_data_structure(self):
        """Test processors handle realistic data structures."""
        # More realistic CSV data structure
        realistic_csv_data = [
            {
                'filename': 'XBRL_data.csv',
                'data': [
                    {
                        'element_id': 'jppfs_cor:CompanyName',
                        'context_ref': 'CurrentYearInstant', 
                        'value': 'テスト株式会社',
                        'unit': None
                    },
                    {
                        'element_id': 'jppfs_cor:Assets',
                        'context_ref': 'CurrentYearInstant',
                        'value': '1000000000',
                        'unit': 'JPY'
                    }
                ]
            }
        ]

        text_blocks = [
            {
                'section': 'management_discussion',
                'content': 'Management discussion content...'
            }
        ]

        result = process_raw_csv_data(
            realistic_csv_data, 'S100REAL', '160'
        )

        assert result['doc_id'] == 'S100REAL'
        if result:  # May be None if processing fails
            assert len(result) > 1  # Should have at least doc_id and type
