"""Test new fields on ExtraordinaryReport."""
import unittest
from edinet_tools.parsers.extraordinary import ExtraordinaryReport, ELEMENT_MAP


class TestExtraordinaryNewFields(unittest.TestCase):
    def test_dataclass_has_amendment_fields(self):
        report = ExtraordinaryReport(doc_id='S100TEST', doc_type_code='180')
        self.assertIsNone(report.amendment_flag)
        self.assertIsNone(report.report_amendment_flag)

    def test_dataclass_has_contact_fields(self):
        report = ExtraordinaryReport(doc_id='S100TEST', doc_type_code='180')
        self.assertIsNone(report.place_of_filing)
        self.assertIsNone(report.contact_person)
        self.assertIsNone(report.contact_address)
        self.assertIsNone(report.contact_phone)

    def test_element_map_has_new_entries(self):
        self.assertIn('amendment_flag', ELEMENT_MAP)
        self.assertIn('report_amendment_flag', ELEMENT_MAP)
        self.assertIn('place_of_filing_fund', ELEMENT_MAP)
        self.assertIn('place_of_filing_corp', ELEMENT_MAP)
        self.assertIn('contact_person_fund', ELEMENT_MAP)
        self.assertIn('contact_person_corp', ELEMENT_MAP)
        self.assertIn('contact_address_fund', ELEMENT_MAP)
        self.assertIn('contact_address_corp', ELEMENT_MAP)
        self.assertIn('contact_phone_fund', ELEMENT_MAP)
        self.assertIn('contact_phone_corp', ELEMENT_MAP)

    def test_extraction_with_csv_files(self):
        """New fields should be extracted from csv_files."""
        from edinet_tools.parsers.extraordinary import parse_extraordinary_report
        csv_files = [{'filename': 'test.csv', 'data': []}]
        result = parse_extraordinary_report(
            csv_files=csv_files, doc_id='S100TEST', doc_type_code='180'
        )
        self.assertIsNone(result.amendment_flag)
        self.assertIsNone(result.place_of_filing)
        self.assertIsNone(result.contact_person)
