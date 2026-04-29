"""
Macro context fetcher — yfinance only, no extra API key required.

Fetches current interest rate and yield curve data to inform valuation
discipline in the Analyst and Trader. This is context, not a signal:
it affects required margin of safety, forward return hurdle, and
debt/refinancing risk assessment — never a reason to buy or sell on its own.
"""
import yfinance as yf


def get_macro_snapshot() -> dict:
    """
    Returns current macro indicators. All fields default to None on failure
    so callers can render graceful fallback text rather than crashing.
    """
    snapshot = {
        "ten_year_yield_pct": None,
        "three_month_yield_pct": None,
        "yield_curve_spread_pct": None,
    }

    try:
        snapshot["ten_year_yield_pct"] = round(
            float(yf.Ticker("^TNX").fast_info.last_price), 2
        )
    except Exception:
        pass

    try:
        snapshot["three_month_yield_pct"] = round(
            float(yf.Ticker("^IRX").fast_info.last_price), 2
        )
    except Exception:
        pass

    t = snapshot["ten_year_yield_pct"]
    s = snapshot["three_month_yield_pct"]
    if t is not None and s is not None:
        snapshot["yield_curve_spread_pct"] = round(t - s, 2)

    return snapshot


def format_macro_context(snapshot: dict) -> str:
    """
    Render macro snapshot as a prompt-ready text block.
    Returns an empty string if no data is available.
    """
    lines = []

    t = snapshot.get("ten_year_yield_pct")
    s = snapshot.get("three_month_yield_pct")
    spread = snapshot.get("yield_curve_spread_pct")

    if t is not None:
        lines.append(f"10-year Treasury yield: {t:.2f}%")
    if s is not None:
        lines.append(f"3-month T-bill yield:   {s:.2f}%")
    if spread is not None:
        curve = "inverted" if spread < 0 else "normal"
        lines.append(f"Yield curve spread:     {spread:+.2f}% ({curve})")

    if not lines:
        return ""

    return (
        "MACRO CONTEXT (informational — not a buy/sell trigger):\n"
        + "\n".join(lines) + "\n\n"
        "Use this to:\n"
        "- Set required margin of safety (higher rates = higher hurdle return)\n"
        "- Assess debt and refinancing risk for leveraged companies\n"
        "- Judge durability of pricing power in this rate environment\n"
        "- Prefer cash over borderline opportunities when rates are high\n"
        "Do NOT buy because rates are falling. Do NOT sell because rates are high.\n"
    )
