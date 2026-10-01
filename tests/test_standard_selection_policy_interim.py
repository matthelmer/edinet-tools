"""Own-standard source selection in the quarterly and semi-annual parsers.

The annual parser's contract (test_standard_selection_policy.py), applied to
the quarterly (Doc 140/150) and semi-annual (Doc 160/170) reports: every
financial field declares its concept, the standards that tag it with an
element of their own, and, per declared standard, what happens when the own
fact is missing. These tests hold each declaration to the parser's tables.
"""

import dataclasses
from decimal import Decimal

import pytest

from edinet_tools.parsers import quarterly as q
from edinet_tools.parsers import semi_annual as s
from edinet_tools.parsers._standard_policy import (
    FALLBACKS,
    element_standard,
    fallback_for,
    table_elements,
)
from edinet_tools.parsers.quarterly import QuarterlyReport, parse_quarterly_report
from edinet_tools.parsers.securities import SecuritiesReport
from edinet_tools.parsers.semi_annual import SemiAnnualReport

STANDARDS = ("Japan GAAP", "IFRS", "US GAAP")
NOT_FINANCIAL = {"quarter_number"}


# ---------------------------------------------------------------------------
# The new fields exist (values arrive with the change)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,name,typ",
    [
        (QuarterlyReport, "profit_before_tax", int),
        (QuarterlyReport, "net_assets_owners", int),
        (QuarterlyReport, "accounting_standard", str),
        (SemiAnnualReport, "net_sales", int),
        (SemiAnnualReport, "operating_cash_flow", int),
        (SemiAnnualReport, "investing_cash_flow", int),
        (SemiAnnualReport, "financing_cash_flow", int),
        (SemiAnnualReport, "profit_before_tax", int),
        (SemiAnnualReport, "profit_attributable_to_owners", int),
        (SemiAnnualReport, "earnings_per_share", Decimal),
        (SecuritiesReport, "profit_before_tax", int),
    ],
)
def test_new_field_defaults_to_none(cls, name, typ):
    (f,) = [f for f in dataclasses.fields(cls) if f.name == name]
    assert typ.__name__ in str(f.type)
    assert getattr(cls(doc_id="X", doc_type_code="000"), name) is None


