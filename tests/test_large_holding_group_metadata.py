"""Group ownership metadata must describe the same scope as group holdings."""
from datetime import date
import pytest

from edinet_tools.parsers.large_holding import ELEMENT_MAP
from tests.test_large_holding_primary_scope import saved, parse


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_group_denominator_does_not_borrow_members_value(source):
    report = saved('S100OAHP', source)
    assert report.shares_outstanding == 6936100
    assert report.shares_held == 728700
    assert any(f.element_id == ELEMENT_MAP['shares_outstanding'] and
               f.value == '6967500' and 'Holder1Member' in f.context_id
               for f in report.raw_facts)


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_group_base_date_does_not_borrow_members_date(source):
    report = saved('S100Z1LZ', source, '360')
    assert report.base_date == date(2026, 8, 26)
    assert report.shares_held == 2512000
    assert any(f.element_id == ELEMENT_MAP['base_date'] and
               f.value == '2026-08-28' and 'Holder1Member' in f.context_id
               for f in report.raw_facts)


@pytest.mark.parametrize('field,value', [('shares_outstanding', '1000'), ('base_date', '2026-08-26')])
def test_joint_filing_without_group_metadata_is_unknown(field, value):
    rows = [('jplvh_cor:Name', 'FilingDateInstant_FilerLargeVolumeHolder1Member', 'lead'),
            ('jplvh_cor:Name', 'FilingDateInstant_FilerLargeVolumeHolder2Member', 'other')]
    rows += [(ELEMENT_MAP[field], context, value) for _,context,_ in rows]
    assert getattr(parse(rows), field) is None


@pytest.mark.parametrize('field,value,expected', [
    ('shares_outstanding', '1000', 1000), ('base_date', '2026-08-26', date(2026, 8, 26)),
])
@pytest.mark.parametrize('context', ['FilingDateInstant', 'FilingDateInstant_JointHolder3Member'])
def test_single_holder_or_axisless_filing_keeps_its_metadata(field, value, expected, context):
    assert getattr(parse([(ELEMENT_MAP[field], context, value)]), field) == expected


@pytest.mark.parametrize('field,value', [('shares_outstanding', '1000'), ('base_date', '2026-08-26')])
@pytest.mark.parametrize('empty', [None, '', '－'])
def test_empty_group_fact_prevents_fallback_to_holder(field, value, empty):
    rows = [(ELEMENT_MAP[field], 'FilingDateInstant_FilerLargeVolumeHolder1Member', value),
            (ELEMENT_MAP[field], 'FilingDateInstant', empty)]
    assert getattr(parse(rows), field) is None


def test_missing_group_denominator_is_not_inferred_from_zero_members():
    rows = [(ELEMENT_MAP['shares_outstanding'], 'FilingDateInstant_FilerLargeVolumeHolder1Member', '0'),
            (ELEMENT_MAP['shares_outstanding'], 'FilingDateInstant_FilerLargeVolumeHolder2Member', '0')]
    assert parse(rows).shares_outstanding is None
