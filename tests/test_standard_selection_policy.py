"""Own-standard source selection in the annual parser.

The contract: when a usable fact for a field's concept exists in the
filing's declared accounting standard, at the eligible context and period,
another standard's fact cannot outrank it. A missing own-standard fact follows
the field's declared fallback. Ownership basis, consolidation scope and period
are preserved independently of the standard.

STANDARD_POLICY (securities.py) declares, for every financial field, the
concept, the standards that tag it with a standard-specific element, and the
fallback. These tests hold the declaration to the tier tables.
"""

import dataclasses

from edinet_tools.parsers import securities as sec
from edinet_tools.parsers.securities import (
    STANDARD_POLICY,
    SecuritiesReport,
    element_standard,
    field_elements,
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
    declared = set(STANDARD_POLICY)
    assert {_policy_name(f) for f in filled} == declared
    assert declared <= report_fields


def test_the_declared_standards_are_the_standards_of_the_field_elements():
    """A field declares exactly the standards its elements belong to; an
    element that is neither J-GAAP, IFRS nor US-GAAP by its taxonomy name must
    be declared neutral by name, never assumed."""
    for name, policy in STANDARD_POLICY.items():
        found = set()
        for el in field_elements(name):
            std = element_standard(el)
            if std == "neutral":
                assert el in policy.neutral, (name, el)
            else:
                found.add(std)
        assert set(policy.standards) == found, name


def test_fallback_is_declared_where_standards_compete():
    for name, policy in STANDARD_POLICY.items():
        assert policy.fallback in ("legacy", "none", "n/a"), name
        if len(policy.standards) >= 2:
            assert policy.fallback in ("legacy", "none"), name
        else:
            assert policy.fallback == "n/a", name
        assert policy.concept, name


def test_element_standard_reads_the_taxonomy_name():
    assert element_standard("jpcrp_cor:NetSalesSummaryOfBusinessResults") == "Japan GAAP"
    assert element_standard("jppfs_cor:NetSales") == "Japan GAAP"
    assert element_standard("jpcrp_cor:RevenueIFRSSummaryOfBusinessResults") == "IFRS"
    assert element_standard("jpigp_cor:RevenueIFRS") == "IFRS"
    assert element_standard("jpcrp_cor:EquityToAssetRatioIFRSSummaryOfBusinessResults") == "IFRS"
    assert element_standard("jpcrp_cor:RevenuesUSGAAPSummaryOfBusinessResults") == "US GAAP"
    assert element_standard("SalesRevenuesIFRS") == "IFRS"
    assert element_standard("jpcrp_cor:NumberOfEmployees") == "neutral"
