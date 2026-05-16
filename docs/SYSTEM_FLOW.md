# System flow — TA-35 paper trader

Educational bot that **pretends** to trade Israeli large-cap stocks (Tel Aviv, symbols like `TEVA.TA`). It reads news, asks a local AI for opinions, updates a **fake portfolio** on disk, and can text you a daily summary on Telegram.

> **Not investment advice.** Money is simulated — nothing is sent to a real bank or broker.

---

## Concepts explained (read this first)

### What is a **cycle**?

A **cycle** is **one full lap** of the bot’s work. The function `run_cycle()` in `bot.py` does everything once:

1. Load your saved portfolio  
2. Download latest stock prices and news  
3. Ask Ollama (AI) what it thinks and whether to buy/sell  
4. Apply any allowed trades to the fake portfolio  
5. Save results to disk (and optionally send Telegram at end of day)

If you run `python -m demo_trader` without `--once`, the bot **repeats a cycle every N minutes** (default **15**), sleeps, then starts again. So:

| Term | Meaning |
|------|---------|
| **Cycle** | One complete ingest → analyze → (maybe) trade → save |
| **Loop** | Many cycles back-to-back until you stop the process |
| **Interval** | Minutes between cycles (`DEMO_TRADER_INTERVAL_MINUTES`) |

Think of a cycle like a single “heartbeat” of the trader — not a trading day, not a stock market session, just **one scheduled tick** of the program.

---

### What is **paper trading** / the **paper broker**?

**Paper trading** = practice trading with **fake money**. No orders go to the Tel Aviv Stock Exchange or any broker API.

The **paper broker** (`demo_trader/paper_broker.py`) is **Python code that simulates** what a broker would do:

| Real broker | Paper broker |
|-------------|----------------|
| Sends order to exchange | Updates numbers in `paper_state.json` |
| Deducts real cash | Subtracts from `cash_ils` |
| Credits shares to account | Adds to `positions` dict |
| May reject order | Returns `ok=False` + message (not enough cash, position too large, etc.) |

It also applies simple realism:

- **Slippage** — buys cost slightly more / sells receive slightly less than the quoted price (`DEMO_TRADER_SLIPPAGE_BPS`)  
- **Position cap** — you cannot put more than X% of portfolio in one stock (`DEMO_TRADER_MAX_POSITION_PCT`)  
- **Cash check** — cannot buy more than you have  

So when docs say “execute trade”, they mean **update the JSON file**, not “place a live order”.

---

### What is **`paper_state.json`**?

**File path:** `data/paper_state.json` (override with `DEMO_TRADER_STATE_PATH`)

This is your **simulated brokerage account** — the source of truth for cash, holdings, and trade history. Human-readable JSON on disk.

| Field | What it stores |
|-------|----------------|
| `cash_ils` | How much fake Israeli shekels are idle |
| `positions` | Map of symbol → share quantity, e.g. `"TEVA.TA": 10` |
| `trades[]` | Every buy/sell the paper broker actually executed (time, price, reason) |
| `session` | Snapshot from **first run**: starting NAV and benchmark level (for “how am I doing vs TA-35?”) |
| `last_cycle_ts` | When the last cycle finished (UTC) |
| `last_daily_report_il_date` | Prevents sending duplicate Telegram summaries same day |

**Example (simplified):**

```json
{
  "cash_ils": 95000.0,
  "positions": { "TEVA.TA": 100 },
  "trades": [
    {
      "ts": "2026-05-16T12:00:00+00:00",
      "symbol": "TEVA.TA",
      "side": "buy",
      "qty": 100,
      "price": 50.25,
      "notional_ils": 5025.0,
      "reason": "חיזוק פוזיציה לאחר חדשות"
    }
  ],
  "session": {
    "started_ts": "2026-05-15T08:00:00+00:00",
    "benchmark_symbol": "TA35.TA",
    "benchmark_start_px": 2100.0,
    "initial_nav_ils": 100000.0
  }
}
```

Telegram daily reports and P&L math **read this file** plus live prices from Yahoo.

---

### What is **`trader.db`**?

**File path:** `data/trader.db` (override with `DEMO_TRADER_DB_PATH`)

