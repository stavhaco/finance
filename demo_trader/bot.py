from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

from demo_trader.benchmark import compute_performance, ensure_session
from demo_trader.config import Config
from demo_trader.db import (
    companies_fundamentals_digest,
    trader_knowledge_digest_en,
    finalize_open_trade_outcomes,
    insert_cycle,
    insert_decision,
    open_db,
    recent_knowledge_for_prompt,
    upsert_companies,
)
from demo_trader.fundamentals import refresh_watchlist_fundamentals
from demo_trader.historic_bars import maybe_daily_intraday_backfill, quotes_from_bars
from demo_trader.knowledge_ingest import ingest_headlines, ingest_maya_rows
from demo_trader.market_data import fetch_last_prices, prices_map
from demo_trader.maya_client import maya_digest_for_prompt, normalize_maya_items
from demo_trader.news_feeds import fetch_headlines, headlines_digest, mock_headlines
from demo_trader.cycle_log import write_cycle_report
from demo_trader.dry_run import dry_run_decision
from demo_trader.ollama_client import build_hebrew_trader_prompt, chat_json
from demo_trader.ollama_health import format_ollama_help, ollama_reachable
from demo_trader.paper_broker import Quote, execute_trade, portfolio_nav
from demo_trader.sim_clock import advance_sim_now, load_sim_now
from demo_trader.state_store import _utc_now_iso, load_state, save_state
from demo_trader.ta35_catalog import TA35_COMPANIES, knowledge_catalog_digest
from demo_trader.tase_calendar import IL_TZ, is_tase_regular_trading_hours, next_tase_regular_session_open_utc
from demo_trader.time_utils import (
    maya_publish_to_utc_iso,
    parse_sim_start_iso,
    rss_published_to_utc_iso,
    sim_default_start_utc,
)


def _fmt_perf(p) -> str:
    if p.portfolio_return_pct is None:
        return f"NAV={p.nav_ils:,.2f} ILS (session not initialized)"
    return (
        f"NAV={p.nav_ils:,.2f} ILS | "
        f"portfolio {p.portfolio_return_pct:+.3f}% vs "
        f"benchmark {p.benchmark_return_pct:+.3f}% "
        f"(alpha {p.alpha_vs_benchmark_pct:+.3f} pts)"
    )


def _portfolio_text(state, prices: dict[str, float], cfg: Config) -> str:
    nav = portfolio_nav(state, prices)
    cash_pct = (float(state.cash_ils) / nav * 100.0) if nav > 0 else 100.0
    lines = [
        f"cash_ils: {state.cash_ils:,.2f}",
        f"nav_ils: {nav:,.2f}",
        f"cash_pct_of_nav: {cash_pct:.1f}%",
        f"deployment_target: keep cash below ~{cfg.max_cash_pct_target:.0f}% when trading is allowed",
    ]
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


def _quotes_from_price_map(px: dict[str, float]) -> dict[str, Quote]:
    return {s: Quote(symbol=s, last=float(p), currency="ILS") for s, p in px.items()}


def _event_utciso_le_sim(iso: str | None, sim_now: datetime) -> bool:
    if not iso:
        return False
    try:
        et = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return False
    if et.tzinfo is None:
        et = et.replace(tzinfo=timezone.utc)
    sim_u = sim_now.astimezone(timezone.utc).replace(microsecond=0)
    return et.astimezone(timezone.utc).replace(microsecond=0) <= sim_u


def _filter_maya_rows_for_sim(rows: list, sim_now: datetime) -> list:
    out: list = []
    for r in rows:
        iso = maya_publish_to_utc_iso(getattr(r, "publish_raw", None))
        if _event_utciso_le_sim(iso, sim_now):
            out.append(r)
    return out


def _filter_headlines_for_sim(headlines: list, sim_now: datetime) -> list:
    out: list = []
    for h in headlines:
        iso = rss_published_to_utc_iso(h.published)
        if _event_utciso_le_sim(iso, sim_now):
            out.append(h)
    return out




