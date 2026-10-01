"""Own-standard source selection in the annual parser.

The contract: when a usable fact for a field's concept exists in the
filing's declared accounting standard, at the eligible context and period,
another standard's fact cannot outrank it. A missing own-standard fact follows
the field's declared fallback. Ownership basis, consolidation scope and period
are preserved independently of the standard.

_STANDARD_POLICY (securities.py) declares, for every financial field, the
concept, the standards that tag it with a standard-specific element, and the
fallback. These tests hold the declaration to the tier tables.
"""

import dataclasses
from decimal import Decimal

import pytest

from edinet_tools.parsers import securities as sec
from edinet_tools.parsers.extraction import _tier_in_scope
from edinet_tools.parsers.securities import (
    _STANDARD_POLICY,
    SecuritiesReport,
    _element_standard,
    _field_elements,
    parse_securities_report,
)

STANDARDS = ("Japan GAAP", "IFRS", "US GAAP")
PER_SHARE = ("net_assets_per_share", "earnings_per_share", "equity_ratio", "roe")
IFRS_TRIO = ("ifrs_summary_basic_eps", "ifrs_summary_roe", "ifrs_summary_bps")


def _filled_fields():
    """Every SecuritiesReport field the tier tables or the per-share block fill."""
    fields = set(sec._DURATION_TIERS) | set(sec._INSTANT_TIERS)
    fields |= {f"prior_{f}" for f in sec._PRIOR_YEAR_FIELDS}
    return fields | set(PER_SHARE) | set(IFRS_TRIO)


def _policy_name(field):
    return field.removeprefix("prior_")


def test_every_financial_field_has_a_declared_policy():
    report_fields = {f.name for f in dataclasses.fields(SecuritiesReport)}
    filled = _filled_fields()
    declared = set(_STANDARD_POLICY)
    assert {_policy_name(f) for f in filled} == declared
    assert declared <= report_fields


def test_the_declared_standards_are_the_standards_of_the_field_elements():
    """A field declares exactly the standards its elements belong to; an
    element that is neither J-GAAP, IFRS nor US-GAAP by its taxonomy name must
    be declared neutral by name, never assumed."""
    for name, policy in _STANDARD_POLICY.items():
        found = set()
        for el in _field_elements(name):
            std = _element_standard(el)
            if std == "neutral":
                assert el in policy.neutral, (name, el)
            else:
                found.add(std)
        assert set(policy.standards) == found, name


def test_fallback_is_declared_where_standards_compete():
    for name, policy in _STANDARD_POLICY.items():
        assert policy.fallback in ("legacy", "none", "n/a"), name
        if len(policy.standards) >= 2:
            assert policy.fallback in ("legacy", "none"), name
        else:
            assert policy.fallback == "n/a", name
        assert policy.concept, name


def test_element_standard_reads_the_taxonomy_name():
    assert _element_standard("jpcrp_cor:NetSalesSummaryOfBusinessResults") == "Japan GAAP"
    assert _element_standard("jppfs_cor:NetSales") == "Japan GAAP"
    assert _element_standard("jpcrp_cor:RevenueIFRSSummaryOfBusinessResults") == "IFRS"
    assert _element_standard("jpigp_cor:RevenueIFRS") == "IFRS"
    assert _element_standard("jpcrp_cor:EquityToAssetRatioIFRSSummaryOfBusinessResults") == "IFRS"
    assert _element_standard("jpcrp_cor:RevenuesUSGAAPSummaryOfBusinessResults") == "US GAAP"
    assert _element_standard("SalesRevenuesIFRS") == "IFRS"
    assert _element_standard("jpcrp_cor:NumberOfEmployees") == "neutral"


# ---------------------------------------------------------------------------
# The competing-source grid
#
# For every field that more than one standard tags, a filing is built with a
# distinct sentinel per standard, and the winner is asserted by value: a wrong
# winner is visible by which sentinel came back.
# ---------------------------------------------------------------------------

