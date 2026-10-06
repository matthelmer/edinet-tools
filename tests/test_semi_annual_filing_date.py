"""The filing date belongs to the cover page, never the financial period."""
from datetime import date
import gzip
import json
from pathlib import Path

import pytest

from edinet_tools import parse_xbrl
from edinet_tools.parsers.extraction import extract_csv_from_zip
from edinet_tools.parsers.semi_annual import parse_semi_annual_report
from tests.conftest import load_semi_annual_fixture

FIXTURES = Path(__file__).parent / 'fixtures' / 'xbrl'
COVER = 'jpcrp_cor:FilingDateCoverPage'
DEI = 'jpdei_cor:DateOfSubmissionDEI'


def parse(rows):
    return parse_semi_annual_report(csv_files=[{'filename': 'dates.csv', 'data': [
        {'要素ID': element, 'コンテキストID': context, '値': value}
        for element, context, value in rows
    ]}], doc_id='DATES', doc_type_code='160')


@pytest.mark.parametrize('name,expected', [
    ('canon', date(2026, 8, 6)), ('modec', date(2026, 8, 7)),
])
def test_real_filing_cover_date_differs_from_june_period_end(name, expected):
    # Canon's complete EDINET type-5 package and MODEC's complete saved CSV.
    # The corresponding original XBRL instances state the same cover dates.
    files = (extract_csv_from_zip((FIXTURES / 'S100YUDN_type5.zip').read_bytes())
             if name == 'canon' else load_semi_annual_fixture('modec_s100yuqz_usd'))
    report = parse_semi_annual_report(csv_files=files, doc_id=name, doc_type_code='160')
    assert report.period_end == date(2026, 6, 30)
    assert report.filing_date == expected


@pytest.mark.parametrize('source', ['xbrl', 'instance'])
def test_modec_native_sources_keep_cover_date(source):
    report = parse_xbrl((FIXTURES / 'S100YUQZ_type1.zip').read_bytes(), '160', source=source)
    assert report.period_end == date(2026, 6, 30)
    assert report.filing_date == date(2026, 8, 7)


@pytest.mark.parametrize('values,expected', [
    ([], None),
    ([(COVER, '2026-08-06')], date(2026, 8, 6)),
    ([(COVER, '2026年8月6日')], date(2026, 8, 6)),
    ([(COVER, '2026/08/06')], date(2026, 8, 6)),
    ([(COVER, '2026-02-30')], None),
    ([(COVER, '－')], None),
    ([(DEI, '2026-08-06')], date(2026, 8, 6)),
    ([(DEI, 'bad')], None),
    ([(COVER, 'bad'), (DEI, '2026-08-06')], date(2026, 8, 6)),
    ([(COVER, '2026-08-06'), (DEI, 'bad')], date(2026, 8, 6)),
    ([(COVER, '2026-08-06'), (DEI, '2026-08-06')], date(2026, 8, 6)),
    ([(COVER, '2026-08-06'), (DEI, '2026-08-07')], None),
    ([(COVER, '2026-08-06'), (COVER, '2026-08-07')], None),
    ([(COVER, '2026-08-06'), (COVER, '2026年8月6日')], date(2026, 8, 6)),
])
def test_only_one_unambiguous_valid_filing_date_is_returned(values, expected):
    rows = [(element, 'FilingDateInstant', value) for element, value in values]
    rows.append(('jpdei_cor:CurrentPeriodEndDateDEI', 'FilingDateInstant', '2026-06-30'))
    report = parse(rows)
    assert report.period_end == date(2026, 6, 30)
    assert report.filing_date == expected


def test_wrong_context_does_not_supply_a_filing_date():
    assert parse([(COVER, 'Prior1YearInstant', '2025-08-06')]).filing_date is None


def test_real_fund_uses_its_own_cover_page_taxonomy():
    report = parse_semi_annual_report(
        csv_files=load_semi_annual_fixture('smbc_trust_am_fund'),
        doc_id='SMBC', doc_type_code='160',
    )
    assert report.filing_date == date(2023, 11, 21)
    assert report.filing_date != report.period_end


def test_conflicting_dates_across_package_files_are_unknown():
    files = [{'filename': name, 'data': [
        {'要素ID': 'jpsps_cor:FilingDateCoverPage',
         'コンテキストID': 'FilingDateInstant', '値': value},
    ]} for name, value in [('a.csv', '2026-08-06'), ('b.csv', '2026-08-07')]]
    report = parse_semi_annual_report(csv_files=files, doc_id='CONFLICT', doc_type_code='160')
    assert report.filing_date is None


def test_amendment_keeps_original_cover_date_not_document_submission():
    # Nabtesco S100Z4CE, Doc 170: the complete saved CSV states 2024-08-09.
    # Original instance independently checked: FilingDateInstant is 2026-09-30,
    # and the cover title identifies the amendment of that date. Do not replace
    # the stated original cover date with the context's amendment date.
    fixture = FIXTURES.parent / 'semi_annual' / 'S100Z4CE.json.gz'
    with gzip.open(fixture, 'rt', encoding='utf-8') as handle:
        files = json.load(handle)
    report = parse_semi_annual_report(csv_files=files, doc_id='S100Z4CE', doc_type_code='170')
    assert report.filing_date == date(2024, 8, 9)
    assert report.period_end == date(2024, 6, 30)
    assert '2026年９月30日付け訂正報告書' in report.raw_fields['jpcrp_cor:DocumentTitleCoverPage']
