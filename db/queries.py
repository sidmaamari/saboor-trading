import sqlite3
import os
from datetime import date
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "saboor.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    with get_conn() as conn:
        conn.executescript(schema)
    print("Database initialized.")


# ── Portfolio ─────────────────────────────────────────────────────────────────

def sync_portfolio(cash: float, equity: float, total_value: float, daily_pl: float):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO portfolio (cash, equity, total_value, daily_pl) VALUES (?, ?, ?, ?)",
            (cash, equity, total_value, daily_pl),
        )


def get_portfolio_value() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM portfolio ORDER BY last_updated DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"cash": 0.0, "equity": 0.0, "total_value": 0.0, "daily_pl": 0.0}
        return dict(row)


def get_daily_pl() -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT daily_pl FROM portfolio ORDER BY last_updated DESC LIMIT 1"
        ).fetchone()
        return row["daily_pl"] if row else 0.0


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
    stop_loss = entry_price * 0.97  # -3% hard stop
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO positions
               (ticker, bucket, shares, entry_price, entry_date,
                thesis, quality_score, momentum_score, combined_score, stop_loss)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticker, bucket, shares, entry_price, entry_date.isoformat(),
                thesis, quality_score, momentum_score, combined_score, stop_loss,
            ),
        )


def get_open_positions(bucket: str = None) -> list[dict]:
    with get_conn() as conn:
        if bucket:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status='open' AND bucket=? ORDER BY entry_date",
                (bucket,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status='open' ORDER BY entry_date"
            ).fetchall()
        return [dict(r) for r in rows]


def get_open_positions_count() -> dict:
    with get_conn() as conn:
        core = conn.execute(
            "SELECT COUNT(*) as n FROM positions WHERE status='open' AND bucket='core'"
        ).fetchone()["n"]
        tactical = conn.execute(
            "SELECT COUNT(*) as n FROM positions WHERE status='open' AND bucket='tactical'"
        ).fetchone()["n"]
        return {"core": core, "tactical": tactical}


def get_position_by_ticker(ticker: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM positions WHERE ticker=? AND status='open'", (ticker,)
        ).fetchone()
        return dict(row) if row else None


def close_position(ticker: str, close_price: float, reason: str):
    with get_conn() as conn:
        pos = conn.execute(
            "SELECT * FROM positions WHERE ticker=? AND status='open'", (ticker,)
        ).fetchone()
        if not pos:
            return
        pnl = (close_price - pos["entry_price"]) * pos["shares"]
        conn.execute(
            """UPDATE positions
               SET status='closed', close_date=?, close_price=?, pnl=?, close_reason=?
               WHERE ticker=? AND status='open'""",
            (date.today().isoformat(), close_price, pnl, reason, ticker),
        )


def update_positions_days_held():
    with get_conn() as conn:
        conn.execute("UPDATE positions SET days_held = days_held + 1 WHERE status='open'")


# ── Watchlist ─────────────────────────────────────────────────────────────────

def save_watchlist(trading_date: date, items: list[dict]):
    with get_conn() as conn:
        conn.execute("DELETE FROM watchlist WHERE date=?", (trading_date.isoformat(),))
        for item in items:
            conn.execute(
                """INSERT INTO watchlist
                   (date, ticker, quality_score, momentum_score, combined_score,
                    bucket, thesis, key_risks, sharia_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trading_date.isoformat(),
                    item["ticker"],
                    item.get("quality_score", 0),
                    item.get("momentum_score", 0),
                    item.get("combined_score", 0),
                    item.get("bucket", "tactical"),
                    item.get("thesis", ""),
                    item.get("key_risks", ""),
                    item.get("sharia_status", "compliant"),
                ),
            )


def get_todays_watchlist() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE date=? AND acted_on=0 ORDER BY combined_score DESC",
            (date.today().isoformat(),),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_watchlist_acted(ticker: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE watchlist SET acted_on=1 WHERE ticker=? AND date=?",
            (ticker, date.today().isoformat()),
        )


# ── Decisions Log ─────────────────────────────────────────────────────────────

def log_decision(
    phase: str,
    ticker: str | None,
    action: str,
    reasoning: str = "",
    confidence: float = None,
    order_id: str = None,
):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO decisions_log (phase, ticker, action, reasoning, confidence, order_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (phase, ticker, action, reasoning, confidence, order_id),
        )


def get_todays_decisions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM decisions_log WHERE date(timestamp)=date('now') ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Benchmark ─────────────────────────────────────────────────────────────────

def get_previous_portfolio_value() -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT portfolio_value FROM benchmark ORDER BY date DESC LIMIT 1"
        ).fetchone()
        return row["portfolio_value"] if row else None


def save_benchmark(
    trading_date: date,
    portfolio_value: float,
    portfolio_return: float,
    spy_return: float,
):
    with get_conn() as conn:
        prev = conn.execute(
            "SELECT cumulative_portfolio, cumulative_spy FROM benchmark ORDER BY date DESC LIMIT 1"
        ).fetchone()

        if prev:
            cum_p = (1 + prev["cumulative_portfolio"] / 100) * (1 + portfolio_return / 100) * 100 - 100
            cum_s = (1 + prev["cumulative_spy"] / 100) * (1 + spy_return / 100) * 100 - 100
        else:
            cum_p = portfolio_return
            cum_s = spy_return

        conn.execute(
            """INSERT OR REPLACE INTO benchmark
               (date, portfolio_value, portfolio_return, spy_return, alpha,
                cumulative_portfolio, cumulative_spy)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                trading_date.isoformat(), portfolio_value, portfolio_return,
                spy_return, portfolio_return - spy_return, cum_p, cum_s,
            ),
        )


def get_weekly_alpha() -> float:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT portfolio_return, spy_return FROM benchmark ORDER BY date DESC LIMIT 5"
        ).fetchall()
        if not rows:
            return 0.0
        return sum(r["portfolio_return"] - r["spy_return"] for r in rows)
