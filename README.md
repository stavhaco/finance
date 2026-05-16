# finance — TA-35 paper trader (Hebrew knowledge + SQLite audit log)

This repository contains an **educational** paper-trading loop (not investment advice) focused on a **TA-35-style universe** of Israeli large caps (Yahoo Finance symbols ending in `.TA`), **Hebrew-first news context**, and a **local Ollama** JSON policy.

## Documentation

| Doc | Audience |
|-----|----------|
| **[docs/BUSINESS_OVERVIEW.md](docs/BUSINESS_OVERVIEW.md)** | Presentation-style: what it does, daily flow, Telegram — minimal jargon |
| **[docs/SYSTEM_FLOW.md](docs/SYSTEM_FLOW.md)** | Technical flow, glossary, file-level detail |

## What it does now

- **Universe / “knowledge center”**: a curated `TA35_COMPANIES` catalog (35 names) with Hebrew display names, sectors, and coarse categories (`demo_trader/ta35_catalog.py`). This is a **static convenience snapshot**; official index membership changes over time, so refresh from TASE when you care about exact parity.
- **Hebrew sources (RSS)**: defaults prioritize **ynet מבזקים**, plus **Globes** and **Calcalist** feeds when your network permits (many Israeli publishers return 403 to datacenters/bots). You can override `DEMO_TRADER_RSS_FEEDS`.
- **Maya (מאיה)**: there is a dedicated prompt section, but **no live Maya scraping** yet (Maya is largely a SPA; reliable ingestion typically needs official API keys or browser automation). See `demo_trader/maya_stub.py`.
- **Knowledge memory**: RSS items are matched to companies (Hebrew names + tickers) and stored in SQLite (`knowledge_events`) for reuse across cycles.
- **Trading vs learning**:
  - **Every X minutes** the bot ingests knowledge (RSS → SQLite) and refreshes prices.
  - **Trades execute only** during a simplified **Sun–Thu 09:00–17:35 Asia/Jerusalem** window (`demo_trader/tase_calendar.py`). Outside that window, model output may still analyze, but executions are logged as `blocked_after_hours`.
- **Benchmarking**: compares your paper NAV to `TA35.TA` (Yahoo proxy for the TA-35 index level), anchored at the first session snapshot in `data/paper_state.json`.
- **Audit trail**: `data/trader.db` stores cycles + decisions (including LLM JSON, Hebrew rationales, and rolling mark-to-market fields for executed trades).

## Quick start

```bash
pip install -r requirements.txt
export OLLAMA_MODEL=llama3.2
python -m demo_trader --once
```

Defaults:

- Starting cash: **₪100,000** (`DEMO_TRADER_STARTING_CASH_ILS`)
- Watchlist: **all 35 catalog symbols** unless you override `DEMO_TRADER_WATCHLIST`
- DB path: `data/trader.db` (`DEMO_TRADER_DB_PATH`)

## Notes / limitations

- Yahoo Finance data can be delayed or wrong for some `.TA` symbols.
- TASE **holiday calendar** is not modeled; the trading gate is intentionally conservative and simple.
- RSS scraping should respect publisher terms; prefer licensed feeds where possible.

## Telegram daily summary

Send a daily message with **buy/sell actions and reasons**, plus **unrealized/realized P&L per holding**.

1. Create a bot via [@BotFather](https://t.me/BotFather) and obtain `TELEGRAM_BOT_TOKEN`.
2. Get your `TELEGRAM_CHAT_ID` (e.g. message [@userinfobot](https://t.me/userinfobot) or use `getUpdates` after messaging your bot).
3. Enable and run:

```bash
export DEMO_TRADER_TELEGRAM_ENABLED=1
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python -m demo_trader --daily-report          # send now
python -m demo_trader --daily-report --dry-run  # preview in stdout
```

When the bot loop is running, it also sends **once per Israel calendar day** after `17:36` (configurable via `DEMO_TRADER_TELEGRAM_DAILY_HOUR` / `DEMO_TRADER_TELEGRAM_DAILY_MINUTE`).

Cron alternative at market close:

```bash
45 17 * * 0-4 cd /path/to/finance && DEMO_TRADER_TELEGRAM_ENABLED=1 python -m demo_trader.daily_report
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
