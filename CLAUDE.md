# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

### Backend (FastAPI + Python)
```bash
cd backend
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt   # first time
python main.py                    # starts on http://localhost:8000
```

### Frontend (React)
```bash
cd frontend
npm install                       # first time
npm start                         # starts on http://localhost:3000
```

### Environment
Copy `.env.example` to `.env` in the project root and set `ANTHROPIC_API_KEY`.

### Frontend build/lint/test
```bash
cd frontend
npm run build    # production build
npm test         # run tests (react-scripts test)
```

### Database migration
```bash
cd backend
python migrate_json_to_sqlite.py  # one-time migration from JSON to SQLite
```

## Architecture

This is a paper-trading investment bot with a **self-improvement loop** powered by Claude AI.

### Backend (`backend/`)
- **`main.py`** — FastAPI app with all API endpoints. The scheduler starts automatically via the `lifespan` context manager on app startup.
- **`scheduler.py`** — Background thread running `run_cycle()` every 30 minutes during NYSE market hours (9:30 AM–4:00 PM ET, weekdays). Cycle: discover → analyze → generate signal → trade → monitor → refine.
- **`config.py`** — All paths, env vars, and tunable constants. Live indicator weights/thresholds live in `data/parameters.json` and are loaded via `load_parameters()`.

### Backend Modules (`backend/modules/`)
| Module | Responsibility |
|---|---|
| `discovery.py` | Scans S&P 500 + NASDAQ 100 + ETFs for candidates |
| `technical.py` | RSI, MACD, SMA, ATR, Bollinger Bands, volume analysis |
| `fundamental.py` | FA scoring for stocks and ETFs |
| `ai_engine.py` | Sends TA+FA snapshots to Claude; returns structured `buy`/`sell`/`hold` signals |
| `paper_trader.py` | Simulated position execution, TP1/TP2/stop-loss monitoring, monthly deposit |
| `outcome_tracker.py` | P&L logging, win-rate analytics, graduation criteria |
| `refiner.py` | Every 20 closed trades, sends outcomes to Claude to update `parameters.json` |
| `circuit_breaker.py` | Throttles new opens and raises confidence thresholds during drawdown |
| `correlation_guard.py` | Prevents opening highly correlated positions simultaneously |
| `earnings_guard.py` | Blocks new entries around earnings announcements |
| `position_sizer.py` | Kelly criterion-based position sizing |
| `sentiment.py` | News sentiment scoring pipeline |
| `hypothesis_engine.py` | Accepts user market thesis, researches tickers via Claude |
| `db.py` | SQLite layer (WAL mode, per-thread connections) alongside the JSON files |

### Data Storage (`backend/data/`)
- **`parameters.json`** — Live indicator weights and thresholds, updated by the refiner. Do not edit manually while the bot is running.
- **`paper_trades.json`** — Portfolio state and active positions.
- **`outcomes.json`** — Closed trade log with win-rate stats.
- **`refinement_log.json`** — History of parameter changes made by the self-improvement engine.
- **`trading_bot.db`** — SQLite database (signals, outcomes, equity curve, sentiment cache). Configurable via `TRADING_BOT_DB` env var.

### Frontend (`frontend/src/components/`)
React 18 dashboard with dark terminal aesthetic, using Recharts for charting and Lucide React for icons. All API calls go to the backend via the proxy configured in `package.json` (`http://localhost:8000`).

### Key Data Flow
1. Scheduler calls `run_cycle()` every 30 min during market hours
2. `DiscoveryModule.scan()` → candidates with pre-computed TA snapshots
3. `FundamentalAnalyzer` + `TechnicalAnalyzer` → signals list
4. `ai_engine.generate_signal()` → Claude returns structured JSON signal (`buy`/`sell`/`hold` + confidence)
5. If `buy` + confidence ≥ threshold + circuit breaker/correlation guards pass → `PaperTrader.open_position()`
6. Every cycle: `monitor_positions()` checks TP1/TP2/stop-loss hits → `OutcomeTracker.record_many()`
7. Every 20 closed trades: `Refiner.run()` → Claude updates `parameters.json`

### API Endpoints
All endpoints return `{"status": "ok", "data": ...}`. Key ones:
- `GET /api/dashboard` — full snapshot used by the React dashboard
- `POST /api/scheduler/run` — manually trigger one analysis cycle
- `POST /api/hypothesis` — submit a market thesis for Claude to research
- `GET /api/circuit-breaker` — current drawdown protection state
- `GET /api/analytics/signals` — win rate per signal type (SQLite-backed)
