from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests

logger = logging.getLogger(__name__)

MAYA_BASE = "https://maya.tase.co.il"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": MAYA_BASE,
}


def _headers(referer_path: str) -> dict[str, str]:
    h = dict(_DEFAULT_HEADERS)
    h["Referer"] = f"{MAYA_BASE}{referer_path}"
    return h


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _within_lookback(publish_raw: str | None, cutoff_utc: datetime) -> bool:
    dt = _parse_dt(publish_raw)
    if dt is None:
        return True
    return dt >= cutoff_utc


def _company_names(item: dict[str, Any]) -> str:
    names: list[str] = []
    for c in item.get("companies") or []:
        n = (c.get("name") or "").strip()
        if n:
            names.append(n)
    cn = (item.get("companyName") or "").strip()
    if cn:
        names.append(cn)
    return " · ".join(dict.fromkeys(names))


def _snippet(item: dict[str, Any], channel: str) -> str:
    attachments: list[dict[str, Any]] = []
    for att in item.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        rel = att.get("url")
        if not rel:
            continue
        attachments.append(
            {
                "fileType": att.get("fileType"),
                "url": str(rel),
            }
        )
    payload = {
        "channel": channel,
        "formId": item.get("formId"),
        "reporterId": item.get("reporterId"),
        "reportId": item.get("id"),
        "companies": [c.get("name") for c in (item.get("companies") or []) if c.get("name")],
        "companyName": item.get("companyName"),
        "attachments": attachments,
    }
    return json.dumps(payload, ensure_ascii=False)


@dataclass(frozen=True)
class MayaKnowledgeRow:
    source: str
    url: str
    title: str
    publish_raw: str | None
    snippet: str


def _http_timeout(connect_sec: int, read_sec: int) -> tuple[float, float]:
    return (float(max(1, connect_sec)), float(max(1, read_sec)))


