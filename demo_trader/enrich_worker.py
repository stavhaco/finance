from __future__ import annotations

import argparse
import logging
import sys
import time

from demo_trader.config import Config
from demo_trader.db import open_db
from demo_trader.enrichment_jobs import claim_pending_jobs, complete_job, pending_job_count
from demo_trader.knowledge_enrichment import enrich_knowledge_event_by_id
from demo_trader.ollama_health import format_ollama_help, ollama_reachable

logger = logging.getLogger(__name__)


def run_enrich_batch(cfg: Config, *, limit: int) -> int:
    conn = open_db(cfg.db_path, announce_migrations=False)
    if not cfg.dry_run:
        ok, detail = ollama_reachable(cfg.ollama_base_url)
        if not ok:
            print(f"Ollama unreachable: {detail}", file=sys.stderr)
            print(format_ollama_help(cfg.ollama_base_url, cfg.ollama_enrichment_model or cfg.ollama_model))
            return 3

    kids = claim_pending_jobs(conn, limit=max(1, limit))
    if not kids:
        print("enrich worker: no pending jobs", flush=True)
        return 0

    done = 0
    failed = 0
    for kid in kids:
        try:
            enrich_knowledge_event_by_id(conn, kid, cfg)
            complete_job(conn, kid, ok=True)
            done += 1
            print(f"enriched knowledge_event id={kid}", flush=True)
        except Exception as e:
            complete_job(conn, kid, ok=False, error=str(e))
            failed += 1
            logger.warning("enrich failed id=%s: %s", kid, e)
            print(f"enrich failed id={kid}: {e}", file=sys.stderr)

    pending = pending_job_count(conn)
    print(f"enrich worker: ok={done} failed={failed} pending={pending}", flush=True)
    return 1 if failed and not done else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Process async knowledge enrichment jobs from SQLite.")
    p.add_argument("--limit", type=int, default=8, help="Max jobs per batch.")
    p.add_argument("--loop", action="store_true", help="Run until no pending jobs.")
    p.add_argument("--sleep-sec", type=int, default=30, help="Sleep between loop batches.")
    args = p.parse_args(argv)
    cfg = Config()

    if not args.loop:
        return run_enrich_batch(cfg, limit=args.limit)

    while True:
        rc = run_enrich_batch(cfg, limit=args.limit)
        if pending_job_count(open_db(cfg.db_path, announce_migrations=False)) == 0:
            return rc
        time.sleep(max(5, int(args.sleep_sec)))


if __name__ == "__main__":
    raise SystemExit(main())
