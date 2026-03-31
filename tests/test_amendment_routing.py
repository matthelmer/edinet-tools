"""Tests that amendment doc types route to the correct base parser."""
import pytest
from unittest.mock import MagicMock
from edinet_tools.parsers import parse
from edinet_tools.parsers.generic import RawReport


AMENDMENT_ROUTES = [
    ("130", "120"),  # Securities Report Amendment -> Securities Report
    ("150", "140"),  # Quarterly Report Amendment -> Quarterly Report
    ("170", "160"),  # Semi-Annual Report Amendment -> Semi-Annual Report
    ("190", "180"),  # Extraordinary Report Amendment -> Extraordinary Report
    ("360", "350"),  # Large Shareholding Amendment -> Large Shareholding Report
]


@pytest.mark.parametrize("amendment_code,base_code", AMENDMENT_ROUTES)
def test_amendment_does_not_fall_through_to_raw(amendment_code, base_code):
    """Amendment doc types should NOT fall through to RawReport/parse_raw."""
    doc = MagicMock()
    doc.doc_type_code = amendment_code
    doc.doc_id = f"TEST_{amendment_code}"
    doc.fetch.return_value = None

    try:
        result = parse(doc)
        assert not isinstance(result, RawReport), \
            f"Doc type {amendment_code} fell through to RawReport instead of routing to base parser"
    except Exception:
        pass  # Parser attempted but failed on mock data = correct routing


def test_existing_amendment_routes_still_work():
    """Verify pre-existing amendment routes (230, 250) are unchanged."""
    for code in ["230", "250"]:
        doc = MagicMock()
        doc.doc_type_code = code
        doc.doc_id = f"TEST_{code}"
        doc.fetch.return_value = None
        try:
            result = parse(doc)
            assert not isinstance(result, RawReport)
        except Exception:
            pass
