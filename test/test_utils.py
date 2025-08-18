"""
Simplified tests for utils.py - Core utility function tests.
"""
import pytest
import os
import tempfile
import zipfile
import pandas as pd
from unittest.mock import patch, MagicMock

import utils


class TestDetectEncoding:
    """Basic tests for detect_encoding function."""

    def test_detect_encoding_basic(self, temp_downloads_dir):
        """Test basic encoding detection."""
        test_file = os.path.join(temp_downloads_dir, 'test.txt')
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('test content')

        encoding = utils.detect_encoding(test_file)
        assert encoding is not None

    def test_detect_encoding_missing_file(self):
        """Test encoding detection with missing file."""
        encoding = utils.detect_encoding('/nonexistent/file.txt')
        assert encoding is None


class TestReadCsvFile:
    """Basic tests for read_csv_file function."""

    def test_read_csv_file_basic(self, temp_downloads_dir):
        """Test basic CSV reading."""
        test_csv = os.path.join(temp_downloads_dir, 'test.csv')

        # Create tab-separated CSV (as expected by the function)
        with open(test_csv, 'w', encoding='utf-8') as f:
            f.write('要素ID\t値\n')  # Real tabs, not \\t
            f.write('element1\tvalue1\n')
            f.write('element2\tvalue2\n')

        result = utils.read_csv_file(test_csv)

        # Function may return list or DataFrame depending on success
        assert result is not None
        assert len(result) > 0

    def test_read_csv_file_missing(self):
        """Test reading non-existent CSV file."""
        result = utils.read_csv_file('/nonexistent/file.csv')
        assert result is None


class TestCleanText:
    """Basic tests for clean_text function."""

    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        text = "  Some text with spaces  \n"  # Real newline
        result = utils.clean_text(text)
        assert result == "Some text with spaces"

    def test_clean_text_none(self):
        """Test clean_text with None input."""
        result = utils.clean_text(None)
        assert result is None

    def test_clean_text_empty(self):
        """Test clean_text with empty string."""
        result = utils.clean_text("")
        assert result == ""

    def test_clean_text_japanese(self):
        """Test clean_text with Japanese text."""
        text = "テストテキスト"
        result = utils.clean_text(text)
        assert result == "テストテキスト"


class TestProcessZipFile:
    """Basic tests for process_zip_file function."""

    def create_test_zip(self, zip_path: str):
        """Helper to create a test ZIP file."""
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('XBRL_TO_CSV/test.csv', '要素ID\t値\nelement1\tvalue1\n')

    def test_process_zip_file_basic(self, temp_downloads_dir):
        """Test basic ZIP file processing."""
        zip_path = os.path.join(temp_downloads_dir, 'test.zip')
        self.create_test_zip(zip_path)

        result = utils.process_zip_file(zip_path, 'TEST123', '160')

        assert result is not None
        assert result['doc_id'] == 'TEST123'
        assert result['doc_type_code'] == '160'

    def test_process_zip_file_missing(self):
        """Test processing non-existent ZIP file."""
        result = utils.process_zip_file('/nonexistent/file.zip', 'TEST', '160')
        assert result is None

    def test_process_zip_file_corrupted(self, temp_downloads_dir):
        """Test processing corrupted ZIP file."""
        zip_path = os.path.join(temp_downloads_dir, 'corrupted.zip')

        with open(zip_path, 'w') as f:
            f.write('Not a ZIP file')

        result = utils.process_zip_file(zip_path, 'TEST', '160')
        assert result is None


class TestProcessZipDirectory:
    """Basic tests for process_zip_directory function."""

    def test_process_zip_directory_empty(self, temp_downloads_dir):
        """Test processing empty directory."""
        result = utils.process_zip_directory(temp_downloads_dir, ['160'])
        assert result == []

    def test_process_zip_directory_basic(self, temp_downloads_dir):
        """Test basic directory processing."""
        # Create a sample ZIP file
        zip_path = os.path.join(temp_downloads_dir, 'S100TEST-160-Company.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('XBRL_TO_CSV/test.csv', '要素ID\t値\nelement\tvalue\n')

        result = utils.process_zip_directory(temp_downloads_dir, ['160'])

        # Should process the file successfully
        assert isinstance(result, list)

    def test_process_zip_directory_missing(self):
        """Test processing non-existent directory."""
        result = utils.process_zip_directory('/nonexistent/path', ['160'])
        assert result == []


class TestUtilsIntegration:
    """Integration tests for utils functions."""

    def test_full_pipeline_basic(self, temp_downloads_dir):
        """Test basic full pipeline functionality."""
        zip_path = os.path.join(temp_downloads_dir, 'S100REAL-160-Company.zip')

        # Create realistic ZIP structure
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('XBRL_TO_CSV/data.csv', '要素ID\t値\njppfs_cor:CompanyName\tTest Company\n')

        # Test processing
        result = utils.process_zip_file(zip_path, 'S100REAL', '160')

        assert result is not None
        assert result['doc_id'] == 'S100REAL'
        assert isinstance(result, dict)

    def test_error_handling_graceful(self):
        """Test that functions handle errors gracefully."""
        # Test various error conditions that should be handled
        assert utils.read_csv_file('/nonexistent') is None
        assert utils.process_zip_file('/nonexistent', 'test', '160') is None

        # Functions should not crash on valid inputs
        assert utils.clean_text("test") == "test"
        assert utils.clean_text(None) is None
