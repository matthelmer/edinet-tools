"""Test new high-coverage fields on SecuritiesReport dataclass."""
import unittest
from edinet_tools.parsers.securities import SecuritiesReport, ELEMENT_MAP


class TestSecuritiesNewFields(unittest.TestCase):
    def test_dataclass_has_high_coverage_fields(self):
        """SecuritiesReport should have balance sheet detail fields."""
        report = SecuritiesReport(doc_id='S100TEST', doc_type_code='120')
        # Balance sheet detail
        self.assertIsNone(report.cash_and_deposits)
        self.assertIsNone(report.current_assets)
        self.assertIsNone(report.noncurrent_assets)
        self.assertIsNone(report.property_plant_equipment)
        self.assertIsNone(report.deferred_tax_assets)
        self.assertIsNone(report.current_liabilities)
        self.assertIsNone(report.accounts_payable_other)
        self.assertIsNone(report.retained_earnings)
        # Income detail
        self.assertIsNone(report.income_before_taxes)
        self.assertIsNone(report.non_operating_income)
        self.assertIsNone(report.non_operating_expenses)
        self.assertIsNone(report.income_taxes)
        # Cash flow detail
        self.assertIsNone(report.depreciation_amortization)
        # Employment - num_employees already exists in edinet-tools

    def test_element_map_has_new_entries(self):
        """ELEMENT_MAP should include high-coverage elements."""
        self.assertIn('cash_and_deposits', ELEMENT_MAP)
        self.assertIn('current_assets', ELEMENT_MAP)
        self.assertIn('noncurrent_assets', ELEMENT_MAP)
        self.assertIn('property_plant_equipment', ELEMENT_MAP)
        self.assertIn('deferred_tax_assets', ELEMENT_MAP)
        self.assertIn('current_liabilities', ELEMENT_MAP)
        self.assertIn('accounts_payable_other', ELEMENT_MAP)
        self.assertIn('retained_earnings', ELEMENT_MAP)
        self.assertIn('income_before_taxes', ELEMENT_MAP)
        self.assertIn('non_operating_income', ELEMENT_MAP)
        self.assertIn('non_operating_expenses', ELEMENT_MAP)
        self.assertIn('income_taxes', ELEMENT_MAP)
        self.assertIn('depreciation_amortization_cfo', ELEMENT_MAP)

    def test_extraction_with_csv_files(self):
        """New fields should be extracted from csv_files."""
        from edinet_tools.parsers.securities import parse_securities_report
        csv_files = [{'filename': 'test.csv', 'data': []}]
        result = parse_securities_report(
            csv_files=csv_files, doc_id='S100TEST', doc_type_code='120'
        )
        # All new fields should be None for empty CSV
        self.assertIsNone(result.cash_and_deposits)
        self.assertIsNone(result.depreciation_amortization)
        self.assertIsNone(result.income_before_taxes)
