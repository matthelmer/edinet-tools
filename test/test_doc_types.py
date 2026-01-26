"""Tests for DocType registry."""
import pytest
from edinet_tools.doc_types import DocType, doc_type, list_doc_types


class TestDocType:
    """Test DocType registry."""

    def test_doc_type_lookup(self):
        """Look up doc type by code."""
        dt = doc_type("350")
        assert dt is not None
        assert dt.code == "350"
        assert dt.name_en == "Large Shareholding Report"
        assert dt.name_jp == "大量保有報告書"

    def test_catalyst_doc_types_defined(self):
        """All catalyst doc types are defined."""
        for code in ["120", "140", "160", "180", "350"]:
            dt = doc_type(code)
            assert dt is not None
            assert dt.name_en is not None

    def test_unknown_doc_type_returns_none(self):
        """Unknown doc type returns None."""
        assert doc_type("999") is None

    def test_list_doc_types(self):
        """list_doc_types returns all defined types."""
        types = list_doc_types()
        assert len(types) >= 5
        assert all(isinstance(t, DocType) for t in types)

    def test_doc_type_has_all_attributes(self):
        """DocType has expected attributes."""
        dt = doc_type("120")
        assert hasattr(dt, 'code')
        assert hasattr(dt, 'name_en')
        assert hasattr(dt, 'name_jp')
        assert hasattr(dt, 'description')

    def test_doc_type_repr(self):
        """DocType repr is informative."""
        dt = doc_type("350")
        repr_str = repr(dt)
        assert "350" in repr_str

    def test_amendment_doc_types(self):
        """Amendment doc types are defined."""
        # 130 is Securities Report Amendment
        dt = doc_type("130")
        assert dt is not None
        assert "Amendment" in dt.name_en or "訂正" in dt.name_jp
