# File: backend/ml_service.py
import random

def load_ml_model():
    """
    Hàm này chạy 1 lần khi khởi động Server.
    Sau này bạn ML sẽ viết code load file model thật (VD: model.pkl, file .h5) ở đây.
    """
    print("Đang tải mô hình Machine Learning...")
    # model = joblib.load('path/to/model.pkl')
    return "Mô hình đã sẵn sàng"

def predict_future_price(model, current_price):
    """
    Hàm này nhận giá trị thực tế và đưa vào mô hình để tiên tri giá tương lai.
    Sau này thay bằng: return model.predict([[current_price]])
    """
    # Hiện tại đang bịa ra giá dự đoán bám theo giá thực
    predicted_price = current_price + random.uniform(-30, 30)
    return round(predicted_price, 2)