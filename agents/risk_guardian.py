from tools.alpaca_client import get_bars
from tools.technical import calculate_signals
from db.queries import get_portfolio_value, get_open_positions_count, get_daily_pl

MAX_POSITION_PCT = 0.13       # hard cap — no single position exceeds 13%
DAILY_LOSS_CAP_PCT = 0.02     # 2% daily loss halts all trading
MAX_CORE_POSITIONS = 8
MAX_TACTICAL_POSITIONS = 4
TACTICAL_MAX_DAYS = 3

RSI_BLOCK_THRESHOLD = 78       # don't buy overbought stocks
MA200_EXTENSION_BLOCK = 1.5    # don't buy >150% above MA200


def _live_entry_check(ticker: str) -> tuple[bool, str]:
    """Re-checks RSI and MA200 extension at order time using fresh bars."""
    try:
        bars = get_bars(ticker, days=210)
        if len(bars) < 55:
            return True, "ok"

        # FIX [HIGH H-12]: Use shared calculator instead of duplicating the math here.
        # REASON: The Analyst and Risk Guardian had two divergent copies of
        #         the RSI/MA200 calculation, which is a correctness hazard —
        #         a fix in one is silently absent from the other.
        # SOLUTION: Single source of truth in tools/technical.py.
        signals = calculate_signals(
            [b["close"] for b in bars],
            [b["volume"] for b in bars],
        )
        rsi = signals["rsi"]
        current = signals["current"]
        ma200 = signals["ma200"]

        if rsi > RSI_BLOCK_THRESHOLD:
            return False, f"RSI {rsi:.0f} > {RSI_BLOCK_THRESHOLD} at order time — overbought, skipping"
        if ma200 > 0 and current > ma200 * (1 + MA200_EXTENSION_BLOCK):
            ext = (current / ma200 - 1) * 100
            return False, f"Price {ext:.0f}% above MA200 at order time — too extended, skipping"
        return True, "ok"
    except Exception as e:
        # FIX [CRITICAL C-4]: Fail closed, not open.
        # REASON: The previous behavior swallowed every error and returned
        #         (True, "ok"), meaning a transient data-feed issue would
        #         silently bypass the live entry check and let a possibly
        #         overbought trade through. Capital preservation requires
        #         the opposite default — when in doubt, don't trade.
        # SOLUTION: Block the entry on any exception and surface the error
        #         in the rejection reason so it appears in the decision log.
        return False, f"entry check failed ({e}) — skipping to protect capital"


def validate_order(
    ticker: str, side: str, shares: float, price: float, bucket: str,
    position_weight_pct: float = None,
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

    # Position size — use analyst weight if provided, else fall back to hard cap
    order_value = shares * price
    target_pct = min((position_weight_pct or 100) / 100, MAX_POSITION_PCT)
    max_allowed = total_value * target_pct
    if order_value > max_allowed:
        max_shares = int(max_allowed / price)
        return False, (
            f"Order ${order_value:,.0f} exceeds {target_pct*100:.0f}% target "
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


def max_shares_for_position(price: float, position_weight_pct: float = None) -> int:
    """Shares for a position sized by analyst weight (capped at 13%)."""
    portfolio = get_portfolio_value()
    total_value = portfolio["total_value"]
    if price <= 0 or total_value <= 0:
        return 0
    target_pct = min((position_weight_pct or 100) / 100, MAX_POSITION_PCT)
    return int((total_value * target_pct) / price)


def get_tactical_positions_to_close() -> list[str]:
    """
    Returns tickers of tactical positions to close: held for 3+ trading days.
    Price drops alone are never a reason to close — only a broken thesis is.
    """
    from db.queries import get_open_positions

    positions = get_open_positions(bucket="tactical")
    to_close = []

    for p in positions:
        if p["days_held"] >= TACTICAL_MAX_DAYS:
            to_close.append((p["ticker"], f"max hold ({TACTICAL_MAX_DAYS} days) reached"))

    return to_close
