import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from collections import deque
import os

WINDOW_SIZE   = 60    # 60 phút lịch sử làm input
WARMUP        = 20    # số điểm đầu cần để MA20/volatility/RSI ổn định (bị cắt bỏ)
NUM_FEATURES  = 5     # return, ma5_ratio, ma20_ratio, volatility, rsi
HIDDEN_SIZE   = 128
NUM_LAYERS    = 2
BATCH_SIZE    = 512
EPOCHS        = 20

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
torch.backends.cudnn.benchmark = True

ml_model = None
price_buffer = {}
MAX_BUFFER_SIZE = 120

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pt")


class LSTMModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=NUM_FEATURES,
            hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS,
            batch_first=True,
            dropout=0.2,
        )
        self.fc = nn.Linear(HIDDEN_SIZE, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])  # lấy output của timestep cuối


# ── Feature engineering (vectorized) ─────────────────────────────────────────

def _rolling_mean(arr, window):
    cumsum = np.cumsum(np.insert(arr, 0, 0.0))
    result = np.full(len(arr), np.nan, dtype=np.float64)
    result[window - 1:] = (cumsum[window:] - cumsum[:-window]) / window
    return result


def _rolling_std(arr, window):
    cumsum = np.cumsum(np.insert(arr, 0, 0.0))
    cumsum_sq = np.cumsum(np.insert(arr ** 2, 0, 0.0))
    mean = (cumsum[window:] - cumsum[:-window]) / window
    mean_sq = (cumsum_sq[window:] - cumsum_sq[:-window]) / window
    var = np.maximum(mean_sq - mean ** 2, 0)
    result = np.full(len(arr), np.nan, dtype=np.float64)
    result[window - 1:] = np.sqrt(var)
    return result


def _compute_rsi(prices, period=14):
    deltas = np.diff(prices, prepend=prices[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = _rolling_mean(gains, period)
    avg_loss = _rolling_mean(losses, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    rsi = np.where(avg_loss == 0, 100.0, rsi)
    rsi = np.nan_to_num(rsi, nan=50.0)
    return rsi / 100.0  # normalize về [0, 1]


def _compute_feature_matrix(prices):
    """Tính ma trận feature (N, NUM_FEATURES) từ mảng giá.
    Cột 0 (return) cũng chính là target khi train.
    20 dòng đầu chứa NaN (chưa đủ dữ liệu cho MA20/RSI) — cần cắt bằng WARMUP.
    """
    prices = np.asarray(prices, dtype=np.float64)

    returns = np.zeros(len(prices), dtype=np.float64)
    returns[1:] = np.diff(prices) / prices[:-1]

    ma5 = _rolling_mean(prices, 5)
    ma20 = _rolling_mean(prices, 20)
    volatility = _rolling_std(prices, 20) / prices
    rsi = _compute_rsi(prices, 14)

    ma5_ratio = prices / ma5 - 1
    ma20_ratio = prices / ma20 - 1

    features = np.stack([returns, ma5_ratio, ma20_ratio, volatility, rsi], axis=1)
    return features.astype(np.float32)


def _create_sequences(prices):
    """Tạo cặp (X, y): X là chuỗi WINDOW_SIZE feature vectors, y là return kế tiếp."""
    features = _compute_feature_matrix(prices)
    returns = features[:, 0]

    features = features[WARMUP:]
    returns = returns[WARMUP:]

    X, y = [], []
    for i in range(len(features) - WINDOW_SIZE):
        X.append(features[i : i + WINDOW_SIZE])
        y.append(returns[i + WINDOW_SIZE])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


# ── Training ──────────────────────────────────────────────────────────────────

def train_model_on_historical_data(historical_prices):
    global ml_model

    min_points = WINDOW_SIZE + WARMUP + 1
    all_X, all_y = [], []
    for symbol, prices in historical_prices.items():
        if len(prices) < min_points:
            print(f"  ⚠️  {symbol}: không đủ dữ liệu ({len(prices)} điểm), bỏ qua")
            continue
        X, y = _create_sequences(prices)
        all_X.append(X)
        all_y.append(y)

    if not all_X:
        print("⚠️  Không đủ dữ liệu để huấn luyện mô hình")
        return

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y, axis=0)

    # Train/val split theo thứ tự thời gian (không shuffle toàn bộ)
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    train_loader = DataLoader(
        TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train).unsqueeze(-1)),
        batch_size=BATCH_SIZE, shuffle=True,
    )
    val_loader = DataLoader(
        TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val).unsqueeze(-1)),
        batch_size=BATCH_SIZE,
    )

    model = LSTMModel().to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    print(f"🖥️  Thiết bị: {DEVICE}")
    print(f"📐 Training trên {len(X_train)} samples, validation trên {len(X_val)} samples")

    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(X_batch), y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
                val_loss += criterion(model(X_batch), y_batch).item()

        print(f"  Epoch {epoch+1:>3}/{EPOCHS} — train: {train_loss/len(train_loader):.6f}  val: {val_loss/len(val_loader):.6f}")

    ml_model = model
    torch.save(model.state_dict(), MODEL_PATH)
    print(f"✅ LSTM đã được huấn luyện trên {len(X)} samples, lưu vào {MODEL_PATH}")


