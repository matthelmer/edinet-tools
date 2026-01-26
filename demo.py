#!/usr/bin/env python3
"""
EDINET Tools Quick Start

Get Japanese corporate filings in 3 lines of code.
"""

import os
from datetime import date
import edinet_tools  # This loads .env automatically


def quick_start():
    """The minimal quick start - get today's documents."""

    # Get today's filings (Japan is ahead, so there's usually data)
    today = date.today().isoformat()
    docs = edinet_tools.documents(today)
    print(f"Found {len(docs)} filings from {today}")

    for doc in docs[:5]:
        print(f"  {doc.doc_id}: {doc.filer_name[:40]} - {doc.doc_type_name}")


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

    # Search multiple results
    results = edinet_tools.search("trading", limit=3)
    print(f"\nSearch 'trading': {len(results)} results")
    for e in results:
        print(f"  {e.ticker or '----'}: {e.name[:50]}")


def parse_document():
    """Download and parse a document."""
    print("\n--- Parse Document ---")

    today = date.today().isoformat()
    docs = edinet_tools.documents(today)

    if not docs:
        print("No documents found - try a weekday")
        return None

    # Find a large holding report (type 350) - common and interesting
    for doc in docs:
        if doc.doc_type_code == "350":
            print(f"Parsing: {doc.doc_id} ({doc.doc_type_name})")
            report = doc.parse()
            print(f"  Parser: {type(report).__name__}")
            print(f"  Fields: {report.fields()[:5]}...")
            if hasattr(report, 'holder_name'):
                print(f"  Holder: {report.holder_name}")
            if hasattr(report, 'target_company'):
                print(f"  Target: {report.target_company}")
            return doc

    # Fallback to first document
    doc = docs[0]
    print(f"Parsing: {doc.doc_id} ({doc.doc_type_name})")
    report = doc.parse()
    print(f"  Parser: {type(report).__name__}")
    print(f"  Fields: {report.fields()[:5]}...")
    return doc


def llm_analysis():
    """Use LLM to generate an executive summary (requires LLM API key)."""
    import tempfile
    from edinet_tools.config import LLM_API_KEY
    from edinet_tools.utils import process_zip_file
    from edinet_tools.analysis import ExecutiveSummaryTool

    print("\n--- LLM Analysis ---")

    if not LLM_API_KEY:
        print("No LLM API key found - skipping")
        print("Set GOOGLE_API_KEY for Gemini or ANTHROPIC_API_KEY for Claude")
        return

    # Get today's documents
    today = date.today().isoformat()
    docs = edinet_tools.documents(today)

    if not docs:
        print("No documents to analyze")
        return

    # Find an interesting document (extraordinary report, quarterly, or large holding)
    doc = None
    for d in docs:
        if d.doc_type_code in ("180", "140", "350"):
            doc = d
            break
    doc = doc or docs[0]

    print(f"Analyzing: {doc.filer_name[:40]}")
    print(f"Type: {doc.doc_type_name}")

    # Fetch and process document
    content = doc.fetch()

    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        structured_data = process_zip_file(temp_path, doc.doc_id, doc.doc_type_code)

        if not structured_data:
            print("Could not extract structured data")
            return

        # Generate executive summary
        tool = ExecutiveSummaryTool()
        result = tool.generate_structured_output(structured_data)

        if result:
            print(f"\n{result.company_name_en}")
            if result.company_description_short:
                print(f"  {result.company_description_short}")
            print(f"\nSummary: {result.summary}")
            if result.key_highlights:
                print("\nKey Points:")
                for h in result.key_highlights[:3]:
                    print(f"  - {h}")
        else:
            print("LLM analysis failed")
    finally:
        os.unlink(temp_path)


def main():
    """Run the demo."""
    # Check API key
    if not os.getenv('EDINET_API_KEY'):
        print("EDINET_API_KEY not set")
        print("Get your free API key at: https://disclosure.edinet-fsa.go.jp/")
        print("\nRunning entity lookup only (no API required)...\n")
        entity_lookup()
        return

    print("EDINET Tools Quick Start")
    print("=" * 40)

    quick_start()
    entity_lookup()
    parse_document()
    llm_analysis()

    print("\n" + "=" * 40)
    print("Getting Started:")
    print("""
  pip install edinet-tools

  import edinet_tools

  # Look up any company
  company = edinet_tools.entity("8058")

  # Get filings for a date
  docs = edinet_tools.documents("2026-01-20")

  # Parse a document
  report = docs[0].parse()

  # LLM analysis (requires API key: ANTHROPIC_API_KEY or OPENAI_API_KEY)
  # Default model: claude-4-sonnet (or set LLM_MODEL env var)
  from edinet_tools.analysis import ExecutiveSummaryTool

  GitHub: https://github.com/matthelmer/edinet-tools
""")


if __name__ == "__main__":
    main()
