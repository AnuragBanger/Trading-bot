"""
Discovery Module
Scans the universe of stocks/ETFs and returns a ranked shortlist of
top candidates per cycle, filtered by liquidity, price, and FA score.
Fetches are parallelized with ThreadPoolExecutor to cut cycle time.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yfinance as yf

from config import load_json, save_json, load_parameters, WATCHLIST_FILE
from modules.technical import TechnicalAnalyzer
from modules.fundamental import FundamentalAnalyzer
from modules.earnings_guard import is_earnings_risk

logger = logging.getLogger(__name__)

_MAX_WORKERS = 10   # parallel yfinance fetch threads


class DiscoveryModule:
    def __init__(self) -> None:
        self.ta = TechnicalAnalyzer()
        self.fa = FundamentalAnalyzer()

    # ── Public API ────────────────────────────────────────────────────────────

    def scan(self, active_tickers: set[str] | None = None) -> list[dict[str, Any]]:
        """
        Run a full scan and return the top 10 candidates for this cycle.

        Parameters
        ----------
        active_tickers : set of ticker strings already in open positions
        """
        params     = load_parameters()
        thresholds = params["thresholds"]
        active_tickers = active_tickers or set()

        # Load watchlist once; pass ETF set to each worker to avoid repeated I/O
        wl      = load_json(WATCHLIST_FILE)
        etf_set = set(wl.get("etfs", []))
        universe = self._build_universe(wl)
        candidates_universe = [t for t in universe if t not in active_tickers]

        logger.info("Scanning universe of %d tickers (%d workers)", len(candidates_universe), _MAX_WORKERS)

        candidates: list[dict] = []
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {
                pool.submit(self._evaluate, ticker, thresholds, etf_set): ticker
                for ticker in candidates_universe
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    result = future.result()
                    if result:
                        candidates.append(result)
                except Exception as exc:
                    logger.debug("Skipping %s: %s", ticker, exc)

        # Rank by composite score descending
        candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top = candidates[:10]
        logger.info(
            "Discovery complete — %d candidates found, returning top %d",
            len(candidates), len(top),
        )
        return top

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_universe(self, wl: dict | None = None) -> list[str]:
        if wl is None:
            wl = load_json(WATCHLIST_FILE)
        universe: set[str] = set()
        universe.update(wl.get("etfs", []))
        universe.update(wl.get("sp500_sample", []))
        universe.update(wl.get("nasdaq100_sample", []))
        universe.update(wl.get("custom", []))   # runtime-added tickers
        return list(universe)

    def _evaluate(self, ticker: str, thresholds: dict, etf_set: set[str]) -> dict | None:
        """Fetch basic info, apply filters, score the ticker. Thread-safe."""
        info = yf.Ticker(ticker).fast_info

        # Price filter
        price = getattr(info, "last_price", None)
        if price is None or not (thresholds["min_price"] <= price <= thresholds["max_price"]):
            return None

        # Volume filter
        volume = getattr(info, "three_month_average_volume", None) or getattr(info, "last_volume", 0)
        if volume < thresholds["min_volume"]:
            return None

        asset_type = "etf" if ticker in etf_set else "stock"

        # Fundamental score
        fa_score = self.fa.score(ticker, asset_type)
        if fa_score < thresholds["min_fa_score"]:
            return None

        # Earnings risk check — single call, reused for both filter and warning
        earnings_info    = None
        earnings_warning = None
        if asset_type == "stock":
            earnings_info = is_earnings_risk(ticker)
            if earnings_info["blocked"]:
                logger.info(
                    "Skipping %s — earnings risk: %s (earnings %s, %s trading days away)",
                    ticker,
                    earnings_info["reason"],
                    earnings_info.get("earnings_date", "unknown"),
                    earnings_info.get("trading_days_away", "?"),
                )
                return None
            if earnings_info.get("flag_for_review"):
                earnings_warning = earnings_info

        # Technical snapshot
        ta_data = self.ta.analyze(ticker)
        if ta_data is None:
            return None

        rsi       = ta_data.get("rsi")
        composite = self._composite_score(fa_score, rsi, ta_data)

        return {
            "ticker":           ticker,
            "type":             asset_type,
            "price":            price,
            "volume":           volume,
            "fa_score":         fa_score,
            "rsi":              rsi,
            "ta_snapshot":      ta_data,
            "composite_score":  composite,
            "earnings_warning": earnings_warning,
        }

    def _composite_score(self, fa_score: float, rsi: float | None, ta: dict) -> float:
        """Simple composite ranking score (higher = better candidate)."""
        score = fa_score * 0.4  # FA is 40% of ranking weight

        # Prefer RSI in a buyable zone (30-55)
        if rsi is not None:
            if 30 <= rsi <= 55:
                score += 30
            elif 55 < rsi <= 65:
                score += 15

        # MACD bullish crossover
        if ta.get("macd_signal") == "bullish":
            score += 15

        # Volume spike
        if ta.get("volume_spike"):
            score += 10

        # Above SMA200 (uptrend)
        if ta.get("above_sma200"):
            score += 5

        return round(score, 2)


# ── Watchlist management helpers (used by API endpoints) ─────────────────────

def add_ticker_to_watchlist(ticker: str, category: str = "custom") -> dict:
    """
    Add a ticker to watchlist.json at runtime.
    Returns {"added": bool, "ticker": str, "category": str, "message": str}.
    """
    ticker = ticker.upper().strip()
    valid_categories = {"etfs", "sp500_sample", "nasdaq100_sample", "custom"}
    if category not in valid_categories:
        category = "custom"

    wl = load_json(WATCHLIST_FILE)
    bucket = wl.setdefault(category, [])

    if ticker in bucket:
        return {"added": False, "ticker": ticker, "category": category,
                "message": f"{ticker} already in {category}"}

    bucket.append(ticker)
    save_json(WATCHLIST_FILE, wl)
    return {"added": True, "ticker": ticker, "category": category,
            "message": f"{ticker} added to {category}"}


def remove_ticker_from_watchlist(ticker: str) -> dict:
    """
    Remove a ticker from all categories in watchlist.json.
    Returns {"removed": bool, "ticker": str, "from_categories": list}.
    """
    ticker = ticker.upper().strip()
    wl = load_json(WATCHLIST_FILE)
    removed_from = []

    for category, bucket in wl.items():
        if isinstance(bucket, list) and ticker in bucket:
            bucket.remove(ticker)
            removed_from.append(category)

    if removed_from:
        save_json(WATCHLIST_FILE, wl)

    return {
        "removed":         bool(removed_from),
        "ticker":          ticker,
        "from_categories": removed_from,
    }
