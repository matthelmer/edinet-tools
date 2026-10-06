"""Real source regressions from the 2026-10-02c saved EDINET corpus.

Complete, unmodified saved CSVs; original instance facts were independently
checked with ElementTree before choosing these assertions. Package SHA256:
S100Z1RU b84a78f5fad34d8547e479a6b6e5385ff89365e7c2fdc192b1ecdcd8af791821
S100Z492 960b3c90b7d294f7d35402421fecc12e84d88c176f8c4a773d0e1456351404b7
S100Z3XE 83482b31dfb8f99245e1ade7ea66c82814a6afe79713e25d57c8da1172a4ed7a
S100Z4ET a02394bf21d8d4f7364c6f70c0d966f0f339bfee4dcb898c698fcd2e0bd00cf2
"""
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools.parsers.securities import parse_securities_report
from edinet_tools.parsers.semi_annual import parse_semi_annual_report

FIXTURES = Path(__file__).parent / 'fixtures' / 'financial_context'
OWNERS = 'jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults'
OWNERS_FS = 'jppfs_cor:ProfitLossAttributableToOwnersOfParent'
REVENUE2 = 'jpcrp_cor:OperatingRevenue2SummaryOfBusinessResults'


def source(doc):
    with gzip.open(FIXTURES / f'{doc}.json.gz', 'rt') as f:
        return json.load(f)


def row(element, context, value, unit='JPY'):
    return {'要素ID': element, 'コンテキストID': context,
            '値': value, 'ユニットID': unit}


def synthetic(*facts, consolidated='false', standard='Japan GAAP'):
    return [{'filename': 'explicit-adversarial-control.csv', 'data': [
        row('jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',
            'FilingDateInstant', consolidated, None),
        row('jpdei_cor:AccountingStandardsDEI', 'FilingDateInstant', standard, None),
        *facts]}]


@pytest.mark.parametrize('doc,old_owners', [('S100Z1RU', '-38585000'), ('S100Z492', '628088000')])
def test_stopped_consolidating_does_not_mix_prior_group_owners_profit(doc, old_owners):
    files = source(doc)
    facts = [r for f in files for r in f['data']]
    assert any(r.get('要素ID') == OWNERS and r.get('コンテキストID') == 'Prior1YearDuration'
               and r.get('値') == old_owners for r in facts)
    report = parse_securities_report(csv_files=files)
    assert report.is_consolidated is False
    assert report.net_income_owners is None
    assert report.prior_net_income_owners is None
    assert report.prior_net_income_total is not None
    assert report.source_contexts['prior_net_income_total'] == 'Prior1YearDuration_NonConsolidatedMember'
    for evidence in (report.source_elements, report.source_contexts, report.units):
        assert 'prior_net_income_owners' not in evidence
    # The full historical group fact is still available in the source bag.
    assert any(f.element_id == OWNERS and f.context_id == 'Prior1YearDuration'
               and f.value == old_owners for f in report.raw_facts)


@pytest.mark.parametrize('period,field', [('CurrentYearDuration', 'net_income_owners'),
                                         ('Prior1YearDuration', 'prior_net_income_owners')])
def test_parent_only_owners_cannot_fall_back_to_bare_group_context(period, field):
    report = parse_securities_report(csv_files=synthetic(row(OWNERS, period, '100')))
    assert getattr(report, field) is None


def test_explicit_parent_fact_in_lower_tier_beats_ineligible_group_summary():
    report = parse_securities_report(csv_files=synthetic(
        row(OWNERS, 'Prior1YearDuration', '100'),
        row(OWNERS_FS, 'Prior1YearDuration_NonConsolidatedMember', '50')))
    assert report.prior_net_income_owners == 50
    assert report.source_elements['prior_net_income_owners'] == OWNERS_FS


def test_first_consolidated_year_does_not_borrow_prior_parent_profit():
    report = parse_securities_report(csv_files=synthetic(
        row(OWNERS, 'CurrentYearDuration', '100'),
        row(OWNERS_FS, 'Prior1YearDuration_NonConsolidatedMember', '50'), consolidated='true'))
    assert report.net_income_owners == 100
    assert report.prior_net_income_owners is None


def test_continuing_consolidated_current_and_prior_are_unchanged():
    report = parse_securities_report(csv_files=synthetic(
        row(OWNERS, 'CurrentYearDuration', '100'),
        row(OWNERS, 'Prior1YearDuration', '80'), consolidated='true'))
    assert (report.net_income_owners, report.prior_net_income_owners) == (100, 80)


def test_missing_scope_keeps_existing_owners_fallback():
    report = parse_securities_report(csv_files=synthetic(
        row(OWNERS, 'Prior1YearDuration', '80'), consolidated=None))
    assert report.is_consolidated is None
    assert report.prior_net_income_owners == 80


@pytest.mark.parametrize('doc,value', [('S100Z3XE', 413774000), ('S100Z4ET', 120934000)])
def test_half_year_operating_revenue2_summary(doc, value):
    report = parse_semi_annual_report(csv_files=source(doc))
    assert report.net_sales == value
    assert report.source_elements['net_sales'] == REVENUE2
    assert report.source_contexts['net_sales'] == 'InterimDuration_NonConsolidatedMember'
    assert report.units['net_sales'] == 'JPY'


@pytest.mark.parametrize('standard', ['IFRS', 'US GAAP'])
def test_new_half_year_revenue_alias_does_not_expand_other_standard_fallback(standard):
    report = parse_semi_annual_report(csv_files=synthetic(
        row(REVENUE2, 'InterimDuration_NonConsolidatedMember', '100'), standard=standard))
    assert report.net_sales is None


def test_new_half_year_alias_preserves_existing_revenue_priority_and_period():
    report = parse_semi_annual_report(csv_files=synthetic(
        row(REVENUE2, 'Prior1InterimDuration_NonConsolidatedMember', '800'),
        row(REVENUE2, 'InterimDuration_NonConsolidatedMember', '100'),
        row('jpcrp_cor:OperatingRevenue1SummaryOfBusinessResults',
            'InterimDuration_NonConsolidatedMember', '90')))
    assert report.net_sales == 90


@pytest.mark.parametrize('context,consolidated', [
    ('Prior1InterimDuration_NonConsolidatedMember', 'false'),
    ('InterimDuration_NonConsolidatedMember', 'true'),
])
def test_new_half_year_alias_rejects_wrong_period_or_parent_for_group(context, consolidated):
    report = parse_semi_annual_report(csv_files=synthetic(
        row(REVENUE2, context, '100'), consolidated=consolidated))
    assert report.net_sales is None
