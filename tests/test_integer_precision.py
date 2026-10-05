"""Typed integer fields must retain the filing's digits, without a float hop."""
from decimal import Decimal, Inexact, Overflow, Rounded, localcontext

import pytest

from edinet_tools.parsers.extraction import parse_int, parse_percentage
from edinet_tools.parsers.large_holding import _normalize_holder_value, parse_large_holding


@pytest.mark.parametrize(('raw', 'expected'), [
    ('9007199254740991', 9007199254740991),
    ('9007199254740992', 9007199254740992),
    ('9007199254740993', 9007199254740993),
    ('-9007199254740993', -9007199254740993),
    ('+9,007,199,254,740,993', 9007199254740993),
    ('9，007，199，254，740，993', 9007199254740993),
    ('9007199254740993.0', 9007199254740993),
    ('9.007199254740993e15', 9007199254740993),
    ('123456789012345678901234567890', 123456789012345678901234567890),
    ('-123.99', -123),
    ('123.99', 123),
    ('9007199254740993.99', 9007199254740993),
    ('-9007199254740993.99', -9007199254740993),
    (9007199254740993, 9007199254740993),
    (Decimal('9007199254740993.99'), 9007199254740993),
])
@pytest.mark.parametrize('reader', [parse_int, lambda raw: _normalize_holder_value(raw, int)])
def test_integer_digits_survive_conversion(raw, expected, reader):
    # Applications can change the decimal context; reading filed digits is
    # not arithmetic and must not round to that ambient precision either.
    with localcontext() as context:
        context.prec = 6
        assert reader(raw) == expected


@pytest.mark.parametrize('raw', [None, '', '－', 'NaN', 'sNaN', 'Infinity', '-Infinity', 'bad'])
def test_missing_and_nonfinite_values_are_not_integers(raw):
    assert parse_int(raw) is None


@pytest.mark.parametrize('raw', [
    '1e999999999', '-1e999999999', Decimal('1e999999999'), '1e10000',
])
def test_integer_conversion_refuses_huge_allocation(raw):
    assert parse_int(raw) is None
    assert _normalize_holder_value(raw, int) is None


def test_integer_bound_and_tiny_values_are_exact():
    assert parse_int('1e9999') == 10 ** 9999
    assert parse_int('1e-999999999') == 0
    assert parse_int('-1e-999999999') == 0
    assert parse_int('0e999999999') == 0


@pytest.mark.parametrize('raw', [
    'NaN', 'sNaN', 'Infinity', '-Infinity', 'NaN%', Decimal('Infinity'), float('nan'),
])
def test_percentage_rejects_nonfinite_values(raw):
    assert parse_percentage(raw) is None


def _ratio_report(current, prior):
    rows = [
        {'要素ID': 'jplvh_cor:' + element, 'コンテキストID': 'FilingDateInstant', '値': value}
        for element, value in [
            ('HoldingRatioOfShareCertificatesEtc', current),
            ('HoldingRatioOfShareCertificatesEtcPerLastReport', prior),
        ]
    ]
    return parse_large_holding(
        csv_files=[{'filename': 'precision.csv', 'data': rows}],
        doc_id='PRECISION', doc_type_code='350',
    )


@pytest.mark.parametrize(('current', 'prior', 'expected'), [
    ('0.123456789012345678901234567890123456789', '0.01',
     '0.113456789012345678901234567890123456789'),
    ('0.01', '0.123456789012345678901234567890123456789',
     '-0.113456789012345678901234567890123456789'),
    ('0.0512', '0.0498', '0.0014'),
    ('0.1309', '0.1409', '-0.0100'),
    ('0.00', '0.00', '0.00'),
    ('0e999999999', '0.1', '-0.1'),
    ('1e100', '1e-100', '9' * 200 + 'e-100'),
])
def test_ownership_change_ignores_application_decimal_context(current, prior, expected):
    with localcontext() as context:
        context.prec = 2
        context.Emax = 1
        context.Emin = -1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        context.traps[Overflow] = True
        report = _ratio_report(current, prior)
        assert report.ownership_pct == Decimal(current)
        assert report.prior_ownership_pct == Decimal(prior)
        assert report.ownership_change.as_tuple() == Decimal(expected).as_tuple()


def test_unbounded_difference_retains_inputs_without_allocating_output():
    report = _ratio_report('1e999999999', '0.1')
    assert report.ownership_pct == Decimal('1e999999999')
    assert report.prior_ownership_pct == Decimal('0.1')
    assert report.ownership_change is None


def test_nonfinite_ratio_cannot_poison_ownership_change():
    report = _ratio_report('Infinity', '0.1')
    assert report.ownership_pct is None
    assert report.prior_ownership_pct == Decimal('0.1')
    assert report.ownership_change is None


def test_group_and_individual_holder_counts_retain_filed_digits():
    holder = 'FilingDateInstant_jplvh010000-lvh_E99999-000FilerLargeVolumeHolder1Member'
    rows = [
        {'要素ID': 'jplvh_cor:TotalNumberOfStocksEtcHeld',
         'コンテキストID': context, '値': value}
        for context, value in [
            ('FilingDateInstant', '9007199254740993'),
            (holder, '9.007199254740993e15'),
        ]
    ]
    report = parse_large_holding(
        csv_files=[{'filename': 'precision.csv', 'data': rows}],
        doc_id='PRECISION', doc_type_code='350',
    )
    assert report.shares_held == 9007199254740993
    assert len(report.joint_holders) == 1
    assert report.joint_holders[0].shares_held == 9007199254740993
