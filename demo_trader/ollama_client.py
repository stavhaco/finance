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


def chat_json_schema(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
    schema: dict[str, Any],
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": schema,
    }
    r = requests.post(url, json=payload, timeout=timeout_sec)
    r.raise_for_status()
    data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    raw = _strip_json_fence(str(content))
    return json.loads(raw)


def chat_json_schema_or_fallback(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
    schema: dict[str, Any],
) -> dict[str, Any]:
    try:
        return chat_json_schema(
            base_url=base_url,
            model=model,
            system=system,
            user=user,
            timeout_sec=timeout_sec,
            schema=schema,
        )
    except Exception:
        strict = system + "\n\nReturn JSON only with keys: title_en, translation_en, executive_summary_en, sentiment, trade_usefulness, is_broad_market. No markdown."
        u = user + "\n\nOutput JSON object only."
        return chat_json(
            base_url=base_url,
            model=model,
            system=strict,
            user=u,
            timeout_sec=timeout_sec,
        )



def chat_plain(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
) -> str:
    """Single-turn chat without JSON schema enforcement (translation / summarization)."""
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    r = requests.post(url, json=payload, timeout=timeout_sec)
    r.raise_for_status()
    data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    return _strip_json_fence(str(content)).strip()


def translate_financial_to_english(
    text: str,
    *,
    base_url: str,
    model: str,
    timeout_sec: int,
    max_input_chars: int = 12_000,
) -> str:
    """Translate Hebrew (or mixed) financial excerpt to English via Ollama."""
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) > max_input_chars:
        t = t[: max(0, max_input_chars - 30)].rstrip() + "\n...[truncated for translation]"
    system = (
        "You translate Israeli financial and business news into clear English. "
        "Preserve numbers, percentages, dates, and ticker symbols like TEVA.TA. "
        "Output only the English translation — no preface, no markdown fences."
    )
    return chat_plain(base_url=base_url, model=model, system=system, user=t, timeout_sec=timeout_sec)


def build_hebrew_trader_prompt(
    *,
    watchlist: tuple[str, ...],
    trading_allowed: bool,
    catalog_digest: str,
    knowledge_digest: str,
    fundamentals_digest: str,
    maya_digest: str,
    quotes_text: str,
    portfolio_text: str,
    news_text: str,
    article_context_en: str = "",
    max_trades: int,
    max_cash_pct_target: float = 15.0,
    min_buys_when_trading: int = 1,
) -> tuple[str, str]:
    system = (
        "אתה סוחר ניירות (paper trading) זהיר בשוק הישראלי. "
        "עליך להחזיר JSON בלבד (בלי markdown). "
        "המטרה: להשוות ביצועים למדד ת\"א-35 (פרוקסי דרך Yahoo Finance). "
        "אין לך ספר פקודות אמיתי; אל תבטיח רווחים. "
        "השתמש בעברית בשדות rationale/analysis/reason. "
        "כשמותר לסחור: העדף להחזיק מזומן נמוך — פרוס הון על מניות TA-35 בגודל מתון (סיכון נמוך), "
        "לא להשאיר את רוב התיק במזומן לאורך זמן."
    )
    gate = "כן" if trading_allowed else "לא"
    user = f"""האם כרגע מותר לבצע פעולות מסחר (חלון מסחר פשוט בת\"א)? {gate}

סביבת מניות (רק סימולים אלה מותרים לפעולות קנייה/מכירה):
{list(watchlist)}

קטלוג וקטגוריות TA-35 (מאגר ידע בסיסי):
{catalog_digest}

מאגר ידע מהרצות קודמות (התאמות כותרות לחברות):
{knowledge_digest}

נתוני חברות מהמסד (שווי שוק, תשואות הלכה למעשה, מכפילים – Yahoo):
{fundamentals_digest}

מאיה / דיווחים רשמיים (טקסט מצומצם):
{maya_digest}

תמונת מחירים (Yahoo, עשוי להיות בעיכוב):
{quotes_text}

תיק נוכחי:
{portfolio_text}

כותרות חדשות (RSS, בעברית ככל האפשר):
{news_text}

Enriched knowledge center (English; full translation + executive summary stored in SQLite; excerpt shown):
{article_context_en or "(none)"}

החזר JSON בצורה:
{{
  "analysis_he": "ניתוח קצר",
  "by_symbol": [
    {{
      "symbol": "TEVA.TA",
      "stance": "buy|sell|hold",
      "buy_lo": null,
      "buy_hi": null,
      "sell_lo": null,
      "sell_hi": null,
      "rationale_he": "הסבר קצר"
    }}
  ],
  "trades": [
    {{"symbol": "TEVA.TA", "side": "buy", "qty": 10, "reason_he": "..."}}
  ]
}}

חוקים:
- trades: לכל היותר {max_trades} עסקאות
- אם אסור מסחר כרגע (לא), החזר trades ריק בכל מקרה, אבל עדיין מלא analysis_he ו-by_symbol
- אם מותר לסחור (כן) ו-cash_pct_of_nav מעל {max_cash_pct_target:.0f}%: הצע לפחות {min_buys_when_trading} קנייה/ות buy בגודל מתון
  ב-{max_trades} מניות שונות (פיזור), לא "הכל או כלום". מכירות sell רק אם יש סיבה ברורה.
- סיכון נמוך: עדיף כמה פוזיציות קטנות מאשר hold מלא עם מזומן גבוה
- לכל trade חובה reason_he בעברית (לא רק "מודל")
- side רק buy או sell; qty חיובי (מניות שלמות, לא חלקי מניה)
"""
    return system, user
