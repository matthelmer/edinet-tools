#!/usr/bin/env python3
"""
EDINET Tools Demo - Japanese Financial Data Analysis

Demonstrates key capabilities: company lookup, document processing, and AI analysis.
"""

import os
import edinet_tools
from edinet_tools.analysis import analyze_document_data


def demo_company_intelligence():
    """Demonstrate company intelligence features."""
    print("╭─────────────────────────────────────────────────╮")
    print("│              EDINET Tools Demo                  │")
    print("│        Japanese Financial Data Analysis         │")
    print("╰─────────────────────────────────────────────────╯")
    
    print("\n▶ Company Intelligence")
    print("  11,079 Japanese companies • Search • Ticker resolution")
    
    print("\n  Search results for 'Mitsubishi' (showing 2 of many):")
    companies = edinet_tools.search_companies("Mitsubishi", limit=2)
    for company in companies[:2]:
        print(f"    {company['name_en']} ({company['ticker']})")
    
    print("\n  Ticker → EDINET resolution:")
    major_tickers = [('7203', 'Toyota'), ('6758', 'Sony'), ('9984', 'SoftBank')]
    for ticker, name in major_tickers:
        edinet_code = edinet_tools.ticker_to_edinet(ticker)
        print(f"    {ticker} ({name}) → {edinet_code}")


def demo_live_document_processing():
    """Demonstrate live document processing with recent filings."""
    print("\n▶ Live Document Processing")
    
    # Check API keys
    edinet_key = os.getenv('EDINET_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('LLM_API_KEY')
    
    if not edinet_key or not anthropic_key:
        print("  ⚠  API keys required")
        if not edinet_key:
            print("    → EDINET_API_KEY (disclosure.edinet-fsa.go.jp)")
        if not anthropic_key:
            print("    → ANTHROPIC_API_KEY (for LLM analysis)")
        print("\n  Demo capabilities:")
        print("    • Download latest EDINET filings")
        print("    • Extract structured data from documents") 
        print("    • Generate LLM analysis (one-line + executive summaries)")
        return
    
    try:
        # Initialize client
        client = edinet_tools.EdinetClient()
        print("  Client initialized")
        
        # Get recent documents
        print("\n  Fetching recent filings...")
        from datetime import datetime, timedelta
        
        # Try recent business days
        for days_back in range(7):
            date = datetime.now() - timedelta(days=days_back)
            if date.weekday() < 5:  # Skip weekends
                date_str = date.strftime('%Y-%m-%d')
                try:
                    documents = client.get_documents_by_date(date_str)
                    if documents and len(documents) > 0:
                        print(f"  Found {len(documents)} documents ({date_str})")
                        
                        # Process first document
                        doc = documents[0]
                        print(f"\n  Processing → {doc['filerName']}")
                        print(f"  Document  → {doc.get('docDescription', 'N/A')}")
                        print(f"  Doc ID    → {doc['docID']}")
                        
                        # Download and extract
                        print("\n  ⏳ Downloading & extracting...")
                        structured_data = client.download_filing(
                            doc['docID'], 
                            extract_data=True, 
                            doc_type_code=doc.get('docTypeCode')
                        )
                        
                        if structured_data:
                            print("  ✓ Data extracted")
                            
                            # Generate LLM analysis
                            print(f"\n  LLM Analysis")
                            print(f"  Generating one-line summary...")
                            summary = analyze_document_data(structured_data, 'one_line_summary')
                            
                            print(f"\n  One-Line Summary:")
                            print(f"  {summary}")
                            
                            print(f"\n  Generating executive summary...")
                            executive_summary = analyze_document_data(structured_data, 'executive_summary')
                            
                            print(f"\n  {executive_summary}")
                            
                            print(f"\n  Next steps:")
                            print(f"    • Process multiple documents • Extract XBRL metrics • Custom analysis")
                            break
                        else:
                            print("    ⚠️  No structured data extracted")
                            continue
                            
                except Exception as e:
                    if days_back == 6:  # Last attempt
                        print(f"    ⚠️  No recent documents found in past week")
                    continue
        
    except Exception as e:
        print(f"  ❌ Demo error: {e}")
        print("  💡 This might be due to API limits or network issues")


def demo_getting_started():
    """Show getting started information."""
    print("\n▶ Getting Started")
    print("  pip install edinet-tools")
    print("  export EDINET_API_KEY=your_key")
    print("  export ANTHROPIC_API_KEY=your_key")
    print("\n  import edinet_tools")
    print("  client = edinet_tools.EdinetClient()")
    print("\n  GitHub: matthelmer/edinet-api-tools")


def main():
    """Run live EDINET Tools demo."""
    demo_company_intelligence()
    demo_live_document_processing()
    demo_getting_started()
    
    print("\n╭─────────────────────────────────────────────────╮")
    print("│  Ready to analyze Japanese financial data!      │")
    print("╰─────────────────────────────────────────────────╯")

if __name__ == "__main__":
    main()