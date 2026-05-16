"""Backfill knowledge_events enrichment (translate / summary / sentiment / tags)."""

from __future__ import annotations

import argparse
import time

from demo_trader.config import Config
from demo_trader.db import open_db
from demo_trader.knowledge_enrichment import enrich_knowledge_event_by_id


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backfill knowledge_events LLM enrichment.")
    p.add_argument("--limit", type=int, default=0, help="Max rows (0 = no limit).")
    p.add_argument("--sleep-sec", type=float, default=0.0, help="Pause between rows (rate limiting).")
    p.add_argument("--force-all", action="store_true", help="Re-run even when enrichment_status=ok.")
    args = p.parse_args(argv)

    cfg = Config()
    conn = open_db(cfg.db_path)

    if args.force_all:
        cur = conn.execute("SELECT id FROM knowledge_events ORDER BY id ASC")
    else:
        cur = conn.execute(
            """
            SELECT id FROM knowledge_events
            WHERE enrichment_status IS NULL OR enrichment_status != 'ok'
            ORDER BY datetime(COALESCE(event_time, ts)) ASC
            """
        )
    ids = [int(r[0]) for r in cur.fetchall()]
    if args.limit and args.limit > 0:
        ids = ids[: int(args.limit)]

    ok = 0
    for i, row_id in enumerate(ids, start=1):
        print(f"[{i}/{len(ids)}] enriching id={row_id}", flush=True)
        if enrich_knowledge_event_by_id(conn, row_id, cfg, force=args.force_all):
            ok += 1
        if args.sleep_sec > 0:
            time.sleep(float(args.sleep_sec))
    print(f"done: succeeded≈{ok}/{len(ids)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
