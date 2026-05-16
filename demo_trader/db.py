from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            symbol TEXT PRIMARY KEY,
            name_he TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sector_he TEXT NOT NULL,
            category_he TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            snippet TEXT,
            matched_symbol TEXT,
            UNIQUE(url, title)
        );

        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            trading_allowed INTEGER NOT NULL,
            knowledge_only INTEGER NOT NULL,
            nav_ils REAL,
            benchmark_symbol TEXT,
            benchmark_px REAL,
            portfolio_return_pct REAL,
            benchmark_return_pct REAL,
            alpha_pct REAL,
            headline_count INTEGER
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            trading_allowed INTEGER NOT NULL,
            kind TEXT NOT NULL, -- trade|hold|blocked_after_hours|ollama_error|skip
            symbol TEXT,
            side TEXT,
            qty REAL,
            executed INTEGER NOT NULL DEFAULT 0,
            exec_price REAL,
            notional_ils REAL,
            reason_he TEXT,
            analysis_he TEXT,
            model_json TEXT,
            nav_before REAL,
            nav_after REAL,
            benchmark_px REAL,
            portfolio_return_pct REAL,
            benchmark_return_pct REAL,
            alpha_pct REAL,
            broker_message TEXT,
            outcome_updated INTEGER NOT NULL DEFAULT 0,
            outcome_mtm_ils REAL,
            outcome_benchmark_px REAL,
            outcome_ts TEXT,
            FOREIGN KEY(cycle_id) REFERENCES cycles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_ts ON knowledge_events(ts DESC);
        CREATE INDEX IF NOT EXISTS idx_knowledge_sym ON knowledge_events(matched_symbol);
        CREATE INDEX IF NOT EXISTS idx_decisions_cycle ON decisions(cycle_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts DESC);
        """
    )
    conn.commit()


_COMPANY_FUNDAMENTAL_COLS: tuple[tuple[str, str], ...] = (
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


def ensure_company_fundamentals_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(companies)")
    have = {str(r[1]) for r in cur.fetchall()}
    for col, typ in _COMPANY_FUNDAMENTAL_COLS:
        if col not in have:
            conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typ}")
    conn.commit()


def upsert_companies(conn: sqlite3.Connection, rows: Iterable[tuple[str, str, str, str, str]]) -> None:
    conn.executemany(
        """
        INSERT INTO companies(symbol, name_he, name_en, sector_he, category_he)
        VALUES(?,?,?,?,?)
        ON CONFLICT(symbol) DO UPDATE SET
            name_he=excluded.name_he,
            name_en=excluded.name_en,
            sector_he=excluded.sector_he,
            category_he=excluded.category_he
        """,
        list(rows),
    )
    conn.commit()


def insert_knowledge_event(
    conn: sqlite3.Connection,
    *,
    source: str,
    url: str,
    title: str,
    snippet: str | None,
    matched_symbol: str | None,
) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO knowledge_events(ts, source, url, title, snippet, matched_symbol)
            VALUES(?,?,?,?,?,?)
            """,
            (_utc_iso(), source, url, title, snippet, matched_symbol),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def update_company_fundamentals(conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
    sym = str(stats.get("symbol") or "").strip()
    if not sym:
        return
    now = _utc_iso()
    conn.execute(
        """
        UPDATE companies SET
            last_price=?,
            currency=?,
            market_cap=?,
            enterprise_value=?,
            trailing_pe=?,
            forward_pe=?,
            price_to_book=?,
            beta=?,
            fifty_two_week_high=?,
            fifty_two_week_low=?,
            return_ytd_pct=?,
            return_1q_pct=?,
            return_1y_pct=?,
            avg_volume_10d=?,
            fundamentals_updated_ts=?
        WHERE symbol=?
        """,
        (
            stats.get("last_price"),
            stats.get("currency"),
            stats.get("market_cap"),
            stats.get("enterprise_value"),
            stats.get("trailing_pe"),
            stats.get("forward_pe"),
            stats.get("price_to_book"),
            stats.get("beta"),
            stats.get("fifty_two_week_high"),
            stats.get("fifty_two_week_low"),
            stats.get("return_ytd_pct"),
            stats.get("return_1q_pct"),
            stats.get("return_1y_pct"),
            stats.get("avg_volume_10d"),
            now,
            sym,
        ),
    )
    conn.commit()


def companies_fundamentals_digest(conn: sqlite3.Connection, symbols: Iterable[str]) -> str:
    syms = list(dict.fromkeys([s for s in symbols if s]))
    if not syms:
        return "(אין סימולים לנתוני סטטיסטיקה)"
    placeholders = ",".join(["?"] * len(syms))
    cur = conn.execute(
        f"""
        SELECT symbol, name_he, last_price, currency, market_cap, trailing_pe, price_to_book,
               return_ytd_pct, return_1q_pct, return_1y_pct, fifty_two_week_low, fifty_two_week_high,
               fundamentals_updated_ts
        FROM companies
        WHERE symbol IN ({placeholders})
        ORDER BY symbol
        """,
        syms,
    )
    lines: list[str] = ["נתוני שוק (Yahoo Finance; עשויים להיות בעיכוב או שגויים):", ""]
    for r in cur.fetchall():
        lines.append(
            f"- {r['symbol']} ({r['name_he']}): מחיר={r['last_price']} {r['currency'] or ''}; "
            f"שווי שוק~{r['market_cap']}; P/E טריילינג~{r['trailing_pe']}; P/B~{r['price_to_book']}; "
            f"תשואה שנתית~{r['return_1y_pct']}% תלת־חודשית~{r['return_1q_pct']}% YTD~{r['return_ytd_pct']}% ; "
            f"52שבוע נמוך/גבוה={r['fifty_two_week_low']}/{r['fifty_two_week_high']} ; עדכון={r['fundamentals_updated_ts']}"
        )
    return "\n".join(lines)


def recent_knowledge_for_prompt(conn: sqlite3.Connection, *, limit: int = 60) -> str:
    cur = conn.execute(
        """
        SELECT ts, source, matched_symbol, title
        FROM knowledge_events
        ORDER BY datetime(ts) DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    if not rows:
        return "(אין עדיין אירועי ידע שנשמרו במסד)"
    lines: list[str] = []
    for r in rows:
        sym = r["matched_symbol"] or "—"
        lines.append(f"- [{r['ts']}] {r['source']} | {sym} | {r['title']}")
    return "אירועי ידע אחרונים מהרצות קודמות (ממוין מהחדש לישן):\n" + "\n".join(lines)


def insert_cycle(
    conn: sqlite3.Connection,
    *,
    trading_allowed: bool,
    knowledge_only: bool,
    nav_ils: float | None,
    benchmark_symbol: str,
    benchmark_px: float | None,
    portfolio_return_pct: float | None,
    benchmark_return_pct: float | None,
    alpha_pct: float | None,
    headline_count: int,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO cycles(
            ts, trading_allowed, knowledge_only, nav_ils, benchmark_symbol, benchmark_px,
            portfolio_return_pct, benchmark_return_pct, alpha_pct, headline_count
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            _utc_iso(),
            int(trading_allowed),
            int(knowledge_only),
            nav_ils,
            benchmark_symbol,
            benchmark_px,
            portfolio_return_pct,
            benchmark_return_pct,
            alpha_pct,
            headline_count,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_decision(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    trading_allowed: bool,
    kind: str,
    symbol: str | None,
    side: str | None,
    qty: float | None,
    executed: bool,
    exec_price: float | None,
    notional_ils: float | None,
    reason_he: str,
    analysis_he: str,
    model_json: dict[str, Any] | None,
    nav_before: float | None,
    nav_after: float | None,
    benchmark_px: float | None,
    portfolio_return_pct: float | None,
    benchmark_return_pct: float | None,
    alpha_pct: float | None,
    broker_message: str | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO decisions(
            cycle_id, ts, trading_allowed, kind, symbol, side, qty, executed,
            exec_price, notional_ils, reason_he, analysis_he, model_json,
            nav_before, nav_after, benchmark_px, portfolio_return_pct, benchmark_return_pct, alpha_pct,
            broker_message
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            cycle_id,
            _utc_iso(),
            int(trading_allowed),
            kind,
            symbol,
            side,
            qty,
            int(executed),
            exec_price,
            notional_ils,
            reason_he,
            analysis_he,
            json.dumps(model_json, ensure_ascii=False) if model_json is not None else None,
            nav_before,
            nav_after,
            benchmark_px,
            portfolio_return_pct,
            benchmark_return_pct,
            alpha_pct,
            broker_message,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def finalize_open_trade_outcomes(
    conn: sqlite3.Connection,
    *,
    prices: dict[str, float],
    benchmark_px: float,
) -> int:
    """Mark-to-market for executed trades that have not been marked yet."""
    cur = conn.execute(
        """
        SELECT id, symbol, side, qty, exec_price
        FROM decisions
        WHERE executed = 1 AND kind = 'trade' AND exec_price IS NOT NULL AND qty IS NOT NULL
        """
    )
    rows = cur.fetchall()
    updated = 0
    now = _utc_iso()
    for r in rows:
        sym = str(r["symbol"])
        side = str(r["side"] or "").lower()
        qty = float(r["qty"] or 0.0)
        exec_px = float(r["exec_price"] or 0.0)
        px = float(prices.get(sym, 0.0) or 0.0)
        if px <= 0 or qty <= 0 or exec_px <= 0:
            continue
        if side == "buy":
            mtm = qty * (px - exec_px)
        elif side == "sell":
            mtm = qty * (exec_px - px)
        else:
            continue
        conn.execute(
            """
            UPDATE decisions
            SET outcome_updated = 1,
                outcome_mtm_ils = ?,
                outcome_benchmark_px = ?,
                outcome_ts = ?
            WHERE id = ?
            """,
            (mtm, benchmark_px, now, int(r["id"])),
        )
        updated += 1
    conn.commit()
    return updated

def open_db(db_path: str) -> sqlite3.Connection:
    conn = connect(db_path)
    init_schema(conn)
    ensure_company_fundamentals_columns(conn)
    return conn
