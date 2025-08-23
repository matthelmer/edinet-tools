# config.py
import os
import logging
from dotenv import load_dotenv

# Load environment variables from project root
project_root = os.path.dirname(os.path.dirname(__file__))  # Go up one level from edinet_tools/
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    # Try loading from current working directory as fallback
    load_dotenv()

EDINET_API_KEY = os.environ.get('EDINET_API_KEY')

# Unified LLM API Key - can be OpenAI, Claude, etc. depending on llm plugin
# We prioritize a generic LLM key, fall back to Claude API key, then OpenAI if only that's set
LLM_API_KEY = os.environ.get('LLM_API_KEY') or os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('OPENAI_API_KEY')

# Specify default LLM model names
LLM_MODEL = os.environ.get('LLM_MODEL', 'claude-4-sonnet') # Default to claude-4-sonnet, can be overridden
LLM_FALLBACK_MODEL = os.environ.get('LLM_FALLBACK_MODEL', 'gpt-5-mini') # Fallback model

AZURE_OPENAI_API_KEY = os.environ.get('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT')


# Check for required keys and log warnings if missing
if not EDINET_API_KEY:
    logging.warning("EDINET_API_KEY not set in .env file.")

if not LLM_API_KEY:
    logging.warning("LLM_API_KEY (or OPENAI_API_KEY) not set in .env file. LLM analysis will not work.")

# Complete EDINET document types mapping
# Based on official EDINET documentation and API specifications
SUPPORTED_DOC_TYPES = {
    "010": "Securities Notification",
    "020": "Amendment Notification (Securities Notification)",
    "030": "Securities Registration Statement",
    "040": "Amended Securities Registration Statement",
    "050": "Withdrawal Request for Registration",
    "060": "Issuance Registration Notification",
    "070": "Amendment Notification (Issuance Registration Notification)",
    "080": "Issuance Registration Statement",
    "090": "Amended Issuance Registration Statement",
    "100": "Supplementary Issuance Registration Document",
    "110": "Issuance Registration Withdrawal Statement",
    "120": "Securities Report",
    "130": "Securities Report (Amended)",
    "135": "Confirmation Document",
    "136": "Amended Confirmation Document",
    "140": "Quarterly Report",
    "150": "Quarterly Report (Amended)",
    "160": "Semi-Annual Report",
    "170": "Semi-Annual Report (Amended)",
    "180": "Extraordinary Report",
    "190": "Amended Extraordinary Report",
    "200": "Parent Company Status Report",
    "210": "Amended Parent Company Status Report",
    "220": "Treasury Stock Purchase Status Report",
    "230": "Amended Treasury Stock Purchase Status Report",
    "235": "Internal Control Report",
    "236": "Amended Internal Control Report",
    "250": "Amended Tender Offer Registration Statement",
    "280": "Amended Tender Offer Report",
    "300": "Amended Statement of Opinion Report",
    "320": "Amended Response to Questions Report",
    "340": "Amended Application for Exemption from Separate Purchase Prohibition",
    "350": "Large Holding Report",
    "360": "Amended Large Shareholding Report",
    "370": "Reference Date Notification",
    "380": "Change Notification",
}
