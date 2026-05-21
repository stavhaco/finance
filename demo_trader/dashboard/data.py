from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from demo_trader.benchmark import compute_performance
from demo_trader.config import Config
from demo_trader.db import connect_readonly
from demo_trader.market_data import fetch_last_prices, price_to_ils, prices_map
from demo_trader.state_store import load_state
from demo_trader.tase_calendar import is_tase_regular_trading_hours


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _in_range(ts: str | None, since: datetime | None, until: datetime | None) -> bool:
    dt = _parse_ts(ts)
    if dt is None:
        return since is None and until is None
    if since and dt < since:
        return False
    if until and dt > until:
        return False
    return True


def _cycle_log_path(log_dir: Path, cycle_id: int, ts: str | None) -> Path | None:
    if not log_dir.is_dir():
        return None
    safe = (ts or "").replace(":", "").replace("+", "Z")[:20]
    exact = log_dir / f"cycle_{cycle_id:05d}_{safe}.json"
    if exact.is_file():
        return exact
    matches = sorted(log_dir.glob(f"cycle_{cycle_id:05d}_*.json"), reverse=True)
    return matches[0] if matches else None


def load_portfolio(cfg: Config) -> dict[str, Any]:
    state_path = Path(cfg.state_path)
    state = load_state(state_path, cfg.starting_cash_ils)
    positions = []
    for sym, qty in sorted(state.positions.items()):
        positions.append(
            {"symbol": sym, "qty": float(qty), "last_price": None, "market_value_ils": 0.0}
        )
    cash = float(state.cash_ils)

    syms = [p["symbol"] for p in positions]
    bench_sym = (state.session.benchmark_symbol if state.session else None) or cfg.benchmark_symbol
    quote_syms = list(dict.fromkeys([*syms, bench_sym]))
    prices: dict[str, float] = {}
    try:
        quotes = fetch_last_prices(quote_syms)
        prices = prices_map(quotes)
    except Exception:
        prices = {}

    if not prices and syms:
        try:
            conn = connect_readonly(cfg.db_path)
            try:
                for p in positions:
                    cur = conn.execute(
                        "SELECT last_price, currency FROM companies WHERE symbol=?",
                        (p["symbol"],),
                    )
                    row = cur.fetchone()
                    if row and row["last_price"]:
                        px = price_to_ils(float(row["last_price"]), row["currency"])
                        if px > 500 and p["symbol"].endswith(".TA"):
                            px = px / 100.0
                        prices[p["symbol"]] = px
            finally:
                conn.close()
        except Exception:
            pass

    for p in positions:
        sym = p["symbol"]
        if sym in prices:
            p["last_price"] = prices[sym]
            p["market_value_ils"] = prices[sym] * p["qty"]

    mv_total = sum(p["market_value_ils"] for p in positions)
    nav = cash + mv_total
    cash_pct = (cash / nav * 100.0) if nav > 0 else 100.0

    bench_last = prices.get(bench_sym)
    perf = compute_performance(
        state,
        prices={s: prices.get(s, 0.0) for s in syms},
        benchmark_last=float(bench_last or (state.session.benchmark_start_px if state.session else 0) or 0),
    )

    session = state.session
    return {
        "cash_ils": cash,
        "nav_ils": nav,
        "cash_pct": round(cash_pct, 2),
        "portfolio_return_pct": perf.portfolio_return_pct,
        "benchmark_return_pct": perf.benchmark_return_pct,
        "alpha_pct": perf.alpha_vs_benchmark_pct,
        "positions": positions,
        "last_cycle_ts": state.last_cycle_ts,
        "session": {
            "started_ts": session.started_ts if session else None,
            "benchmark_symbol": bench_sym,
            "benchmark_start_px": session.benchmark_start_px if session else None,
            "initial_nav_ils": session.initial_nav_ils if session else cfg.starting_cash_ils,
        },
        "allocation": [
            {"label": "Cash", "value_ils": cash},
            *[{"label": p["symbol"], "value_ils": p["market_value_ils"]} for p in positions if p["market_value_ils"] > 0],
        ],
    }


