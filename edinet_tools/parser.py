# xbrl_parser.py
"""
EDINET XBRL CSV Parser

Parses structured financial data from EDINET's XBRL-to-CSV converted files.
These CSV files contain financial metrics with context information (current/prior periods).
"""
import csv
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class FinancialMetric:
    """Represents a single financial metric with context."""
    element_name: str
    japanese_label: str
    context: str
    period_description: str
    unit_type: str
    currency: str
    scale: str
    value: Optional[float]
    
    @property
    def is_current_period(self) -> bool:
        """Check if this metric is for the current period."""
        period = self.period_description.lower()
        context = self.context.lower()
        
        # Check for various current period indicators
        current_indicators = [
            'current' in period,
            'currentytdduration' in period,
            'currentduration' in period,
            'currentinstant' in period,
            'current' in context and 'duration' not in period,  # Instant values
            period == '' and 'prior' not in context  # Default to current if ambiguous
        ]
        return any(current_indicators)
    
    @property
    def is_prior_period(self) -> bool:
        """Check if this metric is for the prior period."""
        period = self.period_description.lower()
        context = self.context.lower()
        
        # Check for various prior period indicators
        prior_indicators = [
            'prior' in period,
            'prior1ytdduration' in period,
            'priorduration' in period,
            'priorinstant' in period,
            'prior' in context
        ]
        return any(prior_indicators)


