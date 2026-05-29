from __future__ import annotations

from collections.abc import Mapping, Sequence


def prompt_focus_symbols(
    watchlist: Sequence[str],
    positions: Mapping[str, float],
    *,
    max_symbols: int,
) -> tuple[str, ...]:
    """Symbols that need full LLM recommendations (positions first, then watchlist order)."""
    cap = max(1, int(max_symbols))
    held = [s for s in watchlist if float(positions.get(s, 0) or 0) > 0]
    rest = [s for s in watchlist if s not in held]
    ordered = list(dict.fromkeys([*held, *rest]))
    return tuple(ordered[:cap])
