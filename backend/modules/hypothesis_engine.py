"""
Hypothesis Engine
Lets users submit a market thesis; Claude researches it and returns
ticker recommendations with confidence scores.

Tickers scoring >= WATCHLIST_MIN_CONFIDENCE are persisted to the
`hypothesis_watchlist` in paper_trades.json so the next discovery
cycle gives them priority.

Workflow
--------
1. User submits thesis string via POST /api/hypothesis
2. Claude identifies 5-10 relevant tickers for the thesis
3. Sentiment module fetches recent headlines for each ticker
4. Claude scores overall thesis confidence + per-ticker conviction
5. Returns structured recommendations; high-confidence tickers added to watchlist
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic

from config import load_json, save_json, PAPER_TRADES_FILE

logger = logging.getLogger(__name__)

WATCHLIST_MIN_CONFIDENCE = 70   # tickers above this go into hypothesis_watchlist
MAX_TICKERS_TO_RESEARCH  = 8    # cap to keep API calls reasonable


# ── Public API ────────────────────────────────────────────────────────────────

def research_hypothesis(thesis: str) -> dict[str, Any]:
    """
    Research a market thesis and return ticker recommendations.

    Parameters
    ----------
    thesis : str
        Free-form market thesis, e.g.
        "AI chip shortage will drive semiconductor stocks higher in 2025"

    Returns
    -------
    {
        "thesis":          str,
        "overall_confidence": int (0-100),
        "thesis_summary":  str,
        "tickers":         list of ticker dicts,
        "watchlist_added": list of ticker strings,
        "researched_at":   ISO timestamp,
    }
    """
    client = Anthropic()

    # ── Step 1: Identify relevant tickers ────────────────────────────────────
    tickers = _identify_tickers(client, thesis)
    if not tickers:
        return {
            "thesis":             thesis,
            "overall_confidence": 0,
            "thesis_summary":     "Could not identify relevant tickers for this thesis.",
            "tickers":            [],
            "watchlist_added":    [],
            "researched_at":      datetime.now(timezone.utc).isoformat(),
        }

    # ── Step 2: Fetch sentiment headlines for each ticker ────────────────────
    ticker_headlines: dict[str, list[str]] = {}
    try:
        from modules.sentiment import get_sentiment
        for t in tickers[:MAX_TICKERS_TO_RESEARCH]:
            sentiment = get_sentiment(t)
            ticker_headlines[t] = sentiment.get("headlines", [])[:5]
    except Exception as exc:
        logger.warning("Sentiment fetch failed during hypothesis research: %s", exc)

    # ── Step 3: Score thesis + each ticker ───────────────────────────────────
    scored = _score_thesis(client, thesis, tickers, ticker_headlines)

    # ── Step 4: Persist high-confidence tickers to watchlist ─────────────────
    watchlist_added = _update_watchlist(scored.get("tickers", []), thesis)

    return {
        "thesis":             thesis,
        "overall_confidence": scored.get("overall_confidence", 0),
        "thesis_summary":     scored.get("thesis_summary", ""),
        "tickers":            scored.get("tickers", []),
        "watchlist_added":    watchlist_added,
        "researched_at":      datetime.now(timezone.utc).isoformat(),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _identify_tickers(client: Anthropic, thesis: str) -> list[str]:
    """Ask Claude to return a JSON list of relevant ticker symbols."""
    prompt = (
        f"A trader has submitted this market thesis:\n\n\"{thesis}\"\n\n"
        "Identify the 5-10 publicly traded US stocks or ETFs most likely to "
        "benefit if this thesis is correct. Focus on direct beneficiaries, "
        "not just tangentially related companies.\n\n"
        "Reply with ONLY a JSON array of ticker symbols, no explanation. "
        'Example: ["NVDA","AMD","INTC","SMH","SOXX"]'
    )
    try:
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        tickers = json.loads(text)
        if isinstance(tickers, list):
            return [str(t).upper().strip() for t in tickers if t]
    except Exception as exc:
        logger.warning("Ticker identification failed: %s", exc)
    return []


def _score_thesis(
    client: Anthropic,
    thesis: str,
    tickers: list[str],
    ticker_headlines: dict[str, list[str]],
) -> dict[str, Any]:
    """Ask Claude to score overall thesis confidence and each ticker."""
    # Build headlines section
    headlines_section = ""
    for ticker in tickers[:MAX_TICKERS_TO_RESEARCH]:
        headlines = ticker_headlines.get(ticker, [])
        if headlines:
            joined = "\n  - ".join(headlines)
            headlines_section += f"\n{ticker}:\n  - {joined}\n"
        else:
            headlines_section += f"\n{ticker}: (no recent headlines available)\n"

    prompt = f"""You are a professional equity analyst. A trader has submitted this thesis:

"{thesis}"

Relevant tickers and their recent headlines:
{headlines_section}

Evaluate this thesis and score each ticker. Respond ONLY with valid JSON in this exact format:
{{
  "overall_confidence": <integer 0-100>,
  "thesis_summary": "<1-2 sentence assessment of the thesis>",
  "tickers": [
    {{
      "ticker": "<SYMBOL>",
      "confidence": <integer 0-100>,
      "rationale": "<1 sentence why this ticker benefits>",
      "risk": "<one key risk>"
    }}
  ]
}}

Score meanings: 0-49 = weak/speculative, 50-69 = plausible, 70-84 = strong, 85-100 = very high conviction.
Only include tickers you believe are genuinely relevant. Omit any that are only tangentially related."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as exc:
        logger.warning("Thesis scoring failed: %s", exc)
        # Fallback: return tickers unscored
        return {
            "overall_confidence": 0,
            "thesis_summary": "Scoring unavailable.",
            "tickers": [{"ticker": t, "confidence": 0, "rationale": "", "risk": ""} for t in tickers],
        }


def _update_watchlist(ticker_results: list[dict], thesis: str) -> list[str]:
    """
    Persist tickers with confidence >= WATCHLIST_MIN_CONFIDENCE to
    the hypothesis_watchlist in paper_trades.json.
    Returns the list of tickers added.
    """
    added: list[str] = []
    high_conf = [
        t for t in ticker_results
        if t.get("confidence", 0) >= WATCHLIST_MIN_CONFIDENCE
    ]
    if not high_conf:
        return added

    try:
        data      = load_json(PAPER_TRADES_FILE)
        portfolio = data.setdefault("portfolio", {})
        watchlist = portfolio.setdefault("hypothesis_watchlist", [])

        existing_tickers = {w["ticker"] for w in watchlist}
        now = datetime.now(timezone.utc).isoformat()

        for item in high_conf:
            ticker = item["ticker"]
            if ticker not in existing_tickers:
                watchlist.append({
                    "ticker":     ticker,
                    "confidence": item.get("confidence", 0),
                    "rationale":  item.get("rationale", ""),
                    "thesis":     thesis[:200],
                    "added_at":   now,
                })
                added.append(ticker)

        portfolio["hypothesis_watchlist"] = watchlist
        save_json(PAPER_TRADES_FILE, data)
        logger.info("Hypothesis watchlist updated: added %s", added)
    except Exception as exc:
        logger.warning("Failed to update hypothesis watchlist: %s", exc)

    return added