A **SQLite database** — a single file containing structured tables. Unlike `paper_state.json` (your wallet), `trader.db` is mainly an **audit log and news memory**:

| Table | Plain English purpose |
|-------|----------------------|
| `knowledge_events` | Headlines seen from RSS, optionally linked to a stock symbol |
| `companies` | TA-35 names/metadata (Hebrew names, sectors) |
| `cycles` | One row per **cycle**: NAV, returns vs benchmark, headline count |
| `decisions` | Everything the bot “decided” that cycle: AI summary, each trade attempt, blocks, errors |

**Why two stores?**

| `paper_state.json` | `trader.db` |
|--------------------|-------------|
| Current portfolio | History of *attempts* (including failed/blocked) |
| Only **executed** trades | AI `reason_he`, full context per cycle |
| Easy to reset/delete | Good for debugging “why didn’t it trade?” |

Example: model says “buy TEVA” at 20:00 → stored in `decisions` as `blocked_after_hours`; **no change** to `paper_state.json` positions.

---

### What is **RSS**?

**RSS** = a standard way websites publish **a list of recent articles** (XML feed). News sites expose URLs like:

- Ynet מבזקים  
- Globes  
- Calcalist  

The bot (`news_feeds.py`) **downloads those feeds**, parses titles/links, and uses them as **market context** for the AI. It does **not** scrape full article pages by default — usually just **headlines** (and sometimes dates).

| You configure | `DEMO_TRADER_RSS_FEEDS` (comma-separated URLs) |
| Used in | Every **cycle** — fresh fetch |
| Also saved to | `trader.db` → `knowledge_events` for later cycles |
| If feeds fail | Mock/demo headlines so the bot still runs |

RSS is **not** email and **not** Telegram — it is **pull-based news XML** from publisher URLs.

---

### What is **Ollama** / the **LLM**?

**Ollama** runs a language model **on your machine** (default `llama3.2`). Each cycle the bot sends one **prompt** (news + portfolio + rules) and gets back **JSON**: analysis text and a list of proposed trades.

The LLM **does not**:

- Touch `paper_state.json` directly  
- Connect to RSS or Yahoo  
- Send Telegram messages  

The Python code **reads** the JSON and **decides** whether to call the paper broker.

---

### What is **Telegram** in this project?

Optional **notification channel**. `daily_report.py` builds a text message (trades today, P&L per stock, NAV) and `telegram_notify.py` posts it via the **Telegram Bot API**.

- **Not** used for trading commands  
- **Not** powered by the LLM — fixed template + your data  
- Can run manually (`--daily-report`) or auto once per Israel day after ~17:36

---

### Other terms

| Term | Meaning |
|------|---------|
| **TA-35** | Tel Aviv 35 index — large Israeli companies; bot uses Yahoo symbol `TA35.TA` as benchmark |
| **Watchlist** | Symbols the model is **allowed** to trade (default: 35 `.TA` tickers) |
| **NAV** | Net asset value — cash + market value of all positions |
| **Benchmark** | Compare your fake portfolio return to the index proxy `TA35.TA` |
| **TASE hours gate** | Trades only execute Sun–Thu 09:00–17:35 Israel time (simplified) |
| **Knowledge ingest** | Match headline text to a stock symbol and save in `trader.db` (rules, not AI) |

---

## At a glance

```mermaid
flowchart TB
    subgraph External["External services (real world)"]
        RSS["RSS news feeds<br/>headlines from ynet · Globes · Calcalist"]
        YF["Yahoo Finance<br/>stock prices for .TA symbols"]
        OLL["Ollama on your PC<br/>AI analysis"]
        TG["Telegram<br/>phone notifications"]
    end

    subgraph Bot["Python bot — one cycle at a time"]
        CYCLE["run_cycle()<br/>single lap"]
        PROMPT["Build prompt + ask Ollama"]
        EXEC["Paper broker<br/>fake buy/sell in code"]
        AUDIT["Write audit to SQLite"]
    end

    subgraph Storage["Files on disk"]
        JSON["paper_state.json<br/>fake cash + shares + trade list"]
        DB["trader.db<br/>news memory + decision history"]
    end

    subgraph Daily["End of day (optional)"]
        REP["daily_report<br/>text summary, no AI"]
    end

    RSS --> CYCLE
    YF --> CYCLE
    CYCLE --> PROMPT
    PROMPT --> OLL
    OLL --> EXEC
    EXEC --> JSON
    CYCLE --> AUDIT
    AUDIT --> DB
    JSON --> REP
    DB --> REP
    YF --> REP
    REP --> TG
    CYCLE -.->|after 17:36 IL once/day| REP
```

