import json
from datetime import date
from tools.claude_client import complete
from tools.alpaca_client import place_order, get_price
from agents.risk_guardian import validate_order, max_shares_for_position
from db.queries import save_position, log_decision, mark_watchlist_acted, get_position_by_ticker, close_position

TRADER_SYSTEM = """You are Saboor's Trader. Make final buy/sell/hold decisions for today's session.

You think like Warren Buffett: only buy what makes sense at this price with a clear thesis.
Momentum confirms timing — it never overrides a weak fundamental case.

BUYING APPROACH — build a diversified portfolio:
- Buy as many watchlist stocks as position limits allow (target 10-12 positions)
- Prefer CORE positions — stable, multi-week holds that should not change daily
- Add TACTICAL positions only when momentum is exceptionally strong
- Deploy capital fully — idle cash does not beat the market

HOLDING APPROACH — stability is a feature, not a bug:
- Do NOT sell a CORE position unless: stop-loss is hit, or the fundamental thesis is clearly broken
- A stock being down 1-2% is NOT a reason to sell — that is normal noise
- A stock being up is NOT a reason to sell core — let winners run
- Only recommend SELL for core when earnings disappoint, sector disrupts, or stop is breached

SELLING:
- Tactical: handled automatically by midday/EOD (3-day max, -3% stop)
- Core: hold through volatility, exit only on fundamental change

OUTPUT: JSON only.
{
  "buys":  [{"ticker": "...", "shares": number, "bucket": "core"|"tactical", "thesis": "..."}],
  "sells": [{"ticker": "...", "reason": "..."}],
  "holds": [{"ticker": "...", "reason": "..."}]
}"""


def execute_trades(watchlist: list[dict], open_positions: list[dict]) -> dict:
    """
    Ask Claude to make decisions, then execute approved orders through Risk Guardian → Alpaca.
    Returns counts of executed buys and sells.
    """
    # Enrich watchlist with live price and approved share quantity
    enriched_watchlist = []
    for item in watchlist:
        try:
            price = get_price(item["ticker"])
            max_shares = max_shares_for_position(price)
            enriched_watchlist.append({**item, "current_price": price, "max_shares": max_shares})
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
        shares = buy.get("shares", 0)
        bucket = buy.get("bucket", "tactical")
        thesis = buy.get("thesis", "")

        if not ticker or shares <= 0:
            continue

        try:
            price = get_price(ticker)
            approved, reason = validate_order(ticker, "buy", shares, price, bucket)

            if not approved:
                log_decision("market_open", ticker, "buy_rejected", reason)
                print(f"  REJECTED {ticker}: {reason}")
                continue

            order = place_order(ticker, "buy", shares)
            save_position(ticker, bucket, shares, price, thesis, date.today())
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

        if not ticker:
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
