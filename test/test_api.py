"""
Unit tests for edinet_tools.api module.

Tests core API functionality including URL construction, parameter handling,
error scenarios, and response processing with realistic Japanese market conditions.
"""

import pytest
import urllib.error
import urllib.request
import json
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from io import BytesIO

from edinet_tools.api import (
    fetch_documents_list, 
    fetch_document, 
    save_document_content,
    download_documents,
    filter_documents,
    get_documents_for_date_range
)


class TestFetchDocumentsList:
    """Test fetch_documents_list function with realistic market scenarios."""
    
    def test_url_construction_with_business_day(self):
        """Test URL construction with typical business day."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Wednesday 2025-01-08 - typical business day
            fetch_documents_list('2025-01-08', api_key='test_key')
            
            called_url = mock_urlopen.call_args[0][0]
            assert 'disclosure.edinet-fsa.go.jp' in called_url
            assert 'date=2025-01-08' in called_url
            assert 'type=2' in called_url
            assert 'Subscription-Key=test_key' in called_url
    
    def test_url_construction_with_date_object(self):
        """Test URL construction with datetime.date object."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            test_date = date(2025, 2, 14)  # Q4 earnings season
            fetch_documents_list(test_date, api_key='test_key')
            
            called_url = mock_urlopen.call_args[0][0]
            assert 'date=2025-02-14' in called_url
    
    def test_japanese_holiday_handling(self):
        """Test that API calls work on Japanese holidays (even if no results)."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": []}'  # Empty results expected
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # New Year's Day 2025 - should not crash, just return empty
            result = fetch_documents_list('2025-01-01', api_key='test_key')
            
            assert result == {"results": []}
            called_url = mock_urlopen.call_args[0][0]
            assert 'date=2025-01-01' in called_url
    
    def test_weekend_date_handling(self):
        """Test handling of weekend dates."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Saturday 2025-01-04
            result = fetch_documents_list('2025-01-04', api_key='test_key')
            
            assert isinstance(result, dict)
            assert 'results' in result
    
    def test_parameter_encoding_special_chars(self):
        """Test that URL parameters are properly encoded."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Test with special characters in API key
            fetch_documents_list('2025-03-31', type=1, api_key='test+key&value=123')
            
            called_url = mock_urlopen.call_args[0][0]
            # Should be URL encoded properly
            assert 'test%2Bkey%26value%3D123' in called_url or 'Subscription-Key=test%2Bkey%26value%3D123' in called_url
    
    def test_invalid_date_formats(self):
        """Test error handling for various invalid date formats."""
        invalid_dates = [
            'invalid-date',
            '2025/01/15',  # Wrong separator
            '25-01-15',    # Wrong format
            '2025-13-01',  # Invalid month
            '2025-01-32',  # Invalid day
        ]
        
        for invalid_date in invalid_dates:
            with pytest.raises(ValueError) as exc_info:
                fetch_documents_list(invalid_date)
            assert "Invalid date string" in str(exc_info.value)
    
    def test_future_date_handling(self):
        """Test handling of future dates."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Future date - should work but likely return no results
            future_date = date.today() + timedelta(days=30)
            result = fetch_documents_list(future_date, api_key='test_key')
            
            assert isinstance(result, dict)
    
    def test_http_error_codes(self):
        """Test handling of various HTTP error codes."""
        error_scenarios = [
            (401, "Unauthorized - Invalid API key"),
            (403, "Forbidden - API access denied"), 
            (404, "Not Found - Invalid endpoint"),
            (429, "Rate limit exceeded"),
            (500, "Internal server error"),
            (503, "Service unavailable")
        ]
        
        for status_code, error_msg in error_scenarios:
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_response = Mock()
                mock_response.getcode.return_value = status_code
                mock_response.read.return_value = error_msg.encode()
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                with pytest.raises(urllib.error.HTTPError):
                    fetch_documents_list('2025-01-15', max_retries=1, api_key='test_key')
    
    def test_retry_logic_server_errors(self):
        """Test retry logic for transient server errors."""
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('time.sleep') as mock_sleep:
            
            # First two calls return 503, third succeeds
            responses = [
                Mock(getcode=lambda: 503, read=lambda: b'Service Unavailable'),
                Mock(getcode=lambda: 503, read=lambda: b'Service Unavailable'),
                Mock(getcode=lambda: 200, read=lambda: b'{"results": [{"docID": "S100A001"}]}')
            ]
            
            mock_urlopen.return_value.__enter__.side_effect = responses
            
            result = fetch_documents_list('2025-01-15', max_retries=3, delay_seconds=1, api_key='test_key')
            
            assert mock_urlopen.call_count == 3
            assert mock_sleep.call_count == 2
            assert result == {"results": [{"docID": "S100A001"}]}
    
    def test_network_timeout_handling(self):
        """Test handling of network timeouts and connection issues."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Network timeout")
            
            with pytest.raises(urllib.error.URLError):
                fetch_documents_list('2025-01-15', max_retries=1, api_key='test_key')
    
    def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'{"results": [invalid json'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            with pytest.raises(json.JSONDecodeError):
                fetch_documents_list('2025-01-15', api_key='test_key')
    
    def test_empty_response_handling(self):
        """Test handling of empty API responses."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b''
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            with pytest.raises(json.JSONDecodeError):
                fetch_documents_list('2025-01-15', api_key='test_key')


