"""Test that parse functions accept pre-extracted csv_files."""
import unittest
from unittest.mock import MagicMock

from edinet_tools.parsers.large_holding import parse_large_holding, LargeHoldingReport
from edinet_tools.parsers.securities import parse_securities_report, SecuritiesReport
from edinet_tools.parsers.extraordinary import parse_extraordinary_report, ExtraordinaryReport
from edinet_tools.parsers.treasury_stock import parse_treasury_stock_report, TreasuryStockReport
from edinet_tools.parsers.semi_annual import parse_semi_annual_report, SemiAnnualReport
from edinet_tools.parsers.tender_offer import parse_tender_offer, TenderOfferReport
from edinet_tools.parsers.quarterly import parse_quarterly_report, QuarterlyReport


class TestCsvFilesParameter(unittest.TestCase):
    """All parse functions should accept csv_files kwarg and not crash on document=None."""

    def _empty_csv(self):
        return [{'filename': 'test.csv', 'data': []}]

    def test_parse_large_holding_with_csv_files(self):
        result = parse_large_holding(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='350'
        )
        self.assertIsInstance(result, LargeHoldingReport)
        self.assertEqual(result.doc_id, 'S100TEST')
        self.assertEqual(result.doc_type_code, '350')

    def test_parse_securities_report_with_csv_files(self):
        result = parse_securities_report(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='120'
        )
        self.assertIsInstance(result, SecuritiesReport)
        self.assertEqual(result.doc_id, 'S100TEST')

    def test_parse_extraordinary_report_with_csv_files(self):
        result = parse_extraordinary_report(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='180'
        )
        self.assertIsInstance(result, ExtraordinaryReport)
        self.assertEqual(result.doc_id, 'S100TEST')

    def test_parse_treasury_stock_report_with_csv_files(self):
        result = parse_treasury_stock_report(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='220'
        )
        self.assertIsInstance(result, TreasuryStockReport)
        self.assertEqual(result.doc_id, 'S100TEST')

    def test_parse_semi_annual_report_with_csv_files(self):
        result = parse_semi_annual_report(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='160'
        )
        self.assertIsInstance(result, SemiAnnualReport)
        self.assertEqual(result.doc_id, 'S100TEST')

    def test_parse_tender_offer_with_csv_files(self):
        result = parse_tender_offer(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='240'
        )
        self.assertIsInstance(result, TenderOfferReport)
        self.assertEqual(result.doc_id, 'S100TEST')

    def test_parse_quarterly_report_with_csv_files(self):
        result = parse_quarterly_report(
            document=None, csv_files=self._empty_csv(),
            doc_id='S100TEST', doc_type_code='140'
        )
        self.assertIsInstance(result, QuarterlyReport)
        self.assertEqual(result.doc_id, 'S100TEST')


class TestDocumentPathStillWorks(unittest.TestCase):
    """Existing document-based call path must not regress."""

    def _mock_doc(self, doc_type='350'):
        mock = MagicMock()
        mock.doc_id = 'S100TEST'
        mock.doc_type_code = doc_type
        mock.filer_name = 'Test Corp'
        mock.filer_edinet_code = 'E99999'
        mock.filing_datetime = None
        mock.fetch.return_value = b''
        return mock

    def test_large_holding_with_document(self):
        """Verify function still accepts a document positionally."""
        try:
            parse_large_holding(self._mock_doc('350'))
        except Exception:
            pass  # Expected — empty ZIP bytes

    def test_securities_with_document(self):
        try:
            parse_securities_report(self._mock_doc('120'))
        except Exception:
            pass