CYD, PYD, CYI = "CurrentYearDuration", "Prior1YearDuration", "CurrentYearInstant"
NC = "_NonConsolidatedMember"
FILER_NS = "jpcrp030000-asr_E99999-000"
DURATION_PER_SHARE = ("earnings_per_share", "roe")
KINDS = {"net_assets_per_share": "dec", "earnings_per_share": "dec"}
KINDS.update({"equity_ratio": "pct", "roe": "pct"})
SENTINEL = {
    "int": {"Japan GAAP": "111", "IFRS": "222", "US GAAP": "333"},
    "dec": {"Japan GAAP": "11.1", "IFRS": "22.2", "US GAAP": "33.3"},
    "pct": {"Japan GAAP": "0.111", "IFRS": "0.222", "US GAAP": "0.333"},
}
PRIOR_SENTINEL = {"Japan GAAP": "444", "IFRS": "555", "US GAAP": "666"}


def _competing():
    return [n for n, p in _STANDARD_POLICY.items() if len(p.standards) >= 2]


def _period(name):
    if name.startswith("prior_"):
        return PYD
    if name in sec._DURATION_TIERS or name in DURATION_PER_SHARE:
        return CYD
    return CYI


def _tables(name):
    name = _policy_name(name)
    if name in sec._DURATION_TIERS:
        return (sec._DURATION_TIERS[name],)
    if name in sec._INSTANT_TIERS:
        return (sec._INSTANT_TIERS[name],)
    return sec._PER_SHARE_TABLES[name]


def _rep(name, standard):
    """The field's first element of `standard` (exact id; a suffix-only
    standard gets a filer-local id, with suffix=True)."""
    els = [e for e in _field_elements(name) if _element_standard(e) == standard]
    exact = [e for e in els if ":" in e]
    if exact:
        return exact[0], False
    return f"{FILER_NS}:{els[0]}", True


def _parsed(value, kind):
    if value is None:
        return None
    return int(value) if kind == "int" else Decimal(value)


def _reachable(name, standard, element):
    """True when a tier in scope for `standard` reads `element` (by id or,
    for a suffix tier, by its local name)."""
    local = element.rpartition(":")[2]
    for table in _tables(name):
        for tier in table:
            if not _tier_in_scope(tier, standard):
                continue
            if element in tier.elements or (tier.suffix_match and local in tier.elements):
                return True
    return False


def _no_standard_winner(name, present):
    """Today's order for a filing without a DEI standard: the first present
    element in the unscoped tiers (last-resort tiers last)."""
    tiers = [t for table in _tables(name) for t in table if _tier_in_scope(t, None)]
    ordered = [t for t in tiers if not t.last_resort] + [t for t in tiers if t.last_resort]
    for tier in ordered:
        for el in tier.elements:
            for std, (rep, suffix) in present.items():
                if rep == el or (tier.suffix_match and rep.rpartition(":")[2] == el):
                    return std
    return None


def _csv(rows, standard, consolidated="true"):
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
        for e, c, v in dei + rows
    ]
    return [{"filename": "grid.csv", "data": data}]


def _parse(rows, standard, consolidated="true"):
    return parse_securities_report(
        csv_files=_csv(rows, standard, consolidated), doc_id="GRID", doc_type_code="120"
    )


def _kind(name):
    return KINDS.get(_policy_name(name), "int")


def _cases(pairs):
    """[(field, own_standard, other_standard)] -> pytest ids."""
    return [pytest.param(*p, id="-".join(x.replace(" ", "") for x in p)) for p in pairs]


def _fields_with_prior():
    out = []
    for name in _competing():
        out.append(name)
        if name in sec._PRIOR_YEAR_FIELDS:
            out.append(f"prior_{name}")
    return out


def _pairs(own_standards, other_pick):
    pairs = []
    for name in _fields_with_prior():
        stds = _STANDARD_POLICY[_policy_name(name)].standards
        for own in own_standards:
            if own not in stds:
                continue
            other = other_pick(stds, own)
            if other is not None:
                pairs.append((name, own, other))
    return pairs


