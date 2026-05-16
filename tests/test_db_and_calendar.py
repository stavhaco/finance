import os
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from demo_trader.db import init_schema, insert_cycle, insert_decision, open_db, upsert_companies
from demo_trader.tase_calendar import is_tase_regular_trading_hours, is_tase_weekday_il


class TestDb(unittest.TestCase):
    def test_init_and_cycle_decision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.db")
            conn = open_db(path, announce_migrations=False)
            init_schema(conn)
            upsert_companies(conn, [("TEVA.TA", "טבע", "Teva", "תרופות", "ערך")])
            cid = insert_cycle(
                conn,
                trading_allowed=True,
                knowledge_only=True,
                nav_ils=100_000.0,
                benchmark_symbol="TA35.TA",
                benchmark_px=1000.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                headline_count=3,
            )
            did = insert_decision(
                conn,
                cycle_id=cid,
                trading_allowed=True,
                kind="llm_summary",
                symbol=None,
                side=None,
                qty=None,
                executed=False,
                exec_price=None,
                notional_ils=None,
                reason_he="בדיקה",
                analysis_he="סיכום",
                model_json={"ok": True},
                nav_before=100_000.0,
                nav_after=100_000.0,
                benchmark_px=1000.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                broker_message=None,
            )
            self.assertGreater(cid, 0)
            self.assertGreater(did, 0)


class TestTaseCalendar(unittest.TestCase):
    def test_sunday_is_weekday_session(self) -> None:
        # 2026-05-17 is a Sunday in Asia/Jerusalem
        dt = datetime(2026, 5, 17, 10, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
        self.assertTrue(is_tase_weekday_il(dt))
        self.assertTrue(is_tase_regular_trading_hours(dt))

    def test_saturday_closed(self) -> None:
        dt = datetime(2026, 5, 16, 10, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
        self.assertFalse(is_tase_weekday_il(dt))


if __name__ == "__main__":
    unittest.main()
