"""
AI Engine Module
Uses Claude to generate trade signals and market analysis.
All LLM calls are isolated here so the rest of the codebase stays clean.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, load_parameters, load_json, OUTCOMES_FILE
from modules.sentiment import get_sentiment
from modules.technical import TechnicalAnalyzer

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ── Market context helper ─────────────────────────────────────────────────────

def get_market_context() -> dict[str, Any]:
    """Fetch SPY and QQQ to determine broad market trend."""
    import yfinance as yf
    context: dict[str, Any] = {}
    for sym in ("SPY", "QQQ"):
        try:
            import pandas_ta as ta
            import yfinance as yf
            df = yf.download(sym, period="3mo", interval="1d", progress=False, auto_adjust=True)
            if df is not None and not df.empty:
                if isinstance(df.columns, __import__("pandas").MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                sma50  = ta.sma(df["Close"], length=50)
                sma200 = ta.sma(df["Close"], length=200)
                price  = float(df["Close"].iloc[-1])
                s50    = float(sma50.iloc[-1])  if sma50  is not None and not sma50.empty  else price
                s200   = float(sma200.iloc[-1]) if sma200 is not None and not sma200.empty else price

                if price > s50 > s200:
                    trend = "bull"
                elif price < s50 < s200:
                    trend = "bear"
                else:
                    trend = "sideways"

                context[sym] = {
                    "price": round(price, 2),
                    "sma50": round(s50, 2),
                    "sma200": round(s200, 2),
                    "trend": trend,
                }
        except Exception as exc:
            logger.warning("Market context failed for %s: %s", sym, exc)
            context[sym] = {"trend": "unknown"}
    return context


# ── Signal generation ─────────────────────────────────────────────────────────

def generate_signal(
    ticker: str,
    asset_type: str,
    ta_data: dict,
    fa_data: dict,
    market_context: dict,
    key_signals: list[str],
    regime: dict | None = None,
) -> dict[str, Any] | None:
    """
    Ask Claude for a trade signal.
    Returns parsed JSON dict or None on failure.

    Parameters
    ----------
    regime : dict | None
        Output of regime_detector.detect_regime(). Injected into system prompt
        so Claude applies regime-appropriate signal logic.
    """
    params = load_parameters()
    outcomes_data = load_json(OUTCOMES_FILE)

    # Fetch sentiment data (cached 30 min — cheap to call every cycle)
    sentiment_data: dict[str, Any] = {}
    try:
        sentiment_data = get_sentiment(ticker)
    except Exception as exc:
        logger.warning("Sentiment fetch failed for %s: %s", ticker, exc)

    # Weekly timeframe analysis for multi-timeframe confirmation
    weekly_ta: dict[str, Any] | None = None
    timeframe_alignment = "neutral"
    try:
        _ta = TechnicalAnalyzer()
        weekly_ta = _ta.analyze_weekly(ticker)
        timeframe_alignment = _ta.get_timeframe_alignment(ta_data, weekly_ta)
    except Exception as exc:
        logger.warning("Weekly TA failed for %s: %s", ticker, exc)

    system_prompt = _build_system_prompt(params, market_context, outcomes_data, regime=regime)
    user_message  = _build_user_message(
        ticker, asset_type, ta_data, fa_data, key_signals,
        sentiment_data=sentiment_data,
        weekly_ta=weekly_ta,
        timeframe_alignment=timeframe_alignment,
    )

    logger.info("Requesting signal from Claude for %s", ticker)
    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        signal = json.loads(raw)
        signal["ticker"] = ticker
        return signal
    except json.JSONDecodeError as exc:
        logger.error("Claude returned non-JSON for %s: %s", ticker, exc)
    except Exception as exc:
        logger.error("AI engine error for %s: %s", ticker, exc)
    return None


def _build_system_prompt(
    params: dict,
    market_context: dict,
    outcomes_data: dict,
    regime: dict | None = None,
) -> str:
    stats = outcomes_data.get("stats", {})
    win_rate   = stats.get("win_rate", 0)
    avg_win    = stats.get("avg_win_pct", 0)
    avg_loss   = stats.get("avg_loss_pct", 0)
    total_trades = stats.get("total_trades", 0)

    spy_trend = market_context.get("SPY", {}).get("trend", "unknown")
    qqq_trend = market_context.get("QQQ", {}).get("trend", "unknown")

    weights    = params["indicator_weights"]
    thresholds = params["thresholds"]

    # Build regime section
    if regime and regime.get("regime") != "unknown":
        regime_name = regime["regime"].upper()
        regime_desc = regime.get("description", "")
        rov = regime.get("overrides", {})
        regime_conf  = rov.get("min_confidence_to_trade", thresholds["min_confidence_to_trade"])
        regime_pos   = rov.get("max_position_pct", thresholds["max_position_pct"])
        regime_section = f"""
