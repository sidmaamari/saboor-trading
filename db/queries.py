from datetime import date, timedelta
from db.supabase_client import get_client


def init_db():
    """Tables live in Supabase — run db/supabase_schema.sql once in the Supabase SQL Editor."""
    print("Supabase tables are managed remotely.")
    print("If tables don't exist yet, run db/supabase_schema.sql in the Supabase SQL Editor.")


# ── Portfolio ─────────────────────────────────────────────────────────────────

_PORTFOLIO_DATE_MIGRATION = (
    "  Run in Supabase SQL Editor:\n"
    "    ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS date DATE;\n"
    "    UPDATE portfolio SET date = DATE(last_updated) WHERE date IS NULL;\n"
    "    ALTER TABLE portfolio ALTER COLUMN date SET NOT NULL;\n"
    "    CREATE UNIQUE INDEX IF NOT EXISTS uniq_portfolio_date ON portfolio(date);"
)


def sync_portfolio(cash: float, equity: float, total_value: float, daily_pl: float):
    from datetime import datetime
    today = date.today().isoformat()
    now = datetime.utcnow().isoformat() + "Z"
    try:
        get_client().table("portfolio").upsert({
            "date": today,
            "cash": cash,
            "equity": equity,
            "total_value": total_value,
            "daily_pl": daily_pl,
            "last_updated": now,
        }, on_conflict="date").execute()
    except Exception as e:
        if "date" in str(e).lower():
            # date column / unique index not yet created — fall back to plain insert
            get_client().table("portfolio").insert({
                "cash": cash,
                "equity": equity,
                "total_value": total_value,
                "daily_pl": daily_pl,
            }).execute()
            print(f"  WARNING: portfolio.date column missing — inserted without dedup.\n{_PORTFOLIO_DATE_MIGRATION}")
        else:
            raise


def get_portfolio_value() -> dict:
    try:
        resp = (
            get_client().table("portfolio")
            .select("*")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if "date" in str(e).lower():
            print(f"  WARNING: portfolio.date column missing — falling back to last_updated order.\n{_PORTFOLIO_DATE_MIGRATION}")
            resp = (
                get_client().table("portfolio")
                .select("*")
                .order("last_updated", desc=True)
                .limit(1)
                .execute()
            )
        else:
            raise
    if not resp.data:
        return {"cash": 0.0, "equity": 0.0, "total_value": 0.0, "daily_pl": 0.0}
    return resp.data[0]


def get_daily_pl() -> float:
    try:
        resp = (
            get_client().table("portfolio")
            .select("daily_pl")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if "date" in str(e).lower():
            resp = (
                get_client().table("portfolio")
                .select("daily_pl")
                .order("last_updated", desc=True)
                .limit(1)
                .execute()
            )
        else:
            raise
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
    existing = get_position_by_ticker(ticker)
    if existing:
        old_shares = float(existing.get("shares", 0) or 0)
        new_shares = old_shares + shares
        if new_shares <= 0:
            return
        avg_entry = (
            (old_shares * float(existing.get("entry_price", 0) or 0)) +
            (shares * entry_price)
        ) / new_shares
        get_client().table("positions").update({
            "shares": new_shares,
            "entry_price": avg_entry,
            "thesis": thesis or existing.get("thesis"),
            "quality_score": quality_score if quality_score is not None else existing.get("quality_score"),
            "momentum_score": momentum_score if momentum_score is not None else existing.get("momentum_score"),
            "combined_score": combined_score if combined_score is not None else existing.get("combined_score"),
            "bucket": "core",
        }).eq("id", existing["id"]).execute()
        return

    get_client().table("positions").insert({
        "ticker": ticker,
        "bucket": "core",
        "shares": shares,
        "entry_price": entry_price,
        "entry_date": entry_date.isoformat(),
        "thesis": thesis,
        "quality_score": quality_score,
        "momentum_score": momentum_score,
        "combined_score": combined_score,
        "status": "open",
    }).execute()


def reduce_position(ticker: str, shares_to_sell: float, close_price: float, reason: str):
    """Trim an open position, or close it entirely if the trim exhausts shares."""
    pos = get_position_by_ticker(ticker)
    if not pos:
        return
    current_shares = float(pos.get("shares", 0) or 0)
    shares_to_sell = min(float(shares_to_sell), current_shares)
    if shares_to_sell <= 0:
        return
    if shares_to_sell >= current_shares:
        close_position(ticker, close_price, reason)
        return

    remaining = current_shares - shares_to_sell
    realized_pnl = (close_price - float(pos["entry_price"])) * shares_to_sell
    get_client().table("positions").update({
        "shares": remaining,
        "pnl": (float(pos.get("pnl") or 0) + realized_pnl),
        "close_reason": reason,
    }).eq("id", pos["id"]).execute()


def get_open_positions(bucket: str = None) -> list[dict]:
    q = get_client().table("positions").select("*").eq("status", "open")
    if bucket:
        q = q.eq("bucket", bucket)
    resp = q.order("entry_date").execute()
    return resp.data or []


def get_open_positions_count() -> dict:
    resp = (
        get_client().table("positions")
        .select("bucket")
        .eq("status", "open")
        .execute()
    )
    counts = {"core": 0, "total": 0}
    for row in (resp.data or []):
        counts["total"] += 1
        counts["core"] += 1
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
    pnl = float(pos.get("pnl") or 0) + (close_price - pos["entry_price"]) * pos["shares"]
    get_client().table("positions").update({
        "status": "closed",
        "close_date": date.today().isoformat(),
        "close_price": close_price,
        "pnl": pnl,
        "close_reason": reason,
    }).eq("id", pos["id"]).execute()


def update_positions_days_held():
    """Legacy no-op: the Buffett-style strategy has no day-counter exit rule."""
    return


# ── Watchlist ─────────────────────────────────────────────────────────────────

def save_watchlist(trading_date: date, items: list[dict]):
    date_str = trading_date.isoformat()
    existing_resp = (
        get_client().table("watchlist")
        .select("ticker, acted_on")
        .eq("date", date_str)
        .execute()
    )
    acted_by_ticker = {
        row["ticker"]: bool(row.get("acted_on"))
        for row in (existing_resp.data or [])
    }
    rows = [
        {
            "date": date_str,
            "ticker": item["ticker"],
            "quality_score": item.get("quality_score", 0),
            "momentum_score": item.get("momentum_score", 0),
            "combined_score": item.get("combined_score", 0),
            "bucket": "core",
            "position_weight_pct": item.get("position_weight_pct", 8),
            "thesis": item.get("thesis", ""),
            "key_risks": item.get("key_risks", ""),
            "sharia_status": item.get("sharia_status", "compliant"),
            "acted_on": acted_by_ticker.get(item["ticker"], False),
        }
        for item in items
    ]
    if not rows:
        return
    try:
        get_client().table("watchlist").upsert(rows, on_conflict="date,ticker").execute()
    except Exception as e:
        if "position_weight_pct" in str(e):
            # Column not yet added to Supabase schema — save without it
            for r in rows:
                r.pop("position_weight_pct", None)
            get_client().table("watchlist").upsert(rows, on_conflict="date,ticker").execute()
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

def get_previous_portfolio_value(before_date: date = None) -> float | None:
    before_date = before_date or date.today()
    resp = (
        get_client().table("benchmark")
        .select("portfolio_value")
        .lt("date", before_date.isoformat())
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
        .lt("date", trading_date.isoformat())
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
