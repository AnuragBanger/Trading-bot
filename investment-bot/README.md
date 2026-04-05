# Investment Advisory Bot

A self-improving paper-trading bot powered by Claude AI.

Starts with **$500/month paper trading**, learns from every trade, refines its
own parameters, and graduates to real money only when it has proven its edge.

---

## Architecture

```
investment-bot/
├── backend/               FastAPI + Python analysis engine
│   ├── main.py            API server + lifespan scheduler
│   ├── config.py          Paths, env vars, parameter helpers
│   ├── scheduler.py       30-min cycle loop (market hours only)
│   ├── data/
│   │   ├── parameters.json     Live indicator weights & thresholds
│   │   ├── paper_trades.json   Portfolio + active positions
│   │   ├── outcomes.json       Closed trade log + win-rate stats
│   │   ├── refinement_log.json History of self-improvement cycles
│   │   └── watchlist.json      S&P 500 / NASDAQ 100 / ETF universe
│   └── modules/
│       ├── discovery.py        Stock/ETF scanner + ranking
│       ├── technical.py        RSI, MACD, SMA, ATR, BB, Volume
│       ├── fundamental.py      FA scoring (stocks & ETFs)
│       ├── ai_engine.py        Claude signal generation
│       ├── paper_trader.py     Simulated execution + position mgmt
│       ├── outcome_tracker.py  P&L logging + win-rate analytics
│       └── refiner.py          Self-improvement engine
└── frontend/              React dashboard (dark terminal aesthetic)
    └── src/components/
        ├── Dashboard.jsx
        ├── PortfolioOverview.jsx
        ├── ActiveTrades.jsx
        ├── SignalFeed.jsx
        ├── PerformanceChart.jsx
        ├── RefinementLog.jsx
        └── GraduationStatus.jsx
```

---

## Quick Start

### 1. Clone and configure

```bash
cd investment-bot
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Server starts on http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm start
# Dashboard opens on http://localhost:3000
```

---

## How It Works

### Scheduler (every 30 min, 9:30 AM – 4:00 PM ET, weekdays)

1. **Discovery** — Scans S&P 500 + NASDAQ 100 + top 20 ETFs
2. **Filter** — Applies price ($10–$500), volume (>1M), and FA score filters
3. **Analysis** — Computes RSI, MACD, SMA, ATR, Bollinger Bands, volume spikes
4. **AI Signal** — Sends full TA + FA snapshot to Claude → strict JSON signal
5. **Trade** — Opens paper positions for `buy` signals with confidence ≥ threshold
6. **Monitor** — Checks open positions for TP1/TP2/stop-loss hits every cycle
7. **Outcomes** — Logs closed trades with full indicator snapshot
8. **Refinement** — Every 20 closed trades, asks Claude to update `parameters.json`

### Budget & Position Rules

| Rule                  | Value                    |
|-----------------------|--------------------------|
| Monthly deposit       | $500 on the 1st          |
| Max concurrent trades | 4                        |
| Max position size     | 25% of total portfolio   |
| Take Profit 1         | +8–12% → sell 50%        |
| Take Profit 2         | +18–25% → close remaining|
| Stop Loss             | entry − (1.5 × ATR)      |

### Graduation Criteria

The bot tracks its own readiness for real-money trading:

| Criterion                    | Target            |
|------------------------------|-------------------|
| Win rate (last 20 trades)    | ≥ 60%             |
| Average loss on bad trades   | < 15%             |
| Consecutive profitable months| ≥ 2               |
| Total closed trades          | ≥ 20              |

Status: **Learning** → **Improving** → **Ready** 🚀

---

## API Endpoints

| Method | Endpoint                  | Description                        |
|--------|---------------------------|------------------------------------|
| GET    | `/api/dashboard`          | Full dashboard snapshot            |
| GET    | `/api/portfolio`          | Portfolio + P&L                    |
| GET    | `/api/trades/active`      | Open positions (live prices)       |
| GET    | `/api/trades/history`     | All closed trades                  |
| GET    | `/api/signals`            | Latest cycle signals               |
| GET    | `/api/performance`        | Win rates + equity curve           |
| GET    | `/api/refinement/log`     | Parameter change history           |
| GET    | `/api/graduation/status`  | Readiness score + criteria         |
| POST   | `/api/scheduler/run`      | Manually trigger one cycle         |
| GET    | `/api/market/context`     | SPY / QQQ trend                    |
| GET    | `/api/parameters`         | Current weights + thresholds       |
| GET    | `/health`                 | Health check                       |

---

## Self-Improvement Engine

Every 20 closed trades, the bot sends to Claude:
- Full trade outcomes with indicator snapshots
- Current parameter weights
- Win rate breakdown by indicator signal

Claude responds with an updated `parameters.json` containing adjusted weights
and thresholds, plus reasoning for every change. All changes are logged in
`refinement_log.json` with before/after diffs.

---

## Notes

- All trading is **paper only** until you manually graduate to real money
- Data is sourced from Yahoo Finance (free, no API key required)
- The scheduler only runs during NYSE market hours to avoid noise
- Outside market hours, the dashboard still shows live data from the last cycle
- `parameters.json` evolves automatically — do not edit it manually while running
