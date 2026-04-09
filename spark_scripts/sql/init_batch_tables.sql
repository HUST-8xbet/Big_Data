-- ============================================================
-- BATCH LAYER — PostgreSQL Schema
-- Chạy script này trước khi batch_layer.py hoạt động
-- ============================================================

-- ── OHLCV Candles ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv_candles (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)   NOT NULL,
    interval    VARCHAR(5)    NOT NULL,   -- '1h', '4h'
    open_time   TIMESTAMP     NOT NULL,
    close_time  TIMESTAMP,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    trade_count BIGINT,
    avg_price   DOUBLE PRECISION,
    high_low_pct   DOUBLE PRECISION,
    close_change_pct DOUBLE PRECISION,
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, interval, open_time)
);

-- ── Market Stats ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_stats (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    window_label    VARCHAR(5)  NOT NULL,   -- '1h', '4h'
    window_start    TIMESTAMP   NOT NULL,
    window_end      TIMESTAMP,
    vwap            DOUBLE PRECISION,
    avg_price       DOUBLE PRECISION,
    max_price       DOUBLE PRECISION,
    min_price       DOUBLE PRECISION,
    total_volume    DOUBLE PRECISION,
    trade_count     BIGINT,
    volatility      DOUBLE PRECISION,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, window_label, window_start)
);

-- ── Symbol Profiles ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS symbol_profiles (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) UNIQUE NOT NULL,
    last_price       DOUBLE PRECISION,
    volume_total     DOUBLE PRECISION,
    price_change_pct DOUBLE PRECISION,
    updated_at       TIMESTAMP DEFAULT NOW()
);

-- ── User Alerts (đã có từ dynamic_alert.py) ─────────────────
CREATE TABLE IF NOT EXISTS user_alerts (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER,
    symbol        VARCHAR(20) NOT NULL,
    alert_type    VARCHAR(20) NOT NULL,  -- 'PRICE' | 'VOLUME'
    condition     VARCHAR(10) NOT NULL,  -- 'UP' | 'DOWN'
    target_value  DOUBLE PRECISION,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ── Index cho truy vấn nhanh ────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_interval
    ON ohlcv_candles (symbol, interval, open_time DESC);
CREATE INDEX IF NOT EXISTS idx_stats_symbol_window
    ON market_stats (symbol, window_label, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol_active
    ON user_alerts (symbol, is_active);
