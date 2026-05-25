from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from demo_trader.config import Config
from demo_trader.dashboard.data import (
    gather_inspect_cited_news_event_ids,
    knowledge_event_refs_by_ids,
    load_cycle_decisions_detail,
    load_cycle_log_payload,
    load_cycles,
    load_knowledge,
    load_portfolio,
    load_supervision_overview,
    parse_range_query,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(cfg: Config | None = None) -> Flask:
    config = cfg or Config()
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/health")
    def health():
        db_ok = Path(config.db_path).is_file()
        state_ok = Path(config.state_path).is_file()
        return jsonify(
            {
                "ok": db_ok and state_ok,
                "db_path": config.db_path,
                "state_path": config.state_path,
                "db_exists": db_ok,
                "state_exists": state_ok,
            }
        )

    @app.get("/api/portfolio")
    def api_portfolio():
        return jsonify(load_portfolio(config))

    @app.get("/api/cycles")
    def api_cycles():
        since, until = parse_range_query(
            request.args.get("since"),
            request.args.get("until"),
        )
        if since is None and until is None:
            days = int(request.args.get("days", "30"))
            since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        limit = int(request.args.get("limit", "100"))
        return jsonify(
            {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
                "cycles": load_cycles(config, since=since, until=until, limit=limit),
            }
        )

    @app.get("/api/knowledge")
    def api_knowledge():
        since, until = parse_range_query(
            request.args.get("since"),
            request.args.get("until"),
        )
        if since is None and until is None:
            days = int(request.args.get("days", "30"))
            since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        source = request.args.get("source")
        maya_only = request.args.get("maya_only", "").lower() in {"1", "true", "yes"}
        prefix = "maya." if maya_only else source
        limit = int(request.args.get("limit", "200"))
        rows = load_knowledge(config, since=since, until=until, source_prefix=prefix, limit=limit)
        return jsonify(
            {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
                "items": rows,
            }
        )

    @app.get("/api/supervision/overview")
    def api_supervision_overview():
        limit = int(request.args.get("cycle_log_limit", "100"))
        return jsonify(load_supervision_overview(config, cycle_log_limit=limit))

    @app.get("/api/supervision/cycle-inspect")
    def api_supervision_cycle_inspect():
        cid = request.args.get("cycle_id", type=int)
        if cid is None or cid < 1:
            return jsonify({"error": "cycle_id must be positive"}), 400
        strip_full = request.args.get("strip_full_prompts", "1").lower() not in {"0", "false", "no"}
        payload = load_cycle_log_payload(config, cid, strip_full_prompts=strip_full)
        decisions = load_cycle_decisions_detail(config, cid)
        cite_ids = gather_inspect_cited_news_event_ids(payload or {}, decisions)
        cited_articles = knowledge_event_refs_by_ids(config, cite_ids)
        return jsonify(
            {
                "cycle_id": cid,
                "cycle_log": payload,
                "decisions": decisions,
                "strip_full_prompts": strip_full,
                "cited_news_event_ids": cite_ids,
                "cited_articles": cited_articles,
            }
        )

    return app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TA-35 paper trader web dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)
    flask_app = create_app()
    print(f"Dashboard: http://{args.host}:{args.port}/", flush=True)
    flask_app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
