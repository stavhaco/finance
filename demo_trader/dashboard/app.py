from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from demo_trader.config import Config
from demo_trader.dashboard.data import (
    load_cycle_decisions_detail,
    load_cycle_log_payload,
    load_cycles,
    load_knowledge,
    load_portfolio,
    load_supervision_overview,
    parse_range_query,
)
from demo_trader.dashboard.ops_status import load_nav_series_api, load_ops_status

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
            days_raw = request.args.get("days", "30")
            if str(days_raw).lower() not in {"all", "0", ""}:
                days = int(days_raw)
                if days > 0:
                    since = datetime.now(timezone.utc) - timedelta(days=days)
        limit = int(request.args.get("limit", "100"))
        offset = int(request.args.get("offset", "0"))
        payload = load_cycles(config, since=since, until=until, limit=limit, offset=offset)
        return jsonify(
            {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
                **payload,
            }
        )

    @app.get("/api/knowledge")
    def api_knowledge():
        since, until = parse_range_query(
            request.args.get("since"),
            request.args.get("until"),
        )
        if since is None and until is None:
            days_raw = request.args.get("days", "30")
            if str(days_raw).lower() not in {"all", "0", ""}:
                days = int(days_raw)
                if days > 0:
                    since = datetime.now(timezone.utc) - timedelta(days=days)
        source = request.args.get("source")
        maya_only = request.args.get("maya_only", "").lower() in {"1", "true", "yes"}
        prefix = "maya." if maya_only else source
        limit = int(request.args.get("limit", "200"))
        offset = int(request.args.get("offset", "0"))
        payload = load_knowledge(
            config, since=since, until=until, source_prefix=prefix, limit=limit, offset=offset
        )
        return jsonify(
            {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
                **payload,
            }
        )

    @app.get("/api/supervision/overview")
    def api_supervision_overview():
        limit = int(request.args.get("cycle_log_limit", "250"))
        offset = int(request.args.get("cycle_log_offset", "0"))
        return jsonify(load_supervision_overview(config, cycle_log_limit=limit, cycle_log_offset=offset))

    @app.get("/api/status")
    def api_status():
        return jsonify(load_ops_status(config))

    @app.get("/api/series/nav")
    def api_series_nav():
        days = int(request.args.get("days", "30"))
        return jsonify(load_nav_series_api(config, days=days))

    @app.get("/api/events")
    def api_events():
        """Lightweight poll endpoint: last cycle id + alert count (for fast dashboard refresh)."""
        st = load_ops_status(config)
        lc = st.get("last_cycle") or {}
        return jsonify(
            {
                "last_cycle_id": lc.get("id"),
                "alert_count": len(st.get("alerts") or []),
                "enrich_pending": int((st.get("enrichment_jobs") or {}).get("pending", 0)),
            }
        )

    @app.get("/api/supervision/cycle-inspect")
    def api_supervision_cycle_inspect():
        cid = request.args.get("cycle_id", type=int)
        if cid is None or cid < 1:
            return jsonify({"error": "cycle_id must be positive"}), 400
        strip_full = request.args.get("strip_full_prompts", "1").lower() not in {"0", "false", "no"}
        payload = load_cycle_log_payload(config, cid, strip_full_prompts=strip_full)
        decisions = load_cycle_decisions_detail(config, cid)
        return jsonify(
            {"cycle_id": cid, "cycle_log": payload, "decisions": decisions, "strip_full_prompts": strip_full}
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
