"""
Shared technical indicator calculations.

FIX [HIGH]: Extracted from agents/analyst.py and agents/risk_guardian.py to
eliminate duplicated RSI / MA200 logic.
REASON: Two divergent copies of the same indicator math is a correctness
hazard — a fix in one place can silently fail to land in the other.
SOLUTION: Single source of truth for all entry-quality signals.
"""
from __future__ import annotations


def calculate_signals(closes: list[float], volumes: list[float] | None = None) -> dict:
    """
    Compute the entry-quality technical signals shared between Analyst and
    Risk Guardian.

    Parameters
    ----------
    closes  : list of daily close prices, oldest first, most recent last.
    volumes : optional list of daily volumes, aligned with `closes`.

    Returns
    -------
    A dict with the keys consumers expect. If there is insufficient data,
    fields default to neutral values (current price for MAs, 50 for RSI,
    0 for derived percentages) so callers can still safely consume them.
    """
    if not closes:
        return {
            "current": 0.0,
            "rsi": 50.0,
            "ma50": 0.0,
            "ma200": 0.0,
            "ma200_extension_pct": 0.0,
            "avg_vol_20": 0.0,
            "above_ma50": False,
            "above_ma200": False,
        }

    current = float(closes[-1])

    # MA50 — fall back to whatever data we have if <50 bars.
    ma50_window = closes[-50:] if len(closes) >= 50 else closes
    ma50 = sum(ma50_window) / len(ma50_window)

    # MA200 — fall back to whatever data we have if <200 bars.
    ma200_window = closes[-200:] if len(closes) >= 200 else closes
    ma200 = sum(ma200_window) / len(ma200_window)

    # RSI-14 — needs at least 16 bars for 14 deltas + boundary safety.
    if len(closes) >= 16:
        deltas = [closes[-i] - closes[-i - 1] for i in range(1, 15)]
        gains = [d for d in deltas if d > 0]
        losses = [abs(d) for d in deltas if d < 0]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14 if losses else 0.001
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
    else:
        rsi = 50.0  # neutral when insufficient data

    # 20-day average volume — defaults to 0 if not supplied.
    if volumes:
        vol_window = volumes[-20:] if len(volumes) >= 20 else volumes
        avg_vol_20 = sum(vol_window) / len(vol_window)
    else:
        avg_vol_20 = 0.0

    ma200_extension_pct = ((current / ma200) - 1) * 100 if ma200 > 0 else 0.0

    return {
        "current": current,
        "rsi": round(rsi, 1),
        "ma50": ma50,
        "ma200": ma200,
        "ma200_extension_pct": round(ma200_extension_pct, 1),
        "avg_vol_20": avg_vol_20,
        "above_ma50": current > ma50,
        "above_ma200": current > ma200,
    }
