# EDINET Tools

> **Python SDK for Japanese corporate disclosure data**

Access Japan's [EDINET](https://disclosure2.edinet-fsa.go.jp/) system — the official repository for securities reports, earnings, large shareholding notices, and other regulatory filings from 11,000+ Japanese companies.

```python
import edinet_tools

docs = edinet_tools.documents("2026-01-20")  # Get all filings for a date
report = docs[0].parse()                      # Parse to typed Python object
```

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

# Get all documents filed on a specific date
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
```

## Document Types

All 30+ EDINET document types are supported. These common types have specialized typed parsers:

| Code | Type | Parser Class |
|------|------|--------------|
| 120 | Securities Report | `SecuritiesReport` |
| 140 | Quarterly Report | `QuarterlyReport` |
| 160 | Semi-Annual Report | `SemiAnnualReport` |
| 180 | Extraordinary Report | `ExtraordinaryReport` |
| 220 | Treasury Stock Report | `TreasuryStockReport` |
| 240 | Tender Offer Registration | `TenderOfferReport` |
| 350 | Large Shareholding | `LargeHoldingReport` |

All other document types parse to `RawReport` with access to the underlying XBRL data.

```python
# Filter by document type
earnings = toyota.documents(doc_type="120")

# Get document type info
dt = edinet_tools.doc_type("120")
print(dt.name_en)  # Securities Report
print(dt.name_jp)  # 有価証券報告書
```

## Parsing Documents

Documents parse into typed Python objects with structured fields:

```python
report = doc.parse()

# Large Shareholding Report
if isinstance(report, edinet_tools.LargeHoldingReport):
    print(report.filer_name)
    print(report.target_company)
    print(report.ownership_pct)
    print(report.purpose)

# Securities Report (Japan GAAP and IFRS)
if isinstance(report, edinet_tools.SecuritiesReport):
    print(report.net_sales)
    print(report.operating_cash_flow)
    print(report.fiscal_year_end)
    print(report.roe)

# Treasury Stock Report
if isinstance(report, edinet_tools.TreasuryStockReport):
    print(report.filer_name)
    print(report.ticker)
    print(report.has_board_authorization)

# Tender Offer (TOB)
if isinstance(report, edinet_tools.TenderOfferReport):
    print(report.acquirer_name)
    print(report.target_name)
    print(report.purchase_ratio)
    print(report.holding_ratio_after)

# All reports
print(report.fields())      # List available fields
print(report.to_dict())     # Export as dictionary
```

## Financial Data

Securities Reports extract comprehensive financial data with automatic support for both **Japan GAAP** and **IFRS** accounting standards:

- **Income Statement**: Revenue, operating income, net income, EPS
- **Balance Sheet**: Assets, liabilities, equity, book value per share
- **Debt**: Short/long-term loans, bonds payable, commercial paper, lease obligations
- **Cash Flow**: Operating, investing, and financing cash flows
- **Ratios**: ROE, equity ratio

```python
report = doc.parse()
print(report.accounting_standard)        # "Japan GAAP" or "IFRS"
print(report.operating_cash_flow)
print(report.short_term_loans_payable)
print(report.bonds_payable)
```

## Testing

```bash
pytest tests/ -v              # Full suite (~350 tests)
python test_runner.py --unit  # Unit tests only
```

## Links

- **PyPI**: [pypi.org/project/edinet-tools](https://pypi.org/project/edinet-tools/)
- **GitHub**: [github.com/matthelmer/edinet-tools](https://github.com/matthelmer/edinet-tools)
- **EDINET**: [disclosure2.edinet-fsa.go.jp](https://disclosure2.edinet-fsa.go.jp/)

## License

MIT License

---

*Independent project, not affiliated with Japan's Financial Services Agency. Verify data independently before making financial decisions.*
