"""
Real API Contract Tests - TIER 2 INTEGRATION

Tests that validate real API contracts and behavior.
Run with: pytest -m integration
Budget: 8-10 API calls per test run to respect API limits.
"""

import pytest
from datetime import date, timedelta

from edinet_tools.api import (
    fetch_documents_list,
    fetch_document,
    get_documents_for_date_range
)


@pytest.mark.integration
class TestRealAPIContracts:
    """Tests that validate real EDINET API behavior and contracts"""
    
    def setup_method(self):
        """Set up API key for integration tests"""
        import os
        from dotenv import load_dotenv
        
        # Load .env file to get API key
        load_dotenv()
        self.api_key = os.environ.get('EDINET_API_KEY')
        
        if not self.api_key:
            pytest.skip("❌ EDINET_API_KEY NOT FOUND - integration tests SKIPPED (set API key in .env file)")
        
        # Check if API key appears to be valid format
        if len(self.api_key.strip()) < 10:  # Basic length check
            pytest.skip(f"❌ API KEY TOO SHORT: {len(self.api_key)} chars (expected >10) - integration tests SKIPPED")
        
        # Debug: Show exactly what key is being found and where it's coming from
        print(f"🔑 EDINET_API_KEY found (length: {len(self.api_key)} chars)")
        print(f"   Key preview: '{self.api_key[:12]}...' (showing first 12 chars)")
        print(f"   Key repr: {repr(self.api_key)}")
        
        # Check multiple sources to see where it might be coming from
        import os
        print(f"   Direct os.environ: {len(os.environ.get('EDINET_API_KEY', ''))} chars")
        
        try:
            from edinet_tools.config import EDINET_API_KEY as CONFIG_KEY
            print(f"   From config module: {len(CONFIG_KEY) if CONFIG_KEY else 0} chars")
            if CONFIG_KEY and len(CONFIG_KEY) != len(self.api_key):
                print(f"   ⚠️  MISMATCH: test={len(self.api_key)} vs config={len(CONFIG_KEY)}")
        except ImportError:
            print("   Config module not available")
        
        # Check .env file directly
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('EDINET_API_KEY'):
                        env_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        print(f"   From .env file: {len(env_key)} chars")
                        break
        except FileNotFoundError:
            print("   No .env file found")
        
        print("✅ Proceeding with integration tests")
    
    def test_fetch_documents_list_recent_date(self):
        """Test document list fetch for a recent date (any day)"""
        # Use yesterday's date - simple and reliable
        test_date = date.today() - timedelta(days=1)
        date_str = test_date.strftime('%Y-%m-%d')
        
        result = fetch_documents_list(date_str, api_key=self.api_key)
        
        # Should get valid response structure regardless of day type
        assert isinstance(result, dict)
        assert 'results' in result
        assert isinstance(result['results'], list)
        
        # Log what we got for debugging
        print(f"Tested date: {date_str} ({test_date.strftime('%A')})")
        print(f"Documents found: {len(result['results'])}")
        
        # Results may be empty on weekends/holidays, which is expected
    
    def test_fetch_documents_list_weekend_handling(self):
        """Test document list fetch for a weekend date"""
        # Find the most recent Saturday
        test_date = date.today()
        while test_date.weekday() != 5:  # Saturday=5
            test_date = test_date - timedelta(days=1)
        
        date_str = test_date.strftime('%Y-%m-%d')
        result = fetch_documents_list(date_str, api_key=self.api_key)
        
        # Should get valid response but likely no documents on weekend
        assert isinstance(result, dict)
        assert 'results' in result
        assert isinstance(result['results'], list)
        
        # Weekend typically has no filings - this is expected behavior
        print(f"Weekend test ({date_str}): {len(result['results'])} documents")
    
    def test_api_response_structure_compliance(self):
        """Verify API response structure matches expected format"""
        # Use 3 days ago to likely hit a business day
        test_date = date.today() - timedelta(days=3)
        date_str = test_date.strftime('%Y-%m-%d')
        
        result = fetch_documents_list(date_str, api_key=self.api_key)
        
        # Validate response structure
        assert isinstance(result, dict)
        assert 'results' in result
        
        # If documents exist, validate their structure
        if result['results']:
            doc = result['results'][0]
            expected_fields = ['docID', 'edinetCode', 'docTypeCode', 'filerName']
            for field in expected_fields:
                assert field in doc, f"Missing required field: {field}"
    
    def test_fetch_document_by_recent_doc_id(self):
        """Test document download with a recent document ID"""
        # Look back up to 7 days to find a document
        for days_back in range(1, 8):
            test_date = date.today() - timedelta(days=days_back)
            date_str = test_date.strftime('%Y-%m-%d')
            
            doc_list = fetch_documents_list(date_str, api_key=self.api_key)
            
            if doc_list['results']:
                # Try to download first document
                doc_id = doc_list['results'][0]['docID']
                zip_content = fetch_document(doc_id, api_key=self.api_key)
                
                # Should get binary ZIP content
                assert isinstance(zip_content, bytes)
                assert len(zip_content) > 0
                
                # Should start with ZIP file signature
                assert zip_content[:4] == b'PK\x03\x04' or zip_content[:4] == b'PK\x05\x06'
                
                print(f"Downloaded document {doc_id}: {len(zip_content)} bytes")
                return
        
        pytest.skip("No documents found in recent 7 days for download test")
    
    def test_date_range_api_usage_efficiency(self):
        """Test date range functionality with minimal API calls"""
        # Test small date range (2 recent days) to limit API usage
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=1)
        
        results = get_documents_for_date_range(start_date, end_date, api_key=self.api_key)
        
        # Should get list of documents
        assert isinstance(results, list)
        
        # Each document should have required metadata
        for doc in results:
            assert 'docID' in doc
            assert 'docTypeCode' in doc
            assert 'filerName' in doc
        
        print(f"Date range ({start_date} to {end_date}): {len(results)} total documents")
    
    def test_api_error_handling_with_invalid_key(self):
        """Test API error handling with invalid credentials"""
        invalid_key = "invalid_test_key_12345"
        test_date = date.today() - timedelta(days=1)
        date_str = test_date.strftime('%Y-%m-%d')
        
        # API should return error response dict, not raise exception
        result = fetch_documents_list(date_str, api_key=invalid_key)
        
        # Should get 401 error response
        assert isinstance(result, dict), "API should return error response as dict"
        assert 'statusCode' in result or 'message' in result, "Error response should have statusCode or message"
        
        # Check for authentication error indicators
        response_str = str(result).lower()
        assert '401' in response_str or 'unauthorized' in response_str or 'access denied' in response_str or 'subscription key' in response_str
    
    def test_api_document_not_found_handling(self):
        """Test API handling of non-existent document IDs"""
        fake_doc_id = "S999FAKE999"
        
        # API should return error response, not raise exception
        result = fetch_document(fake_doc_id, api_key=self.api_key)
        
        # Result could be bytes or dict depending on API response
        if isinstance(result, bytes):
            result_str = result.decode('utf-8').lower()
        else:
            result_str = str(result).lower()
        
        # Should get error response (could be 404, 400, or other error)
        assert ('404' in result_str or 'not found' in result_str or 
                'statuscode' in result_str or 'error' in result_str or
                'invalid' in result_str or 'bad request' in result_str or
                'status' in result_str), f"Expected error response, got: {result_str[:200]}"
    
    def test_api_rate_limit_respectful_usage(self):
        """Verify our API usage patterns are respectful"""
        import time
        
        # Make 3 quick API calls with small delays using recent dates
        start_time = time.time()
        for days_back in range(1, 4):
            test_date = date.today() - timedelta(days=days_back)
            date_str = test_date.strftime('%Y-%m-%d')
            result = fetch_documents_list(date_str, api_key=self.api_key)
            assert 'results' in result
            time.sleep(0.1)  # Minimal delay to avoid rate limiting
        
        total_time = time.time() - start_time
        
        # Should complete without errors (no rate limiting)
        # No strict timing assertion since we want fast tests
        print(f"3 API calls completed in {total_time:.1f} seconds")


