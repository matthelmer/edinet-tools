"""
EDINET Company Data Loader

Downloads and processes official EDINET codes from the Japanese government
and integrates with corporate entity translations.
"""

import csv
import os
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import tempfile
import shutil

logger = logging.getLogger(__name__)

# Official EDINET codes download URL
EDINET_CODES_URL = "https://disclosure2.edinet-fsa.go.jp/weee0020.aspx"
# Alternative direct CSV URL (if available)
EDINET_CSV_URL = "https://disclosure2.edinet-fsa.go.jp/weee0020/EDINET_Code_List.csv"

class EdinetDataLoader:
    """Handles downloading and processing official EDINET company data."""
    
    def __init__(self, data_dir: str = None):
        """
        Initialize the data loader.
        
        Args:
            data_dir: Directory to store downloaded data files. 
                     Defaults to package data directory.
        """
        if data_dir is None:
            # Use package data directory
            package_dir = os.path.dirname(__file__)
            self.data_dir = os.path.join(package_dir, 'data')
        else:
            self.data_dir = data_dir
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.edinet_codes_file = os.path.join(self.data_dir, 'edinet_codes.csv')
        self.translations_file = os.path.join(self.data_dir, 'corporate_entity_translations.csv')
        self.processed_data_file = os.path.join(self.data_dir, 'processed_companies.csv')
    
    def download_edinet_codes(self, force_update: bool = False) -> bool:
        """
        Download the latest EDINET codes from the official government website.
        
        Args:
            force_update: If True, download even if file already exists
            
        Returns:
            True if download was successful, False otherwise
        """
        if not force_update and os.path.exists(self.edinet_codes_file):
            # Check if file is recent (less than 7 days old)
            file_age = datetime.now().timestamp() - os.path.getmtime(self.edinet_codes_file)
            if file_age < 7 * 24 * 3600:  # 7 days in seconds
                logger.info("EDINET codes file is recent, skipping download")
                return True
        
        logger.info("Downloading EDINET codes from official website...")
        
        try:
            # Try direct CSV download first
            with urllib.request.urlopen(EDINET_CSV_URL, timeout=30) as response:
                if response.status == 200:
                    with open(self.edinet_codes_file, 'wb') as f:
                        shutil.copyfileobj(response, f)
                    logger.info(f"Successfully downloaded EDINET codes to {self.edinet_codes_file}")
                    return True
        except urllib.error.URLError as e:
            logger.warning(f"Direct CSV download failed: {e}")
        
        # Fallback: Try to parse the main page (this would need HTML parsing)
        logger.warning("Direct CSV download failed. Manual download may be required.")
        logger.info(f"Please download the EDINET codes manually from {EDINET_CODES_URL}")
        logger.info(f"Save as: {self.edinet_codes_file}")
        return False
    
    def load_translations(self, translation_file: str = None) -> Dict[str, str]:
        """
        Load Japanese to English company name translations.
        
        Args:
            translation_file: Path to translation CSV file
            
        Returns:
            Dictionary mapping Japanese names to English names
        """
        if translation_file is None:
            translation_file = self.translations_file
        
        translations = {}
        
        if not os.path.exists(translation_file):
            logger.warning(f"Translation file not found: {translation_file}")
            return translations
        
        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header row
                for row in reader:
                    if len(row) >= 2 and row[0] and row[1]:
                        translations[row[0]] = row[1]
            
            logger.info(f"Loaded {len(translations)} translations")
        except Exception as e:
            logger.error(f"Error loading translations: {e}")
        
        return translations
    
    def process_edinet_data(self) -> List[Dict]:
        """
        Process the EDINET codes CSV into a clean company dataset.
        
        Returns:
            List of company dictionaries with standardized fields
        """
        if not os.path.exists(self.edinet_codes_file):
            logger.error("EDINET codes file not found. Run download_edinet_codes() first.")
            return []
        
        # Load translations
        translations = self.load_translations()
        
        companies = []
        
        try:
            # Try Shift-JIS encoding first (common for Japanese government files)
            encodings_to_try = ['shift_jis', 'utf-8', 'cp932', 'euc-jp']
            working_encoding = None
            
            for encoding in encodings_to_try:
                try:
                    with open(self.edinet_codes_file, 'r', encoding=encoding) as f:
                        # Read first few lines to check if encoding works
                        lines = f.readlines()
                        if len(lines) > 1 and 'EDINET Code' in lines[1]:
                            working_encoding = encoding
                            logger.info(f"Successfully opened EDINET codes file with {encoding} encoding")
                            break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if working_encoding is None:
                logger.error("Could not decode EDINET codes file with any encoding")
                return []
            
            # Now process the file with the working encoding
            with open(self.edinet_codes_file, 'r', encoding=working_encoding) as f:
                lines = f.readlines()
                
                # Skip metadata line if present, find the header line
                header_line_idx = 0
                for i, line in enumerate(lines):
                    if 'EDINET Code' in line:
                        header_line_idx = i
                        break
                
                # Parse CSV starting from header line
                csv_content = ''.join(lines[header_line_idx:])
                reader = csv.DictReader(csv_content.splitlines())
                
                for row in reader:
                    # Extract key fields
                    edinet_code = row.get("EDINET Code", "").strip()
                    name_ja = row.get("Submitter Name", "").strip()
                    name_en = row.get("Submitter Name（alphabetic）", "").strip()
                    securities_code = row.get("Securities Identification Code", "").strip()
                    industry = row.get("Submitter's industry", "").strip()
                    listed_status = row.get("Listed company / Unlisted company", "").strip()
                    
                    # Skip if missing essential data
                    if not edinet_code or not name_ja:
                        continue
                    
                    # Use translation if available and no English name provided
                    if not name_en and name_ja in translations:
                        name_en = translations[name_ja]
                    
                    # Build company record
                    company = {
                        'edinet_code': edinet_code,
                        'ticker': securities_code if securities_code else None,
                        'name_ja': name_ja,
                        'name_en': name_en if name_en else name_ja,  # Fallback to Japanese
                        'industry': industry,
                        'listed': listed_status == "Listed company",
                        'search_text': f"{name_ja} {name_en} {securities_code}".lower()
                    }
                    
                    companies.append(company)
            
            logger.info(f"Processed {len(companies)} companies from EDINET data")
            
            # Save processed data for faster loading
            self._save_processed_data(companies)
            
            return companies
            
        except Exception as e:
            logger.error(f"Error processing EDINET data: {e}")
            return []
    
    def _save_processed_data(self, companies: List[Dict]):
        """Save processed company data to CSV for faster loading."""
        try:
            with open(self.processed_data_file, 'w', encoding='utf-8', newline='') as f:
                if companies:
                    fieldnames = companies[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(companies)
            logger.info(f"Saved processed data to {self.processed_data_file}")
        except Exception as e:
            logger.error(f"Error saving processed data: {e}")
    
    def load_processed_data(self) -> List[Dict]:
        """Load previously processed company data."""
        if not os.path.exists(self.processed_data_file):
            return []
        
        companies = []
        try:
            with open(self.processed_data_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert string boolean back to actual boolean
                    row['listed'] = row['listed'].lower() == 'true'
                    companies.append(row)
            
            logger.info(f"Loaded {len(companies)} companies from processed data")
            return companies
        except Exception as e:
            logger.error(f"Error loading processed data: {e}")
            return []
    
    def get_companies(self, force_update: bool = False) -> List[Dict]:
        """
        Get complete company dataset, downloading/processing if needed.
        
        Args:
            force_update: If True, force download and reprocess data
            
        Returns:
            List of company dictionaries
        """
        # Try to load existing processed data first
        if not force_update:
            companies = self.load_processed_data()
            if companies:
                return companies
        
        # Download and process if needed
        if force_update or not os.path.exists(self.edinet_codes_file):
            if not self.download_edinet_codes(force_update=force_update):
                logger.error("Failed to download EDINET codes")
                return []
        
        # Process the data
        return self.process_edinet_data()
    


def get_data_loader() -> EdinetDataLoader:
    """Get the default data loader instance."""
    return EdinetDataLoader()