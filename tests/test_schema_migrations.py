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

            conn = open_db(path, announce_migrations=False)
            self.assertEqual(applied_versions(conn), {EXPECTED_LATEST_VERSION})
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
            self.assertEqual(before, {EXPECTED_LATEST_VERSION})
            self.assertEqual(r2.applied, tuple())
            self.assertEqual(r2.latest_version, EXPECTED_LATEST_VERSION)


if __name__ == "__main__":
    unittest.main()
