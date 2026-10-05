"""Commercial-paper liabilities: originals fetched in the Oct-5 sector review.

Package SHA256, complete original packages and saved CSV facts:
S100YBXA 114a57fc53361babcc646d6b39c100b24272fe847d02cce41dc9dfcf9b4de140
S100YCMP a0afe80905f6db3109d681fea7e7f814c3d7d79adea748a5fb40736eeefedf0e
S100YF8Y 97679885ac4951f58b4cd4c7b7d902fee910d519b8e1ebc28053f6676ccf1b17
S100YG5L 0f9523f417db49144b970c53f4cbb326c9e317de819ffcab1138999527431551
S100YIBH aea9950b19486a66170c2fe8c59276afbb91611b8e28be4ccdfe2f70d3194b68
S100YNCJ c713d1813187757572709f30b65322b8e772b29e99dd2eaad6b4ebab36b754c9
S100YC6Z 3c8a30983449f56004d69ce5fb10566b86d245cee51f20d2e1ab2da8416f6804
"""
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.securities import parse_securities_report

ROOT = Path(__file__).parent / 'fixtures'
ELEMENT = 'jppfs_cor:CommercialPapersLiabilities'
OLD_ELEMENT = 'jppfs_cor:CommercialPaper'


def csv(doc):
    return json.loads(gzip.decompress((ROOT/'financial_context'/f'{doc}.json.gz').read_bytes()))


@pytest.mark.parametrize('source', ['csv','instance','xbrl'])
@pytest.mark.parametrize('doc,value', [('S100YBXA',84938000000),
                                     ('S100YCMP',396500000000),
                                     ('S100YF8Y',1921799000000)])
def test_current_consolidated_commercial_paper_from_original(doc,value,source):
    if source == 'csv':
        r = parse_securities_report(csv_files=csv(doc))
    else:
        r = parse_xbrl((ROOT/'xbrl'/f'{doc}_type1.zip').read_bytes(),'120',source=source)
    assert r.accounting_standard == 'Japan GAAP' and r.is_consolidated is True
    assert r.commercial_paper == value
    assert r.source_elements['commercial_paper'] == ELEMENT
    assert r.source_contexts['commercial_paper'] == 'CurrentYearInstant'
    assert r.units['commercial_paper'] == 'JPY'


@pytest.mark.parametrize('doc', ['S100YG5L','S100YIBH'])
def test_usgaap_parent_commercial_paper_is_not_group_debt(doc):
    r = parse_securities_report(csv_files=csv(doc))
    assert r.accounting_standard == 'US GAAP' and r.is_consolidated is True
    assert r.commercial_paper is None
    assert 'commercial_paper' not in r.source_elements
    assert any(f.element_id == ELEMENT and f.context_id.endswith('_NonConsolidatedMember')
               for f in r.raw_facts)


@pytest.mark.parametrize('doc,current,prior', [('S100YNCJ',6436026000000,5949509000000),
                                              ('S100YC6Z',5601496000000,5286210000000)])
def test_msad_and_sompo_keep_ifrs_statement_revenue(doc,current,prior):
    r = parse_securities_report(csv_files=csv(doc))
    assert r.accounting_standard == 'IFRS'
    assert (r.net_sales,r.prior_net_sales) == (current,prior)
    assert r.source_elements['net_sales'] == 'jpigp_cor:Revenue2IFRS'
    assert r.source_elements['prior_net_sales'] == 'jpigp_cor:Revenue2IFRS'


def synthetic(facts,standard='Japan GAAP',consolidated='true'):
    rows = [
        {'要素ID':'jpdei_cor:AccountingStandardsDEI','コンテキストID':'FilingDateInstant','値':standard},
        {'要素ID':'jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',
         'コンテキストID':'FilingDateInstant','値':consolidated},
    ] + [{'要素ID':e,'コンテキストID':c,'値':v,'ユニットID':'JPY'} for e,c,v in facts]
    return parse_securities_report(csv_files=[{'filename':'synthetic.csv','data':rows}])


@pytest.mark.parametrize('current,expected', [('0',0),('－',None),(None,None)])
def test_zero_is_a_value_and_current_nil_never_uses_prior(current,expected):
    r = synthetic([(ELEMENT,'Prior1YearInstant','800'),(ELEMENT,'CurrentYearInstant',current)])
    assert r.commercial_paper == expected
    assert ('commercial_paper' in r.source_elements) == (expected is not None)


def test_consolidated_cannot_borrow_parent_but_parent_filer_can_read_it():
    facts = [(ELEMENT,'CurrentYearInstant_NonConsolidatedMember','500')]
    assert synthetic(facts).commercial_paper is None
    assert synthetic(facts,consolidated='false').commercial_paper == 500


@pytest.mark.parametrize('standard', ['IFRS','US GAAP'])
def test_new_jgaap_alias_cannot_fill_other_accounting_standard(standard):
    assert synthetic([(ELEMENT,'CurrentYearInstant','500')],standard=standard).commercial_paper is None


def test_existing_alias_precedence_and_nil_fallback():
    facts = [(OLD_ELEMENT,'CurrentYearInstant','10'),(ELEMENT,'CurrentYearInstant','20')]
    r = synthetic(facts)
    assert r.commercial_paper == 10 and r.source_elements['commercial_paper'] == OLD_ELEMENT
    facts[0] = (OLD_ELEMENT,'CurrentYearInstant','－')
    r = synthetic(facts)
    assert r.commercial_paper == 20 and r.source_elements['commercial_paper'] == ELEMENT
