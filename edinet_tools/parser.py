# xbrl_parser.py
"""
EDINET XBRL CSV Parser

Parses structured financial data from EDINET's XBRL-to-CSV converted files.
These CSV files contain financial metrics with context information (current/prior periods).
Also extracts narrative text blocks containing business policy, strategy, and targets.
"""
import csv
import logging
import re
from typing import Dict, Optional, Any, List, Tuple
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


@dataclass
class TextBlock:
    """Represents a narrative text block from EDINET filings."""
    element_name: str
    japanese_label: str
    text_content: str

    def search(self, keywords: List[str], context_chars: int = 200) -> List[Tuple[str, str]]:
        """
        Search for keywords in this text block.

        Args:
            keywords: List of keywords/patterns to search for
            context_chars: Number of characters of context to return around matches

        Returns:
            List of (keyword, context_snippet) tuples
        """
        matches = []
        for keyword in keywords:
            pattern = re.compile(keyword, re.IGNORECASE)
            for match in pattern.finditer(self.text_content):
                start = max(0, match.start() - context_chars)
                end = min(len(self.text_content), match.end() + context_chars)
                snippet = self.text_content[start:end]
                matches.append((keyword, snippet))
        return matches


class EdinetXbrlCsvParser:
    """Parser for EDINET XBRL CSV files containing structured financial data and narrative text blocks."""

    # Narrative text blocks containing business policy, strategy, and MTP information
    NARRATIVE_TEXT_BLOCKS = {
        'business_policy': 'jpcrp_cor:BusinessPolicyBusinessEnvironmentIssuesToAddressEtcTextBlock',
        'metrics_and_targets': 'jpcrp_cor:MetricsAndTargetsTextBlock',
        'management_analysis': 'jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock',
        'research_and_development': 'jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock',
        'facilities_plan': 'jpcrp_cor:PlannedAdditionsRetirementsEtcOfFacilitiesTextBlock',
    }

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
        self.text_blocks: List[TextBlock] = []
    
    def parse_xbrl_csv_files(self, csv_files: List[str], extract_text_blocks: bool = True) -> Dict[str, Any]:
        """
        Parse multiple XBRL CSV files and extract financial metrics and text blocks.

        Args:
            csv_files: List of paths to XBRL CSV files
            extract_text_blocks: Whether to extract narrative text blocks (default True)

        Returns:
            Dictionary of structured financial data and text blocks
        """
        self.metrics = []
        self.text_blocks = []

        for csv_file in csv_files:
            if os.path.exists(csv_file):
                logger.debug(f"Parsing XBRL CSV file: {csv_file}")
                self._parse_single_csv_file(csv_file, extract_text_blocks=extract_text_blocks)
            else:
                logger.warning(f"XBRL CSV file not found: {csv_file}")

        result = self._extract_key_metrics()

        if extract_text_blocks:
            result['text_blocks'] = self._format_text_blocks()

        return result
    
    def _parse_single_csv_file(self, csv_file: str, extract_text_blocks: bool = True) -> None:
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
                        # Check if this is a text block BEFORE parsing as metric
                        element_name = row[0].strip() if len(row) > 0 else ""
                        if extract_text_blocks and self._is_text_block(element_name):
                            # Extract text blocks directly from raw row
                            text_content = row[8].strip() if len(row) > 8 else ""
                            if text_content and len(text_content) > 50:
                                text_block = TextBlock(
                                    element_name=element_name,
                                    japanese_label=row[1].strip() if len(row) > 1 else "",
                                    text_content=text_content
                                )
                                self.text_blocks.append(text_block)
                                parsed_rows += 1
                        else:
                            # Parse as financial metric
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

    def _is_text_block(self, element_name: str) -> bool:
        """Check if this is a narrative text block we want to extract."""
        return element_name in self.NARRATIVE_TEXT_BLOCKS.values() or 'TextBlock' in element_name

    def _format_text_blocks(self) -> Dict[str, Any]:
        """Format extracted text blocks for output."""
        result = {}
        for block in self.text_blocks:
            # Find the key name for this block
            block_key = None
            for key, element in self.NARRATIVE_TEXT_BLOCKS.items():
                if block.element_name == element:
                    block_key = key
                    break

            if not block_key:
                # Use element name as fallback
                block_key = block.element_name.split(':')[-1] if ':' in block.element_name else block.element_name

            result[block_key] = {
                'label': block.japanese_label,
                'content': block.text_content,
                'content_length': len(block.text_content)
            }

        return result

    def search_text_blocks(self, keywords: List[str], context_chars: int = 200) -> Dict[str, List[Tuple[str, str]]]:
        """
        Search all text blocks for keywords.

        Args:
            keywords: List of keywords/patterns to search for
            context_chars: Number of characters of context around matches

        Returns:
            Dict mapping block keys to list of (keyword, context) tuples
        """
        results = {}
        for block in self.text_blocks:
            matches = block.search(keywords, context_chars)
            if matches:
                # Find block key
                block_key = None
                for key, element in self.NARRATIVE_TEXT_BLOCKS.items():
                    if block.element_name == element:
                        block_key = key
                        break
                if not block_key:
                    block_key = block.element_name.split(':')[-1] if ':' in block.element_name else block.element_name

                results[block_key] = matches

        return results
    
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


