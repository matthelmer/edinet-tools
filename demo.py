#!/usr/bin/env python3
"""
EDINET Tools — Quick Start Demo

Demonstrates entity lookup, document listing, typed parsing,
and doc type registry. Run with an EDINET API key for the full
experience, or without one for entity-only features.

  python demo.py
"""

import os
from datetime import timedelta
import edinet_tools


def _get_recent_docs(max_days_back=5):
    """Get documents from today (JST) or the most recent filing day."""
    today = edinet_tools.today_jst()
    for i in range(max_days_back):
        d = today - timedelta(days=i)
        docs = edinet_tools.documents(d.isoformat())
        if docs:
            if i > 0:
                print(f"  (No filings today — using {d})")
            return docs, d
    return [], today


# ── 1. Entity lookup (no API key needed) ──────────────────────────

def entity_lookup():
    """Look up companies by ticker, EDINET code, or name."""
    print("\n--- Entity Lookup ---")

    # By ticker
    mitsubishi = edinet_tools.entity("8058")
    print(f"Ticker 8058: {mitsubishi.name} ({mitsubishi.edinet_code})")

    # By EDINET code
    same = edinet_tools.entity("E02529")
    print(f"Code E02529: {same.name}")

    # By name search
    toyota = edinet_tools.entity("Toyota")
    print(f"Search 'Toyota': {toyota.name} ({toyota.ticker})")

    # Multiple results
    results = edinet_tools.search("trading", limit=3)
    print(f"\nSearch 'trading': {len(results)} results")
    for e in results:
        print(f"  {e.ticker or '----'}: {e.name[:50]}")


# ── 2. Document listing ───────────────────────────────────────────

def list_documents():
    """Fetch the latest day's filings and show a summary."""
    print("\n--- Recent Documents ---")

    docs, filing_date = _get_recent_docs()
    print(f"Found {len(docs)} filings from {filing_date}")

    for doc in docs[:5]:
        print(f"  {doc.doc_id}: {doc.filer_name[:40]} — {doc.doc_type_name}")

    return docs


# ── 3. Typed parsers ─────────────────────────────────────────────

def parse_large_holding(docs):
    """Parse a large holding report (doc 350) — typed fields."""
    print("\n--- Large Holding Report (Doc 350) ---")

    for doc in docs:
        if doc.doc_type_code == "350":
            report = doc.parse()  # → LargeHoldingReport
            print(f"  Parser:    {type(report).__name__}")
            print(f"  Filer:     {report.filer_name}")
            print(f"  Target:    {report.target_company}")
            if report.ownership_pct is not None:
                print(f"  Ownership: {report.ownership_pct}%")
            if report.prior_ownership_pct is not None:
                print(f"  Prior:     {report.prior_ownership_pct}%")
            if report.purpose:
                preview = report.purpose[:120].replace('\n', ' ')
                print(f"  Purpose:   {preview}...")
            return

    print("  No doc 350 found in the last 5 days")


def parse_treasury_stock(docs):
    """Parse a treasury stock report (doc 220) — typed fields."""
    print("\n--- Treasury Stock Report (Doc 220) ---")

    for doc in docs:
        if doc.doc_type_code == "220":
            report = doc.parse()  # → TreasuryStockReport
            print(f"  Parser:    {type(report).__name__}")
            print(f"  Company:   {report.filer_name}")
            if report.filer_name_en:
                print(f"             {report.filer_name_en}")
            print(f"  Ticker:    {report.ticker}")
            print(f"  Filed:     {report.filing_date}")
            print(f"  Period:    {report.reporting_period}")
            print(f"  Board auth:       {report.has_board_authorization}")
            print(f"  Shareholder auth: {report.has_shareholder_authorization}")
            return

    print("  No doc 220 found in the last 5 days")


def parse_securities_report(docs):
    """Parse a securities report (doc 120) — rich financial data."""
    print("\n--- Securities Report (Doc 120) ---")

    for doc in docs:
        if doc.doc_type_code == "120":
            report = doc.parse()  # → SecuritiesReport
            print(f"  Parser:       {type(report).__name__}")
            print(f"  Company:      {report.filer_name}")
            print(f"  Ticker:       {report.ticker}")
            print(f"  FY end:       {report.fiscal_year_end}")
            print(f"  Consolidated: {report.is_consolidated}")
            if report.net_sales is not None:
                print(f"  Net sales:    ¥{report.net_sales:,}")
            if report.operating_income is not None:
                print(f"  Op. income:   ¥{report.operating_income:,}")
            if report.roe is not None:
                print(f"  ROE:          {report.roe}%")
            if report.equity_ratio is not None:
                print(f"  Equity ratio: {report.equity_ratio}%")
            return

    print("  No doc 120 found in the last 5 days")


# ── 4. Doc type registry ─────────────────────────────────────────

def doc_type_registry():
    """Browse the document type registry."""
    print("\n--- Doc Type Registry ---")

    all_types = edinet_tools.doc_types()
    print(f"{len(all_types)} document types registered\n")

    for dt in sorted(all_types, key=lambda t: t.code):
        print(f"  {dt.code}: {dt.name_en} ({dt.name_jp})")


# ── Main ──────────────────────────────────────────────────────────

def main():
    has_api_key = bool(os.getenv('EDINET_API_KEY'))

    print("EDINET Tools Quick Start")
    print("=" * 40)

    # Entity lookup works without an API key
    entity_lookup()
    doc_type_registry()

    if not has_api_key:
        print("\n" + "-" * 40)
        print("Set EDINET_API_KEY for document features.")
        print("Get a free key: https://disclosure.edinet-fsa.go.jp/")
    else:
        docs = list_documents()
        if docs:
            parse_large_holding(docs)
            parse_treasury_stock(docs)
            parse_securities_report(docs)

    print("\n" + "=" * 40)
    print("Getting Started:\n")
    print("  pip install edinet-tools\n")
    print("  import edinet_tools\n")
    print("  # Look up any company")
    print('  company = edinet_tools.entity("7203")')
    print(f"  # → {edinet_tools.entity('7203').name}\n")
    print("  # Get filings for a date")
    print('  docs = edinet_tools.documents("2026-01-20")\n')
    print("  # Parse → typed report object")
    print("  report = docs[0].parse()")
    print("  # → SecuritiesReport, LargeHoldingReport, etc.\n")
    print("  GitHub: https://github.com/matthelmer/edinet-tools")


if __name__ == "__main__":
    main()
