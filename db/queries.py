from datetime import date, timedelta
from db.supabase_client import get_client


def init_db():
    """Tables live in Supabase — run db/supabase_schema.sql once in the Supabase SQL Editor."""
    print("Supabase tables are managed remotely.")
    print("If tables don't exist yet, run db/supabase_schema.sql in the Supabase SQL Editor.")


# ── Portfolio ─────────────────────────────────────────────────────────────────

def sync_portfolio(cash: float, equity: float, total_value: float, daily_pl: float):
    get_client().table("portfolio").insert({
        "cash": cash,
        "equity": equity,
        "total_value": total_value,
        "daily_pl": daily_pl,
    }).execute()


def get_portfolio_value() -> dict:
    resp = (
        get_client().table("portfolio")
        .select("*")
        .order("last_updated", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"cash": 0.0, "equity": 0.0, "total_value": 0.0, "daily_pl": 0.0}
    return resp.data[0]


def get_daily_pl() -> float:
    resp = (
        get_client().table("portfolio")
        .select("daily_pl")
        .order("last_updated", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return 0.0
    return float(resp.data[0].get("daily_pl", 0.0))


# ── Positions ─────────────────────────────────────────────────────────────────

def save_position(
    ticker: str,
    bucket: str,
    shares: float,
    entry_price: float,
    thesis: str,
    entry_date: date,
    quality_score: float = None,
    momentum_score: float = None,
    combined_score: float = None,
):
    get_client().table("positions").insert({
        "ticker": ticker,
        "bucket": bucket,
        "shares": shares,
        "entry_price": entry_price,
        "entry_date": entry_date.isoformat(),
        "thesis": thesis,
        "quality_score": quality_score,
        "momentum_score": momentum_score,
        "combined_score": combined_score,
        "status": "open",
    }).execute()


def get_open_positions(bucket: str = None) -> list[dict]:
    q = get_client().table("positions").select("*").eq("status", "open")
    if bucket:
        q = q.eq("bucket", bucket)
    resp = q.order("entry_date").execute()
    return resp.data or []


def get_open_positions_count() -> dict:
    core = get_client().table("positions").select("id").eq("status", "open").eq("bucket", "core").execute()
    tactical = get_client().table("positions").select("id").eq("status", "open").eq("bucket", "tactical").execute()
    return {"core": len(core.data or []), "tactical": len(tactical.data or [])}


def get_position_by_ticker(ticker: str) -> dict | None:
    resp = (
        get_client().table("positions")
        .select("*")
        .eq("ticker", ticker)
        .eq("status", "open")
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def close_position(ticker: str, close_price: float, reason: str):
    resp = (
        get_client().table("positions")
        .select("*")
        .eq("ticker", ticker)
        .eq("status", "open")
        .limit(1)
        .execute()
    )
    if not resp.data:
        return
    pos = resp.data[0]
    pnl = (close_price - pos["entry_price"]) * pos["shares"]
    get_client().table("positions").update({
        "status": "closed",
        "close_date": date.today().isoformat(),
        "close_price": close_price,
        "pnl": pnl,
        "close_reason": reason,
    }).eq("ticker", ticker).eq("status", "open").execute()


def update_positions_days_held():
    resp = get_client().table("positions").select("id, days_held").eq("status", "open").execute()
    for pos in (resp.data or []):
        get_client().table("positions").update({
            "days_held": (pos.get("days_held") or 0) + 1
        }).eq("id", pos["id"]).execute()


# ── Watchlist ─────────────────────────────────────────────────────────────────

def save_watchlist(trading_date: date, items: list[dict]):
    date_str = trading_date.isoformat()
    get_client().table("watchlist").delete().eq("date", date_str).execute()
    rows = [
        {
            "date": date_str,
            "ticker": item["ticker"],
            "quality_score": item.get("quality_score", 0),
            "momentum_score": item.get("momentum_score", 0),
            "combined_score": item.get("combined_score", 0),
            "bucket": item.get("bucket", "tactical"),
            "position_weight_pct": item.get("position_weight_pct", 8),
            "thesis": item.get("thesis", ""),
            "key_risks": item.get("key_risks", ""),
            "sharia_status": item.get("sharia_status", "compliant"),
        }
        for item in items
    ]
    if rows:
        get_client().table("watchlist").insert(rows).execute()


def get_todays_watchlist() -> list[dict]:
    resp = (
        get_client().table("watchlist")
        .select("*")
        .eq("date", date.today().isoformat())
        .eq("acted_on", False)
        .order("combined_score", desc=True)
        .execute()
    )
    return resp.data or []


def mark_watchlist_acted(ticker: str):
    get_client().table("watchlist").update({"acted_on": True}).eq(
        "ticker", ticker
    ).eq("date", date.today().isoformat()).execute()


# ── Decisions Log ─────────────────────────────────────────────────────────────

def log_decision(
    phase: str,
    ticker: str | None,
    action: str,
    reasoning: str = "",
    confidence: float = None,
    order_id: str = None,
):
    get_client().table("decisions_log").insert({
        "phase": phase,
        "ticker": ticker,
        "action": action,
        "reasoning": reasoning,
        "confidence": confidence,
        "order_id": order_id,
    }).execute()


def get_todays_decisions() -> list[dict]:
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = (
        get_client().table("decisions_log")
        .select("*")
        .gte("timestamp", f"{today}T00:00:00")
        .lt("timestamp", f"{tomorrow}T00:00:00")
        .order("timestamp")
        .execute()
    )
    return resp.data or []


# ── Benchmark ─────────────────────────────────────────────────────────────────

def get_previous_portfolio_value() -> float | None:
    resp = (
        get_client().table("benchmark")
        .select("portfolio_value")
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return float(resp.data[0]["portfolio_value"])


def save_benchmark(
    trading_date: date,
    portfolio_value: float,
    portfolio_return: float,
    spy_return: float,
):
    prev_resp = (
        get_client().table("benchmark")
        .select("cumulative_portfolio, cumulative_spy")
        .order("date", desc=True)
        .limit(1)
        .execute()
    )

    if prev_resp.data:
        prev = prev_resp.data[0]
        cum_p = (1 + prev["cumulative_portfolio"] / 100) * (1 + portfolio_return / 100) * 100 - 100
        cum_s = (1 + prev["cumulative_spy"] / 100) * (1 + spy_return / 100) * 100 - 100
    else:
        cum_p = portfolio_return
        cum_s = spy_return

    get_client().table("benchmark").upsert({
        "date": trading_date.isoformat(),
        "portfolio_value": portfolio_value,
        "portfolio_return": portfolio_return,
        "spy_return": spy_return,
        "alpha": portfolio_return - spy_return,
        "cumulative_portfolio": cum_p,
        "cumulative_spy": cum_s,
    }, on_conflict="date").execute()


def get_weekly_alpha() -> float:
    resp = (
        get_client().table("benchmark")
        .select("portfolio_return, spy_return")
        .order("date", desc=True)
        .limit(5)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0.0
    return sum(r["portfolio_return"] - r["spy_return"] for r in rows)