CURRENT MARKET REGIME: {regime_name}
- {regime_desc}
- Regime-adjusted minimum confidence: {regime_conf}
- Regime-adjusted max position: {regime_pos * 100:.0f}%
- BEAR regime: be extra conservative — only "buy" on very high-conviction setups; prefer "hold".
- BULL regime: standard momentum signals are valid; slight upward bias acceptable.
- SIDEWAYS regime: favour mean-reversion (RSI, Bollinger Bands); avoid momentum breakouts."""
    else:
        regime_section = "\nMARKET REGIME: Unknown — apply standard conservative thresholds."

    return f"""You are an expert quantitative investment analyst for a paper-trading bot.
Your role is to analyze technical and fundamental data and produce precise trade signals.

CURRENT INDICATOR WEIGHTS (use these to weight your analysis):
- RSI weight: {weights['rsi']}
- MACD weight: {weights['macd']}
- SMA trend weight: {weights['sma_trend']}
- Volume spike weight: {weights['volume_spike']}
- Bollinger Bands weight: {weights['bollinger']}
- Fundamental score weight: {weights['fa_score']}

CURRENT THRESHOLDS:
- Minimum confidence to trade: {thresholds['min_confidence_to_trade']}
- RSI oversold level: {thresholds['rsi_oversold_level']}
- RSI overbought level: {thresholds['rsi_overbought_level']}
- Minimum FA score: {thresholds['min_fa_score']}

BROAD MARKET CONTEXT:
- SPY trend: {spy_trend}
- QQQ trend: {qqq_trend}
{regime_section}

RECENT BOT PERFORMANCE ({total_trades} closed trades):
- Win rate: {win_rate:.1f}%
- Average win: {avg_win:.1f}%
- Average loss: {avg_loss:.1f}%

RULES:
1. Respond with STRICT JSON only — no markdown, no commentary outside the JSON.
2. position_size_pct must never exceed 0.25 (25% of available budget).
3. stop_loss = entry_price - (1.5 * ATR).
4. take_profit.target_1 should be entry * 1.08 to 1.12 (8-12% gain).
5. take_profit.target_2 should be entry * 1.18 to 1.25 (18-25% gain).
6. signal must be "buy", "hold", or "sell".
7. confidence 0-100 — only generate "buy" if confidence >= {thresholds['min_confidence_to_trade']}.
8. risk_level: "low" if confidence >= 80, "medium" if >= 65, else "high".
9. TIMEFRAME ALIGNMENT: Only generate "buy" if timeframe_alignment is "bull" or "strong_bull".
   If alignment is "bear" or "strong_bear", prefer "hold" or reduce confidence by 20 points.
10. SENTIMENT: If sentiment_label is "bearish" with key negative events, reduce confidence by 10-15.
    If sentiment_label is "bullish" with positive events (beat_earnings, raised_guidance), increase confidence by 5-10.
    If key_events contains any high-impact events (fda_decision, merger_announced, acquisition_target),
    set risk_level to "high" regardless of confidence.

