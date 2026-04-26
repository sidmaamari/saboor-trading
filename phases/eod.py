"""
EOD phase — 3:30 PM ET
Closes remaining tactical positions, records benchmark, sends Telegram EOD report.
"""
from datetime import date
from tools.alpaca_client import get_portfolio, get_spy_return_today, get_price, place_order
from agents.notifier import send_eod_report
from db.queries import (
    get_open_positions, get_position_by_ticker, close_position,
    log_decision, save_benchmark, get_weekly_alpha, get_todays_decisions,
    get_previous_portfolio_value, sync_portfolio
)


def run():
    today = date.today()
    print(f"\n{'='*50}")
    print(f"Saboor EOD — {today}")
    print(f"{'='*50}")

    log_decision("eod", None, "phase_start", "EOD phase started")

    # Force-close all remaining tactical positions
    tactical = get_open_positions(bucket="tactical")
    tactical_closed = 0

    for pos in tactical:
        try:
            current_price = get_price(pos["ticker"])
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
            reason = "eod_underperforming" if pnl_pct <= 0 else "eod_close"
            place_order(pos["ticker"], "sell", pos["shares"])
            close_position(pos["ticker"], current_price, reason)
            log_decision("eod", pos["ticker"], "eod_close", reason)
            print(f"  Closed tactical {pos['ticker']} @ ${current_price:.2f} ({pnl_pct:+.1%})")
            tactical_closed += 1
        except Exception as e:
            log_decision("eod", pos["ticker"], "close_error", str(e))
            print(f"  CLOSE ERROR {pos['ticker']}: {e}")

    # Final portfolio snapshot
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

    # Benchmark
    spy_return = get_spy_return_today()
    prev_value = get_previous_portfolio_value()
    daily_return = (
        (portfolio["total_value"] - prev_value) / prev_value * 100
        if prev_value else 0.0
    )

    save_benchmark(today, portfolio["total_value"], daily_return, spy_return * 100)

    weekly_alpha = get_weekly_alpha()

    # Trade counts for the day
    decisions = get_todays_decisions()
    buys = sum(1 for d in decisions if d["action"] == "buy")
    sells = sum(1 for d in decisions if d["action"] in ("sell", "forced_close", "eod_close"))

    # EOD Telegram report
    core_positions = get_open_positions(bucket="core")
    send_eod_report(
        portfolio_value=portfolio["total_value"],
        daily_return=daily_return,
        spy_return=spy_return * 100,
        core_count=len(core_positions),
        tactical_closed=tactical_closed,
        buys=buys,
        sells=sells,
        weekly_alpha=weekly_alpha,
        date_str=today.strftime("%b %d, %Y"),
    )

    print(
        f"\nEOD complete — Portfolio: ${portfolio['total_value']:,.0f} "
        f"({daily_return:+.2f}% vs SPY {spy_return*100:+.2f}%)"
    )
    print(f"Weekly alpha: {weekly_alpha:+.2f}%")

    log_decision(
        "eod", None, "phase_complete",
        f"Portfolio: ${portfolio['total_value']:,.0f} | Daily: {daily_return:+.2f}% | SPY: {spy_return*100:+.2f}%"
    )
