"""
Earnings Guard Module
Blocks opening new positions within 5 trading days before earnings,
and flags existing positions 2 days before earnings for review.

Earnings cause ±10-30% unpredictable gaps — technical analysis is
unreliable in that window, so we skip those candidates entirely.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# In-memory cache: ticker → (earnings_datetime | None, cached_at_epoch)
_earnings_cache: dict[str, tuple[datetime | None, float]] = {}
_CACHE_TTL_SECONDS = 86_400  # 24 hours


# ── Public API ────────────────────────────────────────────────────────────────

def is_earnings_risk(ticker: str, block_days: int = 5) -> dict[str, Any]:
    """
    Check whether a ticker is within the earnings-risk window.

    Parameters
    ----------
    ticker     : Ticker symbol
    block_days : Trading days before earnings to block new entries (default 5)

    Returns
    -------
    {
        "blocked":           bool,        # True → do not open position
        "flag_for_review":   bool,        # True → warn on existing position
        "earnings_date":     str | None,  # "YYYY-MM-DD" of next earnings
        "trading_days_away": int | None,
        "reason":            str,
    }
    """
    earnings_dt = _get_next_earnings(ticker)

    if earnings_dt is None:
        return {
            "blocked":           False,
            "flag_for_review":   False,
            "earnings_date":     None,
            "trading_days_away": None,
            "reason":            "no_earnings_date_found",
        }

    days_away = _trading_days_until(earnings_dt)
    earnings_str = earnings_dt.strftime("%Y-%m-%d")

    if days_away <= 2:
        return {
            "blocked":           True,
            "flag_for_review":   True,
            "earnings_date":     earnings_str,
            "trading_days_away": days_away,
            "reason":            f"earnings_in_{days_away}_days_imminent",
        }

    if days_away <= block_days:
        return {
            "blocked":           True,
            "flag_for_review":   False,
            "earnings_date":     earnings_str,
            "trading_days_away": days_away,
            "reason":            f"earnings_in_{days_away}_trading_days",
        }

    return {
        "blocked":           False,
        "flag_for_review":   False,
        "earnings_date":     earnings_str,
        "trading_days_away": days_away,
        "reason":            "earnings_safe_distance",
    }


def clear_cache() -> None:
    """Clear the earnings cache (call at start of each trading day)."""
    _earnings_cache.clear()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_next_earnings(ticker: str) -> datetime | None:
    """Fetch (with caching) the next upcoming earnings date for ticker."""
    now_epoch = time.time()
    cached = _earnings_cache.get(ticker)
    if cached is not None:
        earnings_dt, cached_at = cached
        if (now_epoch - cached_at) < _CACHE_TTL_SECONDS:
            return earnings_dt

    earnings_dt = _fetch_earnings_from_yfinance(ticker)
    _earnings_cache[ticker] = (earnings_dt, now_epoch)
    return earnings_dt


def _fetch_earnings_from_yfinance(ticker: str) -> datetime | None:
    """
    Call yfinance to get the next earnings date.
    Returns a timezone-aware datetime, or None if unavailable.
    """
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return None

        # yfinance returns a dict: {'Earnings Date': [Timestamp, ...], ...}
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date", [])
        elif hasattr(cal, "to_dict"):
            dates = cal.to_dict().get("Earnings Date", {}).values()
        else:
            return None

        now = datetime.now(timezone.utc)
        for d in dates:
            if d is None:
                continue
            # Convert pandas Timestamp → datetime
            if hasattr(d, "to_pydatetime"):
                d = d.to_pydatetime()
            if not isinstance(d, datetime):
                continue
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d > now:
                return d

        return None
    except Exception as exc:
        logger.debug("Could not fetch earnings date for %s: %s", ticker, exc)
        return None


def _trading_days_until(target: datetime) -> int:
    """
    Approximate number of trading days between now and target.
    Uses a 5/7 calendar-day ratio as a quick estimate.
    """
    now = datetime.now(timezone.utc)
    if target <= now:
        return 0
    calendar_days = (target - now).days
    return max(0, int(calendar_days * 5 / 7))
