"""
Midday phase — 12:00 PM ET
Monitors portfolio state and urgent thesis/compliance changes.
No tactical auto-closing exists in the Buffett-style strategy.
"""
from datetime import date
from tools.alpaca_client import get_portfolio
from db.queries import get_open_positions, log_decision, sync_portfolio


def run():
    today = date.today()
    print(f"\n{'='*50}")
    print(f"Saboor MIDDAY — {today}")
    print(f"{'='*50}")

    log_decision("midday", None, "phase_start", "Midday monitoring phase started")

    try:
        portfolio = get_portfolio()
        sync_portfolio(
            portfolio["cash"], portfolio["equity"],
            portfolio["total_value"], portfolio["daily_pl"]
        )
        print(f"\nPortfolio: ${portfolio['total_value']:,.0f} | Daily P&L: ${portfolio['daily_pl']:+,.0f}")
    except Exception as e:
        log_decision("midday", None, "portfolio_sync_error", str(e))
        print(f"Portfolio sync failed: {e}")

    open_positions = get_open_positions()
    print(f"\nOpen positions: {len(open_positions)} | No tactical auto-closes")

    log_decision("midday", None, "phase_complete", f"Reviewed {len(open_positions)} open positions")
