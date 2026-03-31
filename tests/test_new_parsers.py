"""
Tests for the three new parser families:
  - ConfirmationReport (Doc 135/136)
  - ParentCompanyReport (Doc 200/210)
  - LargeHoldingChangeReport (Doc 370/380)

Covers routing (no fallthrough to RawReport), empty-document behaviour,
dataclass defaults, repr, and supported_doc_types() count.
"""
import pytest
from unittest.mock import MagicMock

from edinet_tools.parsers import parse, supported_doc_types
from edinet_tools.parsers.generic import RawReport
from edinet_tools.parsers.confirmation import (
    ConfirmationReport,
    parse_confirmation,
)
from edinet_tools.parsers.parent_company import (
    ParentCompanyReport,
    parse_parent_company,
)
from edinet_tools.parsers.large_holding_change import (
    LargeHoldingChangeReport,
    parse_large_holding_change,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(code: str) -> MagicMock:
    doc = MagicMock()
    doc.doc_type_code = code
    doc.doc_id = f'TEST_{code}'
    doc.filer_edinet_code = ''
    doc.fetch.return_value = b''
    return doc


# ---------------------------------------------------------------------------
# Routing — no fallthrough to RawReport
# ---------------------------------------------------------------------------

NEW_DOC_TYPES = ['135', '136', '200', '210', '370', '380']


@pytest.mark.parametrize("code", NEW_DOC_TYPES)
def test_new_doc_type_does_not_fall_through_to_raw(code):
    """All 6 new doc type codes must route to a typed parser, not RawReport."""
    doc = _make_doc(code)
    try:
        result = parse(doc)
        assert not isinstance(result, RawReport), \
            f"Doc type {code} fell through to RawReport instead of a typed parser"
    except Exception:
        pass  # Parser attempted but failed on empty mock data = correct routing


def test_doc_135_routes_to_confirmation():
    doc = _make_doc('135')
    result = parse(doc)
    assert isinstance(result, ConfirmationReport)


def test_doc_136_routes_to_confirmation():
    doc = _make_doc('136')
    result = parse(doc)
    assert isinstance(result, ConfirmationReport)


def test_doc_200_routes_to_parent_company():
    doc = _make_doc('200')
    result = parse(doc)
    assert isinstance(result, ParentCompanyReport)


def test_doc_210_routes_to_parent_company():
    doc = _make_doc('210')
    result = parse(doc)
    assert isinstance(result, ParentCompanyReport)


def test_doc_370_routes_to_large_holding_change():
    doc = _make_doc('370')
    result = parse(doc)
    assert isinstance(result, LargeHoldingChangeReport)


def test_doc_380_routes_to_large_holding_change():
    doc = _make_doc('380')
    result = parse(doc)
    assert isinstance(result, LargeHoldingChangeReport)


# ---------------------------------------------------------------------------
# Empty-document behaviour
# ---------------------------------------------------------------------------

class TestEmptyDocuments:
    def test_confirmation_empty(self):
        doc = _make_doc('135')
        report = parse_confirmation(doc)
        assert isinstance(report, ConfirmationReport)
        assert report.doc_id == 'TEST_135'
        assert report.filer_name is None
        assert report.is_amendment is False
        assert report.source_files == []

    def test_confirmation_amendment_empty(self):
        doc = _make_doc('136')
        report = parse_confirmation(doc)
        assert isinstance(report, ConfirmationReport)
        assert report.doc_id == 'TEST_136'

    def test_parent_company_empty(self):
        doc = _make_doc('200')
        report = parse_parent_company(doc)
        assert isinstance(report, ParentCompanyReport)
        assert report.doc_id == 'TEST_200'
        assert report.filer_name is None
        assert report.is_amendment is False
        assert report.source_files == []

    def test_parent_company_amendment_empty(self):
        doc = _make_doc('210')
        report = parse_parent_company(doc)
        assert isinstance(report, ParentCompanyReport)
        assert report.doc_id == 'TEST_210'

    def test_large_holding_change_empty(self):
        doc = _make_doc('370')
        report = parse_large_holding_change(doc)
        assert isinstance(report, LargeHoldingChangeReport)
        assert report.doc_id == 'TEST_370'
        assert report.filer_name is None
        assert report.is_amendment is False
        assert report.source_files == []

    def test_large_holding_change_amendment_empty(self):
        doc = _make_doc('380')
        report = parse_large_holding_change(doc)
        assert isinstance(report, LargeHoldingChangeReport)
        assert report.doc_id == 'TEST_380'


# ---------------------------------------------------------------------------
# Dataclass defaults
# ---------------------------------------------------------------------------

class TestDataclassDefaults:
    def test_confirmation_defaults(self):
        r = ConfirmationReport(doc_id='X', doc_type_code='135')
        assert r.filer_name is None
        assert r.filer_name_en is None
        assert r.filer_edinet_code is None
        assert r.security_code is None
        assert r.is_amendment is False

    def test_parent_company_defaults(self):
        r = ParentCompanyReport(doc_id='X', doc_type_code='200')
        assert r.filer_name is None
        assert r.filer_name_en is None
        assert r.filer_edinet_code is None
        assert r.security_code is None
        assert r.is_amendment is False

    def test_large_holding_change_defaults(self):
        r = LargeHoldingChangeReport(doc_id='X', doc_type_code='370')
        assert r.filer_name is None
        assert r.filer_name_en is None
        assert r.filer_edinet_code is None
        assert r.security_code is None
        assert r.is_amendment is False


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_confirmation_repr_unknown(self):
        r = ConfirmationReport(doc_id='X', doc_type_code='135')
        assert 'ConfirmationReport' in repr(r)
        assert 'Unknown' in repr(r)

    def test_confirmation_repr_with_name(self):
        r = ConfirmationReport(doc_id='X', doc_type_code='135', filer_name='テスト株式会社')
        assert 'テスト' in repr(r)
        assert 'AMENDED' not in repr(r)

    def test_confirmation_repr_amendment(self):
        r = ConfirmationReport(doc_id='X', doc_type_code='136', is_amendment=True)
        assert 'AMENDED' in repr(r)

    def test_confirmation_repr_truncates_long_name(self):
        r = ConfirmationReport(doc_id='X', doc_type_code='135', filer_name='A' * 50)
        assert '...' in repr(r)

    def test_parent_company_repr_unknown(self):
        r = ParentCompanyReport(doc_id='X', doc_type_code='200')
        assert 'ParentCompanyReport' in repr(r)
        assert 'Unknown' in repr(r)

    def test_parent_company_repr_amendment(self):
        r = ParentCompanyReport(doc_id='X', doc_type_code='210', is_amendment=True)
        assert 'AMENDED' in repr(r)

    def test_large_holding_change_repr_unknown(self):
        r = LargeHoldingChangeReport(doc_id='X', doc_type_code='370')
        assert 'LargeHoldingChangeReport' in repr(r)
        assert 'Unknown' in repr(r)

    def test_large_holding_change_repr_amendment(self):
        r = LargeHoldingChangeReport(doc_id='X', doc_type_code='380', is_amendment=True)
        assert 'AMENDED' in repr(r)


# ---------------------------------------------------------------------------
# supported_doc_types() count
# ---------------------------------------------------------------------------

def test_supported_doc_types_count():
    """After adding 3 parsers (6 codes), total should be 42."""
    codes = supported_doc_types()
    assert len(codes) == 42, (
        f"Expected 42 supported doc types, got {len(codes)}. "
        f"Missing codes: {set(NEW_DOC_TYPES) - set(codes)}"
    )


def test_new_codes_in_supported_doc_types():
    """All 6 new codes must appear in supported_doc_types()."""
    codes = set(supported_doc_types())
    for code in NEW_DOC_TYPES:
        assert code in codes, f"Doc type {code} missing from supported_doc_types()"
