# Saboor — Autonomous Halal Trading Agent

Saboor is an AI-powered autonomous trading system designed to beat the S&P 500 through disciplined, sharia-compliant investing. It uses Claude Opus 4.7 as its decision engine, yfinance for fundamentals research, and Alpaca for trade execution.

**Currently running on Alpaca paper trading (simulated money).**

---

## How It Works

Saboor runs four phases every trading day, fully automated via cron:

| Time (Oman) | Time (ET) | Phase | What Happens |
|---|---|---|---|
| 3:30 PM | 7:30 AM | Pre-market | Sharia screen → yfinance research → Analyst builds ranked watchlist |
| 5:35 PM | 9:35 AM | Market Open | Trader executes buys from watchlist; Risk Guardian validates each order |
| 8:00 PM | 12:00 PM | Midday | Closes tactical positions that hit their 3-day max hold |
| 11:30 PM | 3:30 PM | EOD | Force-closes remaining tactical positions; sends Telegram report |

---

## Strategy

Quality-first (Buffett lens) + momentum timing. See [strategy.readme](strategy.readme) for the full scoring model and rules.

**The Analyst has full authority.** Within the defined rules, it decides what to buy, how much weight to assign, and when to exit. No mechanical override will contradict a well-reasoned Analyst decision.

### Entry Rules (enforced in code — cannot be overridden)

- RSI > 78 → blocked (overbought)
- Price > 150% above MA200 → blocked (over-extended)
- FCF negative + PE > 150x + ROE negative → blocked (pure speculation)
- Non-sharia-compliant business → blocked

### Portfolio Structure

| Bucket | Max Positions | Hold Duration | Exit Rule |
|---|---|---|---|
| Core | 17 | Weeks to months | Only when fundamental thesis breaks |
| Tactical | 3 | Max 3 trading days | Auto-closed at EOD on day 3 |
| **Total** | **20** | | |

### Position Sizing

Assigned purely by the Analyst based on `combined_score` and conviction. No hard cap on any single position. Company size and fame are irrelevant — a small company with a score of 90 gets more weight than a mega-cap with a score of 65.

Target: **80–95% of capital deployed at all times.**

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env.local
# Fill in your keys
```

Required keys:
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com)
- `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` — [alpaca.markets](https://alpaca.markets) (paper account)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — create via [@BotFather](https://t.me/BotFather)
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` — [supabase.com](https://supabase.com)

### 3. Set up Supabase schema

Run `db/supabase_schema.sql` in the Supabase SQL Editor.

### 4. Schedule with cron

```bash
bash deploy/install_cron.sh   # on a Linux VPS (UTC times)
# OR — on Mac, crontab is already configured in Oman local time
```

---

## Running Manually

```bash
python main.py premarket   # Build today's watchlist + send Telegram
python main.py open        # Execute trades
python main.py midday      # Reassess / close 3-day tactical holds
python main.py eod         # Force-close tacticals + send EOD report
```

---

## Project Structure

```
saboor-trading/
├── main.py                  # CLI entry point (premarket / open / midday / eod)
├── strategy.readme          # Full strategy documentation
├── agents/
│   ├── analyst.py           # Claude scoring model + watchlist builder
│   ├── trader.py            # Claude buy/sell decision maker
│   ├── risk_guardian.py     # Entry validation (RSI, MA200, position limits)
│   ├── notifier.py          # Telegram notifications
│   └── researcher.py        # yfinance fundamentals fetcher
├── phases/
│   ├── premarket.py         # 3:30 PM Oman
│   ├── market_open.py       # 5:35 PM Oman
│   ├── midday.py            # 8:00 PM Oman
│   └── eod.py               # 11:30 PM Oman
├── tools/
│   ├── alpaca_client.py     # Alpaca REST API wrapper
│   ├── claude_client.py     # Anthropic API wrapper (with prompt caching)
│   ├── yfinance_client.py   # Free fundamentals from Yahoo Finance
│   ├── sharia_screener.py   # Claude-based AAOIFI compliance gate
│   └── technical.py         # Shared RSI + MA200 calculations
├── db/
│   ├── supabase_client.py   # Supabase singleton client
│   ├── queries.py           # All database operations
│   └── supabase_schema.sql  # PostgreSQL schema
├── data/
│   └── universe.py          # ~224 S&P 500 + NASDAQ 100 tickers
├── dashboard/               # Next.js performance dashboard (Vercel)
├── deploy/                  # VPS setup + cron install scripts
└── launchd/                 # macOS scheduler plists
```

---

## Dashboard

Live performance vs SPY is tracked at the Vercel dashboard. Shows cumulative return chart, daily alpha, and live portfolio breakdown.

---

## Disclaimer

This software is for educational and paper trading purposes only. It is not financial advice. Past performance does not guarantee future results. Always consult a qualified financial advisor before investing real money.
