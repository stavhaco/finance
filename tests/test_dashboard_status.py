import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from demo_trader.config import Config
from demo_trader.dashboard.ops_status import load_ops_status
from demo_trader.db import connect, init_schema, insert_cycle, open_db
from demo_trader.schema_migrations import run_pending_migrations


class TestDashboardStatus(unittest.TestCase):
    def test_ops_status_with_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            state = Path(td) / "state.json"
            conn = connect(db)
            init_schema(conn)
            run_pending_migrations(conn)
            insert_cycle(
                conn,
                trading_allowed=True,
                knowledge_only=False,
                nav_ils=100_000.0,
                benchmark_symbol="TA35.TA",
                benchmark_px=2000.0,
                portfolio_return_pct=1.0,
                benchmark_return_pct=0.5,
                alpha_pct=0.5,
                headline_count=3,
                prompt_version="v2-slim",
                duration_ms=1200,
            )
            state.write_text('{"cash_ils": 100000, "positions": {}, "trades": [], "session": null}')
            cfg = replace(
                Config(),
                db_path=str(db),
                state_path=str(state),
                dry_run=True,
            )
            st = load_ops_status(cfg)
            self.assertTrue(st["ollama_ok"])
            self.assertIsNotNone(st["last_cycle"])
            self.assertEqual(st["last_cycle"]["id"], 1)


if __name__ == "__main__":
    unittest.main()
