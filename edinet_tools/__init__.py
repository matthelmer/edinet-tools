"""
EDINET Tools - Python package for accessing Japanese corporate financial data.

Python library for Japanese financial disclosure data.
"""

__version__ = "0.5.0"
__author__ = "Matt Helmer"
__description__ = "Python package for accessing Japanese corporate financial data from EDINET"

# Core API
from .client import EdinetClient  # Deprecated, but kept for migration
from ._client import configure, documents, fetch_and_parse
from .timezone import today_jst
from .config import SUPPORTED_DOC_TYPES as DOCUMENT_TYPES

# Entity classification
from .entity_classifier import EntityClassifier, EntityType

# Entity-first API
from .entity import (
    Entity,
    entity,
    entity_by_ticker,
    entity_by_edinet_code,
    entity_by_code,  # Shorter alias
    search_entities,
    search,
    Fund,
    fund,
    funds_by_issuer,
)
from .document import Document
from .doc_types import DocType, doc_type, list_doc_types, doc_types

# Parsers
from .parsers import (
    parse,
    supported_doc_types,
    ParsedReport,
    RawReport,
    LargeHoldingReport,
    SecuritiesReport,
    QuarterlyReport,
    SemiAnnualReport,
    ExtraordinaryReport,
    TreasuryStockReport,
    TenderOfferReport,
    InternalControlReport,
    ConfirmationReport,
    ParentCompanyReport,
    LargeHoldingChangeReport,
    GenericReport,  # Backwards compatibility alias
)

__all__ = [
    # Configuration
    "configure",
    "documents",
    "fetch_and_parse",
    "today_jst",
    "DOCUMENT_TYPES",
    "__version__",
    # Entity lookup
    "Entity",
    "entity",
    "entity_by_ticker",
    "entity_by_edinet_code",
    "entity_by_code",  # Shorter alias
    "search_entities",
    "search",
    "Fund",
    "fund",
    "funds_by_issuer",
    # Documents
    "Document",
    "DocType",
    "doc_type",
    "list_doc_types",
    "doc_types",
    # Parsers
    "parse",
    "supported_doc_types",
    "ParsedReport",
    "RawReport",
    "LargeHoldingReport",
    "SecuritiesReport",
    "QuarterlyReport",
    "SemiAnnualReport",
    "ExtraordinaryReport",
    "TreasuryStockReport",
    "TenderOfferReport",
    "InternalControlReport",
    "ConfirmationReport",
    "ParentCompanyReport",
    "LargeHoldingChangeReport",
    # Legacy (deprecated)
    "EdinetClient",
    "EntityClassifier",
    "EntityType",
    "GenericReport",  # Backwards compatibility alias
]
