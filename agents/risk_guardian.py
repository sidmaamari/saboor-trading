from tools.alpaca_client import get_bars
from db.queries import get_portfolio_value, get_open_positions_count, get_daily_pl

MAX_POSITION_PCT = 0.13       # 13% of portfolio per position
DAILY_LOSS_CAP_PCT = 0.02     # 2% daily loss halts all trading
MAX_CORE_POSITIONS = 5
MAX_TACTICAL_POSITIONS = 2
TACTICAL_INTRADAY_STOP = -0.03  # -3% stop loss
TACTICAL_MAX_DAYS = 3

RSI_BLOCK_THRESHOLD = 78       # don't buy overbought stocks
MA200_EXTENSION_BLOCK = 1.5    # don't buy >150% above MA200


def _live_entry_check(ticker: str) -> tuple[bool, str]:
    """Re-checks RSI and MA200 extension at order time using fresh bars."""
    try:
        bars = get_bars(ticker, days=210)
        if len(bars) < 55:
            return True, "ok"
        closes = [b["close"] for b in bars]
        current = closes[-1]
        ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sum(closes) / len(closes)

        deltas = [closes[-i] - closes[-i - 1] for i in range(1, 15)]
        gains = [d for d in deltas if d > 0]
        losses = [abs(d) for d in deltas if d < 0]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14 if losses else 0.001
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        if rsi > RSI_BLOCK_THRESHOLD:
            return False, f"RSI {rsi:.0f} > {RSI_BLOCK_THRESHOLD} at order time — overbought, skipping"
        if current > ma200 * (1 + MA200_EXTENSION_BLOCK):
            ext = (current / ma200 - 1) * 100
            return False, f"Price {ext:.0f}% above MA200 at order time — too extended, skipping"
        return True, "ok"
    except Exception:
        return True, "ok"  # don't block on data errors


def validate_order(
    ticker: str, side: str, shares: float, price: float, bucket: str
) -> tuple[bool, str]:
    """
    Final gate before any buy order touches Alpaca.
    Returns (approved: bool, reason: str).
    Sell orders are always approved — never block an exit.
    """
    if side == "sell":
        return True, "sell approved"

    # Live entry quality check — re-run at order time, not just at premarket scoring
    ok, reason = _live_entry_check(ticker)
    if not ok:
        return False, reason

    portfolio = get_portfolio_value()
    total_value = portfolio["total_value"]

    if total_value <= 0:
        return False, "Portfolio value unavailable"

    # Position size
    order_value = shares * price
    max_allowed = total_value * MAX_POSITION_PCT
    if order_value > max_allowed:
        max_shares = int(max_allowed / price)
        return False, (
            f"Order value ${order_value:,.0f} exceeds 13% cap "
            f"(${max_allowed:,.0f}). Resize to {max_shares} shares."
        )

    # Daily loss cap
    daily_pl = get_daily_pl()
    loss_cap = -(total_value * DAILY_LOSS_CAP_PCT)
    if daily_pl <= loss_cap:
        return False, f"Daily loss cap hit: ${daily_pl:,.0f} (limit ${loss_cap:,.0f})"

    # Max positions
    counts = get_open_positions_count()
    if bucket == "core" and counts["core"] >= MAX_CORE_POSITIONS:
        return False, f"Core position limit reached ({MAX_CORE_POSITIONS})"
    if bucket == "tactical" and counts["tactical"] >= MAX_TACTICAL_POSITIONS:
        return False, f"Tactical position limit reached ({MAX_TACTICAL_POSITIONS})"

    return True, "approved"


def is_daily_loss_cap_hit() -> bool:
    portfolio = get_portfolio_value()
    total_value = portfolio["total_value"]
    if total_value <= 0:
        return False
    return get_daily_pl() <= -(total_value * DAILY_LOSS_CAP_PCT)


def max_shares_for_position(price: float) -> int:
    """Maximum shares allowed for a new position at the given price."""
    portfolio = get_portfolio_value()
    total_value = portfolio["total_value"]
    if price <= 0 or total_value <= 0:
        return 0
    return int((total_value * MAX_POSITION_PCT) / price)


def get_tactical_positions_to_close() -> list[str]:
    """
    Returns tickers of tactical positions that must be closed:
    - Hit the -3% intraday stop, OR
    - Held for 3+ trading days without being reclassified as core
    """
    from db.queries import get_open_positions

    positions = get_open_positions(bucket="tactical")
    to_close = []

    for p in positions:
        current = p.get("current_price") or p["entry_price"]
        pnl_pct = (current - p["entry_price"]) / p["entry_price"]

        if pnl_pct <= TACTICAL_INTRADAY_STOP:
            to_close.append((p["ticker"], "-3% stop hit"))
        elif p["days_held"] >= TACTICAL_MAX_DAYS:
            to_close.append((p["ticker"], f"max hold ({TACTICAL_MAX_DAYS} days) reached"))

    return to_close
