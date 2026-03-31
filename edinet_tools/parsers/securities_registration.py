"""
Parser for Securities Registration Statement filings (Doc Type 030/040).

Extracts registration details from 有価証券届出書 filings. These are primarily
investment trust and fund registration filings containing detailed fund structure,
operational info, and DEI metadata.

Doc 030: Original securities registration statement
Doc 040: Amendment to securities registration statement
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


# XBRL Element ID mappings for Doc 030/040
# These filings are primarily investment trust registrations using the
# jpsps_cor (investment trust) namespace alongside the standard jpdei_cor DEI fields.
ELEMENT_MAP = {
    # === DEI Elements (common across all filing types) ===
    'filer_name': 'jpdei_cor:FilerNameInJapaneseDEI',
    'filer_name_en': 'jpdei_cor:FilerNameInEnglishDEI',
    'filer_edinet_code': 'jpdei_cor:EDINETCodeDEI',
    'security_code': 'jpdei_cor:SecurityCodeDEI',
    'amendment_flag': 'jpdei_cor:AmendmentFlagDEI',

    # === Investment Trust Cover Page (jpsps_cor namespace) ===
    'document_title': 'jpsps_cor:DocumentTitleCoverPage',
    'filing_date': 'jpsps_cor:FilingDateCoverPage',
    'issuer_name': 'jpsps_cor:IssuerNameCoverPage',
    'address': 'jpsps_cor:AddressOfRegisteredHeadquarterCoverPage',
    'representative': 'jpsps_cor:TitleAndNameOfRepresentativeCoverPage',
    'contact_person': 'jpsps_cor:NameOfContactPersonCoverPage',
    'telephone_number': 'jpsps_cor:TelephoneNumberCoverPage',
    'place_of_filing': 'jpsps_cor:PlaceOfFilingCoverPage',
    # Amount and name of trust certificates to be registered — stored as TextBlock
    # but mapped here for discoverability via extract_value.
    'amount_to_register': 'jpsps_cor:AmountOfDomesticInvestmentTrustBeneficiaryCertificateToRegisterForOfferingOrDistributionCoverPageTextBlock',
    'fund_name_for_registration': 'jpsps_cor:NameOfFundRelatedToDomesticInvestmentTrustBeneficiaryCertificateToRegisterForOfferingOrDistributionCoverPageTextBlock',

    # === Fund Identity (TextBlock — mapped for discoverability) ===
    'fund_name': 'jpsps_cor:FundNameTextBlock',
    'fund_purpose': 'jpsps_cor:PurposesAndBasicFeaturesOfFundTextBlock',
    'fund_scheme': 'jpsps_cor:FundSchemeTextBlock',
    'fund_history': 'jpsps_cor:FundHistoryTextBlock',

    # === Investment Policy (TextBlock) ===
    'investment_policy': 'jpsps_cor:InvestmentPolicyTextBlock',
    'investment_risks': 'jpsps_cor:InvestmentRisksTextBlock',
    'eligible_investments': 'jpsps_cor:ThingsToInvestInTextBlock',
    'investment_restrictions': 'jpsps_cor:RestrictionsOnInvestmentTextBlock',

    # === Operations (TextBlock) ===
    'management_fees': 'jpsps_cor:ManagementFeesAndChargesTextBlock',
    'application_fee': 'jpsps_cor:ApplicationFeeSecurityInformationTextBlock',
    'application_period': 'jpsps_cor:ApplicationPeriodSecurityInformationTextBlock',
    'application_unit': 'jpsps_cor:ApplicationUnitSecurityInformationTextBlock',
    'redemption_procedures': 'jpsps_cor:RedemptionProceduresEtcTextBlock',
    'profit_distribution_policy': 'jpsps_cor:ProfitDistributionPolicyTextBlock',
    'taxation': 'jpsps_cor:TaxationTextBlock',

    # === Financial Information (TextBlock) ===
    'financial_info': 'jpsps_cor:FinancialInformationOfFundTextBlock',
    'balance_sheet': 'jpsps_cor:BalanceSheetTextBlock',
    'income_statement': 'jpsps_cor:StatementOfIncomeAndRetainedEarningsTextBlock',
    'changes_in_net_assets': 'jpsps_cor:ChangesInNetAssetsTextBlock',
    'net_assets_calculation': 'jpsps_cor:CalculationOfNetAssetsTextBlock',
}


@dataclass
class SecuritiesRegistrationReport(ParsedReport):
    """
    Parsed Securities Registration Statement (Doc 030/040).

    These filings are primarily investment trust and fund registrations
    (有価証券届出書). They contain DEI metadata and, for investment trusts,
    detailed fund-specific fields under the jpsps_cor namespace.

    Key fields:
        filer_name: Name of the filing entity (Japanese)
        filer_edinet_code: EDINET code of the filing entity
        filing_date: Date the registration was filed
        fund_name: Name of the investment trust fund (if applicable)
        issuer_name: Name of the fund management company
        contact_person: Name of the contact person at the issuer
        telephone_number: Telephone number of the contact
        place_of_filing: Place where the filing was submitted
        amount_to_register: Amount/units of trust certificates being registered (text)
        fund_name_for_registration: Fund name as stated on the cover registration block (text)
        fund_purpose: Fund purpose and basic features (TextBlock)
        fund_scheme: Fund structure description (TextBlock)
        fund_history: Fund history (TextBlock)
        investment_policy: Investment policy (TextBlock)
        investment_risks: Risk disclosure (TextBlock)
        eligible_investments: Eligible investments description (TextBlock)
        investment_restrictions: Investment restrictions (TextBlock)
        management_fees: Management fees and charges (TextBlock)
        application_fee: Application fee details (TextBlock)
        application_period: Application period (TextBlock)
        application_unit: Minimum application unit (TextBlock)
        redemption_procedures: Redemption procedure details (TextBlock)
        profit_distribution_policy: Distribution policy (TextBlock)
        taxation: Taxation details (TextBlock)
        financial_info: Financial information summary (TextBlock)
        balance_sheet: Balance sheet (TextBlock)
        income_statement: Income and retained earnings statement (TextBlock)
        changes_in_net_assets: Changes in net assets (TextBlock)
        net_assets_calculation: Net assets calculation (TextBlock)
        is_amendment: Whether this is an amendment (Doc 040)
    """

    # Filer identification
    filer_name: str | None = None
    filer_name_en: str | None = None
    filer_edinet_code: str | None = None
    security_code: str | None = None

    # Cover page — structured fields
    filing_date: date | None = None
    document_title: str | None = None
    issuer_name: str | None = None
    address: str | None = None
    representative: str | None = None
    contact_person: str | None = None
    telephone_number: str | None = None
    place_of_filing: str | None = None

    # Cover page — registration block (stored as TextBlock in XBRL but key identity info)
    amount_to_register: str | None = None
    fund_name_for_registration: str | None = None

    # Fund identity (TextBlock fields — content is HTML/text from XBRL)
    fund_name: str | None = None
    fund_purpose: str | None = None
    fund_scheme: str | None = None
    fund_history: str | None = None

    # Investment policy (TextBlock)
    investment_policy: str | None = None
    investment_risks: str | None = None
    eligible_investments: str | None = None
    investment_restrictions: str | None = None

    # Operations (TextBlock)
    management_fees: str | None = None
    application_fee: str | None = None
    application_period: str | None = None
    application_unit: str | None = None
    redemption_procedures: str | None = None
    profit_distribution_policy: str | None = None
    taxation: str | None = None

    # Financial information (TextBlock)
    financial_info: str | None = None
    balance_sheet: str | None = None
    income_statement: str | None = None
    changes_in_net_assets: str | None = None
    net_assets_calculation: str | None = None

    # Amendment
    is_amendment: bool = False

    def __repr__(self) -> str:
        name = self.fund_name or self.filer_name or 'Unknown'
        if len(name) > 30:
            name = name[:27] + '...'
        amend = ' [AMENDED]' if self.is_amendment else ''
        return f"SecuritiesRegistrationReport(filer='{name}'{amend})"


def parse_securities_registration(document=None, *, csv_files=None, doc_id=None, doc_type_code=None) -> SecuritiesRegistrationReport:
    """
    Parse a Securities Registration Statement filing.

    Args:
        document: Document object with fetch() method (optional if csv_files provided)
        csv_files: Pre-extracted CSV data (list of dicts with 'filename' and 'data' keys)
        doc_id: Document ID (required if csv_files provided)
        doc_type_code: Document type code (required if csv_files provided)

    Returns:
        SecuritiesRegistrationReport with extracted fields
    """
    if csv_files is None:
        zip_bytes = document.fetch()
        csv_files = extract_csv_from_zip(zip_bytes)
        doc_id = document.doc_id
        doc_type_code = document.doc_type_code

    if not csv_files:
        return SecuritiesRegistrationReport(
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

    # Cover page — structured fields
    document_title = get('document_title')
    filing_date = parse_date(get('filing_date'))
    issuer_name = get('issuer_name') or filer_name
    address = get('address')
    representative = get('representative')
    contact_person = get('contact_person')
    telephone_number = get('telephone_number')
    place_of_filing = get('place_of_filing')

    # Cover page — registration block (TextBlock elements used as identity info)
    amount_to_register = get('amount_to_register')
    fund_name_for_registration = get('fund_name_for_registration')

    # Fund identity (TextBlock)
    fund_name = get('fund_name')
    fund_purpose = get('fund_purpose')
    fund_scheme = get('fund_scheme')
    fund_history = get('fund_history')

    # Investment policy (TextBlock)
    investment_policy = get('investment_policy')
    investment_risks = get('investment_risks')
    eligible_investments = get('eligible_investments')
    investment_restrictions = get('investment_restrictions')

    # Operations (TextBlock)
    management_fees = get('management_fees')
    application_fee = get('application_fee')
    application_period = get('application_period')
    application_unit = get('application_unit')
    redemption_procedures = get('redemption_procedures')
    profit_distribution_policy = get('profit_distribution_policy')
    taxation = get('taxation')

    # Financial information (TextBlock)
    financial_info = get('financial_info')
    balance_sheet = get('balance_sheet')
    income_statement = get('income_statement')
    changes_in_net_assets = get('changes_in_net_assets')
    net_assets_calculation = get('net_assets_calculation')

    # Amendment detection
    is_amendment = amendment_flag == 'true' if amendment_flag else False

    # Categorize all elements
    raw_fields, text_blocks, unmapped_fields = categorize_elements(csv_files, ELEMENT_MAP)

    return SecuritiesRegistrationReport(
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

        # Cover page — structured
        filing_date=filing_date,
        document_title=document_title,
        issuer_name=issuer_name,
        address=address,
        representative=representative,
        contact_person=contact_person,
        telephone_number=telephone_number,
        place_of_filing=place_of_filing,

        # Cover page — registration block
        amount_to_register=amount_to_register,
        fund_name_for_registration=fund_name_for_registration,

        # Fund identity
        fund_name=fund_name,
        fund_purpose=fund_purpose,
        fund_scheme=fund_scheme,
        fund_history=fund_history,

        # Investment policy
        investment_policy=investment_policy,
        investment_risks=investment_risks,
        eligible_investments=eligible_investments,
        investment_restrictions=investment_restrictions,

        # Operations
        management_fees=management_fees,
        application_fee=application_fee,
        application_period=application_period,
        application_unit=application_unit,
        redemption_procedures=redemption_procedures,
        profit_distribution_policy=profit_distribution_policy,
        taxation=taxation,

        # Financial information
        financial_info=financial_info,
        balance_sheet=balance_sheet,
        income_statement=income_statement,
        changes_in_net_assets=changes_in_net_assets,
        net_assets_calculation=net_assets_calculation,

        # Amendment
        is_amendment=is_amendment,
    )
