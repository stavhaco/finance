from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from demo_trader.benchmark import compute_performance, ensure_session
from demo_trader.config import Config
from demo_trader.db import (
    companies_fundamentals_digest,
    finalize_open_trade_outcomes,
    insert_cycle,
    insert_decision,
    open_db,
    recent_knowledge_for_prompt,
    upsert_companies,
)
from demo_trader.fundamentals import refresh_watchlist_fundamentals
from demo_trader.knowledge_ingest import ingest_headlines, ingest_maya_rows
from demo_trader.market_data import fetch_last_prices, prices_map
from demo_trader.maya_client import maya_digest_for_prompt, normalize_maya_items
from demo_trader.news_feeds import fetch_headlines, headlines_digest, mock_headlines
from demo_trader.ollama_client import build_hebrew_trader_prompt, chat_json
from demo_trader.paper_broker import Quote, execute_trade, portfolio_nav
from demo_trader.state_store import _utc_now_iso, load_state, save_state
from demo_trader.ta35_catalog import TA35_COMPANIES, knowledge_catalog_digest
from demo_trader.tase_calendar import is_tase_regular_trading_hours


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
    conn = open_db(cfg.db_path)
    upsert_companies(
        conn,
        ((c.symbol, c.name_he, c.name_en, c.sector_he, c.category_he) for c in TA35_COMPANIES),
    )
    refresh_watchlist_fundamentals(conn, list(cfg.watchlist))

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

    finalize_open_trade_outcomes(conn, prices=prices, benchmark_px=float(bench_q.last))

    headlines = fetch_headlines(cfg.rss_feeds(), cfg.news_max_headlines)
    if not headlines:
        headlines = mock_headlines()
    inserted = ingest_headlines(conn, headlines)

    maya_rows = normalize_maya_items(
        lookback_days=cfg.maya_lookback_days,
        breaking_limit=cfg.maya_breaking_limit,
        post_max_keep=cfg.maya_post_max_keep,
        timeout_sec=cfg.maya_http_timeout_sec,
    )
    maya_inserted = ingest_maya_rows(conn, maya_rows)
    maya_digest = maya_digest_for_prompt(maya_rows, max_lines=40)

    trading_allowed = is_tase_regular_trading_hours()
    news_block = headlines_digest(headlines, max_lines=35)

    ensure_session(state, benchmark_symbol=cfg.benchmark_symbol, benchmark_px=float(bench_q.last), prices=prices)

    perf_pre = compute_performance(state, prices=prices, benchmark_last=float(bench_q.last))
    nav_pre = portfolio_nav(state, prices)

    knowledge_digest = recent_knowledge_for_prompt(conn, limit=cfg.knowledge_prompt_rows)
    catalog_digest = knowledge_catalog_digest()
    fundamentals_digest = companies_fundamentals_digest(conn, cfg.watchlist)

    print("--- cycle ---")
    print(
        f"tase_trading_allowed={trading_allowed} | rss_headlines={len(headlines)} | "
        f"rss_db_new≈{inserted} | maya_rows={len(maya_rows)} maya_db_new≈{maya_inserted}"
    )
    print(_fmt_perf(perf_pre))

    system, user = build_hebrew_trader_prompt(
        watchlist=cfg.watchlist,
        trading_allowed=trading_allowed,
        catalog_digest=catalog_digest,
        knowledge_digest=knowledge_digest,
        fundamentals_digest=fundamentals_digest,
        maya_digest=maya_digest,
        quotes_text=_quotes_text(quotes),
        portfolio_text=_portfolio_text(state, prices),
        news_text=news_block,
        max_trades=cfg.max_trades_per_cycle,
    )

    pending: list[dict[str, Any]] = []

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
        cycle_id = insert_cycle(
            conn,
            trading_allowed=trading_allowed,
            knowledge_only=True,
            nav_ils=nav_pre,
            benchmark_symbol=cfg.benchmark_symbol,
            benchmark_px=float(bench_q.last),
            portfolio_return_pct=perf_pre.portfolio_return_pct,
            benchmark_return_pct=perf_pre.benchmark_return_pct,
            alpha_pct=perf_pre.alpha_vs_benchmark_pct,
            headline_count=len(headlines),
        )
        insert_decision(
            conn,
            cycle_id=cycle_id,
            trading_allowed=trading_allowed,
            kind="ollama_error",
            symbol=None,
            side=None,
            qty=None,
            executed=False,
            exec_price=None,
            notional_ils=None,
            reason_he=str(e)[:500],
            analysis_he="",
            model_json=None,
            nav_before=nav_pre,
            nav_after=nav_pre,
            benchmark_px=float(bench_q.last),
            portfolio_return_pct=perf_pre.portfolio_return_pct,
            benchmark_return_pct=perf_pre.benchmark_return_pct,
            alpha_pct=perf_pre.alpha_vs_benchmark_pct,
            broker_message=None,
        )
        state.last_cycle_ts = _utc_now_iso()
        save_state(path, state)
        return 3

    analysis_he = str(decision.get("analysis_he", "")).strip()

    pending.append(
        {
            "trading_allowed": trading_allowed,
            "kind": "llm_summary",
            "symbol": None,
            "side": None,
            "qty": None,
            "executed": False,
            "exec_price": None,
            "notional_ils": None,
            "reason_he": "סיכום מודל לפני ביצוע עסקאות",
            "analysis_he": analysis_he,
            "model_json": decision,
            "nav_before": nav_pre,
            "nav_after": nav_pre,
            "benchmark_px": float(bench_q.last),
            "portfolio_return_pct": perf_pre.portfolio_return_pct,
            "benchmark_return_pct": perf_pre.benchmark_return_pct,
            "alpha_pct": perf_pre.alpha_vs_benchmark_pct,
            "broker_message": None,
        }
    )

    trades = decision.get("trades") or []
    if not isinstance(trades, list):
        trades = []

    executed = 0
    nav_running = nav_pre

    for raw in trades[: cfg.max_trades_per_cycle]:
        if not isinstance(raw, dict):
            continue
        sym = str(raw.get("symbol", "")).strip()
        side = str(raw.get("side", "")).strip().lower()
        reason_he = str(raw.get("reason_he", raw.get("reason", ""))).strip() or "מודל"
        try:
            qty = float(raw.get("qty", 0.0))
        except (TypeError, ValueError):
            qty = 0.0

        if sym not in cfg.watchlist:
            pending.append(
                {
                    "trading_allowed": trading_allowed,
                    "kind": "skip",
                    "symbol": sym or None,
                    "side": side or None,
                    "qty": qty,
                    "executed": False,
                    "exec_price": None,
                    "notional_ils": None,
                    "reason_he": "סימבול לא ברשימת TA-35 המוגדרת",
                    "analysis_he": analysis_he,
                    "model_json": {"raw": raw},
                    "nav_before": nav_running,
                    "nav_after": nav_running,
                    "benchmark_px": float(bench_q.last),
                    "portfolio_return_pct": perf_pre.portfolio_return_pct,
                    "benchmark_return_pct": perf_pre.benchmark_return_pct,
                    "alpha_pct": perf_pre.alpha_vs_benchmark_pct,
                    "broker_message": "not_in_watchlist",
                }
            )
            print(f"skip trade: symbol not in watchlist: {sym}")
            continue

        q = quotes.get(sym)
        if q is None:
            pending.append(
                {
                    "trading_allowed": trading_allowed,
                    "kind": "skip",
                    "symbol": sym,
                    "side": side,
                    "qty": qty,
                    "executed": False,
                    "exec_price": None,
                    "notional_ils": None,
                    "reason_he": reason_he,
                    "analysis_he": analysis_he,
                    "model_json": {"raw": raw},
                    "nav_before": nav_running,
                    "nav_after": nav_running,
                    "benchmark_px": float(bench_q.last),
                    "portfolio_return_pct": perf_pre.portfolio_return_pct,
                    "benchmark_return_pct": perf_pre.benchmark_return_pct,
                    "alpha_pct": perf_pre.alpha_vs_benchmark_pct,
                    "broker_message": "no_quote",
                }
            )
            print(f"skip trade: no quote for {sym}")
            continue

        if not trading_allowed:
            pending.append(
                {
                    "trading_allowed": trading_allowed,
                    "kind": "blocked_after_hours",
                    "symbol": sym,
                    "side": side,
                    "qty": qty,
                    "executed": False,
                    "exec_price": None,
                    "notional_ils": None,
                    "reason_he": reason_he,
                    "analysis_he": analysis_he,
                    "model_json": {"raw": raw},
                    "nav_before": nav_running,
                    "nav_after": nav_running,
                    "benchmark_px": float(bench_q.last),
                    "portfolio_return_pct": perf_pre.portfolio_return_pct,
                    "benchmark_return_pct": perf_pre.benchmark_return_pct,
                    "alpha_pct": perf_pre.alpha_vs_benchmark_pct,
                    "broker_message": "outside_tase_window",
                }
            )
            print(f"blocked trade (after hours): {sym} {side} qty={qty}")
            continue

        nav_before_trade = portfolio_nav(state, prices)
        ok, msg = execute_trade(
            state,
            symbol=sym,
            side=side,
            qty=qty,
            quote=q,
            slippage_bps=cfg.slippage_bps,
            max_position_pct=cfg.max_position_pct,
            nav=nav_before_trade,
            reason=reason_he,
        )
        nav_after_trade = portfolio_nav(state, prices)
        nav_running = nav_after_trade

        pending.append(
            {
                "trading_allowed": trading_allowed,
                "kind": "trade" if ok else "skip",
                "symbol": sym,
                "side": side,
                "qty": qty,
                "executed": bool(ok),
                "exec_price": float(q.last) if ok else None,
                "notional_ils": None,
                "reason_he": reason_he,
                "analysis_he": analysis_he,
                "model_json": {"raw": raw},
                "nav_before": nav_before_trade,
                "nav_after": nav_after_trade,
                "benchmark_px": float(bench_q.last),
                "portfolio_return_pct": perf_pre.portfolio_return_pct,
                "benchmark_return_pct": perf_pre.benchmark_return_pct,
                "alpha_pct": perf_pre.alpha_vs_benchmark_pct,
                "broker_message": msg,
            }
        )
        print(f"trade {sym} {side} qty={qty}: ok={ok} ({msg})")
        if ok:
            executed += 1

    syms_end = sorted(set(cfg.watchlist) | set(state.positions.keys()) | {cfg.benchmark_symbol})
    quotes_end = fetch_last_prices(syms_end)
    prices_end = prices_map(quotes_end)
    bench_end = quotes_end.get(cfg.benchmark_symbol) or bench_q
    perf_post = compute_performance(state, prices=prices_end, benchmark_last=float(bench_end.last))

    knowledge_only = executed == 0
    cycle_id = insert_cycle(
        conn,
        trading_allowed=trading_allowed,
        knowledge_only=knowledge_only,
        nav_ils=float(perf_post.nav_ils),
        benchmark_symbol=cfg.benchmark_symbol,
        benchmark_px=float(bench_end.last),
        portfolio_return_pct=perf_post.portfolio_return_pct,
        benchmark_return_pct=perf_post.benchmark_return_pct,
        alpha_pct=perf_post.alpha_vs_benchmark_pct,
        headline_count=len(headlines),
    )

    for row in pending:
        insert_decision(
            conn,
            cycle_id=cycle_id,
            trading_allowed=row["trading_allowed"],
            kind=str(row["kind"]),
            symbol=row.get("symbol"),
            side=row.get("side"),
            qty=row.get("qty"),
            executed=bool(row["executed"]),
            exec_price=row.get("exec_price"),
            notional_ils=row.get("notional_ils"),
            reason_he=str(row.get("reason_he") or ""),
            analysis_he=str(row.get("analysis_he") or ""),
            model_json=row.get("model_json"),
            nav_before=row.get("nav_before"),
            nav_after=row.get("nav_after"),
            benchmark_px=row.get("benchmark_px"),
            portfolio_return_pct=row.get("portfolio_return_pct"),
            benchmark_return_pct=row.get("benchmark_return_pct"),
            alpha_pct=row.get("alpha_pct"),
            broker_message=row.get("broker_message"),
        )

    if analysis_he:
        print("model analysis (he):")
        print(analysis_he)

    state.last_cycle_ts = _utc_now_iso()
    save_state(path, state)

    print(f"executed trades this cycle: {executed}")
    print("after trades:", _fmt_perf(perf_post))
    print(f"sqlite db: {cfg.db_path} (cycle_id={cycle_id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TA-35 paper trader with Hebrew context, SQLite audit log, and Ollama.")
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
        db_path=cfg0.db_path,
        slippage_bps=cfg0.slippage_bps,
        benchmark_symbol=cfg0.benchmark_symbol,
        watchlist=cfg0.watchlist,
        max_trades_per_cycle=cfg0.max_trades_per_cycle,
        max_position_pct=cfg0.max_position_pct,
        news_max_headlines=cfg0.news_max_headlines,
        ollama_timeout_sec=cfg0.ollama_timeout_sec,
        knowledge_prompt_rows=cfg0.knowledge_prompt_rows,
        maya_lookback_days=cfg0.maya_lookback_days,
        maya_breaking_limit=cfg0.maya_breaking_limit,
        maya_post_max_keep=cfg0.maya_post_max_keep,
        maya_http_timeout_sec=cfg0.maya_http_timeout_sec,
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
