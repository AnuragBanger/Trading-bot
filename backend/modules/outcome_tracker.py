"""
Outcome Tracker Module
Records closed trades, calculates win rates, and tracks performance metrics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import load_json, save_json, OUTCOMES_FILE, REFINEMENT_TRIGGER_TRADES

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """Persist and analyze closed trade outcomes."""

    # ── Record a closed trade ─────────────────────────────────────────────────

    def record(self, closed_trade: dict[str, Any]) -> None:
        """Append a closed trade and recalculate all stats."""
        data = load_json(OUTCOMES_FILE)
        closed_trade["recorded_at"] = datetime.now(timezone.utc).isoformat()
        data["closed_trades"].append(closed_trade)
        data["stats"] = self._compute_stats(data["closed_trades"])
        save_json(OUTCOMES_FILE, data)
        logger.info(
            "Recorded outcome for %s: %s (%.2f%%)",
            closed_trade["ticker"],
            closed_trade["result"],
            closed_trade["pct_change"],
        )

    def record_many(self, closed_trades: list[dict]) -> int:
        """Batch record closed trades.  Returns count recorded."""
        if not closed_trades:
            return 0
        data = load_json(OUTCOMES_FILE)
        now  = datetime.now(timezone.utc).isoformat()
        for ct in closed_trades:
            ct["recorded_at"] = now
            data["closed_trades"].append(ct)
        data["stats"] = self._compute_stats(data["closed_trades"])
        save_json(OUTCOMES_FILE, data)
        logger.info("Recorded %d closed trades", len(closed_trades))
        return len(closed_trades)

    # ── Stats accessors ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return load_json(OUTCOMES_FILE).get("stats", {})

    def get_all_trades(self) -> list[dict]:
        return load_json(OUTCOMES_FILE).get("closed_trades", [])

    def get_last_n_trades(self, n: int = 20) -> list[dict]:
        return self.get_all_trades()[-n:]

    def should_trigger_refinement(self) -> bool:
        stats = self.get_stats()
        return stats.get("trades_since_last_refinement", 0) >= REFINEMENT_TRIGGER_TRADES

    def reset_refinement_counter(self) -> None:
        data = load_json(OUTCOMES_FILE)
        data["stats"]["trades_since_last_refinement"] = 0
        save_json(OUTCOMES_FILE, data)

    # ── Graduation criteria ───────────────────────────────────────────────────

    def graduation_status(self) -> dict[str, Any]:
        """Evaluate whether the bot is ready to graduate to real money."""
        trades = self.get_all_trades()
        stats  = self.get_stats()

        total = len(trades)
        last20 = trades[-20:] if total >= 20 else trades

        # Criterion 1: Win rate >= 60% over last 20 trades
        last20_wins    = sum(1 for t in last20 if t["was_correct"])
        last20_win_rate= (last20_wins / len(last20) * 100) if last20 else 0.0
        criterion_winrate = last20_win_rate >= 60.0 and len(last20) >= 20

        # Criterion 2: Average loss < 15%
        losses = [abs(t["pct_change"]) for t in last20 if not t["was_correct"]]
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        criterion_loss = avg_loss < 15.0

        # Criterion 3: Profitable 2 consecutive months
        criterion_months, consec = self._check_consecutive_profitable_months(trades)

        # Criterion 4: Min 20 closed trades
        criterion_trades = total >= 20

        criteria = {
            "win_rate_60_pct":          {"met": criterion_winrate,  "value": round(last20_win_rate, 1), "target": 60.0},
            "avg_loss_under_15_pct":    {"met": criterion_loss,     "value": round(avg_loss, 1),       "target": 15.0},
            "profitable_2_months":      {"met": criterion_months,   "value": consec,                   "target": 2},
            "min_20_closed_trades":     {"met": criterion_trades,   "value": total,                    "target": 20},
        }

        met_count = sum(1 for c in criteria.values() if c["met"])

        if met_count == 4:
            status = "ready"
        elif met_count >= 2:
            status = "improving"
        else:
            status = "learning"

        trades_remaining = max(0, 20 - total)

        return {
            "status":           status,
            "criteria":         criteria,
            "met_count":        met_count,
            "total_criteria":   4,
            "trades_remaining": trades_remaining,
            "overall_win_rate": stats.get("win_rate", 0.0),
            "last20_win_rate":  round(last20_win_rate, 1),
            "avg_win_pct":      stats.get("avg_win_pct", 0.0),
            "avg_loss_pct":     stats.get("avg_loss_pct", 0.0),
            "total_trades":     total,
        }

    # ── Internal stats computation ────────────────────────────────────────────

    def _compute_stats(self, trades: list[dict]) -> dict:
        total  = len(trades)
        wins   = [t for t in trades if t["was_correct"]]
        losses = [t for t in trades if not t["was_correct"] and t["result"] != "breakeven"]
        evens  = [t for t in trades if t["result"] == "breakeven"]

        win_rate  = len(wins) / total * 100  if total  else 0.0
        avg_win   = sum(t["pct_change"] for t in wins)   / len(wins)   if wins   else 0.0
        avg_loss  = sum(abs(t["pct_change"]) for t in losses) / len(losses) if losses else 0.0

        # ── Win rate by signal combination ────────────────────────────────────
        by_indicator: dict[str, dict] = {}
        for t in trades:
            for sig in t.get("key_signals", []):
                if sig not in by_indicator:
                    by_indicator[sig] = {"trades": 0, "wins": 0, "win_rate": 0.0}
                by_indicator[sig]["trades"] += 1
                if t["was_correct"]:
                    by_indicator[sig]["wins"] += 1
        for sig, v in by_indicator.items():
            v["win_rate"] = round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0.0

        # ── Win rate by sector/category ───────────────────────────────────────
        by_sector: dict[str, dict] = {}
        for t in trades:
            sector = t.get("sector") or t.get("type", "unknown")
            if sector not in by_sector:
                by_sector[sector] = {"trades": 0, "wins": 0, "win_rate": 0.0}
            by_sector[sector]["trades"] += 1
            if t["was_correct"]:
                by_sector[sector]["wins"] += 1
        for s, v in by_sector.items():
            v["win_rate"] = round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0.0

        # ── Monthly performance ───────────────────────────────────────────────
        monthly: dict[str, dict] = {}
        for t in trades:
            month = t.get("exit_date", "")[:7]
            if not month:
                continue
            if month not in monthly:
                monthly[month] = {"trades": 0, "wins": 0, "total_pnl_pct": 0.0}
            monthly[month]["trades"] += 1
            if t["was_correct"]:
                monthly[month]["wins"] += 1
            monthly[month]["total_pnl_pct"] += t["pct_change"]
        monthly_list = [
            {
                "month": k,
                "trades": v["trades"],
                "wins": v["wins"],
                "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0.0,
                "total_pnl_pct": round(v["total_pnl_pct"], 2),
                "profitable": v["total_pnl_pct"] > 0,
            }
            for k, v in sorted(monthly.items())
        ]

        # Count trades since last refinement (tracks rolling counter)
        prev_stats = {}
        try:
            prev_stats = load_json(OUTCOMES_FILE).get("stats", {})
        except Exception:
            pass
        trades_since = prev_stats.get("trades_since_last_refinement", 0)
        prev_total   = prev_stats.get("total_trades", 0)
        new_trades   = total - prev_total
        if new_trades > 0:
            trades_since = min(trades_since + new_trades, REFINEMENT_TRIGGER_TRADES + 1)

        return {
            "total_trades":                  total,
            "winning_trades":                len(wins),
            "losing_trades":                 len(losses),
            "breakeven_trades":              len(evens),
            "win_rate":                      round(win_rate, 1),
            "avg_win_pct":                   round(avg_win, 2),
            "avg_loss_pct":                  round(avg_loss, 2),
            "by_indicator":                  by_indicator,
            "by_sector":                     by_sector,
            "by_market_condition":           self._by_market_condition(trades),
            "monthly_performance":           monthly_list,
            "trades_since_last_refinement":  trades_since,
        }

    def _by_market_condition(self, trades: list[dict]) -> dict:
        result = {
            "bull":     {"trades": 0, "wins": 0, "win_rate": 0.0},
            "bear":     {"trades": 0, "wins": 0, "win_rate": 0.0},
            "sideways": {"trades": 0, "wins": 0, "win_rate": 0.0},
        }
        for t in trades:
            cond = t.get("market_condition", "sideways")
            if cond in result:
                result[cond]["trades"] += 1
                if t["was_correct"]:
                    result[cond]["wins"] += 1
        for v in result.values():
            v["win_rate"] = round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0.0
        return result

    def _check_consecutive_profitable_months(self, trades: list[dict]) -> tuple[bool, int]:
        monthly: dict[str, float] = {}
        for t in trades:
            month = t.get("exit_date", "")[:7]
            if month:
                monthly[month] = monthly.get(month, 0.0) + t["pct_change"]

        sorted_months = [v for _, v in sorted(monthly.items())]
        if len(sorted_months) < 2:
            return False, 0

        consecutive = 0
        max_consec  = 0
        for pnl in sorted_months:
            if pnl > 0:
                consecutive += 1
                max_consec = max(max_consec, consecutive)
            else:
                consecutive = 0

        return max_consec >= 2, max_consec
