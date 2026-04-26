"""
Market open phase — 9:35 AM ET
Executes trades from today's watchlist. Risk Guardian gates every order.
"""
from datetime import date
from tools.alpaca_client import get_portfolio
from agents.risk_guardian import is_daily_loss_cap_hit
from agents.trader import execute_trades
from agents.notifier import send_daily_loss_cap_alert
from db.queries import get_todays_watchlist, get_open_positions, log_decision, get_daily_pl, sync_portfolio


def run():
    today = date.today()
    print(f"\n{'='*50}")
    print(f"Saboor MARKET OPEN — {today}")
    print(f"{'='*50}")

    log_decision("market_open", None, "phase_start", "Market open phase started")

    # Sync portfolio state from Alpaca
    try:
        portfolio = get_portfolio()
        sync_portfolio(
            portfolio["cash"], portfolio["equity"],
            portfolio["total_value"], portfolio["daily_pl"]
        )
        print(f"\nPortfolio: ${portfolio['total_value']:,.0f} | Cash: ${portfolio['cash']:,.0f}")
    except Exception as e:
        log_decision("market_open", None, "portfolio_sync_error", str(e))
        print(f"Portfolio sync failed: {e}")
        return

    # Hard stop — daily loss cap check
    if is_daily_loss_cap_hit():
        pl = get_daily_pl()
        send_daily_loss_cap_alert(pl, portfolio["total_value"])
        log_decision("market_open", None, "halted", "Daily loss cap hit — no new trades")
        print("🛑 Daily loss cap hit. Trading halted.")
        return

    # Load watchlist and current positions
    watchlist = get_todays_watchlist()
    open_positions = get_open_positions()

    if not watchlist:
        log_decision("market_open", None, "no_watchlist", "No watchlist available")
        print("No watchlist for today — run premarket phase first.")
        return

    print(f"\nWatchlist: {len(watchlist)} stocks | Open positions: {len(open_positions)}")

    # Execute
    result = execute_trades(watchlist, open_positions)

    log_decision(
        "market_open", None, "phase_complete",
        f"Executed {result['buys']} buys, {result['sells']} sells"
    )
    print(f"\nDone: {result['buys']} buys, {result['sells']} sells")
    return result