def _jgaap_else_other(stds, own):
    if own != "Japan GAAP" and "Japan GAAP" in stds:
        return "Japan GAAP"
    rest = [s for s in stds if s != own]
    return rest[0] if rest else None


def _rows_for(name, standards, period=None, sentinels=None, context_suffix=""):
    period = period or _period(name)
    kind = _kind(name)
    sentinels = sentinels or SENTINEL[kind]
    rows = []
    for std in standards:
        rep, _suffix = _rep(name, std)
        rows.append((rep, period + context_suffix, sentinels[std]))
    return rows


# 1-2: the declared standard's fact wins over another standard's fact.
@pytest.mark.parametrize(
    "name,own,other",
    _cases(_pairs(("IFRS", "US GAAP"), lambda s, o: "Japan GAAP" if "Japan GAAP" in s else None)),
)
def test_declared_standard_outranks_jgaap(name, own, other):
    r = _parse(_rows_for(name, (own, other)), own)
    assert getattr(r, name) == _parsed(SENTINEL[_kind(name)][own], _kind(name))


# 3: control — a J-GAAP filing tagging all three reads the J-GAAP fact.
@pytest.mark.parametrize(
    "name",
    [
        n
        for n in _fields_with_prior()
        if "Japan GAAP" in _STANDARD_POLICY[_policy_name(n)].standards
    ],
)
def test_jgaap_declared_reads_jgaap(name):
    stds = _STANDARD_POLICY[_policy_name(name)].standards
    r = _parse(_rows_for(name, stds), "Japan GAAP")
    assert getattr(r, name) == _parsed(SENTINEL[_kind(name)]["Japan GAAP"], _kind(name))


# 4: control — no DEI standard: today's order (a scoped tier never matches).
@pytest.mark.parametrize("name", _fields_with_prior())
def test_no_declared_standard_keeps_todays_order(name):
    stds = _STANDARD_POLICY[_policy_name(name)].standards
    present = {s: _rep(name, s) for s in stds}
    winner = _no_standard_winner(name, present)
    r = _parse(_rows_for(name, stds), None)
    expected = None if winner is None else SENTINEL[_kind(name)][winner]
    assert getattr(r, name) == _parsed(expected, _kind(name))


def _fallback_expected(name, own, other):
    policy = _STANDARD_POLICY[_policy_name(name)]
    if policy.fallback == "none":
        return None
    rep, _ = _rep(name, other)
    if not _reachable(name, own, rep):
        return None
    return _parsed(SENTINEL[_kind(name)][other], _kind(name))


# 5: the own-standard fact is missing: the declared fallback.
@pytest.mark.parametrize("name,own,other", _cases(_pairs(STANDARDS, _jgaap_else_other)))
def test_missing_own_fact_follows_the_declared_fallback(name, own, other):
    r = _parse(_rows_for(name, (other,)), own)
    assert getattr(r, name) == _fallback_expected(name, own, other)


# 6: a null marker is a missing fact; a genuine zero is a value.
@pytest.mark.parametrize("marker", ["－", "—"])
@pytest.mark.parametrize("name,own,other", _cases(_pairs(("IFRS", "US GAAP"), _jgaap_else_other)))
def test_own_null_marker_falls_through(name, own, other, marker):
    rows = _rows_for(name, (other,))
    rep, _ = _rep(name, own)
    rows.append((rep, _period(name), marker))
    r = _parse(rows, own)
    assert getattr(r, name) == _fallback_expected(name, own, other)


@pytest.mark.parametrize("name,own,other", _cases(_pairs(("IFRS", "US GAAP"), _jgaap_else_other)))
def test_own_zero_is_a_value_and_wins(name, own, other):
    rows = _rows_for(name, (other,))
    rep, _ = _rep(name, own)
    rows.append((rep, _period(name), "0"))
    r = _parse(rows, own)
    assert getattr(r, name) == _parsed("0", _kind(name))


