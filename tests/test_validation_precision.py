"""Accounting checks and display must not inherit caller Decimal rounding."""
from decimal import Decimal, Inexact, Rounded, localcontext

import pytest

from edinet_tools.parsers.large_holding import LargeHoldingReport, parse_large_holding
from edinet_tools.parsers.securities import (
    _equity_ratio_reconciles, _equity_ratio_reconciles_jgaap, parse_securities_report,
)
from tests.conftest import load_fixture, load_securities_fixture
from tests.test_quarterly_migration import _parse as parse_quarterly_rows


@pytest.mark.parametrize('name', [
    'horiifood_jgaap', 'hoya_ifrs', 'itochu_ifrs', 'kansaipaint_jgaap',
    'komatsu_usgaap', 'shigagin_jgaap', 'shimamura_jgaap', 'toyota_ifrs',
])
@pytest.mark.parametrize('settings', ['low_precision', 'strict_traps', 'small_emax'])
def test_real_filing_values_and_annotations_ignore_caller_context(name, settings):
    def parse():
        return parse_securities_report(
            csv_files=load_securities_fixture(name), doc_id=name, doc_type_code='120',
        ).to_dict()
    baseline = parse()
    assert baseline['extraction_flags'] == []
    with localcontext() as context:
        if settings == 'low_precision':
            context.prec = 1
        elif settings == 'strict_traps':
            context.traps[Inexact] = True
            context.traps[Rounded] = True
        else:
            context.Emax = 2
        assert parse() == baseline


@pytest.mark.parametrize(('owners', 'assets', 'expected'), [
    (3, 10, True),
    (3 * 10 ** 40 - 1, 10 ** 41, False),
    (3 * 10 ** 40 + 1, 10 ** 41, True),
    (-3, -10, True),
    (3, 0, None),
])
@pytest.mark.parametrize(('precision', 'strict'), [(2, True), (28, False)])
def test_identity_tolerance_is_exact_at_and_beyond_boundary(owners, assets, expected, precision, strict):
    args = Decimal('.32'), Decimal(owners), Decimal(assets)
    with localcontext() as context:
        context.prec = precision
        context.traps[Inexact] = strict
        assert _equity_ratio_reconciles(*args) is expected
        # The same owners numerator, expressed as two J-GAAP components.
        assert _equity_ratio_reconciles_jgaap(
            args[0], Decimal(owners - 1), Decimal(1), args[2],
        ) is expected


@pytest.mark.parametrize('raw', ['1e999999999', '1e-999999999', 'Infinity', 'NaN'])
def test_identity_skips_unbounded_or_nonfinite_operands(raw):
    assert _equity_ratio_reconciles(Decimal(raw), Decimal(3), Decimal(10)) is None
    assert _equity_ratio_reconciles_jgaap(
        Decimal('.3'), Decimal(raw), Decimal(0), Decimal(10),
    ) is None


def test_identity_bound_accepts_safe_large_values_and_arbitrary_zero_exponent():
    assert _equity_ratio_reconciles(Decimal(1), Decimal('1e9999'), Decimal('1e9999')) is True
    assert _equity_ratio_reconciles(Decimal(0), Decimal('0e999999999'), Decimal(1)) is True


def test_ownership_display_keeps_float_api_and_filed_percentage():
    report = parse_large_holding(
        csv_files=load_fixture('large_holding', 'hikari_4491_joint_2026'),
        doc_id='S100YZFS', doc_type_code='350',
    )
    with localcontext() as context:
        context.prec = 2
        context.Emax = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert report.ownership_percentage == 13.09
        assert isinstance(report.ownership_percentage, float)
        assert 'ownership=13.09%' in repr(report)
        assert report.ownership_pct == Decimal('.1309')


@pytest.mark.parametrize(('raw', 'expected'), [('1e999999999', float('inf')), ('1e-999999999', 0.0)])
def test_display_extreme_exponents_do_not_expand_integers(raw, expected):
    report = LargeHoldingReport(doc_id='X', doc_type_code='350', ownership_pct=Decimal(raw))
    assert report.ownership_percentage == expected


@pytest.mark.parametrize(('raw', 'expected'), [
    ('NaN', None), ('sNaN', None), ('Infinity', None), ('-Infinity', None),
    ('1,234.56', Decimal('1234.56')), ('１，２３４．５６', Decimal('1234.56')),
])
def test_quarterly_eps_uses_finite_decimal_contract(raw, expected):
    report = parse_quarterly_rows((
        'jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
        'CurrentYTDDuration', raw,
    ))
    assert report.eps_basic_ytd == expected
