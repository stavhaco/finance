from __future__ import annotations

from typing import Any, Sequence


def dry_run_decision(
    *,
    watchlist: Sequence[str],
    trading_allowed: bool,
    max_trades: int,
    min_buys_when_trading: int,
) -> dict[str, Any]:
    """Deterministic model JSON for CI / cloud agents without Ollama."""
    syms = [s for s in watchlist if s.endswith(".TA")][: max(3, max_trades)]
    if not syms:
        syms = list(watchlist)[:3]

    by_symbol = [
        {
            "symbol": sym,
            "stance": "buy",
            "buy_lo": None,
            "buy_hi": None,
            "sell_lo": None,
            "sell_hi": None,
            "rationale_he": "DRY_RUN: בדיקת צינור — החזקת מזומן נמוכה, קנייה מתונה.",
        }
        for sym in syms
    ]

    trades: list[dict[str, Any]] = []
    if trading_allowed and min_buys_when_trading > 0:
        for sym in syms[: min(len(syms), min_buys_when_trading, max_trades)]:
            trades.append(
                {
                    "symbol": sym,
                    "side": "buy",
                    "qty": 10,
                    "reason_he": "DRY_RUN: פריסת הון מתונה (ללא Ollama).",
                }
            )

    return {
        "analysis_he": "DRY_RUN: מחזור בדיקה — ללא קריאה ל-Ollama. מטרה: אימות ingest, מחירים, ביצוע עסקאות ולוג מחזור.",
        "by_symbol": by_symbol,
        "trades": trades,
    }
