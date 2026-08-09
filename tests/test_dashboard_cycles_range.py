"""Regression: cycles in-range must not be dropped by a post-filter LIMIT."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from demo_trader.config import Config
from demo_trader.dashboard import data as dash_data
from demo_trader.db import connect, init_schema, insert_cycle
from demo_trader.schema_migrations import run_pending_migrations


class TestDashboardCyclesRange(unittest.TestCase):
    def test_load_cycles_includes_older_in_range_despite_dense_recent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            state = Path(td) / "state.json"
            state.write_text('{"cash_ils": 100000, "positions": {}, "trades": [], "session": null}')
            conn = connect(db)
            init_schema(conn)
            run_pending_migrations(conn)

            now = datetime.now(timezone.utc).replace(microsecond=0)
            # Older in-range cycle first (low id), then a dense burst of newer cycles.
            old_ts = (now - timedelta(days=20)).isoformat()
            old_id = insert_cycle(
                conn,
                trading_allowed=False,
                knowledge_only=True,
                nav_ils=99_000.0,
                benchmark_symbol="TA35.TA",
                benchmark_px=1900.0,
                portfolio_return_pct=-1.0,
                benchmark_return_pct=-0.5,
                alpha_pct=-0.5,
                headline_count=1,
                ts_utc_iso=old_ts,
            )
            for i in range(250):
                insert_cycle(
                    conn,
                    trading_allowed=True,
                    knowledge_only=False,
                    nav_ils=100_000.0 + i,
                    benchmark_symbol="TA35.TA",
                    benchmark_px=2000.0,
                    portfolio_return_pct=0.1,
                    benchmark_return_pct=0.0,
                    alpha_pct=0.1,
                    headline_count=0,
                    ts_utc_iso=(now - timedelta(minutes=i)).isoformat(),
                )
            conn.close()

            cfg = replace(
                Config(),
                db_path=str(db),
                state_path=str(state),
                cycle_log_dir=str(Path(td) / "logs"),
                dry_run=True,
            )
            since = now - timedelta(days=30)
            # Old bug: SELECT … LIMIT 100*3 then Python-filter → older in-range row never fetched.
            page = dash_data.load_cycles(cfg, since=since, limit=100, offset=0)
            self.assertEqual(page["total"], 251)
            self.assertEqual(page["returned"], 100)
            self.assertTrue(page["has_more"])

            ids_first = {c["cycle_id"] for c in page["cycles"]}
            self.assertNotIn(old_id, ids_first)

            # Walk pages until the older session appears.
            found = False
            offset = 0
            seen = 0
            while True:
                chunk = dash_data.load_cycles(cfg, since=since, limit=100, offset=offset)
                seen += chunk["returned"]
                if any(c["cycle_id"] == old_id for c in chunk["cycles"]):
                    found = True
                    break
                if not chunk["has_more"]:
                    break
                offset += chunk["returned"]
            self.assertTrue(found, "20-day-old cycle must be reachable via pagination")
            self.assertEqual(seen, 251)

    def test_all_time_has_no_since_bound_in_api_helper(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            state = Path(td) / "state.json"
            state.write_text('{"cash_ils": 1, "positions": {}, "trades": [], "session": null}')
            conn = connect(db)
            init_schema(conn)
            run_pending_migrations(conn)
            insert_cycle(
                conn,
                trading_allowed=True,
                knowledge_only=False,
                nav_ils=1.0,
                benchmark_symbol="TA35.TA",
                benchmark_px=1.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                headline_count=0,
                ts_utc_iso="2020-01-01T00:00:00+00:00",
            )
            conn.close()
            cfg = replace(
                Config(),
                db_path=str(db),
                state_path=str(state),
                cycle_log_dir=str(Path(td) / "logs"),
                dry_run=True,
            )
            page = dash_data.load_cycles(cfg, since=None, until=None, limit=10)
            self.assertEqual(page["total"], 1)
            self.assertEqual(page["cycles"][0]["cycle_id"], 1)


if __name__ == "__main__":
    unittest.main()
