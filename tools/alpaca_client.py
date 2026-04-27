import os
import requests
from datetime import date, timedelta

_raw_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")
BASE_URL = _raw_url[:-3] if _raw_url.endswith("/v2") else _raw_url
DATA_URL = "https://data.alpaca.markets"


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
    }


def get_portfolio() -> dict:
    resp = requests.get(f"{BASE_URL}/v2/account", headers=_headers(), timeout=15)
    resp.raise_for_status()
    acct = resp.json()
    return {
        "cash": float(acct["cash"]),
        "equity": float(acct["equity"]),
        "total_value": float(acct["portfolio_value"]),
        "daily_pl": float(acct.get("unrealized_pl", 0)),
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


def cancel_order(order_id: str) -> None:
    requests.delete(
        f"{BASE_URL}/v2/orders/{order_id}", headers=_headers(), timeout=15
    )


def get_price(ticker: str) -> float:
    """Latest trade price via IEX feed (free tier, ~15 min delay pre-open)."""
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
