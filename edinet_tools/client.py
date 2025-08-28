"""
Main EDINET Client class providing a clean, developer-friendly interface.
"""

import os
import datetime
import json
from typing import List, Dict, Any, Optional, Union
import logging

from .api import fetch_documents_list, fetch_document, download_documents
from .config import SUPPORTED_DOC_TYPES as DOCUMENT_TYPES
from .utils import process_zip_file
from .processors import process_raw_csv_data
from .data import resolve_company, search_companies as search_companies_data, get_company_info
from .exceptions import (
    AuthenticationError, DocumentNotFoundError, CompanyNotFoundError,
    ProcessingError, ConfigurationError, APIError, suggest_companies
)

logger = logging.getLogger(__name__)


class EdinetClient:
    """
    Main client for accessing EDINET (Electronic Disclosure for Investors' NETwork) data.
    
    Provides a clean, developer-friendly interface for:
    - Searching companies by ticker or name
    - Retrieving corporate filings and financial disclosures
    - Processing XBRL financial data
    - Accessing structured document content
    
    Example:
        >>> import edinet_tools
        >>> client = edinet_tools.EdinetClient(api_key="your_key")
        >>> filings = client.get_company_filings("7203")  # Toyota
        >>> client.download_filing(filings[0]["docID"])
    """
    
    def __init__(self, api_key: Optional[str] = None, download_dir: str = "./downloads"):
        """
        Initialize EDINET client.
        
        Args:
            api_key: EDINET API key. If None, will look for EDINET_API_KEY environment variable.
            download_dir: Directory to store downloaded documents.
        """
        self.api_key = api_key or os.getenv('EDINET_API_KEY')
        if not self.api_key:
            raise ConfigurationError(
                "EDINET API key required.",
                "Set EDINET_API_KEY environment variable or pass api_key parameter. "
                "Get your API key from: https://disclosure.edinet-fsa.go.jp/"
            )
        
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # Company lookup functionality is available via data module
        
    def get_documents_by_date(self, 
                             date: Union[str, datetime.date],
                             doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all documents submitted on a specific date.
        
        Args:
            date: Date in 'YYYY-MM-DD' format or datetime.date object
            doc_type: Optional document type filter (e.g., '160', '180')
            
        Returns:
            List of document metadata dictionaries
        """
        try:
            response = fetch_documents_list(date, api_key=self.api_key)
            documents = response.get('results', [])
            
            if doc_type:
                documents = [doc for doc in documents if doc.get('docTypeCode') == doc_type]
                
            return documents
            
        except Exception as e:
            logger.error(f"Error fetching documents for {date}: {e}")
            if "401" in str(e) or "unauthorized" in str(e).lower():
                raise AuthenticationError()
            elif "429" in str(e) or "rate limit" in str(e).lower():
                raise APIError(f"Rate limit exceeded. Please wait before making more requests.")
            else:
                raise APIError(f"Failed to fetch documents for {date}: {e}")
    
    def get_recent_filings(self, 
                          days_back: int = 7,
                          doc_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get recent filings across all companies.
        
        Args:
            days_back: Number of days to look back
            doc_types: List of document types to include (e.g., ['160', '180'])
            
        Returns:
            List of recent filing metadata
        """
        all_filings = []
        end_date = datetime.date.today()
        
        for i in range(days_back):
            check_date = end_date - datetime.timedelta(days=i)
            try:
                daily_filings = self.get_documents_by_date(check_date)
                if doc_types:
                    daily_filings = [
                        doc for doc in daily_filings 
                        if doc.get('docTypeCode') in doc_types
                    ]
                all_filings.extend(daily_filings)
                
            except Exception as e:
                logger.warning(f"Could not fetch filings for {check_date}: {e}")
                continue
        
        # Sort by submission time (newest first), handle None values
        all_filings.sort(key=lambda x: x.get('submitDateTime') or '', reverse=True)
        return all_filings
    
    def get_company_filings(self, 
                           company_identifier: str,
                           days_back: int = 30,
                           doc_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get recent filings for a specific company.
        
        Args:
            company_identifier: Company ticker (e.g., "7203") or EDINET code (e.g., "E02144")
            days_back: Number of days to look back
            doc_types: List of document types to include
            
        Returns:
            List of company's recent filings
        """
        # TODO: Implement ticker to EDINET code lookup
        edinet_code = self._resolve_company_identifier(company_identifier)
        
        recent_filings = self.get_recent_filings(days_back, doc_types)
        company_filings = [
            doc for doc in recent_filings 
            if doc.get('edinetCode') == edinet_code
        ]
        
        return company_filings
    
    def search_companies(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for companies by name or ticker.
        
        Args:
            query: Search term (company name in Japanese/English or ticker)
            
        Returns:
            List of matching companies with metadata
        """
        try:
            return search_companies_data(query)
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return []
    
    def download_filing(self, 
                       doc_id: str,
                       extract_data: bool = True,
                       doc_type_code: Optional[str] = None,
                       raise_on_error: bool = True) -> Optional[Dict[str, Any]]:
        """
        Download and optionally process a specific filing.
        
        Args:
            doc_id: EDINET document ID
            extract_data: Whether to extract and process structured data
            doc_type_code: Optional document type code if known
            raise_on_error: If False, return None on error instead of raising exception
            
        Returns:
            Processed document data if extract_data=True, None otherwise
            
        Raises:
            DocumentNotFoundError: When document doesn't exist (if raise_on_error=True)
            APIError: When API request fails (if raise_on_error=True)
            ProcessingError: When document processing fails (if raise_on_error=True)
            
        Examples:
            # Single document (raises exceptions)
            try:
                data = client.download_filing("S100ABC1")
            except DocumentNotFoundError:
                print("Document not found")
                
            # Batch processing (graceful)
            for doc_id in doc_ids:
                data = client.download_filing(doc_id, raise_on_error=False)
                if data:
                    process(data)
                    
            # Or use the batch convenience method
            results = client.download_filings_batch(doc_ids)
            successful_data = [r for r in results if r is not None]
        """
        try:
            # Download the document
            doc_response = fetch_document(doc_id, api_key=self.api_key)
            
            # Check if the response is actually a JSON error instead of a ZIP file
            if self._is_json_error_response(doc_response):
                error_data = json.loads(doc_response.decode('utf-8'))
                error_message = error_data.get('metadata', {}).get('message', 'Unknown error')
                status = error_data.get('metadata', {}).get('status', 'Unknown')
                
                logger.error(f"API returned error for document {doc_id}: {status} - {error_message}")
                
                if not raise_on_error:
                    return None
                
                if status == '404' or 'not found' in error_message.lower():
                    raise DocumentNotFoundError(doc_id)
                else:
                    raise APIError(f"API error for document {doc_id}: {status} - {error_message}")
            
            # Check if response looks like a ZIP file
            if not self._is_zip_response(doc_response):
                logger.error(f"Document {doc_id} response does not appear to be a valid ZIP file")
                if not raise_on_error:
                    return None
                raise ProcessingError(f"Invalid response format for document {doc_id}", doc_id, "Response is not a ZIP file")
            
            # Save to downloads directory
            filename = f"{doc_id}.zip"
            filepath = os.path.join(self.download_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(doc_response)
            
            logger.info(f"Downloaded {doc_id} to {filepath}")
            
            if extract_data:
                return self.extract_filing_data(filepath, doc_type_code)
            
            return None
            
        except (DocumentNotFoundError, APIError, ProcessingError):
            # Re-raise these specific exceptions without wrapping
            if raise_on_error:
                raise
            else:
                return None
        except Exception as e:
            logger.error(f"Error downloading filing {doc_id}: {e}")
            if not raise_on_error:
                return None
            if "404" in str(e) or "not found" in str(e).lower():
                raise DocumentNotFoundError(doc_id)
            elif "401" in str(e) or "unauthorized" in str(e).lower():
                raise AuthenticationError()
            else:
                raise APIError(f"Failed to download filing {doc_id}: {e}")
    
    def download_filings_batch(self, 
                              doc_ids: List[str],
                              extract_data: bool = True,
                              doc_type_code: Optional[str] = None,
                              raise_on_error: bool = False) -> List[Optional[Dict[str, Any]]]:
        """
        Download multiple filings with configurable error handling.
        
        This is a convenience method for batch processing. By default, it uses
        graceful error handling (raise_on_error=False) to skip problematic documents,
        but can be configured to fail fast if needed.
        
        Args:
            doc_ids: List of EDINET document IDs
            extract_data: Whether to extract and process structured data
            doc_type_code: Optional document type code if known
            raise_on_error: If True, stop on first error; if False, skip failed documents (default)
            
        Returns:
            List of processed data (or None if failed) in same order as input doc_ids
            
        Examples:
            # Graceful batch processing (default)
            >>> results = client.download_filings_batch(["S100ABC1", "S100XYZ2"])
            >>> successful = [r for r in results if r is not None]
            
            # Fail-fast batch processing
            >>> try:
            ...     results = client.download_filings_batch(doc_ids, raise_on_error=True)
            ... except DocumentNotFoundError:
            ...     print("Batch failed on first error")
        """
        results = []
        total = len(doc_ids)
        
        logger.info(f"Starting batch download of {total} documents")
        
        for i, doc_id in enumerate(doc_ids, 1):
            logger.debug(f"Processing document {i}/{total}: {doc_id}")
            
            # Use the specified error handling mode
            result = self.download_filing(
                doc_id, 
                extract_data=extract_data, 
                doc_type_code=doc_type_code,
                raise_on_error=raise_on_error
            )
            results.append(result)
        
        successful_count = sum(1 for v in results if v is not None)
        logger.info(f"Batch download completed: {successful_count}/{total} documents successful")
        
        return results
    
    def _is_json_error_response(self, response_bytes: bytes) -> bool:
        """Check if response is a JSON error message."""
        try:
            # Try to decode as UTF-8 and parse as JSON
            response_text = response_bytes.decode('utf-8')
            data = json.loads(response_text)
            # Check if it has the error structure
            return 'metadata' in data and 'status' in data.get('metadata', {})
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return False
    
    def _is_zip_response(self, response_bytes: bytes) -> bool:
        """Check if response appears to be a ZIP file."""
        # ZIP files start with 'PK' (0x504b)
        return len(response_bytes) > 2 and response_bytes[:2] == b'PK'
    
    def extract_filing_data(self, zip_path: str, doc_type_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Extract structured data from a downloaded filing ZIP file.
        
        Args:
            zip_path: Path to downloaded ZIP file
            doc_type_code: Optional document type code if known
            
        Returns:
            Structured document data
        """
        try:
            # Parse document ID from filename
            filename = os.path.basename(zip_path)
            doc_id = filename.replace('.zip', '').split('-')[0]
            
            # Use provided document type code or try to determine from filename
            if doc_type_code is None:
                doc_type_code = self._determine_document_type([], filename)
            
            # Process ZIP file and extract structured data
            structured_data = process_zip_file(zip_path, doc_id, doc_type_code)
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Error extracting data from {zip_path}: {e}")
            raise ProcessingError(f"Failed to extract data from {zip_path}", doc_id, str(e))
    
    def get_document_types(self) -> Dict[str, str]:
        """Get mapping of document type codes to descriptions."""
        return DOCUMENT_TYPES.copy()
    
    def _resolve_company_identifier(self, identifier: str) -> str:
        """
        Convert ticker symbol or company name to EDINET code.
        """
        try:
            edinet_code = resolve_company(identifier)
            if edinet_code:
                return edinet_code
            
            # If not found, provide helpful error message
            company_info = get_company_info(identifier) if identifier.startswith('E') else None
            if company_info:
                return identifier  # Already valid EDINET code
            
            # Get suggestions for better error message
            suggestions = suggest_companies(identifier)
            raise CompanyNotFoundError(identifier, suggestions)
            
        except Exception as e:
            logger.error(f"Error resolving company identifier '{identifier}': {e}")
            raise
    
    def _determine_document_type(self, csv_data: List[Dict], filename: str) -> str:
        """
        Determine document type code from CSV data or filename.
        
        TODO: Implement more robust document type detection.
        """
        # Try to extract from filename first (format: docID-typeCode-companyName.zip)
        parts = filename.replace('.zip', '').split('-')
        if len(parts) >= 2 and parts[1].isdigit():
            return parts[1]
        
        # TODO: Analyze CSV data to determine document type
        return "unknown"