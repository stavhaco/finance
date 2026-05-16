from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from demo_trader.benchmark import compute_performance
from demo_trader.config import Config
from demo_trader.db import open_db
from demo_trader.holdings_pnl import HoldingPnL, TradeAction, compute_holdings_pnl, il_today, trades_on_il_date
from demo_trader.state_store import PaperState, load_state, save_state
from demo_trader.tase_calendar import IL_TZ
from demo_trader.telegram_notify import send_message


def _fmt_ils(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"₪{v:,.2f}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.2f}%"


def _fmt_pnl(v: float | None) -> str:
    if v is None:
        return "n/a"
    sign = "+" if v >= 0 else ""
    return f"{sign}₪{v:,.2f}"


def _holding_line(h: HoldingPnL) -> str:
    if h.qty <= 0:
        return f"• {h.symbol}: flat | realized {_fmt_pnl(h.realized_pnl_ils)}"
    return (
        f"• {h.symbol}: qty={h.qty:g} MV={_fmt_ils(h.market_value_ils)} "
        f"cost={_fmt_ils(h.cost_basis_ils)} "
        f"uPnL={_fmt_pnl(h.unrealized_pnl_ils)} ({_fmt_pct(h.unrealized_pnl_pct)}) "
        f"| realized {_fmt_pnl(h.realized_pnl_ils)}"
    )


def _action_line(a: TradeAction) -> str:
    status = "EXEC" if a.executed else a.kind.upper()
    return (
        f"• [{status}] {a.side.upper()} {a.symbol} qty={a.qty:g} "
        f"@ {_fmt_ils(a.price)} notional={_fmt_ils(a.notional_ils)}\n"
        f"  why: {a.reason or '(no reason)'}"
    )


def decisions_for_il_date(conn: sqlite3.Connection, day: date) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT ts, kind, symbol, side, qty, executed, exec_price, reason_he, broker_message
        FROM decisions
        WHERE kind IN ('trade', 'blocked_after_hours', 'skip')
        ORDER BY datetime(ts) ASC
        """
    )
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        ts = str(row["ts"])
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(IL_TZ).date()
        except ValueError:
            continue
        if d != day:
            continue
        out.append(dict(row))
    return out


def build_daily_report(
    *,
    state: PaperState,
    prices: dict[str, float],
    benchmark_last: float,
    benchmark_symbol: str,
    day: date | None = None,
    db_conn: sqlite3.Connection | None = None,
) -> str:
    report_day = day or il_today()
    perf = compute_performance(state, prices=prices, benchmark_last=benchmark_last)
    holdings = compute_holdings_pnl(state, prices=prices)
    executed = trades_on_il_date(state, report_day)

    pending: list[TradeAction] = []
    if db_conn is not None:
        for row in decisions_for_il_date(db_conn, report_day):
            if int(row.get("executed") or 0):
                continue
            kind = str(row.get("kind") or "")
            if kind not in {"blocked_after_hours", "skip"}:
                continue
            pending.append(
                TradeAction(
                    ts=str(row.get("ts") or ""),
                    symbol=str(row.get("symbol") or "?"),
                    side=str(row.get("side") or ""),
                    qty=float(row.get("qty") or 0.0),
                    price=float(row.get("exec_price") or 0.0),
                    notional_ils=0.0,
                    reason=str(row.get("reason_he") or row.get("broker_message") or ""),
                    executed=False,
                    kind=kind,
                )
            )

    lines: list[str] = [
        f"📊 TA-35 Paper Trader — daily summary ({report_day.isoformat()} IL)",
        "",
        f"NAV: {_fmt_ils(perf.nav_ils)}",
    ]
    if perf.portfolio_return_pct is not None:
        lines.append(
            f"Session: portfolio {_fmt_pct(perf.portfolio_return_pct)} | "
            f"benchmark {benchmark_symbol} {_fmt_pct(perf.benchmark_return_pct)} | "
            f"alpha {_fmt_pct(perf.alpha_vs_benchmark_pct)}"
        )
    lines.append(f"Cash: {_fmt_ils(state.cash_ils)}")
    lines.append("")

    lines.append(f"Actions today ({len(executed)} executed, {len(pending)} not executed):")
    if not executed and not pending:
        lines.append("• (no buy/sell activity)")
    else:
        for a in executed:
            lines.append(_action_line(a))
        for a in pending:
            lines.append(_action_line(a))
    lines.append("")

    open_holdings = [h for h in holdings if h.qty > 0]
    lines.append(f"Holdings P&L ({len(open_holdings)} open):")
    if not open_holdings:
        lines.append("• (no open positions)")
    else:
        total_upnl = 0.0
        total_realized = 0.0
        for h in open_holdings:
            lines.append(_holding_line(h))
            if h.unrealized_pnl_ils is not None:
                total_upnl += h.unrealized_pnl_ils
            total_realized += h.realized_pnl_ils
        lines.append("")
        lines.append(f"Totals: unrealized {_fmt_pnl(total_upnl)} | realized (session) {_fmt_pnl(total_realized)}")

    return "\n".join(lines)


def should_send_daily_report_il(
    *,
    last_report_il_date: str | None,
    now: datetime | None = None,
    after_hour: int = 17,
    after_minute: int = 36,
) -> bool:
    n = now or datetime.now(IL_TZ)
    if n.tzinfo is None:
        n = n.replace(tzinfo=IL_TZ)
    else:
        n = n.astimezone(IL_TZ)
    today = n.date().isoformat()
    if last_report_il_date == today:
        return False
    minutes = n.hour * 60 + n.minute
    return minutes >= after_hour * 60 + after_minute


def send_daily_report(cfg: Config, *, day: date | None = None, dry_run: bool = False) -> str:
    from demo_trader.market_data import fetch_last_prices, prices_map

    path = Path(cfg.state_path)
    state = load_state(path, cfg.starting_cash_ils)

    symbols = set(cfg.watchlist)
    symbols.add(cfg.benchmark_symbol)
    symbols.update(state.positions.keys())

    quotes = fetch_last_prices(sorted(symbols))
    prices = prices_map(quotes)
    bench = quotes.get(cfg.benchmark_symbol)
    if bench is None or bench.last <= 0:
        raise RuntimeError(f"missing benchmark quote for {cfg.benchmark_symbol}")

    conn = open_db(cfg.db_path)
    try:
        text = build_daily_report(
            state=state,
            prices=prices,
            benchmark_last=float(bench.last),
            benchmark_symbol=cfg.benchmark_symbol,
            day=day,
            db_conn=conn,
        )
    finally:
        conn.close()

    if dry_run:
        return text

    if not cfg.telegram_enabled:
        raise RuntimeError("telegram is disabled; set DEMO_TRADER_TELEGRAM_ENABLED=1")

    send_message(
        bot_token=cfg.telegram_bot_token,
        chat_id=cfg.telegram_chat_id,
        text=text,
        timeout_sec=cfg.telegram_timeout_sec,
    )
    return text


def maybe_send_scheduled_daily_report(cfg: Config, state: PaperState, path: Path) -> bool:
    """Send at most one daily report per IL calendar day after the configured time."""
    if not cfg.telegram_enabled:
        return False
    if not should_send_daily_report_il(
        last_report_il_date=state.last_daily_report_il_date,
        after_hour=cfg.telegram_daily_hour,
        after_minute=cfg.telegram_daily_minute,
    ):
        return False
    send_daily_report(cfg, day=il_today())
    state.last_daily_report_il_date = il_today().isoformat()
    save_state(path, state)
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Send TA-35 paper trader daily Telegram summary.")
    p.add_argument("--dry-run", action="store_true", help="Print report to stdout instead of Telegram.")
    p.add_argument("--date", type=str, default=None, help="IL calendar date YYYY-MM-DD (default: today).")
    args = p.parse_args(argv)

    cfg = Config()
    day = date.fromisoformat(args.date) if args.date else None
    text = send_daily_report(cfg, day=day, dry_run=args.dry_run)
    if args.dry_run:
        print(text)
    else:
        print("daily report sent to Telegram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
