"""Extraordinary-report contacts stay within one cover-page office block.

Complete original packages and saved CSVs from the 2026-10-02c corpus.
Independent XML verification, SHA256:
S100T5Y5 0d3b7a25082bf7ac2ce3187c9b6f4f3d0e979c6ce02088b6ab7e02b0cedf38c2
S100T6J9 46934918ad09ada7dfd396bbafb50885de76af13912e587a20bebab24c693f1e
S100T6ZB 3eef60f8a7eeca64b3250a07026cc324559c8c0e7280d85effc1b9b285f5d191
S100TPGS 8abfd8f0327ae8b27d9c2094ddf9ad3d0a9ac004867321a026a8abd801564f38
"""
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.extraordinary import parse_extraordinary_report

ROOT = Path(__file__).parent/'fixtures/contact_blocks'
CORP = 'jpcrp-esr_cor:'
FUND = 'jpsps-esr_cor:'


@pytest.mark.parametrize('source', ['csv','instance','xbrl'])
@pytest.mark.parametrize('doc,address,phone,person', [
    ('S100T5Y5','東京都新宿区新宿一丁目９番２号','03-6273-2753','コーポレート部長松岡壮'),
    ('S100T6J9','東京都目黒区原町１丁目７番８号クラフトビレッジ西小山内','(03)6885-1010',
     '執行役員経営管理部長阿部良一'),
    ('S100T6ZB','東京都中央区日本橋室町三丁目２番１号','03－6870－2015',
     '財務・経理統括部コーポレート経理グループディレクター半田久倫'),
    ('S100TPGS','岐阜県大垣市上石津町乙坂130番地1','(0584)46-3191(代表)',None),
])
def test_real_contact_address_phone_and_person_are_from_nearest_block(doc,address,phone,person,source):
    if source == 'csv':
        r = parse_extraordinary_report(csv_files=json.loads(gzip.decompress((ROOT/f'{doc}.json.gz').read_bytes())))
    else:
        r = parse_xbrl((ROOT/f'{doc}.zip').read_bytes(),'180',source=source)
    assert r.contact_address == address
    assert r.contact_phone == phone
    assert (''.join(r.contact_person.split()) if r.contact_person else None) == person
    # Both source offices remain in the raw facts; choosing one loses no source.
    assert any(f.element_id == CORP+'NameOfContactPersonCoverPage' for f in r.raw_facts)


def parse(values):
    return parse_extraordinary_report(csv_files=[{'filename':'synthetic.csv','data':[
        {'要素ID':k,'コンテキストID':'FilingDateInstant','値':v} for k,v in values.items()]}])


def blocks():
    return {
        FUND+'PlaceOfContactCoverPage':'fund address',
        FUND+'NameOfContactPersonCoverPage':'fund person',
        FUND+'TelephoneNumberCoverPage':'fund phone',
        CORP+'PlaceOfContactCoverPage':'legacy address',
        CORP+'NameOfContactPersonCoverPage':'legacy person',
        CORP+'TelephoneNumberCoverPage':'legacy phone',
        CORP+'NearestPlaceOfContactCoverPage':'nearest address',
        CORP+'NameOfContactPersonNearestPlaceOfContactCoverPage':'nearest person',
        CORP+'TelephoneNumberNearestPlaceOfContactCoverPage':'nearest phone',
    }


@pytest.mark.parametrize('selected', ['fund','legacy','nearest'])
def test_address_precedence_selects_whole_block(selected):
    values = blocks()
    if selected != 'fund':del values[FUND+'PlaceOfContactCoverPage']
    if selected == 'nearest':del values[CORP+'PlaceOfContactCoverPage']
    r = parse(values)
    assert (r.contact_address,r.contact_person,r.contact_phone) == (
        selected+' address',selected+' person',selected+' phone')


@pytest.mark.parametrize('field,element', [
    ('contact_person','NameOfContactPersonNearestPlaceOfContactCoverPage'),
    ('contact_phone','TelephoneNumberNearestPlaceOfContactCoverPage'),
])
@pytest.mark.parametrize('missing', ['absent',None,''])
def test_missing_nearest_field_never_borrows_head_office(field,element,missing):
    values = {k:v for k,v in blocks().items() if not k.startswith(FUND) and not k.endswith(':PlaceOfContactCoverPage')}
    if missing == 'absent':del values[CORP+element]
    else:values[CORP+element] = missing
    r = parse(values)
    assert r.contact_address == 'nearest address'
    assert getattr(r,field) is None


@pytest.mark.parametrize('prefix,address', [(FUND,'fund address'),(CORP,'legacy address')])
def test_legacy_address_does_not_borrow_person_from_other_block(prefix,address):
    values = blocks()
    if prefix == CORP:del values[FUND+'PlaceOfContactCoverPage']
    del values[prefix+'NameOfContactPersonCoverPage']
    r = parse(values)
    assert r.contact_address == address
    assert r.contact_person is None


@pytest.mark.parametrize('prefix', [FUND,CORP])
def test_no_contact_address_preserves_existing_available_block(prefix):
    values = {prefix+'NameOfContactPersonCoverPage':'person',prefix+'TelephoneNumberCoverPage':'phone'}
    r = parse(values)
    assert (r.contact_address,r.contact_person,r.contact_phone) == (None,'person','phone')


def test_filed_dash_is_preserved_as_text_in_selected_block():
    r = parse({CORP+'NearestPlaceOfContactCoverPage':'nearest',
               CORP+'NameOfContactPersonNearestPlaceOfContactCoverPage':'－',
               CORP+'TelephoneNumberNearestPlaceOfContactCoverPage':'－'})
    assert (r.contact_person,r.contact_phone) == ('－','－')
