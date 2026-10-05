# edinet-tools

[![PyPI](https://img.shields.io/pypi/v/edinet-tools)](https://pypi.org/project/edinet-tools/)
[![Downloads](https://static.pepy.tech/badge/edinet-tools)](https://pepy.tech/project/edinet-tools)
[![Tests](https://github.com/matthelmer/edinet-tools/actions/workflows/test.yml/badge.svg)](https://github.com/matthelmer/edinet-tools/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python library for Japan's [EDINET](https://disclosure2.edinet-fsa.go.jp/) disclosure system — the official source for securities reports, shareholding notices, tender offers, and other regulatory filings from listed Japanese companies.

J-GAAP, IFRS, and US-GAAP filers tag the same figure under different XBRL elements. edinet-tools maps them all to one typed Python field, reading the filing's own accounting standard first. For securities, quarterly and semi-annual reports it records which element, context and unit each financial field was read from.

It reads either EDINET's CSV conversion or the filing's own inline XBRL. The XBRL path keeps text sections that the CSV cuts at 30,000 characters.

**Zero runtime dependencies. Typed parsers for all 42 EDINET document types.**

```python
import edinet_tools

toyota = edinet_tools.entity("7203")
docs = toyota.documents(days=30)   # requires EDINET_API_KEY (see Configuration)
if docs:                            # a quiet month returns an empty list
    report = docs[0].parse()  # → SecuritiesReport, LargeHoldingReport, etc.
```

## Install

```bash
pip install edinet-tools
```

Requires Python 3.10+. Standard library only.

> **Upgrading to 0.9.0?** Values change for IFRS and US GAAP filers: a field now reads
> the filing's own standard first, where 0.8.x could return a J-GAAP figure the filing
> also tags. A few fields still fall back to the J-GAAP figure when the filing tags none
> of its own, and `source_elements` shows when. J-GAAP and fund filings read as before. See the [CHANGELOG](CHANGELOG.md) for every changed value
> and key.
>
> Versions before 0.8.1 call EDINET's retired API host and cannot fetch anything.
>
> Upgrading from 0.7.x? 0.8.0 contains breaking changes; see [MIGRATING.md](https://github.com/matthelmer/edinet-tools/blob/main/MIGRATING.md).

## Design

edinet-tools has three layers:

1. **API client** — fetch document listings and download filings in any format (XBRL, PDF, HTML)
2. **Typed parsers** — every EDINET document type routes to a named Python dataclass with structured fields
3. **Full capture** — elements not yet mapped to typed fields are preserved in `raw_fields`, `unmapped_fields`, `text_blocks`, and `raw_facts` (the full XBRL fact set), so you can explore what's available and nothing is silently dropped

Each parser maps known XBRL elements to typed Python fields (dates, decimals, strings). As EDINET evolves or new elements become useful, adding a field is one line in the element map and one line on the dataclass.

If a filing doesn't state a figure, the field is `None`: never a guess, and never a number borrowed from the parent company. A financial field reads the filing's declared standard first. Where a filing tags no fact on its own standard, a field may fall back to another standard's element that the parser lists for it. On securities, quarterly and semi-annual reports, `source_elements` names the element actually read. Every mapping is tested against real filings and cross-checked against issuers' own earnings releases.

## EDINET Document Types

EDINET defines 42 document types spanning corporate disclosure, capital markets activity, and governance reporting. edinet-tools provides typed parsers for all of them.

| Code | Family | Description |
|------|--------|-------------|
| 120, 130 | Securities Reports | Annual reports — financials, governance, business overview (J-GAAP / IFRS / US GAAP) |
| 140, 150 | Quarterly Reports | Quarterly financials (abolished April 2024) |
| 160, 170 | Semi-Annual Reports | Semi-annual reports, primarily investment funds |
| 180, 190 | Extraordinary Reports | Material events — M&A, management changes, restructuring |
| 220, 230 | Treasury Stock | Share buyback authorization and execution status |
| 235, 236 | Internal Control | J-SOX evaluation results — internal control effectiveness |
| 135, 136 | Confirmation Documents | CEO/CFO attestation (primarily PDF) |
| 200, 210 | Parent Company Reports | Parent-subsidiary relationships |
| 350, 360 | Large Shareholding | 5%+ ownership filings — filer, target, ownership percentage |
| 370, 380 | Reference Date / Change Notifications | Notifications under the large shareholding rules (the 5% change report itself is filed as 350) |
| 240, 250 | Tender Offer Registration | Public tender offer filings |
| 260 | Tender Offer Withdrawal | Withdrawal of tender offers |
| 270, 280 | Tender Offer Reports | Tender offer completion — outcome, final holdings |
| 290, 300 | Statement of Opinion | Target company's board opinion on a tender offer |
| 310, 320 | Response to Questions | Regulatory Q&A during tender offer process |
| 330, 340 | Exemption Application | Exemption from separate purchase prohibition |
| 030, 040 | Securities Registration | New securities registration statements (primarily funds) |
| 010, 020 | Securities Notification | Securities issuance notifications |
| 050 | Registration Withdrawal | Withdrawal of securities registration |
| 070, 080, 090 | Shelf Registration | Shelf registration for future bond/equity issuance |
| 060 | Issuance Notification | Issuance registration notifications |
| 100 | Issuance Supplementary | Supplementary shelf registration drawdown documents |
| 110 | Issuance Withdrawal | Withdrawal of issuance registration |

Amendments (even-numbered codes like 130, 150, 190) route to the same parser as their base type and set `is_amendment = True`.

```python
from edinet_tools import supported_doc_types, doc_type

supported_doc_types()  # All 42 codes with typed parsers

dt = doc_type("235")
print(dt.name_en)  # "Internal Control Report"
print(dt.name_jp)  # "内部統制報告書"
```

## Usage

### Entity Lookup

```python
import edinet_tools

toyota = edinet_tools.entity("7203")      # By ticker (digit or alphanumeric)
toyota = edinet_tools.entity("Toyota")    # By name search
toyota = edinet_tools.entity("E02144")    # By EDINET code
print(toyota.name, toyota.edinet_code)    # TOYOTA MOTOR CORPORATION E02144

# Look up by Japan Corporate Number (法人番号)
toyota = edinet_tools.entity_by_corporate_number("1180301018771")

# Name search handles full-width/half-width, gaiji (㈱), and middle-dot variants
mufg = edinet_tools.search("三菱UFJ銀行")  # matches the catalog's ＵＦＪ form too

banks = edinet_tools.search("bank", limit=5)
```

Entity data comes from FSA registry snapshots bundled with the package, so lookup and search work offline. Snapshots are refreshed each release.  Loading one older than a year raises `StaleDataWarning`, and `EntityClassifier` accepts paths to newer CSVs if you download your own.

### Fetching Documents

```python
# All filings for a date (requires EDINET_API_KEY)
docs = edinet_tools.documents("2026-01-20")

# Filter by company and type
earnings = toyota.documents(doc_type="120", days=365)
```

### Parsing

Each block below runs as written (with `EDINET_API_KEY` set) and fetches one real filing.

**Annual securities report** (doc type 120):

```python
doc = earnings[0]   # Toyota's annual report, from the example above
report = doc.parse()

# Consolidated financials (J-GAAP, IFRS, US-GAAP)
report.net_sales
report.operating_cash_flow
report.roe
report.accounting_standard  # "Japan GAAP", "IFRS", or "US GAAP"
report.segments             # list[SegmentRow] — per-segment metrics

# Figures that depend on ownership basis come as explicit pairs (0.8.0)
report.net_income_owners    # attributable to owners of parent
report.net_income_total     # includes non-controlling interests
report.net_assets_total
report.net_assets_owners    # None for J-GAAP filers (never filed as one element)

# Where a financial field came from: securities, quarterly and semi-annual
# reports fill these; other report types leave them empty. A field missing
# from a map means its source was not recorded, not that it has none.
report.source_elements   # field -> XBRL element read
report.source_contexts   # field -> context read
report.units             # monetary / per-share field -> unit id, e.g. "JPY",
                         # "JPYPerShares"; yen is read first when both are filed
```

**Large shareholding (5%) report** (doc type 350):

```python
# A joint report by three holders, filed 2026-07-24
report = edinet_tools.fetch_and_parse("S100YRDM", "350")

report.filer_name
report.target_company
report.ownership_pct        # joint filing → the co-filers' GROUP total, not
report.is_joint_filing      #   the named filer's own stake (~half are joint)
report.joint_holders        # each holder's own name, code and share count
```

**Tender offer registration** (doc type 240):

```python
# Kaga Electronics' offer for Shinko Shoji, filed 2026-05-18
report = edinet_tools.fetch_and_parse("S100Y4NW", "240")

report.acquirer_name
report.target_name
report.holding_ratio_after
```

**Any report:**

```python
report.fields()     # List available typed fields
report.to_dict()    # Export as dictionary
report.raw_fields        # All XBRL elements by element ID
report.text_blocks       # Narrative text block content
report.extraction_flags  # parse-time structural checks (0.8.0): impossible
                         # values are withheld as None, never served
```

### Reading the filing's own XBRL

By default `parse()` reads EDINET's CSV conversion (download type 5), as earlier versions did. Pass `source` to read the filing itself (download type 1):

```python
report = doc.parse(source="xbrl")       # the inline XBRL ("ixbrl" also accepted)
report = doc.parse(source="instance")   # the .xbrl instance in the same package

# Or from bytes you already have
from edinet_tools import parse_xbrl
report = parse_xbrl(zip_bytes, "350", source="xbrl", doc_id="S100Y8GB")
```

What the XBRL path gives you that the CSV does not:

- **Text sections in full.** The CSV cuts every text value at 30,000 characters. A tender-offer registration's purpose section of 75,894 characters reads in full.
- **Cell boundaries in text sections:** a tab between table cells and a newline between rows.

On 5% reports, both sources now keep each joint holder's own text sections, such as each holder's 60-day trading table: `joint_holder.text_blocks` and `report.text_blocks_by_context`.

The typed report carries values. For the HTML of a text section, decimals, scale and each fact's period dates, read the source rows:

```python
from edinet_tools.parsers.xbrl_rows import extract_rows_from_package

files = extract_rows_from_package(zip_bytes, source="xbrl")
for row in files[0]["data"]:
    row["要素ID"], row["値"], row["html"], row["decimals"]
    row["period_start"], row["period_end"]   # a fact over a period
    row["instant"]                           # a fact at a point in time
```

On the filings tested, typed fields match across sources apart from the documented differences (the 30,000-character cut, whitespace, and text the CSV drops around angle brackets). The reader uses only the standard library. It refuses what it does not implement with a named error (`UnsupportedInlineXBRL`) rather than guessing.

### Download Formats

```python
from edinet_tools.api import fetch_document

doc_id = "S100Y8NY"                           # Toyota's annual report, filed 2026-06-10
csv_zip = fetch_document(doc_id)              # XBRL CSV (default)
pdf = fetch_document(doc_id, type=2)          # PDF
filing_zip = fetch_document(doc_id, type=1)   # the filing: inline XBRL, HTML and the .xbrl instance
```

## Configuration

Get a free API key from [EDINET](https://disclosure2.edinet-fsa.go.jp/) ([video walkthrough](https://youtu.be/2ao-CZS-BtQ?t=63)):

```bash
export EDINET_API_KEY=your_key_here
```

Or set it in code with `edinet_tools.configure(api_key="...")`. Entity lookup and parsing work without an API key (document fetching requires one).

## Limitations

- EDINET stops serving a filing once its public-inspection period ends, so an expired document can no longer be downloaded. Keep the packages you need.
- Some filers' inline files are HTML 4 rather than XHTML. The inline reader refuses them, and `source="instance"` reads them.
- Where a filing's highlights table and its statements disagree, the parser follows a documented order and does not judge which figure is right. `source_elements` shows which was read.

The full list is under "Known limits" in the [CHANGELOG](CHANGELOG.md).

## Testing

```bash
pytest tests/ -q  # 3,000+ tests, including real EDINET filings as fixtures
```

## Links

- [Changelog](CHANGELOG.md)
- [PyPI](https://pypi.org/project/edinet-tools/)
- [GitHub](https://github.com/matthelmer/edinet-tools)
- [EDINET](https://disclosure2.edinet-fsa.go.jp/)

## License

MIT

---

*Independent project. Not affiliated with Japan's Financial Services Agency. Verify data independently before making financial decisions.*
