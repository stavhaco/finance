"""One-shot helpers to seed simulation data (intraday bars + Maya/RSS knowledge)."""

from __future__ import annotations

import argparse
from dataclasses import replace

from demo_trader.config import Config
from demo_trader.db import open_db, upsert_companies
from demo_trader.historic_bars import maybe_daily_intraday_backfill
from demo_trader.knowledge_ingest import ingest_headlines, ingest_maya_rows
from demo_trader.maya_client import normalize_maya_items
from demo_trader.news_feeds import fetch_headlines
from demo_trader.ta35_catalog import TA35_COMPANIES


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backfill price bars and ingest knowledge for simulation.")
    p.add_argument("--force-bars", action="store_true", help="Re-run yfinance backfill even if done today (IL).")
    p.add_argument("--rss", action="store_true", help="Also fetch RSS headlines into the knowledge table.")
    p.add_argument("--maya-lookback-days", type=int, default=None, help="Override DEMO_TRADER_MAYA_LOOKBACK_DAYS for this run.")
    p.add_argument("--no-enrich", action="store_true", help="Skip per-row LLM enrichment during ingest (use backfill_knowledge later).")
    args = p.parse_args(argv)

    cfg = Config()
    if args.no_enrich:
        cfg = replace(cfg, knowledge_enrich_on_ingest=False)

    lookback = args.maya_lookback_days if args.maya_lookback_days is not None else max(cfg.maya_lookback_days, cfg.price_history_days + 5)

    conn = open_db(cfg.db_path)
    upsert_companies(
        conn,
        ((c.symbol, c.name_he, c.name_en, c.sector_he, c.category_he) for c in TA35_COMPANIES),
    )

    bar_syms = sorted(set(cfg.watchlist) | {cfg.benchmark_symbol})
    maybe_daily_intraday_backfill(
        conn,
        symbols=bar_syms,
        interval=cfg.price_bar_interval,
        history_days=cfg.price_history_days,
        force=bool(args.force_bars),
    )

    maya_rows = normalize_maya_items(
        lookback_days=lookback,
        breaking_limit=cfg.maya_breaking_limit,
        post_max_keep=cfg.maya_post_max_keep,
        connect_timeout_sec=cfg.maya_http_connect_timeout_sec,
        read_timeout_sec=cfg.maya_http_read_timeout_sec,
    )
    n_maya = ingest_maya_rows(conn, maya_rows, cfg=cfg)
    print(f"Maya: fetched={len(maya_rows)} inserted_or_new≈{n_maya}")

    if args.rss:
        headlines = fetch_headlines(cfg.rss_feeds(), cfg.news_max_headlines)
        n_rss = ingest_headlines(conn, headlines, cfg=cfg)
        print(f"RSS: headlines={len(headlines)} inserted_or_new≈{n_rss}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
