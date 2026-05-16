from __future__ import annotations

from dataclasses import dataclass

from demo_trader.paper_broker import portfolio_nav
from demo_trader.state_store import PaperState, SessionSnapshot, _utc_now_iso


@dataclass(frozen=True)
class Performance:
    nav_ils: float
    portfolio_return_pct: float | None
    benchmark_return_pct: float | None
    alpha_vs_benchmark_pct: float | None


def ensure_session(
    state: PaperState,
    *,
    benchmark_symbol: str,
    benchmark_px: float,
    prices: dict[str, float],
) -> None:
    if state.session:
        return
    nav = portfolio_nav(state, prices)
    state.session = SessionSnapshot(
        started_ts=_utc_now_iso(),
        benchmark_symbol=benchmark_symbol,
        benchmark_start_px=float(benchmark_px),
        initial_nav_ils=float(nav),
    )


def compute_performance(state: PaperState, *, prices: dict[str, float], benchmark_last: float) -> Performance:
    nav = portfolio_nav(state, prices)
    sess = state.session
    if not sess or sess.initial_nav_ils <= 0 or sess.benchmark_start_px <= 0:
        return Performance(
            nav_ils=nav,
            portfolio_return_pct=None,
            benchmark_return_pct=None,
            alpha_vs_benchmark_pct=None,
        )
    port_ret = (nav / sess.initial_nav_ils - 1.0) * 100.0
    bench_ret = (float(benchmark_last) / sess.benchmark_start_px - 1.0) * 100.0
    alpha = port_ret - bench_ret
    return Performance(
        nav_ils=nav,
        portfolio_return_pct=port_ret,
        benchmark_return_pct=bench_ret,
        alpha_vs_benchmark_pct=alpha,
    )
