"""Real filing regressions: unknown context members must not imply completeness."""
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools.parsers.segments import parse_segments_from_csv

FIXTURES = Path(__file__).parent / 'fixtures' / 'segments'


def filing(doc_id):
    with gzip.open(FIXTURES / f'{doc_id}.json.gz', 'rt') as f:
        return json.load(f)


@pytest.mark.parametrize('doc_id,member,revenue', [
    ('S100Z468', 'ICTSolution', '6681954000'),
    ('S100Z46T', 'INSHOKUJIGYOU', '1842761000'),
    ('S100Z461', 'MarketingBusiness', '17930446000'),
    ('S100Z4HA', 'EnergyBusiness', '9576240000'),
])
def test_real_missing_segment_requires_incomplete_flag(doc_id, member, revenue):
    evidence = filing(doc_id)
    contexts = {cid for cid, c in evidence['segment_context_witness'].items()
                if c['member'] == member and c['period'] == 'CurrentYearDuration'}
    # Original instance context definitions put the missing member on the segment
    # axis; original CSV provides the amount. Expected values are not library output.
    assert contexts
    assert any(r['コンテキストID'] in contexts
               and r['要素ID'].endswith(':RevenuesFromExternalCustomers')
               and r['値'] == revenue
               for f in evidence['csv_files'] for r in f['data'])
    rows, text_only, incomplete = parse_segments_from_csv(evidence['csv_files'])
    assert not text_only
    assert member not in {s.segment_name for s in rows}
    assert incomplete, 'a total or a different segment does not prove full coverage'


def test_total_alone_does_not_prove_individual_segment_coverage():
    rows, _, incomplete = parse_segments_from_csv([{'data': [{
        '要素ID': 'jpcrp_cor:RevenuesFromExternalCustomers',
        'コンテキストID': 'CurrentYearDuration_ReportableSegmentsMember', '値': '100',
    }]}])
    assert len(rows) == 1 and rows[0].axis_family == 'TotalReconciling'
    assert incomplete


def test_unknown_axis_is_flagged_without_inventing_segment():
    rows, _, incomplete = parse_segments_from_csv([{'data': [
        {'要素ID': 'jpcrp_cor:NumberOfEmployees', '値': '10',
         'コンテキストID': 'CurrentYearInstant_FactoryReportableSegmentsMember'},
        {'要素ID': 'jpcrp_cor:NumberOfEmployees', '値': '10',
         'コンテキストID': 'CurrentYearInstant_UnknownGeographicAreaMember'},
    ]}])
    assert {s.segment_name for s in rows} == {'FactoryReportableSegments'}
    assert incomplete  # CSV cannot tell whether this is geography or a segment.


def test_unrelated_unknown_member_does_not_create_coverage_warning():
    rows, _, incomplete = parse_segments_from_csv([{'data': [
        {'要素ID': 'jpcrp_cor:RevenuesFromExternalCustomers', '値': '100',
         'コンテキストID': 'CurrentYearDuration_FactoryReportableSegmentsMember'},
        {'要素ID': 'jpcrp_cor:NumberOfSharesHeld', '値': '10',
         'コンテキストID': 'CurrentYearInstant_No1MajorShareholdersMember'},
    ]}])
    assert len(rows) == 1
    assert not incomplete
