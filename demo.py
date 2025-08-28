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
    print("EDINET Tools Demo - Japanese Financial Data Analysis")
    print("11,079+ companies | Live documents | LLM analysis")
    
    print("\nCompany Intelligence")
    print("  Search across Japanese companies:")
    
    companies = edinet_tools.search_companies("Mitsubishi", limit=3)
    for company in companies[:3]:
        ticker = company['ticker']
        edinet_code = edinet_tools.ticker_to_edinet(ticker)
        print(f"    {company['name_en']} ({ticker}) → {edinet_code}")
    
    print("\n  Major company lookups:")
    major_tickers = [('7203', 'Toyota Motor'), ('6758', 'Sony Group'), ('9984', 'SoftBank Group')]
    for ticker, name in major_tickers:
        edinet_code = edinet_tools.ticker_to_edinet(ticker)
        print(f"    {ticker} ({name}) → {edinet_code}")


def demo_live_document_processing():
    """Demonstrate processing of recent Japanese corporate filings."""
    print("\nLive Document Processing")
    
    # Check API keys
    edinet_key = os.getenv('EDINET_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('LLM_API_KEY')
    
    if not edinet_key or not anthropic_key:
        print("  API keys required:")
        if not edinet_key:
            print("    EDINET_API_KEY → disclosure.edinet-fsa.go.jp")
        if not anthropic_key:
            print("    ANTHROPIC_API_KEY → claude.ai")
        print("  Demo: Download and analyze recent filings")
        return
    
    try:
        from datetime import datetime, timedelta
        
        # Initialize client
        client = edinet_tools.EdinetClient()
        print("  Connected to EDINET")
        
        # Find recent filings, skip document type 135
        print("  Scanning for recent filings...")
        
        successful_data = []
        for days_back in range(7):  # Search up to a week back
            date = datetime.now() - timedelta(days=days_back)
            if date.weekday() >= 5:  # Skip weekends
                continue
                
            date_str = date.strftime('%Y-%m-%d')
            try:
                documents = client.get_documents_by_date(date_str)
                if not documents:
                    continue
                    
                print(f"    {date_str}: {len(documents)} filings found")
                
                # Sort by submission time (most recent first)
                sorted_docs = sorted(documents, 
                                   key=lambda x: x.get('submitDateTime', ''), 
                                   reverse=True)
                
                for doc in sorted_docs:
                    # Skip document type 135
                    if doc.get('docTypeCode') == '135':
                        continue
                        
                    # Try to download and extract data
                    data = client.download_filing(doc['docID'], raise_on_error=False)
                    if data:
                        # Get company name (English if available)
                        company_name = doc['filerName']
                        edinet_code = doc.get('edinetCode')
                        if edinet_code:
                            try:
                                company_info = edinet_tools.get_company_info(edinet_code)
                                if company_info and company_info.get('name_en'):
                                    company_name = company_info['name_en']
                            except:
                                pass
                        
                        # Try analysis
                        try:
                            summary = analyze_document_data(data, 'one_line_summary')
                            successful_data.append({
                                'company': company_name,
                                'date': doc.get('submitDateTime', '')[:10],
                                'summary': summary,
                                'doc_id': doc['docID']
                            })
                            
                            if len(successful_data) >= 5:
                                break
                        except:
                            continue
                
                if len(successful_data) >= 5:
                    break
                    
            except Exception:
                continue
        
        # Display results
        print(f"\n  Successfully analyzed {len(successful_data)} filings:")
        for i, item in enumerate(successful_data, 1):
            company = item['company'][:40] + '...' if len(item['company']) > 40 else item['company']
            print(f"    {i}. {company}")
            print(f"       {item['date']} | {item['doc_id']}")
            print(f"       {item['summary']}")
            print()
        
        if len(successful_data) == 0:
            print("    No filings available for analysis at this time")
        
    except Exception as e:
        print(f"  Error: {e}")


def demo_getting_started():
    """Show getting started information."""
    print("\nGetting Started")
    print("  pip install edinet-tools")
    print("  Set EDINET_API_KEY and ANTHROPIC_API_KEY in environment")
    print("  import edinet_tools")
    print("  client = edinet_tools.EdinetClient()")
    print("\n  GitHub: matthelmer/edinet-api-tools")


def main():
    """Run live EDINET Tools demo."""
    demo_company_intelligence()
    demo_live_document_processing()
    demo_getting_started()
    
    print("\nDemo complete - ready to analyze EDINET filings.")

if __name__ == "__main__":
    main()
