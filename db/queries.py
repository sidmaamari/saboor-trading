from datetime import date, timedelta
from db.supabase_client import get_client


def init_db():
    """Tables live in Supabase — run db/supabase_schema.sql once in the Supabase SQL Editor."""
    print("Supabase tables are managed remotely.")
    print("If tables don't exist yet, run db/supabase_schema.sql in the Supabase SQL Editor.")


# ── Portfolio ─────────────────────────────────────────────────────────────────

def sync_portfolio(cash: float, equity: float, total_value: float, daily_pl: float):
    # FIX [HIGH H-6]: Upsert by date instead of insert.
    # REASON: The portfolio table was accumulating one row per phase per day
    #         (premarket, open, midday, eod), inflating storage and making
    #         "latest portfolio" queries scan more rows than necessary.
    #         More importantly, downstream analytics that join by date
    #         could return ambiguous results.
    # SOLUTION: Upsert on `date` so there is exactly one row per trading day,
    #         updated in place across phases. Requires a UNIQUE(date) on
    #         the `portfolio` table — see supabase_schema.sql.
    get_client().table("portfolio").upsert({
        "date": date.today().isoformat(),
        "cash": cash,
        "equity": equity,
        "total_value": total_value,
        "daily_pl": daily_pl,
    }, on_conflict="date").execute()


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
    # FIX [HIGH H-10]: Single round-trip instead of two parallel queries.
    # REASON: Two sequential SELECTs added latency on every call to the risk
    #         guardian, which runs once per buy decision. With ~12 positions
    #         across two buckets the bandwidth saving is small, but the
    #         latency saving on hot paths matters and the simpler code is
    #         less likely to drift.
    # SOLUTION: One SELECT for all open positions, then count in-memory.
    resp = (
        get_client().table("positions")
        .select("bucket")
        .eq("status", "open")
        .execute()
    )
    counts = {"core": 0, "tactical": 0}
    for row in (resp.data or []):
        bucket = row.get("bucket")
        if bucket in counts:
            counts[bucket] += 1
    return counts


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
    # FIX [CRITICAL C-3]: Close the SPECIFIC position by id, not all open rows for the ticker.
    # REASON: The previous UPDATE matched on (ticker, status='open'), which
    #         would close every open row for that ticker if more than one
    #         existed. This is a data-integrity hazard: a partial fill or
    #         a manual entry could result in two open rows; an EOD close
    #         on one would silently close them both, corrupting P&L.
    # SOLUTION: Fetch the row first to capture its id, then update by id.
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
    }).eq("id", pos["id"]).execute()


def update_positions_days_held():
    # FIX [HIGH H-4 / H-11]: Only increment on trading weekdays (Mon–Fri).
    # REASON: Tactical positions have a 3-trading-day max hold. If days_held
    #         was incremented on Saturday and Sunday, a Friday entry would
    #         hit "max hold" by Monday morning — closing it a full trading
    #         day early. This is a real correctness bug for the tactical
    #         strategy. (Holiday handling is best-effort; weekend handling
    #         is the high-impact win.)
    # SOLUTION: Bail out on weekends so days_held only advances on Mon–Fri.
    #         Note: this still N+1's on Supabase — a true server-side
    #         increment would require an RPC, which is deferred. Each
    #         loop iteration touches one row, capped by open positions
    #         (typically <15), so the perf cost is bounded.
    if date.today().weekday() >= 5:  # 5=Sat, 6=Sun
        return

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
    if not rows:
        return
    try:
        get_client().table("watchlist").insert(rows).execute()
    except Exception as e:
        if "position_weight_pct" in str(e):
            # Column not yet added to Supabase schema — save without it
            for r in rows:
                r.pop("position_weight_pct", None)
            get_client().table("watchlist").insert(rows).execute()
            print("  WARNING: position_weight_pct column missing in Supabase. Run: ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS position_weight_pct REAL DEFAULT 8;")
        else:
            raise


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
