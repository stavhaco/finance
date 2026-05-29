from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from demo_trader.config import Config
from demo_trader.db import connect_readonly
from demo_trader.enrichment_jobs import enrichment_job_stats, pending_job_count
from demo_trader.ollama_health import ollama_reachable
from demo_trader.tase_calendar import is_tase_regular_trading_hours


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_ops_status(cfg: Config) -> dict[str, Any]:
    db_path = Path(cfg.db_path)
    alerts: list[dict[str, str]] = []
    last_cycle: dict[str, Any] | None = None
    enrich = {"pending": 0, "processing": 0, "failed": 0, "done": 0}

    if db_path.is_file():
        conn = connect_readonly(str(db_path))
        try:
            enrich = enrichment_job_stats(conn)
            pending = pending_job_count(conn)
            if pending > 20:
                alerts.append(
                    {
                        "level": "warn",
                        "code": "enrich_backlog",
                        "message": f"{pending} enrichment jobs pending — run enrich worker.",
                    }
                )
            if enrich.get("failed", 0) > 0:
                alerts.append(
                    {
                        "level": "warn",
                        "code": "enrich_failed",
                        "message": f"{enrich['failed']} enrichment jobs failed.",
                    }
                )
            cur = conn.execute(
                """
                SELECT id, ts, nav_ils, alpha_pct, knowledge_only, duration_ms,
                       prompt_version, trading_allowed, ingest_json
                FROM cycles ORDER BY id DESC LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                last_cycle = dict(row)
                ts = _parse_ts(str(row["ts"]))
                if ts and (datetime.now(timezone.utc) - ts).total_seconds() > 1200:
                    alerts.append(
                        {
                            "level": "warn",
                            "code": "stale_cycle",
                            "message": "No cycle in the last 20 minutes.",
                        }
                    )
                if row["knowledge_only"]:
                    alerts.append(
                        {
                            "level": "info",
                            "code": "knowledge_only",
                            "message": "Last cycle was knowledge-only (no trades executed).",
                        }
                    )
            cur = conn.execute(
                """
                SELECT COUNT(*) FROM decisions
                WHERE kind='ollama_error'
                  AND ts >= datetime('now', '-1 day')
                """
            )
            err_n = int(cur.fetchone()[0])
            if err_n > 0:
                alerts.append(
                    {
                        "level": "error",
                        "code": "ollama_errors",
                        "message": f"{err_n} Ollama error(s) in the last 24h.",
                    }
                )
        finally:
            conn.close()

    ollama_ok, ollama_detail = (True, "dry_run") if cfg.dry_run else ollama_reachable(cfg.ollama_base_url)
    if not ollama_ok:
        alerts.append(
            {
                "level": "error",
                "code": "ollama_down",
                "message": f"Ollama unreachable: {ollama_detail}",
            }
        )

    tase_open = is_tase_regular_trading_hours(None)

    return {
        "ts_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tase_trading_open": tase_open,
        "ollama_ok": ollama_ok,
        "ollama_detail": ollama_detail,
        "enrichment_jobs": enrich,
        "last_cycle": last_cycle,
        "alerts": alerts,
        "prompt_version": cfg.prompt_version,
        "knowledge_enrich_async": cfg.knowledge_enrich_async,
    }


def load_nav_series_api(cfg: Config, *, days: int = 30) -> dict[str, Any]:
    from demo_trader.db import load_nav_series

    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    conn = connect_readonly(cfg.db_path)
    try:
        rows = load_nav_series(conn, since_iso=since.isoformat(), limit=2000)
        points = []
        for r in rows:
            points.append(
                {
                    "cycle_id": r["id"],
                    "ts": r["ts"],
                    "nav_ils": r["nav_ils"],
                    "portfolio_return_pct": r["portfolio_return_pct"],
                    "benchmark_return_pct": r["benchmark_return_pct"],
                    "alpha_pct": r["alpha_pct"],
                    "knowledge_only": bool(r["knowledge_only"]),
                }
            )
        return {"since": since.isoformat(), "points": points}
    finally:
        conn.close()
