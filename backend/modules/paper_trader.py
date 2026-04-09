"""
Paper Trader Module
Simulates trade execution and position management without real money.
Budget: $500/month (added on the 1st of each month, profits compound).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, date, timezone
from typing import Any

import yfinance as yf

from config import (
    load_json, save_json,
    PAPER_TRADES_FILE, MONTHLY_BUDGET, OUTCOMES_FILE,
    load_parameters,
)
from modules.position_sizer import kelly_position_size

logger = logging.getLogger(__name__)

_HOLDING_PERIOD_DAYS = {"days": 5, "weeks": 21, "months": 63}

# ── Slippage & commission constants ───────────────────────────────────────────
_SLIPPAGE_NORMAL    = 0.001   # 0.10% for normal-vol stocks
_SLIPPAGE_HIGH_VOL  = 0.003   # 0.30% for high-vol stocks (ATR > 2% of price)
_COMMISSION_PER_SHARE = 0.01  # $0.01 per share
_COMMISSION_MAX       = 6.95  # capped at $6.95 per trade


def _slippage_factor(entry_price: float, atr: float | None) -> float:
    """Return slippage fraction based on realised volatility."""
    if atr and entry_price > 0 and (atr / entry_price) > 0.02:
        return _SLIPPAGE_HIGH_VOL
    return _SLIPPAGE_NORMAL


def _commission(shares: float) -> float:
    """Flat per-share commission capped at max."""
    return min(shares * _COMMISSION_PER_SHARE, _COMMISSION_MAX)


class PaperTrader:
    """Manage simulated portfolio positions."""

    # ── Portfolio helpers ─────────────────────────────────────────────────────

    def load(self) -> dict:
        return load_json(PAPER_TRADES_FILE)

    def save(self, data: dict) -> None:
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        save_json(PAPER_TRADES_FILE, data)

    # ── Monthly deposit ───────────────────────────────────────────────────────

    def apply_monthly_deposit(self) -> bool:
        """
        Add $500 on the 1st of each month if not already added this month.
        Returns True if deposit was applied.
        """
        today = date.today()
        if today.day != 1:
            return False

        data       = self.load()
        portfolio  = data["portfolio"]
        deposits   = portfolio.get("monthly_deposits", [])
        this_month = today.strftime("%Y-%m")

        if any(d["date"].startswith(this_month) for d in deposits):
            return False  # already deposited this month

        portfolio["available_cash"]  += MONTHLY_BUDGET
        portfolio["total_deposited"] += MONTHLY_BUDGET
        deposits.append({"date": today.isoformat(), "amount": MONTHLY_BUDGET})
        portfolio["monthly_deposits"] = deposits
        self._refresh_portfolio_totals(data)
        self.save(data)
        logger.info("Monthly deposit of $%.2f applied", MONTHLY_BUDGET)
        return True

    # ── Open a position ───────────────────────────────────────────────────────

    def open_position(self, signal: dict[str, Any]) -> dict | None:
        """
        Simulate buying a position based on a signal dict.
        Returns the position dict or None if rejected.
        """
        params    = load_parameters()
        thresholds= params["thresholds"]
        data      = self.load()
        portfolio = data["portfolio"]
        positions = data["active_positions"]

        # Guard: max concurrent positions
        if len(positions) >= thresholds["max_concurrent_positions"]:
            logger.info("Max positions (%d) reached, skipping %s",
                        thresholds["max_concurrent_positions"], signal["ticker"])
            return None

        # Guard: already holding this ticker
        if any(p["ticker"] == signal["ticker"] for p in positions):
            return None

        available = portfolio["available_cash"]
        if available <= 0:
            return None

        # Kelly Criterion position sizing (overrides Claude's flat suggestion)
        # Circuit breaker may pass a lower max_pct via _cb_max_position
        cb_max = signal.get("_cb_max_position", thresholds["max_position_pct"])
        effective_max = min(cb_max, thresholds["max_position_pct"])

        outcomes_data = load_json(OUTCOMES_FILE)
        stats = outcomes_data.get("stats", {})
        ta_snap = signal.get("_ta_snapshot", {})
        kelly_pct = kelly_position_size(
            win_rate=stats.get("win_rate", 0.0),
            avg_win_pct=stats.get("avg_win_pct", 0.0),
            avg_loss_pct=stats.get("avg_loss_pct", 0.0),
            total_trades=stats.get("total_trades", 0),
            atr=ta_snap.get("atr"),
            current_price=ta_snap.get("current_price"),
            signal_confidence=float(signal.get("confidence", 70)),
            max_pct=effective_max,
        )
        size_pct   = kelly_pct
        total_value= portfolio["total_value"]
        budget     = total_value * size_pct
        budget     = min(budget, available)

        raw_price = self._get_current_price(signal["ticker"])
        if raw_price is None:
            raw_price = signal.get("entry_zone", {}).get("low", 0)
        if not raw_price or raw_price <= 0:
            return None

        # Apply slippage to simulate realistic fill price
        slip = _slippage_factor(raw_price, ta_snap.get("atr"))
        entry_price = round(raw_price * (1.0 + slip), 4)

        # Shares based on slippage-adjusted price
        shares = budget / entry_price

        # Commission reduces effective budget
        comm = _commission(shares)
        if comm > available - (shares * entry_price):
            comm = 0.0   # safety: skip commission if it would overdraw

        position = {
            "id":             str(uuid.uuid4()),
            "ticker":         signal["ticker"],
            "type":           signal.get("type", "stock"),
            "entry_price":    round(entry_price, 4),
            "shares":         round(shares, 6),
            "cost_basis":     round(shares * entry_price, 2),
            "current_price":  round(entry_price, 4),
            "current_value":  round(shares * entry_price, 2),
            "pnl":            0.0,
            "pnl_pct":        0.0,
            "entry_date":     datetime.now(timezone.utc).isoformat(),
            "take_profit_1":  signal.get("take_profit", {}).get("target_1"),
            "take_profit_2":  signal.get("take_profit", {}).get("target_2"),
            "stop_loss":      signal.get("stop_loss"),
            "holding_period": signal.get("holding_period", "weeks"),
            "holding_days":   _HOLDING_PERIOD_DAYS.get(signal.get("holding_period", "weeks"), 21),
            "confidence":     signal.get("confidence", 0),
            "rationale":      signal.get("rationale", ""),
            "key_signals":    signal.get("key_signals", []),
            "risk_level":     signal.get("risk_level", "medium"),
            "tp1_hit":        False,
            "trailing_stop_active":    False,
            "stop_moved_to_breakeven": False,
            "partial_sold_shares": 0.0,
            "partial_sold_value":  0.0,
            "slippage_cost":  round(shares * raw_price * slip, 2),
            "commission_cost": round(comm, 2),
            # snapshot of indicators at entry (for outcome tracking)
            "indicators_at_entry": signal.get("_ta_snapshot", {}),
        }

        portfolio["available_cash"]  -= position["cost_basis"] + comm
        portfolio["invested_amount"] += position["cost_basis"]
        positions.append(position)
        self._refresh_portfolio_totals(data)
        self.save(data)

        logger.info(
            "Opened position: %s @ $%.4f (slip=%.1fbps), %g shares, cost $%.2f "
            "(Kelly=%.1f%%, comm=$%.2f)",
            position["ticker"], entry_price, slip * 10_000, shares,
            position["cost_basis"], size_pct * 100, comm,
        )
        return position

    # ── Monitor all open positions ────────────────────────────────────────────

    def monitor_positions(self) -> list[dict]:
        """
        Check all open positions against current prices.
        Returns list of closed-trade records.
        """
        data      = self.load()
        positions = data["active_positions"]
        closed    = []

        for pos in list(positions):
            current_price = self._get_current_price(pos["ticker"])
            if current_price is None:
                continue

            pos["current_price"] = round(current_price, 4)
            pos["current_value"] = round(pos["shares"] * current_price, 2)
            pos["pnl"]           = round(pos["current_value"] - pos["cost_basis"], 2)
            pos["pnl_pct"]       = round(
                (current_price - pos["entry_price"]) / pos["entry_price"] * 100, 2
            )

            closed_record = self._check_exit_conditions(pos, current_price, data)
            if closed_record:
                positions.remove(pos)
                closed.append(closed_record)

        self._refresh_portfolio_totals(data)
        self.save(data)
        return closed

    # ── Exit logic ────────────────────────────────────────────────────────────

    def _check_exit_conditions(
        self, pos: dict, price: float, data: dict
    ) -> dict | None:
        """
        Returns a closed-trade dict if an exit was triggered, else None.
        Handles partial take-profit at target_1 and stop adjustment.
        """
        portfolio = data["portfolio"]
        entry     = pos["entry_price"]
        tp1       = pos.get("take_profit_1")
        tp2       = pos.get("take_profit_2")
        sl        = pos.get("stop_loss")

        # ── Ratchet trailing stop upward each cycle (after TP1) ─────────────
        if pos.get("trailing_stop_active") and sl:
            atr = pos.get("indicators_at_entry", {}).get("atr")
            if atr and price > 0:
                new_trail = price - 1.5 * atr   # = price × (1 - 1.5×ATR/price)
                if new_trail > sl:
                    pos["stop_loss"] = round(new_trail, 4)
                    sl = pos["stop_loss"]

        # ── Stop-loss ────────────────────────────────────────────────────────
        if sl and price <= sl:
            reason = "trailing_stop" if pos.get("trailing_stop_active") else "stop_loss"
            return self._close_position(pos, price, reason, data)

        # ── Take-profit target 2 (close remaining) ────────────────────────────
        if tp2 and price >= tp2:
            return self._close_position(pos, price, "target_2", data)

        # ── Take-profit target 1 (sell 50%, set ATR-based trailing stop) ──────
        if tp1 and price >= tp1 and not pos["tp1_hit"]:
            half_shares = pos["shares"] / 2
            sale_value  = half_shares * price
            pos["shares"]             -= half_shares
            pos["cost_basis"]         -= half_shares * entry
            pos["partial_sold_shares"]+= half_shares
            pos["partial_sold_value"] += sale_value
            pos["tp1_hit"]             = True
            pos["stop_moved_to_breakeven"] = True

            # ATR-based trailing stop (at least at entry / breakeven)
            atr = pos.get("indicators_at_entry", {}).get("atr")
            if atr and price > 0:
                trail = price - 1.5 * atr
                pos["stop_loss"] = round(max(trail, entry), 4)
                pos["trailing_stop_active"] = True
                logger.info(
                    "TP1 hit %s @ $%.4f — trailing stop set at $%.4f",
                    pos["ticker"], price, pos["stop_loss"],
                )
            else:
                pos["stop_loss"] = entry   # fallback: breakeven
                pos["trailing_stop_active"] = False
                logger.info(
                    "TP1 hit %s @ $%.4f — stop moved to breakeven $%.4f",
                    pos["ticker"], price, entry,
                )

            portfolio["available_cash"] += sale_value
            return None

        # ── Holding period timeout ────────────────────────────────────────────
        entry_dt = datetime.fromisoformat(pos["entry_date"])
        days_held = (datetime.now(timezone.utc) - entry_dt).days
        if days_held >= pos.get("holding_days", 21):
            return self._close_position(pos, price, "timeout", data)

        return None

    def _close_position(
        self, pos: dict, exit_price: float, reason: str, data: dict
    ) -> dict:
        portfolio = data["portfolio"]

        # Include any partial sale proceeds already banked
        remaining_value = pos["shares"] * exit_price
        total_proceeds  = remaining_value + pos.get("partial_sold_value", 0.0)
        original_cost   = (pos["shares"] + pos.get("partial_sold_shares", 0.0)) * pos["entry_price"]
        pnl             = total_proceeds - original_cost
        pnl_pct         = (pnl / original_cost * 100) if original_cost else 0.0

        portfolio["available_cash"]  += remaining_value
        portfolio["invested_amount"] -= pos["cost_basis"]
        portfolio["invested_amount"]  = max(0.0, portfolio["invested_amount"])

        closed = {
            "id":                    pos["id"],
            "ticker":                pos["ticker"],
            "type":                  pos["type"],
            "entry_price":           pos["entry_price"],
            "exit_price":            round(exit_price, 4),
            "entry_date":            pos["entry_date"],
            "exit_date":             datetime.now(timezone.utc).isoformat(),
            "result":                "profit" if pnl > 0 else ("loss" if pnl < 0 else "breakeven"),
            "pct_change":            round(pnl_pct, 2),
            "pnl":                   round(pnl, 2),
            "exit_reason":           reason,
            "indicators_at_entry":   pos.get("indicators_at_entry", {}),
            "confidence_at_entry":   pos.get("confidence", 0),
            "was_correct":           pnl > 0,
            "key_signals":           pos.get("key_signals", []),
            "risk_level":            pos.get("risk_level", "medium"),
        }

        logger.info("Closed %s @ $%.4f (%s): P&L=%.2f%% (%s)",
                    pos["ticker"], exit_price, reason, pnl_pct, closed["result"])
        return closed

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_current_price(self, ticker: str) -> float | None:
        try:
            info = yf.Ticker(ticker).fast_info
            price = getattr(info, "last_price", None)
            return float(price) if price else None
        except Exception:
            return None

    def _refresh_portfolio_totals(self, data: dict) -> None:
        portfolio  = data["portfolio"]
        positions  = data["active_positions"]

        invested   = sum(p["cost_basis"] for p in positions)
        mkt_value  = sum(p.get("current_value", p["cost_basis"]) for p in positions)
        total      = portfolio["available_cash"] + mkt_value
        start      = portfolio.get("starting_capital", 500.0)
        deposited  = portfolio.get("total_deposited", 500.0)

        portfolio["invested_amount"]  = round(invested, 2)
        portfolio["total_value"]      = round(total, 2)
        portfolio["total_pnl"]        = round(total - deposited, 2)
        portfolio["total_pnl_pct"]    = round((total - deposited) / deposited * 100, 2) if deposited else 0.0

        # Append to equity curve (at most once per hour to keep it lean)
        curve = portfolio.get("equity_curve", [])
        now   = datetime.now(timezone.utc).isoformat()
        if not curve or curve[-1]["value"] != round(total, 2):
            curve.append({"date": now, "value": round(total, 2)})
        portfolio["equity_curve"] = curve[-500:]  # keep last 500 data points
