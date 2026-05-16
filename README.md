# finance — demo paper trader (Tel Aviv symbols + local Ollama)

This repository contains a **small educational demo** (not financial advice) that:

- Maintains a **paper portfolio** in ILS with simple **slippage** and **position caps**
- Pulls **delayed-ish market snapshots** for Tel Aviv–listed Yahoo symbols (suffix `.TA`) via `yfinance`
- Compares performance to a **benchmark** (default: `TA35.TA`, a liquid proxy for the TA-35 index on Yahoo Finance)
- On a timer, ingests **RSS headlines** (configurable) and asks a **local Ollama** model (JSON mode) for a short analysis plus optional paper trades

**Important limitations**

- Yahoo Finance data can be **delayed, incomplete, or wrong** for some `.TA` symbols; this is not a regulated market simulator.
- RSS feeds are **not** a full news wire; many Israeli sites block bots or change URLs. If feeds return nothing, the bot falls back to **mock headlines** so you can still exercise the pipeline.
- LLMs are not reliable forecasters; treat outputs as **practice prompts**, not edge.

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Ollama locally and pull a model you like (example):
#   ollama pull llama3.2

export OLLAMA_MODEL=llama3.2
python -m demo_trader --once
```

Loop mode (default interval 15 minutes):

```bash
export DEMO_TRADER_INTERVAL_MINUTES=30
python -m demo_trader
```

## Configuration (environment variables)

| Variable | Meaning |
|---|---|
| `OLLAMA_BASE_URL` | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Any local Ollama model name |
| `DEMO_TRADER_INTERVAL_MINUTES` | Sleep between cycles in loop mode |
| `DEMO_TRADER_STARTING_CASH_ILS` | Initial cash when state file is first created |
| `DEMO_TRADER_STATE_PATH` | Where portfolio JSON is stored (default `data/paper_state.json`) |
| `DEMO_TRADER_WATCHLIST` | Comma-separated `.TA` symbols the model is allowed to trade |
| `DEMO_TRADER_BENCHMARK` | Benchmark symbol for comparison (default `TA35.TA`) |
| `DEMO_TRADER_RSS_FEEDS` | Comma-separated RSS URLs |
| `DEMO_TRADER_SLIPPAGE_BPS` | Simple execution friction in basis points |
| `DEMO_TRADER_MAX_POSITION_PCT` | Max percent of NAV in a single name (rough cap) |
| `DEMO_TRADER_MAX_TRADES_PER_CYCLE` | Hard cap on trades per cycle |
| `DEMO_TRADER_OLLAMA_TIMEOUT_SEC` | HTTP timeout for Ollama |

**Tel Aviv breadth:** Yahoo’s `TA35.TA` is a practical benchmark proxy. For a broader index, try `TA125.TA` if Yahoo quotes it in your region; otherwise prefer an ETF/index tracker you can actually fetch reliably.

**Israeli RSS:** If you find stable feed URLs (Globes/Calcalist/TheMarker/etc.), set `DEMO_TRADER_RSS_FEEDS` accordingly. Many publishers require cookies or block datacenter IPs.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## Resetting the demo

Delete the state file (default `data/paper_state.json`) to restart cash and benchmark session anchoring.
