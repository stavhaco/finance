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
        "עליך להחזיר JSON תקף בלבד (בלי markdown או טקסט נוסף). "
        "השוואת ביצועים למדד ת\"א-35 (פרוקסי דרך Yahoo Finance). "
        "אין ספר פקודות אמיתי — אל תבטיח רווחים. "
        "כל ההיגיון העסקי למנהלים חייב להיות באנגלית בשדות why_en ו-evidence_* שמתבססים על טבלת Knowledge center "
        "(עמודת news_id שלמה בלבד ב-evidence_news_ids). "
        "analysis_he הוא משפט תקציר קצר בעברית ללוג פנימי (יכול להיות מחרוזת ריקה). "
        "כשמותר לסחור: העדף מזומן נמוך — פריסת פוזיציות מתונה על TA-35 (סיכון נמוך)."
    )
    gate = "כן" if trading_allowed else "לא"
    user = f"""האם כרגע מותר לבצע פעולות מסחר (חלון מסחר פשוט בת\"א)? {gate}

סביבת מניות (רק סימולים אלה מותרים לפעולות קנייה/מכירה):
{list(watchlist)}

קטלוג וקטגוריות TA-35 (מאגר ידע בסיסי):
{catalog_digest}

מאגר ידע מהרצות קודמות (מסונן ל-TA-35 בלבד; כולל news_id לציטוט):
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

Knowledge center (English table; SQLite-enriched TA-35 rows only — cite **news_id** integers here):
{article_context_en or "(none)"}

החזר JSON בצורה:
{{
  "analysis_he": "",
  "recommendations": [
    {{
      "symbol": "TEVA.TA",
      "stance": "hold",
      "why_en": "English paragraph explaining stance vs NEW information.",
      "evidence_news_ids": [],
      "evidence_quote": "Short English phrase grounded in cited rows."
    }}
  ],
  "trades": [
    {{
      "symbol": "TEVA.TA",
      "side": "buy",
      "qty": 10,
      "why_en": "English — must align with recommendation for same symbol.",
      "evidence_news_ids": [],
      "evidence_quote": ""
    }}
  ]
}}

חוקים מחייבים:
- recommendations: בדיוק פריט אחד לכל סימבול בסדר הרשימה {list(watchlist)}
- stance בכל המלצה חייב להיות במדויק באנגלית האחת מהערכים buy או sell או hold (מחרוזת יחידה, לא רשימת אפשרויות)
- evidence_news_ids: מערך שלמים מהעמודה news_id בטבלה האנגלית בלבד; אם אין התאמה ישירה — מערך ריק []
- evidence_quote: באנגלית, משפט קצר שמשקף ציטוט מהידיעות שצורפו (יכול להיות ריק רק אם evidence_news_ids ריק)
- trades: לכל היותר {max_trades} עסקאות ביצוע (buy/sell עם qty חיובי שלם)
- אם אסור מסחר כרגע (לא), החזר trades תמיד ריק [], אך המלא recommendations באופן מלא
- אם מותר לסחור (כן) ויש מזומן גבוה ביחס ל-NAV (ראה תיק): הצע לפחות {min_buys_when_trading} קנייות buy מתונות בעד {max_trades} סימבולים שונים — והצג stance=buy בהמלצה וב-trade באותו סימבול
- כל שורת trade חייבת לכלול את אותם שדות why_en / evidence_news_ids / evidence_quote כמו ההחלטה הלוגית עבור אותו סימבול
- side רק buy או sell
"""
    return system, user
