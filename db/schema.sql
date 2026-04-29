CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    cash REAL NOT NULL,
    equity REAL NOT NULL,
    total_value REAL NOT NULL,
    daily_pl REAL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    bucket TEXT NOT NULL DEFAULT 'core' CHECK(bucket IN ('core')),
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    quality_score REAL NOT NULL DEFAULT 0,
    momentum_score REAL NOT NULL DEFAULT 0,
    combined_score REAL NOT NULL DEFAULT 0,
    bucket TEXT NOT NULL DEFAULT 'core' CHECK(bucket IN ('core')),
    position_weight_pct REAL DEFAULT 8,
    thesis TEXT,
    key_risks TEXT,
    sharia_status TEXT DEFAULT 'compliant',
    acted_on INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, ticker)
);

CREATE TABLE IF NOT EXISTS decisions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    phase TEXT NOT NULL,
    ticker TEXT,
    action TEXT NOT NULL,
    reasoning TEXT,
    confidence REAL,
    order_id TEXT,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS benchmark (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    portfolio_value REAL NOT NULL,
    portfolio_return REAL,
    spy_return REAL,
    alpha REAL,
    cumulative_portfolio REAL DEFAULT 0,
    cumulative_spy REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist(date);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_benchmark_date ON benchmark(date);
