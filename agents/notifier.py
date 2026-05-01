import html
import os
import requests

TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SAFE_LIMIT = 3800


def _split_message(text: str, limit: int = TELEGRAM_SAFE_LIMIT) -> list[str]:
    """Split long Telegram messages on paragraph/word boundaries."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""

    def flush_current():
        nonlocal current
        if current:
            chunks.append(current.rstrip())
            current = ""

    for paragraph in text.split("\n\n"):
        block = paragraph if not current else f"\n\n{paragraph}"
        if len(current) + len(block) <= limit:
            current += block
            continue

        flush_current()
        if len(paragraph) <= limit:
            current = paragraph
            continue

        line = ""
        for word in paragraph.split(" "):
            addition = word if not line else f" {word}"
            if len(line) + len(addition) <= limit:
                line += addition
            else:
                if line:
                    chunks.append(line.rstrip())
                line = word
        current = line

    flush_current()
    return chunks or [text[:TELEGRAM_MESSAGE_LIMIT]]


def _send(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        for chunk in _split_message(text):
            print(f"[Telegram not configured]\n{chunk}\n")
        return

    for chunk in _split_message(text):
        try:
            resp = requests.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
                timeout=10,
            )
            if resp.status_code != 200:
                body_preview = (resp.text or "")[:200]
                print(f"Telegram non-200 status={resp.status_code}: {body_preview}")
        except requests.RequestException as e:
            print(f"Telegram send failed: {e}")


def _safe(value) -> str:
    """
    FIX [MEDIUM M-1]: HTML-escape any string that may have come from Claude
    or other untrusted sources before it lands in a parse_mode=HTML message.
    REASON: Telegram parses HTML mode strictly — an unescaped `<`, `>`, or `&`
        in a Claude-generated thesis could produce a 400 Bad Request from
        Telegram, and an attacker-controllable string could attempt to
        inject HTML tags that aren't part of the supported subset.
    SOLUTION: html.escape every Claude-sourced string at interpolation.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def send_eod_report(
    portfolio_value: float,
    daily_return: float,
    spy_return: float,
    position_count: int,
    buys: int,
    adds: int,
    trims: int,
    exits: int,
    weekly_alpha: float,
    date_str: str,
) -> None:
    d_arrow = "▲" if daily_return >= 0 else "▼"
    s_arrow = "▲" if spy_return >= 0 else "▼"
    alpha = daily_return - spy_return
    a_sign = "+" if alpha >= 0 else ""

    text = (
        f"<b>Saboor EOD — {_safe(date_str)}</b>\n\n"
        f"Portfolio: <b>${portfolio_value:,.0f}</b>\n"
        f"Today: {d_arrow} {abs(daily_return):.2f}%  |  SPY: {s_arrow} {abs(spy_return):.2f}%\n"
        f"Alpha: <b>{a_sign}{alpha:.2f}%</b>\n\n"
        f"Positions: {position_count} open\n"
        f"Actions: {buys} buy  |  {adds} add  |  {trims} trim  |  {exits} exit\n\n"
        f"Weekly vs SPY: <b>{'+' if weekly_alpha >= 0 else ''}{weekly_alpha:.2f}%</b>"
    )
    _send(text)


def send_urgent(ticker: str, trigger: str, action: str) -> None:
    _send(
        f"<b>⚠️ Saboor Alert — {_safe(ticker)}</b>\n"
        f"Trigger: {_safe(trigger)}\n"
        f"Action: {_safe(action)}"
    )


def send_premarket_report(watchlist: list[dict], excluded_count: int) -> None:
    """Premarket candidates are internal only; Telegram reports confirmed trades."""
    return


def send_trade_report(actions: list[dict], date_str: str) -> None:
    executable = [
        item for item in actions
        if str(item.get("action", "")).lower() in {"buy", "add", "trim", "exit"}
    ]
    if not executable:
        return

    lines = []
    for item in executable:
        action = str(item.get("action", "")).upper()
        ticker = _safe(item.get("ticker", ""))
        shares = item.get("shares", 0)
        price = item.get("price", 0) or 0
        side_label = "SELL" if action in {"TRIM", "EXIT"} else "BUY"
        reason = _safe(item.get("reason") or item.get("thesis") or "No reason provided.")

        lines.append(
            f"<b>{side_label} {ticker}</b> — {action}\n"
            f"Shares: <b>{shares:g}</b> @ ${price:,.2f}\n"
            f"Reason: {reason}"
        )

    _send(
        f"<b>Saboor Trade Decision — {_safe(date_str)}</b>\n\n"
        + "\n\n".join(lines)
    )