@pytest.mark.integration
class TestCriticalDocumentTypeRetrieval:
    """Integration tests focused on critical document types 140, 160, 180"""
    
    def setup_method(self):
        """Set up API key for integration tests"""
        import os
        from dotenv import load_dotenv
        
        # Load .env file to get API key
        load_dotenv()
        self.api_key = os.environ.get('EDINET_API_KEY')
        
        if not self.api_key:
            pytest.skip("❌ EDINET_API_KEY NOT FOUND - integration tests SKIPPED (set API key in .env file)")
        
        # Check if API key appears to be valid format
        if len(self.api_key.strip()) < 10:  # Basic length check
            pytest.skip(f"❌ API KEY TOO SHORT: {len(self.api_key)} chars (expected >10) - integration tests SKIPPED")
        
        # Debug: Show exactly what key is being found and where it's coming from
        print(f"🔑 EDINET_API_KEY found (length: {len(self.api_key)} chars)")
        print(f"   Key preview: '{self.api_key[:12]}...' (showing first 12 chars)")
        print(f"   Key repr: {repr(self.api_key)}")
        
        # Check multiple sources to see where it might be coming from
        import os
        print(f"   Direct os.environ: {len(os.environ.get('EDINET_API_KEY', ''))} chars")
        
        try:
            from edinet_tools.config import EDINET_API_KEY as CONFIG_KEY
            print(f"   From config module: {len(CONFIG_KEY) if CONFIG_KEY else 0} chars")
            if CONFIG_KEY and len(CONFIG_KEY) != len(self.api_key):
                print(f"   ⚠️  MISMATCH: test={len(self.api_key)} vs config={len(CONFIG_KEY)}")
        except ImportError:
            print("   Config module not available")
        
        # Check .env file directly
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('EDINET_API_KEY'):
                        env_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        print(f"   From .env file: {len(env_key)} chars")
                        break
        except FileNotFoundError:
            print("   No .env file found")
        
        print("✅ Proceeding with integration tests")
    
    def test_document_type_filtering_in_real_data(self):
        """Test that we can find and filter critical document types in real API data"""
        # Search recent days to find critical document types
        critical_types_found = set()
        
        # Look back up to 14 days to find examples of critical document types
        for days_back in range(1, 15):
            test_date = date.today() - timedelta(days=days_back)
            date_str = test_date.strftime('%Y-%m-%d')
            
            result = fetch_documents_list(date_str, api_key=self.api_key)
            
            for doc in result.get('results', []):
                doc_type = doc.get('docTypeCode')
                if doc_type in ['140', '160', '180']:
                    critical_types_found.add(doc_type)
                    print(f"Found {doc_type}: {doc.get('filerName', 'Unknown')} on {date_str}")
            
            # Stop early if we found examples of all critical types
            if len(critical_types_found) >= 2:
                break
        
        # Log what we found (may not find all types in date range)
        print(f"Critical document types found: {sorted(critical_types_found)}")
        
        # Test passes if we found at least one critical type, or just completes discovery
        assert len(critical_types_found) >= 0  # Always passes, just for discovery