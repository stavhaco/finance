import os
import tempfile
import unittest

from demo_trader.backfill_cycle_rationales import (
    _reason_worth_updating,
    backfill_cycle_from_payload,
)
from demo_trader.db import init_schema, insert_cycle, insert_decision, open_db


class TestBackfillCycleRationales(unittest.TestCase):
    def test_reason_worth_updating(self) -> None:
        self.assertTrue(_reason_worth_updating("מודל", "Bezeq outlook stable."))
        self.assertTrue(
            _reason_worth_updating(
                "[why_en] Old text.\n[evidence_news_ids] [1]",
                "Bezeq outlook stable.",
            )
        )
        self.assertFalse(_reason_worth_updating("Good English reason.", "Good English reason."))
        self.assertFalse(_reason_worth_updating("Good English reason.", "Short"))

    def test_backfill_updates_decisions_from_model_response(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "t.db")
            log_dir = os.path.join(d, "logs")
            os.makedirs(log_dir, exist_ok=True)

            conn = open_db(db_path, announce_migrations=False)
            init_schema(conn)
            cid = insert_cycle(
                conn,
                trading_allowed=True,
                knowledge_only=False,
                nav_ils=100_000.0,
                benchmark_symbol="TA35.TA",
                benchmark_px=1000.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                headline_count=1,
            )
            insert_decision(
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
                reason_he="summary marker",
                analysis_he="תקציר בעברית",
                model_json={},
                nav_before=100_000.0,
                nav_after=100_000.0,
                benchmark_px=1000.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                broker_message=None,
            )
            trade_id = insert_decision(
                conn,
                cycle_id=cid,
                trading_allowed=True,
                kind="trade",
                symbol="BEZQ.TA",
                side="sell",
                qty=10.0,
                executed=True,
                exec_price=5.0,
                notional_ils=50.0,
                reason_he="מודל",
                analysis_he="",
                model_json={"raw": {"symbol": "BEZQ.TA", "why_en": "unused"}},
                nav_before=100_000.0,
                nav_after=100_000.0,
                benchmark_px=1000.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                broker_message=None,
            )
            skip_id = insert_decision(
                conn,
                cycle_id=cid,
                trading_allowed=True,
                kind="skip",
                symbol="ALHE.TA",
                side="buy",
                qty=0.0,
                executed=False,
                exec_price=None,
                notional_ils=None,
                reason_he="[evidence_news_ids] [2631]",
                analysis_he="",
                model_json={},
                nav_before=100_000.0,
                nav_after=100_000.0,
                benchmark_px=1000.0,
                portfolio_return_pct=0.0,
                benchmark_return_pct=0.0,
                alpha_pct=0.0,
                broker_message="outside_tase_window",
            )

            model_response = {
                "analysis_he": "",
                "recommendations": [
                    {
                        "symbol": "BEZQ.TA",
                        "stance": "sell",
                        "why_en": "Bezeq dividend outlook remains stable.",
                    },
                    {
                        "symbol": "ALHE.TA",
                        "stance": "hold",
                        "why_en": "El Al load factor improved on recent routes.",
                        "evidence_news_ids": [2631],
                    },
                ],
                "trades": [
                    {
                        "symbol": "BEZQ.TA",
                        "side": "sell",
                        "qty": 10,
                        "why_en": "Bezeq dividend outlook remains stable.",
                    }
                ],
            }
            reason_n, analysis_n = backfill_cycle_from_payload(
                conn, cycle_id=cid, model_response=model_response, dry_run=False
            )
            self.assertEqual(reason_n, 2)
            self.assertEqual(analysis_n, 1)

            trade_row = conn.execute(
                "SELECT reason_he FROM decisions WHERE id=?", (trade_id,)
            ).fetchone()
            skip_row = conn.execute("SELECT reason_he FROM decisions WHERE id=?", (skip_id,)).fetchone()
            summary_row = conn.execute(
                "SELECT analysis_he FROM decisions WHERE kind='llm_summary' AND cycle_id=?", (cid,)
            ).fetchone()

            self.assertIn("Bezeq", str(trade_row["reason_he"]))
            self.assertIn("El Al", str(skip_row["reason_he"]))
            self.assertIn("BEZQ.TA", str(summary_row["analysis_he"]))


if __name__ == "__main__":
    unittest.main()
