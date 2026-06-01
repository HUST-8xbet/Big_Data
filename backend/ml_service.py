# File: backend/ml_service.py
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
import joblib
import os
from collections import deque

# Global model và price history buffer
ml_model = None
price_buffer = {}  # {symbol: deque(prices)}
MAX_BUFFER_SIZE = 120  # Lưu 120 điểm (2 tiếng với interval 1 phút)

def create_features(price_history):
    """
    Feature Engineering: tạo các đặc trưng từ lịch sử giá
    - MA5, MA10, MA20: Moving averages
    - Momentum: Tốc độ thay đổi
    - Volatility: Độ biến động
    - Trend: Xu hướng
    - RSI: Relative Strength Index
    """
    if len(price_history) < 20:
        return None
    
    prices = np.array(price_history, dtype=float)
    
    # Moving Averages
    ma5 = np.mean(prices[-5:])
    ma10 = np.mean(prices[-10:])
    ma20 = np.mean(prices[-20:])
    
    # Momentum (tốc độ thay đổi)
    momentum = prices[-1] - prices[-5] if len(prices) >= 5 else 0
    
    # Volatility (độ lệch chuẩn)
    volatility = np.std(prices[-20:]) if len(prices) >= 20 else 0
    
    # Trend (hệ số tuyến tính)
    x = np.arange(len(prices[-20:]))
    y = prices[-20:]
    trend = np.polyfit(x, y, 1)[0]  # Slope
    
    # RSI (Relative Strength Index)
    deltas = np.diff(prices[-14:]) if len(prices) >= 14 else np.array([0])
    gains = np.sum(deltas[deltas > 0]) if len(deltas) > 0 else 0
    losses = np.abs(np.sum(deltas[deltas < 0])) if len(deltas) > 0 else 0
    rs = gains / losses if losses > 0 else 0
    rsi = 100 - (100 / (1 + rs)) if rs >= 0 else 50
    
    # Price ratio (giá hiện tại so với MA20)
    price_ratio = prices[-1] / ma20 if ma20 > 0 else 1
    
    features = {
        'price': prices[-1],
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'momentum': momentum,
        'volatility': volatility,
        'trend': trend,
        'rsi': rsi,
        'price_ratio': price_ratio,
    }
    
    return features

def train_model_on_historical_data(historical_prices):
    """
    Training: Huấn luyện mô hình XGBoost trên dữ liệu lịch sử
    historical_prices: dict {symbol: [list of prices]}
    """
    global ml_model
    
    X = []
    y = []
    
    for symbol, prices in historical_prices.items():
        prices = np.array(prices, dtype=float)
        
        # Tạo training samples: dùng 20 điểm trước để dự đoán điểm kế tiếp
        for i in range(20, len(prices) - 1):
            features = create_features(prices[:i+1].tolist())
            if features is not None:
                X.append([
                    features['price'],
                    features['ma5'],
                    features['ma10'],
                    features['ma20'],
                    features['momentum'],
                    features['volatility'],
                    features['trend'],
                    features['rsi'],
                    features['price_ratio'],
                ])
                # Target: đoán giá tiếp theo
                y.append(prices[i+1])
    
    if len(X) > 0:
        X = np.array(X)
        y = np.array(y)
        
        # Training XGBoost
        ml_model = XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=1
        )
        ml_model.fit(X, y)
        print(f"✅ Mô hình XGBoost đã được huấn luyện trên {len(X)} samples")
        
        # Lưu model
        joblib.dump(ml_model, 'model.pkl')
        print("💾 Model đã được lưu vào model.pkl")
    else:
        print("⚠️  Không đủ dữ liệu để huấn luyện mô hình")

def load_ml_model():
    """
    Load mô hình ML từ file hoặc tạo mới nếu chưa có
    """
    global ml_model
    
    print("🚀 Đang khởi tạo mô hình Machine Learning...")
    
    # Cố gắng load model đã lưu trước đó
    if os.path.exists('model.pkl'):
        try:
            ml_model = joblib.load('model.pkl')
            print("✅ Mô hình XGBoost đã được load từ model.pkl")
            return ml_model
        except Exception as e:
            print(f"⚠️  Lỗi load model: {e}")
    
    # Nếu chưa có model, khởi tạo một model mặc định
    # (Sau này sẽ huấn luyện khi có đủ dữ liệu)
    ml_model = XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
    )
    
    print("⚠️  Sử dụng mô hình XGBoost chưa được huấn luyện")
    print("💡 Mô hình sẽ được huấn luyện khi có đủ dữ liệu lịch sử")
    
    return ml_model

def update_price_buffer(symbol, price):
    """
    Cập nhật buffer giá cho một coin
    """
    if symbol not in price_buffer:
        price_buffer[symbol] = deque(maxlen=MAX_BUFFER_SIZE)
    price_buffer[symbol].append(price)

def predict_future_price(model, current_price, symbol=None):
    """
    Dự đoán giá tiếp theo dựa trên XGBoost + feature engineering
    """
    if symbol is None:
        # Fallback: nếu không có lịch sử giá, chỉ dùng giá hiện tại
        return round(current_price * 1.001, 2)
    
    # Lấy lịch sử giá
    price_history = list(price_buffer.get(symbol, []))
    if not price_history:
        price_history = [current_price]
    
    # Thêm giá hiện tại nếu chưa có
    if len(price_history) == 0 or price_history[-1] != current_price:
        price_history.append(current_price)
    
    # Cập nhật buffer
    update_price_buffer(symbol, current_price)
    
    # Tạo features
    features = create_features(price_history)
    if features is None:
        # Nếu chưa đủ dữ liệu, dự đoán bằng simple trend
        return round(current_price * (1 + np.random.uniform(-0.001, 0.001)), 2)
    
    # Dự đoán
    try:
        X_input = np.array([[
            features['price'],
            features['ma5'],
            features['ma10'],
            features['ma20'],
            features['momentum'],
            features['volatility'],
            features['trend'],
            features['rsi'],
            features['price_ratio'],
        ]])
        
        predicted = model.predict(X_input)[0]
        
        # Kiểm soát ngoại lệ (prediction không được chênh lệch quá 5%)
        max_deviation = current_price * 0.05
        predicted = np.clip(predicted, current_price - max_deviation, current_price + max_deviation)
        
        return round(predicted, 2)
    except Exception as e:
        print(f"Lỗi dự đoán: {e}")
        return round(current_price, 2)