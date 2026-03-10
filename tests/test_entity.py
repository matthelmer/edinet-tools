"""Tests for Entity and Fund classes."""
import pytest
from unittest.mock import Mock, patch
from edinet_tools.entity import (
    Entity, entity, entity_by_ticker, entity_by_edinet_code, search_entities,
    Fund, fund, funds_by_issuer
)


class TestEntityBasics:
    """Test Entity dataclass structure."""

    def test_entity_has_required_attributes(self):
        """Entity should have all expected attributes."""
        data = {
            'edinet_code': 'E02144',
            'name_jp': 'トヨタ自動車株式会社',
            'name_en': 'TOYOTA MOTOR CORPORATION',
            'ticker': '7203',
            'is_listed': True,
            'submitter_type': 'Listed company',
            'industry': 'Automobiles',
        }
        entity = Entity(data)

        assert entity.edinet_code == 'E02144'
        assert entity.name_jp == 'トヨタ自動車株式会社'
        assert entity.name_en == 'TOYOTA MOTOR CORPORATION'
        assert entity.ticker == '7203'
        assert entity.is_listed is True

    def test_entity_name_property_prefers_english(self):
        """Entity.name should return English name if available."""
        data = {
            'edinet_code': 'E02144',
            'name_jp': 'トヨタ自動車株式会社',
            'name_en': 'TOYOTA MOTOR CORPORATION',
        }
        entity = Entity(data)
        assert entity.name == 'TOYOTA MOTOR CORPORATION'

    def test_entity_name_falls_back_to_japanese(self):
        """Entity.name should fall back to Japanese if no English."""
        data = {
            'edinet_code': 'E12345',
            'name_jp': 'テスト株式会社',
            'name_en': None,
        }
        entity = Entity(data)
        assert entity.name == 'テスト株式会社'

    def test_entity_repr(self):
        """Entity repr should be informative."""
        data = {
            'edinet_code': 'E02144',
            'name_jp': 'トヨタ自動車株式会社',
            'name_en': 'TOYOTA MOTOR CORPORATION',
            'ticker': '7203',
        }
        entity = Entity(data)
        repr_str = repr(entity)
        assert 'E02144' in repr_str


class TestEntityLookup:
    """Test entity lookup functions using real CSV data."""

    def test_entity_by_ticker_toyota(self):
        """Look up Toyota by ticker."""
        result = entity_by_ticker("7203")
        assert result is not None
        assert result.edinet_code == 'E02144'

    def test_entity_by_ticker_with_suffix(self):
        """Ticker lookup handles .T suffix."""
        result = entity_by_ticker("7203.T")
        assert result is not None
        assert result.edinet_code == 'E02144'

    def test_entity_by_edinet_code(self):
        """Look up by EDINET code."""
        result = entity_by_edinet_code("E02144")
        assert result is not None
        assert 'TOYOTA' in result.name.upper()

    def test_entity_smart_lookup_ticker(self):
        """Smart lookup resolves ticker."""
        result = entity("7203")
        assert result is not None
        assert result.edinet_code == 'E02144'

    def test_entity_smart_lookup_edinet_code(self):
        """Smart lookup resolves EDINET code."""
        result = entity("E02144")
        assert result is not None

    def test_entity_smart_lookup_name(self):
        """Smart lookup resolves name."""
        result = entity("Toyota")
        assert result is not None
        assert result.edinet_code == 'E02144'

    def test_entity_not_found_returns_none(self):
        """Lookup returns None for unknown identifiers."""
        assert entity("XXXXXX") is None
        assert entity_by_ticker("0000") is None
        assert entity_by_edinet_code("E99999") is None


class TestEntitySearch:
    """Test entity search using real CSV data."""

    def test_search_entities_by_name(self):
        """Search finds entities by name."""
        results = search_entities("Toyota", limit=5)
        assert len(results) > 0
        assert any(e.edinet_code == 'E02144' for e in results)

    def test_search_entities_returns_entity_objects(self):
        """Search returns Entity objects."""
        results = search_entities("自動車", limit=3)
        assert all(isinstance(e, Entity) for e in results)

    def test_search_entities_respects_limit(self):
        """Search respects limit parameter."""
        results = search_entities("株式会社", limit=5)
        assert len(results) <= 5


class TestFundBasics:
    """Test Fund class structure."""

    def test_fund_has_required_attributes(self):
        """Fund has expected attributes."""
        data = {
            'fund_code': 'G01003',
            'name': 'しんきんインデックスファンド225',
            'issuer_edinet_code': 'E12422',
            'issuer_name': 'しんきんアセットマネジメント投信株式会社',
        }
        f = Fund(data)
        assert f.fund_code == 'G01003'
        assert f.issuer_edinet_code == 'E12422'

    def test_fund_repr(self):
        """Fund repr is informative."""
        data = {
            'fund_code': 'G01003',
            'name': 'しんきんインデックスファンド225',
            'issuer_edinet_code': 'E12422',
            'issuer_name': 'しんきんアセットマネジメント投信',
        }
        f = Fund(data)
        assert 'G01003' in repr(f)


