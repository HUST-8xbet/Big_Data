from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime

# Khởi tạo ứng dụng FastAPI
app = FastAPI(title="Crypto Price Prediction API")

# CORS Middleware để cho phép Frontend truy cập API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép mọi nguồn (sau này deploy có thể đổi thành tên miền thật)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello Big Data! Server Backend đang chạy ngon lành."}

@app.get("/api/mock-price")
def get_mock_price():
    """
    API này trả về giá Bitcoin giả lập để Frontend test vẽ biểu đồ
    """
    # Sinh ra một mức giá ảo xoay quanh 60000
    mock_real_price = random.uniform(59000, 61000)
    # Giả lập mô hình ML dự đoán giá (lệch một chút so với giá thực)
    mock_predicted_price = mock_real_price + random.uniform(-100, 100)
    
    return {
        "coin": "BTC",
        "timestamp": datetime.now().isoformat(),
        "real_price": round(mock_real_price, 2),
        "predicted_price": round(mock_predicted_price, 2)
    }