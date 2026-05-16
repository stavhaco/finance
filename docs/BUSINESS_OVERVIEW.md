# TA-35 Paper Trader — Business Overview

**Practice investing in Israeli blue chips — with news, AI ideas, and daily updates — without risking real money.**

> Educational simulation only · Not regulated investment advice · No live trading

---

<!-- Slide 1 -->

## What is this?

A **desktop software assistant** that:

- Watches **Israeli large-cap stocks** (TA-35 style universe)
- Reads **Hebrew financial headlines** from major news sites
- Uses a **local AI** on your computer to suggest buys and sells
- Maintains a **practice portfolio** in Israeli shekels (₪)
- Compares results to the **TA-35 index**
- Can send a **daily summary to your phone** (Telegram)

**One sentence:** *It’s a flight simulator for stock decisions — not the real plane.*

---

<!-- Slide 2 -->

## Who is it for?

| Audience | Value |
|----------|--------|
| **Learners** | See how news and index performance might link to simple buy/sell choices |
| **Builders** | Experiment with AI + market data + alerts in one small project |
| **Analysts (informal)** | Get a structured daily log of “what the system did and why” |

**Not for:** live trading, compliance reporting, or production fund management.

---

<!-- Slide 3 -->

## What it does **not** do

```mermaid
flowchart LR
    subgraph Does["✅ The system"]
        D1[Simulate portfolio]
        D2[Read public news]
        D3[Suggest trades via AI]
        D4[Message you a summary]
    end
    subgraph DoesNot["❌ The system"]
        N1[Place real orders]
        N2[Hold your bank account]
        N3[Guarantee profits]
        N4[Replace a licensed advisor]
    end
```

| | |
|---|---|
| **No broker connection** | Nothing is sent to TASE or any bank |
| **No real money** | Balances and trades exist only inside the app’s records |
| **No promise of returns** | Past simulation does not predict future results |

---

<!-- Slide 4 -->

## The big picture

```mermaid
flowchart TB
    NEWS["📰 Market news<br/>Israeli media headlines"]
    MARKET["📈 Market prices<br/>Stock & index levels"]
    BRAIN["🧠 AI advisor<br/>Runs on your computer"]
    PORT["💼 Practice portfolio<br/>Virtual cash & holdings"]
    YOU["📱 You<br/>Daily summary on Telegram"]

    NEWS --> BRAIN
    MARKET --> BRAIN
    PORT --> BRAIN
    BRAIN --> PORT
    PORT --> YOU
    MARKET --> YOU
```

**Flow in plain language:**  
News and prices feed the AI → the AI proposes actions → the system updates your **practice** portfolio → you receive an end-of-day recap.

---

<!-- Slide 5 -->

## A day in the life

```mermaid
flowchart TD
    MORNING["Morning — market opens<br/>System wakes on a schedule"]
    LOOP["Throughout the day<br/>Every ~15 minutes"]
    READ["Read latest headlines"]
    PRICE["Refresh stock prices"]
    THINK["AI reviews news + portfolio"]
    ACT{"Market open<br/>for simulated trades?"}
    TRADE["Update practice portfolio"]
    WAIT["Record ideas only<br/>no simulated trades"]
    CLOSE["After market close<br/>~17:36 Israel time"]
    MSG["Send daily Telegram summary"]

    MORNING --> LOOP
    LOOP --> READ --> PRICE --> THINK --> ACT
    ACT -->|Yes| TRADE --> LOOP
    ACT -->|No| WAIT --> LOOP
    LOOP --> CLOSE --> MSG
```

| Moment | What happens (business view) |
|--------|------------------------------|
| **During the day** | The assistant “checks in” regularly: new news, new prices, fresh AI view |
| **When the market is open** | Approved suggestions become **simulated** buys or sells |
| **When the market is closed** | The AI may still comment; **no** simulated trades are executed |
| **End of day** | Optional message: what traded, why, and profit/loss by holding |

---

<!-- Slide 6 -->

## The “heartbeat” — what is a cycle?

