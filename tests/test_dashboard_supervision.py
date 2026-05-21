import json
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace

from demo_trader.config import Config
from demo_trader.dashboard import data as dash_data


class TestCycleLogFilename(unittest.TestCase):
    def test_parse_cycle_id(self) -> None:
        self.assertEqual(dash_data._cycle_id_from_log_filename("cycle_00012_2026-05-19T10-30-00.json"), 12)
        self.assertEqual(dash_data._cycle_id_from_log_filename("other.json"), 0)


class TestSupervisionData(unittest.TestCase):
    def test_overview_and_cycle_log_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "t.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE companies (symbol TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO companies VALUES ('X.TA')")
            conn.commit()
            conn.close()

            log_dir = os.path.join(d, "logs")
            os.makedirs(log_dir, exist_ok=True)
            payload = {
                "cycle_id": 7,
                "ingest": {"rss_headlines": 2},
                "prompt": {
                    "sections": {
                        "system": {"preview": "sys", "chars": 3, "full": "SECRET"},
                        "user": "plain user",
                    }
                },
                "model_response": {"analysis_he": "ok"},
            }
            fn = os.path.join(log_dir, "cycle_00007_test.json")
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            cfg = replace(
                Config(),
                db_path=db_path,
                state_path=os.path.join(d, "missing_state.json"),
                cycle_log_dir=log_dir,
            )
            ov = dash_data.load_supervision_overview(cfg, cycle_log_limit=10)
            self.assertEqual(ov["paths"]["db"]["exists"], True)
            self.assertEqual(ov["paths"]["state"]["exists"], False)
            self.assertEqual(len(ov["cycle_logs"]), 1)
            self.assertEqual(ov["cycle_logs"][0]["cycle_id"], 7)

            stripped = dash_data.load_cycle_log_payload(cfg, 7, strip_full_prompts=True)
            assert stripped is not None
            sec = stripped["prompt"]["sections"]["system"]
            self.assertNotIn("full", sec)
            self.assertEqual(sec.get("preview"), "sys")

            full = dash_data.load_cycle_log_payload(cfg, 7, strip_full_prompts=False)
            assert full is not None
            self.assertEqual(full["prompt"]["sections"]["system"].get("full"), "SECRET")


if __name__ == "__main__":
    unittest.main()
