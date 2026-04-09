"""
Correlation Guard Module
Prevents the portfolio from becoming over-concentrated in correlated names.

Rules enforced before any new position open:
  1. Block if pairwise 60-day return correlation > 0.75 with any existing position
  2. Block if 2 or more positions already exist in the same GICS sector
     (ETFs are exempt from sector counting)
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CORRELATION_THRESHOLD   = 0.75   # block if correlation exceeds this
MAX_PER_SECTOR          = 2      # max concurrent positions per GICS sector
LOOKBACK_DAYS           = 60     # days of daily returns for correlation

# Sector cache: ticker → sector string (lives for the process lifetime)
_sector_cache: dict[str, str] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def check_correlation(
    candidate_ticker: str,
    active_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Decide whether opening a position in *candidate_ticker* is allowed
    given the list of *active_positions*.

    Returns
    -------
    {
        "allowed":      bool,
        "reason":       str,
        "max_corr":     float | None,
        "corr_with":    str | None,
        "sector":       str | None,
        "sector_count": int,
    }
    """
    if not active_positions:
        return _ok(None, None, None, 0)

    active_tickers = [p["ticker"] for p in active_positions]

    # ── Sector limit ──────────────────────────────────────────────────────────
    candidate_sector = _get_sector(candidate_ticker)
    sector_count = 0

    if candidate_sector and candidate_sector not in ("ETF", "Unknown", ""):
        sector_count = sum(
            1 for p in active_positions
            if _get_sector(p["ticker"]) == candidate_sector
        )
        if sector_count >= MAX_PER_SECTOR:
            logger.info(
                "Sector block for %s: already %d positions in '%s'",
                candidate_ticker, sector_count, candidate_sector,
            )
            return {
                "allowed":      False,
                "reason":       f"sector_limit_{MAX_PER_SECTOR}_in_{candidate_sector}",
                "max_corr":     None,
                "corr_with":    None,
                "sector":       candidate_sector,
                "sector_count": sector_count,
            }

    # ── Return correlation ────────────────────────────────────────────────────
    returns = _fetch_returns([candidate_ticker] + active_tickers)

    if returns is None or candidate_ticker not in returns.columns:
        logger.debug("Correlation data unavailable for %s — allowing", candidate_ticker)
        return _ok(None, None, candidate_sector, sector_count)

    max_corr: float = 0.0
    corr_with: str | None = None

    for t in active_tickers:
        if t not in returns.columns:
            continue
        pair = returns[[candidate_ticker, t]].dropna()
        if len(pair) < 20:
            continue
        corr = float(pair.corr().iloc[0, 1])
        if corr > max_corr:
            max_corr = corr
            corr_with = t

    if max_corr > CORRELATION_THRESHOLD:
        logger.info(
            "Correlation block: %s vs %s corr=%.2f (limit %.2f)",
            candidate_ticker, corr_with, max_corr, CORRELATION_THRESHOLD,
        )
        return {
            "allowed":      False,
            "reason":       f"correlation_{max_corr:.2f}_with_{corr_with}",
            "max_corr":     round(max_corr, 4),
            "corr_with":    corr_with,
            "sector":       candidate_sector,
            "sector_count": sector_count,
        }

    return _ok(round(max_corr, 4), corr_with, candidate_sector, sector_count)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ok(
    max_corr: float | None,
    corr_with: str | None,
    sector: str | None,
    sector_count: int,
) -> dict[str, Any]:
    return {
        "allowed":      True,
        "reason":       "correlation_ok",
        "max_corr":     max_corr,
        "corr_with":    corr_with,
        "sector":       sector,
        "sector_count": sector_count,
    }


def _get_sector(ticker: str) -> str:
    if ticker in _sector_cache:
        return _sector_cache[ticker]
    try:
        info   = yf.Ticker(ticker).info
        sector = info.get("sector") or info.get("category") or "Unknown"
        _sector_cache[ticker] = str(sector)
        return _sector_cache[ticker]
    except Exception:
        _sector_cache[ticker] = "Unknown"
        return "Unknown"


def _fetch_returns(tickers: list[str]) -> pd.DataFrame | None:
    """Download OHLCV for all tickers and return daily pct_change DataFrame."""
    try:
        period = f"{LOOKBACK_DAYS + 10}d"
        if len(tickers) == 1:
            df = yf.download(
                tickers[0], period=period, interval="1d",
                progress=False, auto_adjust=True,
            )
            if df is None or df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df[["Close"]].copy()
            close.columns = [tickers[0]]
        else:
            df = yf.download(
                tickers, period=period, interval="1d",
                progress=False, auto_adjust=True,
            )
            if df is None or df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                close = df["Close"].copy()
            else:
                close = df[["Close"]].copy()
                close.columns = tickers[:1]

        return close.pct_change().dropna(how="all")
    except Exception as exc:
        logger.debug("Failed to fetch correlation returns: %s", exc)
        return None
