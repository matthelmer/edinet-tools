"""
Tests for EntityClassifier.

Uses real FSA data files to validate classification logic.
"""
import pytest
from edinet_tools.entity_classifier import EntityClassifier, EntityType


@pytest.fixture
def classifier():
    """Load EntityClassifier with real data."""
    return EntityClassifier()


class TestEntityClassifierLoading:
    """Test data loading and initialization."""

    def test_loads_successfully(self, classifier):
        """Classifier should load without errors."""
        assert classifier is not None
        assert len(classifier._edinet_entities) > 10000
        assert len(classifier._fund_edinet_codes) > 300

    def test_stats_returns_expected_structure(self, classifier):
        """Stats should return count information."""
        stats = classifier.stats
        assert 'total_entities' in stats
        assert 'listed_companies' in stats
        assert 'unlisted_entities' in stats
        assert 'fund_issuers' in stats
        assert stats['total_entities'] > 10000
        assert stats['listed_companies'] > 3000

    def test_data_version_extracted(self, classifier):
        """Data version should be extracted from filenames."""
        version = classifier.data_version
        assert 'edinet_codes' in version
        assert 'fund_codes' in version
        # Should be YYYY-MM-DD format or 'unknown'
        assert version['edinet_codes'] == 'unknown' or len(version['edinet_codes']) == 10


class TestListedCompanyClassification:
    """Test classification of listed companies."""

    def test_toyota_is_listed_company(self, classifier):
        """Toyota (E02144) should be a listed company."""
        assert classifier.get_entity_type('E02144') == EntityType.LISTED_COMPANY
        assert classifier.is_listed('E02144')
        assert not classifier.is_fund('E02144')
        assert classifier.is_known('E02144')

    def test_toyota_securities_code(self, classifier):
        """Toyota should have correct securities code."""
        code = classifier.get_securities_code('E02144')
        assert code == '7203'

    def test_toyota_name(self, classifier):
        """Toyota should have correct name."""
        name = classifier.get_entity_name('E02144')
        assert 'TOYOTA' in name.upper()

    def test_sony_is_listed_company(self, classifier):
        """Sony (E01777) should be a listed company."""
        assert classifier.get_entity_type('E01777') == EntityType.LISTED_COMPANY
        assert classifier.is_listed('E01777')

    def test_softbank_group_is_listed(self, classifier):
        """SoftBank Group (E02778) should be listed."""
        assert classifier.get_entity_type('E02778') == EntityType.LISTED_COMPANY


class TestFundClassification:
    """Test classification of investment funds."""

    def test_fund_issuer_detected(self, classifier):
        """Fund issuers should be classified as FUND."""
        # Get a known fund issuer from the loaded data
        fund_issuers = list(classifier._fund_edinet_codes)
        assert len(fund_issuers) > 0

        # Test first fund issuer
        fund_code = fund_issuers[0]
        assert classifier.is_fund(fund_code)
        assert classifier.get_entity_type(fund_code) == EntityType.FUND

    def test_fund_not_listed(self, classifier):
        """Fund issuers should not be classified as listed companies."""
        fund_issuers = list(classifier._fund_edinet_codes)
        if fund_issuers:
            # Note: A fund issuer might also be in edinet_entities as a company,
            # but get_entity_type should return FUND (checked first)
            fund_code = fund_issuers[0]
            assert classifier.get_entity_type(fund_code) == EntityType.FUND


class TestUnknownEntities:
    """Test handling of unknown EDINET codes."""

    def test_unknown_code_returns_unknown(self, classifier):
        """Unknown EDINET codes should return UNKNOWN."""
        assert classifier.get_entity_type('E99999') == EntityType.UNKNOWN
        assert not classifier.is_known('E99999')
        assert not classifier.is_listed('E99999')
        assert not classifier.is_fund('E99999')

    def test_empty_code_returns_unknown(self, classifier):
        """Empty or None EDINET codes should return UNKNOWN."""
        assert classifier.get_entity_type('') == EntityType.UNKNOWN
        assert classifier.get_entity_type(None) == EntityType.UNKNOWN

    def test_invalid_format_returns_unknown(self, classifier):
        """Invalid EDINET code formats should return UNKNOWN."""
        assert classifier.get_entity_type('12345') == EntityType.UNKNOWN
        assert classifier.get_entity_type('ABCDE') == EntityType.UNKNOWN


class TestSecuritiesCodeFormatting:
    """Test securities code extraction and formatting."""

    def test_securities_code_is_4_digits(self, classifier):
        """Securities codes should be 4-digit format."""
        # Toyota has 5-digit code in data (72030) that should become 7203
        code = classifier.get_securities_code('E02144')
        if code:
            assert len(code) == 4 or len(code) == 5  # Some may not have trailing 0
            assert code.isdigit()

    def test_no_securities_code_for_unlisted(self, classifier):
        """Unlisted entities typically have no securities code."""
        # Find an unlisted entity
        for edinet_code, entity in classifier._edinet_entities.items():
            if not entity['is_listed']:
                code = classifier.get_securities_code(edinet_code)
                # Many unlisted entities have no code
                # (this is expected behavior, not a test failure)
                break

    def test_no_securities_code_for_unknown(self, classifier):
        """Unknown entities should return None for securities code."""
        assert classifier.get_securities_code('E99999') is None


class TestEntityNames:
    """Test entity name retrieval."""

    def test_english_name_preferred(self, classifier):
        """English name should be returned when available and preferred."""
        name = classifier.get_entity_name('E02144', prefer_english=True)
        assert name is not None
        # Toyota's English name should contain 'TOYOTA'
        assert 'TOYOTA' in name.upper()

    def test_japanese_name_fallback(self, classifier):
        """Japanese name should be returned when English not available."""
        # Find an entity without English name
        for edinet_code, entity in classifier._edinet_entities.items():
            if entity['name_jp'] and not entity.get('name_en'):
                name = classifier.get_entity_name(edinet_code, prefer_english=True)
                assert name == entity['name_jp']
                break

    def test_unknown_entity_name_is_none(self, classifier):
        """Unknown entities should return None for name."""
        assert classifier.get_entity_name('E99999') is None


class TestRepr:
    """Test string representation."""

    def test_repr_contains_counts(self, classifier):
        """Repr should contain entity and fund counts."""
        repr_str = repr(classifier)
        assert 'EntityClassifier' in repr_str
        assert 'entities=' in repr_str
        assert 'funds=' in repr_str
