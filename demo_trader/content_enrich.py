from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from demo_trader.config import Config
from demo_trader.news_feeds import Headline
from demo_trader.ollama_client import translate_financial_to_english

logger = logging.getLogger(__name__)

_HEBREW = re.compile(r"[\u0590-\u05FF]")


def _host_allowed(url: str, suffixes: tuple[str, ...] | None) -> bool:
    if not suffixes:
        return True
    try:
        host = (urlparse(url).netloc or "").split("@")[-1].split(":")[0].lower()
    except ValueError:
        return False
    if not host:
        return False
    for s in suffixes:
        s = s.strip().lower().lstrip(".")
        if not s:
            continue
        if host == s or host.endswith("." + s):
            return True
    return False


def _is_probably_hebrew(text: str) -> bool:
    return bool(_HEBREW.search(text))


def fetch_article_text(
    url: str,
    *,
    timeout_sec: int,
    max_bytes: int,
    max_chars: int,
    headers: dict[str, str] | None = None,
) -> str | None:
    if not url.startswith(("http://", "https://")):
        return None
    hdrs = dict(headers or {})
    hdrs.setdefault(
        "User-Agent",
        "Mozilla/5.0 (compatible; DemoTrader/1.0) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36",
    )
    hdrs.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    try:
        import trafilatura
    except ImportError as e:
        logger.warning("trafilatura not installed: %s", e)
        return None
    try:
        with requests.get(url, headers=hdrs, timeout=timeout_sec, stream=True) as r:
            r.raise_for_status()
            buf = bytearray()
            for chunk in r.iter_content(65_536):
                if not chunk:
                    continue
                buf.extend(chunk)
                if len(buf) >= max_bytes:
                    break
        raw = bytes(buf).decode("utf-8", errors="replace")
        extracted = trafilatura.extract(raw, url=url) or ""
        text = " ".join(extracted.split()).strip()
        if not text:
            return None
        if len(text) > max_chars:
            text = text[: max(0, max_chars - 3)].rstrip() + "..."
        return text
    except Exception as e:
        logger.warning("Article fetch failed %s: %s", url[:120], e)
        return None


def build_article_context_en(
    cfg: Config,
    headlines: list[Headline],
    maya_rows: list,
) -> str:
    """Fetch a few article URLs, extract text, translate Hebrew excerpts to English for the trader prompt."""
    if not cfg.enrich_article_urls:
        return ""

    allow = cfg.enrich_url_host_suffixes
    blocks: list[str] = []
    seen_urls: set[str] = set()

    def take_url(title: str, source: str, url: str) -> None:
        if len(blocks) >= cfg.enrich_max_articles:
            return
        u = (url or "").strip()
        if not u or u in seen_urls:
            return
        if not _host_allowed(u, allow):
            logger.debug("Skipping URL (host not allowlisted): %s", u[:120])
            return
        seen_urls.add(u)
        body = fetch_article_text(
            u,
            timeout_sec=cfg.enrich_fetch_timeout_sec,
            max_bytes=cfg.enrich_max_bytes,
            max_chars=cfg.enrich_max_chars_per_article,
        )
        if not body:
            return
        out_body = body
        if _is_probably_hebrew(body):
            model_for_tr = cfg.ollama_translate_model or cfg.ollama_model
            try:
                out_body = translate_financial_to_english(
                    body,
                    base_url=cfg.ollama_base_url,
                    model=model_for_tr,
                    timeout_sec=cfg.enrich_translate_timeout_sec,
                    max_input_chars=cfg.enrich_translate_max_input_chars,
                )
            except Exception as e:
                logger.warning("Translation failed for %s: %s", u[:120], e)
                out_body = body

        blocks.append(f"[{source}] {title}\nURL: {u}\n{out_body}")

    for r in maya_rows:
        if len(blocks) >= cfg.enrich_max_articles:
            break
        title = str(getattr(r, "title", "") or "").strip()
        url = str(getattr(r, "url", "") or "").strip()
        src = str(getattr(r, "source", "maya") or "maya")
        if title and url:
            take_url(title, src, url)

    for h in headlines:
        if len(blocks) >= cfg.enrich_max_articles:
            break
        title = (h.title or "").strip()
        link = (h.link or "").strip()
        src = h.source or "rss"
        if title and link:
            take_url(title, src, link)

    if not blocks:
        return ""
    return "\n\n---\n\n".join(blocks)
