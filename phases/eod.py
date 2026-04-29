"""
EOD phase — 3:30 PM ET
Records benchmark performance and sends Telegram EOD report.
"""
from datetime import date
from tools.alpaca_client import get_portfolio, get_spy_return_today
from agents.notifier import send_eod_report
from db.queries import (
    get_open_positions, log_decision, save_benchmark, get_weekly_alpha,
    get_todays_decisions, get_previous_portfolio_value, sync_portfolio
)


def run():
    today = date.today()
    print(f"\n{'='*50}")
    print(f"Saboor EOD — {today}")
    print(f"{'='*50}")

    log_decision("eod", None, "phase_start", "EOD phase started")

    try:
        portfolio = get_portfolio()
        sync_portfolio(
            portfolio["cash"], portfolio["equity"],
            portfolio["total_value"], portfolio["daily_pl"]
        )
    except Exception as e:
        log_decision("eod", None, "portfolio_sync_error", str(e))
        print(f"Portfolio sync failed: {e}")
        return

    spy_return = get_spy_return_today()
    prev_value = get_previous_portfolio_value(before_date=today)
    daily_return = (
        (portfolio["total_value"] - prev_value) / prev_value * 100
        if prev_value else 0.0
    )

    save_benchmark(today, portfolio["total_value"], daily_return, spy_return * 100)
    weekly_alpha = get_weekly_alpha()

    decisions = get_todays_decisions()
    buys = sum(1 for d in decisions if d["action"] == "buy")
    adds = sum(1 for d in decisions if d["action"] == "add")
    trims = sum(1 for d in decisions if d["action"] == "trim")
    exits = sum(1 for d in decisions if d["action"] == "exit")
    open_positions = get_open_positions()

    send_eod_report(
        portfolio_value=portfolio["total_value"],
        daily_return=daily_return,
        spy_return=spy_return * 100,
        position_count=len(open_positions),
        buys=buys,
        adds=adds,
        trims=trims,
        exits=exits,
        weekly_alpha=weekly_alpha,
        date_str=today.strftime("%b %d, %Y"),
    )

    print(
        f"\nEOD complete — Portfolio: ${portfolio['total_value']:,.0f} "
        f"({daily_return:+.2f}% vs SPY {spy_return*100:+.2f}%)"
    )
    print(f"Open positions: {len(open_positions)} | Weekly alpha: {weekly_alpha:+.2f}%")

    log_decision(
        "eod", None, "phase_complete",
        f"Portfolio: ${portfolio['total_value']:,.0f} | Daily: {daily_return:+.2f}% | SPY: {spy_return*100:+.2f}%"
    )
