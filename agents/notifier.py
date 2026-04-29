import html
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
        # FIX [HIGH H-8]: Capture the response and check the HTTP status.
        # REASON: Previously a 401/429/5xx from Telegram would silently
        #         drop important portfolio alerts with no visible signal.
        # SOLUTION: Capture the response, log a warning on non-200 with the
        #         response body so misconfiguration (bad token, blocked bot,
        #         rate limiting) is immediately visible in the phase logs.
        resp = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            # Telegram surfaces useful detail in the response body — keep it bounded.
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
    if not watchlist:
        _send(
            f"<b>Saboor Pre-Market</b>\n\n"
            f"No stocks passed today's filters.\n"
            f"{excluded_count} candidates excluded (overbought/extended).\n"
            f"No trades will execute at open."
        )
        return

    lines = []
    for s in watchlist:
        ticker   = _safe(s.get("ticker", ""))
        quality  = s.get("quality_score", 0) or 0
        timing   = s.get("entry_timing_score") or s.get("momentum_score", 0) or 0
        combined = s.get("combined_score", 0) or 0
        weight   = s.get("position_weight_pct", 0) or 0
        sharia   = _safe(s.get("sharia_status", "compliant"))
        thesis   = _safe((s.get("thesis") or "")[:100])
        risks    = _safe((s.get("key_risks") or "")[:80])

        sharia_tag = "" if sharia == "compliant" else f" ⚠️ {sharia}"

        lines.append(
            f"• <b>{ticker}</b>{sharia_tag}  {weight:.0f}% target\n"
            f"  Q:{quality:.0f}  T:{timing:.0f}  Combined:{combined:.0f}/100\n"
            f"  {thesis}\n"
            f"  <i>Risk: {risks}</i>"
        )

    _send(
        f"<b>Saboor Pre-Market — {len(watchlist)} candidates</b>\n\n"
        + "\n\n".join(lines)
        + f"\n\n<i>{excluded_count} excluded by hard filters or below threshold</i>"
    )
