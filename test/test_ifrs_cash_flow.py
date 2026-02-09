"""
Test IFRS cash flow extraction.

Tests both IFRS (JAL) and Japan GAAP (Shizuki Electric) companies to ensure
the 4-tier fallback logic works for both accounting standards.

These are integration tests that fetch real data from EDINET API.
"""
import pytest
from edinet_tools import entity_by_ticker, parse


@pytest.mark.integration
def test_ifrs_company():
    """Test IFRS company (JAL - Airlines) extracts cash flows correctly."""
    
    jal = entity_by_ticker('9201')
    docs = list(jal.documents(days=730))
    sec_report = [d for d in docs if d.doc_type_code == '120'][0]
    
    report = parse(sec_report)
    
    # Verify accounting standard
    assert report.accounting_standard == 'IFRS', "JAL should use IFRS"

    # Verify cash flows are extracted (not None or 0)
    assert report.operating_cash_flow, "Operating CF should be extracted"
    assert report.investing_cash_flow, "Investing CF should be extracted"
    assert report.financing_cash_flow, "Financing CF should be extracted"

    # Verify values are reasonable (JAL is a large airline)
    assert report.operating_cash_flow > 100e9, "Operating CF should be >¥100B"
    assert report.investing_cash_flow < 0, "Investing CF should be negative (CapEx)"

    # FCF should be positive for airlines in recovery
    fcf = report.operating_cash_flow + report.investing_cash_flow
    assert fcf > 0, f"FCF should be positive, got ¥{fcf/1e9:.2f}B"

@pytest.mark.integration
def test_japan_gaap_company():
    """Test Japan GAAP company (Shizuki Electric) still works (regression test)."""
    
    shizuki = entity_by_ticker('6994')
    docs = shizuki.documents(doc_type='120', days=730)
    latest = docs[0]
    
    report = parse(latest)
    
    # Verify accounting standard
    assert report.accounting_standard == 'Japan GAAP', "Shizuki should use Japan GAAP"

    # Verify cash flows are extracted (regression test - should still work)
    assert report.operating_cash_flow, "Operating CF should be extracted"
    assert report.investing_cash_flow, "Investing CF should be extracted"
    assert report.financing_cash_flow, "Financing CF should be extracted"

    # Verify values are reasonable (Shizuki is a small manufacturer)
    assert report.operating_cash_flow > 1e9, "Operating CF should be >¥1B"
    assert report.investing_cash_flow < 0, "Investing CF should be negative (CapEx)"

    # FCF should be positive
    fcf = report.operating_cash_flow + report.investing_cash_flow
    assert fcf > 0, f"FCF should be positive, got ¥{fcf/1e9:.2f}B"

