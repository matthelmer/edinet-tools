"""
ZIP and CSV extraction utilities for EDINET documents.

Handles in-memory extraction of XBRL CSV data from EDINET ZIP files.
"""
import csv
import io
import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


def extract_csv_from_zip(zip_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract CSV data from EDINET ZIP file bytes.

    Args:
        zip_bytes: Raw bytes of the ZIP file

    Returns:
        List of dicts with 'filename' and 'data' keys.
        Each 'data' is a list of row dicts.
    """
    csv_files = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            for name in zf.namelist():
                # Skip non-CSV files and macOS metadata
                if not name.endswith('.csv'):
                    continue
                if '__MACOSX' in name:
                    continue
                # Skip auditor report files
                if name.split('/')[-1].startswith('jpaud'):
                    continue

                try:
                    csv_data = _read_csv_from_zip(zf, name)
                    if csv_data:
                        csv_files.append({
                            'filename': name.split('/')[-1],
                            'data': csv_data
                        })
                except Exception as e:
                    logger.warning(f"Failed to read CSV {name}: {e}")
                    continue

    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        return []
    except Exception as e:
        logger.error(f"Error extracting ZIP: {e}")
        return []

    return csv_files


def _read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    """Read a single CSV file from a ZIP archive."""
    raw_bytes = zf.read(name)

    # Try multiple encodings (EDINET uses various encodings)
    encodings = ['utf-16le', 'utf-16', 'utf-8', 'shift-jis', 'cp932']
    content = None

    for encoding in encodings:
        try:
            decoded = raw_bytes.decode(encoding)
            # Remove BOM if present
            if decoded.startswith('\ufeff'):
                decoded = decoded[1:]
            content = decoded
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not content:
        logger.warning(f"Could not decode {name} with any encoding")
        return []

    # Parse tab-separated CSV
    rows = []
    try:
        lines = content.strip().split('\n')
        reader = csv.reader(lines, delimiter='\t')

        for row in reader:
            if len(row) >= 9:
                # Clean up values
                cleaned = [_clean_value(col) for col in row]
                rows.append({
                    '要素ID': cleaned[0],      # element_id
                    '項目名': cleaned[1],      # japanese_label
                    'コンテキストID': cleaned[2],  # context_id
                    '相対年度': cleaned[3],    # relative_year
                    '連結・個別': cleaned[4],   # consolidated_or_individual
                    '期間・時点': cleaned[5],   # period_or_instant
                    'ユニットID': cleaned[6],   # unit_id
                    '単位': cleaned[7],        # unit
                    '値': cleaned[8],          # value
                })
    except Exception as e:
        logger.warning(f"Error parsing CSV {name}: {e}")
        return []

    return rows


def _clean_value(value: str) -> str:
    """Clean a CSV cell value."""
    if not value:
        return ''
    cleaned = value.strip()
    # Remove null bytes and control characters
    cleaned = cleaned.replace('\x00', '').replace('\ufeff', '')
    # Remove quotes
    cleaned = cleaned.strip('"').strip("'").strip()
    return cleaned


# --- Parsing utilities (borrowed from corpjapan BaseProcessor) ---

def parse_percentage(value: Any) -> Optional[Decimal]:
    """
    Parse percentage/ratio value to Decimal.

    EDINET Doc 350 stores ratios as decimals (0.0967 = 9.67%).
    Returns as-is without dividing by 100.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in ('', '－', '―', '-', '—', 'N/A', 'n/a'):
            return None
        try:
            cleaned = value.replace('%', '').strip()
            return Decimal(cleaned)
        except Exception:
            return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def parse_int(value: Any) -> Optional[int]:
    """
    Parse integer, handling Japanese formatting.

    Removes commas and converts to int.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip().replace(',', '').replace('，', '')
        if not value or value in ('－', '―', '-', '—'):
            return None
        try:
            return int(float(value))
        except Exception:
            return None
    try:
        return int(value)
    except Exception:
        return None


def parse_date(value: Any) -> Optional[date]:
    """
    Parse date from various formats.

    Supports: YYYY-MM-DD, YYYY/MM/DD, YYYY年MM月DD日
    """
    if value is None:
        return None
    # Check datetime first (it's a subclass of date)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value or value in ('－', '―', '-', '—'):
            return None

        # Try standard formats
        for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        # Try Japanese format (2025年11月20日)
        try:
            cleaned = value.replace('年', '-').replace('月', '-').replace('日', '')
            return datetime.strptime(cleaned, '%Y-%m-%d').date()
        except Exception:
            pass

    return None


def extract_value(
    csv_files: list,
    element_id: str,
    get_last: bool = False,
    context_patterns: Optional[list[str]] = None
) -> Optional[str]:
    """
    Extract value from csv_files by XBRL element ID.

    Args:
        csv_files: List of dicts with 'filename' and 'data' keys
        element_id: XBRL element ID to search for
        get_last: If True, return last occurrence (useful for totals in joint filings)
        context_patterns: List of context patterns to try in order (e.g., ['ConsolidatedMember'])
                         If None, returns first match regardless of context.
    """
    # If context patterns specified, try each in priority order
    if context_patterns:
        for pattern in context_patterns:
            for csv_file in csv_files:
                data = csv_file.get('data', [])
                for entry in data:
                    if entry.get('要素ID') == element_id:
                        context = entry.get('コンテキストID', '')
                        if pattern in context:
                            return entry.get('値')
        return None

    # No context patterns - return first (or last) match
    result = None
    for csv_file in csv_files:
        data = csv_file.get('data', [])
        for entry in data:
            if entry.get('要素ID') == element_id:
                value = entry.get('値')
                if get_last:
                    result = value  # Keep updating to get last
                else:
                    return value  # Return first match
    return result


def get_context_patterns(is_consolidated: bool, period: str) -> list[str]:
    """
    Build context patterns in priority order for financial data extraction.

    XBRL data includes context IDs like "CurrentYearDuration_ConsolidatedMember".
    This function returns patterns to try in order, preferring consolidated
    data for consolidated filers and non-consolidated for others.

    Args:
        is_consolidated: Whether the filer prepares consolidated statements
        period: Period identifier (e.g., 'CurrentYearDuration', 'CurrentQuarterInstant')

    Returns:
        List of context patterns to try in priority order
    """
    if is_consolidated:
        return [
            f"{period}_ConsolidatedMember",
            f"{period}_NonConsolidatedMember",
            period
        ]
    else:
        return [
            f"{period}_NonConsolidatedMember",
            f"{period}_ConsolidatedMember",
            period
        ]


def extract_financial(
    csv_files: list,
    element_id: str,
    period: str,
    is_consolidated: bool,
    ifrs_fallback_map: Optional[dict[str, str]] = None
) -> Optional[int]:
    """
    Extract financial value with context preference and optional IFRS fallback.

    Tries to extract a financial value using context patterns appropriate for
    the filer's consolidation status. If not found and an IFRS fallback map
    is provided, tries the IFRS equivalent element.

    Args:
        csv_files: List of dicts with 'filename' and 'data' keys
        element_id: XBRL element ID to extract (e.g., 'jppfs_cor:NetSales')
        period: Period identifier (e.g., 'CurrentYearDuration')
        is_consolidated: Whether the filer prepares consolidated statements
        ifrs_fallback_map: Optional dict mapping JGAAP element IDs to IFRS equivalents

    Returns:
        Parsed integer value, or None if not found
    """
    patterns = get_context_patterns(is_consolidated, period)

    # Try primary element first
    value_str = extract_value(csv_files, element_id, context_patterns=patterns)
    if value_str:
        return parse_int(value_str)

    # Try IFRS fallback if available
    if ifrs_fallback_map:
        ifrs_element = ifrs_fallback_map.get(element_id)
        if ifrs_element:
            value_str = extract_value(csv_files, ifrs_element, context_patterns=patterns)
            if value_str:
                return parse_int(value_str)

    return None


def categorize_elements(
    csv_files: list,
    element_map: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Categorize all elements from csv_files into three buckets.

    Args:
        csv_files: List of dicts with 'filename' and 'data' keys
        element_map: Dict of field_name -> element_id for mapped fields

    Returns:
        Tuple of (raw_fields, text_blocks, unmapped_fields):
        - raw_fields: ALL elements by element_id (nothing lost)
        - text_blocks: TextBlock elements
        - unmapped_fields: Elements not in element_map (excluding TextBlocks)
    """
    # Build reverse map: element_id -> field_name
    mapped_element_ids = set(element_map.values())

    raw_fields: dict[str, Any] = {}
    text_blocks: dict[str, Any] = {}
    unmapped_fields: dict[str, Any] = {}

    for csv_file in csv_files or []:
        for row in csv_file.get('data', []):
            elem_id = row.get('要素ID', '')
            value = row.get('値')

            if not elem_id or value is None:
                continue

            # Store in raw_fields (everything)
            raw_fields[elem_id] = value

            # Categorize
            if 'TextBlock' in elem_id:
                # TextBlock element
                key = elem_id.split(':')[-1] if ':' in elem_id else elem_id
                text_blocks[key] = value
            elif elem_id not in mapped_element_ids:
                # Unmapped element
                key = elem_id.split(':')[-1] if ':' in elem_id else elem_id
                unmapped_fields[key] = value

    return raw_fields, text_blocks, unmapped_fields