class TestFundLookup:
    """Test fund lookup using real CSV data."""

    def test_fund_by_code(self):
        """Look up fund by fund code."""
        result = fund("G01003")
        assert result is not None
        assert result.fund_code == 'G01003'

    def test_funds_by_issuer_returns_list(self):
        """funds_by_issuer returns a list."""
        # Use a known fund issuer from the data
        results = funds_by_issuer("E12422")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(f, Fund) for f in results)


class TestEntityFundIssuer:
    """Test entity fund issuer functionality."""

    def test_is_fund_issuer_false_for_regular_company(self):
        """Regular companies are not fund issuers."""
        toyota = entity("7203")
        assert toyota is not None
        assert toyota.is_fund_issuer is False

    def test_is_fund_issuer_true_for_fund_issuer(self):
        """Fund issuers are correctly identified."""
        # E12422 is しんきんアセットマネジメント投信 - a known fund issuer
        issuer = entity_by_edinet_code("E12422")
        assert issuer is not None
        assert issuer.is_fund_issuer is True

    def test_entity_funds_property_returns_list(self):
        """Entity.funds returns a list."""
        toyota = entity("7203")
        assert isinstance(toyota.funds, list)

    def test_entity_funds_empty_for_non_issuer(self):
        """Non-fund-issuers have empty funds list."""
        toyota = entity("7203")
        assert toyota.funds == []

    def test_entity_funds_populated_for_issuer(self):
        """Fund issuers have populated funds list."""
        issuer = entity_by_edinet_code("E12422")
        assert issuer is not None
        funds_list = issuer.funds
        assert len(funds_list) > 0
        assert all(isinstance(f, Fund) for f in funds_list)


class TestEntityDocuments:
    """Test Entity.documents() with mocked client."""

    def test_entity_documents_uses_module_client_when_no_explicit_client(self):
        """Entity.documents() uses module-level client when _client is None."""
        from unittest.mock import patch, MagicMock
        from edinet_tools._client import _reset_client, configure

        toyota = entity("7203")
        assert toyota._client is None

        _reset_client()
        with patch('edinet_tools._client.EdinetClient') as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get_documents_by_date.return_value = []

            configure(api_key='test-key')
            # Should NOT raise RuntimeError - uses module-level client
            docs = toyota.documents(days=1)
            assert docs == []

    def test_entity_documents_returns_list(self):
        """Entity.documents() returns list of Documents."""
        from edinet_tools.document import Document

        # Mock client response
        mock_filings = [
            {
                'docID': 'S100TEST1',
                'docTypeCode': '350',
                'submitDateTime': '2026-01-15 09:30',
                'edinetCode': 'E02144',
                'filerName': 'トヨタ',
            }
        ]

        mock_client = Mock()
        mock_client.get_documents_by_date.return_value = mock_filings

        toyota = entity("7203")
        toyota._client = mock_client
        docs = toyota.documents(days_back=1)

        assert isinstance(docs, list)

    def test_entity_documents_filters_by_doc_type(self):
        """Entity.documents() filters by doc type."""
        from edinet_tools.document import Document

        mock_filings = [
            {'docID': 'S1', 'docTypeCode': '350', 'submitDateTime': '2026-01-15 09:30', 'edinetCode': 'E02144', 'filerName': 'トヨタ'},
            {'docID': 'S2', 'docTypeCode': '120', 'submitDateTime': '2026-01-15 09:30', 'edinetCode': 'E02144', 'filerName': 'トヨタ'},
        ]

        mock_client = Mock()
        mock_client.get_documents_by_date.return_value = mock_filings

        toyota = entity("7203")
        toyota._client = mock_client
        docs = toyota.documents(doc_type="350", days_back=1)

        for doc in docs:
            assert doc.doc_type_code == "350"

    def test_entity_documents_returns_document_objects(self):
        """Entity.documents() returns Document objects."""
        from edinet_tools.document import Document

        mock_filings = [
            {
                'docID': 'S100TEST1',
                'docTypeCode': '350',
                'submitDateTime': '2026-01-15 09:30',
                'edinetCode': 'E02144',
                'filerName': 'トヨタ',
            }
        ]

        mock_client = Mock()
        mock_client.get_documents_by_date.return_value = mock_filings

        toyota = entity("7203")
        toyota._client = mock_client
        docs = toyota.documents(days_back=1)

        assert len(docs) > 0
        assert all(isinstance(d, Document) for d in docs)
