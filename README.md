# Saboor — Autonomous Halal Trading Agent

Saboor is an AI-powered autonomous trading system designed to beat the S&P 500 through disciplined, sharia-compliant investing. It uses Claude Opus 4.7 as its decision engine, Perplexity for real-time market research, and Alpaca for trade execution.

**Currently running on Alpaca paper trading (simulated money).**

## How It Works

Saboor operates on a daily schedule across four phases:

| Time (ET) | Phase | What Happens |
|-----------|-------|--------------|
| 7:30 AM | Pre-market | Builds a ranked watchlist of 5-10 sharia-screened stocks |
| 9:35 AM | Market Open | Executes buy/sell decisions from the watchlist |
| 12:00 PM | Midday | Reassesses positions; closes stops and max-hold tactical trades |
| 3:30 PM | EOD | Closes remaining tactical positions; sends Telegram report |

### Strategy

Quality-first (Buffett lens) with momentum awareness. See [strategy.readme](strategy.readme) for the full scoring model and rules.

### Guardrails (enforced in code)

- Max 13% of portfolio per position
- 2% daily loss cap — trading halts if breached
- Sharia-compliant positions only (Zoya API + Claude secondary check)
- Max 7 simultaneous positions (5 Core + 2 Tactical)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required keys — see [.env.example](.env.example):
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com)
- `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` — [alpaca.markets](https://alpaca.markets) (paper account)
- `PERPLEXITY_API_KEY` — [perplexity.ai/api](https://www.perplexity.ai/api)
- `ZOYA_API_KEY` — [zoya.finance](https://zoya.finance)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — create via [@BotFather](https://t.me/BotFather)

### 3. Initialize the database

```bash
python main.py init
```

## Running Saboor

Trigger each phase manually for testing:

```bash
python main.py premarket   # Build today's watchlist
python main.py open        # Execute trades
python main.py midday      # Reassess positions
python main.py eod         # Close tactical positions + send report
```

For automated daily execution, configure Claude Code routines in `.claude/settings.json`.

## Project Structure

```
saboor-trading/
├── main.py              # CLI entry point
├── strategy.readme      # Full strategy documentation
├── agents/              # Specialist AI agents
│   ├── researcher.py    # Perplexity-powered research
│   ├── analyst.py       # Claude scoring + watchlist building
│   ├── trader.py        # Claude buy/sell decisions
│   ├── risk_guardian.py # Guardrails enforcement (code-only)
│   └── notifier.py      # Telegram notifications
├── phases/              # Phase orchestrators
│   ├── premarket.py     # 7:30 AM
│   ├── market_open.py   # 9:35 AM
│   ├── midday.py        # 12:00 PM
│   └── eod.py           # 3:30 PM
├── tools/               # API client wrappers
│   ├── alpaca_client.py
│   ├── claude_client.py
│   ├── perplexity_client.py
│   └── zoya_client.py
├── db/
│   ├── schema.sql       # SQLite schema
│   └── queries.py       # Database operations
└── data/
    └── universe.py      # S&P 500 + NASDAQ 100 tickers
```

## Disclaimer

This software is for educational and paper trading purposes. It is not financial advice. Past performance of the strategy does not guarantee future results. Always consult a qualified financial advisor before investing real money.
