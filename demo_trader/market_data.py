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


def _currency_for_ticker(t: yf.Ticker) -> str | None:
    try:
        cur = t.fast_info.get("currency")
        return str(cur) if cur else None
    except Exception:
        return None


def price_to_ils(last: float, currency: str | None) -> float:
    """Yahoo often quotes Israeli stocks in agorot (ILA); convert to shekels for NAV/trades."""
    px = float(last)
    if currency == "ILA":
        return px / 100.0
    return px


def _price_ils(last: float, currency: str | None) -> float:
    return price_to_ils(last, currency)


def _quote_from_last(sym: str, last: float, raw_cur: str | None) -> Quote:
    px_ils = _price_ils(float(last), raw_cur)
    display_cur = "ILS" if raw_cur in {"ILA", "ILS"} else (raw_cur or "ILS")
    return Quote(symbol=sym, last=px_ils, currency=display_cur)


def _fetch_one(sym: str) -> Quote | None:
    t = yf.Ticker(sym)
    last = _last_price(t)
    if last is None or last <= 0:
        return None
    return _quote_from_last(sym, float(last), _currency_for_ticker(t))


def _fetch_batch_yfinance(syms: list[str]) -> dict[str, Quote]:
    """Batch download via yfinance; falls back to per-symbol on failure."""
    out: dict[str, Quote] = {}
    if len(syms) < 2:
        return out
    try:
        frame = yf.download(
            syms,
            period="5d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
    except Exception:
        return out
    if frame is None or frame.empty:
        return out

    for sym in syms:
        try:
            if sym not in frame.columns.get_level_values(0):
                continue
            sub = frame[sym]
            if "Close" not in sub.columns:
                continue
            series = sub["Close"].dropna()
            if series.empty:
                continue
            last = float(series.iloc[-1])
            t = yf.Ticker(sym)
            out[sym] = _quote_from_last(sym, last, _currency_for_ticker(t))
        except Exception:
            continue
    return out


def fetch_last_prices(symbols: Iterable[str]) -> dict[str, Quote]:
    syms = list(dict.fromkeys(symbols))
    out: dict[str, Quote] = {}
    if not syms:
        return out

    if len(syms) >= 2:
        out.update(_fetch_batch_yfinance(syms))

    missing = [s for s in syms if s not in out]
    for sym in missing:
        q = _fetch_one(sym)
        if q is not None:
            out[sym] = q
    return out


def prices_map(quotes: dict[str, Quote]) -> dict[str, float]:
    return {s: q.last for s, q in quotes.items()}
