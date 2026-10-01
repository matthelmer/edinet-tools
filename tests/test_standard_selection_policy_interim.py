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


# ---------------------------------------------------------------------------
# The competing-source grid (cases numbered as the annual grid's, plus 10-14)
#
# Expected values are derived from the declaration and the legacy tables
# (tests/_standard_grid.py), never from the resolved tables the parser uses.
# ---------------------------------------------------------------------------

from tests import _standard_grid as g  # noqa: E402


class Spec:
    def __init__(self, label, mod, parse, doc_type, kinds, instant, prior, tokens):
        self.label, self.mod, self.parse_fn, self.doc_type = label, mod, parse, doc_type
        self.kinds, self.instant, self.prior, self.tokens = kinds, instant, prior, tokens

    def base(self, name):
        return name.removeprefix("prior_")

    def policy(self, name):
        return self.mod._STANDARD_POLICY[self.base(name)]

    def tables(self, name):
        return self.mod._LEGACY_TABLES[self.base(name)]

    def kind(self, name):
        return self.kinds.get(self.base(name), "int")

    def period(self, name):
        if name.startswith("prior_"):
            return self.tokens["P"]
        return self.tokens["I"] if self.base(name) in self.instant else self.tokens["D"]

    def fields(self):
        out = []
        for name in self.mod._STANDARD_POLICY:
            out.append(name)
            if name in self.prior:
                out.append(f"prior_{name}")
        return out

    def parse(self, rows, standard, consolidated="true"):
        cf = g.csv_files(rows, standard, consolidated)
        return self.parse_fn(csv_files=cf, doc_id="GRID", doc_type_code=self.doc_type)

    def sentinel(self, name, std, prior=False):
        if prior:
            return g.PRIOR_SENTINEL[std]
        return g.SENTINEL[self.kind(name)][std]

    def row(self, name, std, value=None, suffix=""):
        element, _ = g.rep(self.tables(name), std)
        return (element, self.period(name) + suffix, value or self.sentinel(name, std))


QS = Spec(
    "quarterly",
    q,
    parse_quarterly_report,
    "140",
    {"eps_basic_ytd": "dec", "equity_ratio": "pct"},
    {"total_assets", "net_assets", "net_assets_owners", "total_liabilities", "equity_ratio"},
    ("revenue_ytd", "operating_profit_ytd", "ordinary_profit_ytd", "net_income_ytd"),
    {"D": "CurrentYTDDuration", "P": "Prior1YTDDuration", "I": "CurrentQuarterInstant"},
)
_S_INSTANT = {
    "total_assets",
    "current_assets",
    "total_liabilities",
    "current_liabilities",
    "net_assets",
}
SI = Spec(
    "semi-interim",
    s,
    s.parse_semi_annual_report,
    "160",
    {"earnings_per_share": "dec"},
    _S_INSTANT,
    (),
    {"D": "InterimDuration", "I": "InterimInstant"},
)
SQ = Spec(
    "semi-q2r",
    s,
    s.parse_semi_annual_report,
    "160",
    {"earnings_per_share": "dec"},
    _S_INSTANT,
    (),
    {"D": "CurrentYTDDuration", "I": "CurrentQuarterInstant"},
)
SPECS = (QS, SI, SQ)


def _params(build):
    out = []
    for spec in SPECS:
        for t in build(spec):
            out.append(
                pytest.param(
                    spec, *t, id=spec.label + "-" + "-".join(str(x).replace(" ", "") for x in t)
                )
            )
    return out


def _pairs(spec, owns, other_pick):
    out = []
    for name in spec.fields():
        stds = spec.policy(name).standards
        for own in owns:
            if own not in stds:
                continue
            other = other_pick(stds, own)
            if other is not None:
                out.append((name, own, other))
    return out


def _jgaap_else_other(stds, own):
    if own != "Japan GAAP" and "Japan GAAP" in stds:
        return "Japan GAAP"
    rest = [x for x in stds if x != own]
    return rest[0] if rest else None


