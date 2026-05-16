from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from demo_trader.benchmark import compute_performance, ensure_session
from demo_trader.config import Config
from demo_trader.market_data import fetch_last_prices, prices_map
from demo_trader.news_feeds import fetch_headlines, headlines_digest, mock_headlines
from demo_trader.ollama_client import build_prompt, chat_json
from demo_trader.paper_broker import Quote, execute_trade, portfolio_nav
from demo_trader.state_store import _utc_now_iso, load_state, save_state


def _fmt_perf(p) -> str:
    if p.portfolio_return_pct is None:
        return f"NAV={p.nav_ils:,.2f} ILS (session not initialized)"
    return (
        f"NAV={p.nav_ils:,.2f} ILS | "
        f"portfolio {p.portfolio_return_pct:+.3f}% vs "
        f"benchmark {p.benchmark_return_pct:+.3f}% "
        f"(alpha {p.alpha_vs_benchmark_pct:+.3f} pts)"
    )


def _portfolio_text(state, prices: dict[str, float]) -> str:
    lines = [f"cash_ils: {state.cash_ils:,.2f}"]
    if not state.positions:
        lines.append("positions: (none)")
    else:
        lines.append("positions:")
        for sym, qty in sorted(state.positions.items()):
            px = prices.get(sym)
            mv = (qty * px) if px is not None else None
            if mv is None:
                lines.append(f"  - {sym}: qty={qty} (missing price)")
            else:
                lines.append(f"  - {sym}: qty={qty} mv_ils={mv:,.2f} last={px}")
    return "\n".join(lines)


def _quotes_text(quotes: dict[str, Quote]) -> str:
    lines = []
    for sym, q in sorted(quotes.items()):
        cur = q.currency or "?"
        lines.append(f"{sym}: last={q.last} {cur}")
    return "\n".join(lines) if lines else "(no quotes)"


def run_cycle(cfg: Config) -> int:
    path = Path(cfg.state_path)
    state = load_state(path, cfg.starting_cash_ils)

    symbols = set(cfg.watchlist)
    symbols.add(cfg.benchmark_symbol)
    symbols.update(state.positions.keys())

    quotes = fetch_last_prices(sorted(symbols))
    prices = prices_map(quotes)

    bench_q = quotes.get(cfg.benchmark_symbol)
    if bench_q is None or bench_q.last <= 0:
        print(f"ERROR: missing benchmark quote for {cfg.benchmark_symbol}", file=sys.stderr)
        return 2

    ensure_session(state, benchmark_symbol=cfg.benchmark_symbol, benchmark_px=float(bench_q.last), prices=prices)

    headlines = fetch_headlines(cfg.rss_feeds(), cfg.news_max_headlines)
    if not headlines:
        headlines = mock_headlines()
    news_block = headlines_digest(headlines, max_lines=30)

    perf = compute_performance(state, prices=prices, benchmark_last=float(bench_q.last))

    print("--- cycle ---")
    print(_fmt_perf(perf))
    print(f"headlines ingested: {len(headlines)}")

    system, user = build_prompt(
        watchlist=cfg.watchlist,
        quotes_text=_quotes_text(quotes),
        portfolio_text=_portfolio_text(state, prices),
        news_text=news_block,
        max_trades=cfg.max_trades_per_cycle,
    )

    try:
        decision = chat_json(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_model,
            system=system,
            user=user,
            timeout_sec=cfg.ollama_timeout_sec,
        )
    except Exception as e:
        print(f"ERROR: Ollama call failed: {e}", file=sys.stderr)
        traceback.print_exc()
        state.last_cycle_ts = _utc_now_iso()
        save_state(path, state)
        return 3

    analysis = str(decision.get("analysis", "")).strip()
    rel = str(decision.get("relative_value_notes", "")).strip()
    if analysis:
        print("model analysis:")
        print(analysis)
    if rel:
        print("relative value notes:")
        print(rel)

    trades = decision.get("trades") or []
    if not isinstance(trades, list):
        trades = []

    executed = 0
    for raw in trades[: cfg.max_trades_per_cycle]:
        if not isinstance(raw, dict):
            continue
        sym = str(raw.get("symbol", "")).strip()
        side = str(raw.get("side", "")).strip().lower()
        reason = str(raw.get("reason", "")).strip() or "model"
        try:
            qty = float(raw.get("qty", 0.0))
        except (TypeError, ValueError):
            qty = 0.0
        if sym not in cfg.watchlist:
            print(f"skip trade: symbol not in watchlist: {sym}")
            continue
        q = quotes.get(sym)
        if q is None:
            print(f"skip trade: no quote for {sym}")
            continue
        nav2 = portfolio_nav(state, prices)
        ok, msg = execute_trade(
            state,
            symbol=sym,
            side=side,
            qty=qty,
            quote=q,
            slippage_bps=cfg.slippage_bps,
            max_position_pct=cfg.max_position_pct,
            nav=nav2,
            reason=reason,
        )
        print(f"trade {sym} {side} qty={qty}: ok={ok} ({msg})")
        if ok:
            executed += 1

    syms_end = sorted(set(cfg.watchlist) | set(state.positions.keys()) | {cfg.benchmark_symbol})
    quotes_end = fetch_last_prices(syms_end)
    prices_end = prices_map(quotes_end)
    bench_end = quotes_end.get(cfg.benchmark_symbol) or bench_q
    perf2 = compute_performance(state, prices=prices_end, benchmark_last=float(bench_end.last))

    state.last_cycle_ts = _utc_now_iso()
    save_state(path, state)

    print(f"executed trades this cycle: {executed}")
    print("after trades:", _fmt_perf(perf2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Demo paper trader with Ollama + TA benchmark comparison.")
    p.add_argument("--once", action="store_true", help="Run a single cycle then exit.")
    p.add_argument("--interval-minutes", type=int, default=None, help="Override DEMO_TRADER_INTERVAL_MINUTES.")
    p.add_argument("--model", type=str, default=None, help="Override OLLAMA_MODEL.")
    args = p.parse_args(argv)

    cfg0 = Config()
    cfg = Config(
        ollama_base_url=cfg0.ollama_base_url,
        ollama_model=args.model or cfg0.ollama_model,
        interval_minutes=args.interval_minutes or cfg0.interval_minutes,
        starting_cash_ils=cfg0.starting_cash_ils,
        state_path=cfg0.state_path,
        slippage_bps=cfg0.slippage_bps,
        benchmark_symbol=cfg0.benchmark_symbol,
        watchlist=cfg0.watchlist,
        max_trades_per_cycle=cfg0.max_trades_per_cycle,
        max_position_pct=cfg0.max_position_pct,
        news_max_headlines=cfg0.news_max_headlines,
        ollama_timeout_sec=cfg0.ollama_timeout_sec,
    )

    if args.once:
        return run_cycle(cfg)

    while True:
        rc = run_cycle(cfg)
        if rc != 0:
            return rc
        sleep_s = max(60, int(cfg.interval_minutes) * 60)
        print(f"sleeping {sleep_s}s until next cycle...")
        time.sleep(sleep_s)


if __name__ == "__main__":
    raise SystemExit(main())
