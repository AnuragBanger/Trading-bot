"""
Scheduler
Runs the full analysis → signal → trade → monitor pipeline every 30 minutes
during market hours (9:30am-4:00pm ET, weekdays).
After market close: monitors positions and checks for outcomes.
Every 20 closed trades: triggers the refinement cycle.

New in this version
-------------------
- Market regime detection (bull/bear/sideways) adjusts confidence/position thresholds
- Claude API call cap per cycle (max_claude_calls_per_cycle in parameters.json)
- Alerting on circuit breaker state changes and stop-loss exits
- current_regime exposed in _state for dashboard consumption
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, time, timezone
from typing import Any

import pytz

from config import SCHEDULER_INTERVAL_MINUTES, load_parameters
from modules.discovery import DiscoveryModule
from modules.technical import TechnicalAnalyzer
from modules.fundamental import FundamentalAnalyzer
from modules.ai_engine import generate_signal, get_market_context
from modules.paper_trader import PaperTrader
from modules.outcome_tracker import OutcomeTracker
from modules.refiner import Refiner
from modules.circuit_breaker import get_circuit_breaker_status
from modules.correlation_guard import check_correlation
from modules.regime_detector import detect_regime
from modules.alerter import send_alert

logger = logging.getLogger(__name__)

ET_TZ   = pytz.timezone("America/New_York")
MARKET_OPEN  = time(9, 30)
MARKET_CLOSE = time(16, 0)

# ── Shared state (read by API endpoints) ─────────────────────────────────────
_state: dict[str, Any] = {
    "last_run":             None,
    "last_signals":         [],
    "market_context":       {},
    "current_regime":       {},
    "cycle_count":          0,
    "is_running":           False,
    "market_open":          False,
    "next_run":             None,
    "last_circuit_breaker": "normal",   # tracks CB state for transition alerts
}
_state_lock = threading.Lock()


def get_state() -> dict:
    with _state_lock:
        return dict(_state)


def _update_state(**kwargs) -> None:
    with _state_lock:
        _state.update(kwargs)


# ── Market hours check ────────────────────────────────────────────────────────

def is_market_open() -> bool:
    now_et = datetime.now(ET_TZ)
    if now_et.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    t = now_et.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


# ── Main analysis cycle ───────────────────────────────────────────────────────

def run_cycle(force: bool = False) -> dict[str, Any]:
    """
    Execute one full analysis cycle.
    Safe to call manually (e.g. via the API).

    Parameters
    ----------
    force : bool
        When True, runs discovery + signal generation even outside market hours.
        Useful for testing and manual inspection.

    Returns a summary dict.
    """
    if _state["is_running"]:
        return {"status": "skipped", "reason": "cycle already running"}

    _update_state(is_running=True, last_run=datetime.now(timezone.utc).isoformat())
    summary: dict[str, Any] = {
        "started_at":        _state["last_run"],
        "market_open":       is_market_open(),
        "signals_generated": [],
        "positions_opened":  [],
        "positions_closed":  [],
        "refinement_run":    False,
        "circuit_breaker":   "normal",
        "regime":            "unknown",
        "claude_calls_used": 0,
        "errors":            [],
    }

    try:
        trader  = PaperTrader()
        tracker = OutcomeTracker()
        refiner = Refiner()

        # ── Monthly deposit check ─────────────────────────────────────────
        trader.apply_monthly_deposit()

        # ── Monitor existing positions (always, even outside market hours) ─
        closed = trader.monitor_positions()
        if closed:
            tracker.record_many(closed)
            for c in closed:
                summary["positions_closed"].append({
                    "ticker":      c["ticker"],
                    "result":      c["result"],
                    "pct_change":  c["pct_change"],
                    "exit_reason": c["exit_reason"],
                })
                # Alert on stop-loss exits
                if c["exit_reason"] in ("stop_loss", "trailing_stop"):
                    send_alert(
                        "stop_loss_closed",
                        ticker=c["ticker"],
                        pnl_pct=c["pct_change"],
                        exit_price=c.get("exit_price"),
                        exit_reason=c["exit_reason"],
                    )

        # ── Discovery + signals — market hours only, or forced manually ─────
        if is_market_open() or force:
            market_ctx = get_market_context()
            _update_state(market_context=market_ctx)

            # ── Regime detection ──────────────────────────────────────────
            regime_data = detect_regime()
            _update_state(current_regime=regime_data)
            summary["regime"] = regime_data.get("regime", "unknown")

            # ── Circuit breaker check ─────────────────────────────────────
            cb = get_circuit_breaker_status()
            summary["circuit_breaker"] = cb["status"]

            # Alert when circuit breaker state changes
            prev_cb = _state.get("last_circuit_breaker", "normal")
            if cb["status"] != prev_cb:
                _update_state(last_circuit_breaker=cb["status"])
                if cb["status"] in ("soft", "hard"):
                    send_alert(
                        f"circuit_breaker_{cb['status']}",
                        drawdown_pct=round(cb["current_drawdown"] * 100, 1),
                        peak_value=cb["peak_value"],
                        current_value=cb["current_value"],
                        message=cb["message"],
                    )
                elif cb["status"] == "normal" and prev_cb in ("soft", "hard"):
                    send_alert("circuit_breaker_normal", message="Circuit breaker cleared — portfolio recovered")

            if cb["status"] != "normal":
                logger.warning("Circuit breaker [%s]: %s", cb["status"], cb["message"])

            params = load_parameters()

            # ── Threshold resolution: regime → circuit breaker → final ────
            # Regime sets the market-condition baseline; CB is more restrictive on top
            regime_overrides = regime_data.get("overrides", {})
            min_confidence = regime_overrides.get(
                "min_confidence_to_trade",
                params["thresholds"]["min_confidence_to_trade"],
            )
            max_position = regime_overrides.get(
                "max_position_pct",
                params["thresholds"]["max_position_pct"],
            )
            if cb["min_confidence_override"] is not None:
                min_confidence = max(min_confidence, cb["min_confidence_override"])
            if cb["max_position_override"] is not None:
                max_position = min(max_position, cb["max_position_override"])

            max_claude_calls = params.get("max_claude_calls_per_cycle", 15)
            claude_calls     = 0

            portfolio   = trader.load()
            active_set  = {p["ticker"] for p in portfolio["active_positions"]}
            active_pos  = portfolio["active_positions"]

            discovery   = DiscoveryModule()
            ta_analyzer = TechnicalAnalyzer()
            fa_analyzer = FundamentalAnalyzer()

            candidates = discovery.scan(active_tickers=active_set)
            signals    = []

            for candidate in candidates:
                # Respect per-cycle Claude call budget
                if claude_calls >= max_claude_calls:
                    logger.info(
                        "Claude call cap (%d) reached — skipping remaining %d candidates",
                        max_claude_calls, len(candidates) - candidates.index(candidate),
                    )
                    break

                ticker     = candidate["ticker"]
                asset_type = candidate["type"]
                try:
                    ta_data  = candidate["ta_snapshot"]
                    fa_data  = fa_analyzer.get_details(ticker, asset_type)
                    key_sigs = ta_analyzer.compute_signals_list(ta_data)

                    signal = generate_signal(
                        ticker=ticker,
                        asset_type=asset_type,
                        ta_data=ta_data,
                        fa_data=fa_data,
                        market_context=market_ctx,
                        key_signals=key_sigs,
                        regime=regime_data,
                    )
                    claude_calls += 1

                    if signal:
                        signal["_ta_snapshot"] = ta_data
                        signals.append(signal)

                        if (
                            signal.get("signal") == "buy"
                            and signal.get("confidence", 0) >= min_confidence
                            and not cb["new_opens_blocked"]
                        ):
                            # Correlation / sector guard before opening
                            corr = check_correlation(ticker, active_pos)
                            if not corr["allowed"]:
                                logger.info(
                                    "Skipping %s — correlation guard: %s",
                                    ticker, corr["reason"],
                                )
                                continue

                            signal["_cb_max_position"] = max_position
                            pos = trader.open_position(signal)
                            if pos:
                                active_pos.append(pos)
                                summary["positions_opened"].append({
                                    "ticker": ticker,
                                    "entry":  pos["entry_price"],
                                    "cost":   pos["cost_basis"],
                                })
                except Exception as exc:
                    logger.warning("Signal generation failed for %s: %s", ticker, exc)
                    summary["errors"].append(f"{ticker}: {exc}")

            _update_state(
                last_signals=signals,
                cycle_count=_state["cycle_count"] + 1,
            )
            summary["signals_generated"] = [
                {
                    "ticker":     s["ticker"],
                    "signal":     s.get("signal"),
                    "confidence": s.get("confidence"),
                }
                for s in signals
            ]
            summary["claude_calls_used"] = claude_calls

        # ── Refinement check ──────────────────────────────────────────────
        if tracker.should_trigger_refinement():
            logger.info("Triggering self-refinement cycle…")
            send_alert("refinement_triggered", trades_analyzed=tracker.get_stats().get("total_trades", 0))
            new_params = refiner.run()
            summary["refinement_run"] = new_params is not None

        # ── Graduation alert (fire once when first reaching "ready") ──────
        grad = tracker.graduation_status()
        if grad.get("status") == "ready" and not _graduation_alerted():
            send_alert(
                "graduation_ready",
                met_count=grad["met_count"],
                total_criteria=grad["total_criteria"],
                message="All graduation criteria met — bot is ready for real-money trading review",
            )

    except Exception as exc:
        logger.error("Cycle failed: %s", exc, exc_info=True)
        summary["errors"].append(str(exc))
    finally:
        _update_state(is_running=False)

    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    return summary


def _graduation_alerted() -> bool:
    """Prevent repeated graduation alerts by checking if one was already sent."""
    try:
        from modules.alerter import get_alerts
        return any(a["type"] == "graduation_ready" for a in get_alerts(limit=200))
    except Exception:
        return False


# ── Background scheduler ──────────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _scheduler_loop() -> None:
    import time as time_module
    interval_sec = SCHEDULER_INTERVAL_MINUTES * 60
    logger.info("Scheduler started — interval %d min", SCHEDULER_INTERVAL_MINUTES)

    while not _stop_event.is_set():
        try:
            logger.info("Scheduler tick — market_open=%s", is_market_open())
            run_cycle()
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc, exc_info=True)

        # Sleep in small increments so we can respond to stop_event
        for _ in range(interval_sec):
            if _stop_event.is_set():
                break
            time_module.sleep(1)

    logger.info("Scheduler stopped")


def start_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.warning("Scheduler already running")
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler")
    _scheduler_thread.start()


def stop_scheduler() -> None:
    _stop_event.set()