def _all_pairs(spec):
    out = []
    for name in spec.fields():
        stds = spec.policy(name).standards
        out += [(name, a, b) for a in stds for b in stds if a != b]
    return out


def _fallback_expected(spec, name, own, other):
    if fallback_for(spec.policy(name), own) == "none":
        return None
    element, _ = g.rep(spec.tables(name), other)
    if not g.reads(spec.tables(name), own, element):
        return None
    return g.typed(spec.sentinel(name, other), spec.kind(name))


def _value(spec, name, r):
    return getattr(r, name)


# 1-3: the declared standard's fact wins over every other standard's fact,
# and the element and context it was read at are recorded.
@pytest.mark.parametrize("spec,name,own,other", _params(_all_pairs))
def test_declared_standard_outranks_each_other_standard(spec, name, own, other):
    r = spec.parse([spec.row(name, own), spec.row(name, other)], own)
    assert _value(spec, name, r) == g.typed(spec.sentinel(name, own), spec.kind(name))
    assert r.source_elements[name] == g.rep(spec.tables(name), own)[0]
    assert r.source_contexts[name] == spec.period(name)


@pytest.mark.parametrize(
    "spec,name",
    [
        pytest.param(sp, n, id=f"{sp.label}-{n}")
        for sp in SPECS
        for n in sp.fields()
        if "Japan GAAP" in sp.policy(n).standards
    ],
)
def test_jgaap_declared_reads_jgaap(spec, name):
    stds = spec.policy(name).standards
    r = spec.parse([spec.row(name, x) for x in stds], "Japan GAAP")
    assert _value(spec, name, r) == g.typed(spec.sentinel(name, "Japan GAAP"), spec.kind(name))


# 4: no DEI standard: the legacy order.
@pytest.mark.parametrize(
    "spec,name", [pytest.param(sp, n, id=f"{sp.label}-{n}") for sp in SPECS for n in sp.fields()]
)
def test_no_declared_standard_keeps_the_legacy_order(spec, name):
    stds = spec.policy(name).standards
    present = {x: g.rep(spec.tables(name), x) for x in stds}
    winner = g.first_reader(spec.tables(name), None, present)
    r = spec.parse([spec.row(name, x) for x in stds], None)
    expected = None if winner is None else spec.sentinel(name, winner)
    assert _value(spec, name, r) == g.typed(expected, spec.kind(name))


# 5: the own-standard fact is missing: the declared fallback.
@pytest.mark.parametrize(
    "spec,name,own,other", _params(lambda sp: _pairs(sp, g.STANDARDS, _jgaap_else_other))
)
def test_missing_own_fact_follows_the_declared_fallback(spec, name, own, other):
    r = spec.parse([spec.row(name, other)], own)
    assert _value(spec, name, r) == _fallback_expected(spec, name, own, other)


# 6: a null marker is a missing fact; a genuine zero is a value.
@pytest.mark.parametrize("marker", ["－", "—"])
@pytest.mark.parametrize(
    "spec,name,own,other",
    _params(lambda sp: _pairs(sp, ("IFRS", "US GAAP"), _jgaap_else_other)),
)
def test_own_null_marker_falls_through(spec, name, own, other, marker):
    r = spec.parse([spec.row(name, other), spec.row(name, own, marker)], own)
    assert _value(spec, name, r) == _fallback_expected(spec, name, own, other)


@pytest.mark.parametrize(
    "spec,name,own,other",
    _params(lambda sp: _pairs(sp, ("IFRS", "US GAAP"), _jgaap_else_other)),
)
def test_own_zero_is_a_value_and_wins(spec, name, own, other):
    r = spec.parse([spec.row(name, other), spec.row(name, own, "0")], own)
    assert _value(spec, name, r) == g.typed("0", spec.kind(name))


# 7: each period chooses independently (the quarterly prior-year fields).
def _prior_pairs(spec):
    return [t for t in _pairs(spec, ("IFRS", "US GAAP"), _jgaap_else_other) if t[0] in spec.prior]


