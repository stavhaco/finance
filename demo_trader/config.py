from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence

from demo_trader.ta35_catalog import ta35_symbols


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_opt_str(key: str) -> str | None:
    raw = os.environ.get(key)
    if raw is None:
        return None
    s = raw.strip()
    return s if s else None


def _parse_symbols(raw: str) -> tuple[str, ...]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return tuple(p for p in parts if p)


@dataclass(frozen=True)
class Config:
    """Runtime configuration; env vars override defaults."""

    ollama_base_url: str = field(default_factory=lambda: _env_str("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    ollama_model: str = field(default_factory=lambda: _env_str("OLLAMA_MODEL", "llama3.2"))
    interval_minutes: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_INTERVAL_MINUTES", 15)))
    starting_cash_ils: float = field(default_factory=lambda: max(1000.0, _env_float("DEMO_TRADER_STARTING_CASH_ILS", 100_000.0)))
    state_path: str = field(default_factory=lambda: _env_str("DEMO_TRADER_STATE_PATH", "data/paper_state.json"))
    db_path: str = field(default_factory=lambda: _env_str("DEMO_TRADER_DB_PATH", "data/trader.db"))
    slippage_bps: float = field(default_factory=lambda: max(0.0, _env_float("DEMO_TRADER_SLIPPAGE_BPS", 5.0)))
    benchmark_symbol: str = field(default_factory=lambda: _env_str("DEMO_TRADER_BENCHMARK", "TA35.TA"))
    watchlist: tuple[str, ...] = field(
        default_factory=lambda: _parse_symbols(
            _env_str(
                "DEMO_TRADER_WATCHLIST",
                ",".join(ta35_symbols()),
            )
        )
    )
    max_trades_per_cycle: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_MAX_TRADES_PER_CYCLE", 3)))
    max_position_pct: float = field(
        default_factory=lambda: min(100.0, max(1.0, _env_float("DEMO_TRADER_MAX_POSITION_PCT", 25.0)))
    )
    news_max_headlines: int = field(default_factory=lambda: max(5, _env_int("DEMO_TRADER_NEWS_MAX", 60)))
    ollama_timeout_sec: int = field(default_factory=lambda: max(30, _env_int("DEMO_TRADER_OLLAMA_TIMEOUT_SEC", 240)))
    knowledge_prompt_rows: int = field(default_factory=lambda: max(10, _env_int("DEMO_TRADER_KNOWLEDGE_DB_ROWS", 80)))
    maya_lookback_days: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_MAYA_LOOKBACK_DAYS", 5)))
    maya_breaking_limit: int = field(default_factory=lambda: max(5, _env_int("DEMO_TRADER_MAYA_BREAKING_LIMIT", 80)))
    maya_post_max_keep: int = field(default_factory=lambda: max(10, _env_int("DEMO_TRADER_MAYA_POST_MAX_KEEP", 150)))
    maya_http_timeout_sec: int = field(default_factory=lambda: max(15, _env_int("DEMO_TRADER_MAYA_HTTP_TIMEOUT_SEC", 60)))
    enforce_tase_hours: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_ENFORCE_TASE_HOURS", True)
    )
    simulation: bool = field(default_factory=lambda: _env_bool("DEMO_TRADER_SIMULATION", False))
    sim_step_minutes: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_SIM_STEP_MINUTES", 15)))
    sim_start_days_ago: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_SIM_START_DAYS_AGO", 7)))
    sim_start_iso: str | None = field(default_factory=lambda: _env_opt_str("DEMO_TRADER_SIM_START_ISO"))
    price_bar_interval: str = field(default_factory=lambda: _env_str("DEMO_TRADER_PRICE_BAR_INTERVAL", "5m"))
    price_history_days: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_PRICE_HISTORY_DAYS", 30)))
    sim_ingest_live: bool = field(default_factory=lambda: _env_bool("DEMO_TRADER_SIM_INGEST_LIVE", True))
    sim_skip_closed_hours: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_SIM_SKIP_CLOSED_HOURS", True)
    )

    def rss_feeds(self) -> Sequence[str]:
        raw = _env_str(
            "DEMO_TRADER_RSS_FEEDS",
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=607,"
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=945,"
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585,"
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=572,"
            "https://www.calcalist.co.il/GeneralRSS/0,,L-5619,00.xml",
        )
        return tuple(u.strip() for u in raw.split(",") if u.strip())
