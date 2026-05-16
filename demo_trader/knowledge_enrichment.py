from __future__ import annotations

import logging
from typing import Any

from demo_trader.config import Config
from demo_trader.content_enrich import _host_allowed, fetch_article_text
from demo_trader.db import (
    get_knowledge_event_by_id,
    update_knowledge_enrichment,
)
from demo_trader.ollama_client import chat_json_schema_or_fallback

logger = logging.getLogger(__name__)


ENRICHMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title_en": {"type": "string"},
        "translation_en": {"type": "string"},
        "executive_summary_en": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "trade_usefulness": {"type": "string", "enum": ["high", "medium", "low"]},
        "is_broad_market": {"type": "boolean"},
    },
    "required": [
        "title_en",
        "translation_en",
        "executive_summary_en",
        "sentiment",
        "trade_usefulness",
        "is_broad_market",
    ],
}


def _truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: max(0, n - 3)].rstrip() + "..."


def _build_source_blob(
    *,
    title: str,
    snippet: str | None,
    body: str | None,
    max_chars: int,
) -> str:
    parts: list[str] = [f"TITLE (Hebrew/mixed):\n{title.strip()}"]
    if snippet:
        parts.append(f"METADATA / SNIPPET:\n{snippet.strip()}")
    if body:
        parts.append(f"ARTICLE BODY (extracted):\n{body.strip()}")
    blob = "\n\n".join(parts).strip()
    return _truncate(blob, max_chars)


def enrich_knowledge_event_by_id(
    conn,
    row_id: int,
    cfg: Config,
    *,
    force: bool = False,
) -> bool:
    """LLM: translate + summary + sentiment/tags; optionally fetch article HTML first. Returns True on success."""
    row = get_knowledge_event_by_id(conn, row_id)
    if row is None:
        return False
    status = (row.get("enrichment_status") or "").strip().lower()
    if status == "ok" and not force:
        return True

    update_knowledge_enrichment(
        conn,
        row_id,
        enrichment_status="pending",
        enrichment_error=None,
    )

    url = str(row.get("url") or "").strip()
    title = str(row.get("title") or "").strip()
    snippet = row.get("snippet")
    snippet_s = str(snippet).strip() if snippet is not None else ""

    body: str | None = None
    if cfg.knowledge_enrich_fetch_body and url.startswith("http") and _host_allowed(url, cfg.enrich_url_host_suffixes):
        body = fetch_article_text(
            url,
            timeout_sec=cfg.enrich_fetch_timeout_sec,
            max_bytes=cfg.enrich_max_bytes,
            max_chars=cfg.enrich_max_chars_per_article,
        )

    blob = _build_source_blob(
        title=title,
        snippet=snippet_s or None,
        body=body,
        max_chars=cfg.knowledge_enrich_max_body_chars,
    )

    model = cfg.ollama_enrichment_model or cfg.ollama_model
    system = (
        "You analyze Israeli capital-markets news for a TA-35 paper trader. "
        "Return JSON only matching the schema. "
        "translation_en must faithfully translate all substantive Hebrew (or mixed) content "
        "from TITLE+METADATA+ARTICLE BODY into English (full translation, not bullet paraphrase). "
        "If only a short title exists, translate it and keep translation_en focused but complete for that text. "
        "executive_summary_en: 3–6 tight English sentences for a busy trader (key facts, numbers, who it affects). "
        "sentiment: positive / negative / neutral for the tone toward the named stock or market (not your mood). "
        "trade_usefulness: high if it can reasonably matter for buy/sell timing on TA-35 names; medium if contextual; low if noise. "
        "is_broad_market true for macro/regulator/index/BoI/inflation/generic TA-125/TA-35 market moves without one main company."
    )
    user = f"Analyze and translate:\n\n{blob}"

    try:
        data = chat_json_schema_or_fallback(
            base_url=cfg.ollama_base_url,
            model=model,
            system=system,
            user=user,
            timeout_sec=cfg.knowledge_enrich_timeout_sec,
            schema=ENRICHMENT_JSON_SCHEMA,
        )
    except Exception as e:
        logger.warning("Enrichment LLM failed id=%s: %s", row_id, e)
        update_knowledge_enrichment(
            conn,
            row_id,
            enrichment_status="error",
            enrichment_error=str(e)[:2000],
        )
        return False

    try:
        title_en = str(data.get("title_en") or "").strip()
        translation_en = str(data.get("translation_en") or "").strip()
        executive_summary_en = str(data.get("executive_summary_en") or "").strip()
        sentiment = str(data.get("sentiment") or "neutral").strip().lower()
        trade_usefulness = str(data.get("trade_usefulness") or "low").strip().lower()
        is_bm = bool(data.get("is_broad_market"))
        if sentiment not in {"positive", "negative", "neutral"}:
            sentiment = "neutral"
        if trade_usefulness not in {"high", "medium", "low"}:
            trade_usefulness = "low"
    except Exception as e:
        update_knowledge_enrichment(
            conn,
            row_id,
            enrichment_status="error",
            enrichment_error=f"bad_json: {e}"[:2000],
        )
        return False

    update_knowledge_enrichment(
        conn,
        row_id,
        title_en=title_en or None,
        body_translation_en=translation_en or None,
        executive_summary_en=executive_summary_en or None,
        sentiment=sentiment,
        trade_usefulness=trade_usefulness,
        is_broad_market=1 if is_bm else 0,
        enrichment_status="ok",
        enrichment_error=None,
    )
    return True
