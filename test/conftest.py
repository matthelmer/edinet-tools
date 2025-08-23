"""
Pytest configuration and fixtures for EDINET API Tools tests.
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import MagicMock

# Sample document metadata for testing
@pytest.fixture
def sample_doc_metadata():
    """Sample EDINET document metadata."""
    return {
        'docID': 'S100TEST123',
        'edinetCode': 'E12345',
        'secCode': '1234',
        'filerName': 'Test Company Ltd.',
        'docTypeCode': '160',
        'submitDateTime': '2024-01-15 15:30:00',
        'periodStart': '2023-04-01',
        'periodEnd': '2023-09-30',
    }

@pytest.fixture  
def sample_doc_metadata_180():
    """Sample extraordinary report metadata."""
    return {
        'docID': 'S100EXTRA456',
        'edinetCode': 'E67890',
        'secCode': '5678', 
        'filerName': 'Another Test Company',
        'docTypeCode': '180',
        'submitDateTime': '2024-01-20 10:15:00',
        'periodStart': None,
        'periodEnd': None,
    }

@pytest.fixture
def sample_csv_data():
    """Sample CSV data structure from processed documents."""
    return {
        'company_info': {
            'company_name_ja': 'テスト株式会社',
            'company_name_en': 'Test Company Ltd.',
            'securities_code': '1234'
        },
        'financial_data': {
            'total_assets': '1000000000',
            'total_liabilities': '600000000', 
            'net_assets': '400000000'
        }
    }

@pytest.fixture
def sample_text_blocks():
    """Sample text blocks from document processing."""
    return [
        {
            'title': 'Business Overview',
            'title_en': 'Business Overview',
            'content_jp': 'テスト会社の事業概要です。',
            'content': 'This is a test company business overview.'
        },
        {
            'title': 'Financial Highlights',
            'title_en': 'Financial Highlights', 
            'content_jp': '財務ハイライトです。',
            'content': 'These are the financial highlights.'
        }
    ]

@pytest.fixture
def sample_structured_data(sample_csv_data, sample_text_blocks):
    """Sample structured document data."""
    return {
        'doc_id': 'S100TEST123',
        'company_name_en': 'Test Company Ltd.',
        'company_name_ja': 'テスト株式会社',
        'document_type': 'Semi-Annual Report',
        'document_title': 'Semi-Annual Securities Report',
        'key_facts': sample_csv_data,
        'text_blocks': sample_text_blocks,
        'submit_date_time': '2024-01-15 15:30:00'
    }

@pytest.fixture
def temp_downloads_dir():
    """Temporary directory for download tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing analysis tools."""
    mock_response = MagicMock()
    mock_response.text.return_value = '{"company_name_en": "Test Company Ltd.", "summary": "Test summary"}'
    mock_response.schema_object = None
    return mock_response

@pytest.fixture
def mock_edinet_api_response():
    """Mock EDINET API response."""
    return {
        'metadata': {
            'title': 'Test Response',
            'parameter': {
                'date': '2024-01-15',
                'type': '2'
            }
        },
        'results': [
            {
                'seqNumber': 1,
                'docID': 'S100TEST123',
                'edinetCode': 'E12345',
                'secCode': '1234',
                'JCN': '1234567890123',
                'filerName': 'Test Company Ltd.',
                'fundCode': None,
                'ordinanceCode': '010',
                'formCode': '030000',
                'docTypeCode': '160',
                'periodStart': '2023-04-01',
                'periodEnd': '2023-09-30',
                'submitDateTime': '2024-01-15 15:30:00',
                'docDescription': 'Semi-Annual Securities Report',
                'issuerEdinetCode': None,
                'subjectEdinetCode': None,
                'subsidiaryEdinetCode': None,
                'currentReportReason': None,
                'parentDocID': None,
                'opeDateTime': '2024-01-15 15:35:00',
                'withdrawalStatus': '0',
                'docInfoEditStatus': '0',
                'disclosureStatus': '0',
                'xbrlFlag': '1',
                'pdfFlag': '1',
                'attachDocFlag': '0',
                'englishDocFlag': '0'
            }
        ]
    }

@pytest.fixture(autouse=True)
def set_test_env_vars():
    """Set test environment variables."""
    original_env = {}
    test_env_vars = {
        'EDINET_API_KEY': 'test-api-key',
        'LLM_API_KEY': 'test-llm-key',
        'LLM_MODEL': 'claude-4-sonnet',
        'LLM_FALLBACK_MODEL': 'gpt-5-mini'
    }

    # Store original values and set test values
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original values
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def sample_xbrl_financial_metrics():
    """Sample processed XBRL financial metrics for testing."""
    return {
        'has_xbrl_data': True,
        'metrics_count': 4,
        'financial_metrics': {
            'revenue_ifrs': {
                'current': 1000000000.0,
                'prior': 800000000.0,
                'element_name': 'jpcrp_cor:RevenueIFRSSummaryOfBusinessResults'
            },
            'revenue_jgaap': {
                'current': 500000000.0,  # Converted from thousands
                'prior': 400000000.0,    # Converted from thousands  
                'element_name': 'jpcrp_cor:NetSalesSummaryOfBusinessResults'
            }
        }
    }
