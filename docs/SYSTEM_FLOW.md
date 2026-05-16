# System flow — TA-35 paper trader

Educational paper-trading bot for Israeli large caps (`.TA` symbols). This document explains how **RSS**, **SQLite knowledge**, **Ollama (LLM)**, **paper execution**, and **Telegram** fit together.

> **Not investment advice.** No live broker connection.

---

## At a glance

```mermaid
flowchart TB
    subgraph External["External services"]
        RSS["Hebrew RSS feeds<br/>ynet · Globes · Calcalist"]
        YF["Yahoo Finance<br/>yfinance quotes"]
        OLL["Ollama<br/>local LLM"]
        TG["Telegram Bot API"]
    end

    subgraph Bot["demo_trader (python -m demo_trader)"]
        CYCLE["run_cycle()"]
        PROMPT["Build prompt + call LLM"]
        EXEC["Paper broker"]
        AUDIT["SQLite audit log"]
    end

    subgraph Storage["Persistent data"]
        JSON["paper_state.json<br/>cash · positions · trades"]
        DB["trader.db<br/>knowledge · cycles · decisions"]
    end

    subgraph Daily["End of day (optional)"]
        REP["daily_report"]
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

| Layer | Role |
|-------|------|
| **RSS** | Fresh Hebrew headlines each cycle |
| **Knowledge DB** | Remember headlines across cycles; match titles → symbols |
| **LLM** | One JSON decision per cycle: analysis + optional trades |
| **Paper broker** | Simulated buy/sell with slippage and position limits |
| **Telegram** | Human-readable daily summary (no LLM) |

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

Each cycle is **one pass** through data collection, analysis, optional trades, and persistence.

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

Headlines are fetched **every cycle** (not only when trading). Knowledge survives in SQLite for later prompts.

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

```mermaid
flowchart LR
    STATE["paper_state.json"]
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

## SQLite audit trail

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

## Related docs

- [README.md](../README.md) — quick start and env vars
- Prompt text reference — see `demo_trader/ollama_client.py` (`build_hebrew_trader_prompt`)
