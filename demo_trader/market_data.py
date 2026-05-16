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
        if cur == "ILA":
            cur = "ILS"
        out[sym] = Quote(symbol=sym, last=float(last), currency=str(cur) if cur else None)
    return out


def prices_map(quotes: dict[str, Quote]) -> dict[str, float]:
    return {s: q.last for s, q in quotes.items()}