@pytest.mark.parametrize("spec,name,own,other", _params(_prior_pairs))
def test_current_own_prior_other(spec, name, own, other):
    own_el, _ = g.rep(spec.tables(name), own)
    other_el, _ = g.rep(spec.tables(name), other)
    rows = [
        (own_el, spec.tokens["D"], g.SENTINEL["int"][own]),
        (other_el, spec.tokens["D"], g.SENTINEL["int"][other]),
        (other_el, spec.tokens["P"], g.PRIOR_SENTINEL[other]),
    ]
    r = spec.parse(rows, own)
    assert getattr(r, name) == int(g.SENTINEL["int"][own])
    expected = _fallback_expected(spec, name, own, other)
    assert getattr(r, f"prior_{name}") == (
        None if expected is None else int(g.PRIOR_SENTINEL[other])
    )


@pytest.mark.parametrize("spec,name,own,other", _params(_prior_pairs))
def test_prior_own_current_other(spec, name, own, other):
    own_el, _ = g.rep(spec.tables(name), own)
    other_el, _ = g.rep(spec.tables(name), other)
    rows = [
        (other_el, spec.tokens["D"], g.SENTINEL["int"][other]),
        (own_el, spec.tokens["P"], g.PRIOR_SENTINEL[own]),
        (other_el, spec.tokens["P"], g.PRIOR_SENTINEL[other]),
    ]
    r = spec.parse(rows, own)
    assert getattr(r, name) == _fallback_expected(spec, name, own, other)
    assert getattr(r, f"prior_{name}") == int(g.PRIOR_SENTINEL[own])


# 8: a consolidated filer's parent-only own-standard fact is not eligible.
@pytest.mark.parametrize(
    "spec,name,own,other", _params(lambda sp: _pairs(sp, g.STANDARDS, _jgaap_else_other))
)
def test_parent_only_own_fact_never_wins_for_a_consolidated_filer(spec, name, own, other):
    r = spec.parse([spec.row(name, other), spec.row(name, own, "999", suffix=g.NC)], own)
    assert _value(spec, name, r) == _fallback_expected(spec, name, own, other)


# 9: a parent-only filer reads the parent context, own standard first.
def _parent_only_pairs(spec):
    return [
        t
        for t in _pairs(spec, ("IFRS", "US GAAP"), _jgaap_else_other)
        if not g.rep(spec.tables(t[0]), t[1])[1] and not g.rep(spec.tables(t[0]), t[2])[1]
    ]


@pytest.mark.parametrize("spec,name,own,other", _params(_parent_only_pairs))
def test_parent_only_filer_reads_its_parent_context(spec, name, own, other):
    rows = [spec.row(name, own, suffix=g.NC), spec.row(name, other, suffix=g.NC)]
    r = spec.parse(rows, own, consolidated="false")
    assert _value(spec, name, r) == g.typed(spec.sentinel(name, own), spec.kind(name))
    assert r.source_contexts[name] == spec.period(name) + g.NC


# 10: a declared 'none' with another standard's fact present: None, also for
# a standard with no element of its own.
def _none_cells(spec):
    out = []
    for name in spec.fields():
        for std in g.STANDARDS:
            if fallback_for(spec.policy(name), std) == "none":
                out.append((name, std))
    return out


@pytest.mark.parametrize("spec,name,declared", _params(_none_cells))
def test_declared_none_withholds_every_other_standards_fact(spec, name, declared):
    others = [x for x in spec.policy(name).standards if x != declared]
    assert others or declared in spec.policy(name).standards
    r = spec.parse([spec.row(name, x) for x in others], declared)
    assert _value(spec, name, r) is None
    assert name not in r.source_elements and name not in r.source_contexts


# 11: a declared standard with no element of its own and the legacy
# fallback: the legacy order serves another standard's fact, and the source
# says so.
def _legacy_no_own_cells(spec):
    out = []
    for name in spec.fields():
        policy = spec.policy(name)
        for std in g.STANDARDS:
            if std not in policy.standards and fallback_for(policy, std) != "none":
                out.append((name, std))
    return out


