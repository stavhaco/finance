from __future__ import annotations

from typing import Any, Sequence


def dry_run_decision(
    *,
    watchlist: Sequence[str],
    trading_allowed: bool,
    max_trades: int,
    min_buys_when_trading: int,
    recommendation_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Deterministic model JSON for CI / cloud agents without Ollama."""
    syms = [s for s in watchlist if s.endswith(".TA")][: max(3, max_trades)]
    if not syms:
        syms = list(watchlist)[:3]

    trade_targets: list[str] = []
    if trading_allowed and min_buys_when_trading > 0:
        trade_targets = syms[: min(len(syms), min_buys_when_trading, max_trades)]

    trades: list[dict[str, Any]] = []
    for sym in trade_targets:
        trades.append(
            {
                "symbol": sym,
                "side": "buy",
                "qty": 10,
                "why_en": "DRY_RUN: modest diversification stub without Ollama.",
                "evidence_news_ids": [],
                "evidence_quote": "",
            }
        )

    rec_list = list(recommendation_symbols) if recommendation_symbols else list(watchlist)
    recommendations: list[dict[str, Any]] = []
    for sym in rec_list:
        stance = "buy" if sym in trade_targets else "hold"
        if not trading_allowed:
            stance = "hold"
        recommendations.append(
            {
                "symbol": sym,
                "stance": stance,
                "why_en": (
                    "DRY_RUN: deployment stub when trading allowed."
                    if stance == "buy"
                    else "DRY_RUN: hold in stub mode."
                ),
                "evidence_news_ids": [],
                "evidence_quote": "",
            }
        )

    return {
        "analysis_he": "DRY_RUN: תקציר קצר בעברית ללוג מחזור.",
        "recommendations": recommendations,
        "trades": trades,
    }