| Piece | One-line description |
|-------|----------------------|
| **Cycle** | One ingest → AI → maybe fake trade → save |
| **RSS** | Headline feeds from Israeli news sites |
| **`trader.db`** | SQLite: news memory + full decision audit log |
| **`paper_state.json`** | Your fake cash, shares, and executed trades |
| **Paper broker** | Code that updates `paper_state.json` like a broker would |
| **Ollama (LLM)** | Local AI: returns analysis + trade ideas as JSON |
| **Telegram** | End-of-day text report to your phone |

---

## How to run it

```mermaid
flowchart LR
    A["python -m demo_trader"] --> B{mode?}
    B -->|default| C["Loop every N minutes"]
    B -->|--once| D["Single run_cycle"]
    B -->|--daily-report| E["Send Telegram summary"]
    C --> F["run_cycle()"]
    D --> F
    F --> G["sleep N min"]
    G --> F
    E --> H["daily_report.send_daily_report()"]
```

| Command | What happens |
|---------|----------------|
| `python -m demo_trader` | Endless loop: cycle → sleep (`DEMO_TRADER_INTERVAL_MINUTES`, default 15) |
| `python -m demo_trader --once` | One cycle, then exit |
| `python -m demo_trader --daily-report` | Build report → Telegram (or `--dry-run` → stdout) |
| `python -m demo_trader.daily_report` | Same as `--daily-report` (cron-friendly) |

---

## Main cycle (`run_cycle`) — step by step

Reminder: **one cycle** = load portfolio → prices + news → ask AI → maybe update `paper_state.json` → log everything to `trader.db` → save.

```mermaid
flowchart LR
    PS[(paper_state.json<br/>your fake account)]
    DB[(trader.db<br/>audit + news memory)]
    PS --> CYCLE[run_cycle]
    CYCLE --> PS
    CYCLE --> DB
```

Detailed flow:

```mermaid
flowchart TD
    START([Start cycle]) --> LOAD[Load paper_state.json]
    LOAD --> PRICES[Fetch quotes via yfinance<br/>watchlist + positions + TA35.TA]
    PRICES --> BENCH{Benchmark<br/>quote OK?}
    BENCH -->|no| ERR([Exit code 2])
    BENCH -->|yes| MTM[Update trade mark-to-market<br/>in SQLite]

    MTM --> RSS[Fetch RSS headlines]
    RSS --> RSSOK{Any headlines?}
    RSSOK -->|no| MOCK[Use mock headlines]
    RSSOK -->|yes| INGEST
    MOCK --> INGEST[Match headlines → symbols<br/>insert knowledge_events]
    INGEST --> GATE{TASE trading<br/>hours?}
    GATE -->|Sun–Thu 09:00–17:35 IL| ALLOW[trading_allowed = yes]
    GATE -->|else| DENY[trading_allowed = no]

    ALLOW --> SESSION
    DENY --> SESSION[Ensure session snapshot<br/>NAV vs benchmark anchor]
    SESSION --> BUILD[Assemble LLM context blocks]
    BUILD --> LLM[Ollama chat JSON]
    LLM --> LLMOK{Ollama OK?}
    LLMOK -->|no| LOGERR[Log ollama_error to DB<br/>save state · exit 3]
    LLMOK -->|yes| PARSE[Parse analysis_he + trades[]]

    PARSE --> LOOP{For each proposed trade<br/>max N per cycle}
    LOOP --> WATCH{Symbol in<br/>watchlist?}
    WATCH -->|no| SKIP1[skip · log decision]
    WATCH -->|yes| QUOTE{Quote<br/>available?}
    QUOTE -->|no| SKIP2[skip · log decision]
    QUOTE -->|yes| HOURS{trading_allowed?}
    HOURS -->|no| BLOCK[blocked_after_hours<br/>log reason]
    HOURS -->|yes| TRADE[paper_broker.execute_trade]
    TRADE --> LOOP

    SKIP1 --> LOOP
    SKIP2 --> LOOP
    BLOCK --> LOOP

    LOOP -->|done| REFRESH[Refresh prices]
    REFRESH --> CYCLOG[Insert cycle + all decisions<br/>into SQLite]
    CYCLOG --> SAVE[Save paper_state.json]
    SAVE --> TGCHK{Telegram enabled<br/>and after 17:36 IL<br/>and not sent today?}
    TGCHK -->|yes| TGSEND[Send daily_report]
    TGCHK -->|no| END([End cycle · code 0])
    TGSEND --> END
```

