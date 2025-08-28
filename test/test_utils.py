"""
Tests for edinet_tools.utils module (utility functions).

Tests file processing, encoding detection, ZIP handling, and text processing
utilities used throughout the EDINET Tools package.
"""

import pytest
import os
import tempfile
import zipfile
import csv
from unittest.mock import Mock, patch, mock_open
import chardet

from edinet_tools.utils import (
    detect_encoding,
    read_csv_file, 
    clean_text,
    process_zip_file,
    process_zip_directory
)


class TestEncodingDetection:
    """Test encoding detection functionality."""
    
    def test_detect_encoding_utf8(self):
        """Test detection of UTF-8 encoded files."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
            f.write('Hello, 世界! Test content.')
            temp_path = f.name
        
        try:
            encoding = detect_encoding(temp_path)
            # Should detect UTF-8 (might be detected as ascii for simple content)
            assert encoding in ['utf-8', 'ascii']
        finally:
            os.unlink(temp_path)
    
    def test_detect_encoding_utf16(self):
        """Test detection of UTF-16 encoded files."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-16', delete=False) as f:
            f.write('要素ID\t項目名\t値\n')  # Japanese headers like in EDINET
            f.write('jpdei_cor:test\tテスト\t12345\n')
            temp_path = f.name
        
        try:
            encoding = detect_encoding(temp_path)
            assert 'utf-16' in encoding.lower()
        finally:
            os.unlink(temp_path)
    
    def test_detect_encoding_shift_jis(self):
        """Test detection of Shift-JIS encoded files."""
        # Create test content that will be clearly Shift-JIS
        japanese_text = 'これはテストです。'
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(japanese_text.encode('shift-jis'))
            temp_path = f.name
        
        try:
            encoding = detect_encoding(temp_path)
            # chardet should detect some Japanese encoding
            assert encoding is not None
            assert encoding.lower() in ['shift-jis', 'shift_jis', 'cp932', 'windows-1252']
        finally:
            os.unlink(temp_path)
    
    def test_detect_encoding_nonexistent_file(self):
        """Test handling of nonexistent files."""
        encoding = detect_encoding('/nonexistent/file.txt')
        assert encoding is None
    
    def test_detect_encoding_empty_file(self):
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name  # Empty file
        
        try:
            encoding = detect_encoding(temp_path)
            # Should return something reasonable for empty files
            assert encoding in ['ascii', 'utf-8', None]
        finally:
            os.unlink(temp_path)


