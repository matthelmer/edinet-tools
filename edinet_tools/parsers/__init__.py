"""
Document parsers for EDINET filings.

Provides typed parsers for known document types and a raw fallback.
"""
from .base import ParsedReport
from .generic import RawReport, parse_raw, GenericReport, parse_generic
from .large_holding import LargeHoldingReport, parse_large_holding
from .securities import SecuritiesReport, parse_securities_report
from .quarterly import QuarterlyReport, parse_quarterly_report
from .semi_annual import SemiAnnualReport, parse_semi_annual_report
from .extraordinary import ExtraordinaryReport, parse_extraordinary_report
from .treasury_stock import TreasuryStockReport, parse_treasury_stock_report
from .tender_offer import TenderOfferReport, parse_tender_offer
from .tender_offer_report import TenderOfferResultReport, parse_tender_offer_report
from .tender_offer_withdrawal import TenderOfferWithdrawalReport, parse_tender_offer_withdrawal
from .opinion_report import OpinionReport, parse_opinion_report
from .question_response import QuestionResponseReport, parse_question_response
from .exemption_application import ExemptionApplicationReport, parse_exemption_application
from .securities_notification import SecuritiesNotificationReport, parse_securities_notification
from .securities_registration import SecuritiesRegistrationReport, parse_securities_registration
from .securities_withdrawal import SecuritiesWithdrawalReport, parse_securities_withdrawal
from .issuance_notification import IssuanceNotificationReport, parse_issuance_notification
from .shelf_registration import ShelfRegistrationReport, parse_shelf_registration
from .issuance_supplementary import IssuanceSupplementaryReport, parse_issuance_supplementary
from .issuance_withdrawal import IssuanceWithdrawalReport, parse_issuance_withdrawal
from .internal_control import InternalControlReport, parse_internal_control
from .confirmation import ConfirmationReport, parse_confirmation
from .parent_company import ParentCompanyReport, parse_parent_company
from .large_holding_change import LargeHoldingChangeReport, parse_large_holding_change


# Doc type codes that have typed parsers (not raw fallback).
# Kept as a frozenset so supported_doc_types() can return it without
# rebuilding a function-reference dict at module load time.
_SUPPORTED_CODES: frozenset[str] = frozenset({
    # === Securities notification / registration family (010-110) ===
    "010", "020",           # Securities notification
    "030", "040", "050",   # Securities registration
    "060",                 # Issuance notification
    "070", "080", "090",   # Shelf registration
    "100",                 # Issuance supplementary
    "110",                 # Issuance withdrawal
    # === Securities reports family (120-170) ===
    "120", "130",          # Securities report + amendment
    "135", "136",          # Confirmation document + amendment
    "140", "150",          # Quarterly report + amendment
    "160", "170",          # Semi-annual report + amendment
    # === Extraordinary / treasury / internal control / tender offer family (180-340) ===
    "180", "190",          # Extraordinary report + amendment
    "200", "210",          # Parent company status report + amendment
    "220", "230",          # Treasury stock + amendment
    "235", "236",          # Internal control report + amendment
    "240", "250",          # Tender offer registration + amendment
    "260",                 # Tender offer withdrawal
    "270", "280",          # Tender offer report + amendment
    "290", "300",          # Opinion report + amendment
    "310", "320",          # Question response + amendment
    "330", "340",          # Exemption application + amendment
    # === Large shareholding family (350-380) ===
    "350", "360",          # Large shareholding + amendment
    "370", "380",          # Large shareholding change + amendment
})


def parse(document) -> ParsedReport:
    """
    Parse any document. Returns typed parser if available,
    RawReport fallback otherwise.

    Args:
        document: Document object with doc_id, doc_type_code, etc.

    Returns:
        ParsedReport subclass appropriate for the document type
    """
    parsers = {
        # === Securities notification / registration family (010-110) ===
        "010": parse_securities_notification,
        "020": parse_securities_notification,  # Amendment
        "030": parse_securities_registration,
        "040": parse_securities_registration,  # Amendment
        "050": parse_securities_withdrawal,
        "060": parse_issuance_notification,
        # Doc 070 is also a shelf registration filing (発行登録書) — same family as 080.
        # Route it to the shelf registration parser pending separate XBRL inspection.
        "070": parse_shelf_registration,
        "080": parse_shelf_registration,
        "090": parse_shelf_registration,       # Amendment
        "100": parse_issuance_supplementary,
        "110": parse_issuance_withdrawal,

        # === Securities reports family (120-170) ===
        "120": parse_securities_report,
        "130": parse_securities_report,        # Amendment
        "135": parse_confirmation,
        "136": parse_confirmation,             # Amendment
        "140": parse_quarterly_report,
        "150": parse_quarterly_report,         # Amendment
        "160": parse_semi_annual_report,
        "170": parse_semi_annual_report,       # Amendment

        # === Extraordinary / treasury / tender offer family (180-340) ===
        "180": parse_extraordinary_report,
        "190": parse_extraordinary_report,     # Amendment
        "200": parse_parent_company,
        "210": parse_parent_company,           # Amendment
        "220": parse_treasury_stock_report,
        "230": parse_treasury_stock_report,    # Amendment (existing)
        "235": parse_internal_control,
        "236": parse_internal_control,         # Amendment
        "240": parse_tender_offer,
        "250": parse_tender_offer,             # Amendment
        "260": parse_tender_offer_withdrawal,
        "270": parse_tender_offer_report,
        "280": parse_tender_offer_report,      # Amendment
        "290": parse_opinion_report,
        "300": parse_opinion_report,           # Amendment
        "310": parse_question_response,
        "320": parse_question_response,        # Amendment
        "330": parse_exemption_application,
        "340": parse_exemption_application,    # Amendment

        # === Large shareholding family (350-380) ===
        "350": parse_large_holding,
        "360": parse_large_holding,            # Amendment
        "370": parse_large_holding_change,
        "380": parse_large_holding_change,     # Amendment
    }

    parser = parsers.get(document.doc_type_code)
    if parser:
        return parser(document)

    return parse_raw(document)


def supported_doc_types() -> list[str]:
    """Return doc type codes that have typed parsers (not raw fallback)."""
    return sorted(_SUPPORTED_CODES)


__all__ = [
    'parse',
    'supported_doc_types',
    'ParsedReport',
    'RawReport',
    'LargeHoldingReport',
    'SecuritiesReport',
    'QuarterlyReport',
    'SemiAnnualReport',
    'ExtraordinaryReport',
    'TreasuryStockReport',
    'TenderOfferReport',
    'TenderOfferResultReport',
    'TenderOfferWithdrawalReport',
    'OpinionReport',
    'QuestionResponseReport',
    'ExemptionApplicationReport',
    'SecuritiesNotificationReport',
    'SecuritiesRegistrationReport',
    'SecuritiesWithdrawalReport',
    'IssuanceNotificationReport',
    'ShelfRegistrationReport',
    'IssuanceSupplementaryReport',
    'IssuanceWithdrawalReport',
    'InternalControlReport',
    'ConfirmationReport',
    'ParentCompanyReport',
    'LargeHoldingChangeReport',
    # Backwards compatibility
    'GenericReport',
]