### Phase map (same cycle, grouped)

```mermaid
flowchart LR
    subgraph P1["① Ingest"]
        R1[RSS]
        R2[Knowledge SQLite]
        R3[Prices]
    end
    subgraph P2["② Analyze"]
        A1[Build prompt]
        A2[Ollama JSON]
    end
    subgraph P3["③ Act"]
        X1[Validate trades]
        X2[Paper execute or block]
    end
    subgraph P4["④ Persist & notify"]
        S1[JSON state]
        S2[Audit DB]
        S3[Telegram optional]
    end
    P1 --> P2 --> P3 --> P4
```

---

## RSS and knowledge flow

**RSS** supplies the “what’s in the news?” layer. Headlines are fetched **every cycle** (even at night when trading is blocked). New items are stored in **`trader.db`** so the AI can see **older headlines** from previous cycles, not only today’s fetch.

```mermaid
flowchart TD
    FEEDS["DEMO_TRADER_RSS_FEEDS<br/>comma-separated URLs"]
    FEEDS --> FETCH["news_feeds.fetch_headlines()"]
    FETCH --> HTTP["HTTP GET + feedparser"]
    HTTP --> LIST["List of Headline<br/>title · link · source · published"]
    LIST --> DIGEST["headlines_digest()<br/>→ news_text in LLM prompt"]
    LIST --> MATCH["knowledge_ingest.match_company()<br/>Hebrew name · ticker · English name"]
    MATCH --> ROW["INSERT knowledge_events<br/>if new URL+title"]
    ROW --> DB[(trader.db)]
    DB --> PROMPT["recent_knowledge_for_prompt()<br/>last N rows → knowledge_digest"]
    PROMPT --> LLM2[Ollama user prompt section]
    DIGEST --> LLM2
```

| Step | Module | Notes |
|------|--------|-------|
| Fetch | `news_feeds.py` | Falls back to **mock** headlines if all feeds fail (common in datacenters) |
| Digest | `news_feeds.py` | Up to 35 lines in prompt; prefixed with UTC timestamp |
| Match | `knowledge_ingest.py` | Rule-based, **no LLM** |
| Store | `db.py` | Deduped by `(url, title)` |
| Recall | `db.py` | Default 80 rows (`DEMO_TRADER_KNOWLEDGE_DB_ROWS`) |

---

## LLM analysis flow (Ollama)

**One LLM call per cycle.** The model returns structured JSON; the bot does not let the model touch the broker directly.

```mermaid
flowchart TD
    subgraph Inputs["Prompt inputs (user message sections)"]
        I1["Trading gate כן/לא"]
        I2["Watchlist symbols"]
        I3["TA-35 catalog digest"]
        I4["Prior knowledge from SQLite"]
        I5["Maya stub placeholder"]
        I6["Live quotes"]
        I7["Portfolio cash + positions"]
        I8["RSS headline digest"]
    end

    Inputs --> BUILD["ollama_client.build_hebrew_trader_prompt()"]
    SYS["System: paper trader · JSON only · Hebrew rationale fields"]
    BUILD --> SYS
    SYS --> API["POST /api/chat<br/>format: json"]
    API --> OUT["JSON response"]

    OUT --> F1["analysis_he"]
    OUT --> F2["by_symbol[]<br/>stance · rationale per symbol"]
    OUT --> F3["trades[]<br/>symbol · side · qty · reason_he"]

    F3 --> BOT["bot.py validates each trade"]
    F1 --> BOT
    F2 --> BOT
```

### Expected JSON shape (simplified)

