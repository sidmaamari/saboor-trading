from db.queries import get_portfolio_value, get_open_positions_count, get_daily_pl

MAX_POSITION_PCT = 0.13       # 13% of portfolio per position
DAILY_LOSS_CAP_PCT = 0.02     # 2% daily loss halts all trading
MAX_CORE_POSITIONS = 5
MAX_TACTICAL_POSITIONS = 2
TACTICAL_INTRADAY_STOP = -0.03  # -3% stop loss
TACTICAL_MAX_DAYS = 3


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
