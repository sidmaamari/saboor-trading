import os
import requests

TELEGRAM_API = "https://api.telegram.org"


def _send(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print(f"[Telegram not configured]\n{text}\n")
        return

    try:
        requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"Telegram send failed: {e}")


def send_eod_report(
    portfolio_value: float,
    daily_return: float,
    spy_return: float,
    core_count: int,
    tactical_closed: int,
    buys: int,
    sells: int,
    weekly_alpha: float,
    date_str: str,
) -> None:
    d_arrow = "▲" if daily_return >= 0 else "▼"
    s_arrow = "▲" if spy_return >= 0 else "▼"
    alpha = daily_return - spy_return
    a_sign = "+" if alpha >= 0 else ""

    text = (
        f"<b>Saboor EOD — {date_str}</b>\n\n"
        f"Portfolio: <b>${portfolio_value:,.0f}</b>\n"
        f"Today: {d_arrow} {abs(daily_return):.2f}%  |  SPY: {s_arrow} {abs(spy_return):.2f}%\n"
        f"Alpha: <b>{a_sign}{alpha:.2f}%</b>\n\n"
        f"Positions: {core_count} Core open  |  {tactical_closed} Tactical closed\n"
        f"Trades: {buys} buy  |  {sells} sell\n\n"
        f"Weekly vs SPY: <b>{'+' if weekly_alpha >= 0 else ''}{weekly_alpha:.2f}%</b>"
    )
    _send(text)


def send_urgent(ticker: str, trigger: str, action: str) -> None:
    _send(
        f"<b>⚠️ Saboor Alert — {ticker}</b>\n"
        f"Trigger: {trigger}\n"
        f"Action: {action}"
    )


def send_daily_loss_cap_alert(daily_pl: float, portfolio_value: float) -> None:
    pct = abs(daily_pl / portfolio_value * 100) if portfolio_value else 0
    _send(
        f"<b>🛑 Saboor: Daily Loss Cap Hit</b>\n\n"
        f"Loss: <b>${abs(daily_pl):,.0f} ({pct:.1f}%)</b>\n"
        f"All new trading halted for today.\n"
        f"Existing Core positions are held."
    )