def load_ml_model():
    global ml_model
    print("🚀 Đang khởi tạo LSTM model...")
    print(f"🖥️  Thiết bị: {DEVICE}")

    model = LSTMModel().to(DEVICE)

    if os.path.exists(MODEL_PATH):
        try:
            model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
            model.eval()
            ml_model = model
            print("✅ LSTM model đã được load từ model.pt")
            return ml_model
        except Exception as e:
            print(f"⚠️  Lỗi load model: {e}")

    ml_model = model
    print("⚠️  Sử dụng LSTM chưa được huấn luyện — hãy chạy train_model.py trước")
    return ml_model


# ── Real-time prediction ─────────────────────────────────────────────────────

def update_price_buffer(symbol, price):
    if symbol not in price_buffer:
        price_buffer[symbol] = deque(maxlen=MAX_BUFFER_SIZE)
    price_buffer[symbol].append(price)


def forecast_future_prices(model, symbol, steps=15):
    """Dự đoán nhiều bước tương lai (mỗi bước 1 phút) bằng rollout lặp:
    dự đoán return kế tiếp → nối giá mới vào chuỗi → dự đoán tiếp.
    Trả về list giá dự đoán, [] nếu buffer chưa đủ dữ liệu.
    """
    history = list(price_buffer.get(symbol, []))
    min_required = WINDOW_SIZE + WARMUP

    if len(history) < min_required:
        return []

    prices = list(history)
    out = []
    try:
        model.eval()
        for _ in range(steps):
            arr = np.array(prices[-min_required:], dtype=np.float64)
            features = _compute_feature_matrix(arr)[-WINDOW_SIZE:]
            X = torch.from_numpy(features).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                predicted_return = model(X).item()
            predicted_return = float(np.clip(predicted_return, -0.02, 0.02))
            next_price = prices[-1] * (1 + predicted_return)
            out.append(round(next_price, 2))
            prices.append(next_price)
    except Exception as e:
        print(f"Lỗi dự đoán tương lai {symbol}: {e}")
        return []
    return out


def predict_future_price(model, current_price, symbol=None):
    if symbol is None:
        return round(current_price * 1.001, 2)

    history = list(price_buffer.get(symbol, []))
    min_required = WINDOW_SIZE + WARMUP

    if len(history) < min_required:
        return round(current_price, 2)

    prices = np.array(history[-min_required:], dtype=np.float64)
    features = _compute_feature_matrix(prices)[-WINDOW_SIZE:]  # (WINDOW_SIZE, NUM_FEATURES)

    X = torch.from_numpy(features).unsqueeze(0).to(DEVICE)  # (1, WINDOW_SIZE, NUM_FEATURES)

    try:
        model.eval()
        with torch.no_grad():
            predicted_return = model(X).item()

        # Giới hạn không cho dự đoán vọt >2% trong 1 phút
        predicted_return = float(np.clip(predicted_return, -0.02, 0.02))
        return round(current_price * (1 + predicted_return), 2)
    except Exception as e:
        print(f"Lỗi dự đoán: {e}")
        return round(current_price, 2)
