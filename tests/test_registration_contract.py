"""Cover labels verified directly in original S100TZNV and S100UXDQ."""
from pathlib import Path
import gzip
import json
import pytest
from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.issuance_supplementary import parse_issuance_supplementary
from edinet_tools.parsers.extraordinary import parse_extraordinary_report

FIXTURES = Path(__file__).parent / 'fixtures/xbrl'

def report(doc, code, source, parser):
    if source == 'csv':
        return parser(csv_files=json.loads(gzip.decompress((FIXTURES / (doc+'.json.gz')).read_bytes())), doc_id=doc, doc_type_code=code)
    return parse_xbrl((FIXTURES / (doc+'.zip')).read_bytes(), code, doc_id=doc, source=source)

@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_resona_supplement_keeps_ceiling_balance_and_offering_distinct(source):
    parsed = report('S100TZNV', '100', source, parse_issuance_supplementary)
    assert parsed.planned_amount == '発行予定額　300,000百万円'
    assert parsed.remaining_balance == '-円'
    assert parsed.offering_amount_text == '10,000百万円'
    assert '300,000百万円' in parsed.remaining_amount_text
    assert parsed.offering_amount_text != parsed.planned_amount
    assert parsed.remaining_amount_text != parsed.remaining_balance

@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_corporate_extraordinary_contact_from_original(source):
    parsed = report('S100UXDQ', '180', source, parse_extraordinary_report)
    assert parsed.contact_address == '東京都港区北青山２丁目５番１号'

@pytest.mark.parametrize('namespace', ['jpcrp-esr_cor', 'jpsps-esr_cor'])
def test_original_contact_element_remains_supported(namespace):
    rows=[{'要素ID':namespace+':PlaceOfContactCoverPage','コンテキストID':'FilingDateInstant','値':'old address'}]
    assert parse_extraordinary_report(csv_files=[{'filename':'test.csv','data':rows}]).contact_address == 'old address'


def test_supplement_new_fields_do_not_invent_amounts_when_absent():
    parsed=parse_issuance_supplementary(csv_files=[{'filename':'test.csv','data':[]}])
    assert parsed.offering_amount_text is None and parsed.remaining_amount_text is None
