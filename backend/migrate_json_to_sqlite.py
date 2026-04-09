"""
One-time migration: JSON files → SQLite (trading_bot.db)

Run once from the backend/ directory:
    python migrate_json_to_sqlite.py

What it migrates
----------------
- outcomes.json  → outcomes table + signals table (no signal history to migrate)
- paper_trades.json → equity_curve table
- refinement_log.json → refinements table

The JSON files are NOT deleted — they remain as the primary store.
This migration seeds the SQLite DB so analytics queries work immediately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import load_json, OUTCOMES_FILE, PAPER_TRADES_FILE, REFINEMENT_LOG_FILE
from modules.db import get_db


def migrate_outcomes(db) -> int:
    data   = load_json(OUTCOMES_FILE)
    trades = data.get("closed_trades", [])
    count  = 0
    for t in trades:
        try:
            db.insert_outcome(t)
            count += 1
        except Exception as exc:
            print(f"  [warn] outcome {t.get('id', '?')}: {exc}")
    return count


def migrate_equity_curve(db) -> int:
    data      = load_json(PAPER_TRADES_FILE)
    portfolio = data.get("portfolio", {})
    curve     = portfolio.get("equity_curve", [])
    count     = 0
    for pt in curve:
        try:
            db.insert_equity_point(
                value=pt.get("value", 0),
                cash=portfolio.get("available_cash", 0),
                invested=portfolio.get("invested_amount", 0),
            )
            count += 1
        except Exception as exc:
            print(f"  [warn] equity point: {exc}")
    return count


def migrate_refinements(db) -> int:
    data        = load_json(REFINEMENT_LOG_FILE)
    refinements = data.get("refinements", [])
    count       = 0
    for r in refinements:
        try:
            db.insert_refinement(r)
            count += 1
        except Exception as exc:
            print(f"  [warn] refinement {r.get('refinement_number', '?')}: {exc}")
    return count


def main() -> None:
    print("Starting JSON → SQLite migration…")
    db = get_db()

    n_out  = migrate_outcomes(db)
    print(f"  outcomes:      {n_out} records")

    n_eq   = migrate_equity_curve(db)
    print(f"  equity curve:  {n_eq} points")

    n_ref  = migrate_refinements(db)
    print(f"  refinements:   {n_ref} records")

    print("\nMigration complete. SQLite DB:", db._path)
    print("JSON files are unchanged and remain the primary store.")


if __name__ == "__main__":
    main()
