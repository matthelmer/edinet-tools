"""
Integration tests for EDINET Tools package.

Tests the complete package functionality end-to-end.
"""

import pytest
import edinet_tools
from edinet_tools.exceptions import ConfigurationError, CompanyNotFoundError


class TestPackageImports:
    """Test package-level imports and exports."""
    
    def test_package_version(self):
        """Test package version is available."""
        assert hasattr(edinet_tools, '__version__')
        assert edinet_tools.__version__ == "0.1.0"
    
    def test_main_exports(self):
        """Test main package exports are available."""
        # Main client class
        assert hasattr(edinet_tools, 'EdinetClient')
        
        # Company lookup functions
        assert hasattr(edinet_tools, 'search_companies')
        assert hasattr(edinet_tools, 'ticker_to_edinet')
        assert hasattr(edinet_tools, 'resolve_company')
        assert hasattr(edinet_tools, 'get_supported_companies')
        
        # Document types
        assert hasattr(edinet_tools, 'DOCUMENT_TYPES')
        
        # Convenience functions
        assert hasattr(edinet_tools, 'get_client')


class TestPackageLevelFunctions:
    """Test package-level convenience functions."""
    
    def test_ticker_lookup(self):
        """Test package-level ticker lookup."""
        edinet_code = edinet_tools.ticker_to_edinet('7203')
        assert edinet_code == 'E02144'
    
    def test_company_search(self):
        """Test package-level company search."""
        results = edinet_tools.search_companies('Toyota')
        assert len(results) > 0
        assert any('TOYOTA' in r['name_en'] for r in results)
    
    def test_supported_companies(self):
        """Test getting supported companies list."""
        companies = edinet_tools.get_supported_companies()
        assert len(companies) > 0
        assert all('edinet_code' in c for c in companies)
    
    def test_document_types(self):
        """Test document types mapping."""
        doc_types = edinet_tools.DOCUMENT_TYPES
        assert isinstance(doc_types, dict)
        assert len(doc_types) > 0


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    def test_company_discovery_workflow(self):
        """Test complete company discovery workflow."""
        # 1. Search for companies
        search_results = edinet_tools.search_companies('Auto')
        assert len(search_results) > 0
        
        # 2. Get detailed info about a company
        toyota_results = edinet_tools.search_companies('Toyota')
        assert len(toyota_results) > 0
        toyota = toyota_results[0]
        
        # 3. Resolve different identifiers for the same company
        edinet_by_ticker = edinet_tools.ticker_to_edinet(toyota['ticker'])
        edinet_by_resolve = edinet_tools.resolve_company(toyota['ticker'])
        assert edinet_by_ticker == toyota['edinet_code']
        assert edinet_by_resolve == toyota['edinet_code']
    
    def test_client_creation_workflow(self):
        """Test client creation and basic functionality."""
        # Test with no API key (should fail gracefully)
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError):
                edinet_tools.get_client()
        
        # Test with dummy API key
        client = edinet_tools.get_client(api_key='dummy_key')
        assert isinstance(client, edinet_tools.EdinetClient)
        
        # Test client functionality
        results = client.search_companies('Sony')
        assert len(results) > 0
    
    def test_error_handling_workflow(self):
        """Test error handling across the package."""
        # Invalid company lookup
        edinet_code = edinet_tools.ticker_to_edinet('INVALID')
        assert edinet_code is None
        
        resolved = edinet_tools.resolve_company('INVALID')
        assert resolved is None
        
        # Empty search
        results = edinet_tools.search_companies('')
        assert len(results) == 0
        
        # Client with invalid company
        client = edinet_tools.EdinetClient(api_key='dummy')
        with pytest.raises(CompanyNotFoundError):
            client._resolve_company_identifier('INVALID_COMPANY')


class TestDataIntegrity:
    """Test data consistency and integrity."""
    
    def test_ticker_edinet_consistency(self):
        """Test consistency between ticker and EDINET mappings."""
        companies = edinet_tools.get_supported_companies()
        
        for company in companies:
            ticker = company['ticker']
            edinet_code = company['edinet_code']
            
            # Skip companies without tickers
            if not ticker or ticker.strip() == '':
                continue
            
            # Verify ticker lookup works
            lookup_result = edinet_tools.ticker_to_edinet(ticker)
            assert lookup_result == edinet_code, f"Ticker {ticker} should map to {edinet_code}"
            
            # Verify resolve works
            resolve_result = edinet_tools.resolve_company(ticker)
            assert resolve_result == edinet_code, f"Resolve {ticker} should return {edinet_code}"
    
    def test_search_result_completeness(self):
        """Test that search results have complete information."""
        results = edinet_tools.search_companies('Corporation', limit=5)
        
        for result in results:
            # Check required fields
            assert 'edinet_code' in result
            assert 'ticker' in result
            assert 'name_en' in result
            assert 'name_ja' in result
            assert 'industry' in result
            assert 'match_score' in result
            
            # Check data types
            assert isinstance(result['match_score'], (int, float))
            assert result['match_score'] > 0
    
    def test_document_types_validity(self):
        """Test document types mapping validity."""
        doc_types = edinet_tools.DOCUMENT_TYPES
        
        # Check that all keys are strings
        for key in doc_types.keys():
            assert isinstance(key, str)
            assert key.isdigit() or key == 'unknown'  # Should be numeric codes
        
        # Check that all values are strings
        for value in doc_types.values():
            assert isinstance(value, str)
            assert len(value) > 0


class TestPackageMetadata:
    """Test package metadata and configuration."""
    
    def test_package_info(self):
        """Test package information is available."""
        assert hasattr(edinet_tools, '__author__')
        assert hasattr(edinet_tools, '__description__')
        assert edinet_tools.__author__ == "Matt Helmer"
        assert "Japanese corporate financial data" in edinet_tools.__description__
    
    def test_all_exports(self):
        """Test that __all__ contains all expected exports."""
        expected_exports = [
            'EdinetClient',
            'DOCUMENT_TYPES',
            'search_companies',
            'get_supported_companies', 
            'ticker_to_edinet',
            'resolve_company',
            'get_company_info',
            'get_client',
            '__version__'
        ]
        
        for export in expected_exports:
            assert export in edinet_tools.__all__
            assert hasattr(edinet_tools, export)


if __name__ == "__main__":
    # Run tests if pytest is available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("pytest not available. Install with: pip install pytest")
        print("Running basic integration validation...")
        
        # Basic validation
        assert edinet_tools.__version__ == "0.1.0"
        assert edinet_tools.ticker_to_edinet('7203') == 'E02144'
        assert len(edinet_tools.search_companies('Toyota')) > 0
        assert len(edinet_tools.get_supported_companies()) > 0
        
        client = edinet_tools.EdinetClient(api_key='dummy')
        assert len(client.search_companies('Sony')) > 0
        
        print("✅ Basic integration validation passed!")