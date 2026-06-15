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

-- ── Users (Quản lý tài khoản) ───────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    email         VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Thêm khóa ngoại cho bảng user_alerts (chạy cái này sau khi tạo bảng users)
ALTER TABLE user_alerts 
ADD CONSTRAINT fk_user 
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- ── Alert History (Lịch sử cảnh báo đã bắn) ─────────────────
CREATE TABLE IF NOT EXISTS alert_history (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
    alert_rule_id INTEGER REFERENCES user_alerts(id) ON DELETE CASCADE,
    symbol        VARCHAR(20) NOT NULL,
    triggered_at  TIMESTAMP DEFAULT NOW(),
    trigger_price DOUBLE PRECISION NOT NULL,
    message       TEXT NOT NULL,
    is_read       BOOLEAN DEFAULT FALSE  -- Đánh dấu đã đọc/chưa đọc trên UI
);

-- ── ML Predictions (Kết quả dự báo của Model) ───────────────
CREATE TABLE IF NOT EXISTS ml_predictions (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    prediction_time  TIMESTAMP NOT NULL, -- Thời điểm đưa ra dự báo
    target_time      TIMESTAMP NOT NULL, -- Dự báo cho tương lai (ví dụ: 4h sau)
    model_version    VARCHAR(50),        -- Lưu version lấy từ MLflow/MinIO
    prediction_type  VARCHAR(20),        -- 'PRICE_UP', 'PRICE_DOWN', 'VOLATILITY'
    confidence_score DOUBLE PRECISION,   -- Độ tin cậy (VD: 0.85 = 85%)
    created_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, prediction_time, model_version)
);

-- ── Bổ sung Index cho các bảng mới ──────────────────────────
CREATE INDEX IF NOT EXISTS idx_alert_history_user
    ON alert_history (user_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_symbol_time
    ON ml_predictions (symbol, target_time DESC);