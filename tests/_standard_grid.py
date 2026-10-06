"""Builders for the competing-source grid, shared by the parsers' policy tests.

The annual grid (test_standard_selection_policy.py) introduced them; this
module holds the same builders over any parser's tables, so the quarterly and
semi-annual grids assert by the same rules: a filing is built with a distinct
sentinel per standard, and the winner is read off by which sentinel came back.
"""

from decimal import Decimal

import pytest

from edinet_tools.parsers._standard_policy import element_standard, table_elements
from edinet_tools.parsers.extraction import _tier_in_scope

STANDARDS = ("Japan GAAP", "IFRS", "US GAAP")
NC = "_NonConsolidatedMember"
FILER_NS = "jpcrp030000-asr_E99999-000"
SENTINEL = {
    "int": {"Japan GAAP": "111", "IFRS": "222", "US GAAP": "333"},
    "dec": {"Japan GAAP": "11.1", "IFRS": "22.2", "US GAAP": "33.3"},
    "pct": {"Japan GAAP": "0.111", "IFRS": "0.222", "US GAAP": "0.333"},
}
PRIOR_SENTINEL = {"Japan GAAP": "444", "IFRS": "555", "US GAAP": "666"}


def csv_files(rows, standard, consolidated="true"):
    """A filing: DEI rows (the declared standard unless None) plus `rows`,
    each (element, context, value)."""
    dei = [("jpdei_cor:EDINETCodeDEI", "FilingDateInstant", "E99999")]
    if standard is not None:
        dei.append(("jpdei_cor:AccountingStandardsDEI", "FilingDateInstant", standard))
    dei.append(
        (
            "jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI",
            "FilingDateInstant",
            consolidated,
        )
    )
    data = [
        {
            "要素ID": e,
            "項目名": "",
            "コンテキストID": c,
            "相対年度": "",
            "連結・個別": "",
            "期間・時点": "",
            "ユニットID": "JPY",
            "単位": "",
            "値": v,
        }
        for e, c, v in dei + list(rows)
    ]
    return [{"filename": "grid.csv", "data": data}]


def rep(tables, standard):
    """The first element of `standard` the tables read (exact id; a
    suffix-only standard gets a filer-local id, with suffix=True)."""
    els = [e for e in table_elements(*tables) if element_standard(e) == standard]
    exact = [e for e in els if ":" in e]
    if exact:
        return exact[0], False
    return f"{FILER_NS}:{els[0]}", True


def reads(tables, standard, element):
    """True when a tier in scope for `standard` reads `element` (by id or,
    for a suffix tier, by its local name)."""
    local = element.rpartition(":")[2]
    for table in tables:
        for tier in table:
            if not _tier_in_scope(tier, standard):
                continue
            if element in tier.elements or (tier.suffix_match and local in tier.elements):
                return True
    return False


def first_reader(tables, standard, present):
    """The standard whose fact the tables read first for a filing declaring
    `standard`, among `present` {standard: (element, suffix)}: legacy order,
    last-resort tiers last."""
    tiers = [t for table in tables for t in table if _tier_in_scope(t, standard)]
    ordered = [t for t in tiers if not t.last_resort] + [t for t in tiers if t.last_resort]
    for tier in ordered:
        for el in tier.elements:
            for std, (element, _suffix) in present.items():
                if element == el or (tier.suffix_match and element.rpartition(":")[2] == el):
                    return std
    return None


def typed(value, kind):
    if value is None:
        return None
    return int(value) if kind == "int" else Decimal(value)


def cases(triples):
    """[(field, standard, standard), ...] -> pytest params with readable ids."""
    return [pytest.param(*t, id="-".join(str(x).replace(" ", "") for x in t)) for t in triples]
