from __future__ import annotations

from demo_trader.config import Config
from demo_trader.content_enrich import _host_allowed, fetch_article_text
from demo_trader.maya_content import fetch_maya_attachment_text, is_maya_url


def fetch_knowledge_body(
    url: str,
    snippet: str | None,
    cfg: Config,
) -> str | None:
    """Best-effort article body for knowledge enrichment (RSS HTML or Maya attachments)."""
    if not cfg.knowledge_enrich_fetch_body or not url.startswith("http"):
        return None

    max_chars = cfg.enrich_max_chars_per_article
    timeout = cfg.enrich_fetch_timeout_sec
    max_bytes = cfg.enrich_max_bytes

    if is_maya_url(url):
        body = fetch_maya_attachment_text(
            snippet,
            timeout_sec=timeout,
            max_bytes=max_bytes,
            max_chars=max_chars,
        )
        if body:
            return body

    if not _host_allowed(url, cfg.enrich_url_host_suffixes):
        return None

    return fetch_article_text(
        url,
        timeout_sec=timeout,
        max_bytes=max_bytes,
        max_chars=max_chars,
    )