def extract_mtp_targets(zip_extract_path: str) -> Dict[str, Any]:
    """
    Extract Medium-Term Plan (MTP) targets from EDINET Yuho text blocks.

    This function looks for operating profit targets, revenue targets, and fiscal year goals
    mentioned in the business policy and management strategy sections.

    Args:
        zip_extract_path: Path to extracted ZIP contents

    Returns:
        Dictionary containing MTP targets and related information
    """
    result = {
        'has_mtp_data': False,
        'targets': [],
        'raw_matches': []
    }

    xbrl_csv_dir = os.path.join(zip_extract_path, 'XBRL_TO_CSV')

    if not os.path.exists(xbrl_csv_dir):
        return result

    # Find all CSV files
    csv_files = []
    for filename in os.listdir(xbrl_csv_dir):
        if filename.endswith('.csv'):
            csv_files.append(os.path.join(xbrl_csv_dir, filename))

    if not csv_files:
        return result

    # Parse and extract text blocks
    parser = EdinetXbrlCsvParser()
    data = parser.parse_xbrl_csv_files(csv_files, extract_text_blocks=True)

    if 'text_blocks' not in data or not data['text_blocks']:
        return result

    # Search for MTP-related keywords in text blocks
    mtp_keywords = [
        r'中期経営計画',  # Medium-term management plan
        r'中期.*計画',    # Medium-term plan (variations)
        r'営業利益.*目標', # Operating profit target
        r'目標.*営業利益', # Target operating profit
        r'20\d{2}年.*目標', # Year target (2025, 2027, etc.)
        r'\d+億円.*目標',  # Billion yen target
        r'FY20\d{2}',     # Fiscal year
    ]

    matches = parser.search_text_blocks(mtp_keywords, context_chars=300)

    if matches:
        result['has_mtp_data'] = True
        result['raw_matches'] = matches

        # Try to extract structured targets using regex patterns
        for block_key, match_list in matches.items():
            for keyword, context in match_list:
                # Pattern: operating profit + number + billion yen
                op_pattern = r'営業利益[^\d]*?(\d+(?:,\d+)*)\s*億円'
                op_matches = re.findall(op_pattern, context)

                # Pattern: fiscal year
                fy_pattern = r'(?:FY)?20(\d{2})年?'
                fy_matches = re.findall(fy_pattern, context)

                if op_matches or fy_matches:
                    target_entry = {
                        'block': block_key,
                        'context': context[:200],  # Limit context length
                        'operating_profit_billions': [int(m.replace(',', '')) for m in op_matches] if op_matches else None,
                        'fiscal_years': [f"FY20{y}" for y in fy_matches] if fy_matches else None
                    }
                    result['targets'].append(target_entry)

    logger.info(f"Found {len(result['targets'])} MTP target mentions")
    return result