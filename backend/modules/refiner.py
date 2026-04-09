"""
Self-Refinement Engine
Analyzes the last 20 trade outcomes and asks Claude to update parameters.json.
Triggers every REFINEMENT_TRIGGER_TRADES closed trades.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import anthropic

from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    load_parameters, save_parameters,
    load_json, save_json,
    REFINEMENT_LOG_FILE,
)
from modules.outcome_tracker import OutcomeTracker

logger = logging.getLogger(__name__)


class Refiner:
    """Self-improving parameter optimizer."""

    def __init__(self) -> None:
        self.tracker = OutcomeTracker()
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._client

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> dict | None:
        """
        Run a refinement cycle.
        Returns the new parameters dict, or None if refinement was skipped.
        """
        last20 = self.tracker.get_last_n_trades(20)
        if len(last20) < 5:
            logger.info("Not enough trades (%d) for refinement", len(last20))
            return None

        current_params = load_parameters()
        stats          = self.tracker.get_stats()
        new_params     = self._ask_claude(last20, current_params, stats)
        if new_params is None:
            return None

        self._validate_and_clamp(new_params)
        self._log_refinement(current_params, new_params, stats)

        save_parameters(new_params)
        self.tracker.reset_refinement_counter()

        logger.info(
            "Refinement complete — %s",
            new_params.get("refinement_reasoning", "no reasoning provided")[:120],
        )
        return new_params

    # ── Claude call ───────────────────────────────────────────────────────────

    def _ask_claude(
        self, trades: list[dict], params: dict, stats: dict
    ) -> dict | None:
        system_prompt = self._system_prompt()
        user_message  = self._user_message(trades, params, stats)

        try:
            client   = self._get_client()
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)
            return result
        except json.JSONDecodeError as exc:
            logger.error("Refiner received non-JSON from Claude: %s", exc)
        except Exception as exc:
            logger.error("Refiner Claude call failed: %s", exc)
        return None

    def _system_prompt(self) -> str:
        return """You are an expert quantitative trading system optimizer.
Your job is to analyze trade outcomes and refine indicator weights and thresholds
to improve the win rate of a paper-trading bot.

CONSTRAINTS:
- All indicator_weights must be floats between 0.05 and 0.50
- indicator_weights must sum to exactly 1.0
- min_confidence_to_trade: 60-85
- min_fa_score: 40-80
- rsi_oversold_level: 25-45
- rsi_overbought_level: 60-80
- Do NOT make drastic changes — adjust weights by max ±0.10 per cycle
- Respond with STRICT JSON only — no markdown, no text outside JSON

JSON SCHEMA:
{
  "indicator_weights": {
    "rsi": float,
    "macd": float,
    "sma_trend": float,
    "volume_spike": float,
    "bollinger": float,
    "fa_score": float
  },
  "thresholds": {
    "min_confidence_to_trade": int,
    "min_fa_score": int,
    "rsi_oversold_level": int,
    "rsi_overbought_level": int
  },
  "refinement_reasoning": string,
  "trades_analyzed": int
}"""

    def _user_message(self, trades: list[dict], params: dict, stats: dict) -> str:
        # Summarize indicator performance
        by_indicator = stats.get("by_indicator", {})
        indicator_summary = "\n".join(
            f"  {sig}: {v['win_rate']}% win rate over {v['trades']} trades"
            for sig, v in by_indicator.items()
        )

        attribution = self._compute_signal_attribution(trades)

        trades_summary = []
        for t in trades:
            trades_summary.append({
                "ticker":      t["ticker"],
                "result":      t["result"],
                "pct_change":  t["pct_change"],
                "exit_reason": t["exit_reason"],
                "confidence":  t["confidence_at_entry"],
                "key_signals": t.get("key_signals", []),
            })

        risk_section = ""
        sharpe = stats.get("sharpe_ratio")
        pf     = stats.get("profit_factor")
        exp    = stats.get("expectancy_pct")
        max_dd = stats.get("max_drawdown_pct")
        if any(v is not None for v in (sharpe, pf, exp, max_dd)):
            risk_section = (
                f"\nRISK-ADJUSTED METRICS:\n"
                f"- Sharpe Ratio: {sharpe}\n"
                f"- Profit Factor: {pf}\n"
                f"- Expectancy per trade: {exp}%\n"
                f"- Max Drawdown: {max_dd}%\n"
                f"- Max consecutive losses: {stats.get('max_consecutive_losses', 'N/A')}\n"
            )

        return f"""Analyze these {len(trades)} recent trades and refine the parameters to improve performance.

CURRENT PARAMETERS:
{json.dumps(params, indent=2)}

OVERALL STATS:
- Win rate: {stats.get('win_rate', 0)}%
- Avg win: {stats.get('avg_win_pct', 0)}%
- Avg loss: {stats.get('avg_loss_pct', 0)}%
- Total trades: {stats.get('total_trades', 0)}
{risk_section}
INDICATOR WIN RATES (all trades):
{indicator_summary or '  No indicator data yet'}

SIGNAL ATTRIBUTION (causal analysis):
{attribution}

RECENT TRADE OUTCOMES:
{json.dumps(trades_summary, indent=2)}

Based on this data:
1. Increase weights for indicators that appear in winning trades and signal combinations
2. Decrease weights for indicators with low standalone win rates
3. Adjust thresholds to filter out low-confidence trades that are losing
4. If Sharpe < 1.0 or Profit Factor < 1.3, tighten confidence thresholds
5. Provide clear reasoning for each change

