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
        "120": parse_securities_report,
        "140": parse_quarterly_report,
        "160": parse_semi_annual_report,
        "180": parse_extraordinary_report,
        "350": parse_large_holding,
    }

    parser = parsers.get(document.doc_type_code)
    if parser:
        return parser(document)

    return parse_raw(document)


__all__ = [
    'parse',
    'ParsedReport',
    'RawReport',
    'LargeHoldingReport',
    'SecuritiesReport',
    'QuarterlyReport',
    'SemiAnnualReport',
    'ExtraordinaryReport',
    # Backwards compatibility
    'GenericReport',
]
