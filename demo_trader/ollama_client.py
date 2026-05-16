from __future__ import annotations

import json
import re
from typing import Any

import requests


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def chat_json(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
    }
    r = requests.post(url, json=payload, timeout=timeout_sec)
    r.raise_for_status()
    data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    raw = _strip_json_fence(str(content))
    return json.loads(raw)


def build_prompt(
    *,
    watchlist: tuple[str, ...],
    quotes_text: str,
    portfolio_text: str,
    news_text: str,
    max_trades: int,
) -> tuple[str, str]:
    system = (
        "You are a cautious paper-trading research assistant for Israeli equities (Yahoo .TA symbols). "
        "You must output ONLY valid JSON (no markdown). "
        "You do not have order-book data: treat 'arbitrage' as relative-value hypotheses between names in the watchlist, "
        "not guaranteed profit. Never invent symbols outside the watchlist."
    )
    user = f"""Watchlist (only trade these exact symbols): {list(watchlist)}

Market snapshot:
{quotes_text}

Portfolio:
{portfolio_text}

News / headlines context:
{news_text}

Return JSON with this shape:
{{
  "analysis": "short reasoning in English or Hebrew",
  "relative_value_notes": "optional cross-name comparisons; may be empty string",
  "trades": [
    {{"symbol": "TEVA.TA", "side": "buy", "qty": 10, "reason": "..."}}
  ]
}}

Rules:
- trades array length <= {max_trades}
- qty must be a positive number (fractional shares allowed for ETFs like TA35.TA; otherwise prefer whole shares)
- side is only "buy" or "sell"
- If no good action, return an empty trades array
"""
    return system, user
