import json
import re
from datetime import date
from tools.claude_client import complete
from tools.alpaca_client import place_order, get_price
from agents.risk_guardian import validate_order, max_shares_for_position
from data.universe import get_universe
from db.queries import save_position, log_decision, mark_watchlist_acted, get_position_by_ticker, close_position

TRADER_SYSTEM = """You are Saboor's Trader. Make final buy/sell/hold decisions for today's session.

You think like Warren Buffett: only buy what makes sense at this price with a clear thesis.
Momentum confirms timing — it never overrides a weak fundamental case.

BUYING APPROACH — build a diversified portfolio:
- Buy as many watchlist stocks as position limits allow (target 10-12 positions)
- Prefer CORE positions — stable, multi-week holds that should not change daily
- Add TACTICAL positions only when momentum is exceptionally strong
- Deploy capital fully — idle cash does not beat the market

HOLDING APPROACH — patience is the edge:
- NEVER sell because a price dropped. A stock down 5%, 10%, even 15% is noise if the thesis is intact.
- The only valid reason to sell is a broken thesis: earnings collapse, business model disruption, or sector destruction.
- A stock being up is NOT a reason to sell core — let winners run.
- Conviction in the original thesis > short-term price anxiety.

SELLING:
- Tactical: handled automatically at EOD (3-day max hold). Do not sell tactical intraday on price alone.
- Core: hold through all volatility. Exit only when the fundamental reason you bought it no longer exists.

OUTPUT: JSON only.
{
  "buys":  [{"ticker": "...", "shares": number, "bucket": "core"|"tactical", "thesis": "..."}],
  "sells": [{"ticker": "...", "reason": "..."}],
  "holds": [{"ticker": "...", "reason": "..."}]
}"""


# FIX [CRITICAL C-2]: Validate Claude response fields before placing Alpaca orders.
# REASON: Claude is a non-deterministic upstream and must be treated as
#         untrusted input. Without validation, a hallucinated ticker, an
#         invalid bucket value, or an inflated share count could be sent
#         straight to Alpaca, resulting in failed orders or — worse —
#         oversized positions that break the risk model.
# SOLUTION: Constrain every Claude-supplied field to a strict allow-list
#         (universe membership, regex on ticker, bucket enum) and clamp
#         shares to the risk-model-derived max — never trust Claude's count.
_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
_VALID_BUCKETS = ("core", "tactical")


def _is_valid_ticker(ticker, universe: set[str]) -> bool:
    return (
        isinstance(ticker, str)
        and bool(_TICKER_RE.match(ticker))
        and ticker in universe
    )