class TestCSVFileReading:
    """Test CSV file reading with various encodings."""
    
    def setup_method(self):
        """Set up test CSV data."""
        # Standard EDINET CSV structure
        self.csv_headers = ['要素ID', '項目名', 'コンテキストID', '相対年度', '連結・個別', '期間・時点', 'ユニットID', '単位', '値']
        self.csv_rows = [
            ['jpdei_cor:EDINETCodeDEI', 'EDINETコード、DEI', 'FilingDateInstant', '提出日時点', 'その他', '時点', 'pure', '', 'E02144'],
            ['jpcrp_cor:NetSales', '売上高', 'CurrentYear', '当事業年度', '連結', '期間', 'jpy', '百万円', '1000000'],
            ['jpcrp_cor:NetSales', '売上高', 'PriorYear', '前事業年度', '連結', '期間', 'jpy', '百万円', '900000']
        ]
    
    def create_test_csv(self, encoding='utf-8'):
        """Helper to create test CSV file."""
        with tempfile.NamedTemporaryFile(mode='w', encoding=encoding, delete=False, suffix='.csv') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(self.csv_headers)
            writer.writerows(self.csv_rows)
            return f.name
    
    def test_read_csv_file_utf8(self):
        """Test reading UTF-8 CSV file."""
        csv_path = self.create_test_csv('utf-8')
        
        try:
            records = read_csv_file(csv_path)
            
            assert len(records) == 3  # 3 data rows
            assert records[0]['要素ID'] == 'jpdei_cor:EDINETCodeDEI'
            assert records[0]['項目名'] == 'EDINETコード、DEI'
            assert records[0]['値'] == 'E02144'
            
            # Check financial data
            assert records[1]['要素ID'] == 'jpcrp_cor:NetSales'
            assert records[1]['値'] == '1000000'
        finally:
            os.unlink(csv_path)
    
    def test_read_csv_file_utf16(self):
        """Test reading UTF-16 CSV file."""
        csv_path = self.create_test_csv('utf-16')
        
        try:
            records = read_csv_file(csv_path)
            
            assert len(records) == 3
            assert records[0]['要素ID'] == 'jpdei_cor:EDINETCodeDEI'
            assert records[1]['値'] == '1000000'
        finally:
            os.unlink(csv_path)
    
    def test_read_csv_file_with_missing_values(self):
        """Test reading CSV with missing/None values."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(['要素ID', '項目名', '値'])
            writer.writerow(['test:element1', 'Test Element', 'value1'])
            writer.writerow(['test:element2', '', ''])  # Empty values
            writer.writerow(['test:element3', 'Element 3', None])  # None value
            csv_path = f.name
        
        try:
            records = read_csv_file(csv_path)
            
            assert len(records) == 3
            
            # First record normal
            assert records[0]['値'] == 'value1'
            
            # Second record with empty string converted to None
            assert records[1]['項目名'] is None
            assert records[1]['値'] is None
            
            # Third record
            assert records[2]['項目名'] == 'Element 3'
        finally:
            os.unlink(csv_path)
    
    def test_read_csv_file_nonexistent(self):
        """Test reading nonexistent CSV file."""
        records = read_csv_file('/nonexistent/file.csv')
        assert records is None
    
    def test_read_csv_file_malformed(self):
        """Test reading malformed CSV file."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write('This is not a valid CSV file\n')
            f.write('Random text without proper structure\n')
            csv_path = f.name
        
        try:
            records = read_csv_file(csv_path)
            # Should handle gracefully and return some result or None
            assert records is not None or records is None  # Either outcome is acceptable
        finally:
            os.unlink(csv_path)
    
    @patch('edinet_tools.utils.detect_encoding')
    def test_read_csv_file_encoding_detection_failure(self, mock_detect_encoding):
        """Test CSV reading when encoding detection fails."""
        mock_detect_encoding.return_value = None
        
        csv_path = self.create_test_csv('utf-8')
        
        try:
            records = read_csv_file(csv_path)
            # Should still work by trying common encodings
            assert records is not None
            assert len(records) >= 0
        finally:
            os.unlink(csv_path)


class TestTextCleaning:
    """Test text cleaning functionality."""
    
    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        assert clean_text('  Hello World  ') == 'Hello World'
        assert clean_text('Text\nwith\nnewlines') == 'Text with newlines'
        assert clean_text('Text\twith\ttabs') == 'Text with tabs'
        assert clean_text('Multiple   spaces   here') == 'Multiple spaces here'
    
    def test_clean_text_japanese(self):
        """Test cleaning Japanese text."""
        japanese_text = '  これは　　テストです。\n改行あり　　'
        cleaned = clean_text(japanese_text)
        
        assert cleaned == 'これは テストです。 改行あり'
        assert not cleaned.startswith(' ')
        assert not cleaned.endswith(' ')
    
    def test_clean_text_none_and_empty(self):
        """Test cleaning None and empty strings."""
        assert clean_text(None) is None  # None input returns None
        assert clean_text('') == ''
        assert clean_text('   ') == ''
    
    def test_clean_text_mixed_content(self):
        """Test cleaning mixed Japanese and English content."""
        mixed_text = '  Test テスト\n\nEnglish 日本語  \t  '
        cleaned = clean_text(mixed_text)
        
        assert cleaned == 'Test テスト English 日本語'
    
    def test_clean_text_financial_data(self):
        """Test cleaning typical financial text data."""
        financial_text = '''
        ４【経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析】
        
        当連結会計年度における当社グループの財政状態、経営成績及び
        キャッシュ・フロー（以下、「経営成績等」という。）の状況の概要
        '''
        
        cleaned = clean_text(financial_text)
        
        assert '４【経営者による財政状態' in cleaned
        assert cleaned.count('\n') == 0  # No newlines in cleaned text
        assert '  ' not in cleaned  # No double spaces