class EdinetXbrlCsvParser:
    """Parser for EDINET XBRL CSV files containing structured financial data."""
    
    # Key financial metrics mapping - expanded to include J-GAAP variants
    FINANCIAL_METRICS = {
        # Revenue/Sales - IFRS
        'revenue_ifrs': 'jpcrp_cor:RevenueIFRSSummaryOfBusinessResults',
        'revenue_jgaap': 'jpcrp_cor:NetSalesSummaryOfBusinessResults',
        'operating_revenue': 'jpcrp_cor:OperatingRevenueIFRSSummaryOfBusinessResults',
        
        # Profit/Loss - IFRS
        'profit_before_tax_ifrs': 'jpcrp_cor:ProfitLossBeforeTaxIFRSSummaryOfBusinessResults',
        'net_income_ifrs': 'jpcrp_cor:ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults',
        'comprehensive_income': 'jpcrp_cor:ComprehensiveIncomeAttributableToOwnersOfParentIFRSSummaryOfBusinessResults',
        'operating_profit_ifrs': 'jpcrp_cor:OperatingProfitLossIFRSSummaryOfBusinessResults',
        
        # Profit/Loss - J-GAAP
        'net_income_jgaap': 'jpcrp_cor:NetIncomeLossSummaryOfBusinessResults',
        'operating_profit_jgaap': 'jpcrp_cor:OperatingIncomeLossSummaryOfBusinessResults',
        'ordinary_profit': 'jpcrp_cor:OrdinaryIncomeLossSummaryOfBusinessResults',
        
        # Balance Sheet - IFRS
        'total_assets_ifrs': 'jpcrp_cor:TotalAssetsIFRSSummaryOfBusinessResults',
        'equity_ifrs': 'jpcrp_cor:EquityAttributableToOwnersOfParentIFRSSummaryOfBusinessResults',
        
        # Balance Sheet - J-GAAP
        'total_assets_jgaap': 'jpcrp_cor:TotalAssetsSummaryOfBusinessResults',
        'equity_jgaap': 'jpcrp_cor:NetAssetsSummaryOfBusinessResults',
        
        # Per Share - IFRS
        'earnings_per_share_ifrs': 'jpcrp_cor:BasicEarningsLossPerShareIFRSSummaryOfBusinessResults',
        'earnings_per_share_diluted_ifrs': 'jpcrp_cor:DilutedEarningsLossPerShareIFRSSummaryOfBusinessResults',
        
        # Per Share - J-GAAP
        'earnings_per_share_jgaap': 'jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
        'earnings_per_share_diluted_jgaap': 'jpcrp_cor:DilutedEarningsLossPerShareSummaryOfBusinessResults',
        
        # Ratios
        'equity_ratio_ifrs': 'jpcrp_cor:RatioOfOwnersEquityToGrossAssetsIFRSSummaryOfBusinessResults',
        'equity_ratio_jgaap': 'jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults',
        'roe': 'jpcrp_cor:RateOfReturnOnEquitySummaryOfBusinessResults',
        'roa': 'jpcrp_cor:RateOfReturnOnAssetsSummaryOfBusinessResults',
    }
    
    def __init__(self):
        self.metrics: List[FinancialMetric] = []
    
    def parse_xbrl_csv_files(self, csv_files: List[str]) -> Dict[str, Any]:
        """
        Parse multiple XBRL CSV files and extract financial metrics.
        
        Args:
            csv_files: List of paths to XBRL CSV files
            
        Returns:
            Dictionary of structured financial data
        """
        self.metrics = []
        
        for csv_file in csv_files:
            if os.path.exists(csv_file):
                logger.debug(f"Parsing XBRL CSV file: {csv_file}")
                self._parse_single_csv_file(csv_file)
            else:
                logger.warning(f"XBRL CSV file not found: {csv_file}")
        
        return self._extract_key_metrics()
    
    def _parse_single_csv_file(self, csv_file: str) -> None:
        """Parse a single XBRL CSV file."""
        logger.debug(f"Parsing XBRL CSV file: {csv_file}")
        # Try multiple encodings for robust parsing
        encodings = ['utf-16le', 'utf-16', 'utf-8', 'shift-jis', 'euc-jp']
        content = None
        
        for encoding in encodings:
            try:
                with open(csv_file, 'r', encoding=encoding, errors='ignore') as f:
                    content = f.read()
                    # Remove BOM if present
                    if content.startswith('\ufeff'):
                        content = content[1:]
                    if content.startswith('��'):
                        content = content[1:]
                    break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if not content:
            logger.error(f"Could not read XBRL CSV file with any encoding: {csv_file}")
            return
        
        try:
            # Parse CSV content
            lines = content.strip().split('\n')
            reader = csv.reader(lines, delimiter='\t')
            
            total_rows = 0
            parsed_rows = 0
            relevant_rows = 0
            
            for row_num, row in enumerate(reader, 1):
                total_rows += 1
                if len(row) >= 9:  # Ensure we have all required columns (updated from 11 to 9)
                    try:
                        if total_rows <= 3:  # Show raw data for first few rows
                            logger.debug(f"Raw row {row_num}: {[col[:50] for col in row[:3]]}")  # Truncate long values
                        metric = self._parse_csv_row(row, total_rows)
                        if metric:
                            parsed_rows += 1
                            if self._is_relevant_metric(metric.element_name):
                                relevant_rows += 1
                                self.metrics.append(metric)
                            elif total_rows <= 10 and metric.element_name:  # Show more examples for debugging
                                logger.debug(f"Non-relevant element: '{metric.element_name[:100]}'")
                    except Exception as e:
                        logger.debug(f"Error parsing row {row_num} in {csv_file}: {e}")
                        continue
                        
            logger.debug(f"Processed {total_rows} rows, parsed {parsed_rows}, found {relevant_rows} relevant metrics")
                            
        except Exception as e:
            logger.error(f"Error reading XBRL CSV file {csv_file}: {e}")
    
    def _parse_csv_row(self, row: List[str], total_rows: int = 0) -> Optional[FinancialMetric]:
        """Parse a single CSV row into a FinancialMetric."""
        try:
            # Clean up quoted values and handle encoding issues
            cleaned_row = []
            for i, col in enumerate(row):
                if not col:
                    cleaned_row.append('')
                    continue
                    
                cleaned = col.strip()
                # Remove null bytes, control characters, and quotes
                cleaned = cleaned.replace('\x00', '').replace('\ufeff', '')
                # Remove various quote types and control characters
                cleaned = cleaned.strip('"').strip("'").strip()
                # Remove other control characters that might appear
                cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in ['\t', '\n'])
                cleaned_row.append(cleaned)
            
            # CSV structure: "要素ID", "項目名", "コンテキストID", "相対年度", "連結・個別", "期間・時点", "ユニットID", "単位", "値"
            element_name = cleaned_row[0]           # 要素ID
            japanese_label = cleaned_row[1]         # 項目名
            context = cleaned_row[2]                # コンテキストID
            period_description = cleaned_row[3]     # 相対年度
            consolidation_type = cleaned_row[4]     # 連結・個別
            period_type = cleaned_row[5]            # 期間・時点
            unit_id = cleaned_row[6]                # ユニットID
            unit_scale = cleaned_row[7]             # 単位
            value_str = cleaned_row[8]              # 値
            
            # Debug: show cleaned values for first few relevant rows
            if total_rows <= 50 and self._is_relevant_metric(element_name) and len([m for m in self.metrics if self._is_relevant_metric(m.element_name)]) == 0:
                logger.debug(f"First relevant metric found:")
                logger.debug(f"  Element: '{element_name}'")
                logger.debug(f"  Context: '{context}'")
                logger.debug(f"  All columns: {cleaned_row}")
            
            # Parse numeric value with better handling
            value = None
            if value_str:
                try:
                    # Remove commas and handle negative values
                    clean_value = value_str.replace(',', '').strip()
                    if clean_value and (clean_value.replace('-', '').replace('.', '').isdigit() or 
                                      clean_value.count('.') == 1 and clean_value.replace('-', '').replace('.', '').isdigit()):
                        value = float(clean_value)
                        # Convert based on scale information
                        if unit_scale:
                            if '千円' in unit_scale or '千' in unit_scale:
                                value = value * 1000
                            elif '百万円' in unit_scale or '百万' in unit_scale:
                                value = value * 1000000
                            elif '十億円' in unit_scale or '十億' in unit_scale:
                                value = value * 1000000000
                except (ValueError, TypeError):
                    value = None
            
            return FinancialMetric(
                element_name=element_name,
                japanese_label=japanese_label,
                context=context,
                period_description=period_description,  # 相対年度
                unit_type=period_type,                  # 期間・時点
                currency=unit_id,                       # ユニットID
                scale=unit_scale,                       # 単位
                value=value
            )
            
        except (IndexError, ValueError) as e:
            logger.debug(f"Error parsing CSV row: {e}")
            return None
    
    def _is_relevant_metric(self, element_name: str) -> bool:
        """Check if this metric is one we care about."""
        return element_name in self.FINANCIAL_METRICS.values()
    
    def _extract_key_metrics(self) -> Dict[str, Any]:
        """Extract and organize key financial metrics."""
        result = {
            'financial_metrics': {},
            'has_xbrl_data': len(self.metrics) > 0,
            'metrics_count': len(self.metrics)
        }
        
        # Group metrics by type and period
        for metric_key, element_name in self.FINANCIAL_METRICS.items():
            current_value = None
            prior_value = None
            
            # Find current and prior values for this metric
            for metric in self.metrics:
                if metric.element_name == element_name:
                    logger.debug(f"Found metric {metric_key}: element={metric.element_name}, context={metric.context}, value={metric.value}")
                    if metric.is_current_period:
                        current_value = metric.value
                    elif metric.is_prior_period:
                        prior_value = metric.value
            
            # Store the metric data
            if current_value is not None or prior_value is not None:
                result['financial_metrics'][metric_key] = {
                    'current': current_value,
                    'prior': prior_value,
                    'element_name': element_name
                }
                logger.debug(f"Extracted metric {metric_key}: current={current_value}, prior={prior_value}")
        
        # Debug: Show what elements we found
        if self.metrics:
            unique_elements = set(m.element_name for m in self.metrics)
            logger.debug(f"Found {len(unique_elements)} unique XBRL elements:")
            for element in sorted(unique_elements)[:10]:  # Show first 10
                logger.debug(f"  - {element}")
            if len(unique_elements) > 10:
                logger.debug(f"  ... and {len(unique_elements) - 10} more")
        
        logger.info(f"Extracted {len(result['financial_metrics'])} financial metrics from XBRL data")
        return result


def extract_xbrl_financial_data(zip_extract_path: str) -> Dict[str, Any]:
    """
    Extract financial metrics from XBRL CSV files in a document extraction.
    
    Args:
        zip_extract_path: Path to extracted ZIP contents
        
    Returns:
        Dictionary of financial metrics or empty dict if no XBRL data
    """
    xbrl_csv_dir = os.path.join(zip_extract_path, 'XBRL_TO_CSV')
    
    if not os.path.exists(xbrl_csv_dir):
        logger.debug("No XBRL_TO_CSV directory found")
        return {'has_xbrl_data': False}
    
    # Find all CSV files in the XBRL directory
    csv_files = []
    for filename in os.listdir(xbrl_csv_dir):
        if filename.endswith('.csv'):
            csv_files.append(os.path.join(xbrl_csv_dir, filename))
    
    if not csv_files:
        logger.debug("No CSV files found in XBRL_TO_CSV directory")
        return {'has_xbrl_data': False}
    
    # Parse the XBRL CSV files
    parser = EdinetXbrlCsvParser()
    return parser.parse_xbrl_csv_files(csv_files)