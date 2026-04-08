"""
Sentiment Pipeline Module
Fetches news headlines from multiple free RSS sources and scores them
with Claude to produce a per-ticker sentiment signal.

Sources used (no API keys required):
  1. Yahoo Finance RSS  — direct company headlines
  2. Google News RSS    — broader market/analyst coverage

Results are cached for 30 minutes to avoid re-scoring every cycle.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import quote

import anthropic
import httpx

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

CACHE_TTL_MINUTES = 30

# ticker → result dict (including "cached_at" epoch)
_cache: dict[str, dict[str, Any]] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def get_sentiment(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    """
    Return a sentiment snapshot for *ticker*.

    Returns
    -------
    {
        "ticker":           str,
        "sentiment_score":  float,   # -1.0 (very bearish) → 1.0 (very bullish)
        "sentiment_label":  str,     # "bullish" | "neutral" | "bearish"
        "headline_count":   int,
        "key_events":       list[str],  # e.g. ["beat_earnings", "raised_guidance"]
        "headlines":        list[str],  # raw headlines used for scoring
        "sources_used":     list[str],
        "cached":           bool,
    }
    """
    key = ticker.upper()

    if not force_refresh and _is_fresh(key):
        result = dict(_cache[key])
        result["cached"] = True
        return result

    headlines: list[str] = []
    sources: list[str] = []

    yf_headlines = _fetch_yahoo_rss(ticker)
    if yf_headlines:
        headlines.extend(yf_headlines[:5])
        sources.append("yahoo_finance_rss")

    gn_headlines = _fetch_google_news_rss(ticker)
    if gn_headlines:
        headlines.extend(gn_headlines[:5])
        sources.append("google_news_rss")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    headlines = unique[:10]

    if not headlines:
        result = _empty_result(ticker, sources)
    else:
        scored = _score_with_claude(ticker, headlines)
        result = {
            "ticker":          ticker,
            "sentiment_score": scored.get("sentiment_score", 0.0),
            "sentiment_label": scored.get("sentiment_label", "neutral"),
            "headline_count":  len(headlines),
            "key_events":      scored.get("key_events", []),
            "headlines":       headlines,
            "sources_used":    sources,
            "cached":          False,
            "cached_at":       time.time(),
        }

    _cache[key] = result
    return result


def clear_cache() -> None:
    _cache.clear()


# ── RSS fetchers ──────────────────────────────────────────────────────────────

def _fetch_yahoo_rss(ticker: str) -> list[str]:
    url = (
        f"https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={quote(ticker)}&region=US&lang=en-US"
    )
    return _get_rss_titles(url, label=f"Yahoo/{ticker}")


def _fetch_google_news_rss(ticker: str) -> list[str]:
    query = quote(f"{ticker} stock")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    return _get_rss_titles(url, label=f"GoogleNews/{ticker}")


def _get_rss_titles(url: str, label: str) -> list[str]:
    try:
        with httpx.Client(timeout=6.0, follow_redirects=True) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return []
        return _parse_titles(resp.text)
    except Exception as exc:
        logger.debug("RSS fetch failed (%s): %s", label, exc)
        return []


def _parse_titles(xml: str) -> list[str]:
    """Extract <title> content from RSS XML, skip the feed-level title."""
    matches = re.findall(
        r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
        xml,
        re.DOTALL,
    )
    titles = []
    for raw in matches[1:]:   # [0] is the channel/feed title
        clean = (
            raw.strip()
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )
        if clean and len(clean) > 10:
            titles.append(clean)
    return titles[:8]


# ── Claude scoring ────────────────────────────────────────────────────────────

def _score_with_claude(ticker: str, headlines: list[str]) -> dict[str, Any]:
    """Send headlines to Claude for batch sentiment scoring."""
    bullet_list = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""Analyze these recent news headlines for {ticker} stock.
Respond with ONLY valid JSON — no markdown, no commentary.

Headlines:
{bullet_list}

JSON format:
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "<bullish|neutral|bearish>",
  "key_events": [<strings: "beat_earnings","missed_earnings","raised_guidance","cut_guidance",
                   "fda_approval","fda_rejection","merger_announced","acquisition_target",
                   "ceo_change","layoffs","share_buyback","dividend_cut","revenue_miss",
                   "strong_revenue_growth","analyst_upgrade","analyst_downgrade">],
  "brief_summary": "<one sentence>"
}}"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Sentiment scoring failed for %s: %s", ticker, exc)
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "neutral",
            "key_events":      [],
            "brief_summary":   "scoring_unavailable",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_fresh(key: str) -> bool:
    if key not in _cache:
        return False
    age_minutes = (time.time() - _cache[key].get("cached_at", 0)) / 60
    return age_minutes < CACHE_TTL_MINUTES


def _empty_result(ticker: str, sources: list[str]) -> dict[str, Any]:
    return {
        "ticker":          ticker,
        "sentiment_score": 0.0,
        "sentiment_label": "neutral",
        "headline_count":  0,
        "key_events":      [],
        "headlines":       [],
        "sources_used":    sources,
        "cached":          False,
        "cached_at":       time.time(),
    }
