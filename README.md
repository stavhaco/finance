# finance — TA-35 paper trader (Hebrew knowledge + simulation)

Educational **paper trading** loop for Israeli large caps (Yahoo `.TA` symbols), Hebrew/Maya/RSS context, **SQLite knowledge center** with English enrichment, optional **historical simulation**, and **local Ollama** for decisions.

Not investment advice.

## Quick start (Mac / Linux)

```bash
cd /path/to/finance
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ollama (separate app — keep it running outside this repo)
ollama serve   # or use the Ollama.app menu bar on macOS
ollama pull llama3.2

export OLLAMA_MODEL=llama3.2
export DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST=1   # translate/summarize new rows once in DB

# One trading cycle (recommended for scheduling)
python -m demo_trader --once
```

Data defaults:

| Path | Purpose |
|------|---------|
| `data/trader.db` | SQLite: knowledge, cycles, decisions, price bars |
| `data/paper_state.json` | Paper portfolio + benchmark session |
| `data/logs/cycles/` | Per-cycle JSON audit (prompt inputs, model output, executions) |

## Per-cycle logs (what the model saw and did)

Each `python -m demo_trader --once` run can write a JSON report under `data/logs/cycles/` (enabled by default):

```bash
ls -lt data/logs/cycles/
cat data/logs/cycles/cycle_00042_2026-05-19T10-30-00.json | python3 -m json.tool | less
```

Typical fields:

| Field | Meaning |
|-------|---------|
| `cycle_id`, `ts_utc`, `mode` | DB cycle id, timestamp, `live` or `simulation` |
| `ingest` | RSS/Maya counts ingested this cycle |
| `performance_before` / `performance_after` | NAV, return vs benchmark |
| `portfolio_after` | Cash %, positions (includes `cash_pct_of_nav`, deployment target) |
| `prompt.sections` | Each input block sent to Ollama (`preview` + optional `full`) |
| `model_response` | Parsed JSON from Ollama (`analysis_he`, `trades`, …) |
| `executions` | What the bot recorded (fills, skips, `reason_he`) |

Env vars:

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEMO_TRADER_CYCLE_LOG_ENABLED` | `1` | Write cycle JSON files |
| `DEMO_TRADER_CYCLE_LOG_DIR` | `data/logs/cycles` | Output directory |
| `DEMO_TRADER_CYCLE_LOG_FULL_PROMPTS` | `0` | If `1`, store full prompt text (large files) |

SQLite still holds the authoritative audit: `cycles`, `decisions` (query with `sqlite3 data/trader.db`).

## Deploy capital (encourage buys, low cash)

The Hebrew prompt tells the model to keep cash low when trading is allowed and to suggest modest **buy** trades across several TA-35 names (not leave most NAV in cash).

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEMO_TRADER_MAX_CASH_PCT_TARGET` | `15` | If `cash_pct_of_nav` is above this and TASE window is open, prompt asks for buys |
| `DEMO_TRADER_MIN_BUYS_WHEN_TRADING` | `1` | Minimum buy trades to suggest in that case |
| `DEMO_TRADER_MAX_TRADES_PER_CYCLE` | `5` | Cap on trades executed per cycle |

Example (more aggressive, still modest size per trade):

```bash
export DEMO_TRADER_MAX_CASH_PCT_TARGET=10
export DEMO_TRADER_MIN_BUYS_WHEN_TRADING=2
export DEMO_TRADER_MAX_TRADES_PER_CYCLE=5
```

Yahoo sometimes quotes Israeli tickers in **agorot** (`ILA`); the bot converts to shekels for NAV and orders. If an old `paper_state.json` was built with wrong prices, start a fresh session or reset state after pulling this fix.

## Run reliably on a Mac Mini (outside the Python loop)

**Do not** leave `python -m demo_trader` running its built-in `while True` sleep loop for production scheduling. Use **`--once` per invocation** and let **macOS launchd** (or cron) restart it.

```bash
cp scripts/mac/demo-trader.env.example scripts/mac/demo-trader.env
# edit scripts/mac/demo-trader.env (REPO_ROOT, OLLAMA_MODEL, paths)

./scripts/mac/install_launchd.sh
# installs ~/Library/LaunchAgents/com.finance.demo-trader.plist
# logs: data/logs/demo-trader.stdout.log

launchctl kickstart -k gui/$(id -u)/com.finance.demo-trader   # run now
./scripts/mac/uninstall_launchd.sh                             # remove agent
```

The agent runs `scripts/mac/run_cycle.sh` every **15 minutes** (edit `StartInterval` in the plist template). Ollama should run as its own service (Ollama.app or `ollama serve`).

## Knowledge center (translate once, read every cycle)

On each **new** RSS/Maya row (when `DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST=1`):

