"""
DocType registry for EDINET document types.

Provides metadata about document types including English/Japanese names
and descriptions.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DocType:
    """
    EDINET document type metadata.

    Attributes:
        code: Document type code (e.g., "350")
        name_en: English name
        name_jp: Japanese name
        description: Brief description of the document type
    """
    code: str
    name_en: str
    name_jp: str
    description: str = ""

    def __repr__(self) -> str:
        return f"DocType(code='{self.code}', name='{self.name_en}')"


# Registry of known document types
_DOC_TYPES: dict[str, DocType] = {
    # Securities Reports (有価証券報告書)
    "120": DocType(
        code="120",
        name_en="Securities Report",
        name_jp="有価証券報告書",
        description="Annual securities report filed by listed companies",
    ),
    "130": DocType(
        code="130",
        name_en="Securities Report Amendment",
        name_jp="有価証券報告書の訂正報告書",
        description="Amendment to annual securities report",
    ),

    # Quarterly Reports (四半期報告書)
    "140": DocType(
        code="140",
        name_en="Quarterly Report",
        name_jp="四半期報告書",
        description="Quarterly financial report (Q1, Q2, Q3)",
    ),
    "150": DocType(
        code="150",
        name_en="Quarterly Report Amendment",
        name_jp="四半期報告書の訂正報告書",
        description="Amendment to quarterly report",
    ),

    # Semi-Annual Reports (半期報告書)
    "160": DocType(
        code="160",
        name_en="Semi-Annual Report",
        name_jp="半期報告書",
        description="Semi-annual report (primarily for investment funds)",
    ),
    "170": DocType(
        code="170",
        name_en="Semi-Annual Report Amendment",
        name_jp="半期報告書の訂正報告書",
        description="Amendment to semi-annual report",
    ),

    # Extraordinary Reports (臨時報告書)
    "180": DocType(
        code="180",
        name_en="Extraordinary Report",
        name_jp="臨時報告書",
        description="Report on material events (M&A, management changes, etc.)",
    ),
    "190": DocType(
        code="190",
        name_en="Extraordinary Report Amendment",
        name_jp="臨時報告書の訂正報告書",
        description="Amendment to extraordinary report",
    ),

    # Large Shareholding Reports (大量保有報告書)
    "350": DocType(
        code="350",
        name_en="Large Shareholding Report",
        name_jp="大量保有報告書",
        description="Report when ownership exceeds 5% of a listed company",
    ),
    "360": DocType(
        code="360",
        name_en="Large Shareholding Report Amendment",
        name_jp="大量保有報告書の訂正報告書",
        description="Amendment to large shareholding report",
    ),
    "370": DocType(
        code="370",
        name_en="Large Shareholding Change Report",
        name_jp="変更報告書",
        description="Report on changes to large shareholding position",
    ),
    "380": DocType(
        code="380",
        name_en="Large Shareholding Change Report Amendment",
        name_jp="変更報告書の訂正報告書",
        description="Amendment to change report",
    ),

    # Tender Offer Reports (公開買付届出書)
    "030": DocType(
        code="030",
        name_en="Tender Offer Registration",
        name_jp="公開買付届出書",
        description="Registration for tender offer",
    ),
    "040": DocType(
        code="040",
        name_en="Tender Offer Registration Amendment",
        name_jp="公開買付届出書の訂正届出書",
        description="Amendment to tender offer registration",
    ),

    # Shelf Registration (発行登録書)
    "070": DocType(
        code="070",
        name_en="Shelf Registration",
        name_jp="発行登録書",
        description="Shelf registration for securities issuance",
    ),

    # Securities Registration (有価証券届出書)
    "010": DocType(
        code="010",
        name_en="Securities Registration",
        name_jp="有価証券届出書",
        description="Registration for new securities issuance",
    ),
    "020": DocType(
        code="020",
        name_en="Securities Registration Amendment",
        name_jp="有価証券届出書の訂正届出書",
        description="Amendment to securities registration",
    ),
}


def doc_type(code: str) -> DocType | None:
    """
    Look up a document type by code.

    Args:
        code: Document type code (e.g., "350")

    Returns:
        DocType object or None if not found
    """
    return _DOC_TYPES.get(code)


def list_doc_types() -> list[DocType]:
    """
    Get all registered document types.

    Returns:
        List of all DocType objects
    """
    return list(_DOC_TYPES.values())


# Shorter alias (v0.2)
def doc_types() -> list[DocType]:
    """
    Get all registered document types.

    Alias for list_doc_types().

    Returns:
        List of all DocType objects
    """
    return list_doc_types()
