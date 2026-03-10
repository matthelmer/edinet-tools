"""
Tests for edinet_tools.processors module (document processing functionality).

Tests all document processors including the new specialized processors for different
document types, ensuring proper data extraction and no data loss.
"""

import pytest
from unittest.mock import Mock, patch
from edinet_tools.processors import (
    BaseDocumentProcessor,
    ExtraordinaryReportProcessor, 
    SemiAnnualReportProcessor,
    SecuritiesReportProcessor,
    InternalControlReportProcessor,
    GenericReportProcessor,
    process_raw_csv_data
)


class TestBaseDocumentProcessor:
    """Test the base document processor functionality."""
    
    def setup_method(self):
        """Set up test data for base processor."""
        # Mock CSV data with Japanese XBRL structure
        self.mock_csv_data = [
            {
                'filename': 'test_file.csv',
                'data': [
                    {'要素ID': 'jpdei_cor:EDINETCodeDEI', '項目名': 'EDINET Code', '値': 'E02144'},
                    {'要素ID': 'jpdei_cor:FilerNameInJapaneseDEI', '項目名': '会社名', '値': 'テスト株式会社'},
                    {'要素ID': 'jpcrp_cor:BusinessResultsTextBlock', '項目名': 'Business Results', '値': 'Test business content'},
                    {'要素ID': 'jpcrp_cor:NetSales', '項目名': 'Net Sales', 'コンテキストID': 'CurrentYear', '値': '1000000'},
                    {'要素ID': 'jpcrp_cor:NetSales', '項目名': 'Net Sales', 'コンテキストID': 'PriorYear', '値': '900000'},
                ]
            }
        ]
        self.processor = BaseDocumentProcessor(
            self.mock_csv_data, 
            doc_id='TEST001', 
            doc_type_code='120'
        )
    
    def test_initialization(self):
        """Test processor initialization."""
        assert self.processor.doc_id == 'TEST001'
        assert self.processor.doc_type_code == '120'
        assert len(self.processor.all_records) == 5
    
    def test_get_value_by_id(self):
        """Test getting values by element ID."""
        # Test basic value retrieval
        edinet_code = self.processor.get_value_by_id('jpdei_cor:EDINETCodeDEI')
        assert edinet_code == 'E02144'
        
        # Test context filtering
        current_sales = self.processor.get_value_by_id('jpcrp_cor:NetSales', context_filter='Current')
        assert current_sales == '1000000'
        
        prior_sales = self.processor.get_value_by_id('jpcrp_cor:NetSales', context_filter='Prior') 
        assert prior_sales == '900000'
        
        # Test non-existent ID
        missing = self.processor.get_value_by_id('nonexistent:element')
        assert missing is None
    
    def test_get_records_by_id(self):
        """Test getting all records for an element ID."""
        sales_records = self.processor.get_records_by_id('jpcrp_cor:NetSales')
        assert len(sales_records) == 2
        assert sales_records[0]['コンテキストID'] == 'CurrentYear'
        assert sales_records[1]['コンテキストID'] == 'PriorYear'
    
    def test_get_all_text_blocks(self):
        """Test text block extraction."""
        text_blocks = self.processor.get_all_text_blocks()
        assert len(text_blocks) == 1
        
        block = text_blocks[0]
        assert block['id'] == 'jpcrp_cor:BusinessResultsTextBlock'
        assert block['title'] == 'Business Results'
        assert block['content'] == 'Test business content'
    
    def test_get_common_metadata(self):
        """Test common metadata extraction."""
        metadata = self.processor._get_common_metadata()
        
        assert metadata['edinet_code'] == 'E02144'
        assert metadata['company_name_ja'] == 'テスト株式会社'
        assert metadata['doc_id'] == 'TEST001'
        assert metadata['doc_type_code'] == '120'
    
    def test_empty_data_handling(self):
        """Test handling of empty or malformed data."""
        empty_processor = BaseDocumentProcessor([], 'EMPTY001', '999')
        
        assert len(empty_processor.all_records) == 0
        assert empty_processor.get_value_by_id('any:element') is None
        assert empty_processor.get_all_text_blocks() == []
    
    def test_none_value_handling(self):
        """Test handling of None values in data."""
        data_with_nones = [
            {
                'filename': 'test.csv',
                'data': [
                    {'要素ID': None, '項目名': 'Test', '値': 'value'},
                    {'要素ID': 'valid:element', '項目名': None, '値': None},
                    {'要素ID': 'another:element', '項目名': 'Valid Title', '値': 'valid value'},
                ]
            }
        ]
        
        processor = BaseDocumentProcessor(data_with_nones, 'TEST002', '180')
        
        # Should handle None gracefully
        text_blocks = processor.get_all_text_blocks()
        assert len(text_blocks) == 0  # No TextBlocks in this data
        
        # Should handle valid elements
        value = processor.get_value_by_id('another:element')
        assert value == 'valid value'


