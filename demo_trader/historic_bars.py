from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from demo_trader.time_utils import IL_TZ

logger = logging.getLogger(__name__)

KEY_BACKFILL_IL_DATE = "bars_backfill_il_date"


def app_kv_get(conn, key: str) -> str | None:
    cur = conn.execute("SELECT value FROM app_kv WHERE key=?", (key,))
    row = cur.fetchone()
    return str(row[0]) if row else None


def app_kv_set(conn, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_kv(key, value) VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, value),
    )
    conn.commit()


def maybe_daily_intraday_backfill(
    conn,
    *,
    symbols: list[str],
    interval: str,
    history_days: int,
    force: bool = False,
) -> bool:
    """If Israel calendar date changed since last run (or `force`), download missing intraday bars.

    Returns True when a yfinance fetch was attempted (even if zero new rows).
    """
    today_il = datetime.now(IL_TZ).date().isoformat()
    last = app_kv_get(conn, KEY_BACKFILL_IL_DATE)
    if not force and last == today_il:
        logger.debug("Intraday backfill skipped (already ran today IL=%s).", today_il)
        return False

    logger.info("Intraday backfill: IL calendar day=%s symbols=%s interval=%s", today_il, len(symbols), interval)
    end = datetime.now(timezone.utc)
    start_floor = end - timedelta(days=max(1, int(history_days)))

    inserted_total = 0
    for sym in symbols:
        try:
            inserted_total += _backfill_symbol_range(conn, symbol=sym, interval=interval, start_floor=start_floor, end=end)
        except Exception as e:
            logger.warning("Backfill failed for %s: %s", sym, e)

    app_kv_set(conn, KEY_BACKFILL_IL_DATE, today_il)
    logger.info("Intraday backfill finished (approx new rows=%s).", inserted_total)
    return True


def _backfill_symbol_range(
    conn,
    *,
    symbol: str,
    interval: str,
    start_floor: datetime,
    end: datetime,
) -> int:
    cur = conn.execute(
        "SELECT MAX(bar_start) FROM price_bars WHERE symbol=? AND interval=?",
        (symbol, interval),
    )
    row = cur.fetchone()
    last_iso = row[0] if row and row[0] else None

    if last_iso:
        last_dt = datetime.fromisoformat(str(last_iso).replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        fetch_start = max(start_floor, last_dt - timedelta(hours=2))
    else:
        fetch_start = start_floor

    if fetch_start >= end - timedelta(minutes=1):
        return 0

    t = yf.Ticker(symbol)
    hist = t.history(
        start=fetch_start.astimezone(timezone.utc),
        end=end.astimezone(timezone.utc),
        interval=interval,
        auto_adjust=False,
        prepost=False,
    )
    if hist is None or hist.empty:
        return 0

    rows = 0
    for idx, r in hist.iterrows():
        ts = pd.Timestamp(idx)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        bar_start = ts.to_pydatetime().astimezone(timezone.utc).replace(microsecond=0).isoformat()
        conn.execute(
            """
            INSERT OR REPLACE INTO price_bars(symbol, bar_start, interval, open, high, low, close, volume)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                symbol,
                bar_start,
                interval,
                float(r["Open"]),
                float(r["High"]),
                float(r["Low"]),
                float(r["Close"]),
                float(r["Volume"]) if r["Volume"] == r["Volume"] else None,
            ),
        )
        rows += 1
    conn.commit()
    return rows


def price_close_at_or_before(conn, *, symbol: str, interval: str, as_of: datetime) -> float | None:
    """Return close of latest bar with `bar_start <= as_of` (both UTC-aware ISO comparable)."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    as_iso = as_of.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    cur = conn.execute(
        """
        SELECT close FROM price_bars
        WHERE symbol=? AND interval=? AND bar_start <= ?
        ORDER BY bar_start DESC
        LIMIT 1
        """,
        (symbol, interval, as_iso),
    )
    row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return float(row[0])


def quotes_from_bars(
    conn,
    *,
    symbols: list[str],
    interval: str,
    as_of: datetime,
) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym in symbols:
        px = price_close_at_or_before(conn, symbol=sym, interval=interval, as_of=as_of)
        if px is not None and px > 0:
            out[sym] = px
    return out
