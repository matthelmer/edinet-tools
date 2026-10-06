# edinet-tools

[![PyPI](https://img.shields.io/pypi/v/edinet-tools)](https://pypi.org/project/edinet-tools/)
[![Downloads](https://static.pepy.tech/badge/edinet-tools)](https://pepy.tech/project/edinet-tools)
[![Tests](https://github.com/matthelmer/edinet-tools/actions/workflows/test.yml/badge.svg)](https://github.com/matthelmer/edinet-tools/actions/workflows/test.yml)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/matthelmer/edinet-tools/blob/main/LICENSE)

Read Japan's EDINET regulatory filings as typed Python objects: financial
reports, 5% shareholding disclosures, tender offers and more.
Each filing can be read from EDINET's CSV conversion, from the filing's own
inline XBRL, or from its XBRL instance.

Python 3.10+. No runtime dependencies. Company lookup works offline;
fetching filings requires a free EDINET API key.

## Install and configure

```bash
pip install edinet-tools
export EDINET_API_KEY=your_key_here
```

Get your key from [EDINET API registration](https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1)
([video walkthrough](https://youtu.be/2ao-CZS-BtQ?t=63)). You can also set it
in Python with `edinet_tools.configure(api_key="...")`.

**Upgrading to 0.9.0:** financial values, currency selection and per-holder
share totals change even on the default CSV path. Read
[MIGRATING.md](https://github.com/matthelmer/edinet-tools/blob/main/MIGRATING.md) before re-parsing stored reports.

## Parse an annual report

This example reads Toyota's annual report filed June 10, 2026. The document
ID identifies a specific filing; it is not a request for the latest report.

```python
import edinet_tools

report = edinet_tools.fetch_and_parse("S100Y8NY", "120")
print(report.net_sales)
print(report.net_income_owners)
print(report.accounting_standard)
print(report.source_elements.get("net_sales"))
print(report.units.get("net_sales"))
```

Financial parsers read the filing's declared accounting standard first:
J-GAAP, IFRS or US GAAP. Listed fallbacks remain where no eligible fact is
found on that standard. `source_elements`, `source_contexts` and `units`
identify the selected source on annual, quarterly and semi-annual reports.
Other report types expose those maps but leave them empty.

An absent field or provenance entry is not a zero. A typed value can be
`None` when no eligible fact is found or an extraction check withholds it;
`extraction_flags` records the checks that produced flags. An empty flags
list does not establish completeness or correctness.

## Find companies and filings

Company lookup uses bundled FSA registry snapshots and needs no API key.

```python
import edinet_tools

toyota = edinet_tools.entity("7203")
print(toyota.name, toyota.edinet_code)

edinet_tools.entity("Toyota")
edinet_tools.entity("E02144")
edinet_tools.entity_by_corporate_number("1180301018771")
edinet_tools.search("bank", limit=5)
```

Lookup accepts digit or alphanumeric tickers and handles width, gaiji and
middle-dot variants in names. The bundled snapshots are dated October 5,
2026. Loading data older than a year emits `StaleDataWarning`.

List a day's annual filings, then select by the filer's EDINET code:

```python
import edinet_tools

docs = edinet_tools.documents("2026-06-10", doc_type="120")
for doc in docs:
    if doc.filer_edinet_code == "E02144":
        print(doc.doc_id, doc.doc_description, doc.filing_datetime)
```

A quiet day returns an empty list. `toyota.documents(doc_type="120",
days=365)` scans a year, making a document-list request for each day.
For chronology, use the document-list submission metadata. Some report
types' tagged `filing_date` can retain the original date after an amendment.

## Choose a source

| Source | How to read it | Useful for |
|---|---|---|
| CSV, the default | `doc.parse()` | EDINET's CSV conversion, compatible with existing workflows |
| Inline XBRL | `doc.parse(source="xbrl")` | Original text sections, table boundaries and native fact metadata |
| XBRL instance | `doc.parse(source="instance")` | The `.xbrl` file in the same package, including packages whose inline HTML is unsupported |

`"ixbrl"` is an alias for `"xbrl"`. The CSV source downloads type 5;
the two native sources download type 1. The inline reader raises
`UnsupportedInlineXBRL` for unsupported constructs instead of guessing.
Catch native-reader errors through `edinet_tools.exceptions.EdinetError`;
`UnsupportedInlineXBRL` is not exported from the top-level package.
Choosing the instance reader is explicit; there is no automatic fallback.

To parse a saved type-1 package without an API key:

```python
from pathlib import Path
from edinet_tools import parse_xbrl
from edinet_tools.parsers.xbrl_rows import extract_rows_from_package

zip_bytes = Path("S100Y4NW_type1.zip").read_bytes()
report = parse_xbrl(zip_bytes, "240", source="xbrl", doc_id="S100Y4NW")

files = extract_rows_from_package(zip_bytes, source="xbrl")
for file in files:
    for row in file["data"]:
        print(row["要素ID"], row["値"], row["コンテキストID"])
```

Download a package with `doc.fetch(type=1)` or
`edinet_tools.api.fetch_document(doc_id, type=1)`. Type 2 returns PDF;
type 5 returns CSV. Source rows also retain HTML, decimals, scale, sign,
nil status and period dates.

The native path preserves text beyond the CSV's 30,000-character cut. For
example, S100Y4NW's tender-offer purpose section has 75,894 characters.
Text tables retain tabs between cells and newlines between rows. Source
choice can also affect typed values in multi-series fund packages; inspect
their field identities before combining figures.

## Other report types

Parse a joint 5% shareholding filing:

```python
import edinet_tools

report = edinet_tools.fetch_and_parse("S100YRDM", "350")
print(report.filer_name, report.target_company)
print(report.ownership_pct, report.is_joint_filing)
for holder in report.joint_holders:
    print(holder.name_jp, holder.shares_held, holder.stock_lines_held)
```

On a joint filing, `ownership_pct` is the co-filers' group total.
Each holder's `shares_held` is the filed total after deductions and can
be zero or negative. `stock_lines_held` counts stock lines before deductions;
it excludes depositary receipts, trust certificates, warrants and
convertibles. The member totals need not sum to the group total.

Parse a tender-offer registration:

```python
import edinet_tools

report = edinet_tools.fetch_and_parse("S100Y4NW", "240")
print(report.acquirer_name, report.target_name)
print(report.holding_ratio_after)
```

Every report supports `fields()` and `to_dict()`. Unmapped elements and
narrative sections remain available through `raw_fields`,
`unmapped_fields`, `text_blocks` and `raw_facts`.

## Coverage and limits

All 42 EDINET document codes route to typed parsers. This does not imply
complete field extraction for every legal form. Amendments share their
base parser; amendment attributes vary between report types.

For financial reports, keep owners-of-parent and whole-group figures
separate: `net_income_owners` versus `net_income_total`, and
`net_assets_owners` versus `net_assets_total`. J-GAAP filers do not file a
single owners-only net-assets element. Unit provenance matters when
storing monetary figures, and segment rows require a checked denominator
and scope before summing.

<details>
<summary>All 42 document codes</summary>

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

</details>

<details>
<summary>Detailed extraction and source limits</summary>

- EDINET stops serving a filing once its public-inspection period ends, so an expired document can no longer be downloaded. Keep the packages you need.
- Some filers' inline files are HTML 4 rather than XHTML. The inline reader refuses them, and `source="instance"` reads them.
- Where a filing's highlights table and its statements disagree, the parser follows a documented order and does not judge which figure is right. `source_elements` shows which was read.
- A package containing several sub-funds can produce different typed values on CSV and XBRL because their file orders differ. A report-wide identity does not establish the sub-fund of every field; inspect the source rows before using these values together.
- The instance reader cannot distinguish an escaped non-TextBlock string from plain text. Such a value can contain HTML that the inline reader renders as text.

- A report's `filing_date` can be the original cover date even when its content is amended. This includes quarterly 150, half-year 170, holdings 360, tender 250/300, internal-control 236, extraordinary 190 and fund-registration 040. Use document-list submission metadata for chronology. An amended extraordinary report's tagged reason can also belong to the original; the amendment's own correction document is not read.
- `ExtraordinaryReport.event_type` is a keyword guess from the reason text. It does not establish which entity had an event: a subsidiary's dissolution can produce `dissolution` for the parent's report. Read the source reason and content before attributing an event.
- Shelf supplement (100) `planned_amount` describes the parent shelf's ceiling; `remaining_balance` is the filed 【残高】. Use `offering_amount_text` for this supplement's offering and `remaining_amount_text` for 【残額】. These are filed text sections, not calculated amounts.

- Supported document codes do not imply complete coverage of every form. Typed fields are incomplete for issuer self-tenders (`jptoi_cor`), investment-corporation buybacks (`jpsps-sbr_cor`), investment-corporation shelf forms (080/100 under `jpsps_cor`), and company-form registrations (030/040 under `jpcrp_cor`). Read the original source facts when fields are missing.
- Segment rows can include subtotals and different periods, scopes and metrics. They are not automatically additive or necessarily a revenue table; the parser does not reconstruct the presentation hierarchy. `segments_extraction_incomplete=True` means incomplete or uncertain extraction, including total-only evidence. `False` does not establish completeness. Inspect the rows and source before summing.
- `text_blocks` is keyed only by element name; repeated contexts overwrite earlier entries. It can contain a parent-only note instead of the consolidated note or only one director's entry. Use `raw_facts` with element/context identity for all occurrences; per-holder text has its own holder-aware interface.
- Some legacy typed strings and top-level text sections represent a nil fact as `－`. Do not globally convert filed dashes to missing values: use the native fact's `nil` metadata when the distinction matters. `raw_facts` in a typed report is a CSV-shaped view, not a substitute for that native metadata.
- `joint_holder_count` counts parsed holder sections, including departing holders; it can differ from the cover's current-group count. Group denominator/date fields require group evidence on a joint report and may be `None` even when member rows agree.

</details>

See the [CHANGELOG](https://github.com/matthelmer/edinet-tools/blob/main/CHANGELOG.md) for the full known limits and
[MIGRATING.md](https://github.com/matthelmer/edinet-tools/blob/main/MIGRATING.md) for changes to stored-data semantics.

## Development

```bash
git clone https://github.com/matthelmer/edinet-tools.git
cd edinet-tools
python -m pip install -e ".[dev]"
python -m pytest tests/ -q
```

Tests cover real filings, accounting standards, context and currency
selection, numeric precision, API errors and native-reader refusals.

## License

MIT. Independent project, not affiliated with Japan's Financial Services
Agency. Verify data independently before making financial decisions.