class TestSecuritiesReportProcessor:
    """Test the Securities Report processor (Type 120)."""
    
    def setup_method(self):
        """Set up comprehensive test data for Securities Report."""
        self.mock_csv_data = [
            {
                'filename': 'jpcrp030000-asr-001.csv',
                'data': [
                    # Metadata
                    {'要素ID': 'jpdei_cor:EDINETCodeDEI', '項目名': 'EDINET Code', '値': 'E02144'},
                    {'要素ID': 'jpdei_cor:FilerNameInEnglishDEI', '項目名': 'Company Name EN', '値': 'Test Corporation'},
                    {'要素ID': 'jpdei_cor:DocumentTypeDEI', '項目名': 'Document Type', '値': 'Securities Report'},
                    
                    # Financial metrics
                    {'要素ID': 'jpcrp_cor:NetSales', '項目名': 'Net Sales', 'コンテキストID': 'CurrentYear', '値': '5000000'},
                    {'要素ID': 'jpcrp_cor:NetSales', '項目名': 'Net Sales', 'コンテキストID': 'PriorYear', '値': '4500000'},
                    {'要素ID': 'jpcrp_cor:OperatingIncome', '項目名': 'Operating Income', 'コンテキストID': 'CurrentYear', '値': '500000'},
                    {'要素ID': 'jpcrp_cor:TotalAssets', '項目名': 'Total Assets', '値': '10000000'},
                    {'要素ID': 'jpcrp_cor:BasicEarningsLossPerShare', '項目名': 'EPS', '値': '120.50'},
                    
                    # Business information
                    {'要素ID': 'jpcrp_cor:NumberOfEmployees', '項目名': 'Employee Count', '値': '50000'},
                    {'要素ID': 'jpcrp_cor:AverageAnnualSalary', '項目名': 'Average Salary', '値': '7000000'},
                    
                    # Text blocks
                    {'要素ID': 'jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock', 
                     '項目名': 'Management Analysis', '値': 'Management discusses financial position and results...'},
                    {'要素ID': 'jpcrp_cor:RiskFactorsTextBlock', 
                     '項目名': 'Risk Factors', '値': 'Key business risks include market volatility...'},
                    {'要素ID': 'jpcrp_cor:CorporateGovernanceTextBlock',
                     '項目名': 'Corporate Governance', '値': 'Our corporate governance framework...'},
                ]
            }
        ]
        
        self.processor = SecuritiesReportProcessor(
            self.mock_csv_data,
            doc_id='S100TEST1', 
            doc_type_code='120'
        )
    
    def test_process_securities_report(self):
        """Test full processing of Securities Report."""
        result = self.processor.process()
        
        assert result is not None
        assert result['doc_id'] == 'S100TEST1'
        assert result['doc_type_code'] == '120'
        assert result['company_name_en'] == 'Test Corporation'
        
        # Check structure
        assert 'key_facts' in result
        assert 'financial_tables' in result  
        assert 'text_blocks' in result
    
    def test_extract_financial_metrics(self):
        """Test financial metrics extraction."""
        metrics = self.processor._extract_financial_metrics()
        
        # Should extract sales with current/prior
        assert 'net_sales' in metrics
        assert metrics['net_sales']['current'] == '5000000'
        assert metrics['net_sales']['prior'] == '4500000'
        
        # Should extract single values
        assert 'total_assets' in metrics
        assert metrics['total_assets'] == '10000000'
        
        assert 'earnings_per_share' in metrics
        assert metrics['earnings_per_share'] == '120.50'
    
    def test_extract_business_facts(self):
        """Test business facts extraction.""" 
        facts = self.processor._extract_business_facts()
        
        assert 'employee_count' in facts
        assert facts['employee_count'] == '50000'
        
        assert 'average_annual_salary' in facts
        assert facts['average_annual_salary'] == '7000000'
    
    def test_categorize_text_blocks(self):
        """Test text block categorization."""
        blocks = self.processor._categorize_text_blocks()
        
        assert len(blocks) == 3
        
        # Check categories are assigned
        categories = [block['category'] for block in blocks]
        assert 'management_analysis' in categories
        assert 'risk_factors' in categories
        assert 'corporate_governance' in categories
    
    def test_categorize_element(self):
        """Test element categorization logic."""
        # Test various categorization patterns - check actual implementation
        assert self.processor._categorize_element('jpcrp_cor:RiskFactorsTextBlock') == 'risk_factors'  # 'risk' keyword
        assert self.processor._categorize_element('jpcrp_cor:ManagementAnalysisTextBlock') == 'management_analysis'
        assert self.processor._categorize_element('jpcrp_cor:CorporateGovernanceTextBlock') == 'corporate_governance'
        assert self.processor._categorize_element('jpcrp_cor:ShareholderInformationTextBlock') == 'shareholder_information'
        assert self.processor._categorize_element('jpcrp_cor:UnknownElement') == 'other'