def fetch_breaking_announcements(
    limit: int,
    *,
    connect_timeout_sec: int = 10,
    read_timeout_sec: int = 25,
) -> list[dict[str, Any]]:
    # API returns 400 if limit is not in 1..5 ("'Limit' חייב להיות בין 1 לבין 5").
    req_limit = min(5, max(1, int(limit)))
    if req_limit < int(limit):
        logger.debug(
            "Maya breaking-announcement limit capped from %s to %s (API allows at most 5)",
            limit,
            req_limit,
        )
    url = f"{MAYA_BASE}/api/v1/reports/breaking-announcement"
    r = requests.get(
        url,
        params={"limit": req_limit},
        headers=_headers("/he/reports/breaking-announcements"),
        timeout=_http_timeout(connect_timeout_sec, read_timeout_sec),
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _post_list(
    path: str,
    body: dict[str, Any] | None,
    *,
    connect_timeout_sec: int,
    read_timeout_sec: int,
) -> list[dict[str, Any]]:
    url = f"{MAYA_BASE}/api/v1/reports/{path}"
    hdrs = _headers(f"/he/reports/{path.split('/')[0]}")
    hdrs["Content-Type"] = "application/json"
    try:
        r = requests.post(
            url,
            json=body or {},
            headers=hdrs,
            timeout=_http_timeout(connect_timeout_sec, read_timeout_sec),
        )
        if r.status_code >= 400:
            logger.warning("Maya POST %s failed: HTTP %s", path, r.status_code)
            return []
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Maya POST %s error: %s", path, e)
        return []


def fetch_companies_reports(
    *, connect_timeout_sec: int = 10, read_timeout_sec: int = 25
) -> list[dict[str, Any]]:
    return _post_list("companies", {}, connect_timeout_sec=connect_timeout_sec, read_timeout_sec=read_timeout_sec)


def fetch_tase_reports(*, connect_timeout_sec: int = 10, read_timeout_sec: int = 25) -> list[dict[str, Any]]:
    return _post_list("tase", {}, connect_timeout_sec=connect_timeout_sec, read_timeout_sec=read_timeout_sec)


def fetch_financial_reports(
    *, connect_timeout_sec: int = 10, read_timeout_sec: int = 25
) -> list[dict[str, Any]]:
    return _post_list("finance", {}, connect_timeout_sec=connect_timeout_sec, read_timeout_sec=read_timeout_sec)


def normalize_maya_items(
    *,
    lookback_days: int,
    breaking_limit: int,
    post_max_keep: int,
    connect_timeout_sec: int = 10,
    read_timeout_sec: int = 25,
) -> list[MayaKnowledgeRow]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))
    rows: list[MayaKnowledgeRow] = []
    ct = int(connect_timeout_sec)
    rt = int(read_timeout_sec)

    breaking: list[dict[str, Any]] = []
    companies: list[dict[str, Any]] = []
    tase: list[dict[str, Any]] = []
    finance: list[dict[str, Any]] = []

    def _breaking() -> list[dict[str, Any]]:
        return fetch_breaking_announcements(
            breaking_limit, connect_timeout_sec=ct, read_timeout_sec=rt
        )

    tasks = {
        "breaking": _breaking,
        "companies": lambda: fetch_companies_reports(connect_timeout_sec=ct, read_timeout_sec=rt),
        "tase": lambda: fetch_tase_reports(connect_timeout_sec=ct, read_timeout_sec=rt),
        "finance": lambda: fetch_financial_reports(connect_timeout_sec=ct, read_timeout_sec=rt),
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                data = fut.result()
            except Exception as e:
                logger.warning("Maya %s fetch failed: %s", name, e)
                data = []
            if name == "breaking":
                breaking = data
            elif name == "companies":
                companies = data
            elif name == "tase":
                tase = data
            else:
                finance = data

    for it in breaking:
        if not isinstance(it, dict):
            continue
        pub = it.get("publishDate")
        if not _within_lookback(str(pub) if pub is not None else None, cutoff):
            continue
        rid = it.get("id")
        title = str(it.get("title") or "").strip()
        if not title or rid is None:
            continue
        url = f"{MAYA_BASE}/he/reports/breaking-announcements/{rid}"
        rows.append(
            MayaKnowledgeRow(
                source="maya.breaking",
                url=url,
                title=title,
                publish_raw=str(pub) if pub is not None else None,
                snippet=_snippet(it, "breaking"),
            )
        )

    def _consume(items: list[dict[str, Any]], channel: str, path_for_url: str) -> None:
        kept = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            pub = it.get("publishDate")
            if not _within_lookback(str(pub) if pub is not None else None, cutoff):
                continue
            rid = it.get("id")
            if rid is None:
                continue
            title = str(it.get("title") or "").strip()
            if not title:
                cname = str(it.get("companyName") or "").strip()
                form = str(it.get("formId") or "").strip()
                if cname and form:
                    title = f"{cname} — דיווח כספי ({form})"
                elif cname:
                    title = f"{cname} — דיווח כספי"
                else:
                    title = "דיווח כספי (ללא כותרת)"
            url = f"{MAYA_BASE}/he/reports/{path_for_url}/{rid}"
            rows.append(
                MayaKnowledgeRow(
                    source=f"maya.{channel}",
                    url=url,
                    title=title,
                    publish_raw=str(pub) if pub is not None else None,
                    snippet=_snippet(it, channel),
                )
            )
            kept += 1
            if kept >= post_max_keep:
                break

    _consume(companies, "companies", "companies")
    _consume(tase, "tase", "tase")
    _consume(finance, "finance", "financial-report")

    rows.sort(key=lambda r: r.publish_raw or "", reverse=True)
    return rows


def maya_digest_for_prompt(rows: Iterable[MayaKnowledgeRow], *, max_lines: int = 35) -> str:
    lines: list[str] = []
    for r in list(rows)[:max_lines]:
        when = r.publish_raw or ""
        lines.append(f"- [{r.source}] ({when}) {r.title}")
    if not lines:
        return "מאיה: לא נמשכו דיווחים (רשת / חסימה / שגיאה)."
    return "מאיה – דיווחים אחרונים (מסוננים לפי חלון ימים):\n" + "\n".join(lines)
