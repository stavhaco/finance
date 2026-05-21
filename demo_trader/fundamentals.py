from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        v = float(x)
        if v != v:  # NaN
            return None
        return v
    except (TypeError, ValueError):
        return None


def _return_over_bars(close_series, bars: int) -> float | None:
    try:
        s = close_series.dropna()
        if s is None or len(s) < bars + 1:
            return None
        last = float(s.iloc[-1])
        prev = float(s.iloc[-1 - bars])
        if prev == 0:
            return None
        return (last / prev - 1.0) * 100.0
    except Exception:
        return None


def _ytd_return(close_series) -> float | None:
    try:
        s = close_series.dropna()
        if s is None or s.empty:
            return None
        last_ts = s.index[-1]
        year_start = datetime(last_ts.year, 1, 1, tzinfo=getattr(last_ts, "tzinfo", None))
        sub = s[s.index >= year_start]
        if sub.empty or len(sub) < 2:
            return None
        first = float(sub.iloc[0])
        last = float(sub.iloc[-1])
        if first == 0:
            return None
        return (last / first - 1.0) * 100.0
    except Exception:
        return None


def fetch_equity_fundamentals(symbol: str) -> dict[str, Any]:
    """Pull static + simple historical performance stats for one `.TA` symbol."""
    out: dict[str, Any] = {"symbol": symbol}
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        hist = t.history(period="400d", auto_adjust=True)
    except Exception as e:
        logger.warning("fundamentals: %s: %s", symbol, e)
        return out

    raw_cur = info.get("currency") or info.get("financialCurrency")
    cur = str(raw_cur) if raw_cur else None
    raw_px = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    from demo_trader.market_data import price_to_ils

    px_ils = price_to_ils(raw_px, cur) if raw_px is not None else None
    display_cur = "ILS" if cur in {"ILA", "ILS"} else cur

    out.update(
        {
            "currency": display_cur,
            "last_price": px_ils,
            "market_cap": _safe_float(info.get("marketCap")),
            "enterprise_value": _safe_float(info.get("enterpriseValue")),
            "trailing_pe": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "price_to_book": _safe_float(info.get("priceToBook")),
            "beta": _safe_float(info.get("beta")),
            "fifty_two_week_high": (
                price_to_ils(v, cur)
                if (v := _safe_float(info.get("fiftyTwoWeekHigh"))) is not None
                else None
            ),
            "fifty_two_week_low": (
                price_to_ils(v, cur)
                if (v := _safe_float(info.get("fiftyTwoWeekLow"))) is not None
                else None
            ),
            "avg_volume_10d": _safe_float(info.get("averageVolume10days")),
            "return_1y_pct": _return_over_bars(hist["Close"], 252) if hist is not None and not hist.empty else None,
            "return_1q_pct": _return_over_bars(hist["Close"], 63) if hist is not None and not hist.empty else None,
            "return_ytd_pct": _ytd_return(hist["Close"]) if hist is not None and not hist.empty else None,
        }
    )
    return out


def refresh_watchlist_fundamentals(conn, symbols: list[str], *, timeout_soft: bool = True) -> int:
    """Update `companies` table numeric columns for symbols (ignores failures per symbol)."""
    from demo_trader.db import update_company_fundamentals

    updated = 0
    for sym in symbols:
        try:
            stats = fetch_equity_fundamentals(sym)
            if not stats or stats.get("last_price") is None and stats.get("market_cap") is None:
                continue
            update_company_fundamentals(conn, stats)
            updated += 1
        except Exception as e:
            if not timeout_soft:
                raise
            logger.warning("fundamentals update failed for %s: %s", sym, e)
    return updated