def load_cycles(
    cfg: Config,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conn = connect_readonly(cfg.db_path)
    log_dir = Path(cfg.cycle_log_dir)
    try:
        cur = conn.execute(
            """
            SELECT id, ts, trading_allowed, knowledge_only, nav_ils, benchmark_symbol,
                   benchmark_px, portfolio_return_pct, benchmark_return_pct, alpha_pct, headline_count
            FROM cycles
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit) * 3,),
        )
        cycles_raw = cur.fetchall()
        out: list[dict[str, Any]] = []
        for c in cycles_raw:
            if not _in_range(c["ts"], since, until):
                continue
            cid = int(c["id"])
            dcur = conn.execute(
                """
                SELECT id, ts, kind, symbol, side, qty, executed, reason_he, analysis_he
                FROM decisions
                WHERE cycle_id=?
                ORDER BY id ASC
                """,
                (cid,),
            )
            decisions = [dict(r) for r in dcur.fetchall()]
            trades = []
            blocked = []
            summary_he = ""
            for d in decisions:
                kind = d.get("kind") or ""
                if kind == "llm_summary" and d.get("analysis_he"):
                    summary_he = str(d["analysis_he"])[:500]
                if kind == "trade" and d.get("executed"):
                    trades.append(d)
                elif kind in {"trade", "blocked_after_hours", "skip"}:
                    blocked.append(d)

            log_path = _cycle_log_path(log_dir, cid, c["ts"])
            model_note = ""
            if log_path and log_path.is_file():
                try:
                    payload = json.loads(log_path.read_text(encoding="utf-8"))
                    mr = payload.get("model_response") or {}
                    if isinstance(mr, dict):
                        model_note = str(mr.get("analysis_he") or "")[:400]
                    ingest = payload.get("ingest") or {}
                except Exception:
                    ingest = {}
            else:
                ingest = {}

            ref = _parse_ts(c["ts"])
            market_open = bool(c["trading_allowed"]) if ref is None else is_tase_regular_trading_hours(ref)

            actions = []
            for t in trades:
                actions.append(
                    {
                        "type": "trade",
                        "symbol": t.get("symbol"),
                        "side": t.get("side"),
                        "qty": t.get("qty"),
                        "executed": True,
                        "reason_he": (t.get("reason_he") or "")[:200],
                    }
                )
            for b in blocked[:8]:
                actions.append(
                    {
                        "type": "blocked" if b.get("kind") == "blocked_after_hours" else "skip",
                        "symbol": b.get("symbol"),
                        "side": b.get("side"),
                        "qty": b.get("qty"),
                        "executed": False,
                        "reason_he": (b.get("reason_he") or "")[:200],
                    }
                )
            if not actions and summary_he:
                actions.append({"type": "hold", "symbol": None, "reason_he": summary_he[:200]})

            out.append(
                {
                    "cycle_id": cid,
                    "ts": c["ts"],
                    "market_open": market_open,
                    "trading_allowed": bool(c["trading_allowed"]),
                    "nav_ils": c["nav_ils"],
                    "portfolio_return_pct": c["portfolio_return_pct"],
                    "benchmark_return_pct": c["benchmark_return_pct"],
                    "alpha_pct": c["alpha_pct"],
                    "benchmark_px": c["benchmark_px"],
                    "headline_count": c["headline_count"],
                    "executed_trades": len(trades),
                    "summary_he": summary_he or model_note,
                    "actions": actions,
                    "cycle_log": str(log_path) if log_path else None,
                }
            )
            if len(out) >= limit:
                break
        return out
    finally:
        conn.close()


def load_knowledge(
    cfg: Config,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    source_prefix: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    conn = connect_readonly(cfg.db_path)
    try:
        cur = conn.execute(
            """
            SELECT id, ts, event_time, source, url, title, matched_symbol,
                   title_en, executive_summary_en, body_translation_en,
                   sentiment, trade_usefulness, is_broad_market,
                   enrichment_status, snippet
            FROM knowledge_events
            ORDER BY datetime(COALESCE(event_time, ts)) DESC
            LIMIT ?
            """,
            (int(limit) * 2,),
        )
        rows = []
        for r in cur.fetchall():
            when = r["event_time"] or r["ts"]
            if not _in_range(when, since, until):
                continue
            src = r["source"] or ""
            if source_prefix and not src.startswith(source_prefix):
                continue
            is_maya = src.startswith("maya.")
            rows.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "event_time": r["event_time"],
                    "source": src,
                    "url": r["url"],
                    "title": r["title"],
                    "title_en": r["title_en"],
                    "matched_symbol": r["matched_symbol"],
                    "executive_summary_en": r["executive_summary_en"],
                    "body_translation_en": (r["body_translation_en"] or "")[:2000],
                    "sentiment": r["sentiment"],
                    "trade_usefulness": r["trade_usefulness"],
                    "is_broad_market": bool(r["is_broad_market"]),
                    "enrichment_status": r["enrichment_status"],
                    "is_maya_flash": is_maya and "breaking" in src,
                    "snippet": (r["snippet"] or "")[:500],
                }
            )
            if len(rows) >= limit:
                break
        return rows
    finally:
        conn.close()


def parse_range_query(since_s: str | None, until_s: str | None) -> tuple[datetime | None, datetime | None]:
    since = _parse_ts(since_s) if since_s else None
    until = _parse_ts(until_s) if until_s else None
    return since, until
