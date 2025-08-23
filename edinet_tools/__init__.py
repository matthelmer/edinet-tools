"""
EDINET Tools - Python package for accessing Japanese corporate financial data.

The authoritative Python library for Japanese financial disclosure data.
"""

__version__ = "0.1.0"
__author__ = "Matt Helmer" 
__description__ = "Python package for accessing Japanese corporate financial data from EDINET"

# Core API imports
from .client import EdinetClient
from .config import SUPPORTED_DOC_TYPES as DOCUMENT_TYPES
from .data import (
    search_companies, 
    get_supported_companies, 
    ticker_to_edinet, 
    resolve_company,
    get_company_info
)

# Make key classes and functions available at package level
__all__ = [
    "EdinetClient",
    "DOCUMENT_TYPES",
    "search_companies",
    "get_supported_companies", 
    "ticker_to_edinet",
    "resolve_company",
    "get_company_info",
    "get_client",
    "__version__"
]

# Convenience functions
def get_client(api_key=None):
    """Get an EDINET client instance."""
    return EdinetClient(api_key=api_key)