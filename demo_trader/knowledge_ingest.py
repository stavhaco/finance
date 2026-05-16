from __future__ import annotations

import re
import sqlite3

from demo_trader.db import insert_knowledge_event
from demo_trader.news_feeds import Headline
from demo_trader.ta35_catalog import TA35_COMPANIES


def _norm_he(s: str) -> str:
    s = s.replace("״", '"').replace("׳", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_company_text(text: str) -> str | None:
    synthetic = Headline(title=_norm_he(text), link="", source="", published=None)
    return match_company(synthetic)


def match_company(headline: Headline) -> str | None:
    title = _norm_he(headline.title)
    title_l = title.lower()
    for c in TA35_COMPANIES:
        if c.name_he and c.name_he in title:
            return c.symbol
        # ticker without suffix
        base = c.symbol.split(".")[0].lower()
        if base and re.search(rf"\b{re.escape(base)}\b", title_l):
            return c.symbol
        if c.name_en and c.name_en.lower() in title_l:
            return c.symbol
    return None


def ingest_headlines(conn: sqlite3.Connection, headlines: list[Headline]) -> int:
    inserted = 0
    for h in headlines:
        sym = match_company(h)
        ok = insert_knowledge_event(
            conn,
            source=h.source,
            url=h.link or h.source,
            title=h.title,
            snippet=None,
            matched_symbol=sym,
        )
        if ok:
            inserted += 1
    return inserted


def ingest_maya_rows(conn: sqlite3.Connection, rows: list) -> int:
    """Persist Maya `MayaKnowledgeRow` items (duck-typed) into knowledge_events."""
    inserted = 0
    for row in rows:
        title = str(getattr(row, "title", "") or "").strip()
        url = str(getattr(row, "url", "") or "").strip()
        if not title or not url:
            continue
        source = str(getattr(row, "source", "maya"))
        snippet = getattr(row, "snippet", None)
        blob = title
        if snippet:
            blob = f"{title} | {snippet}"
        sym = match_company_text(blob)
        if insert_knowledge_event(
            conn,
            source=source,
            url=url,
            title=title,
            snippet=str(snippet) if snippet is not None else None,
            matched_symbol=sym,
        ):
            inserted += 1
    return inserted

