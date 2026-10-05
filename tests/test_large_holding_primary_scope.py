"""A missing lead-holder fact must not become a co-holder's statement."""
from pathlib import Path
import gzip
import json

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.large_holding import parse_large_holding, ELEMENT_MAP

FIXTURES = Path(__file__).parent / 'fixtures' / 'holder_scope'
FIELDS = ('filer_business', 'purpose', 'acquisition_fund_own',
          'acquisition_fund_borrowing', 'acquisition_fund_other', 'acquisition_fund_total')


def saved(doc, source):
    if source == 'csv':
        with gzip.open(FIXTURES / (doc + '.json.gz'), 'rt') as handle:
            files = json.load(handle)
        return parse_large_holding(csv_files=files, doc_id=doc, doc_type_code='350')
    return parse_xbrl((FIXTURES / (doc + '.zip')).read_bytes(), '350', source=source)


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_individual_does_not_borrow_corporate_coholders_business(source):
    report = saved('S100MJGI', source)
    assert '近藤' in report.filer_name
    assert report.filer_business is None
    assert any(f.element_id == ELEMENT_MAP['filer_business'] and
               '株式会社' not in f.value and '株式その他資産' in f.value
               for f in report.raw_facts)


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_lead_company_does_not_borrow_third_holders_funding(source):
    report = saved('S100MJJC', source)
    assert 'ラテール・エンタプライズ' in report.filer_name
    for field in FIELDS[2:]:
        assert getattr(report, field) is None
    assert any(f.element_id == ELEMENT_MAP['acquisition_fund_total'] and
               f.value == '232989000' and 'Holder3Member' in f.context_id
               for f in report.raw_facts)


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_lead_holder_does_not_borrow_relatives_purpose(source):
    report = saved('S100MKVJ', source)
    assert '譲冶' in report.filer_name
    assert report.purpose is None
    assert report.joint_holders[0].purpose is None
    assert '三女' in report.joint_holders[1].purpose


def parse(rows):
    return parse_large_holding(csv_files=[{'filename': 'scope.csv', 'data': [
        {'要素ID': element, 'コンテキストID': context, '値': value}
        for element, context, value in rows
    ]}], doc_id='SCOPE', doc_type_code='350')


@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('axis', ['FilerLargeVolumeHolder', 'JointHolder'])
def test_missing_fact_does_not_change_which_holder_is_primary(field, axis):
    # Gapped holder indices are legitimate. Lead identity comes from the
    # whole filing, not the lowest holder who happened to tag this field.
    lead = 'FilingDateInstant_' + axis + '2Member'
    other = 'FilingDateInstant_' + axis + '4Member'
    rows = [('jplvh_cor:Name', lead, 'lead'),
            ('jplvh_cor:Name', other, 'other'),
            (ELEMENT_MAP[field], other, '123')]
    assert getattr(parse(rows), field) is None


@pytest.mark.parametrize('field', FIELDS)
def test_legacy_filing_without_holder_axes_retains_its_own_value(field):
    report = parse([(ELEMENT_MAP[field], 'FilingDateInstant', '123')])
    assert getattr(report, field) == (123 if field.startswith('acquisition') else '123')


@pytest.mark.parametrize('value', [None, '', '－', '-'])
@pytest.mark.parametrize('field', ['filer_business', 'purpose'])
def test_filed_empty_or_dash_lead_value_is_not_replaced(field, value):
    report = parse([
        ('jplvh_cor:Name', 'FilingDateInstant_FilerLargeVolumeHolder1Member', 'lead'),
        (ELEMENT_MAP[field], 'FilingDateInstant_FilerLargeVolumeHolder2Member', 'other'),
        (ELEMENT_MAP[field], 'FilingDateInstant_FilerLargeVolumeHolder1Member', value),
    ])
    assert getattr(report, field) == value
