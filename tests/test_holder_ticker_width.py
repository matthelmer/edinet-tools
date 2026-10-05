"""Normalize the display ticker while preserving the filed issuer code."""
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.large_holding import parse_large_holding

ELEMENT = 'jplvh_cor:SecurityCodeOfIssuer'
FIXTURES = Path(__file__).parent / 'fixtures' / 'holder_scope'


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_original_fullwidth_issuer_code_retained_but_ticker_resolves(source):
    if source == 'csv':
        with gzip.open(FIXTURES / 'S100N8JB.json.gz', 'rt') as handle:
            report = parse_large_holding(csv_files=json.load(handle),
                                         doc_id='S100N8JB', doc_type_code='350')
    else:
        report = parse_xbrl((FIXTURES / 'S100N8JB.zip').read_bytes(),
                            '350', source=source)
    assert report.target_ticker == '6146.T'
    assert any(f.element_id == ELEMENT and f.value == '６１４６'
               for f in report.raw_facts)


@pytest.mark.parametrize('filed, expected', [
    ('６１４６', '6146.T'), ('６１４６０', '6146.T'),
    ('６1４6', '6146.T'), (' 61460 ', '6146.T'),
    ('285A0', '285A.T'), ('285A', '285A.T'),
])
def test_width_normalization_preserves_existing_ticker_shapes(filed, expected):
    report = parse_large_holding(csv_files=[{'filename': 'issuer.csv', 'data': [
        {'要素ID': ELEMENT, 'コンテキストID': 'FilingDateInstant', '値': filed}
    ]}], doc_id='WIDTH', doc_type_code='350')
    assert report.target_ticker == expected