# 7: each period chooses independently.
def _prior_pairs():
    return [
        (n, own, other)
        for n, own, other in _pairs(("IFRS", "US GAAP"), _jgaap_else_other)
        if n in sec._PRIOR_YEAR_FIELDS
    ]


@pytest.mark.parametrize("name,own,other", _cases(_prior_pairs()))
def test_current_own_prior_other(name, own, other):
    own_rep, _ = _rep(name, own)
    other_rep, _ = _rep(name, other)
    rows = [
        (own_rep, CYD, SENTINEL["int"][own]),
        (other_rep, CYD, SENTINEL["int"][other]),
        (other_rep, PYD, PRIOR_SENTINEL[other]),
    ]
    r = _parse(rows, own)
    assert getattr(r, name) == int(SENTINEL["int"][own])
    reach = _reachable(name, own, other_rep)
    assert getattr(r, f"prior_{name}") == (int(PRIOR_SENTINEL[other]) if reach else None)


@pytest.mark.parametrize("name,own,other", _cases(_prior_pairs()))
def test_prior_own_current_other(name, own, other):
    own_rep, _ = _rep(name, own)
    other_rep, _ = _rep(name, other)
    rows = [
        (other_rep, CYD, SENTINEL["int"][other]),
        (own_rep, PYD, PRIOR_SENTINEL[own]),
        (other_rep, PYD, PRIOR_SENTINEL[other]),
    ]
    r = _parse(rows, own)
    reach = _reachable(name, own, other_rep)
    assert getattr(r, name) == (int(SENTINEL["int"][other]) if reach else None)
    assert getattr(r, f"prior_{name}") == int(PRIOR_SENTINEL[own])


# 8: a consolidated filer's parent-only own-standard fact is not eligible.
@pytest.mark.parametrize("name,own,other", _cases(_pairs(STANDARDS, _jgaap_else_other)))
def test_parent_only_own_fact_never_wins_for_a_consolidated_filer(name, own, other):
    rows = _rows_for(name, (other,))
    rep, _ = _rep(name, own)
    rows.append((rep, _period(name) + NC, "999"))
    r = _parse(rows, own)
    assert getattr(r, name) == _fallback_expected(name, own, other)


# 9: a parent-only filer reads the parent context, own standard first.
def _parent_only_pairs():
    return [
        (n, own, other)
        for n, own, other in _pairs(("IFRS", "US GAAP"), _jgaap_else_other)
        if not _rep(n, own)[1] and not _rep(n, other)[1]
    ]


@pytest.mark.parametrize("name,own,other", _cases(_parent_only_pairs()))
def test_parent_only_filer_reads_its_parent_context(name, own, other):
    rows = _rows_for(name, (own, other), context_suffix=NC)
    r = _parse(rows, own, consolidated="false")
    assert getattr(r, name) == _parsed(SENTINEL[_kind(name)][own], _kind(name))


# 1-3 generalised: every ordered pair of the field's standards.
def _all_pairs():
    pairs = []
    for name in _fields_with_prior():
        stds = _STANDARD_POLICY[_policy_name(name)].standards
        pairs += [(name, own, other) for own in stds for other in stds if other != own]
    return pairs


@pytest.mark.parametrize("name,own,other", _cases(_all_pairs()))
def test_declared_standard_outranks_each_other_standard(name, own, other):
    r = _parse(_rows_for(name, (own, other)), own)
    assert getattr(r, name) == _parsed(SENTINEL[_kind(name)][own], _kind(name))


# ---------------------------------------------------------------------------
# Provenance: source_elements names the element each field was read from
# ---------------------------------------------------------------------------

NI_JG = "jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults"
NI_IFRS = "jpcrp_cor:ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults"
EPS_JG = "jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults"
EPS_IFRS = "jpcrp_cor:BasicEarningsLossPerShareIFRSSummaryOfBusinessResults"


