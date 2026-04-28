import json
from tools.claude_client import complete
from tools.alpaca_client import get_bars
from tools.technical import calculate_signals

SCORING_SYSTEM = """You are Saboor's Analyst. Score stocks for a halal portfolio that seeks to beat the S&P 500.

You receive structured financial data (from yfinance/SEC filings) plus technical signals.
All numeric fields are already parsed — no extraction needed. None means data unavailable; treat as neutral (mid-range score).

STRATEGY: Quality-first (Buffett lens) + momentum awareness. Do not depend on news/events as the primary driver.
Default to caution. Only recommend a stock if you are genuinely confident it will generate positive returns.
A pass is better than a bad trade — missing a winner costs nothing, a bad entry loses real money.

HARD EXCLUSIONS — exclude these immediately, do not score them:
  - RSI > 78: stock is overbought, high reversal risk
  - Price > 150% above MA200: dangerously extended, mean-reversion risk
  - FCF negative AND PE > 150x AND ROE negative: pure speculation, no fundamental floor
  - ma200_extension_pct field provided — use it

QUALITY SCORE (0-100) — weight depends on bucket:
  Revenue growth YoY: >20%=25pts | 10-20%=15pts | <10%=5pts | negative=0pts
  Gross margin:       >50%=20pts | 30-50%=12pts  | <30%=5pts
  ROE:                >20%=20pts | 10-20%=12pts  | <10%=5pts | negative=-10pts
  Debt/Equity:        <0.3=20pts | 0.3-1.0=12pts | >1.0=5pts
  FCF positive:       yes=10pts  | no=0pts
  PEG ratio:          <1.5=5pts  | 1.5-2.5=3pts  | >2.5=0pts | N/A=2pts
  PENALTY: FCF negative + PE > 100x = subtract 10pts from quality score

MOMENTUM SCORE (0-100):
  Price above 50-day MA:  yes=25pts | no=0pts
  Price above 200-day MA: yes=25pts | no=0pts
  RSI 40-65:              25pts (ideal entry zone)
  RSI 65-72:              15pts (getting hot — acceptable)
  RSI 72-78:              5pts  (caution — only enter with strong quality)
  RSI > 78 or < 38:       EXCLUDE stock entirely (see hard exclusions above)
  Volume > 20-day avg:    yes=15pts | no=0pts
  30-day return vs SPY:   outperforming=10pts | underperforming=0pts
  PENALTY: ma200_extension_pct > 100% = subtract 10pts from momentum score

BUCKET CLASSIFICATION:
  CORE:     quality_score >= 60 AND combined_score >= 65
            Combined = quality*0.6 + momentum*0.4
  TACTICAL: momentum_score >= 65 AND combined_score >= 60
            Combined = quality*0.3 + momentum*0.7
  EXCLUDE:  anything below both thresholds

SHARIA SECONDARY CHECK: If sharia_status is 'borderline' or 'not_found', apply AAOIFI criteria:
  - Exclude: conventional banking/insurance, alcohol, tobacco, weapons, adult content, pork
  - Financial ratios: interest-bearing debt < 33% of market cap, interest income < 5% of revenue
  - Mark as 'compliant', 'non_compliant', or 'borderline' in your output

POSITION SIZING — assign position_weight_pct based purely on score and conviction.
Company size, name, and market cap are irrelevant. A small unknown company with a
score of 90 gets more weight than a mega-cap with a score of 65. Score drives everything.
There is no hard cap — assign what the conviction warrants.

  CORE positions (long-term hold, weeks to months):
    combined_score 85–100 → 11–15%
    combined_score 75–84  → 8–11%
    combined_score 65–74  → 5–8%
    combined_score 55–64  → 3–5%

  TACTICAL positions (short-term, 2–3 days, momentum-driven):
    combined_score 80–100 → 4–6%
    combined_score 70–79  → 3–4%
    combined_score 60–69  → 2–3%

  Aim for total allocation 80–95% — idle cash does not beat the market.
  Be decisive: high conviction = high weight, regardless of company size or fame.
  Maximum 20 simultaneous positions: 17 Core + 3 Tactical.

OUTPUT: Return a JSON array only. Only include stocks that pass sharia AND meet entry thresholds.
Schema per entry:
{
  "ticker": "string",
  "quality_score": number,
  "momentum_score": number,
  "combined_score": number,
  "bucket": "core" | "tactical",
  "position_weight_pct": number,
  "thesis": "1-2 sentences on why this is a good trade today",
  "key_risks": "1 sentence on the main risk",
  "sharia_status": "compliant" | "non_compliant" | "borderline"
}"""


def _calculate_momentum(ticker: str, spy_30d_return: float = 0.0) -> dict | None:
    # FIX [HIGH H-12]: Delegate RSI/MA math to the shared calculator.
    # REASON: Eliminates duplicate code that previously diverged between
    #         this file and risk_guardian.py.
    # SOLUTION: tools.technical.calculate_signals is the single source of truth.
    bars = get_bars(ticker, days=210)
    if len(bars) < 55:
        return None

    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]

    signals = calculate_signals(closes, volumes)
    rsi = signals["rsi"]
    current = signals["current"]
    ma200_extension_pct = signals["ma200_extension_pct"]
    avg_vol_20 = signals["avg_vol_20"]

    return_30d = ((closes[-1] - closes[-30]) / closes[-30] * 100) if len(closes) >= 30 else 0

    # Hard pre-filter — block before Claude sees the stock
    if rsi > 78:
        print(f"    [{ticker}] excluded: RSI {rsi:.0f} > 78 (overbought)")
        return None
    if ma200_extension_pct > 150:
        print(f"    [{ticker}] excluded: {ma200_extension_pct:.0f}% above MA200 (too extended)")
        return None

    volume_ratio = round(volumes[-1] / avg_vol_20, 2) if avg_vol_20 > 0 else 0.0

    return {
        "current_price": round(current, 2),
        "above_ma50": signals["above_ma50"],
        "above_ma200": signals["above_ma200"],
        "rsi": rsi,
        "volume_vs_20d_avg": volume_ratio,
        "return_30d_pct": round(return_30d, 2),
        "outperforming_spy": return_30d > spy_30d_return,
        "ma200_extension_pct": ma200_extension_pct,
    }


def score_stocks(dossiers: list[dict], spy_return_30d: float = 0.0) -> list[dict]:
    """Score dossiers and return ranked list of stocks meeting entry thresholds."""
    stock_data = []
    for d in dossiers:
        try:
            momentum = _calculate_momentum(d["ticker"], spy_return_30d)
            if momentum is None:
                continue
            stock_data.append({
                "ticker": d["ticker"],
                "sharia_status": d.get("sharia_status", "compliant"),
                "fundamentals": {
                    k: v for k, v in d.items()
                    if k not in ("ticker", "sharia_status")
                },
                "momentum_signals": momentum,
            })
        except Exception as e:
            print(f"  Momentum calc failed for {d['ticker']}: {e}")

    if not stock_data:
        return []

    user_msg = (
        f"Score these stocks. SPY 30-day return: {spy_return_30d:.2f}%.\n\n"
        f"Stock data:\n{json.dumps(stock_data, indent=2)}\n\n"
        "Return JSON array only."
    )

    try:
        result = complete(SCORING_SYSTEM, user_msg, as_json=True)
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"Analyst scoring failed: {e}")
        return []
