import json
import re
from datetime import date
from tools.claude_client import complete
from tools.alpaca_client import place_order, get_price
from agents.risk_guardian import validate_order, max_shares_for_position
from tools.macro_client import format_macro_context
from data.universe import get_universe
from db.queries import (
    save_position,
    reduce_position,
    log_decision,
    mark_watchlist_acted,
    get_position_by_ticker,
    close_position,
)

TRADER_SYSTEM = """You are Saboor's Trader. Saboor is a Buffett-style halal investing system with one portfolio and no tactical bucket.

You receive refreshed ownership candidates plus current open positions.

Valid actions:
- buy: open a new position from today's refreshed candidates
- add: increase an existing position only if refreshed candidate data supports the thesis
- hold: do nothing
- trim: reduce a position when valuation, concentration, conviction, or better opportunities justify it
- exit: close a position when thesis breaks, sharia status changes, intrinsic value falls, or forward expected return is unattractive

Rules:
- Never buy or add because of momentum alone.
- Never sell, trim, or exit only because price dropped.
- Cash is valid. Do not force deployment.
- Do not recommend token positions that are too small to matter.
- Respect the 14% hard cap that Risk Guardian will enforce.
- Treat AI as business economics, not hype.

OUTPUT JSON ONLY:
{
  "actions": [
    {
      "action": "buy" | "add" | "hold" | "trim" | "exit",
      "ticker": "AAPL",
      "shares": number,
      "trim_pct": number,
      "thesis": "required for buy/add",
      "reason": "required for hold/trim/exit"
    }
  ]
}"""

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
_VALID_ACTIONS = ("buy", "add", "hold", "trim", "exit")


def _is_valid_ticker(ticker, universe: set[str]) -> bool:
    return (
        isinstance(ticker, str)
        and bool(_TICKER_RE.match(ticker))
        and ticker in universe
    )


def _coerce_shares(value) -> int:
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return 0


def _coerce_trim_pct(value) -> float:
    try:
        return min(max(float(value), 0.0), 100.0)
    except (TypeError, ValueError):
        return 0.0


def _actions_from_decisions(decisions: dict) -> list[dict]:
    if isinstance(decisions, dict) and isinstance(decisions.get("actions"), list):
        return decisions["actions"]

    # Backward-compatible parsing if Claude returns the old shape.
    actions = []
    for buy in (decisions or {}).get("buys", []):
        actions.append({**buy, "action": "buy"})
    for sell in (decisions or {}).get("sells", []):
        actions.append({**sell, "action": "exit"})
    for hold in (decisions or {}).get("holds", []):
        actions.append({**hold, "action": "hold"})
    return actions


