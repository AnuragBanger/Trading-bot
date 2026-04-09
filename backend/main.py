"""
FastAPI Backend — Investment Advisory Bot
All API endpoints wired here; scheduler starts on app startup.
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure backend directory is on sys.path when running directly
sys.path.insert(0, str(Path(__file__).parent))

from config import FRONTEND_ORIGIN, load_json, save_json, load_parameters
from config import (
    PAPER_TRADES_FILE, OUTCOMES_FILE,
    REFINEMENT_LOG_FILE, WATCHLIST_FILE,
)
from modules.outcome_tracker import OutcomeTracker
from modules.paper_trader import PaperTrader
from scheduler import (
    start_scheduler, stop_scheduler,
    run_cycle, get_state, is_market_open,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting investment bot scheduler…")
    start_scheduler()
    yield
    logger.info("Shutting down scheduler…")
    stop_scheduler()


app = FastAPI(
    title="Investment Advisory Bot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper ────────────────────────────────────────────────────────────────────

def _ok(data) -> JSONResponse:
    return JSONResponse(content={"status": "ok", "data": data})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard():
    """Full dashboard snapshot."""
    trader  = PaperTrader()
    tracker = OutcomeTracker()

    pt_data    = trader.load()
    portfolio  = pt_data["portfolio"]
    positions  = pt_data["active_positions"]
    stats      = tracker.get_stats()
    grad       = tracker.graduation_status()
    sched      = get_state()
    refine_log = load_json(REFINEMENT_LOG_FILE)
    last_sigs  = sched.get("last_signals", [])

    return _ok({
        "portfolio":          portfolio,
        "active_positions":   positions,
        "stats":              stats,
        "graduation":         grad,
        "market_open":        is_market_open(),
        "market_context":     sched.get("market_context", {}),
        "current_regime":     sched.get("current_regime", {}),
        "last_signals":       last_sigs[-10:],   # last 10 signals
        "last_cycle":         sched.get("last_run"),
        "cycle_count":        sched.get("cycle_count", 0),
        "total_refinements":  refine_log.get("total_refinements", 0),
    })


@app.get("/api/portfolio")
async def portfolio():
    """Current paper portfolio and P&L."""
    trader   = PaperTrader()
    pt_data  = trader.load()
    return _ok(pt_data["portfolio"])


@app.get("/api/trades/active")
async def active_trades():
    """All open positions."""
    trader    = PaperTrader()
    pt_data   = trader.load()
    positions = pt_data["active_positions"]

    # Refresh current prices inline
    import yfinance as yf
    for pos in positions:
        try:
            info  = yf.Ticker(pos["ticker"]).fast_info
            price = getattr(info, "last_price", None)
            if price:
                pos["current_price"] = round(float(price), 4)
                pos["current_value"] = round(pos["shares"] * float(price), 2)
                pos["pnl"]     = round(pos["current_value"] - pos["cost_basis"], 2)
                pos["pnl_pct"] = round(
                    (float(price) - pos["entry_price"]) / pos["entry_price"] * 100, 2
                )
        except Exception:
            pass

    return _ok(positions)


@app.get("/api/trades/history")
async def trade_history():
    """All closed trades."""
    tracker = OutcomeTracker()
    return _ok(tracker.get_all_trades())


@app.get("/api/signals")
async def signals():
    """Latest buy/sell signals from the last scheduler cycle."""
    sched = get_state()
    return _ok(sched.get("last_signals", []))


@app.get("/api/performance")
async def performance():
    """Win rates, metrics, equity curve."""
    tracker   = OutcomeTracker()
    stats     = tracker.get_stats()
    trader    = PaperTrader()
    portfolio = trader.load()["portfolio"]
    return _ok({
        "stats":        stats,
        "equity_curve": portfolio.get("equity_curve", []),
    })


@app.get("/api/refinement/log")
async def refinement_log():
    """Full history of parameter refinements."""
    log = load_json(REFINEMENT_LOG_FILE)
    return _ok(log)


@app.get("/api/graduation/status")
async def graduation_status():
    """Readiness score and criteria breakdown."""
    tracker = OutcomeTracker()
    return _ok(tracker.graduation_status())


@app.post("/api/scheduler/run")
async def manual_run():
    """Manually trigger one analysis cycle."""
    sched = get_state()
    if sched.get("is_running"):
        raise HTTPException(status_code=409, detail="Cycle already in progress")
    import asyncio
    loop    = asyncio.get_event_loop()
    summary = await loop.run_in_executor(None, run_cycle)
    return _ok(summary)


@app.get("/api/market/context")
async def market_context():
    """Current SPY/QQQ trend context."""
    from modules.ai_engine import get_market_context
    import asyncio
    loop    = asyncio.get_event_loop()
    context = await loop.run_in_executor(None, get_market_context)
    return _ok(context)


@app.get("/api/parameters")
async def get_parameters():
    """Current indicator weights and thresholds."""
    return _ok(load_parameters())


@app.get("/api/circuit-breaker")
async def circuit_breaker_status():
    """Current circuit breaker state and drawdown metrics."""
    from modules.circuit_breaker import get_circuit_breaker_status
    return _ok(get_circuit_breaker_status())


class HypothesisRequest(BaseModel):
    thesis: str


@app.post("/api/hypothesis")
async def submit_hypothesis(body: HypothesisRequest):
    """
    Submit a market thesis. Claude researches relevant tickers and scores them.
    High-confidence tickers (>= 70) are added to the hypothesis watchlist
    for priority consideration in the next discovery cycle.
    """
    thesis = body.thesis.strip()
    if not thesis:
        raise HTTPException(status_code=400, detail="thesis is required")
    if len(thesis) > 1000:
        raise HTTPException(status_code=400, detail="thesis must be under 1000 characters")

    from modules.hypothesis_engine import research_hypothesis
    import asyncio
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, research_hypothesis, thesis)
    return _ok(result)


@app.get("/api/hypothesis/watchlist")
async def hypothesis_watchlist():
    """Return tickers currently on the hypothesis watchlist."""
    trader   = PaperTrader()
    pt_data  = trader.load()
    watchlist = pt_data.get("portfolio", {}).get("hypothesis_watchlist", [])
    return _ok(watchlist)


@app.get("/api/analytics/signals")
async def analytics_signals():
    """Win rate per signal type from the SQLite outcomes table."""
    from modules.db import get_db
    db = get_db()
    return _ok(db.win_rate_by_signal())


@app.get("/api/analytics/equity")
async def analytics_equity(limit: int = 500):
    """Equity curve time-series from SQLite (faster than JSON for large histories)."""
    from modules.db import get_db
    db = get_db()
    return _ok(db.get_equity_curve(limit=limit))


@app.get("/api/regime")
async def regime():
    """Current market regime (bull/bear/sideways) and parameter overrides."""
    sched = get_state()
    return _ok(sched.get("current_regime", {}))


# ── Watchlist management ──────────────────────────────────────────────────────

class WatchlistAddRequest(BaseModel):
    ticker: str
    category: str = "custom"   # etfs | sp500_sample | nasdaq100_sample | custom


@app.get("/api/watchlist")
async def get_watchlist():
    """Return the full watchlist with per-category counts."""
    wl = load_json(WATCHLIST_FILE)
    counts = {k: len(v) for k, v in wl.items() if isinstance(v, list)}
    return _ok({"watchlist": wl, "counts": counts})


@app.post("/api/watchlist")
async def add_to_watchlist(body: WatchlistAddRequest):
    """Add a ticker to the watchlist at runtime."""
    from modules.discovery import add_ticker_to_watchlist
    result = add_ticker_to_watchlist(body.ticker.upper().strip(), body.category)
    return _ok(result)


@app.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    """Remove a ticker from all watchlist categories."""
    from modules.discovery import remove_ticker_from_watchlist
    result = remove_ticker_from_watchlist(ticker)
    if not result["removed"]:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} not found in watchlist")
    return _ok(result)


# ── Graduation enforcement ────────────────────────────────────────────────────

@app.post("/api/graduation/approve")
async def graduation_approve():
    """
    Mark the bot as graduated (ready for real-money review) only when all
    graduation criteria are met.  Sets portfolio.graduated = True.
    """
    tracker = OutcomeTracker()
    grad    = tracker.graduation_status()

    if grad["status"] != "ready":
        unmet = [k for k, v in grad["criteria"].items() if not v["met"]]
        raise HTTPException(
            status_code=409,
            detail={
                "error":     "Graduation criteria not yet met",
                "status":    grad["status"],
                "met_count": grad["met_count"],
                "unmet":     unmet,
            },
        )

    data      = load_json(PAPER_TRADES_FILE)
    portfolio = data["portfolio"]
    if portfolio.get("graduated"):
        return _ok({"message": "Already graduated", "graduated_at": portfolio.get("graduated_at")})

    from datetime import datetime, timezone
    portfolio["graduated"]    = True
    portfolio["graduated_at"] = datetime.now(timezone.utc).isoformat()
    save_json(PAPER_TRADES_FILE, data)

    from modules.alerter import send_alert
    send_alert(
        "graduation_approved",
        message="Bot manually approved for real-money trading review",
        met_count=grad["met_count"],
    )

    return _ok({
        "message":      "Graduation approved — bot is marked ready for real-money review.",
        "graduated_at": portfolio["graduated_at"],
        "criteria":     grad["criteria"],
    })


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    """Return the most recent alerts (circuit breaker, stop-loss, refinement, graduation)."""
    from modules.alerter import get_alerts as _get_alerts
    return _ok(_get_alerts(limit=limit))


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, log_level="info")
