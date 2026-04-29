from tools.alpaca_client import get_bars
from tools.technical import calculate_signals
from db.queries import get_portfolio_value, get_position_by_ticker

MAX_POSITION_PCT = 0.14
RSI_BLOCK_THRESHOLD = 78
MA200_EXTENSION_BLOCK = 1.5


def _live_entry_check(ticker: str) -> tuple[bool, str]:
    """Re-check RSI and MA200 extension for new buys/adds using fresh bars."""
    try:
        bars = get_bars(ticker, days=210)
        if len(bars) < 55:
            return True, "ok"

        signals = calculate_signals(
            [b["close"] for b in bars],
            [b["volume"] for b in bars],
        )
        rsi = signals["rsi"]
        current = signals["current"]
        ma200 = signals["ma200"]

        if rsi > RSI_BLOCK_THRESHOLD:
            return False, f"RSI {rsi:.0f} > {RSI_BLOCK_THRESHOLD}; buy/add blocked"
        if ma200 > 0 and current > ma200 * (1 + MA200_EXTENSION_BLOCK):
            ext = (current / ma200 - 1) * 100
            return False, f"Price {ext:.0f}% above MA200; buy/add blocked"
        return True, "ok"
    except Exception as e:
        return False, f"entry check failed ({e}); skipping to protect capital"


def _position_value_after_order(ticker: str, shares: float, price: float, side: str) -> float:
    current = get_position_by_ticker(ticker)
    current_shares = float(current.get("shares", 0)) if current else 0.0
    if side in ("buy", "add"):
        return (current_shares + shares) * price
    if side in ("sell", "trim"):
        return max(current_shares - shares, 0) * price
    return current_shares * price


def validate_order(
    ticker: str,
    side: str,
    shares: float,
    price: float,
    bucket: str = "core",
    position_weight_pct: float = None,
) -> tuple[bool, str]:
    """
    Final gate before an order touches Alpaca.
    Buys/adds are blocked by entry filters and the 14% cap.
    Trims/exits are allowed once request shape is valid.
    """
    if shares <= 0:
        return False, "Share quantity must be positive"
    if price <= 0:
        return False, "Price unavailable"

    side = "add" if side == "buy" and get_position_by_ticker(ticker) else side

    if side in ("sell", "trim", "exit"):
        return True, "exit/trim approved"

    if side not in ("buy", "add"):
        return False, f"Unsupported order side: {side!r}"

    ok, reason = _live_entry_check(ticker)
    if not ok:
        return False, reason

    portfolio = get_portfolio_value()
    total_value = float(portfolio.get("total_value", 0) or 0)
    if total_value <= 0:
        return False, "Portfolio value unavailable"

    new_position_value = _position_value_after_order(ticker, shares, price, side)
    max_allowed = total_value * MAX_POSITION_PCT
    if new_position_value > max_allowed:
        max_total_shares = int(max_allowed / price)
        return False, (
            f"Position would be ${new_position_value:,.0f}, above 14% cap "
            f"(${max_allowed:,.0f}). Max total shares: {max_total_shares}."
        )

    return True, "approved"


def max_shares_for_position(price: float, position_weight_pct: float = None, ticker: str = None) -> int:
    """Maximum additional shares while respecting analyst target and the 14% hard cap."""
    portfolio = get_portfolio_value()
    total_value = float(portfolio.get("total_value", 0) or 0)
    if price <= 0 or total_value <= 0:
        return 0

    target_pct = min((position_weight_pct or 6) / 100, MAX_POSITION_PCT)
    max_value = total_value * target_pct
    existing_value = 0.0
    if ticker:
        existing = get_position_by_ticker(ticker)
        if existing:
            existing_value = float(existing.get("shares", 0) or 0) * price
    return max(int((max_value - existing_value) / price), 0)
