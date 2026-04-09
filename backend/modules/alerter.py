"""
Alerter Module
Writes structured alerts to backend/data/alerts.json (kept to last 200 entries)
and optionally POSTs to a webhook URL via the ALERT_WEBHOOK_URL environment variable.

Alert types
-----------
circuit_breaker_soft     — 15% drawdown threshold crossed, restrictions applied
circuit_breaker_hard     — 25% drawdown threshold crossed, all new opens blocked
circuit_breaker_normal   — circuit breaker cleared / portfolio recovered
stop_loss_closed         — position closed via stop_loss or trailing_stop
refinement_triggered     — self-improvement cycle started
graduation_ready         — all graduation criteria met

Usage
-----
    from modules.alerter import send_alert
    send_alert("stop_loss_closed", ticker="AAPL", pnl_pct=-8.5, exit_price=172.30)
    send_alert("circuit_breaker_soft", drawdown_pct=16.2)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ALERTS_FILE = Path(__file__).parent.parent / "data" / "alerts.json"
_MAX_ALERTS  = 200
_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")


def send_alert(alert_type: str, **kwargs: Any) -> None:
    """
    Record an alert and optionally POST it to a webhook.

    Parameters
    ----------
    alert_type : str
        One of the alert type constants above.
    **kwargs :
        Arbitrary key-value context (ticker, pnl_pct, drawdown_pct, etc.).
    """
    alert = {
        "type":       alert_type,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    _append_to_file(alert)
    logger.info("ALERT [%s]: %s", alert_type, kwargs)

    if _WEBHOOK_URL:
        _post_webhook(alert)


def get_alerts(limit: int = 50) -> list[dict]:
    """Return the most recent `limit` alerts (newest first)."""
    try:
        with open(_ALERTS_FILE) as f:
            data = json.load(f)
        alerts = data.get("alerts", [])
        return list(reversed(alerts[-limit:]))
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning("Could not read alerts file: %s", exc)
        return []


# ── Internal helpers ──────────────────────────────────────────────────────────

def _append_to_file(alert: dict) -> None:
    """Append alert to alerts.json, capping at _MAX_ALERTS entries."""
    try:
        _ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(_ALERTS_FILE) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"alerts": []}

        data["alerts"].append(alert)
        data["alerts"] = data["alerts"][-_MAX_ALERTS:]   # keep last N

        with open(_ALERTS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as exc:
        logger.warning("Failed to write alert to file: %s", exc)


def _post_webhook(alert: dict) -> None:
    """POST alert JSON to the configured webhook URL (fire-and-forget)."""
    try:
        import httpx
        httpx.post(
            _WEBHOOK_URL,
            json=alert,
            timeout=5.0,
        )
    except Exception as exc:
        logger.warning("Webhook POST failed: %s", exc)
