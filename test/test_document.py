"""Tests for Document class."""
import pytest
from datetime import datetime
from edinet_tools.document import Document


class TestDocumentBasics:
    """Test Document class structure."""

    def test_document_has_required_attributes(self):
        """Document has expected attributes."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト株式会社',
        }
        doc = Document(data)
        assert doc.doc_id == 'S100ABC123'
        assert doc.doc_type_code == '350'
        assert doc.filer_edinet_code == 'E12345'

    def test_document_filing_datetime_parsing(self):
        """Document parses filing datetime."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト',
        }
        doc = Document(data)
        assert isinstance(doc.filing_datetime, datetime)
        assert doc.filing_datetime.year == 2026
        assert doc.filing_datetime.month == 1
        assert doc.filing_datetime.day == 15

    def test_document_doc_type_returns_doctype_object(self):
        """Document.doc_type returns DocType object."""
        from edinet_tools.doc_types import DocType
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト',
        }
        doc = Document(data)
        assert isinstance(doc.doc_type, DocType)
        assert doc.doc_type.code == '350'
        assert doc.doc_type.name_en == 'Large Shareholding Report'

    def test_document_doc_type_returns_none_for_unknown(self):
        """Document.doc_type returns None for unknown type code."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '999',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト',
        }
        doc = Document(data)
        assert doc.doc_type is None

    def test_document_doc_type_name_returns_english_name(self):
        """Document.doc_type_name returns English name."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト',
        }
        doc = Document(data)
        assert doc.doc_type_name == 'Large Shareholding Report'

    def test_document_doc_type_name_returns_none_for_unknown(self):
        """Document.doc_type_name returns None for unknown type code."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '999',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト',
        }
        doc = Document(data)
        assert doc.doc_type_name is None

    def test_document_filer_property_returns_entity(self):
        """Document.filer returns Entity for known filer."""
        from edinet_tools.entity import Entity
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E02144',  # Toyota
            'filerName': 'トヨタ自動車株式会社',
        }
        doc = Document(data)
        filer = doc.filer
        assert filer is not None
        assert isinstance(filer, Entity)
        assert filer.edinet_code == 'E02144'

    def test_document_filer_returns_none_for_unknown(self):
        """Document.filer returns None for unknown filer."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E99999',  # Unknown
            'filerName': 'Unknown Corp',
        }
        doc = Document(data)
        assert doc.filer is None

    def test_document_repr(self):
        """Document repr is informative."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト',
        }
        doc = Document(data)
        repr_str = repr(doc)
        assert 'S100ABC123' in repr_str
        assert '350' in repr_str

    def test_document_filer_name(self):
        """Document.filer_name returns raw filer name."""
        data = {
            'docID': 'S100ABC123',
            'docTypeCode': '350',
            'submitDateTime': '2026-01-15 09:30',
            'edinetCode': 'E12345',
            'filerName': 'テスト株式会社',
        }
        doc = Document(data)
        assert doc.filer_name == 'テスト株式会社'
