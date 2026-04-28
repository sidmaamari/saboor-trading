"""
Midday phase — 12:00 PM ET
Reassesses open positions. Closes tactical positions that hit stops or max hold days.
Only sends Telegram if something urgent happens.
"""
from datetime import date
from tools.alpaca_client import get_portfolio, get_price, place_order
from agents.risk_guardian import is_daily_loss_cap_hit, get_tactical_positions_to_close
from agents.notifier import send_daily_loss_cap_alert, send_urgent
from db.queries import (
    get_open_positions, get_position_by_ticker, close_position,
    log_decision, get_daily_pl, sync_portfolio
)


def run():
    today = date.today()
    print(f"\n{'='*50}")
    print(f"Saboor MIDDAY — {today}")
    print(f"{'='*50}")

    log_decision("midday", None, "phase_start", "Midday phase started")

    # FIX [CRITICAL C-6]: Initialize `portfolio` before the try block.
    # REASON: The previous code relied on `"portfolio" in dir()` to detect
    #         whether the assignment landed inside the try. `dir()` is
    #         unreliable across Python implementations and shadowing rules,
    #         and worse — once `portfolio` was set in any prior call (it
    #         won't be in a fresh process, but it's still a fragile pattern),
    #         the check would pass even if THIS try block had failed.
    # SOLUTION: Bind `portfolio = None` before the try, then explicitly
    #         check `if portfolio is None` later. Plain, idiomatic Python.
    portfolio = None

    # Refresh portfolio state
    try:
        portfolio = get_portfolio()
        sync_portfolio(
            portfolio["cash"], portfolio["equity"],
            portfolio["total_value"], portfolio["daily_pl"]
        )
        print(f"\nPortfolio: ${portfolio['total_value']:,.0f} | Daily P&L: ${portfolio['daily_pl']:+,.0f}")
    except Exception as e:
        log_decision("midday", None, "portfolio_sync_error", str(e))

    # Daily loss cap check
    if is_daily_loss_cap_hit():
        pl = get_daily_pl()
        pv = portfolio.get("total_value", 0) if portfolio is not None else 0
        send_daily_loss_cap_alert(pl, pv)
        log_decision("midday", None, "halted", "Daily loss cap hit")
        print("🛑 Daily loss cap hit. No midday activity.")
        return

    # Close tactical positions that hit stop or max days
    to_close = get_tactical_positions_to_close()
    closed = 0

    for ticker, reason in to_close:
        try:
            pos = get_position_by_ticker(ticker)
            if not pos:
                continue

            current_price = get_price(ticker)
            place_order(ticker, "sell", pos["shares"])
            close_position(ticker, current_price, reason)
            send_urgent(ticker, reason, f"Closed at ${current_price:.2f}")
            log_decision("midday", ticker, "forced_close", reason)
            print(f"  CLOSED {ticker}: {reason} @ ${current_price:.2f}")
            closed += 1

        except Exception as e:
            log_decision("midday", ticker, "close_error", str(e))
            print(f"  CLOSE ERROR {ticker}: {e}")

    open_positions = get_open_positions()
    print(f"\nOpen positions: {len(open_positions)} | Closed today: {closed}")

    log_decision("midday", None, "phase_complete", f"Closed {closed} positions at midday")
