from demo_trader.db import _markdown_cell, trader_knowledge_digest_en


def test_markdown_cell_escapes_pipes_and_newlines() -> None:
    out = _markdown_cell("line1\nline2 | pipe", max_len=200)
    assert "\n" not in out
    assert "|" not in out or "\\|" in out


def test_trader_knowledge_digest_en_empty_db() -> None:
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE knowledge_events (
            id INTEGER PRIMARY KEY,
            ts TEXT, event_time TEXT, source TEXT, matched_symbol TEXT,
            title_en TEXT, body_translation_en TEXT, executive_summary_en TEXT,
            sentiment TEXT, trade_usefulness TEXT, enrichment_status TEXT
        );
        """
    )
    text = trader_knowledge_digest_en(conn, benchmark_symbol="TA35.TA", limit=5)
    assert "No enriched" in text


def test_trader_knowledge_digest_en_renders_table_row() -> None:
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE knowledge_events (
            id INTEGER PRIMARY KEY,
            ts TEXT, event_time TEXT, source TEXT, matched_symbol TEXT,
            title_en TEXT, body_translation_en TEXT, executive_summary_en TEXT,
            sentiment TEXT, trade_usefulness TEXT, enrichment_status TEXT
        );
        INSERT INTO knowledge_events VALUES (
            1, '2026-05-28T12:00:00+00:00', '2026-05-28T12:00:00+00:00',
            'globes', 'TEVA.TA', 'Title | pipe', 'Body line1\nline2', 'Summary', 'neutral', 'high', 'ok'
        );
        """
    )
    text = trader_knowledge_digest_en(conn, benchmark_symbol="TA35.TA", limit=5)
    assert "| 1 |" in text
    assert "Title" in text
    assert "Summary" in text
