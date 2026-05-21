from __future__ import annotations

from typing import Iterable

import yfinance as yf

from demo_trader.paper_broker import Quote


def _last_price(t: yf.Ticker) -> float | None:
    try:
        fast = t.fast_info
        last = fast.get("last_price") or fast.get("regular_market_price")
        if last is not None:
            return float(last)
    except Exception:
        pass
    try:
        hist = t.history(period="5d", auto_adjust=False)
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        return None
    return None


def _price_ils(last: float, currency: str | None) -> float:
    """Yahoo often quotes Israeli stocks in agorot (ILA); convert to shekels for NAV/trades."""
    px = float(last)
    if currency == "ILA":
        return px / 100.0
    return px


def fetch_last_prices(symbols: Iterable[str]) -> dict[str, Quote]:
    syms = list(dict.fromkeys(symbols))
    out: dict[str, Quote] = {}
    for sym in syms:
        t = yf.Ticker(sym)
        last = _last_price(t)
        if last is None or last <= 0:
            continue
        cur = None
        try:
            cur = t.fast_info.get("currency")
        except Exception:
            cur = None
        raw_cur = str(cur) if cur else None
        px_ils = _price_ils(float(last), raw_cur)
        display_cur = "ILS" if raw_cur in {"ILA", "ILS"} else (raw_cur or "ILS")
        out[sym] = Quote(symbol=sym, last=px_ils, currency=display_cur)
    return out


def prices_map(quotes: dict[str, Quote]) -> dict[str, float]:
    return {s: q.last for s, q in quotes.items()}
