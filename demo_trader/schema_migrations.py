from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# Bump when adding a new migration at the bottom of MIGRATIONS.
EXPECTED_LATEST_VERSION: int = 3


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    cur = conn.execute("SELECT version FROM schema_migrations")
    return {int(r[0]) for r in cur.fetchall()}


def record_migration(conn: sqlite3.Connection, version: int, name: str) -> None:
    conn.execute(
        """
        INSERT INTO schema_migrations(version, name, applied_at)
        VALUES(?,?,?)
        """,
        (version, name, _utc_iso()),
    )
    conn.commit()


COMPANY_FUNDAMENTAL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("last_price", "REAL"),
    ("currency", "TEXT"),
    ("market_cap", "REAL"),
    ("enterprise_value", "REAL"),
    ("trailing_pe", "REAL"),
    ("forward_pe", "REAL"),
    ("price_to_book", "REAL"),
    ("beta", "REAL"),
    ("fifty_two_week_high", "REAL"),
    ("fifty_two_week_low", "REAL"),
    ("return_ytd_pct", "REAL"),
    ("return_1q_pct", "REAL"),
    ("return_1y_pct", "REAL"),
    ("avg_volume_10d", "REAL"),
    ("fundamentals_updated_ts", "TEXT"),
)




def _upgrade_002_simulation_bars_and_event_times(conn: sqlite3.Connection) -> None:
    """Simulation support: intraday bars, app_kv, and knowledge_events.event_time."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_bars (
            symbol TEXT NOT NULL,
            bar_start TEXT NOT NULL,
            interval TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, bar_start, interval)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_price_bars_lookup ON price_bars(symbol, interval, bar_start);"
    )
    cur = conn.execute("PRAGMA table_info(knowledge_events)")
    have = {str(r[1]) for r in cur.fetchall()}
    if "event_time" not in have:
        conn.execute("ALTER TABLE knowledge_events ADD COLUMN event_time TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_events_event_time ON knowledge_events(event_time);")
    conn.commit()

def _upgrade_003_knowledge_enrichment(conn: sqlite3.Connection) -> None:
    """English enrichment fields for knowledge_events (translate/summary/sentiment)."""
    cur = conn.execute("PRAGMA table_info(knowledge_events)")
    have = {str(r[1]) for r in cur.fetchall()}
    additions: tuple[tuple[str, str], ...] = (
        ("title_en", "TEXT"),
        ("body_translation_en", "TEXT"),
        ("executive_summary_en", "TEXT"),
        ("sentiment", "TEXT"),
        ("trade_usefulness", "TEXT"),
        ("is_broad_market", "INTEGER NOT NULL DEFAULT 0"),
        ("enrichment_status", "TEXT"),
        ("enrichment_error", "TEXT"),
        ("enriched_at", "TEXT"),
    )
    for col, typ in additions:
        if col in have:
            continue
        conn.execute(f"ALTER TABLE knowledge_events ADD COLUMN {col} {typ}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_enrich_status ON knowledge_events(enrichment_status);"
    )
    conn.commit()

def _upgrade_001_company_fundamentals(conn: sqlite3.Connection) -> None:
    """Add Yahoo/fundamental analytics columns to `companies` (idempotent per column)."""
    cur = conn.execute("PRAGMA table_info(companies)")
    have = {str(r[1]) for r in cur.fetchall()}
    for col, typ in COMPANY_FUNDAMENTAL_COLUMNS:
        if col in have:
            continue
        conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typ}")
        logger.info("Migration 001: added companies.%s %s", col, typ)


MigrationFn = Callable[[sqlite3.Connection], None]

MIGRATIONS: Sequence[tuple[int, str, MigrationFn]] = (
    (1, "001_company_fundamentals", _upgrade_001_company_fundamentals),
    (2, "002_simulation_bars_and_event_times", _upgrade_002_simulation_bars_and_event_times),
    (3, "003_knowledge_enrichment", _upgrade_003_knowledge_enrichment),
)


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of `run_pending_migrations`."""

    applied: tuple[str, ...]
    pending_before: int
    latest_version: int


def run_pending_migrations(conn: sqlite3.Connection) -> MigrationResult:
    """Apply any migrations not yet recorded in `schema_migrations`."""
    ensure_migrations_table(conn)
    done = applied_versions(conn)
    pending = [m for m in MIGRATIONS if m[0] not in done]
    applied_names: list[str] = []

    if not pending:
        latest = max(done) if done else 0
        if latest > EXPECTED_LATEST_VERSION:
            logger.warning(
                "Database schema is newer than this build (db v%s > expected v%s). "
                "Downgrade the database or upgrade the app.",
                latest,
                EXPECTED_LATEST_VERSION,
            )
        elif latest < EXPECTED_LATEST_VERSION:
            logger.error(
                "Database schema is behind but no pending migrations are registered "
                "(db v%s < expected v%s). Check schema_migrations.MIGRATIONS.",
                latest,
                EXPECTED_LATEST_VERSION,
            )
        else:
            logger.debug("Schema up to date: no pending migrations (version=%s).", latest)
        return MigrationResult(applied=tuple(), pending_before=0, latest_version=latest)

    logger.info("Applying %s pending database migration(s)...", len(pending))

    for version, name, upgrade in pending:
        logger.info("Running migration %s: %s", version, name)
        try:
            upgrade(conn)
        except Exception:
            logger.exception("Migration %s (%s) failed", version, name)
            raise
        record_migration(conn, version, name)
        applied_names.append(name)

    latest = max(applied_versions(conn))
    if latest != EXPECTED_LATEST_VERSION:
        logger.warning(
            "After migrations, latest_version=%s but EXPECTED_LATEST_VERSION=%s.",
            latest,
            EXPECTED_LATEST_VERSION,
        )
    logger.info("Migrations finished: applied=%s newest_version=%s", applied_names, latest)
    return MigrationResult(
        applied=tuple(applied_names),
        pending_before=len(pending),
        latest_version=latest,
    )

_mig_max = max(v for v, _, _ in MIGRATIONS)
if _mig_max != EXPECTED_LATEST_VERSION:
    raise RuntimeError(
        f"schema_migrations.MIGRATIONS max version {_mig_max} "
        f"!= EXPECTED_LATEST_VERSION {EXPECTED_LATEST_VERSION}"
    )

