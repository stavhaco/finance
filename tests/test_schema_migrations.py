from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from demo_trader.db import init_schema, open_db
from demo_trader.schema_migrations import (
    EXPECTED_LATEST_VERSION,
    applied_versions,
    run_pending_migrations,
)


class TestSchemaMigrations(unittest.TestCase):
    def test_migrations_idempotent_on_fresh_db(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.db")
            conn = sqlite3.connect(path)
            conn.execute("PRAGMA foreign_keys=ON")
            init_schema(conn)
            conn.close()

            expected_applied = set(range(1, EXPECTED_LATEST_VERSION + 1))
            conn = open_db(path, announce_migrations=False)
            self.assertEqual(applied_versions(conn), expected_applied)
            cur = conn.execute("PRAGMA table_info(companies)")
            cols = {str(r[1]) for r in cur.fetchall()}
            self.assertIn("market_cap", cols)
            self.assertIn("return_1y_pct", cols)
            conn.close()

            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            before = applied_versions(conn)
            init_schema(conn)
            r2 = run_pending_migrations(conn)
            conn.close()
            self.assertEqual(before, expected_applied)
            self.assertEqual(r2.applied, tuple())
            self.assertEqual(r2.latest_version, EXPECTED_LATEST_VERSION)

    def test_migration_002_sim_tables(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            conn = open_db(path, announce_migrations=False)
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            names = {str(r[0]) for r in cur.fetchall()}
            self.assertIn("app_kv", names)
            self.assertIn("price_bars", names)
            cur = conn.execute("PRAGMA table_info(knowledge_events)")
            cols = {str(r[1]) for r in cur.fetchall()}
            self.assertIn("event_time", cols)
            conn.close()

    def test_migration_003_knowledge_enrichment_columns(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "k3.db")
            conn = open_db(path, announce_migrations=False)
            cur = conn.execute("PRAGMA table_info(knowledge_events)")
            cols = {str(r[1]) for r in cur.fetchall()}
            for c in (
                "title_en",
                "body_translation_en",
                "executive_summary_en",
                "sentiment",
                "trade_usefulness",
                "is_broad_market",
                "enrichment_status",
            ):
                self.assertIn(c, cols)
            conn.close()


if __name__ == "__main__":
    unittest.main()