def execute_trades(
    watchlist: list[dict],
    open_positions: list[dict],
    macro: dict | None = None,
) -> dict:
    """
    Ask Claude for Buy/Add/Hold/Trim/Exit decisions, then execute approved orders.
    """
    universe = set(get_universe())
    watchlist_by_ticker = {item["ticker"]: item for item in watchlist if "ticker" in item}

    enriched_candidates = []
    for item in watchlist:
        ticker = item.get("ticker")
        try:
            price = get_price(ticker)
            weight = item.get("position_weight_pct")
            max_shares = max_shares_for_position(price, weight, ticker=ticker)
            enriched_candidates.append({
                **item,
                "current_price": price,
                "max_additional_shares": max_shares,
                "target_allocation_pct": min(weight or 6, 14),
            })
        except Exception as e:
            print(f"  Price fetch failed for {ticker}: {e}")

    macro_block = format_macro_context(macro or {})
    user_msg = (
        f"{macro_block}"
        "Make portfolio decisions under the Buffett-style strategy.\n\n"
        f"REFRESHED CANDIDATES:\n{json.dumps(enriched_candidates, indent=2)}\n\n"
        f"OPEN POSITIONS:\n{json.dumps(open_positions, indent=2)}\n\n"
        "Return JSON with an actions array."
    )

    try:
        decisions = complete(TRADER_SYSTEM, user_msg, as_json=True)
    except Exception as e:
        log_decision("market_open", None, "trader_error", str(e))
        return {"buys": 0, "adds": 0, "trims": 0, "exits": 0, "holds": 0, "sells": 0}

    counts = {"buys": 0, "adds": 0, "trims": 0, "exits": 0, "holds": 0, "sells": 0}

    for item in _actions_from_decisions(decisions):
        action = str(item.get("action", "")).lower()
        ticker = item.get("ticker")

        if action not in _VALID_ACTIONS:
            log_decision("market_open", ticker, "action_rejected", f"invalid action: {action!r}")
            continue
        if not _is_valid_ticker(ticker, universe):
            log_decision("market_open", ticker, f"{action}_rejected", f"invalid ticker: {ticker!r}")
            print(f"  REJECTED invalid ticker: {ticker!r}")
            continue

        if action == "hold":
            reason = item.get("reason", "thesis intact")
            log_decision("market_open", ticker, "hold", reason)
            counts["holds"] += 1
            continue

        try:
            price = get_price(ticker)
            pos = get_position_by_ticker(ticker)
            wl_item = watchlist_by_ticker.get(ticker)

            if action in ("buy", "add"):
                if not wl_item:
                    log_decision("market_open", ticker, f"{action}_rejected", "not in refreshed candidate list")
                    print(f"  REJECTED {ticker}: not in refreshed candidate list")
                    continue

                weight = wl_item.get("position_weight_pct")
                risk_max_shares = max_shares_for_position(price, weight, ticker=ticker)
                requested = _coerce_shares(item.get("shares"))
                shares = min(requested or risk_max_shares, risk_max_shares)

                if shares <= 0:
                    log_decision("market_open", ticker, f"{action}_rejected", "0 shares after 14% cap")
                    print(f"  REJECTED {ticker}: 0 shares after 14% cap")
                    continue

                approved, reason = validate_order(ticker, action, shares, price, "core", weight)
                if not approved:
                    log_decision("market_open", ticker, f"{action}_rejected", reason)
                    print(f"  REJECTED {ticker}: {reason}")
                    continue

                order = place_order(ticker, "buy", shares)
                thesis = item.get("thesis") or wl_item.get("thesis", "")
                save_position(
                    ticker,
                    "core",
                    shares,
                    price,
                    thesis,
                    date.today(),
                    quality_score=wl_item.get("quality_score"),
                    momentum_score=wl_item.get("momentum_score"),
                    combined_score=wl_item.get("combined_score"),
                )
                mark_watchlist_acted(ticker)
                actual_action = "add" if pos else "buy"
                log_decision("market_open", ticker, actual_action, thesis, order_id=order.get("id"))
                print(f"  {actual_action.upper()} {shares} {ticker} @ ${price:.2f}")
                counts["adds" if pos else "buys"] += 1
                continue

            if not pos:
                log_decision("market_open", ticker, f"{action}_rejected", "no open position")
                continue

            if action == "trim":
                shares = _coerce_shares(item.get("shares"))
                if shares <= 0:
                    trim_pct = _coerce_trim_pct(item.get("trim_pct"))
                    shares = int(float(pos.get("shares", 0) or 0) * trim_pct / 100)
                if shares <= 0:
                    log_decision("market_open", ticker, "trim_rejected", "no shares specified")
                    continue

                approved, reason = validate_order(ticker, "trim", shares, price)
                if not approved:
                    log_decision("market_open", ticker, "trim_rejected", reason)
                    continue

                place_order(ticker, "sell", shares)
                reduce_position(ticker, shares, price, item.get("reason", "valuation/concentration trim"))
                log_decision("market_open", ticker, "trim", item.get("reason", "trim"))
                print(f"  TRIMMED {shares} {ticker} @ ${price:.2f}")
                counts["trims"] += 1
                counts["sells"] += 1
                continue

            if action == "exit":
                shares = float(pos.get("shares", 0) or 0)
                approved, reason = validate_order(ticker, "exit", shares, price)
                if not approved:
                    log_decision("market_open", ticker, "exit_rejected", reason)
                    continue

                place_order(ticker, "sell", shares)
                close_position(ticker, price, item.get("reason", "strategy_exit"))
                log_decision("market_open", ticker, "exit", item.get("reason", "strategy_exit"))
                print(f"  EXITED {ticker} @ ${price:.2f}")
                counts["exits"] += 1
                counts["sells"] += 1

        except Exception as e:
            log_decision("market_open", ticker, f"{action}_error", str(e))
            print(f"  {action.upper()} ERROR {ticker}: {e}")

    return counts