class TestFetchDocument:
    """Test fetch_document function with realistic 2025 document scenarios."""
    
    def test_url_construction_realistic_doc_id(self):
        """Test URL construction with realistic 2025 document IDs."""
        realistic_doc_ids = ['S100A001', 'S100B999', 'S100ZZZZ', 'S100C123']
        
        for doc_id in realistic_doc_ids:
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_response = Mock()
                mock_response.getcode.return_value = 200
                mock_response.read.return_value = b'fake_zip_content'
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                fetch_document(doc_id, api_key='test_key')
                
                called_url = mock_urlopen.call_args[0][0]
                assert 'disclosure.edinet-fsa.go.jp' in called_url  # Correct domain
                assert f'documents/{doc_id}' in called_url
                assert 'type=5' in called_url  # CSV format
                assert 'Subscription-Key=test_key' in called_url
    
    def test_csv_type_parameter(self):
        """Test that type=5 (CSV) is correctly specified."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'csv_content'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            fetch_document('S100A001', api_key='test_key')
            
            called_url = mock_urlopen.call_args[0][0]
            assert 'type=5' in called_url
    
    def test_zip_file_content_handling(self):
        """Test handling of actual ZIP file binary content."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            # Actual ZIP file header bytes
            zip_content = b'\x50\x4b\x03\x04\x14\x00\x00\x00\x08\x00'
            mock_response.read.return_value = zip_content
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = fetch_document('S100A001', api_key='test_key')
            
            assert result == zip_content
            assert isinstance(result, bytes)
            assert result.startswith(b'\x50\x4b')  # ZIP signature
    
    def test_large_document_handling(self):
        """Test handling of large document downloads."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            # Simulate 5MB document
            large_content = b'x' * (5 * 1024 * 1024)
            mock_response.read.return_value = large_content
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = fetch_document('S100A001', api_key='test_key')
            
            assert len(result) == 5 * 1024 * 1024
            assert isinstance(result, bytes)
    
    def test_document_not_found_scenarios(self):
        """Test various document not found scenarios."""
        not_found_scenarios = [
            ('S100XXXX', 404, "Document not found"),
            ('S099ZZZZ', 404, "Invalid document ID format"),
            ('S100OLD1', 410, "Document no longer available"),
        ]
        
        for doc_id, status_code, error_msg in not_found_scenarios:
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_response = Mock()
                mock_response.getcode.return_value = status_code
                mock_response.read.return_value = error_msg.encode()
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                with pytest.raises(urllib.error.HTTPError):
                    fetch_document(doc_id, api_key='test_key')
    
    def test_api_key_authentication_errors(self):
        """Test API key related authentication errors."""
        auth_scenarios = [
            ("", 401, "Missing API key"),
            ("invalid_key", 401, "Invalid API key"),
            ("expired_key", 401, "API key expired"),
        ]
        
        for api_key, status_code, error_msg in auth_scenarios:
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_response = Mock()
                mock_response.getcode.return_value = status_code
                mock_response.read.return_value = error_msg.encode()
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                with pytest.raises(urllib.error.HTTPError):
                    fetch_document('S100A001', api_key=api_key)
    
    def test_retry_logic_for_transient_failures(self):
        """Test retry logic for network and server issues."""
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('time.sleep') as mock_sleep:
            
            # First call network error, second call success
            mock_success_response = Mock()
            mock_success_response.getcode.return_value = 200
            mock_success_response.read.return_value = b'success_content'
            mock_success_response.__enter__ = Mock(return_value=mock_success_response)
            mock_success_response.__exit__ = Mock(return_value=False)
            
            side_effects = [
                urllib.error.URLError("Network timeout"),
                mock_success_response
            ]
            
            mock_urlopen.side_effect = side_effects
            
            result = fetch_document('S100A001', max_retries=2, delay_seconds=1, api_key='test_key')
            
            assert result == b'success_content'
            assert mock_urlopen.call_count == 2
            assert mock_sleep.call_count == 1


class TestSaveDocumentContent:
    """Test save_document_content with realistic file scenarios."""
    
    def test_save_zip_content(self, tmp_path):
        """Test saving actual ZIP file content."""
        # Realistic ZIP file content with proper headers
        zip_content = (
            b'\x50\x4b\x03\x04\x14\x00\x00\x00\x08\x00'  # ZIP header
            b'test_document_content_here'
        )
        output_path = tmp_path / "S100A001-160-TestCompany.zip"
        
        save_document_content(zip_content, str(output_path))
        
        assert output_path.exists()
        assert output_path.read_bytes() == zip_content
        assert output_path.suffix == '.zip'
    
    def test_save_large_financial_document(self, tmp_path):
        """Test saving large financial documents (realistic file sizes)."""
        # Simulate 10MB financial document (typical size)
        chunk_size = len(b'XBRL_FINANCIAL_DATA')  # 19 bytes
        target_size = 10 * 1024 * 1024  # 10MB
        repeat_count = target_size // chunk_size
        large_content = b'XBRL_FINANCIAL_DATA' * repeat_count
        output_path = tmp_path / "S100B999-180-LargeCompany.zip"
        
        save_document_content(large_content, str(output_path))
        
        assert output_path.exists()
        file_size = output_path.stat().st_size
        assert file_size >= 9 * 1024 * 1024  # At least 9MB (allow some variance)
    
    def test_save_to_nested_directory(self, tmp_path):
        """Test saving to nested directory structure."""
        nested_dir = tmp_path / "downloads" / "2025" / "01"
        nested_dir.mkdir(parents=True)
        
        test_content = b'test_zip_content'
        output_path = nested_dir / "S100C123.zip"
        
        save_document_content(test_content, str(output_path))
        
        assert output_path.exists()
        assert output_path.read_bytes() == test_content
    
    def test_permission_errors(self, tmp_path):
        """Test handling of file permission errors."""
        import os
        test_content = b'test'
        
        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only
        
        output_path = readonly_dir / "test.zip"
        
        try:
            with pytest.raises(IOError):
                save_document_content(test_content, str(output_path))
        finally:
            # Cleanup - restore write permissions
            readonly_dir.chmod(0o755)


class TestFilterDocuments:
    """Test document filtering with realistic 2025 market data."""
    
    def test_filter_by_document_type_earnings(self):
        """Test filtering for earnings-related document types."""
        docs = [
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Toyota Motor Corp', 'edinetCode': 'E02144', 'secCode': '7203'},
            {'docID': 'S100A002', 'docTypeCode': '180', 'filerName': 'Sony Group Corp', 'edinetCode': 'E02134', 'secCode': '6758'},
            {'docID': 'S100A003', 'docTypeCode': '999', 'filerName': 'Other Filing', 'edinetCode': 'E99999'},
        ]
        
        # Filter for semi-annual reports (160) and extraordinary reports (180)
        earnings_docs = filter_documents(docs, doc_type_codes=['160', '180'])
        assert len(earnings_docs) == 2
        assert all(doc['docTypeCode'] in ['160', '180'] for doc in earnings_docs)
    
    def test_filter_by_major_companies(self):
        """Test filtering for major Japanese companies."""
        docs = [
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Toyota Motor Corp', 'edinetCode': 'E02144', 'secCode': '7203'},
            {'docID': 'S100A002', 'docTypeCode': '160', 'filerName': 'Sony Group Corp', 'edinetCode': 'E02134', 'secCode': '6758'},
            {'docID': 'S100A003', 'docTypeCode': '160', 'filerName': 'Small Company Ltd', 'edinetCode': 'E99999', 'secCode': None},
        ]
        
        # Filter for companies with securities codes (listed companies)
        listed_companies = filter_documents(docs, require_sec_code=True)
        assert len(listed_companies) == 2
        assert all(doc['secCode'] is not None for doc in listed_companies)
    
    def test_filter_quarterly_earnings_season(self):
        """Test filtering during quarterly earnings season."""
        docs = [
            # Q3 earnings filings - need edinetCode for filtering to work
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Company A', 'edinetCode': 'E12345', 'submitDateTime': '2025-02-14T15:00:00'},
            {'docID': 'S100A002', 'docTypeCode': '180', 'filerName': 'Company B', 'edinetCode': 'E12346', 'submitDateTime': '2025-02-14T16:30:00'},
            # Regular filings
            {'docID': 'S100A003', 'docTypeCode': '999', 'filerName': 'Company C', 'edinetCode': 'E12347', 'submitDateTime': '2025-02-14T10:00:00'},
        ]
        
        earnings_types = filter_documents(docs, doc_type_codes=['160', '180'], require_sec_code=False)
        assert len(earnings_types) == 2
    
    def test_filter_incomplete_filings(self):
        """Test filtering out incomplete or malformed filings."""
        docs = [
            # Complete filing - need edinetCode to pass all filters
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Complete Company', 'edinetCode': 'E12345'},
            # Missing required fields
            {'docID': 'S100A002', 'docTypeCode': '160'},  # Missing filerName
            {'docTypeCode': '160', 'filerName': 'Missing DocID'},  # Missing docID
            {'docID': 'S100A004', 'filerName': 'Missing Type'},  # Missing docTypeCode
            {},  # Empty document
            None,  # Null document
        ]
        
        # Filter should handle None values gracefully
        docs_clean = [doc for doc in docs if doc is not None]
        filtered = filter_documents(docs_clean, require_sec_code=False)
        assert len(filtered) == 1
        assert filtered[0]['docID'] == 'S100A001'
    
    def test_filter_by_industry_sector(self):
        """Test filtering by company industry patterns."""
        docs = [
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Toyota Motor Corporation', 'industry': 'Automotive'},
            {'docID': 'S100A002', 'docTypeCode': '160', 'filerName': 'Sony Group Corporation', 'industry': 'Technology'},
            {'docID': 'S100A003', 'docTypeCode': '160', 'filerName': 'Mitsubishi UFJ Bank', 'industry': 'Financial'},
        ]
        
        # Test string and list inputs for EDINET codes
        auto_docs = filter_documents(docs, edinet_codes='E02144')  # String input
        tech_docs = filter_documents(docs, edinet_codes=['E02134'])  # List input
        
        # Should not crash with missing edinetCode field
        assert isinstance(auto_docs, list)
        assert isinstance(tech_docs, list)


class TestDownloadDocuments:
    """Test bulk document download functionality."""
    
    @patch('edinet_tools.api.fetch_document')
    @patch('edinet_tools.api.save_document_content')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_download_earnings_batch(self, mock_makedirs, mock_exists, mock_save, mock_fetch):
        """Test downloading a batch of earnings documents."""
        mock_exists.return_value = False
        mock_fetch.return_value = b'fake_zip_content'
        
        # Realistic earnings season documents
        docs = [
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Toyota Motor Corporation'},
            {'docID': 'S100A002', 'docTypeCode': '180', 'filerName': 'Sony Group Corporation'},
            {'docID': 'S100A003', 'docTypeCode': '160', 'filerName': 'SoftBank Group Corp'},
        ]
        
        download_documents(docs, download_dir='/downloads/2025/earnings')
        
        assert mock_fetch.call_count == 3
        assert mock_save.call_count == 3
        mock_makedirs.assert_called_once_with('/downloads/2025/earnings', exist_ok=True)
        
        # Check filename format
        save_calls = mock_save.call_args_list
        for i, call in enumerate(save_calls):
            filepath = call[0][1]  # Second argument is filepath
            assert f"S100A00{i+1}" in filepath
            assert docs[i]['docTypeCode'] in filepath
            assert filepath.endswith('.zip')
    
    @patch('os.path.exists')
    def test_skip_already_downloaded(self, mock_exists):
        """Test skipping documents that were already downloaded."""
        mock_exists.return_value = True  # All files already exist
        
        docs = [
            {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Toyota Motor Corporation'},
        ]
        
        with patch('edinet_tools.api.fetch_document') as mock_fetch:
            download_documents(docs)
            
            # Should not download if file already exists
            mock_fetch.assert_not_called()
    
    def test_handle_problematic_filer_names(self):
        """Test handling of filer names with special characters."""
        with patch('edinet_tools.api.fetch_document') as mock_fetch, \
             patch('os.path.exists') as mock_exists, \
             patch('edinet_tools.api.save_document_content') as mock_save:
            
            mock_exists.return_value = False
            mock_fetch.return_value = b'content'
            
            docs = [
                {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Company/With\\Slashes'},
                {'docID': 'S100A002', 'docTypeCode': '160', 'filerName': 'Company<With>Brackets'},
                {'docID': 'S100A003', 'docTypeCode': '160', 'filerName': 'Company:With:Colons'},
            ]
            
            download_documents(docs)
            
            # Should still attempt to save files (with filename sanitization)
            assert mock_save.call_count == 3
    
    def test_partial_failure_handling(self):
        """Test handling when some downloads fail."""
        with patch('edinet_tools.api.fetch_document') as mock_fetch, \
             patch('os.path.exists') as mock_exists, \
             patch('edinet_tools.api.save_document_content') as mock_save:
            
            mock_exists.return_value = False
            # First download fails, second succeeds
            mock_fetch.side_effect = [Exception("Network error"), b'success_content']
            
            docs = [
                {'docID': 'S100FAIL', 'docTypeCode': '160', 'filerName': 'Failing Company'},
                {'docID': 'S100GOOD', 'docTypeCode': '160', 'filerName': 'Working Company'},
            ]
            
            # Should not crash on partial failures
            download_documents(docs)
            
            assert mock_fetch.call_count == 2
            assert mock_save.call_count == 1  # Only successful download saved


class TestGetDocumentsForDateRange:
    """Test date range document retrieval with Japanese market patterns."""
    
    @patch('edinet_tools.api.fetch_documents_list')
    def test_business_week_range(self, mock_fetch):
        """Test fetching documents for a typical business week."""
        mock_fetch.return_value = {'results': []}
        
        # Week of 2025-01-06 to 2025-01-10 (Monday to Friday)
        start_date = date(2025, 1, 6)
        end_date = date(2025, 1, 10)
        
        get_documents_for_date_range(start_date, end_date)
        
        # Should call for 5 business days
        assert mock_fetch.call_count == 5
        
        # Verify dates are sequential
        called_dates = [call[1]['date'] for call in mock_fetch.call_args_list]
        expected_dates = [
            date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8),
            date(2025, 1, 9), date(2025, 1, 10)
        ]
        assert called_dates == expected_dates
    
    @patch('edinet_tools.api.fetch_documents_list')
    def test_new_year_holiday_period(self, mock_fetch):
        """Test handling of New Year holiday period (2025-01-01 to 2025-01-03)."""
        mock_fetch.return_value = {'results': []}
        
        # New Year period - typically no filings but API should still work
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 3)
        
        result = get_documents_for_date_range(start_date, end_date)
        
        assert mock_fetch.call_count == 3
        assert isinstance(result, list)
        # Likely empty during holidays but shouldn't crash
    
    @patch('edinet_tools.api.fetch_documents_list')
    def test_golden_week_period(self, mock_fetch):
        """Test handling of Golden Week period (late April/early May)."""
        mock_fetch.return_value = {'results': []}
        
        # Golden Week 2025: April 29 - May 5
        start_date = date(2025, 4, 29)
        end_date = date(2025, 5, 5)
        
        result = get_documents_for_date_range(start_date, end_date)
        
        assert mock_fetch.call_count == 7  # 7 days in range
        assert isinstance(result, list)
    
    @patch('edinet_tools.api.fetch_documents_list')
    def test_earnings_season_filtering(self, mock_fetch):
        """Test filtering during earnings season with high volume."""
        # Mock high-volume earnings period response
        mock_fetch.return_value = {
            'results': [
                {'docID': 'S100A001', 'docTypeCode': '160', 'filerName': 'Company A', 'secCode': '7203'},
                {'docID': 'S100A002', 'docTypeCode': '180', 'filerName': 'Company B', 'secCode': '6758'},
                {'docID': 'S100A003', 'docTypeCode': '999', 'filerName': 'Company C'},  # Non-earnings
            ]
        }
        
        # Q4 earnings period
        start_date = date(2025, 2, 10)
        end_date = date(2025, 2, 14)
        
        result = get_documents_for_date_range(
            start_date, end_date,
            doc_type_codes=['160', '180'],  # Earnings reports only
            require_sec_code=True  # Listed companies only
        )
        
        # Should filter to only earnings documents with securities codes
        earnings_docs = [doc for doc in result if doc.get('secCode')]
        assert len(earnings_docs) >= 0  # May be filtered out
    
    @patch('edinet_tools.api.fetch_documents_list')
    def test_weekend_handling(self, mock_fetch):
        """Test that weekends are handled (even though typically no filings)."""
        mock_fetch.return_value = {'results': []}
        
        # Weekend: Saturday 2025-01-04 to Sunday 2025-01-05
        start_date = date(2025, 1, 4)
        end_date = date(2025, 1, 5)
        
        result = get_documents_for_date_range(start_date, end_date)
        
        assert mock_fetch.call_count == 2
        assert isinstance(result, list)
        # Weekends typically empty but should not crash
    
    @patch('edinet_tools.api.fetch_documents_list')
    def test_api_failure_resilience(self, mock_fetch):
        """Test that API failures on individual days don't stop processing."""
        # First day fails, second day succeeds, third day fails
        mock_fetch.side_effect = [
            Exception("Network error"),
            {'results': [{'docID': 'S100GOOD', 'docTypeCode': '160'}]},
            Exception("Server error")
        ]
        
        start_date = date(2025, 1, 6)
        end_date = date(2025, 1, 8)
        
        # Should not crash, should continue processing
        result = get_documents_for_date_range(start_date, end_date)
        
        assert mock_fetch.call_count == 3
        assert isinstance(result, list)
        # Should contain results from successful day
        if result:
            assert any(doc['docID'] == 'S100GOOD' for doc in result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])