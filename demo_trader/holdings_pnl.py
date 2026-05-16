from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from demo_trader.state_store import PaperState
from demo_trader.tase_calendar import IL_TZ


@dataclass(frozen=True)
class HoldingPnL:
    symbol: str
    qty: float
    last_px: float | None
    market_value_ils: float | None
    cost_basis_ils: float
    unrealized_pnl_ils: float | None
    unrealized_pnl_pct: float | None
    realized_pnl_ils: float


@dataclass(frozen=True)
class TradeAction:
    ts: str
    symbol: str
    side: str
    qty: float
    price: float
    notional_ils: float
    reason: str
    executed: bool
    kind: str


def _parse_ts(ts: str) -> datetime:
    raw = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(raw)


def il_date_from_ts(ts: str) -> date:
    return _parse_ts(ts).astimezone(IL_TZ).date()


def il_today() -> date:
    return datetime.now(IL_TZ).date()


def _trade_rows(state: PaperState) -> list[dict[str, Any]]:
    return sorted(state.trades, key=lambda t: str(t.get("ts", "")))


def compute_holdings_pnl(state: PaperState, *, prices: dict[str, float]) -> list[HoldingPnL]:
    """Average-cost accounting from trade history; open positions use state.positions."""
    cost_basis: dict[str, float] = {}
    qty_held: dict[str, float] = {}
    realized: dict[str, float] = {}

    for raw in _trade_rows(state):
        sym = str(raw.get("symbol", ""))
        side = str(raw.get("side", "")).lower()
        q = float(raw.get("qty", 0.0) or 0.0)
        notional = float(raw.get("notional_ils", 0.0) or 0.0)
        if not sym or q <= 0:
            continue
        if side == "buy":
            cost_basis[sym] = cost_basis.get(sym, 0.0) + notional
            qty_held[sym] = qty_held.get(sym, 0.0) + q
        elif side == "sell":
            held = qty_held.get(sym, 0.0)
            if held <= 0:
                continue
            avg = cost_basis.get(sym, 0.0) / held
            sell_q = min(q, held)
            sold_cost = avg * sell_q
            realized[sym] = realized.get(sym, 0.0) + (notional - sold_cost)
            cost_basis[sym] = cost_basis.get(sym, 0.0) - sold_cost
            qty_held[sym] = held - sell_q

    symbols = sorted(set(state.positions.keys()) | set(realized.keys()))
    out: list[HoldingPnL] = []
    for sym in symbols:
        qty = float(state.positions.get(sym, 0.0))
        px = prices.get(sym)
        cb = cost_basis.get(sym, 0.0) if qty > 0 else 0.0
        mv = (qty * px) if px is not None and qty > 0 else None
        upnl = (mv - cb) if mv is not None else None
        upnl_pct = (upnl / cb * 100.0) if upnl is not None and cb > 0 else None
        out.append(
            HoldingPnL(
                symbol=sym,
                qty=qty,
                last_px=px,
                market_value_ils=mv,
                cost_basis_ils=cb,
                unrealized_pnl_ils=upnl,
                unrealized_pnl_pct=upnl_pct,
                realized_pnl_ils=realized.get(sym, 0.0),
            )
        )
    return out


def trades_on_il_date(state: PaperState, day: date) -> list[TradeAction]:
    actions: list[TradeAction] = []
    for raw in _trade_rows(state):
        ts = str(raw.get("ts", ""))
        if not ts:
            continue
        if il_date_from_ts(ts) != day:
            continue
        actions.append(
            TradeAction(
                ts=ts,
                symbol=str(raw.get("symbol", "")),
                side=str(raw.get("side", "")),
                qty=float(raw.get("qty", 0.0) or 0.0),
                price=float(raw.get("price", 0.0) or 0.0),
                notional_ils=float(raw.get("notional_ils", 0.0) or 0.0),
                reason=str(raw.get("reason", "")),
                executed=True,
                kind="trade",
            )
        )
    return actions