1. Fetch body: RSS HTML (Globes/Calcalist…) or **Maya HTM/PDF attachments** from API metadata in `snippet`.
2. One Ollama JSON call stores in `knowledge_events`:
   - `title_en`, `body_translation_en` (full EN translation)
   - `executive_summary_en`
   - `sentiment`: `positive` | `negative` | `neutral`
   - `trade_usefulness`: `high` | `medium` | `low`
   - `is_broad_market` (macro / BoI / index-level stories)

Trading cycles read **`trader_knowledge_digest_en`** (TA-35 names, `high` usefulness, or broad market) — **no re-translation per cycle**.

### Backfill existing rows

```bash
# After migration 003 (applied automatically on first open_db)
python -m demo_trader.seed_sim --rss --no-enrich    # ingest only, fast
python -m demo_trader.backfill_knowledge --limit 50 --sleep-sec 1

# Re-enrich everything
python -m demo_trader.backfill_knowledge --force-all --sleep-sec 1
```

### Knowledge / enrichment env vars

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST` | `1` | LLM enrich each new row at ingest |
| `DEMO_TRADER_KNOWLEDGE_ENRICH_FETCH_BODY` | `1` | Fetch HTML/PDF before LLM |
| `DEMO_TRADER_OLLAMA_ENRICHMENT_MODEL` | (same as `OLLAMA_MODEL`) | Model for enrichment only |
| `DEMO_TRADER_KNOWLEDGE_ENRICH_TIMEOUT_SEC` | `300` | Ollama timeout per article |
| `DEMO_TRADER_KNOWLEDGE_ENRICH_MAX_BODY_CHARS` | `14000` | Max chars sent to LLM |
| `DEMO_TRADER_KNOWLEDGE_TRADER_DIGEST_LIMIT` | `40` | Rows in trading prompt |
| `DEMO_TRADER_KNOWLEDGE_DIGEST_EXCERPT_CHARS` | `600` | Excerpt of full translation in prompt |
| `DEMO_TRADER_ENRICH_URL_HOST_SUFFIXES` | globes, calcalist, maya… | `*` = allow all hosts |

## Simulation / practice mode

Replay the past week (or custom start) with historic **5m** bars and news only up to `sim_now`.

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEMO_TRADER_SIMULATION` | `0` | Enable sim clock + historic prices |
| `DEMO_TRADER_SIM_START_DAYS_AGO` | `7` | Start at 00:00 IL N days ago |
| `DEMO_TRADER_SIM_START_ISO` | — | Explicit UTC/offset start |
| `DEMO_TRADER_SIM_STEP_MINUTES` | `15` | Advance sim time after each cycle |
| `DEMO_TRADER_SIM_SKIP_CLOSED_HOURS` | `1` | Jump to next Sun–Thu 09:00–17:35 IL open |
| `DEMO_TRADER_ENFORCE_TASE_HOURS` | `1` | Block trades outside TASE window (`0` = practice anytime) |
| `DEMO_TRADER_SIM_INGEST_LIVE` | `1` | Still fetch RSS/Maya each cycle (filtered by `sim_now`) |
| `DEMO_TRADER_PRICE_BAR_INTERVAL` | `5m` | Stored bar interval (Yahoo ~30d for 5m) |
| `DEMO_TRADER_PRICE_HISTORY_DAYS` | `30` | Intraday backfill depth |

```bash
python -m demo_trader.seed_sim --force-bars   # daily gap-fill bars (once per IL day)
export DEMO_TRADER_SIMULATION=1
export DEMO_TRADER_SIM_START_DAYS_AGO=7
python -m demo_trader --once
```

## Maya API notes

- Breaking announcements: API **`limit` max 5** (client caps automatically).
- Report text: enrichment prefers **HTM/PDF attachment URLs** from Maya JSON (not the SPA page URL).

## Trading / Ollama env vars

| Variable | Default |
|----------|---------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `llama3.2` |
| `DEMO_TRADER_INTERVAL_MINUTES` | `15` (only if you use the built-in loop) |
| `DEMO_TRADER_STARTING_CASH_ILS` | `100000` |
| `DEMO_TRADER_WATCHLIST` | all TA-35 catalog symbols |
| `DEMO_TRADER_DB_PATH` | `data/trader.db` |
| `DEMO_TRADER_MAX_TRADES_PER_CYCLE` | `5` |
| `DEMO_TRADER_MAX_CASH_PCT_TARGET` | `15` |
| `DEMO_TRADER_MIN_BUYS_WHEN_TRADING` | `1` |
| `DEMO_TRADER_CYCLE_LOG_ENABLED` | `1` |
| `DEMO_TRADER_CYCLE_LOG_DIR` | `data/logs/cycles` |
| `DEMO_TRADER_CYCLE_LOG_FULL_PROMPTS` | `0` |

## Tests (no LLM)

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Limitations

- Yahoo `.TA` data can be delayed or wrong.
- TASE holidays not modeled; hours gate is simplified Sun–Thu 09:00–17:35 IL.
- RSS from some publishers may 403 non-browser clients.
- Enrichment quality depends on Ollama model and attachment availability.
