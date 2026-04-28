import os
import re
import requests
from datetime import date, timedelta

_raw_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")
BASE_URL = _raw_url[:-3] if _raw_url.endswith("/v2") else _raw_url
DATA_URL = "https://data.alpaca.markets"

# FIX [HIGH H-3]: Validate ticker symbols before use in URL paths.
# REASON: Untrusted ticker strings flow from Claude JSON output and external
#         data sources directly into URL path segments. An attacker-controlled
#         (or simply malformed) ticker could perform path traversal, hit
#         unintended endpoints, or break the request entirely.
# SOLUTION: Strict allow-list — uppercase A-Z, 1 to 5 characters. This matches
#         every ticker in our universe (and US equity convention generally).
_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


def _validate_ticker(ticker: str) -> str:
    """Raise ValueError if `ticker` is not a well-formed US equity symbol."""
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
        raise ValueError(f"Invalid ticker symbol: {ticker!r}")
    return ticker


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
    }


def get_portfolio() -> dict:
    resp = requests.get(f"{BASE_URL}/v2/account", headers=_headers(), timeout=15)
    resp.raise_for_status()
    acct = resp.json()

    # FIX [CRITICAL C-5]: Use equity delta for daily P&L instead of unrealized_pl.
    # REASON: `unrealized_pl` only reflects mark-to-market on currently open
    #         positions. Realized losses from closing positions intraday were
    #         being silently dropped — an obvious blind spot for the daily
    #         loss cap which is supposed to halt all trading at -2%.
    # SOLUTION: equity - last_equity is the true intraday P&L number Alpaca
    #         exposes for exactly this purpose; it captures both realized
    #         and unrealized changes since the prior session close.
    equity = float(acct.get("equity", 0) or 0)
    last_equity = float(acct.get("last_equity", 0) or 0)
    daily_pl = equity - last_equity

    return {
        "cash": float(acct["cash"]),
        "equity": equity,
        "total_value": float(acct["portfolio_value"]),
        "daily_pl": daily_pl,
    }


def get_positions() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/v2/positions", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return [
        {
            "ticker": p["symbol"],
            "shares": float(p["qty"]),
            "entry_price": float(p["avg_entry_price"]),
            "current_price": float(p["current_price"]),
            "market_value": float(p["market_value"]),
            "unrealized_pl": float(p["unrealized_pl"]),
            "unrealized_plpc": float(p["unrealized_plpc"]),
        }
        for p in resp.json()
    ]


def place_order(ticker: str, side: str, qty: float, order_type: str = "market") -> dict:
    # FIX [HIGH H-3]: validate ticker before it touches the order endpoint.
    _validate_ticker(ticker)
    if side not in ("buy", "sell"):
        raise ValueError(f"Invalid order side: {side!r}")

    payload = {
        "symbol": ticker,
        "qty": str(round(qty, 4)),
        "side": side,
        "type": order_type,
        "time_in_force": "day",
    }
    resp = requests.post(
        f"{BASE_URL}/v2/orders", json=payload, headers=_headers(), timeout=15
    )
    resp.raise_for_status()
    return resp.json()


def cancel_order(order_id: str) -> dict | None:
    # FIX [HIGH H-9]: cancel_order() now raises on HTTP error and returns the response body.
    # REASON: Silent failures here meant a stuck order could continue to consume
    #         buying power and skew portfolio metrics with no signal back to
    #         the caller. Callers had no way to know whether the cancel landed.
    # SOLUTION: raise_for_status() surfaces server-side rejections; we return
    #         the response JSON (or None for 204 No Content) so callers can act on it.
    resp = requests.delete(
        f"{BASE_URL}/v2/orders/{order_id}", headers=_headers(), timeout=15
    )
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def get_price(ticker: str) -> float:
    """Latest trade price via IEX feed (free tier, ~15 min delay pre-open)."""
    # FIX [HIGH H-3]: validate ticker before it lands in the URL path.
    _validate_ticker(ticker)
    resp = requests.get(
        f"{DATA_URL}/v2/stocks/{ticker}/trades/latest",
        params={"feed": "iex"},
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return float(resp.json()["trade"]["p"])


def get_bars(ticker: str, days: int = 60) -> list[dict]:
    """Return daily OHLCV bars, most recent last."""
    # FIX [HIGH H-3]: validate ticker before it lands in the URL path.
    _validate_ticker(ticker)
    end = date.today()
    start = end - timedelta(days=days + 45)  # buffer for weekends/holidays
    resp = requests.get(
        f"{DATA_URL}/v2/stocks/{ticker}/bars",
        params={
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": days + 45,
            "adjustment": "all",
            "feed": "iex",
        },
        headers=_headers(),
        timeout=20,
    )
    resp.raise_for_status()
    bars = resp.json().get("bars", [])
    return [
        {
            "date": b["t"],
            "open": b["o"],
            "high": b["h"],
            "low": b["l"],
            "close": b["c"],
            "volume": b["v"],
        }
        for b in bars
    ]


def get_spy_return_today() -> float:
    """SPY daily return for benchmark comparison."""
    bars = get_bars("SPY", days=5)
    if len(bars) < 2:
        return 0.0
    return (bars[-1]["close"] - bars[-2]["close"]) / bars[-2]["close"]
