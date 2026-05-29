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


def _enrich_url_host_suffixes() -> tuple[str, ...] | None:
    raw = os.environ.get("DEMO_TRADER_ENRICH_URL_HOST_SUFFIXES")
    if raw is None:
        return (
            "globes.co.il",
            "calcalist.co.il",
            "themarker.co.il",
            "bizportal.co.il",
            "maya.tase.co.il",
        )
    s = raw.strip()
    if s == "" or s == "*":
        return None
    return tuple(x.strip().lower().lstrip(".") for x in s.split(",") if x.strip())


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
    max_trades_per_cycle: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_MAX_TRADES_PER_CYCLE", 5)))
    max_cash_pct_target: float = field(
        default_factory=lambda: min(50.0, max(5.0, _env_float("DEMO_TRADER_MAX_CASH_PCT_TARGET", 15.0)))
    )
    min_buys_when_trading: int = field(default_factory=lambda: max(0, _env_int("DEMO_TRADER_MIN_BUYS_WHEN_TRADING", 1)))
    max_position_pct: float = field(
        default_factory=lambda: min(100.0, max(1.0, _env_float("DEMO_TRADER_MAX_POSITION_PCT", 25.0)))
    )
    news_max_headlines: int = field(default_factory=lambda: max(5, _env_int("DEMO_TRADER_NEWS_MAX", 60)))
    ollama_timeout_sec: int = field(default_factory=lambda: max(30, _env_int("DEMO_TRADER_OLLAMA_TIMEOUT_SEC", 240)))
    knowledge_prompt_rows: int = field(default_factory=lambda: max(10, _env_int("DEMO_TRADER_KNOWLEDGE_DB_ROWS", 80)))
    maya_enabled: bool = field(default_factory=lambda: _env_bool("DEMO_TRADER_MAYA_ENABLED", True))
    maya_lookback_days: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_MAYA_LOOKBACK_DAYS", 5)))
    maya_breaking_limit: int = field(default_factory=lambda: max(5, _env_int("DEMO_TRADER_MAYA_BREAKING_LIMIT", 80)))
    maya_post_max_keep: int = field(default_factory=lambda: max(10, _env_int("DEMO_TRADER_MAYA_POST_MAX_KEEP", 150)))
    maya_http_connect_timeout_sec: int = field(
        default_factory=lambda: max(3, _env_int("DEMO_TRADER_MAYA_HTTP_CONNECT_TIMEOUT_SEC", 10))
    )
    maya_http_read_timeout_sec: int = field(
        default_factory=lambda: max(
            5,
            _env_int(
                "DEMO_TRADER_MAYA_HTTP_READ_TIMEOUT_SEC",
                _env_int("DEMO_TRADER_MAYA_HTTP_TIMEOUT_SEC", 25),
            ),
        )
    )
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
    enrich_article_urls: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_ENRICH_ARTICLE_URLS", False)
    )
    enrich_max_articles: int = field(default_factory=lambda: max(1, _env_int("DEMO_TRADER_ENRICH_MAX_ARTICLES", 4)))
    enrich_max_bytes: int = field(default_factory=lambda: max(50_000, _env_int("DEMO_TRADER_ENRICH_MAX_BYTES", 1_500_000)))
    enrich_max_chars_per_article: int = field(
        default_factory=lambda: max(500, _env_int("DEMO_TRADER_ENRICH_MAX_CHARS", 5000))
    )
    enrich_fetch_timeout_sec: int = field(default_factory=lambda: max(5, _env_int("DEMO_TRADER_ENRICH_FETCH_TIMEOUT_SEC", 25)))
    enrich_translate_timeout_sec: int = field(
        default_factory=lambda: max(30, _env_int("DEMO_TRADER_ENRICH_TRANSLATE_TIMEOUT_SEC", 180))
    )
    enrich_translate_max_input_chars: int = field(
        default_factory=lambda: max(500, _env_int("DEMO_TRADER_ENRICH_TRANSLATE_MAX_INPUT_CHARS", 10_000))
    )
    ollama_translate_model: str | None = field(default_factory=lambda: _env_opt_str("DEMO_TRADER_OLLAMA_TRANSLATE_MODEL"))
    knowledge_enrich_on_ingest: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST", True)
    )
    knowledge_enrich_async: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_KNOWLEDGE_ENRICH_ASYNC", True)
    )
    knowledge_enrich_fetch_body: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_KNOWLEDGE_ENRICH_FETCH_BODY", True)
    )
    ollama_enrichment_model: str | None = field(default_factory=lambda: _env_opt_str("DEMO_TRADER_OLLAMA_ENRICHMENT_MODEL"))
    knowledge_enrich_timeout_sec: int = field(
        default_factory=lambda: max(60, _env_int("DEMO_TRADER_KNOWLEDGE_ENRICH_TIMEOUT_SEC", 300))
    )
    knowledge_enrich_max_body_chars: int = field(
        default_factory=lambda: max(2000, _env_int("DEMO_TRADER_KNOWLEDGE_ENRICH_MAX_BODY_CHARS", 14_000))
    )
    knowledge_trader_digest_limit: int = field(
        default_factory=lambda: max(5, _env_int("DEMO_TRADER_KNOWLEDGE_TRADER_DIGEST_LIMIT", 40))
    )
    knowledge_trader_digest_excerpt_chars: int = field(
        default_factory=lambda: max(200, _env_int("DEMO_TRADER_KNOWLEDGE_DIGEST_EXCERPT_CHARS", 600))
    )

    enrich_url_host_suffixes: tuple[str, ...] | None = field(default_factory=_enrich_url_host_suffixes)

    sim_skip_closed_hours: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_SIM_SKIP_CLOSED_HOURS", True)
    )
    cycle_log_enabled: bool = field(default_factory=lambda: _env_bool("DEMO_TRADER_CYCLE_LOG_ENABLED", True))
    cycle_log_dir: str = field(default_factory=lambda: _env_str("DEMO_TRADER_CYCLE_LOG_DIR", "data/logs/cycles"))
    cycle_log_full_prompts: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_CYCLE_LOG_FULL_PROMPTS", False)
    )
    prompt_version: str = field(
        default_factory=lambda: _env_str("DEMO_TRADER_PROMPT_VERSION", "v2-slim")
    )
    prompt_slim_recommendations: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_PROMPT_SLIM_RECOMMENDATIONS", True)
    )
    prompt_focus_max_symbols: int = field(
        default_factory=lambda: max(5, _env_int("DEMO_TRADER_PROMPT_FOCUS_MAX_SYMBOLS", 18))
    )
    skip_cycle_without_high_news: bool = field(
        default_factory=lambda: _env_bool("DEMO_TRADER_SKIP_CYCLE_WITHOUT_HIGH_NEWS", False)
    )
    high_news_lookback_hours: int = field(
        default_factory=lambda: max(1, _env_int("DEMO_TRADER_HIGH_NEWS_LOOKBACK_HOURS", 24))
    )
    dry_run: bool = field(default_factory=lambda: _env_bool("DEMO_TRADER_DRY_RUN", False))

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
