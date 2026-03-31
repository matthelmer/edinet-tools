"""
Parser for Issuance Supplementary filings (Doc Type 100).

Extracts shelf registration supplement details from 発行登録追補書類 filings.
These are filed to supplement a shelf registration with the specific terms
of each actual issuance under the shelf. Key data includes the supplement
number, parent shelf registration number, planned amounts, and remaining
balance available under the shelf.

Doc 100: Issuance supplementary document
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


# XBRL Element ID mappings for Doc 100
# Namespace: jpcrp_cor (same family as shelf_registration 080/090)
ELEMENT_MAP = {
    # === DEI Elements ===
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',

    # === Cover Page (jpcrp_cor namespace) ===
    'company_name': 'jpcrp_cor:CompanyNameCoverPage',
    'company_name_en': 'jpcrp_cor:CompanyNameInEnglishCoverPage',
    'filing_date': 'jpcrp_cor:FilingDateCoverPage',
    'document_title': 'jpcrp_cor:DocumentTitleCoverPage',

    # === Supplement / Shelf registration linkage ===
    'supplement_number': 'jpcrp_cor:ShelfRegistrationSupplementNumberCoverPage',
    'parent_shelf_reg_number': 'jpcrp_cor:ShelfRegistrationNumberContentsOfShelfRegistrationStatementCoverPage',
    'parent_filing_date': 'jpcrp_cor:FilingDateContentsOfShelfRegistrationStatementCoverPage',
    'effective_date': 'jpcrp_cor:EffectiveDateContentsOfShelfRegistrationStatementCoverPage',
    'end_of_issue_period': 'jpcrp_cor:EndOfPeriodOfIssueContentsOfShelfRegistrationStatementCoverPage',
    'planned_amount': 'jpcrp_cor:PlannedAmountOfIssueOrLimitOnOutstandingBalanceContentsOfShelfRegistrationStatementCoverPage',
    'remaining_balance': 'jpcrp_cor:RemainingBalanceCoverPage',
    'security_types': 'jpcrp_cor:TypesOfSecuritiesToShelfRegisterForOfferingOrDistributionCoverPage',

    # === Filer / representative details ===
    'address': 'jpcrp_cor:AddressOfRegisteredHeadquarterCoverPage',
    'representative': 'jpcrp_cor:TitleAndNameOfRepresentativeCoverPage',
    'place_of_filing': 'jpcrp_cor:PlaceOfFilingCoverPage',
}


@dataclass
class IssuanceSupplementaryReport(ParsedReport):
    """
    Parsed Issuance Supplementary filing (Doc 100).

    Filed to supplement a shelf registration (発行登録追補書類) with the
    specific terms of each actual issuance. Links back to the parent shelf
    registration and discloses the amounts issued and remaining balance.

    Key fields:
        company_name: Name of the issuing company (Japanese)
        company_name_en: Name of the issuing company (English)
        filer_edinet_code: EDINET code of the filing entity
        filing_date: Date this supplement was filed
        supplement_number: Sequential number of this supplement under the shelf
        parent_shelf_reg_number: Registration number of the parent shelf filing
        planned_amount: Amount planned for issuance under this supplement
        remaining_balance: Remaining balance available under the shelf registration
        security_types: Types of securities being issued
        is_amendment: Whether this is an amendment
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

    # Supplement / shelf linkage
    supplement_number: str | None = None
    parent_shelf_reg_number: str | None = None
    parent_filing_date: date | None = None
    effective_date: str | None = None
    end_of_issue_period: str | None = None
    planned_amount: str | None = None
    remaining_balance: str | None = None
    security_types: str | None = None

    # Filer / representative details
    address: str | None = None
    representative: str | None = None
    place_of_filing: str | None = None

    # Amendment
    is_amendment: bool = False

    def __repr__(self) -> str:
        name = self.company_name or self.filer_name or 'Unknown'
        if len(name) > 25:
            name = name[:22] + '...'
        supp = self.supplement_number or '?'
        amend = ' [AMENDED]' if self.is_amendment else ''
        return f"IssuanceSupplementaryReport(filer='{name}', supplement='{supp}'{amend})"


def parse_issuance_supplementary(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> IssuanceSupplementaryReport:
    """
    Parse an Issuance Supplementary filing.

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        IssuanceSupplementaryReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return IssuanceSupplementaryReport(
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
    is_amendment = amendment_flag == 'true' if amendment_flag else False

    # Cover page
    company_name = get('company_name') or filer_name
    company_name_en = get('company_name_en') or filer_name_en
    filing_date = parse_date(get('filing_date'))
    document_title = get('document_title')

    # Supplement / shelf linkage
    supplement_number = get('supplement_number')
    parent_shelf_reg_number = get('parent_shelf_reg_number')
    parent_filing_date = parse_date(get('parent_filing_date'))
    effective_date = get('effective_date')
    end_of_issue_period = get('end_of_issue_period')
    planned_amount = get('planned_amount')
    remaining_balance = get('remaining_balance')
    security_types = get('security_types')

    # Filer / representative details
    address = get('address')
    representative = get('representative')
    place_of_filing = get('place_of_filing')

    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return IssuanceSupplementaryReport(
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

        # Supplement / shelf linkage
        supplement_number=supplement_number,
        parent_shelf_reg_number=parent_shelf_reg_number,
        parent_filing_date=parent_filing_date,
        effective_date=effective_date,
        end_of_issue_period=end_of_issue_period,
        planned_amount=planned_amount,
        remaining_balance=remaining_balance,
        security_types=security_types,

        # Filer / representative details
        address=address,
        representative=representative,
        place_of_filing=place_of_filing,

        # Amendment
        is_amendment=is_amendment,
    )