Respond with the updated parameters JSON now."""

    def _compute_signal_attribution(self, trades: list[dict]) -> str:
        """
        Compute standalone and combination win rates for each signal.
        Returns a formatted string for the Claude refinement prompt.
        """
        # Individual signal stats
        sig_stats: dict[str, dict] = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in trades:
            for sig in t.get("key_signals", []):
                sig_stats[sig]["total"] += 1
                if t["was_correct"]:
                    sig_stats[sig]["wins"] += 1

        # Two-signal combination stats
        combo_stats: dict[str, dict] = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in trades:
            signals = sorted(t.get("key_signals", []))
            for i, s1 in enumerate(signals):
                for s2 in signals[i + 1:]:
                    combo = f"{s1}+{s2}"
                    combo_stats[combo]["total"] += 1
                    if t["was_correct"]:
                        combo_stats[combo]["wins"] += 1

        lines: list[str] = []

        # Individual signals sorted by win rate (min 2 trades)
        ranked_sigs = sorted(
            [(s, v) for s, v in sig_stats.items() if v["total"] >= 2],
            key=lambda x: x[1]["wins"] / x[1]["total"],
            reverse=True,
        )
        if ranked_sigs:
            lines.append("Individual signals (by win rate):")
            for sig, v in ranked_sigs[:8]:
                wr = round(v["wins"] / v["total"] * 100, 1)
                lines.append(f"  {sig}: {wr}% win rate ({v['wins']}/{v['total']})")

        # Best 2-signal combinations (min 2 trades)
        ranked_combos = sorted(
            [(c, v) for c, v in combo_stats.items() if v["total"] >= 2],
            key=lambda x: x[1]["wins"] / x[1]["total"],
            reverse=True,
        )
        if ranked_combos:
            lines.append("Best 2-signal combinations:")
            for combo, v in ranked_combos[:5]:
                wr = round(v["wins"] / v["total"] * 100, 1)
                lines.append(f"  {combo}: {wr}% ({v['wins']}/{v['total']})")

        return "\n".join(lines) if lines else "  Insufficient data for attribution"

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_and_clamp(self, params: dict) -> None:
        """Ensure weights are valid and sum to 1.0."""
        weights = params.get("indicator_weights", {})
        expected_keys = {"rsi", "macd", "sma_trend", "volume_spike", "bollinger", "fa_score"}

        # Fill missing keys with equal share
        for k in expected_keys:
            if k not in weights:
                weights[k] = 1.0 / len(expected_keys)

        # Clamp each weight
        for k in weights:
            weights[k] = max(0.05, min(0.50, float(weights[k])))

        # Normalize to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            for k in weights:
                weights[k] = round(weights[k] / total, 4)

        params["indicator_weights"] = weights

        # Clamp thresholds
        t = params.get("thresholds", {})
        t["min_confidence_to_trade"] = max(60, min(85, int(t.get("min_confidence_to_trade", 70))))
        t["min_fa_score"]            = max(40, min(80, int(t.get("min_fa_score", 60))))
        t["rsi_oversold_level"]      = max(25, min(45, int(t.get("rsi_oversold_level", 40))))
        t["rsi_overbought_level"]    = max(60, min(80, int(t.get("rsi_overbought_level", 65))))
        params["thresholds"] = t

        # Carry over non-AI-managed thresholds from current params
        current = load_parameters().get("thresholds", {})
        for key in (
            "min_volume", "min_price", "max_price", "volume_spike_multiplier",
            "max_concurrent_positions", "max_position_pct",
            "take_profit_1_pct", "take_profit_2_pct", "stop_loss_atr_multiplier",
        ):
            if key in current:
                params["thresholds"][key] = current[key]

        params["version"]      = current.get("version", 1) + 1
        params["last_updated"] = datetime.now(timezone.utc).isoformat()

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log_refinement(self, old: dict, new: dict, stats: dict) -> None:
        log_data = load_json(REFINEMENT_LOG_FILE)
        entry = {
            "timestamp":         datetime.now(timezone.utc).isoformat(),
            "refinement_number": log_data["total_refinements"] + 1,
            "trades_analyzed":   new.get("trades_analyzed", 20),
            "reasoning":         new.get("refinement_reasoning", ""),
            "before": {
                "indicator_weights": old.get("indicator_weights", {}),
                "thresholds": {
                    k: old.get("thresholds", {}).get(k)
                    for k in ("min_confidence_to_trade", "min_fa_score",
                               "rsi_oversold_level", "rsi_overbought_level")
                },
            },
            "after": {
                "indicator_weights": new.get("indicator_weights", {}),
                "thresholds": {
                    k: new.get("thresholds", {}).get(k)
                    for k in ("min_confidence_to_trade", "min_fa_score",
                               "rsi_oversold_level", "rsi_overbought_level")
                },
            },
            "stats_at_refinement": {
                "win_rate":    stats.get("win_rate", 0),
                "avg_win":     stats.get("avg_win_pct", 0),
                "avg_loss":    stats.get("avg_loss_pct", 0),
                "total_trades":stats.get("total_trades", 0),
            },
        }
        log_data["refinements"].append(entry)
        log_data["total_refinements"] += 1
        save_json(REFINEMENT_LOG_FILE, log_data)
