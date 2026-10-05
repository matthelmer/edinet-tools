"""Independent examples from the 2011-07-31 Transformation Registry grammar.

https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2011-07-31+errata-2019-04-17/inlineXBRL-transformationRegistry-REC-2011-07-31+corrected-errata-2019-04-17.html
The fractional part is one or two digits in hundredths, not tenths.
"""
import io
import zipfile
from decimal import Decimal

import pytest

from edinet_tools import parse_xbrl
from edinet_tools.parsers.ixbrl import UnsupportedInlineXBRL
from tests.test_ixbrl_reader import facts_of, ixdoc, one


def fact(shown, name='x:N', extra=''):
    return (f'<ix:nonFraction name="{name}" contextRef="CurrentYearDuration" '
            f'unitRef="JPY" format="ixt:numunitdecimal" {extra}>{shown}</ix:nonFraction>')


@pytest.mark.parametrize('shown,expected', [
    ('127円5銭', '127.05'), ('0円5銭', '0.05'), ('0円0銭', '0.00'),
    ('127円00銭', '127.00'), ('127円50銭', '127.50'), ('127円5', '127.05'),
    ('1,234円5銭', '1234.05'), ('1.234円5銭', '1234.05'),
    ('３，０００円５銭', '3000.05'), ('3.000 euro 5 cent', '3000.05'),
    ('１２７円０５銭', '127.05'), ('1234567円89銭', '1234567.89'),
])
def test_registry_examples_preserve_hundredths(shown, expected):
    assert one(facts_of(fact(shown)), 'x:N').value == expected


@pytest.mark.parametrize('shown', [
    '12円345銭', '007円00銭', '00円05銭', '1 234円5銭', '1\u00a0234円5銭',
    '1,23円05銭', '1,,234円05銭', '１２７円１２３銭', '1．234円05銭',
    '127円', '円5銭', '-127円05銭', '127.05',
])
def test_invalid_registry_spelling_is_refused(shown):
    with pytest.raises(UnsupportedInlineXBRL, match='numunitdecimal'):
        facts_of(fact(shown))


def test_sign_and_scale_apply_after_hundredths_transformation():
    assert one(facts_of(fact('127円5銭', extra='scale="2" sign="-"')), 'x:N').value == '-12705'


def test_public_annual_parser_keeps_one_digit_sen_in_eps():
    body = fact('127円5銭', name='jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults')
    document = ixdoc(body).replace(
        b'xmlns:x="http://example.com/x"',
        b'xmlns:x="http://example.com/x" xmlns:jpcrp_cor="http://example.com/jpcrp"',
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as package:
        package.writestr('XBRL/PublicDoc/0101010_honbun_x_ixbrl.htm', document)
    report = parse_xbrl(buffer.getvalue(), '120', source='xbrl')
    assert report.earnings_per_share == Decimal('127.05')
