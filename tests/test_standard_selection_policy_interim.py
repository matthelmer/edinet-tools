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


def _financial_fields(cls):
    out = set()
    for f in dataclasses.fields(cls):
        t = str(f.type)
        if ("int" in t or "Decimal" in t) and f.name not in NOT_FINANCIAL:
            out.add(f.name.removeprefix("prior_"))
    return out


PARSERS = [
    pytest.param(q, QuarterlyReport, id="quarterly"),
    pytest.param(s, SemiAnnualReport, id="semi"),
]


@pytest.mark.parametrize("mod,cls", PARSERS)
def test_every_interim_financial_field_has_a_declared_policy(mod, cls):
    assert set(mod._STANDARD_POLICY) == _financial_fields(cls)


@pytest.mark.parametrize("mod,cls", PARSERS)
def test_every_field_and_declared_standard_has_one_fallback(mod, cls):
    for name, policy in mod._STANDARD_POLICY.items():
        assert policy.concept, name
        for std in STANDARDS:
            assert fallback_for(policy, std) in FALLBACKS, (name, std)


@pytest.mark.parametrize("mod,cls", PARSERS)
def test_the_declared_standards_are_the_standards_of_the_field_elements(mod, cls):
    """A field declares exactly the standards its tables' elements belong to;
    a standard it does not declare has no element of its own ('none
    exist')."""
    for name, policy in mod._STANDARD_POLICY.items():
        found = set()
        for el in table_elements(*mod._LEGACY_TABLES[name]):
            std = element_standard(el)
            if std == "neutral":
                assert el in policy.neutral, (name, el)
            else:
                found.add(std)
        assert set(policy.standards) == found, name


def test_the_decided_fallbacks():
    """The checklist's 'none' cells (Matt and the controller, 2026-09-30)."""
    none = {
        (q, "operating_profit_ytd"): ("IFRS", "US GAAP"),
        (q, "ordinary_profit_ytd"): ("IFRS", "US GAAP"),
        (q, "profit_before_tax"): STANDARDS,
        (q, "net_assets_owners"): STANDARDS,
        (s, "operating_income"): ("IFRS", "US GAAP"),
        (s, "profit_loss"): ("US GAAP",),
        (s, "profit_before_tax"): STANDARDS,
    }
    for mod in (q, s):
        for name, policy in mod._STANDARD_POLICY.items():
            closed = tuple(x for x in STANDARDS if fallback_for(policy, x) == "none")
            assert closed == none.get((mod, name), ()), (mod.__name__, name)


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


def _qparse(*rows):
    data = [
        {"要素ID": e, "コンテキストID": c, "値": v}
        for e, c, v in [("jpdei_cor:EDINETCodeDEI", "FilingDateInstant", "E00000"), *rows]
    ]
    return parse_quarterly_report(
        csv_files=[{"filename": "t.csv", "data": data}], doc_id="T", doc_type_code="140"
    )


def test_quarterly_reads_the_declared_standard():
    r = _qparse(("jpdei_cor:AccountingStandardsDEI", "FilingDateInstant", "IFRS"))
    assert r.accounting_standard == "IFRS"


def test_quarterly_standard_is_whitespace_stripped():
    r = _qparse(("jpdei_cor:AccountingStandardsDEI", "FilingDateInstant", "Japan GAAP\t\t"))
    assert r.accounting_standard == "Japan GAAP"


def test_quarterly_standard_is_none_when_not_declared():
    assert _qparse().accounting_standard is None


def test_quarterly_standard_dei_stays_in_unmapped_fields():
    """Reading the standard does not move its DEI element out of the bag."""
    r = _qparse(("jpdei_cor:AccountingStandardsDEI", "FilingDateInstant", "IFRS"))
    assert r.unmapped_fields["AccountingStandardsDEI"] == "IFRS"
