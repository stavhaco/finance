from __future__ import annotations

import json
import sqlite3
import re
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


def _company_map(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    cur = conn.execute(
        "SELECT symbol, COALESCE(name_he,'') AS name_he, COALESCE(name_en,'') AS name_en FROM companies"
    )
    return {
        str(r["symbol"]): {"name_he": str(r["name_he"] or ""), "name_en": str(r["name_en"] or "")}
        for r in cur.fetchall()
    }


def company_display_label(sym: str | None, cmap: dict[str, dict[str, str]]) -> str | None:
    """Hebrew-first company line with ticker suffix."""
    if not sym:
        return None
    row = cmap.get(sym)
    if not row:
        return sym
    he = row["name_he"].strip()
    en = row["name_en"].strip()
    if he and en and en.casefold() != he.casefold():
        return f"{he} ({en}) · {sym}"
    if he:
        return f"{he} · {sym}"
    if en:
        return f"{en} · {sym}"
    return sym


def _model_decision_hints(mr: Any) -> tuple[str, dict[str, str]]:
    if not isinstance(mr, dict):
        return "", {}
    ana = str(mr.get("analysis_he") or "").strip()
    by_sym: dict[str, str] = {}
    for row in mr.get("recommendations") or []:
        if not isinstance(row, dict):
            continue
        s = str(row.get("symbol") or "").strip()
        why = str(row.get("why_en") or "").strip()
        if s and why:
            by_sym[s] = why
    for row in mr.get("by_symbol") or []:
        if not isinstance(row, dict):
            continue
        s = str(row.get("symbol") or "").strip()
        rationale = str(row.get("rationale_he") or "").strip()
        if s and rationale and s not in by_sym:
            by_sym[s] = rationale
    return ana, by_sym


def merge_action_reason(
    reason_he: str,
    *,
    symbol: str | None,
    by_sym_hints: dict[str, str],
) -> str:
    chunks: list[str] = [(reason_he or "").strip()]
    if symbol and symbol in by_sym_hints:
        hint = by_sym_hints[symbol].strip()
        if hint and hint not in (reason_he or ""):
            chunks.append(f"היערכות והנמקה מהמודל לפי {symbol}: {hint}")
    return "\n\n".join(c for c in chunks if c)




_HE = "\u0590-\u05FF"
_SPACE_BETWEEN_HE = re.compile(rf"(?<=[{_HE}])\s+(?=[{_HE}])")


def _tighten_spaced_hebrew(text: str) -> str:
    """Remove stray spaces between Hebrew letters (LLM artifacts)."""
    s = text or ""
    prev = None
    while prev != s:
        prev = s
        s = _SPACE_BETWEEN_HE.sub("", s)
    return s.strip()


def _flatten_logged_prompt_section(section: Any) -> str:
    if section is None:
        return ""
    if isinstance(section, str):
        return section.strip()
    if isinstance(section, dict):
        full = section.get("full")
        if isinstance(full, str) and full.strip():
            return full.strip()
        preview = section.get("preview")
        if isinstance(preview, str) and preview.strip():
            return preview.strip()
    return str(section).strip()


def _english_digest_from_cycle_payload(payload: dict[str, Any]) -> str:
    prompt = payload.get("prompt") or {}
    sections = prompt.get("sections") or {}
    if not isinstance(prompt, dict) or not isinstance(sections, dict):
        return ""
    return _flatten_logged_prompt_section(sections.get("knowledge_en")).strip()[:8000]


def _avg_buy_ils_from_trades(trades: list[dict[str, Any]]) -> dict[str, float]:
    """Average cost per remaining share after replaying buys/sells in trade log order."""
    rows = sorted((t for t in trades if isinstance(t, dict)), key=lambda t: str(t.get("ts") or ""))
    qty: dict[str, float] = {}
    cost_basis: dict[str, float] = {}
    for t in rows:
        sym = str(t.get("symbol") or "").strip()
        if not sym:
            continue
        side = str(t.get("side") or "").lower()
        try:
            q = float(t.get("qty") or 0.0)
            px = float(t.get("price") or 0.0)
        except (TypeError, ValueError):
            continue
        if q <= 0 or px <= 0:
            continue
        prev_q = float(qty.get(sym, 0.0))
        prev_cb = float(cost_basis.get(sym, 0.0))
        if side == "buy":
            qty[sym] = prev_q + q
            cost_basis[sym] = prev_cb + q * px
        elif side == "sell":
            if prev_q <= 0:
                continue
            sold = min(q, prev_q)
            avg_px = prev_cb / prev_q
            qty[sym] = prev_q - sold
            cost_basis[sym] = prev_cb - sold * avg_px
            if qty[sym] <= 1e-12:
                qty.pop(sym, None)
                cost_basis.pop(sym, None)
    out: dict[str, float] = {}
    for sym, qv in qty.items():
        if qv <= 1e-12:
            continue
        cb = float(cost_basis.get(sym, 0.0))
        if cb > 0:
            out[sym] = cb / qv
    return out


def _round2_maybe(val: float | None) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return None


def _cycle_id_from_log_filename(name: str) -> int:
    if not name.startswith("cycle_") or not name.endswith(".json"):
        return 0
    rest = name[len("cycle_") : -len(".json")]
    sep = rest.find("_")
    if sep <= 0:
        return 0
    try:
        return int(rest[:sep])
    except ValueError:
        return 0


def _file_stat(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "bytes": 0, "modified": None}
    st = path.stat()
    return {
        "exists": True,
        "bytes": int(st.st_size),
        "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    }


TABLE_PURPOSES: dict[str, str] = {
    "companies": "TA-35 catalog and Yahoo fundamentals (updated each cycle).",
    "knowledge_events": "RSS/Maya ingest + optional English enrichment.",
    "cycles": "One row per loop: NAV, benchmark, ingest headline count.",
    "decisions": "LLM summary, trades, skips, blocked — audit trail.",
    "price_bars": "Historical intraday OHLCV (simulation / Yahoo backfill).",
    "app_kv": "Internal keys (last bar backfill day, etc.).",
    "schema_migrations": "Migration versions applied to this SQLite file.",
}


def sqlite_table_row_counts(db_path: str) -> list[dict[str, Any]]:
    conn = connect_readonly(db_path)
    try:
        cur = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        names = [str(r[0]) for r in cur.fetchall()]
        out: list[dict[str, Any]] = []
        for name in names:
            try:
                cnt = int(conn.execute(f"SELECT COUNT(*) AS c FROM {name}").fetchone()["c"])
            except sqlite3.Error:
                cnt = -1
            out.append(
                {"name": name, "rows": cnt, "purpose": TABLE_PURPOSES.get(name, "Application table.")}
            )
        return out
    finally:
        conn.close()


def load_model_runtime_snapshot(cfg: Config) -> dict[str, Any]:
    return {
        "ollama_base_url": cfg.ollama_base_url,
        "ollama_model": cfg.ollama_model,
        "ollama_timeout_sec": cfg.ollama_timeout_sec,
        "ollama_enrichment_model": cfg.ollama_enrichment_model,
        "ollama_translate_model": cfg.ollama_translate_model,
        "dry_run": cfg.dry_run,
        "simulation": cfg.simulation,
        "enforce_tase_hours": cfg.enforce_tase_hours,
        "maya_enabled": cfg.maya_enabled,
        "cycle_log_enabled": cfg.cycle_log_enabled,
        "cycle_log_dir": cfg.cycle_log_dir,
        "cycle_log_full_prompts": cfg.cycle_log_full_prompts,
        "knowledge_enrich_on_ingest": cfg.knowledge_enrich_on_ingest,
        "benchmark_symbol": cfg.benchmark_symbol,
        "watchlist_count": len(cfg.watchlist),
    }


def load_supervision_overview(cfg: Config, *, cycle_log_limit: int = 100) -> dict[str, Any]:
    db_p = Path(cfg.db_path)
    state_p = Path(cfg.state_path)
    log_dir = Path(cfg.cycle_log_dir)
    logs: list[dict[str, Any]] = []
    log_bytes_total = 0
    log_count = 0
    if log_dir.is_dir():
        all_logs = sorted(
            [p for p in log_dir.glob("cycle_*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        log_count = len(all_logs)
        for p in all_logs[: max(1, int(cycle_log_limit))]:
            st = p.stat()
            sz = int(st.st_size)
            log_bytes_total += sz
            logs.append(
                {
                    "cycle_id": _cycle_id_from_log_filename(p.name),
                    "filename": p.name,
                    "bytes": sz,
                    "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                }
            )

    tables: list[dict[str, Any]] = []
    if db_p.is_file():
        try:
            tables = sqlite_table_row_counts(str(db_p))
        except Exception as exc:
            tables = [{"name": "(error)", "rows": -1, "purpose": str(exc)}]

    return {
        "paths": {
            "db_path": str(db_p),
            "state_path": str(state_p),
            "cycle_log_dir": str(log_dir),
            "db": _file_stat(db_p),
            "state": _file_stat(state_p),
            "cycle_log_dir_exists": log_dir.is_dir(),
            "cycle_log_file_count": log_count,
            "cycle_logs_listed_byte_sum": log_bytes_total,
        },
        "sqlite_tables": tables,
        "cycle_logs": logs,
        "notes": [
            "Cycle JSON files mirror ingest counts, prompts, and model_response when DEMO_TRADER_CYCLE_LOG_ENABLED=1.",
            "`model_runtime` reflects this dashboard server's Config/env (align with cron/trader env for exact match).",
        ],
        "model_runtime": load_model_runtime_snapshot(cfg),
    }


def _strip_prompt_full_sections(payload: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(payload, ensure_ascii=False))
    pr = out.get("prompt")
    if not isinstance(pr, dict):
        return out
    sections = pr.get("sections")
    if not isinstance(sections, dict):
        return out
    for key in list(sections.keys()):
        sec = sections[key]
        if isinstance(sec, dict) and "full" in sec:
            sections[key] = {k: v for k, v in sec.items() if k != "full"}
    return out


def load_cycle_log_payload(cfg: Config, cycle_id: int, *, strip_full_prompts: bool) -> dict[str, Any] | None:
    root = Path(cfg.cycle_log_dir)
    if not root.is_dir():
        return None
    matches = sorted(root.glob(f"cycle_{int(cycle_id):05d}_*.json"), reverse=True)
    path = matches[0] if matches else None
    if not path or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    payload["_log_filename"] = path.name
    if strip_full_prompts:
        payload = _strip_prompt_full_sections(payload)
    return payload


def _parse_model_json_cell(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def load_cycle_decisions_detail(cfg: Config, cycle_id: int) -> list[dict[str, Any]]:
    conn = connect_readonly(cfg.db_path)
    try:
        cur = conn.execute(
            """
            SELECT id, ts, kind, symbol, side, qty, executed, exec_price, notional_ils,
                   reason_he, analysis_he, model_json, broker_message,
                   outcome_mtm_ils, outcome_ts
            FROM decisions
            WHERE cycle_id=?
            ORDER BY id ASC
            """,
            (int(cycle_id),),
        )
        cmap = _company_map(conn)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            sym = str(d["symbol"]) if d.get("symbol") else None
            d["company_label"] = company_display_label(sym, cmap)
            d["model_json"] = _parse_model_json_cell(d.get("model_json"))
            rows.append(d)
        return rows
    finally:
        conn.close()


def load_portfolio(cfg: Config) -> dict[str, Any]:
    state_path = Path(cfg.state_path)
    state = load_state(state_path, cfg.starting_cash_ils)
    positions: list[dict[str, Any]] = []
    for sym, qty in state.positions.items():
        positions.append({"symbol": sym, "qty": float(qty), "last_price": None, "market_value_ils": 0.0})
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

    if syms:
        missing_px = [
            sym
            for sym in syms
            if sym not in prices
            or prices.get(sym) is None
            or float(prices.get(sym, 0) or 0) <= 0
        ]
        if missing_px:
            try:
                conn_px = connect_readonly(cfg.db_path)
                try:
                    for sym in missing_px:
                        cur_px = conn_px.execute(
                            "SELECT last_price, currency FROM companies WHERE symbol=?",
                            (sym,),
                        )
                        row = cur_px.fetchone()
                        if row and row["last_price"]:
                            px_raw = price_to_ils(float(row["last_price"]), row["currency"])
                            if px_raw > 500 and sym.endswith(".TA"):
                                px_raw = px_raw / 100.0
                            prices[sym] = px_raw
                finally:
                    conn_px.close()
            except Exception:
                pass

    avg_buy_map = _avg_buy_ils_from_trades(list(state.trades))

    cmap: dict[str, dict[str, str]] = {}
    try:
        nm_conn = connect_readonly(cfg.db_path)
        try:
            cmap = _company_map(nm_conn)
            for pos in positions:
                sym = pos["symbol"]
                pos["company_label"] = company_display_label(sym, cmap) or sym
                lp = prices.get(sym)
                if lp is not None and float(lp) > 0:
                    pos["last_price"] = round(float(lp), 2)
                    pos["market_value_ils"] = round(float(lp) * float(pos["qty"]), 2)
                ab = avg_buy_map.get(sym)
                pos["avg_buy_ils"] = round(float(ab), 2) if ab is not None else None
                up = None
                if ab is not None and lp is not None and float(ab) > 0:
                    up = round((float(lp) - float(ab)) / float(ab) * 100.0, 2)
                pos["unrealized_pnl_pct"] = up
        finally:
            nm_conn.close()
    except Exception:
        for pos in positions:
            sym = pos["symbol"]
            pos["company_label"] = sym
            lp = prices.get(sym)
            if lp is not None and float(lp) > 0:
                pos["last_price"] = round(float(lp), 2)
                pos["market_value_ils"] = round(float(lp) * float(pos["qty"]), 2)
            ab = avg_buy_map.get(sym)
            pos["avg_buy_ils"] = round(float(ab), 2) if ab is not None else None
            up = None
            if ab is not None and lp is not None and float(ab) > 0:
                up = round((float(lp) - float(ab)) / float(ab) * 100.0, 2)
            pos["unrealized_pnl_pct"] = up

    positions.sort(key=lambda x: float(x["market_value_ils"] or 0), reverse=True)

    mv_total = sum(float(p["market_value_ils"] or 0) for p in positions)
    nav = cash + mv_total
    cash_pct = (cash / nav * 100.0) if nav > 0 else 100.0

    bench_last = prices.get(bench_sym)
    perf = compute_performance(
        state,
        prices={s: prices.get(s, 0.0) for s in syms},
        benchmark_last=float(bench_last or (state.session.benchmark_start_px if state.session else 0) or 0),
    )

    holdings_alloc: list[dict[str, Any]] = []
    for pos in positions:
        v = float(pos["market_value_ils"] or 0)
        if v <= 0:
            continue
        holdings_alloc.append(
            {
                "kind": "position",
                "symbol": pos["symbol"],
                "label": pos.get("company_label") or pos["symbol"],
                "value_ils": round(v, 2),
                "uplift_pct": pos.get("unrealized_pnl_pct"),
            }
        )

    allocation: list[dict[str, Any]] = [
        {"kind": "cash", "symbol": None, "label": "מזומן (Cash)", "value_ils": round(cash, 2), "uplift_pct": None}
    ]
    allocation.extend(holdings_alloc)

    session = state.session
    return {
        "cash_ils": round(cash, 2),
        "nav_ils": round(nav, 2),
        "cash_pct": round(cash_pct, 2),
        "portfolio_return_pct": _round2_maybe(perf.portfolio_return_pct),
        "benchmark_return_pct": _round2_maybe(perf.benchmark_return_pct),
        "alpha_pct": _round2_maybe(perf.alpha_vs_benchmark_pct),
        "positions": [{**p, "qty": round(float(p["qty"]), 2)} for p in positions],
        "last_cycle_ts": state.last_cycle_ts,
        "session": {
            "started_ts": session.started_ts if session else None,
            "benchmark_symbol": bench_sym,
            "benchmark_label": company_display_label(bench_sym, cmap),
            "benchmark_start_px": _round2_maybe(session.benchmark_start_px) if session else None,
            "initial_nav_ils": round(float(session.initial_nav_ils if session else cfg.starting_cash_ils), 2),
        },
        "allocation": allocation,
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
        cmap = _company_map(conn)
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
            trades: list[dict[str, Any]] = []
            blocked: list[dict[str, Any]] = []
            summary_from_db = ""
            for item in decisions:
                kind = str(item.get("kind") or "")
                if kind == "llm_summary" and item.get("analysis_he"):
                    summary_from_db = str(item["analysis_he"]).strip()
                if kind == "trade" and item.get("executed"):
                    trades.append(item)
                elif kind in {"trade", "blocked_after_hours", "skip"}:
                    blocked.append(item)

            log_path = _cycle_log_path(log_dir, cid, c["ts"])
            model_analysis = ""
            by_sym_hints: dict[str, str] = {}
            english_digest = ""
            payload_for_digest: dict[str, Any] = {}
            if log_path and log_path.is_file():
                try:
                    payload_for_digest = json.loads(log_path.read_text(encoding="utf-8"))
                    model_analysis, by_sym_hints = _model_decision_hints(payload_for_digest.get("model_response"))
                    if isinstance(payload_for_digest, dict):
                        english_digest = _english_digest_from_cycle_payload(payload_for_digest)
                except Exception:
                    payload_for_digest = {}

            sa = model_analysis.strip()
            sb = summary_from_db.strip()
            if sa and sb:
                if sa == sb or sb in sa:
                    summary_he_full = sa
                elif sa in sb:
                    summary_he_full = sb
                else:
                    summary_he_full = sa + "\n\n—— מהמסד (SQLite) ——\n" + sb
            else:
                summary_he_full = sa or sb

            summary_he_full = _tighten_spaced_hebrew(summary_he_full)

            ref = _parse_ts(c["ts"])
            market_open = bool(c["trading_allowed"]) if ref is None else is_tase_regular_trading_hours(ref)

            actions = []
            for t in trades:
                sym_t = str(t.get("symbol") or "") or None
                reason_he = _tighten_spaced_hebrew(merge_action_reason(str(t.get("reason_he") or ""), symbol=sym_t, by_sym_hints=by_sym_hints))
                actions.append(
                    {
                        "type": "trade",
                        "symbol": sym_t,
                        "company_label": company_display_label(sym_t, cmap),
                        "side": t.get("side"),
                        "qty": t.get("qty"),
                        "executed": True,
                        "reason_he": reason_he,
                    }
                )
            for b in blocked[:12]:
                sym_b = str(b.get("symbol") or "") or None
                reason_b = _tighten_spaced_hebrew(merge_action_reason(str(b.get("reason_he") or ""), symbol=sym_b, by_sym_hints=by_sym_hints))
                actions.append(
                    {
                        "type": "blocked" if b.get("kind") == "blocked_after_hours" else "skip",
                        "symbol": sym_b,
                        "company_label": company_display_label(sym_b, cmap),
                        "side": b.get("side"),
                        "qty": b.get("qty"),
                        "executed": False,
                        "reason_he": reason_b,
                    }
                )
            if not actions and summary_he_full:
                actions.append({"type": "hold", "symbol": None, "company_label": None, "reason_he": summary_he_full})

            nav_raw = c["nav_ils"]
            bm_px = c["benchmark_px"]
            out.append(
                {
                    "cycle_id": cid,
                    "ts": c["ts"],
                    "market_open": market_open,
                    "trading_allowed": bool(c["trading_allowed"]),
                    "nav_ils": round(float(nav_raw), 2) if nav_raw is not None else None,
                    "portfolio_return_pct": _round2_maybe(c["portfolio_return_pct"]),
                    "benchmark_return_pct": _round2_maybe(c["benchmark_return_pct"]),
                    "alpha_pct": _round2_maybe(c["alpha_pct"]),
                    "benchmark_px": round(float(bm_px), 2) if bm_px is not None else None,
                    "benchmark_symbol": str(c["benchmark_symbol"] or ""),
                    "benchmark_label": company_display_label(str(c["benchmark_symbol"] or ""), cmap),
                    "headline_count": c["headline_count"],
                    "executed_trades": len(trades),
                    "summary_he": summary_he_full,
                    "english_digest": english_digest[:4000] if english_digest else "",
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
        cmap = _company_map(conn)
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
            msym = str(r["matched_symbol"] or "").strip() or None
            rows.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "event_time": r["event_time"],
                    "source": src,
                    "url": r["url"],
                    "title": r["title"],
                    "title_en": r["title_en"],
                    "matched_symbol": msym,
                    "matched_company_label": company_display_label(msym, cmap),
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
