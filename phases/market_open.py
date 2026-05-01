"""
Market open phase — 9:35 AM ET
Reviews candidates and open positions. Risk Guardian gates every order.
"""
from datetime import date
from tools.alpaca_client import get_portfolio
from tools.macro_client import get_macro_snapshot
from agents.trader import execute_trades
from agents.notifier import send_trade_report
from db.queries import get_todays_watchlist, get_open_positions, log_decision, sync_portfolio


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

    # Load watchlist and current positions
    watchlist = get_todays_watchlist()
    open_positions = get_open_positions()

    if not watchlist and not open_positions:
        log_decision("market_open", None, "no_candidates_or_positions", "No candidates or positions to review")
        print("No candidates or open positions to review — run premarket first.")
        return

    print(f"\nCandidates: {len(watchlist)} stocks | Open positions: {len(open_positions)}")

    macro = get_macro_snapshot()
    if macro.get("ten_year_yield_pct"):
        print(f"  Macro: 10yr {macro['ten_year_yield_pct']:.2f}% | "
              f"3mo {macro.get('three_month_yield_pct', 'n/a')}% | "
              f"Spread {macro.get('yield_curve_spread_pct', 'n/a')}%")

    # Execute
    result = execute_trades(watchlist, open_positions, macro=macro)
    send_trade_report(result.get("executed_actions", []), today.strftime("%b %d, %Y"))

    log_decision(
        "market_open", None, "phase_complete",
        f"Buys {result['buys']}, adds {result['adds']}, trims {result['trims']}, exits {result['exits']}, holds {result['holds']}"
    )
    print(
        f"\nDone: {result['buys']} buys, {result['adds']} adds, "
        f"{result['trims']} trims, {result['exits']} exits, {result['holds']} holds"
    )
    return result
