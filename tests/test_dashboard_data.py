"""Tests for dashboard data helpers."""

from demo_trader.dashboard.data import (
    gather_inspect_cited_news_event_ids,
    sanitize_hebrew_rationale,
)


def test_sanitize_hebrew_strips_stray_scripts() -> None:
    messy = "הסבר μבדיקת κטקסט"  # Greek letters should go
    out = sanitize_hebrew_rationale(messy)
    assert "μ" not in out
    assert "κ" not in out
    assert "הסבר" in out


def test_gather_inspect_collects_trade_citations_and_dedupes() -> None:
    log_payload = {
        "model_response": {
            "trades": [
                {"symbol": "X.TA", "cited_news_event_ids": [3, 2]},
                {"symbol": "Y.TA", "evidence_news_ids": ["2"]},
            ]
        }
    }
    decisions = [
        {
            "model_json": {"raw": {"based_on_news_event_ids": [5]}},
        }
    ]
    ids = gather_inspect_cited_news_event_ids(log_payload, decisions)
    assert ids == [2, 3, 5]
