"""
Entity classification for EDINET filers using official FSA data.

Uses two official data sources:
- EdinetcodeDlInfo.csv: All EDINET-registered entities
- FundcodeDlInfo.csv: Investment fund registry

IMPORTANT: Uses official data only. No keyword matching.
"""
from enum import Enum
from pathlib import Path
import csv
import re
import glob


class EntityType(Enum):
    """Classification of EDINET-registered entities."""
    FUND = "fund"
    LISTED_COMPANY = "listed_company"
    UNLISTED_COMPANY = "unlisted_company"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"


class EntityClassifier:
    """
    Classify EDINET entities using official FSA data.

    Data sources:
    - EdinetcodeDlInfo.csv: All EDINET-registered entities (11,000+ entities)
    - FundcodeDlInfo.csv: Investment fund registry (6,000+ funds, ~300 unique issuers)

    IMPORTANT: Uses official data only. No keyword matching.

    Usage:
        classifier = EntityClassifier()
        classifier.get_entity_type('E00001')  # -> EntityType.LISTED_COMPANY
        classifier.is_fund('E12345')          # -> True
        classifier.is_listed('E00001')        # -> True
        classifier.is_known('E99999')         # -> False (stale data indicator)
    """

    def __init__(self, edinet_codes_path: str = None, fund_codes_path: str = None):
        """
        Initialize classifier with data files.

        Args:
            edinet_codes_path: Path to EdinetcodeDlInfo CSV (auto-detected if None)
            fund_codes_path: Path to FundcodeDlInfo CSV (auto-detected if None)
        """
        self.edinet_codes_path = edinet_codes_path or self._find_latest_file('EdinetcodeDlInfo')
        self.fund_codes_path = fund_codes_path or self._find_latest_file('FundcodeDlInfo')

        if not self.edinet_codes_path:
            raise FileNotFoundError("No EdinetcodeDlInfo CSV found in data directory")
        if not self.fund_codes_path:
            raise FileNotFoundError("No FundcodeDlInfo CSV found in data directory")

        # Extract dates from filenames for version tracking
        self.edinet_codes_date = self._extract_date(self.edinet_codes_path)
        self.fund_codes_date = self._extract_date(self.fund_codes_path)

        self._load_data()

    def _find_latest_file(self, prefix: str) -> str | None:
        """Find the latest dated file matching prefix in data directory."""
        data_dir = Path(__file__).parent / 'data'
        pattern = str(data_dir / f'{prefix}*.csv')
        matches = glob.glob(pattern)

        if not matches:
            return None

        # Sort by filename (dated files will sort chronologically)
        matches.sort(reverse=True)
        return matches[0]

    def _extract_date(self, path: str) -> str:
        """Extract date from filename like 'EdinetcodeDlInfo_20251205.csv'."""
        match = re.search(r'_(\d{8})\.csv$', str(path))
        if match:
            d = match.group(1)
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return "unknown"

    def _load_data(self):
        """Load and index both CSV files."""
        self._fund_edinet_codes = set()
        self._edinet_entities = {}  # edinet_code -> entity info

        # Load fund codes (Shift-JIS encoded)
        # Column 7 is the EDINET code of the fund issuer
        with open(self.fund_codes_path, 'r', encoding='cp932', errors='replace') as f:
            reader = csv.reader(f)
            next(reader)  # Skip metadata row
            next(reader)  # Skip header row
            for row in reader:
                if len(row) >= 8:
                    edinet_code = row[7].strip()
                    if edinet_code.startswith('E'):
                        self._fund_edinet_codes.add(edinet_code)

        # Load EDINET codes (Shift-JIS encoded)
        # Columns: 0=EDINET Code, 1=Type, 2=Listed/Unlisted, 6=Name JP, 7=Name EN, 11=Securities Code
        with open(self.edinet_codes_path, 'r', encoding='cp932', errors='replace') as f:
            reader = csv.reader(f)
            next(reader)  # Skip metadata row
            next(reader)  # Skip header row
            for row in reader:
                if len(row) >= 7:
                    edinet_code = row[0].strip()
                    if edinet_code.startswith('E'):
                        self._edinet_entities[edinet_code] = {
                            'submitter_type': row[1].strip(),
                            'is_listed': row[2].strip() == 'Listed company',
                            'name_jp': row[6].strip() if len(row) > 6 else None,
                            'name_en': row[7].strip() if len(row) > 7 else None,
                            'securities_code': row[11].strip() if len(row) > 11 else None,
                        }

    def get_entity_type(self, edinet_code: str) -> EntityType:
        """
        Determine entity type from official data.

        Args:
            edinet_code: EDINET code (e.g., 'E00001')

        Returns:
            EntityType classification
        """
        if not edinet_code:
            return EntityType.UNKNOWN

        # Check if it's a fund issuer first (fund issuers are in both lists)
        if edinet_code in self._fund_edinet_codes:
            return EntityType.FUND

        # Check EDINET registry
        entity = self._edinet_entities.get(edinet_code)
        if not entity:
            return EntityType.UNKNOWN

        # Check submitter type for individuals
        # Japanese: '個人' means individual
        if '個人' in entity['submitter_type']:
            return EntityType.INDIVIDUAL

        # Listed vs unlisted company
        if entity['is_listed']:
            return EntityType.LISTED_COMPANY
        else:
            return EntityType.UNLISTED_COMPANY

    def is_fund(self, edinet_code: str) -> bool:
        """Check if entity is an investment fund issuer."""
        return edinet_code in self._fund_edinet_codes

    def is_listed(self, edinet_code: str) -> bool:
        """Check if entity is a listed company."""
        entity = self._edinet_entities.get(edinet_code)
        return entity is not None and entity.get('is_listed', False)

    def is_known(self, edinet_code: str) -> bool:
        """
        Check if entity exists in our data.

        Returns False for unknown codes, which indicates either:
        - Stale reference data (need to update CSVs)
        - Invalid EDINET code
        """
        return edinet_code in self._edinet_entities or edinet_code in self._fund_edinet_codes

    def get_securities_code(self, edinet_code: str) -> str | None:
        """
        Get 4-digit securities code for listed companies.

        Args:
            edinet_code: EDINET code

        Returns:
            4-digit securities code (e.g., '7203' for Toyota) or None
        """
        entity = self._edinet_entities.get(edinet_code)
        if entity and entity.get('securities_code'):
            code = entity['securities_code']
            # Convert 5-digit (12340) to 4-digit (1234)
            if len(code) == 5 and code.endswith('0'):
                return code[:4]
            return code if code else None
        return None

    def get_entity_name(self, edinet_code: str, prefer_english: bool = True) -> str | None:
        """
        Get entity name.

        Args:
            edinet_code: EDINET code
            prefer_english: If True, return English name if available

        Returns:
            Entity name or None
        """
        entity = self._edinet_entities.get(edinet_code)
        if not entity:
            return None

        if prefer_english and entity.get('name_en'):
            return entity['name_en']
        return entity.get('name_jp')

    @property
    def data_version(self) -> dict:
        """Return data file versions for staleness tracking."""
        return {
            'edinet_codes': self.edinet_codes_date,
            'fund_codes': self.fund_codes_date
        }

    @property
    def stats(self) -> dict:
        """Return statistics about loaded data."""
        listed = sum(1 for e in self._edinet_entities.values() if e['is_listed'])
        return {
            'total_entities': len(self._edinet_entities),
            'listed_companies': listed,
            'unlisted_entities': len(self._edinet_entities) - listed,
            'fund_issuers': len(self._fund_edinet_codes)
        }

    def __repr__(self) -> str:
        return (
            f"EntityClassifier("
            f"entities={len(self._edinet_entities)}, "
            f"funds={len(self._fund_edinet_codes)}, "
            f"version={self.data_version})"
        )