class TestInternalControlReportProcessor:
    """Test the Internal Control Report processor (Type 235)."""
    
    def setup_method(self):
        """Set up test data for Internal Control Report."""
        self.mock_csv_data = [
            {
                'filename': 'internal_control.csv',
                'data': [
                    # Metadata
                    {'要素ID': 'jpdei_cor:EDINETCodeDEI', '項目名': 'EDINET Code', '値': 'E02126'},
                    {'要素ID': 'jpdei_cor:FilerNameInEnglishDEI', '項目名': 'Company Name', '値': 'Internal Control Test Co.'},
                    
                    # Internal control specific elements  
                    {'要素ID': 'jpcrp_cor:InternalControlAssessmentResult', '項目名': 'Assessment Result', '値': 'Effective'},
                    {'要素ID': 'jpcrp_cor:MaterialWeaknessInInternalControl', '項目名': 'Material Weakness', '値': 'None identified'},
                    
                    # Text blocks
                    {'要素ID': 'jpcrp_cor:InternalControlFrameworkTextBlock', 
                     '項目名': 'Internal Control Framework', '値': 'Our internal control framework is based on...'},
                    {'要素ID': 'jpcrp_cor:EvaluationScopeTextBlock',
                     '項目名': 'Evaluation Scope', '値': 'The evaluation covered company and subsidiaries...'},
                ]
            }
        ]
        
        self.processor = InternalControlReportProcessor(
            self.mock_csv_data,
            doc_id='S100IC01',
            doc_type_code='235'
        )
    
    def test_process_internal_control_report(self):
        """Test processing of Internal Control Report."""
        result = self.processor.process()
        
        assert result is not None
        assert result['doc_type_code'] == '235'
        assert result['company_name_en'] == 'Internal Control Test Co.'
        
        # Internal control reports should have specific structure
        key_facts = result['key_facts']
        assert 'assessment_result' in key_facts
        assert key_facts['assessment_result'] == 'Effective'
        
        assert 'material_weakness' in key_facts
        assert key_facts['material_weakness'] == 'None identified'
        
        # Should have no financial tables
        assert result['financial_tables'] == []
        
        # Should have text blocks
        assert len(result['text_blocks']) == 2


class TestExtraordinaryReportProcessor:
    """Test the Extraordinary Report processor (Type 180)."""
    
    def setup_method(self):
        """Set up test data for Extraordinary Report."""
        self.mock_csv_data = [
            {
                'filename': 'extraordinary.csv', 
                'data': [
                    {'要素ID': 'jpdei_cor:EDINETCodeDEI', '項目名': 'EDINET Code', '値': 'E99999'},
                    
                    # Extraordinary report specific elements
                    {'要素ID': 'jpcrp-esr_cor:ResolutionOfBoardOfDirectorsDescription', 
                     '項目名': 'Board Resolution', '値': 'Board resolved to acquire subsidiary...'},
                    {'要素ID': 'jpcrp-esr_cor:DateOfResolutionOfBoardOfDirectors',
                     '項目名': 'Resolution Date', '値': '2025-06-01'},
                    {'要素ID': 'jpcrp-esr_cor:ImpactOnBusinessResultsDescription',
                     '項目名': 'Business Impact', '値': 'Expected to increase revenue by 10%...'},
                     
                    # Text blocks
                    {'要素ID': 'jpcrp_cor:SubmissionReasonTextBlock',
                     '項目名': 'Submission Reason', '値': 'Filing due to material acquisition...'},
                ]
            }
        ]
        
        self.processor = ExtraordinaryReportProcessor(
            self.mock_csv_data,
            doc_id='S100ER01',
            doc_type_code='180'
        )
    
    def test_process_extraordinary_report(self):
        """Test processing of Extraordinary Report."""
        result = self.processor.process()
        
        assert result is not None
        assert result['doc_type_code'] == '180'
        
        # Check key facts extraction - use the actual cleaned key names from processor
        key_facts = result['key_facts']
        assert 'ResolutionOfBoardOfDirectors' in key_facts
        assert 'DateOfResolutionOfBoardOfDirectors' in key_facts
        assert 'ImpactOnResults' in key_facts  # Key gets cleaned to ImpactOnResults
        
        # Check text blocks
        assert len(result['text_blocks']) == 1
        assert result['text_blocks'][0]['title'] == 'Submission Reason'


