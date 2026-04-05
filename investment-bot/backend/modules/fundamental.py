"""
Fundamental Analysis Module
Scores stocks (0-100) and ETFs (0-100) using yfinance data.
"""
from __future__ import annotations

import logging
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


class FundamentalAnalyzer:
    """Score a ticker on fundamentals."""

    # ── Public API ────────────────────────────────────────────────────────────

    def score(self, ticker: str, asset_type: str = "stock") -> float:
        """Return a fundamental score 0-100."""
        try:
            info = yf.Ticker(ticker).info
            if asset_type == "etf":
                return self._score_etf(info)
            return self._score_stock(info)
        except Exception as exc:
            logger.warning("FA score failed for %s: %s", ticker, exc)
            return 50.0  # neutral fallback

    def get_details(self, ticker: str, asset_type: str = "stock") -> dict[str, Any]:
        """Return the raw fundamental data dict alongside the score."""
        try:
            info = yf.Ticker(ticker).info
            if asset_type == "etf":
                score  = self._score_etf(info)
                detail = self._etf_detail(info)
            else:
                score  = self._score_stock(info)
                detail = self._stock_detail(info)
            detail["fa_score"] = score
            return detail
        except Exception as exc:
            logger.warning("FA details failed for %s: %s", ticker, exc)
            return {"fa_score": 50.0}

    # ── Stock scoring ─────────────────────────────────────────────────────────

    def _score_stock(self, info: dict) -> float:
        score = 0.0

        # P/E ratio vs rough sector median (20 pts)
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe and pe > 0:
            if pe < 15:
                score += 20
            elif pe < 25:
                score += 15
            elif pe < 40:
                score += 8
            elif pe < 60:
                score += 3

        # EPS growth YoY (20 pts)
        eps_trailing = info.get("trailingEps") or 0
        eps_forward  = info.get("forwardEps")  or 0
        if eps_trailing > 0 and eps_forward > 0:
            eps_growth = (eps_forward - eps_trailing) / abs(eps_trailing)
            if eps_growth > 0.20:
                score += 20
            elif eps_growth > 0.10:
                score += 15
            elif eps_growth > 0.0:
                score += 10
            elif eps_growth > -0.05:
                score += 5
        elif eps_trailing > 0:
            score += 10  # at least profitable

        # Revenue growth (15 pts)
        rev_growth = info.get("revenueGrowth")
        if rev_growth is not None:
            if rev_growth > 0.20:
                score += 15
            elif rev_growth > 0.10:
                score += 12
            elif rev_growth > 0.0:
                score += 7
            elif rev_growth > -0.05:
                score += 3

        # Debt/Equity < 1.5 (15 pts)
        de = info.get("debtToEquity")
        if de is not None:
            if de < 50:    # yfinance returns as percentage * 100
                score += 15
            elif de < 100:
                score += 10
            elif de < 150:
                score += 5

        # Free Cash Flow positive (15 pts)
        fcf = info.get("freeCashflow")
        if fcf is not None:
            if fcf > 1_000_000_000:
                score += 15
            elif fcf > 0:
                score += 10

        # ROE > 10% (15 pts)
        roe = info.get("returnOnEquity")
        if roe is not None:
            if roe > 0.20:
                score += 15
            elif roe > 0.10:
                score += 12
            elif roe > 0.0:
                score += 6

        return round(min(score, 100.0), 1)

    # ── ETF scoring ───────────────────────────────────────────────────────────

    def _score_etf(self, info: dict) -> float:
        score = 0.0

        # Expense ratio < 0.5% (25 pts)
        expense = info.get("annualReportExpenseRatio") or info.get("totalExpenseRatio") or info.get("expenseRatio")
        if expense is not None:
            if expense < 0.001:
                score += 25
            elif expense < 0.003:
                score += 20
            elif expense < 0.005:
                score += 15
            elif expense < 0.01:
                score += 8

        # AUM > $1B (20 pts)
        aum = info.get("totalAssets")
        if aum:
            if aum > 10_000_000_000:
                score += 20
            elif aum > 1_000_000_000:
                score += 15
            elif aum > 100_000_000:
                score += 8

        # 1yr performance vs rough benchmark (30 pts) — use 52w data
        hi52 = info.get("fiftyTwoWeekHigh")
        lo52 = info.get("fiftyTwoWeekLow")
        curr = info.get("currentPrice") or info.get("regularMarketPrice")
        if hi52 and lo52 and curr and hi52 > lo52:
            pct_from_low = (curr - lo52) / (hi52 - lo52)
            if pct_from_low > 0.75:
                score += 30
            elif pct_from_low > 0.50:
                score += 22
            elif pct_from_low > 0.25:
                score += 12

        # Volume / liquidity (25 pts)
        avg_vol = info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0
        if avg_vol > 10_000_000:
            score += 25
        elif avg_vol > 1_000_000:
            score += 18
        elif avg_vol > 500_000:
            score += 10

        return round(min(score, 100.0), 1)

    # ── Detail helpers ────────────────────────────────────────────────────────

    def _stock_detail(self, info: dict) -> dict:
        return {
            "sector":         info.get("sector"),
            "industry":       info.get("industry"),
            "pe_ratio":       info.get("trailingPE"),
            "forward_pe":     info.get("forwardPE"),
            "eps_trailing":   info.get("trailingEps"),
            "eps_forward":    info.get("forwardEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cash_flow": info.get("freeCashflow"),
            "roe":            info.get("returnOnEquity"),
            "market_cap":     info.get("marketCap"),
        }

    def _etf_detail(self, info: dict) -> dict:
        return {
            "category":       info.get("category"),
            "expense_ratio":  info.get("annualReportExpenseRatio") or info.get("totalExpenseRatio"),
            "total_assets":   info.get("totalAssets"),
            "avg_volume":     info.get("averageVolume"),
            "52w_high":       info.get("fiftyTwoWeekHigh"),
            "52w_low":        info.get("fiftyTwoWeekLow"),
        }
