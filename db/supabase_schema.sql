-- Run this once in the Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql)
-- to create all tables for the Saboor trading agent.

CREATE TABLE IF NOT EXISTS portfolio (
    id BIGSERIAL PRIMARY KEY,
    -- FIX [HIGH H-6]: One row per trading day, enforced at the schema level.
    -- sync_portfolio() now upserts on `date`; the UNIQUE constraint backs that.
    date DATE NOT NULL UNIQUE,
    cash REAL NOT NULL,
    equity REAL NOT NULL,
    total_value REAL NOT NULL,
    daily_pl REAL DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);
-- For existing deployments — additive migration:
-- ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS date DATE;
-- UPDATE portfolio SET date = CURRENT_DATE WHERE date IS NULL;
-- ALTER TABLE portfolio ALTER COLUMN date SET NOT NULL;
-- CREATE UNIQUE INDEX IF NOT EXISTS uniq_portfolio_date ON portfolio(date);

CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    bucket TEXT NOT NULL CHECK(bucket IN ('core', 'tactical')),
    shares REAL NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    entry_date DATE NOT NULL,
    days_held INTEGER DEFAULT 0,
    thesis TEXT,
    quality_score REAL,
    momentum_score REAL,
    combined_score REAL,
    stop_loss REAL,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    close_date DATE,
    close_price REAL,
    pnl REAL,
    close_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    quality_score REAL NOT NULL DEFAULT 0,
    momentum_score REAL NOT NULL DEFAULT 0,
    combined_score REAL NOT NULL DEFAULT 0,
    bucket TEXT NOT NULL CHECK(bucket IN ('core', 'tactical')),
    -- FIX [HIGH H-14]: position_weight_pct surfaces the analyst's per-stock
    -- conviction-weighted allocation. Risk Guardian uses this to size the order.
    position_weight_pct REAL DEFAULT 8,
    thesis TEXT,
    key_risks TEXT,
    sharia_status TEXT DEFAULT 'compliant',
    acted_on BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, ticker)
);
-- For existing deployments — additive migration:
-- ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS position_weight_pct REAL DEFAULT 8;

CREATE TABLE IF NOT EXISTS decisions_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    phase TEXT NOT NULL,
    ticker TEXT,
    action TEXT NOT NULL,
    reasoning TEXT,
    confidence REAL,
    order_id TEXT,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS benchmark (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    portfolio_value REAL NOT NULL,
    portfolio_return REAL,
    spy_return REAL,
    alpha REAL,
    cumulative_portfolio REAL DEFAULT 0,
    cumulative_spy REAL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist(date);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_benchmark_date ON benchmark(date);
