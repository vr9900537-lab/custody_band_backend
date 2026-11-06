"""
Date and Time Utilities
Conversions for UTC, IST (Indian Standard Time), and Huaten C05 format parser.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

IST_OFFSET = timedelta(hours=5, minutes=30)
IST_TZ = timezone(IST_OFFSET, name="IST")


def current_iso_timestamp() -> str:
    """Returns current ISO 8601 timestamp with local timezone offset."""
    return datetime.now().astimezone().isoformat()


def current_ist_time() -> datetime:
    """Returns current datetime in Indian Standard Time (IST)."""
    return datetime.now(timezone.utc).astimezone(IST_TZ)


def parse_watch_datetime(date_str: str, time_str: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parses Huaten C05 protocol date and time.
    date_str: 'YYMMDD' (e.g. '261102' -> 2026-11-02)
    time_str: 'HHMMSS' (e.g. '092137' -> 09:21:37 UTC)

    Returns:
        (utc_datetime, ist_datetime)
    """
    try:
        if len(date_str) == 6 and len(time_str) == 6:
            year = 2000 + int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])

            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])

            dt_utc = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
            dt_ist = dt_utc.astimezone(IST_TZ)
            return dt_utc, dt_ist
    except Exception:
        pass
    return None, None


def format_utc_to_ist(utc_str: str) -> str:
    """Converts an ISO UTC string or formatted string to human readable IST."""
    try:
        dt = datetime.fromisoformat(utc_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(IST_TZ)
        return ist_dt.strftime("%Y-%m-%d %I:%M:%S %p IST")
    except Exception:
        return utc_str

