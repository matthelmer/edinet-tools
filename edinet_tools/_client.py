"""
Module-level client singleton for EDINET API access.

Provides lazy initialization of EdinetClient from environment variables
or explicit configuration.
"""
import os
import warnings
from typing import Optional

from .client import EdinetClient

# Module-level state
_client: Optional[EdinetClient] = None
_configured_api_key: Optional[str] = None


def _get_client() -> EdinetClient:
    """
    Get the module-level EdinetClient instance.

    Lazily initializes from EDINET_API_KEY env var or configure() call.

    Returns:
        EdinetClient instance
    """
    global _client
    if _client is None:
        api_key = _configured_api_key or os.environ.get('EDINET_API_KEY')
        # Suppress deprecation warning for internal usage
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            _client = EdinetClient(api_key=api_key)
    return _client


def _reset_client() -> None:
    """Reset the client singleton (for testing)."""
    global _client
    _client = None


def configure(api_key: Optional[str] = None) -> None:
    """
    Configure the module-level client.

    Args:
        api_key: EDINET API key (if None, uses EDINET_API_KEY env var)
    """
    global _configured_api_key, _client
    _configured_api_key = api_key
    _client = None  # Reset so next _get_client() uses new config


def documents(date: str, doc_type: Optional[str] = None) -> list:
    """
    Get all documents filed on a specific date.

    Args:
        date: Date string (YYYY-MM-DD)
        doc_type: Optional filter by document type code

    Returns:
        List of Document objects
    """
    from .document import Document

    client = _get_client()
    filings = client.get_documents_by_date(date)

    if doc_type:
        filings = [f for f in filings if f.get('docTypeCode') == doc_type]

    return [Document(f, client=client) for f in filings]
