from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

IL_TZ = ZoneInfo("Asia/Jerusalem")


def maya_publish_to_utc_iso(raw: str | None) -> str | None:
    """Parse Maya `publishDate` strings (typically no timezone) as Asia/Jerusalem, then UTC ISO."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            naive = datetime.strptime(s[:26], fmt)
            return naive.replace(tzinfo=IL_TZ).astimezone(timezone.utc).replace(microsecond=0).isoformat()
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IL_TZ)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except ValueError:
        return None


def rss_published_to_utc_iso(published: str | None) -> str | None:
    """RSS `pubDate` / similar (RFC 2822) -> UTC ISO."""
    if not published:
        return None
    try:
        dt = parsedate_to_datetime(str(published).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def sim_default_start_utc(*, days_ago: int) -> datetime:
    """Start simulation at 00:00 Asia/Jerusalem `days_ago` from 'today' in IL."""
    days_ago = max(1, int(days_ago))
    today_il = datetime.now(IL_TZ).date()
    d0 = today_il - timedelta(days=days_ago)
    return datetime(d0.year, d0.month, d0.day, 0, 0, tzinfo=IL_TZ).astimezone(timezone.utc)


def parse_sim_start_iso(raw: str | None, *, fallback_start: datetime) -> datetime:
    if not raw:
        return fallback_start
    s = raw.strip()
    if not s:
        return fallback_start
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IL_TZ)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return fallback_start
