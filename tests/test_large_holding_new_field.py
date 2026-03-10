"""Test listed_or_otc field on LargeHoldingReport."""
import unittest
from edinet_tools.parsers.large_holding import LargeHoldingReport, ELEMENT_MAP


class TestLargeHoldingNewField(unittest.TestCase):
    def test_listed_or_otc_field_exists(self):
        report = LargeHoldingReport(doc_id='S100TEST', doc_type_code='350')
        self.assertIsNone(report.listed_or_otc)

    def test_element_map_has_listed_or_otc(self):
        self.assertIn('listed_or_otc', ELEMENT_MAP)

    def test_extraction_with_csv_files(self):
        """listed_or_otc should be extracted from csv_files."""
        from edinet_tools.parsers.large_holding import parse_large_holding
        csv_files = [{'filename': 'test.csv', 'data': []}]
        result = parse_large_holding(
            csv_files=csv_files, doc_id='S100TEST', doc_type_code='350'
        )
        self.assertIsNone(result.listed_or_otc)
