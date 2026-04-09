"""
Market Regime Detector
Classifies the current market into bull / bear / sideways using SPY price
relative to its SMA50 and SMA200, with ATR as a volatility overlay.

Regimes
-------
bull     — SPY > SMA50 > SMA200  → favor momentum signals, standard thresholds
bear     — SPY < SMA50 < SMA200  → raise confidence bar, shrink positions
sideways — mixed SMA alignment   → favor mean-reversion signals (RSI, BB)

Per-regime overrides are sourced from parameters.json["regime_overrides"]
so the refiner can tune them over time.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Conservative defaults used when parameters.json hasn't been updated yet
DEFAULT_REGIME_OVERRIDES: dict[str, dict] = {
    "bull":     {"min_confidence_to_trade": 70, "max_position_pct": 0.25, "rsi_oversold_level": 45},
    "bear":     {"min_confidence_to_trade": 80, "max_position_pct": 0.15, "rsi_oversold_level": 35},
    "sideways": {"min_confidence_to_trade": 75, "max_position_pct": 0.20, "rsi_oversold_level": 35},
}


def detect_regime() -> dict[str, Any]:
    """
    Detect the current market regime.

    Returns
    -------
    {
        "regime":      "bull" | "bear" | "sideways" | "unknown",
        "spy_price":   float | None,
        "sma50":       float | None,
        "sma200":      float | None,
        "atr_pct":     float | None,   # ATR as % of SPY price
        "overrides":   dict,           # parameter overrides for this regime
        "description": str,
    }
    """
    try:
        import yfinance as yf
        import pandas_ta as ta
        import pandas

        df = yf.download("SPY", period="1y", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 60:
            logger.warning("Regime detection: insufficient SPY data")
            return _unknown()

        if isinstance(df.columns, pandas.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        sma50_s  = ta.sma(df["Close"], length=50)
        sma200_s = ta.sma(df["Close"], length=200)
        atr14_s  = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        price = float(df["Close"].iloc[-1])
        s50   = float(sma50_s.iloc[-1])  if sma50_s  is not None and len(sma50_s)  and not sma50_s.empty  else price
        s200  = float(sma200_s.iloc[-1]) if sma200_s is not None and len(sma200_s) and not sma200_s.empty else price
        atr   = float(atr14_s.iloc[-1])  if atr14_s  is not None and len(atr14_s)  and not atr14_s.empty  else 0.0
        atr_pct = round((atr / price * 100) if price > 0 else 0.0, 2)

        above_sma50  = price > s50
        above_sma200 = price > s200
        sma50_above_sma200 = s50 > s200

        if above_sma50 and above_sma200 and sma50_above_sma200:
            regime = "bull"
            desc = (
                f"Bull market: SPY ${price:.2f} above SMA50 ${s50:.2f} and SMA200 ${s200:.2f}"
            )
        elif not above_sma50 and not above_sma200 and not sma50_above_sma200:
            regime = "bear"
            desc = (
                f"Bear market: SPY ${price:.2f} below SMA50 ${s50:.2f} and SMA200 ${s200:.2f}"
            )
        else:
            regime = "sideways"
            desc = (
                f"Sideways/choppy: SPY ${price:.2f}, SMA50=${s50:.2f}, "
                f"SMA200=${s200:.2f} — mixed alignment"
            )

        if atr_pct > 2.0:
            desc += f" (elevated vol: ATR {atr_pct:.1f}%)"

        from config import load_parameters
        params = load_parameters()
        regime_overrides_cfg = params.get("regime_overrides", DEFAULT_REGIME_OVERRIDES)
        overrides = regime_overrides_cfg.get(regime, DEFAULT_REGIME_OVERRIDES.get(regime, {}))

        logger.info(
            "Market regime: %s (SPY=$%.2f, SMA50=$%.2f, SMA200=$%.2f, ATR=%.1f%%)",
            regime.upper(), price, s50, s200, atr_pct,
        )

        return {
            "regime":      regime,
            "spy_price":   round(price, 2),
            "sma50":       round(s50, 2),
            "sma200":      round(s200, 2),
            "atr_pct":     atr_pct,
            "overrides":   overrides,
            "description": desc,
        }

    except Exception as exc:
        logger.warning("Regime detection failed: %s", exc)
        return _unknown()


def _unknown() -> dict[str, Any]:
    return {
        "regime":      "unknown",
        "spy_price":   None,
        "sma50":       None,
        "sma200":      None,
        "atr_pct":     None,
        "overrides":   DEFAULT_REGIME_OVERRIDES["sideways"],   # conservative fallback
        "description": "Regime unknown — using sideways/conservative defaults",
    }
