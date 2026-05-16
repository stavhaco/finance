from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from urllib.parse import urlparse

import feedparser
import requests


@dataclass(frozen=True)
class Headline:
    title: str
    link: str
    source: str
    published: str | None


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc or "rss"
    except Exception:
        return "rss"


def _fetch_feed_bytes(url: str, timeout_sec: int = 30) -> bytes | None:
    headers = {
        "User-Agent": "demo-trader/0.1 (+https://example.local) python-requests",
        "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout_sec)
        if r.status_code >= 400:
            return None
        return r.content
    except Exception:
        return None


def fetch_headlines(feed_urls: Sequence[str], max_items: int) -> list[Headline]:
    items: list[Headline] = []
    for url in feed_urls:
        content = _fetch_feed_bytes(url)
        parsed = feedparser.parse(content if content is not None else url)
        for e in parsed.entries or []:
            title = (getattr(e, "title", None) or "").strip()
            link = (getattr(e, "link", None) or "").strip()
            if not title:
                continue
            pub = getattr(e, "published", None) or getattr(e, "updated", None)
            pub_s = str(pub).strip() if pub else None
            items.append(Headline(title=title, link=link, source=_host(url), published=pub_s))
            if len(items) >= max_items:
                return items
    return items


def mock_headlines() -> list[Headline]:
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return [
        Headline(
            title="Demo headline: TA-35 futures implied volatility rose in overseas markets (MOCK)",
            link="",
            source="demo_trader.mock",
            published=ts,
        ),
        Headline(
            title="Demo headline: Large-cap banks mixed; energy names lagging (MOCK)",
            link="",
            source="demo_trader.mock",
            published=ts,
        ),
    ]


def headlines_digest(headlines: Sequence[Headline], max_lines: int = 25) -> str:
    lines: list[str] = []
    for h in headlines[:max_lines]:
        ts = h.published or ""
        prefix = f"[{h.source}]"
        if ts:
            prefix = f"{prefix} ({ts})"
        lines.append(f"{prefix} {h.title}")
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"As-of {stamp} UTC headlines:\n" + "\n".join(lines)
