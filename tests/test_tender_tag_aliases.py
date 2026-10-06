"""Real old/new taxonomy sections must reach their typed tender fields."""
from pathlib import Path
import gzip
import json

import pytest

from edinet_tools.parsers import parse_xbrl
from edinet_tools.parsers.opinion_report import parse_opinion_report, ELEMENT_MAP
from edinet_tools.parsers.tender_offer import parse_tender_offer
from edinet_tools.parsers.extraction import extract_csv_from_zip

FIXTURES = Path(__file__).parent / 'fixtures'
FIELDS = ('extension_request_text', 'inquiries_text', 'profit_provision_text', 'defense_policy_text')


def opinion(doc, source):
    if source == 'csv':
        with gzip.open(FIXTURES / 'tender_aliases' / (doc + '.json.gz'), 'rt') as handle:
            files = json.load(handle)
        return parse_opinion_report(csv_files=files, doc_id=doc, doc_type_code='290')
    return parse_xbrl((FIXTURES / 'tender_aliases' / (doc + '.zip')).read_bytes(), '290', source=source)


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_2026_opinion_and_all_four_sections(source):
    report = opinion('S100Z4K0', source)
    assert '当該公開買付けに関する意見の内容、根拠及び理由等' in report.opinion_text
    assert '賛同の意見を表明' in report.opinion_text
    for field in FIELDS:
        assert '該当事項はありません' in getattr(report, field)
    if source != 'csv':
        assert len(report.opinion_text) > 60000


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_2021_substantive_sections_are_not_lost_to_na_only_mapping(source):
    report = opinion('S100MGAW', source)
    assert '株主意思確認' in report.defense_policy_text
    assert '添付別紙をご参照ください' in report.inquiries_text
    assert '2021年12月８日' in report.extension_request_text
    assert '該当事項はありません' in report.profit_provision_text
    assert '意見の表明を留保' in report.opinion_text


@pytest.mark.parametrize('source', ['csv', 'xbrl', 'instance'])
def test_readme_tender_example_recovers_2026_purchase_period(source):
    if source == 'csv':
        files = extract_csv_from_zip((FIXTURES / 'xbrl/S100Y4NW_type5.zip').read_bytes())
        report = parse_tender_offer(csv_files=files, doc_id='S100Y4NW', doc_type_code='240')
    else:
        report = parse_xbrl((FIXTURES / 'xbrl/S100Y4NW_type1.zip').read_bytes(), '240', source=source)
    assert '買付け等の期間' in report.period_text
    assert '2026年' in report.period_text


def synthetic(rows):
    files = [{'filename': 'opinion.csv', 'data': [
        {'要素ID': element, 'コンテキストID': 'FilingDateInstant', '値': value}
        for element, value in rows
    ]}]
    return parse_opinion_report(csv_files=files, doc_id='SYNTHETIC', doc_type_code='290')


@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('reverse', [False, True])
def test_content_precedes_na_independent_of_row_order(field, reverse):
    na = ELEMENT_MAP[field]
    rows = [(na, '該当事項なし'), (na[:-2] + 'TextBlock', '具体的な記載')]
    report = synthetic(rows[::-1] if reverse else rows)
    assert getattr(report, field) == '具体的な記載'


@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('suffix', ['NA', 'TextBlock'])
def test_filed_dash_is_retained(field, suffix):
    element = ELEMENT_MAP[field][:-2] + suffix
    assert getattr(synthetic([(element, '－')]), field) == '－'


def test_older_opinion_alias_keeps_precedence_when_both_are_filed():
    report = synthetic([
        ('jptoo-pst_cor:OpinionRegardingSaidTenderOfferAndBasisAndReasonsEtcTextBlock', 'new'),
        (ELEMENT_MAP['opinion_text'], 'old'),
    ])
    assert report.opinion_text == 'old'


def test_older_period_alias_keeps_precedence_when_both_are_filed():
    files = [{'filename': 'offer.csv', 'data': [
        {'要素ID': element, 'コンテキストID': 'FilingDateInstant', '値': value}
        for element, value in [
            ('jptoo-ton_cor:PeriodOfPurchaseEtcTextBlock', 'new'),
            ('jptoo-ton_cor:OriginalPeriodAtFilingTextBlock', 'old'),
        ]
    ]}]
    assert parse_tender_offer(csv_files=files, doc_id='BOTH', doc_type_code='240').period_text == 'old'
