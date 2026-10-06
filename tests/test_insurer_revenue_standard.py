"""Tokio Marine's first IFRS year must not borrow J-GAAP comparison revenue.

Original package S100YLS8 SHA256:
fb29257edb281d5bc5145919df2a02a9590cc9ac0532f1da026b56c838a90807.
Complete saved CSVs and original package fetched in Fable's financial-sector
review, 2026-10-05; facts independently checked in the original XML.
"""
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.securities import parse_securities_report
from edinet_tools.parsers.semi_annual import parse_semi_annual_report

ROOT = Path(__file__).parent / 'fixtures'
ORDINARY_REVENUE = 'jpcrp_cor:OrdinaryIncomeSummaryOfBusinessResults'


def csv(doc):
    return json.loads(gzip.decompress((ROOT / 'financial_context' / f'{doc}.json.gz').read_bytes()))


@pytest.mark.parametrize('source', ['csv', 'instance', 'xbrl'])
def test_tokio_marine_keeps_ifrs_profit_without_jgaap_revenue(source):
    if source == 'csv':
        report = parse_securities_report(csv_files=csv('S100YLS8'))
    else:
        report = parse_xbrl((ROOT / 'xbrl' / 'S100YLS8_type1.zip').read_bytes(), '120', source=source)
    assert report.accounting_standard == 'IFRS'
    assert report.net_income_owners == 531255000000
    assert report.net_sales is None
    assert report.prior_net_sales is None
    for mapping in (report.source_elements, report.source_contexts, report.units):
        assert 'net_sales' not in mapping and 'prior_net_sales' not in mapping
    # Neither the rejected J-GAAP comparison nor the unmapped IFRS insurance
    # revenue is lost. They are different concepts; no inferred substitution.
    for period,ordinary,insurance in [('CurrentYearDuration','8872277000000','7693560000000'),
                                      ('Prior1YearDuration','8440114000000','7396221000000')]:
        assert any(f.element_id == ORDINARY_REVENUE and f.context_id == period
                   and f.value.strip() == ordinary for f in report.raw_facts)
        assert any(f.element_id.endswith(':InsuranceRevenueIFRS') and f.context_id == period
                   and f.value.strip() == insurance for f in report.raw_facts)


@pytest.mark.parametrize('doc,current,prior', [
    ('S100YF8Y',9085438000000,9030374000000),  # Mizuho
    ('S100YDSE',445037000000,362179000000),    # Chiba
    ('S100YC1N',220025000000,214408000000),    # Seven
    ('S100YCRO',242314000000,231460000000),    # Aozora
])
def test_jgaap_banks_keep_current_and_prior_ordinary_revenue(doc,current,prior):
    report = parse_securities_report(csv_files=csv(doc))
    assert report.accounting_standard == 'Japan GAAP'
    assert (report.net_sales,report.prior_net_sales) == (current,prior)
    assert report.source_elements['net_sales'] == ORDINARY_REVENUE
    assert report.source_elements['prior_net_sales'] == ORDINARY_REVENUE


@pytest.mark.parametrize('standard', ['IFRS','US GAAP'])
@pytest.mark.parametrize('interim', [False,True])
def test_comparison_revenue_gate_preserves_own_standard_fallback(standard,interim):
    period = 'InterimDuration' if interim else 'CurrentYearDuration'
    own = ('RevenueIFRS' if standard == 'IFRS' else 'RevenuesUSGAAP') + 'SummaryOfBusinessResults'
    rows = [
        {'要素ID':'jpdei_cor:AccountingStandardsDEI','コンテキストID':'FilingDateInstant','値':standard},
        {'要素ID':'jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',
         'コンテキストID':'FilingDateInstant','値':'true'},
        {'要素ID':ORDINARY_REVENUE,'コンテキストID':period,'値':'100','ユニットID':'JPY'},
    ]
    parse = parse_semi_annual_report if interim else parse_securities_report
    assert parse(csv_files=[{'filename':'synthetic.csv','data':rows}]).net_sales is None
    rows.append({'要素ID':'jpcrp_cor:'+own,'コンテキストID':period,'値':'80','ユニットID':'JPY'})
    report = parse(csv_files=[{'filename':'synthetic.csv','data':rows}])
    assert report.net_sales == 80
    assert report.source_elements['net_sales'] == 'jpcrp_cor:'+own
