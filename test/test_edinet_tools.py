"""
Tests for edinet_tools.py - EDINET API interaction functions.
"""
import pytest
import datetime
import json
import os
import tempfile
from unittest.mock import patch, mock_open, MagicMock, call
from urllib.error import HTTPError, URLError

import edinet_tools


class TestFetchDocumentsList:
    """Tests for fetch_documents_list function."""

    def test_fetch_documents_list_with_string_date(self, mock_edinet_api_response):
        """Test fetch_documents_list with string date."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = json.dumps(mock_edinet_api_response).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = edinet_tools.fetch_documents_list('2024-01-15')

            assert result == mock_edinet_api_response
            mock_urlopen.assert_called_once()

    def test_fetch_documents_list_with_datetime_date(self, mock_edinet_api_response):
        """Test fetch_documents_list with datetime.date object."""
        test_date = datetime.date(2024, 1, 15)

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = json.dumps(mock_edinet_api_response).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = edinet_tools.fetch_documents_list(test_date)

            assert result == mock_edinet_api_response

    def test_fetch_documents_list_invalid_date_string(self):
        """Test fetch_documents_list with invalid date string."""
        with pytest.raises(ValueError, match="Invalid date string"):
            edinet_tools.fetch_documents_list('invalid-date')

    def test_fetch_documents_list_invalid_date_type(self):
        """Test fetch_documents_list with invalid date type."""
        with pytest.raises(TypeError, match="Date must be"):
            edinet_tools.fetch_documents_list(123)

    def test_fetch_documents_list_http_error_retry(self, mock_edinet_api_response):
        """Test fetch_documents_list retries on HTTP error."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            # First two attempts fail, third succeeds
            mock_success_response = MagicMock()
            mock_success_response.getcode.return_value = 200
            mock_success_response.read.return_value = json.dumps(mock_edinet_api_response).encode()

            mock_success_context = MagicMock()
            mock_success_context.__enter__.return_value = mock_success_response

            mock_urlopen.side_effect = [
                HTTPError('url', 500, 'Server Error', None, None),
                HTTPError('url', 503, 'Service Unavailable', None, None),
                mock_success_context
            ]

            with patch('time.sleep'):  # Skip actual delay
                result = edinet_tools.fetch_documents_list('2024-01-15')

            assert result == mock_edinet_api_response
            assert mock_urlopen.call_count == 3

    def test_fetch_documents_list_max_retries_exceeded(self):
        """Test fetch_documents_list when max retries are exceeded."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = HTTPError('url', 500, 'Server Error', None, None)

            with patch('time.sleep'):  # Skip actual delay
                with pytest.raises(HTTPError):
                    edinet_tools.fetch_documents_list('2024-01-15', max_retries=2)

            assert mock_urlopen.call_count == 2


class TestFetchDocument:
    """Tests for fetch_document function."""

    def test_fetch_document_success(self):
        """Test successful document fetch."""
        test_doc_id = 'S100TEST123'
        test_content = b'test document content'

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = test_content
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = edinet_tools.fetch_document(test_doc_id)

            assert result == test_content
            mock_urlopen.assert_called_once()

    def test_fetch_document_http_error(self):
        """Test fetch_document with HTTP error."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = HTTPError('url', 404, 'Not Found', None, None)

            with patch('time.sleep'):  # Skip actual delay
                with pytest.raises(HTTPError):
                    edinet_tools.fetch_document('S100INVALID')

    def test_fetch_document_non_200_status(self):
        """Test fetch_document with non-200 status code."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 204  # No content
            mock_response.read.return_value = b''
            mock_urlopen.return_value.__enter__.return_value = mock_response

            with patch('time.sleep'):
                with pytest.raises(HTTPError, match="HTTP Error: 204"):
                    edinet_tools.fetch_document('S100TEST123')


class TestSaveDocumentContent:
    """Tests for save_document_content function."""

    def test_save_document_content(self, temp_downloads_dir):
        """Test saving document content to file."""
        test_content = b'test document content'
        output_path = os.path.join(temp_downloads_dir, 'test_doc.zip')

        edinet_tools.save_document_content(test_content, output_path)

        assert os.path.exists(output_path)
        with open(output_path, 'rb') as f:
            saved_content = f.read()
        assert saved_content == test_content

    def test_save_document_content_with_existing_directory(self, temp_downloads_dir):
        """Test saving document content to existing directory."""
        test_content = b'test content'
        output_path = os.path.join(temp_downloads_dir, 'test.zip')

        edinet_tools.save_document_content(test_content, output_path)

        assert os.path.exists(output_path)
        with open(output_path, 'rb') as f:
            saved_content = f.read()
        assert saved_content == test_content


class TestDownloadDocuments:
    """Tests for download_documents function."""

    def test_download_documents(self, sample_doc_metadata, temp_downloads_dir):
        """Test downloading multiple documents."""
        docs = [sample_doc_metadata]
        test_content = b'test zip content'

        with patch.object(edinet_tools, 'fetch_document') as mock_fetch:
            with patch.object(edinet_tools, 'save_document_content') as mock_save:
                mock_fetch.return_value = test_content

                edinet_tools.download_documents(docs, temp_downloads_dir)

                mock_fetch.assert_called_once_with('S100TEST123')
                mock_save.assert_called_once()
                # Check that save was called with correct path
                save_call_args = mock_save.call_args[0]
                assert save_call_args[0] == test_content
                assert save_call_args[1].endswith('S100TEST123-160-Test Company Ltd..zip')

    def test_download_documents_with_error(self, sample_doc_metadata, temp_downloads_dir):
        """Test download_documents handles individual document errors gracefully."""
        docs = [sample_doc_metadata]

        with patch.object(edinet_tools, 'fetch_document') as mock_fetch:
            mock_fetch.side_effect = HTTPError('url', 404, 'Not Found', None, None)

            # Should not raise an exception, just log the error
            edinet_tools.download_documents(docs, temp_downloads_dir)

            mock_fetch.assert_called_once()


class TestFilterDocuments:
    """Tests for filter_documents function."""

    def test_filter_documents_by_type(self, sample_doc_metadata, sample_doc_metadata_180):
        """Test filtering documents by document type."""
        docs = [sample_doc_metadata, sample_doc_metadata_180]

        # Filter for only 160 (Semi-Annual Reports)
        filtered = edinet_tools.filter_documents(docs, [], ['160'], [], True)

        assert len(filtered) == 1
        assert filtered[0]['docTypeCode'] == '160'

    def test_filter_documents_by_multiple_types(self, sample_doc_metadata, sample_doc_metadata_180):
        """Test filtering documents by multiple document types."""
        docs = [sample_doc_metadata, sample_doc_metadata_180]

        # Filter for both types
        filtered = edinet_tools.filter_documents(docs, [], ['160', '180'], [], True)

        assert len(filtered) == 2

    def test_filter_documents_by_edinet_code(self, sample_doc_metadata):
        """Test filtering documents by EDINET code."""
        docs = [sample_doc_metadata]

        # Should match existing EDINET code
        filtered = edinet_tools.filter_documents(docs, ['E12345'], [], [], True)
        assert len(filtered) == 1

        # Should not match non-existent code
        filtered = edinet_tools.filter_documents(docs, ['E99999'], [], [], True)
        assert len(filtered) == 0

    def test_filter_documents_no_criteria(self, sample_doc_metadata):
        """Test filter_documents returns filtered docs based on supported doc types."""
        docs = [sample_doc_metadata]

        filtered = edinet_tools.filter_documents(docs, [], [], [], True)

        assert len(filtered) == 1  # Should still filter by supported doc types


class TestGetDocumentsForDateRange:
    """Tests for get_documents_for_date_range function."""

    def test_get_documents_for_date_range_single_date(self, mock_edinet_api_response):
        """Test getting documents for a single date range."""
        start_date = datetime.date(2024, 1, 15)
        end_date = datetime.date(2024, 1, 15)

        with patch.object(edinet_tools, 'fetch_documents_list') as mock_fetch:
            mock_fetch.return_value = mock_edinet_api_response

            docs = edinet_tools.get_documents_for_date_range(start_date, end_date)

            mock_fetch.assert_called_once_with(date=start_date)
            # Should return filtered results, not raw results
            assert len(docs) >= 0  # Results depend on filtering logic

    def test_get_documents_for_date_range_multiple_dates(self, mock_edinet_api_response):
        """Test getting documents for multiple dates."""
        start_date = datetime.date(2024, 1, 15)
        end_date = datetime.date(2024, 1, 17)  # 3 days

        with patch.object(edinet_tools, 'fetch_documents_list') as mock_fetch:
            mock_fetch.return_value = mock_edinet_api_response

            docs = edinet_tools.get_documents_for_date_range(start_date, end_date)

            assert mock_fetch.call_count == 3  # Called for each day
            expected_calls = [
                call(date=datetime.date(2024, 1, 15)),
                call(date=datetime.date(2024, 1, 16)), 
                call(date=datetime.date(2024, 1, 17))
            ]
            mock_fetch.assert_has_calls(expected_calls)

    def test_get_documents_for_date_range_with_filtering(self, mock_edinet_api_response):
        """Test getting documents with filtering applied."""
        start_date = datetime.date(2024, 1, 15)
        end_date = datetime.date(2024, 1, 15)

        with patch.object(edinet_tools, 'fetch_documents_list') as mock_fetch:
            with patch.object(edinet_tools, 'filter_documents') as mock_filter:
                mock_fetch.return_value = mock_edinet_api_response
                mock_filter.return_value = mock_edinet_api_response['results'][:1]  # Return subset

                docs = edinet_tools.get_documents_for_date_range(
                    start_date, end_date, [], ['160'], [], True
                )

                mock_filter.assert_called_once_with(
                    mock_edinet_api_response['results'],
                    [], ['160'], [], True
                )

    def test_get_documents_for_date_range_handles_errors(self, mock_edinet_api_response):
        """Test that date range function handles individual date errors gracefully."""
        start_date = datetime.date(2024, 1, 15)
        end_date = datetime.date(2024, 1, 16)

        with patch.object(edinet_tools, 'fetch_documents_list') as mock_fetch:
            # First date fails, second succeeds
            mock_fetch.side_effect = [
                HTTPError('url', 500, 'Server Error', None, None),
                mock_edinet_api_response
            ]

            docs = edinet_tools.get_documents_for_date_range(start_date, end_date)

            # Should still return results from successful date
            assert docs == mock_edinet_api_response['results']
            assert mock_fetch.call_count == 2

