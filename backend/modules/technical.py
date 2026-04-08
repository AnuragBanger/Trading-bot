"""
Technical Analysis Module
Computes TA indicators using pandas-ta and returns a structured snapshot.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import pandas_ta as ta
import yfinance as yf

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Compute all required TA indicators for a given ticker."""

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, ticker: str, period: str = "6mo", interval: str = "1d") -> dict[str, Any] | None:
        """
        Returns a dict with all indicator values, or None if data unavailable.
        """
        df = self._fetch_ohlcv(ticker, period, interval)
        if df is None or len(df) < 30:
            return None

        result: dict[str, Any] = {"ticker": ticker}

        # ── RSI(14) ──────────────────────────────────────────────────────────
        rsi = ta.rsi(df["Close"], length=14)
        result["rsi"] = round(float(rsi.iloc[-1]), 2) if rsi is not None and not rsi.empty else None

        # ── MACD(12,26,9) ────────────────────────────────────────────────────
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            macd_val   = float(macd_df["MACD_12_26_9"].iloc[-1])
            macd_sig   = float(macd_df["MACDs_12_26_9"].iloc[-1])
            macd_hist  = float(macd_df["MACDh_12_26_9"].iloc[-1])
            prev_hist  = float(macd_df["MACDh_12_26_9"].iloc[-2]) if len(macd_df) > 1 else 0.0
            result["macd"]            = round(macd_val, 4)
            result["macd_signal_line"]= round(macd_sig, 4)
            result["macd_histogram"]  = round(macd_hist, 4)
            # Bullish: histogram crossed from negative to positive
            if prev_hist <= 0 and macd_hist > 0:
                result["macd_signal"] = "bullish"
            elif prev_hist >= 0 and macd_hist < 0:
                result["macd_signal"] = "bearish"
            else:
                result["macd_signal"] = "neutral"
        else:
            result.update({"macd": None, "macd_signal_line": None, "macd_histogram": None, "macd_signal": "neutral"})

        # ── SMA(50) & SMA(200) ───────────────────────────────────────────────
        sma50  = ta.sma(df["Close"], length=50)
        sma200 = ta.sma(df["Close"], length=200)
        current_price = float(df["Close"].iloc[-1])

        result["sma50"]       = round(float(sma50.iloc[-1]), 4)  if sma50  is not None and not sma50.empty  else None
        result["sma200"]      = round(float(sma200.iloc[-1]), 4) if sma200 is not None and not sma200.empty else None
        result["above_sma50"] = (current_price > result["sma50"])  if result["sma50"]  else False
        result["above_sma200"]= (current_price > result["sma200"]) if result["sma200"] else False

        # Golden/death cross check (SMA50 vs SMA200)
        if result["sma50"] and result["sma200"]:
            prev_sma50  = float(sma50.iloc[-2])  if len(sma50)  > 1 else result["sma50"]
            prev_sma200 = float(sma200.iloc[-2]) if len(sma200) > 1 else result["sma200"]
            if prev_sma50 <= prev_sma200 and result["sma50"] > result["sma200"]:
                result["sma_cross"] = "golden"
            elif prev_sma50 >= prev_sma200 and result["sma50"] < result["sma200"]:
                result["sma_cross"] = "death"
            else:
                result["sma_cross"] = "none"
        else:
            result["sma_cross"] = "none"

        # ── EMA(20) ──────────────────────────────────────────────────────────
        ema20 = ta.ema(df["Close"], length=20)
        result["ema20"]       = round(float(ema20.iloc[-1]), 4) if ema20 is not None and not ema20.empty else None
        result["above_ema20"] = (current_price > result["ema20"]) if result["ema20"] else False

        # ── ATR(14) ──────────────────────────────────────────────────────────
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        result["atr"] = round(float(atr.iloc[-1]), 4) if atr is not None and not atr.empty else None

        # ── Bollinger Bands(20,2) ────────────────────────────────────────────
        bbands = ta.bbands(df["Close"], length=20, std=2)
        if bbands is not None and not bbands.empty:
            bb_lower = float(bbands["BBL_20_2.0"].iloc[-1])
            bb_mid   = float(bbands["BBM_20_2.0"].iloc[-1])
            bb_upper = float(bbands["BBU_20_2.0"].iloc[-1])
            result["bb_lower"] = round(bb_lower, 4)
            result["bb_mid"]   = round(bb_mid, 4)
            result["bb_upper"] = round(bb_upper, 4)
            result["bb_pct"]   = round((current_price - bb_lower) / (bb_upper - bb_lower), 4) if (bb_upper - bb_lower) else 0.5
            result["bb_signal"]= (
                "oversold"   if current_price <= bb_lower else
                "overbought" if current_price >= bb_upper else
                "neutral"
            )
        else:
            result.update({"bb_lower": None, "bb_mid": None, "bb_upper": None, "bb_pct": None, "bb_signal": "neutral"})

        # ── Volume Spike ─────────────────────────────────────────────────────
        if "Volume" in df.columns and len(df) >= 20:
            avg_volume  = float(df["Volume"].rolling(20).mean().iloc[-1])
            last_volume = float(df["Volume"].iloc[-1])
            result["avg_volume"]   = round(avg_volume, 0)
            result["last_volume"]  = round(last_volume, 0)
            result["volume_ratio"] = round(last_volume / avg_volume, 2) if avg_volume else 1.0
            result["volume_spike"] = result["volume_ratio"] >= 1.5
        else:
            result.update({"avg_volume": None, "last_volume": None, "volume_ratio": 1.0, "volume_spike": False})

        # ── Support / Resistance (rolling 20-period highs/lows) ──────────────
        if len(df) >= 20:
            result["support"]    = round(float(df["Low"].rolling(20).min().iloc[-1]), 4)
            result["resistance"] = round(float(df["High"].rolling(20).max().iloc[-1]), 4)
        else:
            result["support"]    = None
            result["resistance"] = None

        result["current_price"] = round(current_price, 4)
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_ohlcv(self, ticker: str, period: str, interval: str) -> pd.DataFrame | None:
        try:
            df = yf.download(ticker, period=period, interval=interval,
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                return None
            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df.dropna(subset=["Close"])
        except Exception as exc:
            logger.warning("Failed to fetch OHLCV for %s: %s", ticker, exc)
            return None

    # ── Weekly timeframe analysis ─────────────────────────────────────────────

    def analyze_weekly(self, ticker: str) -> dict[str, Any] | None:
        """
        Compute weekly-timeframe indicators for multi-timeframe confirmation.
        Uses 3 years of weekly data to support SMA50 and SMA100.

        Returns a dict with weekly TA snapshot, or None if data unavailable.
        """
        df = self._fetch_ohlcv(ticker, period="3y", interval="1wk")
        if df is None or len(df) < 20:
            return None

        result: dict[str, Any] = {"ticker": ticker, "timeframe": "weekly"}

        current_price = float(df["Close"].iloc[-1])
        result["current_price"] = round(current_price, 4)

        # Weekly RSI(14)
        rsi = ta.rsi(df["Close"], length=14)
        result["rsi_weekly"] = round(float(rsi.iloc[-1]), 2) if rsi is not None and not rsi.empty else None

        # Weekly MACD direction (trend, not crossover)
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            hist = float(macd_df["MACDh_12_26_9"].iloc[-1])
            result["macd_weekly_histogram"] = round(hist, 4)
            result["macd_weekly_trend"] = "bullish" if hist > 0 else "bearish"
        else:
            result["macd_weekly_histogram"] = None
            result["macd_weekly_trend"] = "neutral"

        # Weekly SMA20 and SMA50
        sma20w = ta.sma(df["Close"], length=20)
        sma50w = ta.sma(df["Close"], length=50)
        result["sma20_weekly"] = round(float(sma20w.iloc[-1]), 4) if sma20w is not None and not sma20w.empty else None
        result["sma50_weekly"] = round(float(sma50w.iloc[-1]), 4) if sma50w is not None and not sma50w.empty else None
        result["above_sma20_weekly"] = (current_price > result["sma20_weekly"]) if result["sma20_weekly"] else False
        result["above_sma50_weekly"] = (current_price > result["sma50_weekly"]) if result["sma50_weekly"] else False

        # Weekly ATR (volatility context)
        atr_w = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        result["atr_weekly"] = round(float(atr_w.iloc[-1]), 4) if atr_w is not None and not atr_w.empty else None

        return result

    def get_timeframe_alignment(
        self, daily_ta: dict, weekly_ta: dict | None
    ) -> str:
        """
        Combine daily + weekly signals to classify the multi-timeframe trend.

        Returns one of:
          "strong_bull" — both timeframes clearly bullish
          "bull"        — weekly uptrend + daily either bullish or neutral
          "neutral"     — mixed signals
          "bear"        — weekly downtrend or conflicting signals
          "strong_bear" — both timeframes clearly bearish
        """
        if weekly_ta is None:
            # No weekly data: classify from daily only
            above200 = daily_ta.get("above_sma200", False)
            above50  = daily_ta.get("above_sma50",  False)
            macd_sig = daily_ta.get("macd_signal",  "neutral")
            if above200 and above50 and macd_sig == "bullish":
                return "bull"
            if not above200 and not above50:
                return "bear"
            return "neutral"

        above50w  = weekly_ta.get("above_sma50_weekly", False)
        above20w  = weekly_ta.get("above_sma20_weekly", False)
        rsi_w     = weekly_ta.get("rsi_weekly") or 50.0
        macd_w    = weekly_ta.get("macd_weekly_trend", "neutral")
        above200d = daily_ta.get("above_sma200", False)
        above50d  = daily_ta.get("above_sma50",  False)

        bull_weekly = above50w and above20w and rsi_w > 45 and macd_w == "bullish"
        bear_weekly = not above50w and not above20w and rsi_w < 55 and macd_w == "bearish"
        bull_daily  = above200d and above50d
        bear_daily  = not above200d and not above50d

        if bull_weekly and bull_daily:
            return "strong_bull"
        if bull_weekly and not bear_daily:
            return "bull"
        if bear_weekly and bear_daily:
            return "strong_bear"
        if bear_weekly:
            return "bear"
        return "neutral"

    def compute_signals_list(self, ta_data: dict) -> list[str]:
        """Convert TA snapshot into a list of signal strings for the AI engine."""
        signals: list[str] = []
        params_raw = {}
        try:
            from config import load_parameters
            params_raw = load_parameters().get("thresholds", {})
        except Exception:
            pass

        rsi_oversold  = params_raw.get("rsi_oversold_level", 40)
        rsi_overbought= params_raw.get("rsi_overbought_level", 65)

        rsi = ta_data.get("rsi")
        if rsi is not None:
            if rsi <= rsi_oversold:
                signals.append("rsi_oversold")
            elif rsi >= rsi_overbought:
                signals.append("rsi_overbought")

        if ta_data.get("macd_signal") == "bullish":
            signals.append("macd_bullish_crossover")
        elif ta_data.get("macd_signal") == "bearish":
            signals.append("macd_bearish_crossover")

        if ta_data.get("sma_cross") == "golden":
            signals.append("golden_cross")
        elif ta_data.get("sma_cross") == "death":
            signals.append("death_cross")

        if ta_data.get("above_sma200"):
            signals.append("above_sma200")
        if ta_data.get("above_sma50"):
            signals.append("above_sma50")

        if ta_data.get("bb_signal") == "oversold":
            signals.append("bb_lower_band_touch")
        elif ta_data.get("bb_signal") == "overbought":
            signals.append("bb_upper_band_touch")

        if ta_data.get("volume_spike"):
            signals.append("volume_spike_1_5x")

        return signals