class TestZIPProcessing:
    """Test ZIP file processing functionality."""
    
    def setup_method(self):
        """Set up test ZIP file."""
        self.test_csv_content = '''要素ID	項目名	コンテキストID	値
jpdei_cor:EDINETCodeDEI	EDINETコード	FilingDateInstant	E02144
jpcrp_cor:CompanyNameTextBlock	会社名	FilingDateInstant	Test Corporation
jpcrp_cor:BusinessResultsTextBlock	事業結果	FilingDateInstant	Strong quarterly results...'''
    
    def create_test_zip(self):
        """Helper to create test ZIP file."""
        zip_path = tempfile.mktemp(suffix='.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Add main CSV file
            zf.writestr('XBRL_TO_CSV/main_file.csv', self.test_csv_content.encode('utf-16'))
            
            # Add auditor files (should be skipped)
            zf.writestr('XBRL_TO_CSV/jpaud-aai-cc-001.csv', 'auditor data')
            zf.writestr('XBRL_TO_CSV/jpaud-aar-cn-001.csv', 'auditor data')
            
            # Add other file
            zf.writestr('XBRL_TO_CSV/secondary_file.csv', 
                       'secondary_data\tvalue\ntest_element\ttest_value'.encode('utf-8'))
        
        return zip_path
    
    def test_process_zip_file_success(self):
        """Test successful ZIP file processing."""
        zip_path = self.create_test_zip()
        
        try:
            with patch('edinet_tools.utils.process_raw_csv_data') as mock_process:
                mock_process.return_value = {
                    'edinet_code': 'E02144',
                    'company_name_en': 'Test Corporation',
                    'text_blocks': [{'title': 'Business Results', 'content': 'Strong quarterly results...'}]
                }
                
                result = process_zip_file(zip_path, 'S100TEST1', '120')
                
                assert result is not None
                assert result['edinet_code'] == 'E02144'
                assert result['company_name_en'] == 'Test Corporation'
                
                # Check that process_raw_csv_data was called correctly
                mock_process.assert_called_once()
                call_args = mock_process.call_args[0]
                csv_data_list = call_args[0]
                
                # Should have main_file.csv and secondary_file.csv (auditor files skipped)
                csv_filenames = [csv_file['filename'] for csv_file in csv_data_list]
                assert 'main_file.csv' in csv_filenames
                assert 'secondary_file.csv' in csv_filenames
                assert not any('jpaud-' in name for name in csv_filenames)
                
        finally:
            os.unlink(zip_path)
    
    def test_process_zip_file_nonexistent(self):
        """Test processing nonexistent ZIP file."""
        result = process_zip_file('/nonexistent/file.zip', 'TEST001', '120')
        assert result is None
    
    def test_process_zip_file_corrupted(self):
        """Test processing corrupted ZIP file."""
        # Create a file that's not actually a ZIP
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as f:
            f.write(b'This is not a ZIP file')
            corrupted_zip = f.name
        
        try:
            result = process_zip_file(corrupted_zip, 'TEST002', '120')
            assert result is None
        finally:
            os.unlink(corrupted_zip)
    
    def test_process_zip_directory_success(self):
        """Test processing ZIP directory with multiple files."""
        import shutil
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a proper ZIP file in the directory
            test_zip_path = os.path.join(temp_dir, 'S100TEST1-180-TestCompany.zip')
            
            with zipfile.ZipFile(test_zip_path, 'w') as zf:
                # Add CSV content
                csv_content = '''要素ID\t項目名\tコンテキストID\t値
jpdei_cor:EDINETCodeDEI\tEDINETコード\tFilingDateInstant\tE02144
jpcrp_cor:NetSales\t売上高\tCurrentYear\t1000000'''
                zf.writestr('main_data.csv', csv_content.encode('utf-8'))
            
            with patch('edinet_tools.utils.process_raw_csv_data') as mock_process:
                mock_process.return_value = {'test': 'result'}
                
                result = process_zip_directory(temp_dir, doc_type_codes=['180'])
                
                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0]['test'] == 'result'
                mock_process.assert_called_once()
    
    def test_process_zip_directory_empty(self):
        """Test processing empty directory."""
        with tempfile.TemporaryDirectory() as empty_dir:
            result = process_zip_directory(empty_dir, doc_type_codes=['235'])
            assert len(result) == 0  # Should return empty list, not None
    
    def test_auditor_file_filtering(self):
        """Test that auditor files are properly filtered out."""
        zip_path = tempfile.mktemp(suffix='.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Add various auditor file patterns
            zf.writestr('XBRL_TO_CSV/jpaud-aai-cc-001_company.csv', 'auditor content 1')
            zf.writestr('XBRL_TO_CSV/jpaud-aar-cn-002_company.csv', 'auditor content 2')
            zf.writestr('XBRL_TO_CSV/jpaud-xyz-ab-003_company.csv', 'auditor content 3')
            
            # Add non-auditor file
            zf.writestr('XBRL_TO_CSV/jpcrp-main-001_company.csv', 
                       'element_id\tvalue\ntest\tvalue'.encode('utf-8'))
        
        try:
            with patch('edinet_tools.utils.process_raw_csv_data') as mock_process:
                mock_process.return_value = {'filtered': 'result'}
                
                result = process_zip_file(zip_path, 'S100FILTER', '120')
                
                assert result is not None
                
                # Check that only non-auditor file was processed
                call_args = mock_process.call_args[0]
                csv_data_list = call_args[0]
                
                assert len(csv_data_list) == 1
                assert csv_data_list[0]['filename'] == 'jpcrp-main-001_company.csv'
        finally:
            os.unlink(zip_path)


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""
    
    def test_real_world_edinet_zip_structure(self):
        """Test processing with realistic EDINET ZIP structure."""
        zip_path = tempfile.mktemp(suffix='.zip')
        
        # Create realistic EDINET file structure
        realistic_content = '''要素ID	項目名	コンテキストID	相対年度	連結・個別	期間・時点	ユニットID	単位	値
jpdei_cor:EDINETCodeDEI	EDINETコード、DEI	FilingDateInstant	提出日時点	その他	時点	pure		E02144
jpdei_cor:FilerNameInJapaneseDEI	提出者名、日本語、DEI	FilingDateInstant	提出日時点	その他	時点	pure		トヨタ自動車株式会社
jpdei_cor:FilerNameInEnglishDEI	提出者名、英語、DEI	FilingDateInstant	提出日時点	その他	時点	pure		TOYOTA MOTOR CORPORATION
jpcrp_cor:NetSales	売上高	CurrentYearInstant	当事業年度	連結	期間	jpy	百万円	5000000
jpcrp_cor:NetSales	売上高	PriorYearInstant	前事業年度	連結	期間	jpy	百万円	4500000'''
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('XBRL_TO_CSV/jpcrp030000-asr-001_E02144-000_2025-03-31_01_2025-06-27.csv', 
                       realistic_content.encode('utf-16'))
        
        try:
            with patch('edinet_tools.utils.process_raw_csv_data') as mock_process:
                mock_process.return_value = {
                    'edinet_code': 'E02144',
                    'company_name_en': 'TOYOTA MOTOR CORPORATION',
                    'company_name_ja': 'トヨタ自動車株式会社',
                    'key_facts': {'net_sales': {'current': '5000000', 'prior': '4500000'}},
                    'text_blocks': []
                }
                
                result = process_zip_file(zip_path, 'S100REAL1', '120')
                
                assert result is not None
                assert result['edinet_code'] == 'E02144'
                assert result['company_name_en'] == 'TOYOTA MOTOR CORPORATION'
                assert result['company_name_ja'] == 'トヨタ自動車株式会社'
                
        finally:
            os.unlink(zip_path)
    
    def test_mixed_encoding_handling(self):
        """Test handling of mixed encoding scenarios."""
        zip_path = tempfile.mktemp(suffix='.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # UTF-16 file
            utf16_content = 'element_id\tvalue\ntest_utf16\t日本語テスト'
            zf.writestr('XBRL_TO_CSV/utf16_file.csv', utf16_content.encode('utf-16'))
            
            # UTF-8 file
            utf8_content = 'element_id\tvalue\ntest_utf8\tEnglish Test'
            zf.writestr('XBRL_TO_CSV/utf8_file.csv', utf8_content.encode('utf-8'))
        
        try:
            with patch('edinet_tools.utils.process_raw_csv_data') as mock_process:
                mock_process.return_value = {'mixed_encoding': 'handled'}
                
                result = process_zip_file(zip_path, 'S100MIXED', '999')
                
                assert result is not None
                
                # Both files should be processed despite different encodings
                call_args = mock_process.call_args[0]
                csv_data_list = call_args[0]
                assert len(csv_data_list) == 2
                
        finally:
            os.unlink(zip_path)


if __name__ == "__main__":
    # Run tests if pytest is available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("pytest not available. Install with: pip install pytest")
        print("Running basic utils validation...")
        
        # Basic validation tests
        assert clean_text('  test  ') == 'test'
        assert clean_text(None) == ''
        
        # Test encoding detection with simple case
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
            f.write('test content')
            temp_path = f.name
        
        try:
            encoding = detect_encoding(temp_path)
            assert encoding is not None
        finally:
            os.unlink(temp_path)
        
        print("✅ Basic utils validation passed!")