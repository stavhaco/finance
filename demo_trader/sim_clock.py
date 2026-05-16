from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from demo_trader.historic_bars import app_kv_get, app_kv_set


KEY_SIM_NOW = "sim_now_utc_iso"


@dataclass(frozen=True)
class SimClock:
    now: datetime


def load_sim_now(conn, *, default_start: datetime) -> datetime:
    raw = app_kv_get(conn, KEY_SIM_NOW)
    if not raw:
        app_kv_set(conn, KEY_SIM_NOW, default_start.replace(microsecond=0).isoformat())
        return default_start.replace(microsecond=0)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        app_kv_set(conn, KEY_SIM_NOW, default_start.replace(microsecond=0).isoformat())
        return default_start.replace(microsecond=0)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def advance_sim_now(conn, *, new_now: datetime) -> None:
    if new_now.tzinfo is None:
        new_now = new_now.replace(tzinfo=timezone.utc)
    app_kv_set(conn, KEY_SIM_NOW, new_now.astimezone(timezone.utc).replace(microsecond=0).isoformat())


def bump_sim_minutes(conn, *, sim_now: datetime, step_minutes: int) -> datetime:
    nxt = sim_now.astimezone(timezone.utc) + timedelta(minutes=max(1, int(step_minutes)))
    advance_sim_now(conn, new_now=nxt)
    return nxt.replace(microsecond=0)