People often ask: *“What is a cycle?”*

| Term | Business meaning |
|------|------------------|
| **Cycle** | One complete check-in: news + prices + AI opinion + update records |
| **Schedule** | Default: every **15 minutes** while the program is running |
| **Not the same as** | A trading day, a stock exchange session, or a human “rebalance” meeting |

```mermaid
flowchart LR
    C1["Check-in 1"] --> C2["Check-in 2"] --> C3["Check-in 3"] --> C4["…"]
```

Think: **regular pulse of the assistant**, not a single end-of-day batch job.

---

<!-- Slide 7 -->

## Your practice portfolio

```mermaid
flowchart TB
    subgraph Portfolio["Virtual account (practice only)"]
        CASH["Cash in ₪"]
        STOCKS["Stock holdings<br/>e.g. Teva, Leumi, Nice…"]
        HISTORY["Trade history<br/>what was bought/sold and when"]
    end
    subgraph Scorecard["Performance scorecard"]
        NAV["Total value<br/>cash + shares"]
        INDEX["Compare vs TA-35 index"]
        ALPHA["Ahead or behind the index"]
    end
    CASH --> NAV
    STOCKS --> NAV
    NAV --> INDEX --> ALPHA
```

| Question | Answer |
|----------|--------|
| Where is it stored? | On your machine (a simple saved file the app reads/writes) |
| Starting amount | Default **₪100,000** (configurable) |
| Currency | Israeli shekels |
| Real custody? | **No** — numbers only |

---

<!-- Slide 8 -->

## How buy/sell decisions are made

```mermaid
flowchart TD
    IN1["Today's headlines"] --> DECIDE
    IN2["Current holdings & cash"] --> DECIDE
    IN3["Stock list allowed<br/>TA-35 style names"] --> DECIDE
    IN4["Company reference data<br/>sectors & names"] --> DECIDE
    DECIDE["AI advisor<br/>produces analysis + trade ideas"]
    DECIDE --> REVIEW["Safety checks"]
    REVIEW --> R1{"Allowed stock?"}
    R1 -->|No| DROP1["Idea discarded"]
    R1 -->|Yes| R2{"Market open?"}
    R2 -->|No| DROP2["Idea logged<br/>not executed"]
    R2 -->|Yes| R3{"Enough cash /<br/>position limits?"}
    R3 -->|No| DROP3["Idea rejected"]
    R3 -->|Yes| DONE["Simulated trade<br/>updates portfolio"]
```

**Important:** The AI **suggests**; the software **enforces rules**. You get an audit trail of both executed and rejected ideas.

---

<!-- Slide 9 -->

## Where the news comes from (RSS)

**RSS** = how news websites publish a **running list of headlines**.

| For you | For the system |
|---------|----------------|
| Same headlines you’d see in news apps / sites | Pulled automatically on each check-in |
| Hebrew sources by default (Ynet, Globes, Calcalist) | Used as context for the AI |
| Public feeds (no paywall bypass) | Stored so older headlines can still inform later check-ins |

```mermaid
flowchart LR
    WEB["News websites"] --> FEED["Headline feeds"]
    FEED --> APP["Assistant"]
    APP --> MEMORY["News memory<br/>builds over days"]
    MEMORY --> APP
```

If feeds are unreachable, the system may use **placeholder headlines** so the rest of the demo still runs.

---

<!-- Slide 10 -->

## What the system remembers

Two complementary records — like **your wallet** vs **your diary**.

```mermaid
flowchart TB
    subgraph Wallet["Practice wallet"]
        W1["Cash balance"]
        W2["Shares you hold"]
        W3["Executed trades only"]
    end
    subgraph Diary["Activity diary"]
        D1["Every check-in summary"]
        D2["Every AI suggestion"]
        D3["Blocked or rejected ideas + reasons"]
        D4["Headlines linked to companies"]
    end
```

| Record type | Business role |
|-------------|---------------|
| **Practice wallet** | “What do I own right now?” |
| **Activity diary** | “What did the assistant think, try, or refuse — and why?” |

