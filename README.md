# EDINET Tools

> **Access Japanese corporate disclosure data**

A Python package for Japan's [EDINET](https://disclosure2.edinet-fsa.go.jp/) disclosure system. Clean API, comprehensive testing, and optional LLM-powered analysis.

## Features

**Company Data**
- Search 11,000+ Japanese companies by name or ticker
- Convert ticker symbols to EDINET codes instantly
- Access official government financial disclosure data

**Document Processing**
- Download EDINET filings programmatically
- Extract structured data from XBRL documents
- Handle Japanese text encoding automatically

**Optional AI Analysis**
- Generate executive summaries from financial documents
- One-line insights for quick analysis
- Support for Anthropic, OpenAI, and other LLM providers

## Installation

Install from PyPI:

```bash
pip install edinet-tools
```

Or install from source:

```bash
git clone https://github.com/matthelmer/edinet-api-tools.git
cd edinet-api-tools
pip install -e .
```

## Quick Start

```python
import edinet_tools

# Search companies
companies = edinet_tools.search_companies("Toyota")
print(companies[0]['name_en'])  # TOYOTA MOTOR CORPORATION

# Convert ticker to EDINET code
edinet_code = edinet_tools.ticker_to_edinet("7203")  # E02144

# Initialize client
client = edinet_tools.EdinetClient()

# Get recent filings
filings = client.get_recent_filings(days_back=7)

# Download and analyze a filing (requires LLM API key)
structured_data = client.download_filing(filings[0]['docID'], extract_data=True)

# Batch processing with graceful error handling
results = client.download_filings_batch([f['docID'] for f in filings[:5]])
successful = [r for r in results if r is not None]
print(f"Successfully processed {len(successful)}/{len(results)} documents")

# Graceful single document processing (skip errors)
for filing in filings:
    data = client.download_filing(filing['docID'], raise_on_error=False)
    if data:
        summary = analyze_document_data(data, 'one_line_summary')
        print(f"• {summary}")
    else:
        print(f"• Skipped {filing['docID']} - not available")
```

## Configuration

Set up your environment variables:

```bash
export EDINET_API_KEY=your_edinet_key
export ANTHROPIC_API_KEY=your_anthropic_key
export OPENAI_API_KEY=your_openai_key
```

Or create a `.env` file:

```dotenv
EDINET_API_KEY=your_edinet_key

ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_api_key

LLM_MODEL=claude-4-sonnet              # Or gpt-5-mini, gpt-4o, etc.
LLM_FALLBACK_MODEL=gpt-5-mini          # Optional fallback

# Azure OpenAI Configuration (optional)
# AZURE_OPENAI_API_KEY=your_azure_openai_api_key
# AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
# AZURE_OPENAI_API_VERSION=your_azure_openai_api_version
# AZURE_OPENAI_DEPLOYMENT=your_azure_openai_deployment_name
```

**API Keys:**
- **EDINET_API_KEY**: Get from [EDINET website](https://disclosure2.edinet-fsa.go.jp/) (free)
- **ANTHROPIC_API_KEY**: For Claude models (claude-4-sonnet, etc.)
- **OPENAI_API_KEY**: For GPT models (gpt-5, gpt-5-mini, etc.)
- **AZURE_OPENAI_API_KEY**: Enterprise LLM option via Microsoft Azure

## Demo

Run the interactive demo to see the package in action:

```bash
python demo.py
```

This demonstrates:
- Company search and ticker resolution
- Live EDINET document processing
- LLM-powered summaries

## Testing

Run the comprehensive test suite:

```bash
python test_runner.py --all         # Full test suite (198 tests)
python test_runner.py --unit        # Unit tests only (~172 tests, <30s)
python test_runner.py --integration # Integration tests only (~24 tests, requires API key)
python test_runner.py --smoke       # Quick validation (3 tests, <5s)
```

## LLM Analysis

Generate insights from financial documents using a LLM:

```python
from edinet_tools.analysis import analyze_document_data

# Executive summary
summary = analyze_document_data(structured_data, 'executive_summary')

# One-line summary
insights = analyze_document_data(structured_data, 'one_line_summary')
```

**Models**: Claude-4-Sonnet, GPT-5-Mini, GPT-4o, and more via the `llm` library.

## Error Handling

The library provides flexible error handling for both single and batch document processing:

```python
# Traditional approach (raises exceptions)
try:
    data = client.download_filing("S100ABC1")
    process(data)
except DocumentNotFoundError:
    print("Document not found")
except APIError:
    print("API request failed")

# Graceful approach (returns None on error)
data = client.download_filing("S100ABC1", raise_on_error=False)
if data:
    process(data)
else:
    print("Document not available")

# Batch processing (graceful by default)
results = client.download_filings_batch(doc_ids)
for i, (doc_id, data) in enumerate(zip(doc_ids, results)):
    if data:
        print(f"✅ {doc_id}: Success")
    else:
        print(f"⚠️  {doc_id}: Skipped")

# Batch processing (fail-fast mode)
try:
    results = client.download_filings_batch(doc_ids, raise_on_error=True)
except DocumentNotFoundError as e:
    print(f"Batch failed: {e}")
```

## Contributing

Contributions welcome. Run tests before submitting:

```bash
python test_runner.py --all
```

## Disclaimer

Independent project, not affiliated with Japan's Financial Services Agency (FSA).

Official EDINET: [disclosure2.edinet-fsa.go.jp](https://disclosure2.edinet-fsa.go.jp/)

Provided "as is" for informational purposes. Verify data independently.

## License

This project is licensed under the MIT License.
