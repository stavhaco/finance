import tempfile
import unittest
from pathlib import Path

from demo_trader.db import connect, init_schema, insert_knowledge_event, open_db
from demo_trader.enrichment_jobs import (
    claim_pending_jobs,
    complete_job,
    enqueue_enrichment_job,
    pending_job_count,
)
from demo_trader.schema_migrations import run_pending_migrations


class TestEnrichmentJobs(unittest.TestCase):
    def test_enqueue_claim_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            conn = connect(db)
            init_schema(conn)
            run_pending_migrations(conn)
            kid = insert_knowledge_event(
                conn,
                source="test",
                url="http://x/1",
                title="t",
                snippet=None,
                matched_symbol=None,
            )
            assert kid is not None
            self.assertTrue(enqueue_enrichment_job(conn, kid))
            self.assertFalse(enqueue_enrichment_job(conn, kid))
            self.assertEqual(pending_job_count(conn), 1)
            claimed = claim_pending_jobs(conn, limit=5)
            self.assertEqual(claimed, [kid])
            complete_job(conn, kid, ok=True)
            self.assertEqual(pending_job_count(conn), 0)


if __name__ == "__main__":
    unittest.main()
