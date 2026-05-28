from demo_trader.dashboard.data import _tighten_spaced_hebrew, format_action_display


def test_tighten_hebrew_does_not_eat_newlines() -> None:
    s = "מודל\n\nהיערכות והנמקה"
    out = _tighten_spaced_hebrew(s)
    assert "\n" in out
    assert "מודל" in out


def test_format_action_display_parses_legacy_tags() -> None:
    raw = "[why_en] Bezeq dividend outlook stable.\n[evidence_news_ids] [2631]"
    disp = format_action_display(raw, symbol="BEZQ.TA", by_sym_hints={})
    assert "Bezeq" in disp["display_en"]
    assert "[evidence" not in disp["display_en"]


def test_format_action_display_uses_hint_for_placeholder() -> None:
    disp = format_action_display("מודל", symbol="ALHE.TA", by_sym_hints={"ALHE.TA": "El Al load factor improved."})
    assert "El Al" in disp["display_en"]


def test_format_action_display_ids_only() -> None:
    disp = format_action_display("[evidence_news_ids] [2631]", symbol="AZRG.TA", by_sym_hints={})
    assert disp["display_note"] or disp["display_en"] or "2631" in disp["display_text"]
