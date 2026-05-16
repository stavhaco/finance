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
    max_trades: int,
) -> tuple[str, str]:
    system = (
        "אתה סוחר ניירות (paper trading) זהיר בשוק הישראלי. "
        "עליך להחזיר JSON בלבד (בלי markdown). "
        "המטרה: להשוות ביצועים למדד ת\"א-35 (פרוקסי דרך Yahoo Finance). "
        "אין לך ספר פקודות אמיתי; אל תבטיח רווחים. "
        "השתמש בעברית בשדות rationale/analysis/reason."
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
- אם stance הוא hold לכל השמות, מותר שמערך העסקאות יהיה ריק
- אם אסור מסחר כרגע (לא), החזר trades ריק בכל מקרה, אבל עדיין מלא analysis_he ו-by_symbol
- side רק buy או sell
- qty חיובי
"""
    return system, user
