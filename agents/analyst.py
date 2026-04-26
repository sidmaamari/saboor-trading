import json
from tools.claude_client import complete
from tools.alpaca_client import get_bars

SCORING_SYSTEM = """You are Saboor's Analyst. Score stocks for a halal portfolio that seeks to beat the S&P 500.

STRATEGY: Quality-first (Buffett lens) + momentum awareness. Do not depend on news/events as the primary driver.

QUALITY SCORE (0-100) — weight depends on bucket:
  Revenue growth YoY: >20%=25pts | 10-20%=15pts | <10%=5pts | negative=0pts
  Gross margin:       >50%=20pts | 30-50%=12pts  | <30%=5pts
  ROE:                >20%=20pts | 10-20%=12pts  | <10%=5pts
  Debt/Equity:        <0.3=20pts | 0.3-1.0=12pts | >1.0=5pts
  FCF positive:       yes=10pts  | no=0pts
  PEG ratio:          <1.5=5pts  | 1.5-2.5=3pts  | >2.5=0pts | N/A=2pts

MOMENTUM SCORE (0-100):
  Price above 50-day MA:  yes=25pts | no=0pts
  Price above 200-day MA: yes=25pts | no=0pts
  RSI 40-65:              yes=25pts | RSI 65-70=15pts | RSI>70 or <40=0pts
  Volume > 20-day avg:    yes=15pts | no=0pts
  30-day return vs SPY:   outperforming=10pts | underperforming=0pts

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

OUTPUT: Return a JSON array only. Only include stocks that pass sharia AND meet entry thresholds.
Schema per entry:
{
  "ticker": "string",
  "quality_score": number,
  "momentum_score": number,
  "combined_score": number,
  "bucket": "core" | "tactical",
  "thesis": "1-2 sentences on why this is a good trade today",
  "key_risks": "1 sentence on the main risk",
  "sharia_status": "compliant" | "non_compliant" | "borderline"
}"""


def _calculate_momentum(ticker: str, spy_30d_return: float = 0.0) -> dict | None:
    bars = get_bars(ticker, days=210)
    if len(bars) < 55:
        return None

    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]
    current = closes[-1]

    ma50 = sum(closes[-50:]) / 50
    ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sum(closes) / len(closes)

    # RSI-14 (simple)
    deltas = [closes[-i] - closes[-i - 1] for i in range(1, 15)]
    gains = [d for d in deltas if d > 0]
    losses = [abs(d) for d in deltas if d < 0]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14 if losses else 0.001
    rsi = 100 - (100 / (1 + avg_gain / avg_loss))

    avg_vol_20 = sum(volumes[-20:]) / 20
    return_30d = ((closes[-1] - closes[-30]) / closes[-30] * 100) if len(closes) >= 30 else 0

    return {
        "current_price": round(current, 2),
        "above_ma50": current > ma50,
        "above_ma200": current > ma200,
        "rsi": round(rsi, 1),
        "volume_vs_20d_avg": round(volumes[-1] / avg_vol_20, 2),
        "return_30d_pct": round(return_30d, 2),
        "outperforming_spy": return_30d > spy_30d_return,
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
                "research": d["raw_research"],
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
