from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IL_TZ = ZoneInfo("Asia/Jerusalem")

# Approximation: continuous session Sun–Thu, excluding Friday–Saturday.
# This does not model TASE holidays or special sessions.


def _to_il(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(IL_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=IL_TZ)
    return now.astimezone(IL_TZ)


def is_tase_weekday_il(now: datetime | None = None) -> bool:
    n = _to_il(now)
    return n.weekday() in {6, 0, 1, 2, 3}


def is_tase_regular_trading_hours(now: datetime | None = None) -> bool:
    """Return True during a simplified regular-day continuous window (Asia/Jerusalem)."""
    n = _to_il(now)
    if not is_tase_weekday_il(n):
        return False
    minutes = n.hour * 60 + n.minute
    return (9 * 60) <= minutes <= (17 * 60 + 35)


def next_tase_regular_session_open_utc(after: datetime) -> datetime:
    """Earliest instant >= `after` (any tz) when simplified TASE regular hours are open.

    Session: Sun–Thu, 09:00–17:35 Asia/Jerusalem. If `after` is already inside that window,
    returns `after` normalized to whole seconds in UTC (microseconds cleared).
    """
    after_u = after.astimezone(timezone.utc).replace(microsecond=0)
    il = after_u.astimezone(IL_TZ)
    if is_tase_regular_trading_hours(il):
        return after_u

    base_date = il.date()

    for offset in range(10):
        day = base_date + timedelta(days=offset)
        noon_il = datetime(day.year, day.month, day.day, 12, 0, tzinfo=IL_TZ)
        if not is_tase_weekday_il(noon_il):
            continue

        open_il = datetime(day.year, day.month, day.day, 9, 0, tzinfo=IL_TZ)
        close_il = datetime(day.year, day.month, day.day, 17, 35, 0, tzinfo=IL_TZ)
        open_utc = open_il.astimezone(timezone.utc)

        if offset == 0:
            if il < open_il:
                return open_utc
            if il > close_il:
                continue
            continue

        return open_utc

    return after_u
