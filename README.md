# EDINET Tools

> **Python SDK for Japanese corporate disclosure data**

Access Japan's [EDINET](https://disclosure2.edinet-fsa.go.jp/) system - the official repository for securities reports, earnings, large shareholding notices, and other regulatory filings from 11,000+ Japanese companies.

```python
import edinet_tools

docs = edinet_tools.documents("2026-01-20")  # Get all filings for a date
report = docs[0].parse()                      # Parse to typed Python object
```

## Why EDINET?

EDINET (Electronic Disclosure for Investors' NETwork) is Japan's equivalent to the SEC's EDGAR. Every listed company in Japan must file:

- **Securities Reports (有価証券報告書)** - Annual reports with full financials
- **Quarterly Reports (四半期報告書)** - Quarterly earnings data
- **Large Shareholding Reports (大量保有報告書)** - 5%+ ownership disclosures
- **Extraordinary Reports (臨時報告書)** - Material events (M&A, executive changes)

This package gives you programmatic access to all of it.

## Installation

```bash
pip install edinet-tools
```

## Quick Start

```python
import edinet_tools

# Look up any company
toyota = edinet_tools.entity("7203")      # By ticker
toyota = edinet_tools.entity("Toyota")    # By name
print(toyota.name, toyota.edinet_code)    # TOYOTA MOTOR CORPORATION E02144

# Search companies
banks = edinet_tools.search("bank", limit=5)

# Get filings (requires EDINET_API_KEY)
docs = toyota.documents(days=30)
for doc in docs[:3]:
    print(f"{doc.filing_datetime}: {doc.doc_type_name}")

# Parse a document into a typed object
report = docs[0].parse()
print(type(report).__name__)  # SecuritiesReport, LargeHoldingReport, etc.

# Or get all documents filed on a specific date
all_filings = edinet_tools.documents("2026-01-20")
```

## Configuration

Get your free API key from [EDINET](https://disclosure2.edinet-fsa.go.jp/) and set it:

```bash
export EDINET_API_KEY=your_key_here
```

Or create a `.env` file in your project:

```dotenv
EDINET_API_KEY=your_edinet_key

# Optional: For LLM-powered analysis
ANTHROPIC_API_KEY=your_anthropic_key   # Claude models
OPENAI_API_KEY=your_openai_key         # GPT models
GOOGLE_API_KEY=your_google_key         # Gemini models

LLM_MODEL=claude-4-sonnet              # Default model (optional)
```

## Document Types

All 30+ EDINET document types are supported. These common types have specialized typed parsers:

| Code | Type | Parser Class |
|------|------|--------------|
| 120 | Securities Report | `SecuritiesReport` |
| 140 | Quarterly Report | `QuarterlyReport` |
| 160 | Semi-Annual Report | `SemiAnnualReport` |
| 180 | Extraordinary Report | `ExtraordinaryReport` |
| 350 | Large Shareholding | `LargeHoldingReport` |

All other document types parse to `RawReport`, which provides access to the underlying XBRL data.

```python
# Filter by document type
earnings = toyota.documents(doc_type="120")

# Get document type info
dt = edinet_tools.doc_type("120")
print(dt.name_en)  # Securities Report
print(dt.name_jp)  # 有価証券報告書

# See all supported types
all_types = edinet_tools.doc_types()
```

## Parsing Documents

Documents parse into typed Python objects with structured fields:

```python
report = doc.parse()

# Large Shareholding Report
if hasattr(report, 'holder_name'):
    print(report.holder_name)
    print(report.target_company)
    print(report.ownership_pct)

# Securities Report
if hasattr(report, 'net_sales'):
    print(report.filer_name)
    print(report.net_sales)
    print(report.fiscal_year_end)

# All reports have these
print(report.fields())      # List available fields
print(report.to_dict())     # Export as dictionary
```

## LLM Analysis (Optional)

Generate executive summaries using Claude, GPT, or Gemini:

```python
from edinet_tools.analysis import ExecutiveSummaryTool
from edinet_tools.utils import process_zip_file
import tempfile

# Fetch document
content = doc.fetch()

# Process to structured data
with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
    f.write(content)
    temp_path = f.name

structured_data = process_zip_file(temp_path, doc.doc_id, doc.doc_type_code)

# Generate summary
tool = ExecutiveSummaryTool()
result = tool.generate_structured_output(structured_data)
print(result.summary)
print(result.key_highlights)
```

Requires the [llm](https://github.com/simonw/llm) library and an API key (Anthropic, OpenAI, or Google).

## Entity Properties

```python
company = edinet_tools.entity("7203")

company.name          # Company name
company.ticker        # Stock ticker (e.g., "7203")
company.edinet_code   # EDINET code (e.g., "E02144")
company.is_listed     # True if publicly traded
company.is_fund_issuer # True if investment fund manager
company.funds         # List of funds (if fund issuer)
```

## Document Properties

```python
doc.doc_id            # EDINET document ID
doc.doc_type_code     # Type code (e.g., "120")
doc.doc_type_name     # English name
doc.filer_name        # Filing company name
doc.filer             # Entity object
doc.filing_datetime   # When filed
doc.period_start      # Reporting period start
doc.period_end        # Reporting period end
```

## Error Handling

```python
from edinet_tools.exceptions import DocumentNotFoundError, APIError

try:
    content = doc.fetch()
    report = doc.parse()
except DocumentNotFoundError:
    print(f"Document not available: {doc.doc_id}")
except APIError as e:
    print(f"API error: {e}")
```

## Testing

```bash
python test_runner.py --unit        # Fast unit tests (~290 tests)
python test_runner.py --integration # API tests (requires key)
python test_runner.py --all         # Everything
```

## Demo

```bash
python demo.py
```

Shows entity lookup, document retrieval, parsing, and LLM analysis.

## Links

- **PyPI**: [pypi.org/project/edinet-tools](https://pypi.org/project/edinet-tools/)
- **GitHub**: [github.com/matthelmer/edinet-tools](https://github.com/matthelmer/edinet-tools)
- **EDINET**: [disclosure2.edinet-fsa.go.jp](https://disclosure2.edinet-fsa.go.jp/)

## License

MIT License

---

*Independent project, not affiliated with Japan's Financial Services Agency. Data provided for informational purposes - verify independently for financial decisions.*
