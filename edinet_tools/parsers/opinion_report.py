"""
Parser for Statement of Opinion Report filings (Doc Type 290/300).

Extracts data from 意見表明報告書 filings. These are filed by the target
company's board in response to a tender offer, disclosing the board's
opinion (support, oppose, or neutral) and the rationale.

Doc 290: Original statement of opinion report
Doc 300: Amendment to statement of opinion report
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


# XBRL Element ID mappings for Doc 290/300
# Namespace: jptoo-pst_cor (Japanese Public Tender Offer — Position Statement)
ELEMENT_MAP = {
    # === DEI Elements ===
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',

    # === Cover Page (jptoo-pst_cor namespace) ===
    'document_title': 'jptoo-pst_cor:DocumentTitleCoverPage',
    'filing_date': 'jptoo-pst_cor:FilingDateCoverPage',
    'target_company_name': 'jptoo-pst_cor:NameOfFilerCoverPage',
    'target_company_address': 'jptoo-pst_cor:LocationOfFilerCoverPage',

    # === Key TextBlock Elements ===
    # The acquirer and opinion are the two most important fields.
    'acquirer_info_text': 'jptoo-pst_cor:NameAndResidentialAddressOrLocationOfTenderOfferorTextBlock',
    'opinion_text': 'jptoo-pst_cor:OpinionAndBasisAndReasonOfOpinionRegardingSaidTenderOfferTextBlock',
    'share_classes_text': 'jptoo-pst_cor:ClassesOfShareCertificatesEtcForTenderOfferorToAcquireByPurchaseEtcTextBlock',
    'officer_holdings_text': 'jptoo-pst_cor:NumberOfShareCertificatesEtcAndNumberOfVotingRightsOwnedByOfficersTextBlock',
    'extension_request_text': 'jptoo-pst_cor:RequestForExtendingTenderOfferPeriodNA',
    'inquiries_text': 'jptoo-pst_cor:InquiriesToTenderOfferorNA',
    'profit_provision_text': 'jptoo-pst_cor:DescriptionOfProvisionOfProfitByTenderOfferorOrItsSpecialInterestPartiesNA',
    'defense_policy_text': 'jptoo-pst_cor:PolicyToAddressBasicPolicyAboutHowToControlCompanyNA',
}


@dataclass
class OpinionReport(ParsedReport):
    """
    Parsed Statement of Opinion Report (Doc 290/300).

    Filed by the target company's board in response to a tender offer.
    The board discloses whether it supports, opposes, or is neutral on
    the offer and provides the reasoning.

    Key fields:
        target_company_name: Name of the target company filing the opinion
        filer_edinet_code: EDINET code of the target company
        security_code: Securities code of the target company
        filing_date: Date the opinion was filed
        opinion_text: THE KEY FIELD — the board's actual opinion and rationale
        acquirer_info_text: Name and address of the acquirer (tender offeror)
        share_classes_text: Classes of shares the tender offer covers
        officer_holdings_text: Shares and voting rights owned by officers
        defense_policy_text: Poison pill / takeover defense policy disclosure
        is_amendment: Whether this is an amendment (Doc 300)
    """

    # Filer identification
    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    security_code: str | None = None

    # Cover page
    filing_date: date | None = None
    document_title: str | None = None
    target_company_name: str | None = None
    target_company_address: str | None = None

    # Key text blocks (Japanese text)
    acquirer_info_text: str | None = None
    opinion_text: str | None = None
    share_classes_text: str | None = None
    officer_holdings_text: str | None = None
    extension_request_text: str | None = None
    inquiries_text: str | None = None
    profit_provision_text: str | None = None
    defense_policy_text: str | None = None

    # Amendment
    is_amendment: bool = False

    def __repr__(self) -> str:
        name = self.target_company_name or self.filer_name or 'Unknown'
        if len(name) > 30:
            name = name[:27] + '...'
        amend = ' [AMENDED]' if self.is_amendment else ''
        return f"OpinionReport(filer='{name}'{amend})"


def parse_opinion_report(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> OpinionReport:
    """
    Parse a Statement of Opinion Report filing (Doc 290/300).

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        OpinionReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return OpinionReport(
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
    filing_date = parse_date(get('filing_date'))
    document_title = get('document_title')
    target_company_name = get('target_company_name') or filer_name
    target_company_address = get('target_company_address')

    # Key text blocks
    acquirer_info_text = get('acquirer_info_text')
    opinion_text = get('opinion_text')
    share_classes_text = get('share_classes_text')
    officer_holdings_text = get('officer_holdings_text')
    extension_request_text = get('extension_request_text')
    inquiries_text = get('inquiries_text')
    profit_provision_text = get('profit_provision_text')
    defense_policy_text = get('defense_policy_text')

    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return OpinionReport(
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
        filing_date=filing_date,
        document_title=document_title,
        target_company_name=target_company_name,
        target_company_address=target_company_address,

        # Key text blocks
        acquirer_info_text=acquirer_info_text,
        opinion_text=opinion_text,
        share_classes_text=share_classes_text,
        officer_holdings_text=officer_holdings_text,
        extension_request_text=extension_request_text,
        inquiries_text=inquiries_text,
        profit_provision_text=profit_provision_text,
        defense_policy_text=defense_policy_text,

        # Amendment
        is_amendment=is_amendment,
    )
