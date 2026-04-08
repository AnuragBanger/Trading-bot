"""
Discovery Module
Scans the universe of stocks/ETFs and returns a ranked shortlist of
top candidates per cycle, filtered by liquidity, price, and FA score.
"""
from __future__ import annotations

import logging
import random
from typing import Any

import yfinance as yf

from config import load_json, load_parameters, WATCHLIST_FILE
from modules.technical import TechnicalAnalyzer
from modules.fundamental import FundamentalAnalyzer
from modules.earnings_guard import is_earnings_risk

logger = logging.getLogger(__name__)


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
        params = load_parameters()
        thresholds = params["thresholds"]
        active_tickers = active_tickers or set()

        universe = self._build_universe()
        logger.info("Scanning universe of %d tickers", len(universe))

        candidates: list[dict] = []
        for ticker in universe:
            if ticker in active_tickers:
                continue
            try:
                result = self._evaluate(ticker, thresholds)
                if result:
                    candidates.append(result)
            except Exception as exc:
                logger.debug("Skipping %s: %s", ticker, exc)

        # Rank by composite score descending
        candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top = candidates[:10]
        logger.info("Discovery complete — %d candidates found, returning top %d", len(candidates), len(top))
        return top

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_universe(self) -> list[str]:
        wl = load_json(WATCHLIST_FILE)
        universe: set[str] = set()
        universe.update(wl.get("etfs", []))
        universe.update(wl.get("sp500_sample", []))
        universe.update(wl.get("nasdaq100_sample", []))
        return list(universe)

    def _evaluate(self, ticker: str, thresholds: dict) -> dict | None:
        """Fetch basic info, apply filters, score the ticker."""
        info = yf.Ticker(ticker).fast_info

        # Price filter
        price = getattr(info, "last_price", None)
        if price is None or not (thresholds["min_price"] <= price <= thresholds["max_price"]):
            return None

        # Volume filter
        volume = getattr(info, "three_month_average_volume", None) or getattr(info, "last_volume", 0)
        if volume < thresholds["min_volume"]:
            return None

        # Determine type
        wl = load_json(WATCHLIST_FILE)
        is_etf = ticker in wl.get("etfs", [])
        asset_type = "etf" if is_etf else "stock"

        # Fundamental score
        fa_score = self.fa.score(ticker, asset_type)
        if fa_score < thresholds["min_fa_score"]:
            return None

        # Earnings risk check — skip tickers within 5 trading days of earnings
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

        # Technical snapshot (lightweight — just RSI for filtering)
        ta_data = self.ta.analyze(ticker)
        if ta_data is None:
            return None

        rsi = ta_data.get("rsi")

        # Composite score for ranking
        composite = self._composite_score(fa_score, rsi, ta_data)

        # Flag existing positions for review if earnings are imminent (≤2 days)
        earnings_warning = None
        if asset_type == "stock":
            einfo = is_earnings_risk(ticker)
            if einfo["flag_for_review"]:
                earnings_warning = einfo

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
