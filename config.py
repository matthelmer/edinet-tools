# config.py
import os
import logging
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

EDINET_API_KEY = os.environ.get('EDINET_API_KEY')

# Unified LLM API Key - can be OpenAI, Claude, etc. depending on llm plugin
# We prioritize a generic LLM key, fall back to OpenAI if only that's set
LLM_API_KEY = os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY')

# Specify default LLM model names
LLM_MODEL = os.environ.get('LLM_MODEL', 'gpt-5-mini') # Default to gpt-5-mini, can be overridden
LLM_FALLBACK_MODEL = os.environ.get('LLM_FALLBACK_MODEL', 'claude-4-sonnet') # Fallback model

AZURE_OPENAI_API_KEY = os.environ.get('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT')


# Check for required keys and log warnings if missing
if not EDINET_API_KEY:
    logging.warning("EDINET_API_KEY not set in .env file.")

if not LLM_API_KEY:
    logging.warning("LLM_API_KEY (or OPENAI_API_KEY) not set in .env file. LLM analysis will not work.")

# Define supported document types for filtering/processing
# Add more as needed
SUPPORTED_DOC_TYPES = {
    "160": "Semi-Annual Report",
    "140": "Quarterly Report",
    "180": "Extraordinary Report",
    "350": "Large Holding Report",
    "030": "Securities Registration Statement",
    "120": "Securities Report",
}
