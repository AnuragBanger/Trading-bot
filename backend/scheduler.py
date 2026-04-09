"""
Scheduler
Runs the full analysis → signal → trade → monitor pipeline every 30 minutes
during market hours (9:30am-4:00pm ET, weekdays).
After market close: monitors positions and checks for outcomes.
Every 20 closed trades: triggers the refinement cycle.
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

logger = logging.getLogger(__name__)

ET_TZ   = pytz.timezone("America/New_York")
MARKET_OPEN  = time(9, 30)
MARKET_CLOSE = time(16, 0)

# ── Shared state (read by API endpoints) ─────────────────────────────────────
_state: dict[str, Any] = {
    "last_run":          None,
    "last_signals":      [],
    "market_context":    {},
    "cycle_count":       0,
    "is_running":        False,
    "market_open":       False,
    "next_run":          None,
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

def run_cycle() -> dict[str, Any]:
    """
    Execute one full analysis cycle.
    Safe to call manually (e.g. via the API).
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
                    "ticker": c["ticker"],
                    "result": c["result"],
                    "pct_change": c["pct_change"],
                    "exit_reason": c["exit_reason"],
                })

        # ── Discovery + signals — only during market hours ────────────────
        if is_market_open():
            market_ctx = get_market_context()
            _update_state(market_context=market_ctx)

            # ── Circuit breaker check ─────────────────────────────────────
            cb = get_circuit_breaker_status()
            summary["circuit_breaker"] = cb["status"]
            if cb["status"] != "normal":
                logger.warning("Circuit breaker [%s]: %s", cb["status"], cb["message"])

            portfolio   = trader.load()
            active_set  = {p["ticker"] for p in portfolio["active_positions"]}
            active_pos  = portfolio["active_positions"]
            params      = load_parameters()

            # Apply circuit breaker overrides to thresholds for this cycle
            min_confidence = params["thresholds"]["min_confidence_to_trade"]
            max_position   = params["thresholds"]["max_position_pct"]
            if cb["min_confidence_override"] is not None:
                min_confidence = cb["min_confidence_override"]
            if cb["max_position_override"] is not None:
                max_position = cb["max_position_override"]

            discovery   = DiscoveryModule()
            ta_analyzer = TechnicalAnalyzer()
            fa_analyzer = FundamentalAnalyzer()

            candidates = discovery.scan(active_tickers=active_set)
            signals    = []

            for candidate in candidates:
                ticker     = candidate["ticker"]
                asset_type = candidate["type"]
                try:
                    ta_data = candidate["ta_snapshot"]
                    fa_data = fa_analyzer.get_details(ticker, asset_type)
                    key_sigs= ta_analyzer.compute_signals_list(ta_data)

                    signal  = generate_signal(
                        ticker=ticker,
                        asset_type=asset_type,
                        ta_data=ta_data,
                        fa_data=fa_data,
                        market_context=market_ctx,
                        key_signals=key_sigs,
                    )
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

                            # Pass circuit-breaker max_position to signal
                            signal["_cb_max_position"] = max_position
                            pos = trader.open_position(signal)
                            if pos:
                                active_pos.append(pos)  # keep local list in sync
                                summary["positions_opened"].append({
                                    "ticker": ticker,
                                    "entry":  pos["entry_price"],
                                    "cost":   pos["cost_basis"],
                                })
                except Exception as exc:
                    logger.warning("Signal generation failed for %s: %s", ticker, exc)
                    summary["errors"].append(f"{ticker}: {exc}")

            _update_state(last_signals=signals, cycle_count=_state["cycle_count"] + 1)
            summary["signals_generated"] = [
                {"ticker": s["ticker"], "signal": s.get("signal"), "confidence": s.get("confidence")}
                for s in signals
            ]

        # ── Refinement check ──────────────────────────────────────────────
        if tracker.should_trigger_refinement():
            logger.info("Triggering self-refinement cycle…")
            new_params = refiner.run()
            summary["refinement_run"] = new_params is not None

    except Exception as exc:
        logger.error("Cycle failed: %s", exc, exc_info=True)
        summary["errors"].append(str(exc))
    finally:
        _update_state(is_running=False)

    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    return summary


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
