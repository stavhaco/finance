from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def enqueue_enrichment_job(conn: sqlite3.Connection, knowledge_event_id: int) -> bool:
    """Queue one knowledge row for async enrichment. Returns True if newly queued."""
    now = _utc_iso()
    try:
        conn.execute(
            """
            INSERT INTO enrichment_jobs(knowledge_event_id, status, attempts, created_at, updated_at)
            VALUES(?, 'pending', 0, ?, ?)
            """,
            (int(knowledge_event_id), now, now),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        cur = conn.execute(
            """
            SELECT status FROM enrichment_jobs WHERE knowledge_event_id=?
            """,
            (int(knowledge_event_id),),
        )
        row = cur.fetchone()
        if row and str(row[0]) in {"failed", "pending"}:
            conn.execute(
                """
                UPDATE enrichment_jobs
                SET status='pending', updated_at=?
                WHERE knowledge_event_id=? AND status='failed'
                """,
                (now, int(knowledge_event_id)),
            )
            conn.commit()
        return False


def claim_pending_jobs(conn: sqlite3.Connection, *, limit: int = 5) -> list[int]:
    """Claim up to `limit` pending jobs; returns knowledge_event ids."""
    now = _utc_iso()
    cur = conn.execute(
        """
        SELECT id, knowledge_event_id
        FROM enrichment_jobs
        WHERE status='pending'
        ORDER BY id ASC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    rows = cur.fetchall()
    out: list[int] = []
    for job_id, kid in rows:
        conn.execute(
            """
            UPDATE enrichment_jobs
            SET status='processing', attempts=attempts+1, updated_at=?
            WHERE id=? AND status='pending'
            """,
            (now, int(job_id)),
        )
        if conn.total_changes:
            out.append(int(kid))
    conn.commit()
    return out


def complete_job(
    conn: sqlite3.Connection,
    knowledge_event_id: int,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    status = "done" if ok else "failed"
    conn.execute(
        """
        UPDATE enrichment_jobs
        SET status=?, last_error=?, updated_at=?
        WHERE knowledge_event_id=?
        """,
        (status, (error or "")[:500] if error else None, _utc_iso(), int(knowledge_event_id)),
    )
    conn.commit()


def pending_job_count(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM enrichment_jobs WHERE status IN ('pending', 'processing')"
    )
    return int(cur.fetchone()[0])


def enrichment_job_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    cur = conn.execute(
        """
        SELECT status, COUNT(*) AS c
        FROM enrichment_jobs
        GROUP BY status
        """
    )
    by_status = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    return {
        "pending": by_status.get("pending", 0),
        "processing": by_status.get("processing", 0),
        "done": by_status.get("done", 0),
        "failed": by_status.get("failed", 0),
    }
