from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from demo_trader.maya_client import MAYA_BASE, _headers

logger = logging.getLogger(__name__)

_MAYA_HOST = "maya.tase.co.il"


def is_maya_url(url: str) -> bool:
    return _MAYA_HOST in (url or "").lower()


def _attachments_from_snippet(snippet: str | None) -> list[dict[str, Any]]:
    if not snippet:
        return []
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        return []
    atts = data.get("attachments")
    if not isinstance(atts, list):
        return []
    return [a for a in atts if isinstance(a, dict)]


def _extract_text_from_bytes(raw: bytes, *, file_type: str, max_chars: int) -> str | None:
    ft = (file_type or "").lower()
    if ft in {"htm", "html", "edit"} or raw[:15].lstrip().lower().startswith((b"<!doctype", b"<html")):
        try:
            import trafilatura
        except ImportError:
            text = raw.decode("utf-8", errors="replace")
        else:
            html = raw.decode("utf-8", errors="replace")
            text = trafilatura.extract(html) or ""
        text = " ".join(text.split()).strip()
        if text:
            return text[:max_chars] if len(text) > max_chars else text
        return None
    if ft.startswith("pdf") or raw[:4] == b"%PDF":
        try:
            from io import BytesIO

            from pypdf import PdfReader
        except ImportError:
            logger.debug("pypdf not installed; skip Maya PDF attachment")
            return None
        try:
            reader = PdfReader(BytesIO(raw))
            parts: list[str] = []
            for page in reader.pages[:40]:
                parts.append(page.extract_text() or "")
            text = " ".join(" ".join(parts).split()).strip()
            if text:
                return text[:max_chars] if len(text) > max_chars else text
        except Exception as e:
            logger.warning("Maya PDF extract failed: %s", e)
        return None
    return None


def fetch_maya_attachment_text(
    snippet: str | None,
    *,
    timeout_sec: int,
    max_bytes: int,
    max_chars: int,
    referer_path: str = "/he/reports/breaking-announcements",
) -> str | None:
    """Download Maya report HTM/PDF attachments listed in ingest snippet JSON."""
    attachments = _attachments_from_snippet(snippet)
    if not attachments:
        return None

    # Prefer HTML disclosure, then PDF variants.
    def rank(att: dict[str, Any]) -> int:
        ft = str(att.get("fileType") or "").lower()
        if ft in {"htm", "html"}:
            return 0
        if ft.startswith("pdf"):
            return 1
        if ft == "edit":
            return 2
        return 9

    attachments = sorted(attachments, key=rank)
    hdrs = _headers(referer_path)

    for att in attachments:
        rel = str(att.get("url") or "").strip()
        if not rel:
            continue
        if rel.startswith("http"):
            full_url = rel
        else:
            full_url = f"{MAYA_BASE}/{rel.lstrip('/')}"
        ft = str(att.get("fileType") or "")
        try:
            with requests.get(full_url, headers=hdrs, timeout=timeout_sec, stream=True) as r:
                r.raise_for_status()
                buf = bytearray()
                for chunk in r.iter_content(65_536):
                    if not chunk:
                        continue
                    buf.extend(chunk)
                    if len(buf) >= max_bytes:
                        break
            text = _extract_text_from_bytes(bytes(buf), file_type=ft, max_chars=max_chars)
            if text:
                return text
        except Exception as e:
            logger.warning("Maya attachment fetch failed %s: %s", full_url[:100], e)
    return None


def report_id_from_maya_page_url(url: str) -> int | None:
    m = re.search(r"/reports/[^/]+/(\d+)\s*$", (url or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None
