# Saboor - Autonomous Halal Investing Agent

Saboor is an AI-powered investing system designed to beat the S&P 500 over time through disciplined, sharia-compliant, Buffett-style ownership of high-quality businesses. It uses Claude Opus 4.7 as its decision engine, yfinance for fundamentals research, Alpaca for paper-trading execution, and Supabase for portfolio records and performance tracking.

**Currently running on Alpaca paper trading. This is not financial advice.**

---

## How It Works

Saboor runs one strategy: long-term quality investing. It does not run a separate tactical trading sleeve.

| Time (Oman) | Time (ET) | Phase | What Happens |
|---|---|---|---|
| 3:30 PM | 7:30 AM | Pre-market | Sharia screen -> yfinance research -> Analyst builds or refreshes candidate list |
| 5:35 PM | 9:35 AM | Market Open | Analyst/Trader reviews entries, adds, trims, exits; Risk Guardian validates orders |
| 8:00 PM | 12:00 PM | Midday | Reviews portfolio risk, thesis alerts, and urgent compliance/business changes |
| 11:30 PM | 3:30 PM | EOD | Records benchmark performance and sends Telegram report |

---

## Strategy

Saboor thinks like a patient business owner. It buys understandable, sharia-compliant companies with durable economics, strong balance sheets, attractive reinvestment opportunities, and sensible prices. Momentum can help with entry timing, but it is never the reason to own a stock.

The Analyst has discretion inside strict boundaries. It may recommend `Buy`, `Add`, `Hold`, `Trim`, or `Exit`, but every action must be justified through business quality, intrinsic value, margin of safety, forward expected return, portfolio concentration, and sharia compliance.

### Hard Rules

These rules are enforced in code and cannot be overridden by the Analyst:

- Non-sharia-compliant business -> blocked
- RSI > 78 -> blocked for new buys/adds
- Price > 150% above MA200 -> blocked for new buys/adds
- FCF negative + PE > 150x + ROE negative -> blocked as pure speculation
- Single position size > 14% of portfolio -> blocked

### Portfolio Philosophy

Saboor does not target a fixed number of positions. Position count is an output of conviction, account size, valuation, and available opportunity.

Suggested portfolio shape:

| Account Size | Typical Holdings |
|---|---|
| Under $5k | 3-5 |
| $5k-$25k | 4-8 |
| $25k-$100k | 5-10 |
| $100k+ | 6-12 |

These are guidance ranges, not quotas. If only a few excellent opportunities exist, Saboor may hold only those and keep cash. If nothing is compelling, cash is a valid position.

### Position Sizing

The Analyst assigns position weights based on conviction, business quality, valuation, and risk. There is no formal minimum percentage, but Saboor should avoid opening token positions that are too small to matter.

Maximum position size: **14% of portfolio value**.

The system may average up or average down only after a fresh review confirms:

- the thesis is intact or stronger
- the company remains sharia-compliant
- the valuation is still reasonable
- the forward expected return remains attractive
- the resulting position stays within the 14% cap

### Selling, Trimming, and Valuation

Saboor never sells just because a stock price dropped. Price movement is information, not a thesis.

Valid reasons to `Trim`:

- the business remains excellent, but price is materially above intrinsic value
- expected 3-5 year forward return has fallen below the hurdle rate
- the position has grown too large relative to risk or conviction
- a clearly superior opportunity exists

Valid reasons to `Exit`:

- the business thesis breaks
- sharia status changes
- management, balance sheet, moat, or industry structure deteriorates
- intrinsic value falls materially
- forward expected return is unattractive and capital is better used elsewhere

Saboor judges overvaluation through an intrinsic-value band, not market mood. The Analyst should estimate bear/base/bull value ranges and compare today's price to expected business cash generation.

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

- `ANTHROPIC_API_KEY` - [console.anthropic.com](https://console.anthropic.com)
- `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` - [alpaca.markets](https://alpaca.markets) paper account
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` - create via [@BotFather](https://t.me/BotFather)
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` - [supabase.com](https://supabase.com)

### 3. Set up Supabase schema

Run `db/supabase_schema.sql` in the Supabase SQL Editor.

### 4. Schedule automation

```bash
bash deploy/install_cron.sh
```

The VPS cron schedule uses UTC. Local macOS scheduler files live in `launchd/`.

---

## Running Manually

```bash
python main.py premarket   # Build or refresh candidate list
python main.py open        # Review and execute buys/adds/trims/exits
python main.py midday      # Monitor portfolio and urgent thesis/compliance changes
python main.py eod         # Record benchmark + send EOD report
```

---

## Project Structure

```text
saboor-trading/
├── main.py                  # CLI entry point
├── strategy.readme          # Full strategy documentation
├── agents/
│   ├── analyst.py           # Claude scoring and business analysis
│   ├── trader.py            # Claude portfolio action decision maker
│   ├── risk_guardian.py     # Non-negotiable risk and entry validation
│   ├── notifier.py          # Telegram notifications
│   └── researcher.py        # yfinance fundamentals fetcher
├── phases/
│   ├── premarket.py
│   ├── market_open.py
│   ├── midday.py
│   └── eod.py
├── tools/
│   ├── alpaca_client.py
│   ├── claude_client.py
│   ├── yfinance_client.py
│   ├── sharia_screener.py
│   └── technical.py
├── db/
│   ├── supabase_client.py
│   ├── queries.py
│   └── supabase_schema.sql
├── data/
│   └── universe.py
├── dashboard/
├── deploy/
└── launchd/
```

---

## Dashboard

Live performance vs SPY is tracked on the dashboard. It shows cumulative return, daily alpha, portfolio value, and open positions.

---

## Disclaimer

This software is for educational and paper trading purposes only. It is not financial advice. Past performance does not guarantee future results. Always consult a qualified financial advisor before investing real money.