def _trade_audit_reason(raw: dict[str, Any]) -> str:
    """Audit text from English evidence fields (preferred) or legacy Hebrew reason_he."""
    why = str(raw.get("why_en") or "").strip()
    ids = raw.get("evidence_news_ids")
    quote = str(raw.get("evidence_quote") or "").strip()
    legacy = str(raw.get("reason_he") or raw.get("reason") or "").strip()
    parts: list[str] = []
    if why:
        parts.append(f"[why_en] {why}")
    if ids not in (None, [], ()):
        parts.append(f"[evidence_news_ids] {ids}")
    if quote:
        parts.append(f"[evidence_quote] {quote}")
    if parts:
        return "\n".join(parts)[:900]
    return legacy[:900] if legacy else "מודל"



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

    sim_now = None
    sim_ts_label: str | None = None

    if cfg.simulation:
        bar_syms = sorted(set(cfg.watchlist) | {cfg.benchmark_symbol})
        maybe_daily_intraday_backfill(
            conn,
            symbols=bar_syms,
            interval=cfg.price_bar_interval,
            history_days=cfg.price_history_days,
        )
        fallback_start = sim_default_start_utc(days_ago=cfg.sim_start_days_ago)
        default_start = parse_sim_start_iso(cfg.sim_start_iso, fallback_start=fallback_start)
        sim_now = load_sim_now(conn, default_start=default_start)
        if cfg.sim_skip_closed_hours and cfg.enforce_tase_hours:
            snapped = next_tase_regular_session_open_utc(sim_now)
            sim_u = sim_now.astimezone(timezone.utc).replace(microsecond=0)
            if snapped != sim_u:
                advance_sim_now(conn, new_now=snapped)
                sim_now = snapped
        sim_now = sim_now.astimezone(timezone.utc).replace(microsecond=0)
        sim_ts_label = sim_now.isoformat()
        px_map = quotes_from_bars(
            conn,
            symbols=sorted(symbols),
            interval=cfg.price_bar_interval,
            as_of=sim_now,
        )
        quotes = _quotes_from_price_map(px_map)
        prices = prices_map(quotes)
    else:
        quotes = fetch_last_prices(sorted(symbols))
        prices = prices_map(quotes)

    bench_q = quotes.get(cfg.benchmark_symbol)
    if bench_q is None or bench_q.last <= 0:
        print(f"ERROR: missing benchmark quote for {cfg.benchmark_symbol}", file=sys.stderr)
        return 2

    finalize_open_trade_outcomes(
        conn,
        prices=prices,
        benchmark_px=float(bench_q.last),
        outcome_ts_utc_iso=sim_ts_label if cfg.simulation else None,
    )

    if cfg.simulation and not cfg.sim_ingest_live:
        headlines = []
        inserted = 0
        maya_rows = []
        maya_inserted = 0
    else:
        headlines = fetch_headlines(cfg.rss_feeds(), cfg.news_max_headlines)
        if not headlines:
            headlines = mock_headlines()
        inserted = ingest_headlines(conn, headlines, cfg=cfg)

        if cfg.maya_enabled:
            maya_rows = normalize_maya_items(
                lookback_days=cfg.maya_lookback_days,
                breaking_limit=cfg.maya_breaking_limit,
                post_max_keep=cfg.maya_post_max_keep,
                connect_timeout_sec=cfg.maya_http_connect_timeout_sec,
                read_timeout_sec=cfg.maya_http_read_timeout_sec,
            )
            maya_inserted = ingest_maya_rows(conn, maya_rows, cfg=cfg)
        else:
            maya_rows = []
            maya_inserted = 0

    if cfg.simulation and not cfg.sim_ingest_live:
        maya_digest = (
            "(סימולציה: ללא מאיה/RSS חיה; משתמשים בידע שכבר נשמר במסד הנתונים עד זמן הסימולציה)"
        )
        news_block = maya_digest
    elif cfg.simulation and sim_now is not None:
        maya_digest = maya_digest_for_prompt(_filter_maya_rows_for_sim(maya_rows, sim_now), max_lines=40)
        news_block = headlines_digest(_filter_headlines_for_sim(headlines, sim_now), max_lines=35)
    else:
        maya_digest = maya_digest_for_prompt(maya_rows, max_lines=40)
        news_block = headlines_digest(headlines, max_lines=35)

    ref_for_tase = sim_now if cfg.simulation else None
    if cfg.enforce_tase_hours:
        trading_allowed = is_tase_regular_trading_hours(ref_for_tase)
    else:
        trading_allowed = True

    ensure_session(state, benchmark_symbol=cfg.benchmark_symbol, benchmark_px=float(bench_q.last), prices=prices)

    perf_pre = compute_performance(state, prices=prices, benchmark_last=float(bench_q.last))
    nav_pre = portfolio_nav(state, prices)

    knowledge_digest = recent_knowledge_for_prompt(
        conn,
        limit=cfg.knowledge_prompt_rows,
        as_of_utc=sim_now if cfg.simulation else None,
        benchmark_symbol=cfg.benchmark_symbol,
    )
    catalog_digest = knowledge_catalog_digest()
    fundamentals_digest = companies_fundamentals_digest(conn, cfg.watchlist)

    print("--- cycle ---")
    if cfg.simulation and sim_now is not None:
        print(
            f"SIMULATION sim_now_utc={sim_now.isoformat()} | step={cfg.sim_step_minutes}m | "
            f"bars={cfg.price_bar_interval} | ingest_live={cfg.sim_ingest_live} | "
            f"skip_closed={cfg.sim_skip_closed_hours}"
        )
    ref_wall = sim_now if cfg.simulation and sim_now is not None else datetime.now(timezone.utc)
    il_now = ref_wall.astimezone(IL_TZ).strftime("%Y-%m-%d %H:%M %Z")
    print(
        f"il_local={il_now} | tase_trading_allowed={trading_allowed} "
        f"(enforce_hours={cfg.enforce_tase_hours}) | "
        f"rss_headlines={len(headlines)} | rss_db_new≈{inserted} | "
        f"maya_enabled={cfg.maya_enabled} maya_rows={len(maya_rows)} maya_db_new≈{maya_inserted}"
    )
    if not trading_allowed and cfg.enforce_tase_hours:
        nxt = next_tase_regular_session_open_utc(ref_wall)
        print(f"next_tase_open_utc={nxt.isoformat()} (trades execute only inside Sun–Thu 09:00–17:35 IL)")
    print(_fmt_perf(perf_pre))

    article_context_en = trader_knowledge_digest_en(
        conn,
        benchmark_symbol=cfg.benchmark_symbol,
        limit=cfg.knowledge_trader_digest_limit,
        as_of_utc=sim_now if cfg.simulation else None,
        translation_snippet_chars=cfg.knowledge_trader_digest_excerpt_chars,
    )
    if article_context_en and not article_context_en.startswith("(No enriched"):
        print(f"knowledge_digest_en: {len(article_context_en)} chars", flush=True)

    portfolio_text = _portfolio_text(state, prices, cfg)

    system, user = build_hebrew_trader_prompt(
        watchlist=cfg.watchlist,
        trading_allowed=trading_allowed,
        catalog_digest=catalog_digest,
        knowledge_digest=knowledge_digest,
        fundamentals_digest=fundamentals_digest,
        maya_digest=maya_digest,
        quotes_text=_quotes_text(quotes),
        portfolio_text=portfolio_text,
        news_text=news_block,
        article_context_en=article_context_en,
        max_trades=cfg.max_trades_per_cycle,
        max_cash_pct_target=cfg.max_cash_pct_target,
        min_buys_when_trading=cfg.min_buys_when_trading,
    )

    pending: list[dict[str, Any]] = []
    audit_ts = sim_ts_label if cfg.simulation and sim_ts_label else None

    cycle_log_holder: dict[str, Any] = {
        "system": system,
        "user": user,
        "portfolio_text": portfolio_text,
        "decision": None,
        "error": None,
    }

    try:
        if cfg.dry_run:
            print("DRY_RUN: skipping Ollama; using deterministic stub decision.", flush=True)
            decision = dry_run_decision(
                watchlist=cfg.watchlist,
                trading_allowed=trading_allowed,
                max_trades=cfg.max_trades_per_cycle,
                min_buys_when_trading=cfg.min_buys_when_trading,
            )
        else:
            ok, detail = ollama_reachable(cfg.ollama_base_url)
            if not ok:
                raise ConnectionError(f"{detail}\n{format_ollama_help(cfg.ollama_base_url, cfg.ollama_model)}")
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
            ts_utc_iso=audit_ts,
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
            ts_utc_iso=audit_ts,
        )
        state.last_cycle_ts = audit_ts or _utc_now_iso()
        save_state(path, state)
        cycle_log_holder["error"] = str(e)[:2000]
        if cfg.cycle_log_enabled:
            ts_log = audit_ts or _utc_now_iso()
            report = {
                "cycle_id": cycle_id,
                "ts_utc": ts_log,
                "mode": "simulation" if cfg.simulation else "live",
                "model_error": cycle_log_holder["error"],
                "prompt": {"sections": {"system": system, "user": user}},
                "performance_before": {"nav_ils": perf_pre.nav_ils},
            }
            log_path = write_cycle_report(
                log_dir=cfg.cycle_log_dir,
                cycle_id=cycle_id,
                ts_utc_iso=ts_log,
                payload=report,
                include_full_prompts=cfg.cycle_log_full_prompts,
            )
            print(f"cycle log: {log_path}", flush=True)
        return 3

    analysis_he = str(decision.get("analysis_he", "")).strip()
    cycle_log_holder["decision"] = decision

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
        reason_he = _trade_audit_reason(raw)
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
    if cfg.simulation and sim_now is not None:
        sim_after = sim_now + timedelta(minutes=max(1, int(cfg.sim_step_minutes)))
        sim_after = sim_after.astimezone(timezone.utc).replace(microsecond=0)
        if cfg.sim_skip_closed_hours and cfg.enforce_tase_hours:
            sim_after = next_tase_regular_session_open_utc(sim_after)
        advance_sim_now(conn, new_now=sim_after)
        px_end = quotes_from_bars(
            conn,
            symbols=syms_end,
            interval=cfg.price_bar_interval,
            as_of=sim_after,
        )
        quotes_end = _quotes_from_price_map(px_end)
        prices_end = prices_map(quotes_end)
        print(f"sim clock advanced to {sim_after.isoformat()} (UTC)", flush=True)
    else:
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
        ts_utc_iso=audit_ts,
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
            ts_utc_iso=audit_ts,
        )

    if cfg.cycle_log_enabled:
        ts_log = audit_ts or _utc_now_iso()
        executions = [
            {
                "kind": row.get("kind"),
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "qty": row.get("qty"),
                "executed": row.get("executed"),
                "broker_message": row.get("broker_message"),
                "reason_he": row.get("reason_he"),
                "analysis_he": row.get("analysis_he"),
            }
            for row in pending
        ]
        report = {
            "cycle_id": cycle_id,
            "ts_utc": ts_log,
            "mode": "simulation" if cfg.simulation else "live",
            "sim_now_utc": sim_now.isoformat() if sim_now is not None else None,
            "ollama_model": cfg.ollama_model,
            "trading_allowed": trading_allowed,
            "ingest": {
                "rss_headlines": len(headlines),
                "rss_db_new": inserted,
                "maya_rows": len(maya_rows),
                "maya_db_new": maya_inserted,
            },
            "performance_before": {
                "nav_ils": perf_pre.nav_ils,
                "portfolio_return_pct": perf_pre.portfolio_return_pct,
                "benchmark_return_pct": perf_pre.benchmark_return_pct,
                "alpha_pct": perf_pre.alpha_vs_benchmark_pct,
            },
            "performance_after": {
                "nav_ils": perf_post.nav_ils,
                "portfolio_return_pct": perf_post.portfolio_return_pct,
                "benchmark_return_pct": perf_post.benchmark_return_pct,
                "alpha_pct": perf_post.alpha_vs_benchmark_pct,
            },
            "portfolio_after": _portfolio_text(state, prices_end, cfg),
            "prompt": {
                "ollama_model": cfg.ollama_model,
                "trading_allowed": trading_allowed,
                "max_cash_pct_target": cfg.max_cash_pct_target,
                "min_buys_when_trading": cfg.min_buys_when_trading,
                "sections": {
                    "system": cycle_log_holder["system"],
                    "user": cycle_log_holder["user"],
                    "catalog": catalog_digest,
                    "knowledge_he": knowledge_digest,
                    "fundamentals": fundamentals_digest,
                    "maya_headlines": maya_digest,
                    "quotes": _quotes_text(quotes),
                    "portfolio": cycle_log_holder["portfolio_text"],
                    "news_headlines": news_block,
                    "knowledge_en": article_context_en,
                },
            },
            "model_response": cycle_log_holder.get("decision"),
            "model_error": cycle_log_holder.get("error"),
            "executions": executions,
            "executed_trade_count": executed,
        }
        log_path = write_cycle_report(
            log_dir=cfg.cycle_log_dir,
            cycle_id=cycle_id,
            ts_utc_iso=ts_log,
            payload=report,
            include_full_prompts=cfg.cycle_log_full_prompts,
        )
        print(f"cycle log: {log_path}", flush=True)

    if analysis_he:
        print("model analysis (he):")
        print(analysis_he)

    state.last_cycle_ts = audit_ts or _utc_now_iso()
    save_state(path, state)

    print(f"executed trades this cycle: {executed}")
    print("after trades:", _fmt_perf(perf_post))
    print(f"sqlite db: {cfg.db_path} (cycle_id={cycle_id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TA-35 paper trader with Hebrew context, SQLite audit log, and Ollama.")
    p.add_argument("--once", action="store_true", help="Run a single cycle then exit.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Ollama; use deterministic stub trades (CI / agent iteration).",
    )
    p.add_argument("--interval-minutes", type=int, default=None, help="Override DEMO_TRADER_INTERVAL_MINUTES.")
    p.add_argument("--model", type=str, default=None, help="Override OLLAMA_MODEL.")
    args = p.parse_args(argv)

    cfg0 = Config()
    cfg = replace(
        cfg0,
        ollama_model=args.model or cfg0.ollama_model,
        interval_minutes=args.interval_minutes or cfg0.interval_minutes,
        dry_run=args.dry_run or cfg0.dry_run,
    )

    if args.once:
        return run_cycle(cfg)

    print(
        "NOTE: built-in loop mode. For a Mac Mini, prefer `python -m demo_trader --once` "
        "via scripts/mac/run_cycle.sh + launchd (see README).",
        flush=True,
    )
    while True:
        rc = run_cycle(cfg)
        if rc != 0:
            print(
                f"WARN: cycle exited with code {rc}; "
                + (
                    "exiting (DEMO_TRADER_LOOP_EXIT_ON_NONZERO=1)."
                    if cfg.loop_exit_on_nonzero
                    else "waiting for next interval then retrying."
                ),
                flush=True,
            )
            if cfg.loop_exit_on_nonzero:
                return rc
        sleep_s = max(60, int(cfg.interval_minutes) * 60)
        print(f"sleeping {sleep_s}s until next cycle...", flush=True)
        time.sleep(sleep_s)


if __name__ == "__main__":
    raise SystemExit(main())
