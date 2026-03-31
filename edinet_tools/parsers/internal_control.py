"""
Parser for Internal Control Report filings (Doc Type 235/236).

Extracts internal control evaluation data from 内部統制報告書 filings.
These are filed annually by listed companies reporting on the effectiveness
of their internal controls over financial reporting (J-SOX compliance).
The key field is the evaluation result — whether internal controls are
effective or material weaknesses were found.

Doc 235: Original internal control report
Doc 236: Amendment to internal control report
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


# XBRL Element ID mappings for Doc 235/236
# Namespace: jpctl_cor (Japanese Internal Control)
ELEMENT_MAP = {
    # === DEI Elements ===
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',

    # === Cover Page (jpctl_cor namespace) ===
    'company_name': 'jpctl_cor:CompanyNameCoverPage',
    'company_name_en': 'jpctl_cor:CompanyNameInEnglishCoverPage',
    'filing_date': 'jpctl_cor:FilingDateCoverPage',
    'document_title': 'jpctl_cor:DocumentTitleCoverPage',
    'clause_of_stipulation': 'jpctl_cor:ClauseOfStipulationCoverPage',
    'representative': 'jpctl_cor:TitleAndNameOfRepresentativeCoverPage',
    'cfo': 'jpctl_cor:TitleAndNameOfChiefFinancialOfficerCoverPage',
    'address': 'jpctl_cor:AddressOfRegisteredHeadquarterCoverPage',
    'place_of_filing': 'jpctl_cor:PlaceOfFilingCoverPage',

    # === Key TextBlock Elements ===
    # These are captured automatically by categorize_elements but also mapped
    # here for direct access on the dataclass.
    'evaluation_result_text': 'jpctl_cor:ResultOfEvaluationTextBlock',
    'scope_and_procedures_text': 'jpctl_cor:ScopeDateAndProceduresForEvaluationTextBlock',
    'framework_text': 'jpctl_cor:BasicFrameworkOfInternalControlRelatedToFinancialReportingTextBlock',
    'special_attention_text': 'jpctl_cor:OtherInformationForSpecialAttentionTextBlock',
    'supplementary_info_text': 'jpctl_cor:SupplementaryInformationTextBlock',
}


@dataclass
class InternalControlReport(ParsedReport):
    """
    Parsed Internal Control Report (Doc 235/236).

    Filed annually by listed companies under J-SOX (金融商品取引法 Section 24-4-4)
    to report on the effectiveness of internal controls over financial reporting.
    The board's evaluation result is the critical output — it discloses whether
    controls are effective or whether material weaknesses exist.

    Key fields:
        company_name: Name of the reporting company (Japanese)
        company_name_en: Name of the reporting company (English)
        filer_edinet_code: EDINET code of the filing entity
        filing_date: Date the report was filed
        representative: Title and name of the representative who signed
        cfo: Title and name of the CFO who signed
        clause_of_stipulation: Legal clause reference (e.g. Article 24-4-4)
        evaluation_result_text: THE KEY FIELD — board's evaluation of effectiveness
        scope_and_procedures_text: Scope, date, and procedures used in evaluation
        framework_text: Internal control framework description
        special_attention_text: Matters requiring special attention
        supplementary_info_text: Supplementary disclosures
        is_amendment: Whether this is an amendment (Doc 236)
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
    clause_of_stipulation: str | None = None
    representative: str | None = None
    cfo: str | None = None
    address: str | None = None
    place_of_filing: str | None = None

    # Key text blocks (Japanese text)
    evaluation_result_text: str | None = None
    scope_and_procedures_text: str | None = None
    framework_text: str | None = None
    special_attention_text: str | None = None
    supplementary_info_text: str | None = None

    # Amendment
    is_amendment: bool = False

    def __repr__(self) -> str:
        name = self.company_name or self.filer_name or 'Unknown'
        if len(name) > 25:
            name = name[:22] + '...'
        amend = ' [AMENDED]' if self.is_amendment else ''
        return f"InternalControlReport(filer='{name}'{amend})"


def parse_internal_control(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> InternalControlReport:
    """
    Parse an Internal Control Report filing (Doc 235/236).

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        InternalControlReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return InternalControlReport(
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
    clause_of_stipulation = get('clause_of_stipulation')
    representative = get('representative')
    cfo = get('cfo')
    address = get('address')
    place_of_filing = get('place_of_filing')

    # Key text blocks
    evaluation_result_text = get('evaluation_result_text')
    scope_and_procedures_text = get('scope_and_procedures_text')
    framework_text = get('framework_text')
    special_attention_text = get('special_attention_text')
    supplementary_info_text = get('supplementary_info_text')

    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return InternalControlReport(
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
        clause_of_stipulation=clause_of_stipulation,
        representative=representative,
        cfo=cfo,
        address=address,
        place_of_filing=place_of_filing,

        # Key text blocks
        evaluation_result_text=evaluation_result_text,
        scope_and_procedures_text=scope_and_procedures_text,
        framework_text=framework_text,
        special_attention_text=special_attention_text,
        supplementary_info_text=supplementary_info_text,

        # Amendment
        is_amendment=is_amendment,
    )