Use the diary to answer: *“Why didn’t it buy when the headline looked bullish?”*

---

<!-- Slide 11 -->

## Simulated trading (paper trading)

**Paper trading** = trading on paper, not on the exchange.

```mermaid
flowchart LR
    REAL["Real trading"] --- SIM["This project"]
    REAL --> R1["Broker account"]
    REAL --> R2["Regulation & fees"]
    REAL --> R3["Market impact"]
    SIM --> S1["Virtual account"]
    SIM --> S2["Simple rules<br/>slippage & limits"]
    SIM --> S3["Learning & logging"]
```

| Realistic touches in the simulation | |
|-------------------------------------|---|
| Slightly worse buy / better sell prices | Slippage |
| Cannot overload one stock | Position limit (% of portfolio) |
| Cannot spend cash you don’t have | Cash check |

Still: **no taxes, no fees model, no order book** — keep expectations modest.

---

<!-- Slide 12 -->

## What you get on Telegram

End-of-day **message to your phone** (optional):

```mermaid
flowchart TD
    T1["Portfolio value & vs TA-35"]
    T2["Trades today<br/>buy / sell + reason"]
    T3["Ideas that did not execute"]
    T4["Profit / loss per holding"]
    T1 --> MSG["Single daily message"]
    T2 --> MSG
    T3 --> MSG
    T4 --> MSG
    MSG --> PHONE["Your Telegram chat"]
```

| Section | You see |
|---------|---------|
| **Performance** | Total value, return vs index |
| **Actions** | What changed in the practice portfolio and why (often Hebrew reasons from AI) |
| **Holdings** | Unrealized gain/loss per stock; realized where relevant |

**Telegram is reporting only** — you cannot trade by replying to the bot.

---

<!-- Slide 13 -->

## Operating modes

| Mode | When to use |
|------|-------------|
| **Continuous assistant** | Leave running; check-ins every N minutes |
| **Single check-in** | Run once and stop (testing) |
| **Daily report only** | Just send Telegram summary (e.g. cron at market close) |

```mermaid
flowchart LR
    A["Always-on assistant"] 
    B["One-time check-in"]
    C["Report-only"]
```

---

<!-- Slide 14 -->

## Universe & benchmark

| Item | Meaning |
|------|---------|
| **Stock universe** | ~35 large Israeli companies (`.TA` tickers on Yahoo) |
| **Benchmark** | TA-35 index level via `TA35.TA` proxy |
| **Goal (educational)** | See if the **practice portfolio** beats the index over a “session” |

Official index membership changes over time; the built-in list is a **convenience snapshot**, not a live TASE subscription.

---

<!-- Slide 15 -->

## Limitations (set expectations)

| Area | Limitation |
|------|------------|
| **Prices** | May be delayed or wrong for some Israeli symbols |
| **News** | Headlines only — not full articles; feeds may block automated access |
| **Calendar** | Simple Sun–Thu hours — not full TASE holiday calendar |
| **Filings** | Corporate disclosures (מאיה) — placeholder only today |
| **AI** | Can misunderstand Hebrew news or hallucinate links |
| **Legal** | Not investment advice; not audited |

---

<!-- Slide 16 -->

## Summary

```mermaid
flowchart TB
    subgraph Value["Business value"]
        V1["Safe environment to explore TA-35 ideas"]
        V2["Transparent log of actions and reasons"]
        V3["Daily accountability via Telegram"]
    end
    subgraph Stack["Under the hood — one line each"]
        S1["News feeds"]
        S2["Local AI"]
        S3["Virtual portfolio engine"]
        S4["Phone alerts"]
    end
    Value --- Stack
```

| | |
|---|---|
| **In one line** | An automated practice desk for Israeli large caps, with news-aware AI and optional daily phone summaries. |
| **Technical deep-dive** | [SYSTEM_FLOW.md](SYSTEM_FLOW.md) — for engineers |
| **Get started** | [README.md](../README.md) — install & configuration |

---

*Document version: business overview for the finance paper-trader project.*