```json
{
  "analysis_he": "short market view",
  "by_symbol": [
    { "symbol": "TEVA.TA", "stance": "hold", "rationale_he": "..." }
  ],
  "trades": [
    { "symbol": "TEVA.TA", "side": "buy", "qty": 10, "reason_he": "..." }
  ]
}
```

### Trade validation (after LLM)

```mermaid
flowchart TD
    T[Proposed trade] --> V1{In watchlist?}
    V1 -->|no| S1[skip]
    V1 -->|yes| V2{Has quote?}
    V2 -->|no| S2[skip]
    V2 -->|yes| V3{Inside TASE window?}
    V3 -->|no| B[blocked_after_hours<br/>keeps Hebrew reason]
    V3 -->|yes| V4{Broker rules OK?<br/>cash · qty · position cap · slippage}
    V4 -->|no| S3[skip + broker_message]
    V4 -->|yes| OK[executed → append to paper_state.trades]
```

| Rule | Config |
|------|--------|
| Max trades per cycle | `DEMO_TRADER_MAX_TRADES_PER_CYCLE` (default 3) |
| Max position size | `DEMO_TRADER_MAX_POSITION_PCT` (default 25% NAV) |
| Slippage | `DEMO_TRADER_SLIPPAGE_BPS` (default 5 bps) |

---

## Paper portfolio and benchmark

All portfolio math reads **`paper_state.json`** + live prices. The paper broker only changes `cash_ils`, `positions`, and appends to `trades[]`.

```mermaid
flowchart LR
    STATE["paper_state.json<br/>(fake account file)"]
    STATE --> CASH["cash_ils"]
    STATE --> POS["positions symbol→qty"]
    STATE --> TRADES["trades history"]
    STATE --> SESS["session anchor<br/>initial NAV · benchmark start"]

    YF2["TA35.TA + holdings prices"] --> NAV["portfolio_nav()"]
    CASH --> NAV
    POS --> NAV

    NAV --> PERF["compute_performance()<br/>portfolio % vs benchmark %<br/>alpha"]
    SESS --> PERF
```

- **Session** starts on first cycle: locks initial NAV and `TA35.TA` level.
- Every cycle logs **portfolio_return_pct**, **benchmark_return_pct**, **alpha** into SQLite `cycles` table.

---

## SQLite audit trail (`trader.db`)

**`trader.db`** is optional for “having a portfolio” (that’s JSON), but required for rich history: every cycle’s performance, every AI rationale, every blocked trade.

```mermaid
erDiagram
    cycles ||--o{ decisions : contains
    companies ||--o{ knowledge_events : "matched via ingest"

    cycles {
        int id PK
        string ts
        bool trading_allowed
        bool knowledge_only
        float nav_ils
        float portfolio_return_pct
        float benchmark_return_pct
        float alpha_pct
    }

    decisions {
        int id PK
        int cycle_id FK
        string kind
        string symbol
        string side
        bool executed
        string reason_he
        string analysis_he
        float outcome_mtm_ils
    }

    knowledge_events {
        int id PK
        string title
        string matched_symbol
        string source
    }
```

| `decisions.kind` | Meaning |
|------------------|---------|
| `llm_summary` | Model analysis before trades |
| `trade` | Buy/sell attempt (executed or broker-rejected) |
| `blocked_after_hours` | Model wanted trade; gate closed |
| `skip` | Invalid symbol, no quote, or broker reject |
| `ollama_error` | LLM call failed |

---

## Telegram daily summary flow

Telegram is **separate from the LLM**: a deterministic report built from state, prices, and the audit DB.

```mermaid
flowchart TD
    subgraph Triggers["When does it send?"]
        T1["python -m demo_trader --daily-report"]
        T2["python -m demo_trader.daily_report"]
        T3["End of run_cycle after 17:36 IL<br/>once per calendar day"]
        T4["Cron at market close"]
    end

    Triggers --> LOAD2[Load paper_state.json]
    LOAD2 --> PX[Fetch yfinance prices]
    PX --> BUILD2["build_daily_report()"]

    subgraph Report["Report sections"]
        R1["NAV · session return vs TA35"]
        R2["Actions today<br/>executed buys/sells + reasons"]
        R3["Blocked/skipped from SQLite"]
        R4["Per-holding P&L<br/>unrealized + realized"]
    end

    BUILD2 --> Report
    Report --> DRY{--dry-run?}
    DRY -->|yes| STDOUT[Print to terminal]
    DRY -->|no| API["telegram_notify.send_message()"]
    API --> TG["Telegram chat"]
```

