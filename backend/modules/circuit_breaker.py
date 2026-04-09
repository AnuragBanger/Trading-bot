"""
Circuit Breaker Module
Monitors portfolio drawdown from its all-time peak and restricts or halts
new position opens when losses become significant.

Soft limit — 15% drawdown from peak:
  - Raise minimum confidence threshold to 85
  - Reduce maximum position size to 15%
  - Log circuit_breaker_soft event

Hard limit — 25% drawdown from peak:
  - Block ALL new position opens
  - Log circuit_breaker_hard event
  - Remains active until portfolio recovers to within 20% of peak
"""
from __future__ import annotations

import logging
from typing import Any

from config import load_json, PAPER_TRADES_FILE

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
SOFT_DRAWDOWN_PCT  = 0.15   # 15% from peak → apply restrictions
HARD_DRAWDOWN_PCT  = 0.25   # 25% from peak → block all new opens
RECOVERY_PCT       = 0.20   # hard block clears when back within 20% of peak

# ── Restrictions at soft limit ────────────────────────────────────────────────
SOFT_MIN_CONFIDENCE = 85
SOFT_MAX_POSITION   = 0.15


# ── Public API ────────────────────────────────────────────────────────────────

def get_circuit_breaker_status() -> dict[str, Any]:
    """
    Evaluate current portfolio drawdown and return the circuit breaker status.

    Returns
    -------
    {
        "status":                  "normal" | "soft" | "hard",
        "current_drawdown":        float,        # fraction, e.g. 0.18 = 18%
        "peak_value":              float,
        "current_value":           float,
        "new_opens_blocked":       bool,
        "min_confidence_override": int | None,   # None if no override
        "max_position_override":   float | None, # None if no override
        "message":                 str,
    }
    """
    data      = load_json(PAPER_TRADES_FILE)
    portfolio = data.get("portfolio", {})

    current_value = portfolio.get("total_value", 0.0)
    curve         = portfolio.get("equity_curve", [])

    # Peak = highest portfolio value ever recorded
    peak_value = max((pt["value"] for pt in curve), default=current_value)
    peak_value = max(peak_value, current_value)   # can never be below current

    if peak_value <= 0:
        return _normal(0.0, peak_value, current_value)

    drawdown = (peak_value - current_value) / peak_value

    # ── Hard limit ────────────────────────────────────────────────────────────
    if drawdown >= HARD_DRAWDOWN_PCT:
        logger.warning(
            "HARD circuit breaker: drawdown=%.1f%% (peak=$%.2f current=$%.2f)",
            drawdown * 100, peak_value, current_value,
        )
        recovery_target = peak_value * (1.0 - RECOVERY_PCT)
        return {
            "status":                  "hard",
            "current_drawdown":        round(drawdown, 4),
            "peak_value":              round(peak_value, 2),
            "current_value":           round(current_value, 2),
            "new_opens_blocked":       True,
            "min_confidence_override": None,
            "max_position_override":   None,
            "message": (
                f"HARD circuit breaker active: {drawdown*100:.1f}% drawdown from peak "
                f"${peak_value:.2f}. All new positions blocked until recovery to "
                f"${recovery_target:.2f}."
            ),
        }

    # ── Soft limit ────────────────────────────────────────────────────────────
    if drawdown >= SOFT_DRAWDOWN_PCT:
        logger.warning(
            "SOFT circuit breaker: drawdown=%.1f%%, confidence>=%d, max_pos=%.0f%%",
            drawdown * 100, SOFT_MIN_CONFIDENCE, SOFT_MAX_POSITION * 100,
        )
        return {
            "status":                  "soft",
            "current_drawdown":        round(drawdown, 4),
            "peak_value":              round(peak_value, 2),
            "current_value":           round(current_value, 2),
            "new_opens_blocked":       False,
            "min_confidence_override": SOFT_MIN_CONFIDENCE,
            "max_position_override":   SOFT_MAX_POSITION,
            "message": (
                f"SOFT circuit breaker: {drawdown*100:.1f}% drawdown. "
                f"Confidence raised to {SOFT_MIN_CONFIDENCE}, "
                f"max position capped at {SOFT_MAX_POSITION*100:.0f}%."
            ),
        }

    return _normal(drawdown, peak_value, current_value)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normal(drawdown: float, peak: float, current: float) -> dict[str, Any]:
    return {
        "status":                  "normal",
        "current_drawdown":        round(drawdown, 4),
        "peak_value":              round(peak, 2),
        "current_value":           round(current, 2),
        "new_opens_blocked":       False,
        "min_confidence_override": None,
        "max_position_override":   None,
        "message":                 "normal",
    }
