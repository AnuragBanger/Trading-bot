"""
Central configuration for the Investment Advisory Bot.
All tunable parameters live in data/parameters.json and are loaded here.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

WATCHLIST_FILE      = DATA_DIR / "watchlist.json"
PAPER_TRADES_FILE   = DATA_DIR / "paper_trades.json"
OUTCOMES_FILE       = DATA_DIR / "outcomes.json"
PARAMETERS_FILE     = DATA_DIR / "parameters.json"
REFINEMENT_LOG_FILE = DATA_DIR / "refinement_log.json"

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── AI Model ─────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── Server ───────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# ── Market Hours (ET) ─────────────────────────────────────────────────────────
MARKET_OPEN_HOUR   = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR  = 16
MARKET_CLOSE_MINUTE = 0

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_INTERVAL_MINUTES = 30
REFINEMENT_TRIGGER_TRADES  = 20  # trigger refinement every N closed trades

# ── Budget ───────────────────────────────────────────────────────────────────
MONTHLY_BUDGET = 500.0  # USD added on the 1st of each month


def load_parameters() -> dict:
    """Load live parameters from parameters.json."""
    with open(PARAMETERS_FILE) as f:
        return json.load(f)


def save_parameters(params: dict) -> None:
    """Persist updated parameters to parameters.json."""
    with open(PARAMETERS_FILE, "w") as f:
        json.dump(params, f, indent=2)


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict | list) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