def test_source_elements_name_the_winning_element():
    rows = [
        (NI_JG, CYD, "16729000000"),
        (NI_IFRS, CYD, "30430000000"),
        (EPS_JG, CYD, "81.05"),
        (EPS_IFRS, CYD, "147.43"),
    ]
    r = _parse(rows, "IFRS")
    assert r.net_income_owners == 30_430_000_000
    assert r.earnings_per_share == Decimal("147.43")
    assert r.source_elements["net_income_owners"] == NI_IFRS
    assert r.source_elements["earnings_per_share"] == EPS_IFRS
    # a field that resolved to nothing has no source
    assert "net_sales" not in r.source_elements


def test_source_elements_show_a_fallback():
    """An IFRS filing with only the J-GAAP fact: the value is the legacy
    fallback, and the source says so."""
    r = _parse([(NI_JG, CYD, "16729000000")], "IFRS")
    assert r.net_income_owners == 16_729_000_000
    assert _element_standard(r.source_elements["net_income_owners"]) == "Japan GAAP"


def test_source_elements_cover_prior_year_reads():
    rows = [(NI_IFRS, PYD, "1"), (NI_JG, PYD, "2")]
    r = _parse(rows, "IFRS")
    assert r.prior_net_income_owners == 1
    assert r.source_elements["prior_net_income_owners"] == NI_IFRS


def test_empty_filing_has_empty_source_elements():
    r = parse_securities_report(csv_files=[], doc_id="X", doc_type_code="120")
    assert r.source_elements == {}


def test_none_fallback_leaves_the_field_empty():
    """The 'none' fallback: when the declared standard's fact is missing,
    another standard's fact is not served."""
    from edinet_tools.parsers.extraction import resolve_tiers
    from edinet_tools.parsers.securities import _FieldPolicy, _with_own_standard_first

    legacy = sec._DURATION_LEGACY["net_income_owners"]
    none = _FieldPolicy("test", ("Japan GAAP", "IFRS", "US GAAP"), "none")
    tiers = _with_own_standard_first(legacy, none)
    cf = _csv([(NI_JG, CYD, "5")], "IFRS")
    kw = dict(period=CYD, is_consolidated=True)
    assert resolve_tiers(cf, tiers, standard="IFRS", **kw) is None
    assert resolve_tiers(cf, tiers, standard="Japan GAAP", **kw).value == 5
    # no declared standard: today's order, untouched
    assert resolve_tiers(cf, tiers, standard=None, **kw).value == 5


# ---------------------------------------------------------------------------
# Public surface: the policy machinery is private; source_elements is public
# ---------------------------------------------------------------------------


def test_policy_machinery_is_private():
    for name in ("STANDARD_POLICY", "FieldPolicy", "element_standard", "field_elements"):
        assert not hasattr(sec, name), name
        assert hasattr(sec, "_" + name), name


def test_source_elements_is_typed_str_to_str():
    (f,) = [f for f in dataclasses.fields(SecuritiesReport) if f.name == "source_elements"]
    assert f.type in (dict[str, str], "dict[str, str]")


def test_source_elements_include_the_ifrs_trio():
    bps = "jpcrp_cor:EquityToAssetRatioIFRSSummaryOfBusinessResults"
    roe = "jpcrp_cor:RateOfReturnOnEquityIFRSSummaryOfBusinessResults"
    rows = [(EPS_IFRS, CYD, "147.43"), (roe, CYD, "0.1"), (bps, CYI, "1460")]
    r = _parse(rows, "IFRS")
    assert r.source_elements["ifrs_summary_basic_eps"] == EPS_IFRS
    assert r.source_elements["ifrs_summary_roe"] == roe
    assert r.source_elements["ifrs_summary_bps"] == bps
    # no value, no source
    r = _parse([(EPS_IFRS, CYD, "－")], "IFRS")
    assert "ifrs_summary_basic_eps" not in r.source_elements