JSON SCHEMA (respond with ONLY this):
{{
  "ticker": string,
  "type": "stock" | "etf",
  "signal": "buy" | "hold" | "sell",
  "confidence": integer,
  "entry_zone": {{ "low": float, "high": float }},
  "take_profit": {{ "target_1": float, "target_2": float }},
  "stop_loss": float,
  "holding_period": "days" | "weeks" | "months",
  "position_size_pct": float,
  "rationale": string,
  "key_signals": [string],
  "risk_level": "low" | "medium" | "high"
}}"""


def _build_user_message(
    ticker: str,
    asset_type: str,
    ta_data: dict,
    fa_data: dict,
    key_signals: list[str],
    sentiment_data: dict | None = None,
    weekly_ta: dict | None = None,
    timeframe_alignment: str = "neutral",
) -> str:
    # Build weekly section
    if weekly_ta:
        weekly_section = f"""
WEEKLY TIMEFRAME (multi-timeframe confirmation):
- Weekly RSI(14): {weekly_ta.get('rsi_weekly')}
- Weekly MACD Trend: {weekly_ta.get('macd_weekly_trend')} (histogram: {weekly_ta.get('macd_weekly_histogram')})
- Above Weekly SMA20: {weekly_ta.get('above_sma20_weekly')}, SMA50: {weekly_ta.get('above_sma50_weekly')}
- Weekly ATR: {weekly_ta.get('atr_weekly')}
- TIMEFRAME ALIGNMENT: {timeframe_alignment.upper()}"""
    else:
        weekly_section = f"\nTIMEFRAME ALIGNMENT: {timeframe_alignment.upper()} (weekly data unavailable)"

    # Build sentiment section
    if sentiment_data and sentiment_data.get("headline_count", 0) > 0:
        sentiment_section = f"""
NEWS SENTIMENT:
- Sentiment Score: {sentiment_data.get('sentiment_score', 0.0):.2f} ({sentiment_data.get('sentiment_label', 'neutral').upper()})
- Headlines Analyzed: {sentiment_data.get('headline_count', 0)}
- Key Events Detected: {sentiment_data.get('key_events', [])}
- Sources: {', '.join(sentiment_data.get('sources_used', []))}"""
    else:
        sentiment_section = "\nNEWS SENTIMENT: No recent headlines found (treat as neutral)"

    return f"""Analyze {ticker} ({asset_type.upper()}) and generate a trade signal.

DAILY TECHNICAL ANALYSIS:
- Current Price: {ta_data.get('current_price')}
- RSI(14): {ta_data.get('rsi')}
- MACD: {ta_data.get('macd')}, Signal: {ta_data.get('macd_signal_line')}, Histogram: {ta_data.get('macd_histogram')}
- MACD Signal: {ta_data.get('macd_signal')}
- SMA50: {ta_data.get('sma50')}, SMA200: {ta_data.get('sma200')}
- Above SMA50: {ta_data.get('above_sma50')}, Above SMA200: {ta_data.get('above_sma200')}
- SMA Cross: {ta_data.get('sma_cross')}
- EMA20: {ta_data.get('ema20')}, Above EMA20: {ta_data.get('above_ema20')}
- ATR(14): {ta_data.get('atr')}
- Bollinger Band: Lower={ta_data.get('bb_lower')}, Mid={ta_data.get('bb_mid')}, Upper={ta_data.get('bb_upper')}
- BB Signal: {ta_data.get('bb_signal')}, BB %: {ta_data.get('bb_pct')}
- Volume Ratio: {ta_data.get('volume_ratio')}, Volume Spike: {ta_data.get('volume_spike')}
- Support: {ta_data.get('support')}, Resistance: {ta_data.get('resistance')}
{weekly_section}
{sentiment_section}

FUNDAMENTAL DATA:
{json.dumps(fa_data, indent=2, default=str)}

KEY TECHNICAL SIGNALS DETECTED: {key_signals}

Based on all this data (daily TA, weekly alignment, sentiment, and fundamentals), provide your trade signal JSON now."""
