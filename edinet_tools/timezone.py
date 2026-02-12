"""
Japan Standard Time utilities for EDINET.

EDINET filings are dated in JST (UTC+9). Using today_jst() instead of
date.today() ensures you get the correct EDINET business day regardless
of your local timezone.
"""
from datetime import datetime, date, timezone, timedelta

JST = timezone(timedelta(hours=9))


def today_jst() -> date:
    """Get today's date in Japan Standard Time (UTC+9)."""
    return datetime.now(JST).date()