class TestProcessorDispatcher:
    """Test the processor dispatching functionality."""
    
    def test_process_raw_csv_data_securities_report(self):
        """Test dispatcher selects SecuritiesReportProcessor for type 120."""
        mock_data = [{'filename': 'test.csv', 'data': []}]
        
        with patch('edinet_tools.processors.SecuritiesReportProcessor') as mock_processor_class:
            mock_instance = Mock()
            mock_instance.process.return_value = {'test': 'data'}
            mock_processor_class.return_value = mock_instance
            mock_processor_class.__name__ = 'SecuritiesReportProcessor'  # Fix __name__ attribute
            
            result = process_raw_csv_data(mock_data, 'TEST001', '120')
            
            # Should use SecuritiesReportProcessor
            mock_processor_class.assert_called_once_with(mock_data, 'TEST001', '120', None)
            mock_instance.process.assert_called_once()
            assert result == {'test': 'data'}
    
    def test_process_raw_csv_data_internal_control(self):
        """Test dispatcher selects InternalControlReportProcessor for type 235."""
        mock_data = [{'filename': 'test.csv', 'data': []}]
        
        with patch('edinet_tools.processors.InternalControlReportProcessor') as mock_processor_class:
            mock_instance = Mock()
            mock_instance.process.return_value = {'control': 'data'}
            mock_processor_class.return_value = mock_instance
            mock_processor_class.__name__ = 'InternalControlReportProcessor'  # Fix __name__ attribute
            
            result = process_raw_csv_data(mock_data, 'TEST002', '235')
            
            mock_processor_class.assert_called_once_with(mock_data, 'TEST002', '235', None)
            assert result == {'control': 'data'}
    
    def test_process_raw_csv_data_unknown_type(self):
        """Test dispatcher uses GenericReportProcessor for unknown types."""
        mock_data = [{'filename': 'test.csv', 'data': []}]
        
        with patch('edinet_tools.processors.GenericReportProcessor') as mock_processor_class:
            mock_instance = Mock()
            mock_instance.process.return_value = {'generic': 'data'}
            mock_processor_class.return_value = mock_instance
            mock_processor_class.__name__ = 'GenericReportProcessor'  # Fix __name__ attribute
            
            result = process_raw_csv_data(mock_data, 'TEST003', '999')
            
            mock_processor_class.assert_called_once_with(mock_data, 'TEST003', '999', None)
            assert result == {'generic': 'data'}
    
    def test_process_raw_csv_data_with_exception(self):
        """Test dispatcher handles processor exceptions."""
        mock_data = [{'filename': 'test.csv', 'data': []}]
        
        with patch('edinet_tools.processors.GenericReportProcessor') as mock_processor_class:
            mock_processor_class.side_effect = Exception('Test error')
            mock_processor_class.__name__ = 'GenericReportProcessor'  # Fix __name__ attribute
            
            result = process_raw_csv_data(mock_data, 'TESTERR', '999')
            
            # Should return None on exception
            assert result is None


class TestGenericReportProcessor:
    """Test the Generic Report processor (fallback)."""
    
    def test_generic_processor_basic_functionality(self):
        """Test generic processor handles any document type."""
        mock_data = [
            {
                'filename': 'generic.csv',
                'data': [
                    {'要素ID': 'jpdei_cor:EDINETCodeDEI', '項目名': 'EDINET Code', '値': 'E12345'},
                    {'要素ID': 'jpcrp_cor:SomeTextBlock', '項目名': 'Some Text Block', '値': 'Generic content'},
                ]
            }
        ]
        
        processor = GenericReportProcessor(mock_data, 'GENERIC01', '999')
        result = processor.process()
        
        assert result is not None
        assert result['doc_type_code'] == '999'
        assert result['edinet_code'] == 'E12345'
        
        # Generic processor should have empty key facts and financial tables
        assert result['key_facts'] == {}
        assert result['financial_tables'] == []
        
        # Should extract text blocks
        assert len(result['text_blocks']) == 1


if __name__ == "__main__":
    # Run tests if pytest is available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("pytest not available. Install with: pip install pytest")
        print("Running basic processor validation...")
        
        # Basic validation tests
        mock_data = [{'filename': 'test.csv', 'data': [
            {'要素ID': 'test:element', '項目名': 'Test', '値': 'value'}
        ]}]
        
        # Test each processor can be instantiated
        base_proc = BaseDocumentProcessor(mock_data, 'TEST001', '999')
        assert len(base_proc.all_records) == 1
        
        securities_proc = SecuritiesReportProcessor(mock_data, 'TEST002', '120') 
        assert securities_proc.doc_type_code == '120'
        
        ic_proc = InternalControlReportProcessor(mock_data, 'TEST003', '235')
        assert ic_proc.doc_type_code == '235'
        
        print("✅ Basic processor validation passed!")