from __future__ import annotations

from dataclasses import dataclass

from demo_trader.state_store import PaperState, TradeRecord, append_trade, _utc_now_iso


@dataclass(frozen=True)
class Quote:
    symbol: str
    last: float
    currency: str | None


def apply_slippage(side: str, price: float, slippage_bps: float) -> float:
    adj = slippage_bps / 10_000.0
    if side.lower() == "buy":
        return price * (1.0 + adj)
    if side.lower() == "sell":
        return price * (1.0 - adj)
    raise ValueError("side must be buy or sell")


def portfolio_nav(state: PaperState, prices: dict[str, float]) -> float:
    nav = float(state.cash_ils)
    for sym, qty in state.positions.items():
        px = prices.get(sym)
        if px is None:
            continue
        nav += float(qty) * float(px)
    return nav


def max_buy_qty(state: PaperState, symbol: str, price: float, max_position_pct: float, nav: float) -> float:
    if price <= 0 or nav <= 0:
        return 0.0
    cap_value = nav * (max_position_pct / 100.0)
    current_qty = float(state.positions.get(symbol, 0.0))
    current_value = current_qty * price
    room = max(0.0, cap_value - current_value)
    return room / price


def execute_trade(
    state: PaperState,
    *,
    symbol: str,
    side: str,
    qty: float,
    quote: Quote,
    slippage_bps: float,
    max_position_pct: float,
    nav: float,
    reason: str,
) -> tuple[bool, str]:
    if qty <= 0:
        return False, "qty must be positive"
    side_l = side.lower()
    if side_l not in {"buy", "sell"}:
        return False, "invalid side"
    if quote.last <= 0:
        return False, "invalid price"

    px = apply_slippage(side_l, float(quote.last), slippage_bps)

    if side_l == "buy":
        max_q = max_buy_qty(state, symbol, px, max_position_pct, nav)
        if qty > max_q:
            qty = max_q
        if qty <= 0:
            return False, "position limit or zero room"
        notional = qty * px
        if notional > state.cash_ils + 1e-6:
            qty = state.cash_ils / px
            notional = qty * px
        if qty <= 0:
            return False, "insufficient cash"
        state.cash_ils -= notional
        state.positions[symbol] = float(state.positions.get(symbol, 0.0)) + qty
        append_trade(
            state,
            TradeRecord(
                ts=_utc_now_iso(),
                symbol=symbol,
                side=side_l,
                qty=float(qty),
                price=float(px),
                notional_ils=float(notional),
                reason=str(reason)[:500],
            ),
        )
        return True, "bought"

    held = float(state.positions.get(symbol, 0.0))
    if qty > held:
        qty = held
    if qty <= 0:
        return False, "nothing to sell"
    notional = qty * px
    state.cash_ils += notional
    new_qty = held - qty
    if new_qty <= 1e-12:
        state.positions.pop(symbol, None)
    else:
        state.positions[symbol] = new_qty
    append_trade(
        state,
        TradeRecord(
            ts=_utc_now_iso(),
            symbol=symbol,
            side=side_l,
            qty=float(qty),
            price=float(px),
            notional_ils=float(notional),
            reason=str(reason)[:500],
        ),
    )
    return True, "sold"
