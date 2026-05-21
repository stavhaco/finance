import sqlite3
import tempfile
import unittest
from pathlib import Path

from demo_trader.db import connect, connect_readonly, init_schema


class TestDbWal(unittest.TestCase):
    def test_wal_and_readonly(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.db"
            w = connect(path)
            init_schema(w)
            w.execute("INSERT INTO companies(symbol,name_he,name_en,sector_he,category_he) VALUES('X.TA','a','b','c','d')")
            w.commit()
            w.close()
            r = connect_readonly(path)
            row = r.execute("SELECT symbol FROM companies").fetchone()
            self.assertEqual(row["symbol"], "X.TA")
            mode = r.execute("PRAGMA journal_mode").fetchone()[0]
            r.close()
            self.assertIn(mode.lower(), {"wal", "memory"})


if __name__ == "__main__":
    unittest.main()
