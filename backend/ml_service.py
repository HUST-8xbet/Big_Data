import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from collections import deque
import os

WINDOW_SIZE = 60   # 60 phút lịch sử làm input
HIDDEN_SIZE = 64
NUM_LAYERS = 2

ml_model = None
price_buffer = {}
MAX_BUFFER_SIZE = 120


class LSTMModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS,
            batch_first=True,
            dropout=0.2,
        )
        self.fc = nn.Linear(HIDDEN_SIZE, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])  # lấy output của timestep cuối


def _to_returns(prices):
    """Chuyển mảng giá sang % thay đổi (returns), giải quyết vấn đề scale giữa các coin."""
    prices = np.array(prices, dtype=float)
    returns = np.diff(prices) / prices[:-1]
    return returns


def _create_sequences(prices):
    """Tạo cặp (X, y) từ mảng giá.
    X: chuỗi WINDOW_SIZE returns liên tiếp
    y: return tiếp theo cần dự đoán
    """
    returns = _to_returns(prices)
    X, y = [], []
    for i in range(len(returns) - WINDOW_SIZE):
        X.append(returns[i : i + WINDOW_SIZE])
        y.append(returns[i + WINDOW_SIZE])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def train_model_on_historical_data(historical_prices):
    global ml_model

    all_X, all_y = [], []
    for symbol, prices in historical_prices.items():
        if len(prices) < WINDOW_SIZE + 2:
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

    # Reshape: (batch, seq_len, features=1)
    X_train_t = torch.from_numpy(X_train).unsqueeze(-1)
    y_train_t = torch.from_numpy(y_train).unsqueeze(-1)
    X_val_t   = torch.from_numpy(X_val).unsqueeze(-1)
    y_val_t   = torch.from_numpy(y_val).unsqueeze(-1)

    loader = DataLoader(TensorDataset(X_train_t, y_train_t), batch_size=64, shuffle=True)

    model = LSTMModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    print(f"📐 Training trên {len(X_train)} samples, validation trên {len(X_val)} samples")

    for epoch in range(50):
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in loader:
            optimizer.zero_grad()
            loss = criterion(model(X_batch), y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        if (epoch + 1) % 10 == 0:
            model.eval()
            with torch.no_grad():
                val_loss = criterion(model(X_val_t), y_val_t).item()
            print(f"  Epoch {epoch+1:>3}/50 — train: {train_loss/len(loader):.6f}  val: {val_loss:.6f}")

    ml_model = model
    torch.save(model.state_dict(), "model.pt")
    print(f"✅ LSTM đã được huấn luyện trên {len(X)} samples, lưu vào model.pt")


def load_ml_model():
    global ml_model
    print("🚀 Đang khởi tạo LSTM model...")

    model = LSTMModel()

    if os.path.exists("model.pt"):
        try:
            model.load_state_dict(torch.load("model.pt", map_location="cpu"))
            model.eval()
            ml_model = model
            print("✅ LSTM model đã được load từ model.pt")
            return ml_model
        except Exception as e:
            print(f"⚠️  Lỗi load model: {e}")

    ml_model = model
    print("⚠️  Sử dụng LSTM chưa được huấn luyện — hãy chạy train_model.py trước")
    return ml_model


def update_price_buffer(symbol, price):
    if symbol not in price_buffer:
        price_buffer[symbol] = deque(maxlen=MAX_BUFFER_SIZE)
    price_buffer[symbol].append(price)


def predict_future_price(model, current_price, symbol=None):
    if symbol is None:
        return round(current_price * 1.001, 2)

    history = list(price_buffer.get(symbol, []))

    # Cần ít nhất WINDOW_SIZE + 1 giá để tính WINDOW_SIZE returns
    if len(history) < WINDOW_SIZE + 1:
        return round(current_price, 2)

    returns = _to_returns(history[-(WINDOW_SIZE + 1):])  # đúng WINDOW_SIZE returns
    X = torch.from_numpy(returns.astype(np.float32)).unsqueeze(0).unsqueeze(-1)  # (1, 60, 1)

    try:
        model.eval()
        with torch.no_grad():
            predicted_return = model(X).item()

        # Giới hạn không cho dự đoán vọt >2% trong 1 phút (crypto thực tế hiếm hơn)
        predicted_return = float(np.clip(predicted_return, -0.02, 0.02))
        return round(current_price * (1 + predicted_return), 2)
    except Exception as e:
        print(f"Lỗi dự đoán: {e}")
        return round(current_price, 2)
