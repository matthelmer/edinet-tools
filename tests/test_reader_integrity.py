"""Release-review regressions: exact numbers and unambiguous source identities."""

from decimal import Inexact, Rounded, ROUND_DOWN, ROUND_UP, localcontext
import io
import warnings
import zipfile

import pytest

from edinet_tools.parsers import ixbrl
from edinet_tools.parsers._xbrl_model import read_package_members
from edinet_tools.parsers.ixbrl import UnsupportedInlineXBRL, read_inline_xbrl_package
from edinet_tools.parsers.xbrl_instance import read_instance, read_instance_package
from tests.test_ixbrl_reader import facts_of, ixdoc, one
from tests.test_xbrl_instance_reader import INSTANCE


def numeric(value, scale=None, sign=None):
    attrs = ''
    if scale is not None:
        attrs += f' scale="{scale}"'
    if sign is not None:
        attrs += f' sign="{sign}"'
    return one(facts_of(
        '<ix:nonFraction name="x:N" contextRef="CurrentYearDuration" unitRef="JPY"'
        f'{attrs}>{value}</ix:nonFraction>'
    ), 'x:N').value


@pytest.mark.parametrize('precision,traps', [(28, False), (6, False), (6, True)])
@pytest.mark.parametrize('shown,scale,sign,expected', [
    ('1675916', '3', None, '1675916000'),
    ('123456789012345678901234567890', '0', None, '123456789012345678901234567890'),
    ('123456789012345678901234567890', None, None, '123456789012345678901234567890'),
    ('123456789012345678901234567890', '-2', '-', '-1234567890123456789012345678.90'),
    ('127.00', '0', None, '127.00'),
    ('127.00', '-2', None, '1.2700'),
    ('127.00', '2', None, '12700'),
    ('0', '3', '-', '-0'),
    ('0.00', '0', '-', '-0.00'),
    ('0', '-2', '-', '-0.00'),
    ('0', None, None, '0'),
    ('0001.20', '+2', None, '120'),
])
def test_numeric_is_exact_independent_of_decimal_context(
    precision, traps, shown, scale, sign, expected
):
    # Emax/Emin deliberately narrower than these facts. Source reading must not inherit
    # the arithmetic policy of the application calling the library.
    with localcontext() as context:
        context.prec = precision
        context.Emax = 2
        context.Emin = -2
        context.traps[Inexact] = traps
        context.traps[Rounded] = traps
        context.clear_flags()
        value = numeric(shown, scale, sign)
        assert value == expected
        assert not any(context.flags.values())
    # Independent literal instance facts carry the same exact string, including zeros.
    fact = (
        f'<x:N contextRef="CurrentYearDuration" unitRef="JPY">{expected}</x:N>'
    ).encode()
    instance = read_instance(INSTANCE.replace(b'</xbrli:xbrl>', fact + b'</xbrli:xbrl>'))
    assert one(instance.facts, 'x:N').value == value


def test_default_context_does_not_round_a_zero_scale_long_coefficient():
    with localcontext() as context:
        context.prec = 28
        value = '123456789012345678901234567890'
        assert numeric(value, '0') == value


@pytest.mark.parametrize('rounding', [ROUND_DOWN, ROUND_UP])
@pytest.mark.parametrize('traps', [False, True])
def test_low_precision_rounding_and_traps_cannot_change_a_filed_number(rounding, traps):
    with localcontext() as context:
        context.prec = 6
        context.rounding = rounding
        context.traps[Inexact] = traps
        context.traps[Rounded] = traps
        context.clear_flags()
        assert numeric('1675916', '3') == '1675916000'
        assert numeric('127.00', '-2', '-') == '-1.2700'
        assert not any(context.flags.values())


@pytest.mark.parametrize('scale', ['1000000', '-1000000', '9' * 5000, '', '1_0', '1.5'])
def test_unsupported_scale_has_named_refusal(scale):
    with pytest.raises(UnsupportedInlineXBRL, match='scale'):
        numeric('1', scale)


def test_output_limit_is_checked_before_expansion(monkeypatch):
    monkeypatch.setattr(ixbrl, 'MAX_NUMERIC_CHARS', 10)
    assert numeric('1', '9') == '1000000000'
    assert numeric('1', '-8') == '0.00000001'
    assert numeric('1', '8', '-') == '-100000000'
    for value, scale, sign in [('1', '10', None), ('1', '-9', None), ('1', '9', '-')]:
        with pytest.raises(UnsupportedInlineXBRL, match='numeric size'):
            numeric(value, scale, sign)
    with pytest.raises(UnsupportedInlineXBRL, match='numeric value'):
        numeric('1' * 11)


def test_instance_prefix_rebinding_cannot_conflate_distinct_elements():
    extra = (
        b'<x:N xmlns:x="urn:one" contextRef="CurrentYearDuration" unitRef="JPY">1</x:N>'
        b'<x:N xmlns:x="urn:two" contextRef="CurrentYearDuration" unitRef="JPY">2</x:N>'
    )
    with pytest.raises(UnsupportedInlineXBRL, match='prefix.*two namespaces'):
        read_instance(INSTANCE.replace(b'</xbrli:xbrl>', extra + b'</xbrli:xbrl>'))


def test_instance_repeated_identical_namespace_declaration_is_allowed():
    extra = (
        b'<x:N xmlns:x="http://example.com/x" contextRef="CurrentYearDuration" '
        b'unitRef="JPY">1</x:N>'
    )
    result = read_instance(INSTANCE.replace(b'</xbrli:xbrl>', extra + b'</xbrli:xbrl>'))
    assert one(result.facts, 'x:N').value == '1'


def duplicate_package(path, first, second):
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(buffer, 'w') as package:
            package.writestr(path, first)
            package.writestr(path, second)
    return buffer.getvalue()


@pytest.mark.parametrize('same', [False, True])
@pytest.mark.parametrize('source', ['inline', 'instance'])
def test_duplicate_selected_package_paths_are_refused_before_reading(monkeypatch, same, source):
    if source == 'inline':
        reader = read_inline_xbrl_package
        path = 'XBRL/PublicDoc/0101010_honbun_x_ixbrl.htm'
        first = ixdoc('')
    else:
        reader = read_instance_package
        path = 'XBRL/PublicDoc/x.xbrl'
        first = INSTANCE
    package = duplicate_package(path, first, first if same else b'different document')

    def must_not_read(*args, **kwargs):
        pytest.fail('duplicate paths must be refused before a member is inflated')

    monkeypatch.setattr(zipfile.ZipFile, 'open', must_not_read)
    with pytest.raises(UnsupportedInlineXBRL, match='duplicate member path'):
        reader(package)


def test_duplicate_unselected_members_do_not_affect_the_reader():
    package = duplicate_package('images/logo.png', b'one', b'two')
    names, members = read_package_members(package, lambda name: name.endswith('.xbrl'))
    assert names == ['images/logo.png', 'images/logo.png']
    assert members == {}
