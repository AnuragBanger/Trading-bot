"""
Position Sizer Module
Implements fractional Kelly Criterion with volatility scaling.

Kelly formula:  f* = (b·p − q) / b
    b = avg_win / avg_loss   (win/loss ratio)
    p = historical win rate (probability)
    q = 1 − p

We apply:
  1. 50% Kelly fraction  → reduces variance substantially
  2. ATR-based vol scaling → size down in high-vol environments
  3. Confidence scalar    → reduce size for lower-confidence signals
  4. Hard cap at max_position_pct

When no outcome history exists yet, falls back to confidence-based sizing.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Tuning constants
KELLY_FRACTION      = 0.50   # Use 50% of full Kelly (half-Kelly)
TARGET_ANNUAL_VOL   = 0.20   # 20% annualised vol target for scaling
MIN_POSITION_PCT    = 0.05   # Never allocate less than 5%
DEFAULT_MAX_PCT     = 0.25   # Hard cap (overrideable via max_pct arg)
MIN_TRADES_FOR_KELLY = 10    # Need at least 10 closed trades to trust Kelly


def kelly_position_size(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    total_trades: int = 0,
    atr: float | None = None,
    current_price: float | None = None,
    signal_confidence: float = 70.0,
    max_pct: float = DEFAULT_MAX_PCT,
) -> float:
    """
    Compute the recommended position size as a fraction of portfolio value.

    Parameters
    ----------
    win_rate          : Historical win rate (0–100 scale, e.g. 60.0 = 60%)
    avg_win_pct       : Average winning trade return in % (e.g. 12.5)
    avg_loss_pct      : Average losing trade loss in % (e.g. 8.0, positive)
    total_trades      : Number of closed trades used to derive the stats
    atr               : ATR(14) of the candidate ticker
    current_price     : Current price of the candidate ticker
    signal_confidence : Claude's confidence score (0–100)
    max_pct           : Hard upper bound on position size (default 25%)

    Returns
    -------
    float : Position size fraction of portfolio (MIN_POSITION_PCT … max_pct)
    """
    # Not enough history → fall back to confidence-based sizing
    if total_trades < MIN_TRADES_FOR_KELLY or win_rate <= 0 or avg_win_pct <= 0 or avg_loss_pct <= 0:
        size = _confidence_based_size(signal_confidence, max_pct)
        logger.debug(
            "Kelly fallback (insufficient history: %d trades) → confidence-based %.4f",
            total_trades, size,
        )
        return size

    p = win_rate / 100.0        # probability of win
    q = 1.0 - p                 # probability of loss
    b = avg_win_pct / avg_loss_pct  # win/loss ratio

    kelly_f = (b * p - q) / b

    if kelly_f <= 0:
        # Negative Kelly → edge is negative, use minimum size
        logger.debug("Negative Kelly (b=%.2f, p=%.2f) → using min size", b, p)
        return MIN_POSITION_PCT

    # Apply fractional Kelly
    adjusted = kelly_f * KELLY_FRACTION

    # Volatility scaling: scale position inversely with realised vol
    if atr is not None and current_price and current_price > 0:
        daily_vol = atr / current_price                    # daily vol proxy from ATR
        annual_vol = daily_vol * (252 ** 0.5)              # annualise
        if annual_vol > 0:
            vol_scalar = TARGET_ANNUAL_VOL / annual_vol
            vol_scalar = max(0.5, min(2.0, vol_scalar))    # clamp [0.5, 2.0]
            adjusted *= vol_scalar

    # Confidence scaling: full size at 90+, scaled down below
    confidence_scalar = min(1.0, signal_confidence / 90.0)
    adjusted *= confidence_scalar

    result = max(MIN_POSITION_PCT, min(max_pct, adjusted))

    logger.debug(
        "Kelly sizing: win_rate=%.1f%%, b=%.2f, raw_kelly=%.4f, "
        "half_kelly=%.4f, final=%.4f",
        win_rate, b, kelly_f, kelly_f * KELLY_FRACTION, result,
    )
    return round(result, 4)


# ── Fallback ──────────────────────────────────────────────────────────────────

def _confidence_based_size(confidence: float, max_pct: float) -> float:
    """Simple tiered sizing when Kelly data is unavailable."""
    if confidence >= 88:
        return min(0.20, max_pct)
    elif confidence >= 80:
        return min(0.15, max_pct)
    elif confidence >= 72:
        return min(0.12, max_pct)
    else:
        return min(0.10, max_pct)