@pytest.mark.parametrize("spec,name,declared", _params(_legacy_no_own_cells))
def test_legacy_fallback_without_an_own_element(spec, name, declared):
    stds = spec.policy(name).standards
    present = {x: g.rep(spec.tables(name), x) for x in stds}
    winner = g.first_reader(spec.tables(name), declared, present)
    r = spec.parse([spec.row(name, x) for x in stds], declared)
    expected = None if winner is None else spec.sentinel(name, winner)
    assert _value(spec, name, r) == g.typed(expected, spec.kind(name))
    if winner is not None:
        assert element_standard(r.source_elements[name]) == winner != declared


# 13: an Interim* semi-annual never reads a CurrentYTD/CurrentQuarter fact.
@pytest.mark.parametrize(
    "name,declared",
    [
        pytest.param(n, x, id=f"{n}-{x.replace(' ', '')}")
        for n in s._STANDARD_POLICY
        for x in s._STANDARD_POLICY[n].standards
    ],
)
def test_interim_document_ignores_the_q2r_contexts(name, declared):
    stds = SQ.policy(name).standards
    rows = [SQ.row(name, x) for x in stds] + [("jpcrp_cor:Marker", "InterimInstant", "1")]
    r = SQ.parse(rows, declared)
    assert _value(SQ, name, r) is None


# 14: J-GAAP controls for every declared 'none': closing the legacy table to
# IFRS / US GAAP moves no J-GAAP value, declared or undeclared.
def _control_cells(spec):
    return [
        (n,)
        for n in spec.fields()
        if any(fallback_for(spec.policy(n), x) == "none" for x in g.STANDARDS)
        and "Japan GAAP" in spec.policy(n).standards
    ]


@pytest.mark.parametrize("declared", ["Japan GAAP", None])
@pytest.mark.parametrize("spec,name", _params(_control_cells))
def test_jgaap_control_for_every_declared_none(spec, name, declared):
    r = spec.parse([spec.row(name, "Japan GAAP")], declared)
    assert _value(spec, name, r) == g.typed(spec.sentinel(name, "Japan GAAP"), spec.kind(name))


def test_owners_equity_undeclared_keeps_the_legacy_order():
    """Quarterly net_assets_owners has no J-GAAP element: closed to a
    declared J-GAAP filing, open to one that declares nothing."""
    row = QS.row("net_assets_owners", "IFRS")
    assert QS.parse([row], "Japan GAAP").net_assets_owners is None
    assert QS.parse([row], None).net_assets_owners == 222


# ---------------------------------------------------------------------------
# profit_before_tax and income_before_taxes on the annual report
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from edinet_tools.parsers.securities import parse_securities_report  # noqa: E402
from tests.conftest import load_securities_fixture  # noqa: E402

_ANNUAL = sorted(p.stem for p in (Path(__file__).parent / "fixtures" / "securities").glob("*.csv"))


@pytest.mark.parametrize("name", _ANNUAL)
def test_profit_before_tax_and_income_before_taxes(name):
    """income_before_taxes is unchanged (J-GAAP FS with its IFRS chain, no
    US-GAAP source). Where it came from the declared standard's own element it
    equals profit_before_tax; on a US-GAAP filing it is None while
    profit_before_tax reads the US-GAAP figure."""
    r = parse_securities_report(
        csv_files=load_securities_fixture(name), doc_id=name, doc_type_code="120"
    )
    src = r.source_elements
    if "income_before_taxes" in src and element_standard(src["income_before_taxes"]) == (
        r.accounting_standard
    ):
        assert r.profit_before_tax == r.income_before_taxes
    if r.accounting_standard == "US GAAP":
        assert r.income_before_taxes is None
    if r.profit_before_tax is not None:
        assert element_standard(src["profit_before_tax"]) == r.accounting_standard
