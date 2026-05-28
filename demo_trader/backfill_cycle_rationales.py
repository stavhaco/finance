"""Backfill English trade rationales from cycle JSON logs into SQLite decisions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from demo_trader.bot import _trade_audit_reason
from demo_trader.config import Config
from demo_trader.dashboard.data import _looks_english, _model_decision_hints
from demo_trader.db import open_db

_PLACEHOLDER_REASONS = frozenset({"מודל", "model", "Model", ""})


def _symbols_from_model_response(model_response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in ("recommendations", "trades"):
        rows = model_response.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or "").strip()
            if sym:
                out[sym] = row
    return out


def _reason_worth_updating(old: str, new: str) -> bool:
    old_s = (old or "").strip()
    new_s = (new or "").strip()
    if not new_s or new_s == old_s:
        return False
    if _looks_english(old_s) and not _looks_english(new_s):
        return False
    if old_s in _PLACEHOLDER_REASONS:
        return True
    if old_s.startswith("[why_en]") or old_s.startswith("[evidence_"):
        return True
    if not _looks_english(old_s) and _looks_english(new_s):
        return True
    return _looks_english(new_s) and len(new_s) > len(old_s)


def _analysis_worth_updating(old: str, new: str) -> bool:
    old_s = (old or "").strip()
    new_s = (new or "").strip()
    if not new_s or new_s == old_s:
        return False
    if not _looks_english(new_s):
        return False
    if not old_s:
        return True
    if not _looks_english(old_s):
        return True
    return len(new_s) > len(old_s)


def _load_cycle_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def backfill_cycle_from_payload(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    model_response: dict[str, Any],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Update decisions for one cycle. Returns (reason_updates, analysis_updates)."""
    by_sym = _symbols_from_model_response(model_response)
    _, _, summary_en = _model_decision_hints(model_response)

    cur = conn.execute(
        """
        SELECT id, kind, symbol, reason_he, analysis_he
        FROM decisions
        WHERE cycle_id=?
        ORDER BY id ASC
        """,
        (int(cycle_id),),
    )
    reason_updates = 0
    analysis_updates = 0

    for row in cur.fetchall():
        kind = str(row["kind"] or "")
        old_reason = str(row["reason_he"] or "")
        old_analysis = str(row["analysis_he"] or "")

        if kind == "llm_summary" and summary_en and _analysis_worth_updating(old_analysis, summary_en):
            if not dry_run:
                conn.execute(
                    "UPDATE decisions SET analysis_he=? WHERE id=?",
                    (summary_en[:4000], int(row["id"])),
                )
            analysis_updates += 1
            continue

        sym = str(row["symbol"] or "").strip()
        if kind not in {"trade", "skip", "blocked_after_hours"} or not sym:
            continue
        raw = by_sym.get(sym)
        if not raw:
            continue
        new_reason = _trade_audit_reason(raw)
        if not _reason_worth_updating(old_reason, new_reason):
            continue
        if not dry_run:
            conn.execute(
                "UPDATE decisions SET reason_he=? WHERE id=?",
                (new_reason[:900], int(row["id"])),
            )
        reason_updates += 1

    if not dry_run and (reason_updates or analysis_updates):
        conn.commit()
    return reason_updates, analysis_updates


def iter_cycle_log_paths(log_dir: Path) -> list[Path]:
    if not log_dir.is_dir():
        return []
    return sorted(log_dir.glob("cycle_*.json"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Backfill English rationales from cycle JSON logs into SQLite decisions."
    )
    p.add_argument("--dry-run", action="store_true", help="Print updates without writing.")
    p.add_argument("--cycle-id", type=int, default=0, help="Only process this cycle id (0 = all).")
    p.add_argument("--limit", type=int, default=0, help="Max cycle logs to scan (0 = no limit).")
    args = p.parse_args(argv)

    cfg = Config()
    conn = open_db(cfg.db_path)
    log_dir = Path(cfg.cycle_log_dir)
    paths = iter_cycle_log_paths(log_dir)
    if args.cycle_id > 0:
        paths = [p for p in paths if p.name.startswith(f"cycle_{args.cycle_id:05d}_")]
    if args.limit and args.limit > 0:
        paths = paths[: int(args.limit)]

    total_reason = 0
    total_analysis = 0
    scanned = 0

    for path in paths:
        payload = _load_cycle_payload(path)
        if not payload:
            print(f"skip (unreadable): {path.name}", flush=True)
            continue
        cycle_id = int(payload.get("cycle_id") or 0)
        if cycle_id <= 0:
            print(f"skip (no cycle_id): {path.name}", flush=True)
            continue
        model_response = payload.get("model_response")
        if not isinstance(model_response, dict):
            print(f"skip (no model_response): cycle #{cycle_id}", flush=True)
            continue

        scanned += 1
        reason_n, analysis_n = backfill_cycle_from_payload(
            conn,
            cycle_id=cycle_id,
            model_response=model_response,
            dry_run=bool(args.dry_run),
        )
        total_reason += reason_n
        total_analysis += analysis_n
        if reason_n or analysis_n:
            mode = "would update" if args.dry_run else "updated"
            print(
                f"cycle #{cycle_id}: {mode} reason={reason_n} analysis={analysis_n} ({path.name})",
                flush=True,
            )

    suffix = " (dry-run)" if args.dry_run else ""
    print(
        f"done{suffix}: scanned={scanned} reason_updates={total_reason} analysis_updates={total_analysis}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