def execute_trades(watchlist: list[dict], open_positions: list[dict]) -> dict:
    """
    Ask Claude to make decisions, then execute approved orders through Risk Guardian → Alpaca.
    Returns counts of executed buys and sells.
    """
    universe = set(get_universe())

    # Index watchlist by ticker for O(1) lookup of analyst-supplied weights and scores.
    watchlist_by_ticker = {item["ticker"]: item for item in watchlist if "ticker" in item}

    # Enrich watchlist with live price and analyst-weighted share quantity
    enriched_watchlist = []
    for item in watchlist:
        try:
            price = get_price(item["ticker"])
            weight = item.get("position_weight_pct")
            max_shares = max_shares_for_position(price, weight)
            enriched_watchlist.append({
                **item,
                "current_price": price,
                "max_shares": max_shares,
                "target_allocation_pct": weight or 8,
            })
        except Exception as e:
            print(f"  Price fetch failed for {item['ticker']}: {e}")

    user_msg = (
        f"Make trading decisions.\n\n"
        f"WATCHLIST:\n{json.dumps(enriched_watchlist, indent=2)}\n\n"
        f"OPEN POSITIONS:\n{json.dumps(open_positions, indent=2)}\n\n"
        "Return JSON with buys/sells/holds arrays."
    )

    try:
        decisions = complete(TRADER_SYSTEM, user_msg, as_json=True)
    except Exception as e:
        log_decision("market_open", None, "trader_error", str(e))
        return {"buys": 0, "sells": 0}

    executed_buys, executed_sells = 0, 0

    for buy in decisions.get("buys", []):
        ticker = buy.get("ticker")
        bucket = buy.get("bucket", "tactical")
        thesis = buy.get("thesis", "")

        # FIX [CRITICAL C-2]: Validate ticker is in our universe AND well-formed.
        if not _is_valid_ticker(ticker, universe):
            log_decision("market_open", ticker, "buy_rejected", f"invalid ticker: {ticker!r}")
            print(f"  REJECTED invalid ticker: {ticker!r}")
            continue

        # FIX [CRITICAL C-2]: Constrain bucket to the exact enum.
        if bucket not in _VALID_BUCKETS:
            log_decision("market_open", ticker, "buy_rejected", f"invalid bucket: {bucket!r}")
            print(f"  REJECTED {ticker}: invalid bucket {bucket!r}")
            continue

        try:
            price = get_price(ticker)
            wl_item = watchlist_by_ticker.get(ticker, {})
            weight = wl_item.get("position_weight_pct")

            # FIX [CRITICAL C-2]: Cap shares to risk-model maximum — never
            # trust Claude's share count. Treat its count as an upper bound
            # we may further reduce, never as a number we honor as-is.
            risk_max_shares = max_shares_for_position(price, weight)
            requested_shares = buy.get("shares", 0)
            try:
                requested_shares = int(requested_shares)
            except (TypeError, ValueError):
                requested_shares = 0
            shares = min(requested_shares, risk_max_shares)

            if shares <= 0:
                log_decision("market_open", ticker, "buy_rejected", "no shares (risk-cap or 0 requested)")
                print(f"  REJECTED {ticker}: 0 shares after risk cap")
                continue

            approved, reason = validate_order(ticker, "buy", shares, price, bucket, weight)

            if not approved:
                log_decision("market_open", ticker, "buy_rejected", reason)
                print(f"  REJECTED {ticker}: {reason}")
                continue

            order = place_order(ticker, "buy", shares)

            # FIX [HIGH H-5]: Pass scores when saving positions so the
            # decisions log and dashboard retain the analyst signal that
            # drove the entry.
            save_position(
                ticker,
                bucket,
                shares,
                price,
                thesis,
                date.today(),
                quality_score=wl_item.get("quality_score"),
                momentum_score=wl_item.get("momentum_score"),
                combined_score=wl_item.get("combined_score"),
            )
            mark_watchlist_acted(ticker)
            log_decision("market_open", ticker, "buy", thesis, order_id=order.get("id"))
            print(f"  BOUGHT {shares} {ticker} @ ${price:.2f} ({bucket})")
            executed_buys += 1

        except Exception as e:
            log_decision("market_open", ticker, "buy_error", str(e))
            print(f"  BUY ERROR {ticker}: {e}")

    for sell in decisions.get("sells", []):
        ticker = sell.get("ticker")
        reason = sell.get("reason", "trader_decision")

        # FIX [CRITICAL C-2]: Validate sell ticker too — the same untrusted-input
        # threat applies. We further require an open position, so universe
        # membership is implicitly enforced, but we still want a fast-fail
        # on malformed strings before they hit any code path.
        if not _is_valid_ticker(ticker, universe):
            log_decision("market_open", ticker, "sell_rejected", f"invalid ticker: {ticker!r}")
            print(f"  REJECTED invalid sell ticker: {ticker!r}")
            continue

        try:
            pos = get_position_by_ticker(ticker)
            if not pos:
                continue

            place_order(ticker, "sell", pos["shares"])
            close_price = get_price(ticker)
            close_position(ticker, close_price, reason)
            log_decision("market_open", ticker, "sell", reason)
            print(f"  SOLD {ticker}: {reason}")
            executed_sells += 1

        except Exception as e:
            log_decision("market_open", ticker, "sell_error", str(e))
            print(f"  SELL ERROR {ticker}: {e}")

    return {"buys": executed_buys, "sells": executed_sells}
