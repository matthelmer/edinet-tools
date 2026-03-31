"""
Parser for Shelf Registration Statement filings (Doc Type 080/090).

Extracts shelf registration details from 発行登録書（株券、社債券等）filings.
These are filed when a company registers a shelf of securities it may issue
over a future period. Key data includes the planned issuance period, security
types to be shelf-registered, and identifying information.

Doc 080: Original shelf registration statement
Doc 090: Amendment to shelf registration statement
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .base import ParsedReport
from .extraction import (
    extract_csv_from_zip,
    extract_value,
    categorize_elements,
    parse_date,
)


# XBRL Element ID mappings for Doc 080/090
ELEMENT_MAP = {
    # === Cover Page (jpcrp_cor namespace) ===
    'company_name': 'jpcrp_cor:CompanyNameCoverPage',
    'company_name_en': 'jpcrp_cor:CompanyNameInEnglishCoverPage',
    'filing_date': 'jpcrp_cor:FilingDateCoverPage',
    'document_title': 'jpcrp_cor:DocumentTitleCoverPage',
    'shelf_registration_number': 'jpcrp_cor:ShelfRegistrationNumberCoverPage',
    'planned_period': 'jpcrp_cor:PlannedPeriodOfIssueCoverPage',
    'security_types': 'jpcrp_cor:TypesOfSecuritiesToShelfRegisterForOfferingOrDistributionCoverPage',
    'place_of_filing': 'jpcrp_cor:PlaceOfFilingCoverPage',
    'address': 'jpcrp_cor:AddressOfRegisteredHeadquarterCoverPage',
    'representative': 'jpcrp_cor:TitleAndNameOfRepresentativeCoverPage',

    # === DEI Elements (jpdei_cor namespace) ===
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',
}


@dataclass
class ShelfRegistrationReport(ParsedReport):
    """
    Parsed Shelf Registration Statement (Doc 080/090).

    These filings disclose a company's shelf registration of securities
    (発行登録書) that it plans to issue over a defined future period.
    The shelf registration number identifies the specific registration.

    Key fields:
        company_name: Name of the issuing company (Japanese)
        company_name_en: Name of the issuing company (English)
        filer_edinet_code: EDINET code of the filing entity
        filing_date: Date the shelf registration was filed
        shelf_registration_number: Unique registration identifier
        planned_period: Planned issuance period (Japanese text)
        security_types: Types of securities to be registered
        is_amendment: Whether this is an amendment (Doc 090)
    """

    # Filer identification
    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    security_code: str | None = None

    # Cover page
    company_name: str | None = None
    company_name_en: str | None = None
    filing_date: date | None = None
    document_title: str | None = None
    shelf_registration_number: str | None = None
    planned_period: str | None = None
    security_types: str | None = None
    place_of_filing: str | None = None
    address: str | None = None
    representative: str | None = None

    # Amendment
    is_amendment: bool = False

    def __repr__(self) -> str:
        name = self.company_name or self.filer_name or 'Unknown'
        if len(name) > 25:
            name = name[:22] + '...'
        reg = self.shelf_registration_number or '?'
        amend = ' [AMENDED]' if self.is_amendment else ''
        return f"ShelfRegistrationReport(filer='{name}', reg='{reg}'{amend})"


def parse_shelf_registration(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> ShelfRegistrationReport:
    """
    Parse a Shelf Registration Statement filing.

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        ShelfRegistrationReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return ShelfRegistrationReport(
            doc_id=doc_id,
            doc_type_code=doc_type_code,
            source_files=[],
            raw_fields={},
            unmapped_fields={},
            text_blocks={},
        )

    source_files = [f['filename'] for f in csv_files]

    def get(key: str, context: list[str] | None = None) -> str | None:
        return extract_value(csv_files, ELEMENT_MAP.get(key, ''), context_patterns=context)

    # DEI elements
    filer_edinet_code = get('filer_edinet_code', ['FilingDateInstant'])
    filer_name = get('filer_name', ['FilingDateInstant'])
    filer_name_en = get('filer_name_en', ['FilingDateInstant'])
    security_code = get('security_code', ['FilingDateInstant'])
    amendment_flag = get('amendment_flag', ['FilingDateInstant'])

    # Cover page elements
    company_name = get('company_name') or filer_name
    company_name_en = get('company_name_en') or filer_name_en
    filing_date = parse_date(get('filing_date'))
    document_title = get('document_title')
    shelf_registration_number = get('shelf_registration_number')
    planned_period = get('planned_period')
    security_types = get('security_types')
    place_of_filing = get('place_of_filing')
    address = get('address')
    representative = get('representative')

    # Amendment detection
    is_amendment = amendment_flag == 'true' if amendment_flag else False

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return ShelfRegistrationReport(
        doc_id=doc_id,
        doc_type_code=doc_type_code,
        source_files=source_files,
        raw_fields=raw_fields,
        unmapped_fields=unmapped_fields,
        text_blocks=text_blocks,

        # Filer identification
        filer_name=filer_name,
        filer_name_en=filer_name_en,
        filer_edinet_code=filer_edinet_code or getattr(document, 'filer_edinet_code', None) if document else filer_edinet_code,
        security_code=security_code,

        # Cover page
        company_name=company_name,
        company_name_en=company_name_en,
        filing_date=filing_date,
        document_title=document_title,
        shelf_registration_number=shelf_registration_number,
        planned_period=planned_period,
        security_types=security_types,
        place_of_filing=place_of_filing,
        address=address,
        representative=representative,

        # Amendment
        is_amendment=is_amendment,
    )
