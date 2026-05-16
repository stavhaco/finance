from __future__ import annotations

from datetime import datetime
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