### P&L calculation (holdings)

```mermaid
flowchart LR
    TR["paper_state.trades[]"] --> AVG["Average-cost accounting<br/>holdings_pnl.py"]
    POS["positions"] --> AVG
    PX2["current prices"] --> AVG
    AVG --> U["Unrealized per open symbol"]
    AVG --> R["Realized on sells"]
```

Env vars:

| Variable | Purpose |
|----------|---------|
| `DEMO_TRADER_TELEGRAM_ENABLED` | `1` to enable auto-send in loop |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat id |
| `DEMO_TRADER_TELEGRAM_DAILY_HOUR` | Default `17` |
| `DEMO_TRADER_TELEGRAM_DAILY_MINUTE` | Default `36` |

---

## Static context (no network)

These blocks are injected into the LLM prompt every cycle:

```mermaid
flowchart LR
    CAT["ta35_catalog.py<br/>35 names · sectors · categories"] --> PROMPT2[LLM user prompt]
    MAYA["maya_stub.py<br/>placeholder text"] --> PROMPT2
```

Maya is reserved for future TASE/Maya API integration; today it only informs the model that live filings are not loaded.

---

## File map

| File | Responsibility |
|------|----------------|
| `demo_trader/bot.py` | Orchestrator: `run_cycle()`, CLI |
| `demo_trader/news_feeds.py` | RSS fetch + headline digest |
| `demo_trader/knowledge_ingest.py` | Headline → symbol matching |
| `demo_trader/db.py` | SQLite schema, cycles, decisions, knowledge |
| `demo_trader/ollama_client.py` | Prompt builder + Ollama HTTP |
| `demo_trader/paper_broker.py` | Simulated execution |
| `demo_trader/benchmark.py` | NAV vs `TA35.TA` |
| `demo_trader/tase_calendar.py` | Trading-hours gate |
| `demo_trader/daily_report.py` | Telegram report builder |
| `demo_trader/telegram_notify.py` | Telegram HTTP client |
| `demo_trader/holdings_pnl.py` | Per-holding P&L math |
| `data/paper_state.json` | Portfolio state |
| `data/trader.db` | Audit + knowledge |

---

## Timing diagram (typical day)

```mermaid
sequenceDiagram
    participant Cron as Bot loop (every 15m)
    participant RSS as RSS feeds
    participant DB as SQLite
    participant LLM as Ollama
    participant Paper as Paper broker
    participant TG as Telegram

    loop Each cycle
        Cron->>RSS: fetch headlines
        RSS-->>Cron: titles (Hebrew)
        Cron->>DB: ingest knowledge + log cycle
        Cron->>LLM: prompt with news + portfolio
        LLM-->>Cron: JSON trades + analysis
        alt Inside TASE hours
            Cron->>Paper: execute trades
        else After hours
            Cron->>DB: blocked_after_hours
        end
    end

    Note over Cron,TG: After 17:36 IL once per day
    Cron->>TG: daily summary (actions + P&L)
```

---

## Quick reference: where is data written?

| Event | `paper_state.json` | `trader.db` |
|-------|-------------------|-------------|
| Successful buy/sell | ✅ cash, positions, `trades[]` | ✅ `decisions` row (`executed=1`) |
| AI says buy, market closed | ❌ no change | ✅ `blocked_after_hours` |
| AI says buy, not enough cash | ❌ no change | ✅ `decisions` + `broker_message` |
| RSS headline ingested | ❌ | ✅ `knowledge_events` |
| Cycle finished | ✅ `last_cycle_ts` | ✅ `cycles` row (NAV, alpha, etc.) |
| Telegram sent today | ✅ `last_daily_report_il_date` | ❌ |

---

## Related docs

- [README.md](../README.md) — quick start and env vars
- Prompt text — `demo_trader/ollama_client.py` (`build_hebrew_trader_prompt`)
