"""
Tests for edinet_tools.data module (company lookup functionality).
"""

import pytest
from edinet_tools.data import (
    ticker_to_edinet, resolve_company, search_companies,
    get_company_info, get_supported_companies, CompanyLookup
)


class TestTickerLookup:
    """Test ticker symbol to EDINET code conversion."""
    
    def test_valid_tickers(self):
        """Test conversion of valid ticker symbols."""
        assert ticker_to_edinet('7203') == 'E02144'  # Toyota Motor Corporation
        assert ticker_to_edinet('6758') == 'E01777'  # Sony Group Corporation
        assert ticker_to_edinet('9984') == 'E02778'  # SoftBank Group Corp
    
    def test_ticker_with_suffix(self):
        """Test tickers with .T or .JP suffixes."""
        assert ticker_to_edinet('7203.T') == 'E02144'
        assert ticker_to_edinet('6758.JP') == 'E01777'
    
    def test_invalid_ticker(self):
        """Test invalid ticker symbols."""
        assert ticker_to_edinet('0000') is None
        assert ticker_to_edinet('INVALID') is None
        assert ticker_to_edinet('') is None


class TestCompanyResolution:
    """Test company identifier resolution."""
    
    def test_edinet_code_passthrough(self):
        """Test that valid EDINET codes pass through unchanged."""
        assert resolve_company('E02144') == 'E02144'
        assert resolve_company('E01777') == 'E01777'
    
    def test_ticker_resolution(self):
        """Test ticker to EDINET code resolution."""
        assert resolve_company('7203') == 'E02144'
        assert resolve_company('6758') == 'E01777'
    
    def test_invalid_identifier(self):
        """Test invalid identifiers return None."""
        assert resolve_company('INVALID') is None
        assert resolve_company('0000') is None
        assert resolve_company('') is None


class TestCompanySearch:
    """Test company search functionality."""
    
    def test_exact_name_search(self):
        """Test searching by exact company name."""
        results = search_companies('TOYOTA MOTOR CORPORATION')
        assert len(results) > 0
        assert results[0]['name_en'] == 'TOYOTA MOTOR CORPORATION'
    
    def test_partial_name_search(self):
        """Test searching by partial company name."""
        results = search_companies('Toyota')
        assert len(results) > 0
        toyota_found = any('TOYOTA' in r['name_en'] for r in results)
        assert toyota_found
    
    def test_ticker_search(self):
        """Test searching by ticker symbol."""
        results = search_companies('72030')  # EDINET uses 5-digit format
        assert len(results) > 0
        assert results[0]['ticker'] == '72030'
    
    def test_industry_search(self):
        """Test searching by industry."""
        results = search_companies('Banks')
        assert len(results) > 0
        banking_found = any('Banks' in r.get('industry', '') for r in results)
        assert banking_found
    
    def test_no_results(self):
        """Test search with no results."""
        results = search_companies('NonexistentCompany12345')
        assert len(results) == 0
    
    def test_search_limit(self):
        """Test search result limiting."""
        results = search_companies('Corporation', limit=2)
        assert len(results) <= 2


class TestCompanyInfo:
    """Test company information retrieval."""
    
    def test_valid_edinet_code(self):
        """Test getting info for valid EDINET codes."""
        info = get_company_info('E02144')  # Toyota
        assert info is not None
        assert info['ticker'] == '72030'  # EDINET uses 5-digit format
        assert 'TOYOTA' in info['name_en']
    
    def test_invalid_edinet_code(self):
        """Test getting info for invalid EDINET codes."""
        info = get_company_info('E00000')
        assert info is None
        
        info = get_company_info('INVALID')
        assert info is None


class TestSupportedCompanies:
    """Test supported companies list."""
    
    def test_get_supported_companies(self):
        """Test getting list of supported companies."""
        companies = get_supported_companies()
        assert len(companies) > 0
        
        # Check structure
        for company in companies:
            assert 'edinet_code' in company
            assert 'ticker' in company
            assert 'name_en' in company
            assert 'name_ja' in company
    
    def test_companies_sorted(self):
        """Test that companies are sorted by ticker."""
        companies = get_supported_companies()
        tickers = [c.get('ticker', '') for c in companies if c.get('ticker')]
        assert tickers == sorted(tickers)


class TestCompanyLookupClass:
    """Test CompanyLookup class directly."""
    
    def setup_method(self):
        """Set up test instance."""
        self.lookup = CompanyLookup()
    
    def test_initialization(self):
        """Test proper initialization."""
        assert len(self.lookup.ticker_to_edinet_map) > 0
        assert len(self.lookup.companies) > 0
        assert len(self.lookup.edinet_to_ticker_map) > 0
    
    def test_reverse_lookup(self):
        """Test EDINET to ticker reverse lookup."""
        ticker = self.lookup.edinet_to_ticker_code('E02144')
        assert ticker == '72030'  # EDINET uses 5-digit format
    
    def test_search_indexes(self):
        """Test that search indexes are built."""
        assert len(self.lookup.name_to_edinet) > 0
        
        # Test that some variations exist
        toyota_variations = [
            k for k in self.lookup.name_to_edinet.keys() 
            if 'toyota' in k.lower()
        ]
        assert len(toyota_variations) > 0


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_strings(self):
        """Test handling of empty strings."""
        assert ticker_to_edinet('') is None
        assert resolve_company('') is None
        
        results = search_companies('')
        assert len(results) == 0
    
    def test_whitespace_handling(self):
        """Test handling of whitespace."""
        assert ticker_to_edinet('  7203  ') == 'E02144'
        assert resolve_company('  E02144  ') == 'E02144'
    
    def test_case_insensitive_search(self):
        """Test case insensitive search."""
        results_lower = search_companies('toyota')
        results_upper = search_companies('TOYOTA')
        results_mixed = search_companies('Toyota')
        
        # Should find results regardless of case
        assert len(results_lower) > 0
        assert len(results_upper) > 0
        assert len(results_mixed) > 0


if __name__ == "__main__":
    # Run tests if pytest is available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("pytest not available. Install with: pip install pytest")
        print("Running basic test validation...")
        
        # Basic validation
        assert ticker_to_edinet('7203') == 'E02144'
        assert resolve_company('7203') == 'E02144'
        assert len(search_companies('Toyota')) > 0
        assert get_company_info('E02144') is not None
        assert len(get_supported_companies()) > 0
        
        print("✅ Basic validation passed!")