# 🤖 XGBoost ML Model - Crypto Price Prediction

## Tổng Quan

Backend hiện tại đã được nâng cấp với **XGBoost + Feature Engineering** để dự đoán giá cryptocurrency một cách chính xác hơn.

---

## 🎯 Tính Năng

### Feature Engineering
Mô hình sử dụng 9 đặc trưng chính:

| Đặc trưng | Mô tả |
|----------|-------|
| **price** | Giá hiện tại |
| **ma5** | Moving Average 5 điểm |
| **ma10** | Moving Average 10 điểm |
| **ma20** | Moving Average 20 điểm |
| **momentum** | Tốc độ thay đổi giá |
| **volatility** | Độ biến động (độ lệch chuẩn) |
| **trend** | Xu hướng giá (slope) |
| **rsi** | Relative Strength Index |
| **price_ratio** | Tỷ lệ giá/MA20 |

### Mô hình XGBoost
- **n_estimators**: 100 cây quyết định
- **max_depth**: 6 (kiểm soát overfitting)
- **learning_rate**: 0.1 (tốc độ học)
- **subsample**: 0.8 (random sampling)

---

## 📦 Cài đặt Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Hoặc cài riêng:
```bash
pip install xgboost scikit-learn pandas numpy joblib
```

---

## 🚀 Cách Sử Dụng

### 1️⃣ Khởi động Backend (Lần Đầu)

Nếu chưa có `model.pkl`:

```bash
cd backend
python train_model.py  # ⚠️ Cần có dữ liệu trong InfluxDB
python main.py
```

### 2️⃣ Huấn luyện Mô hình (Khi có Dữ liệu)

Khi InfluxDB đã tích lũy đủ dữ liệu lịch sử:

```bash
cd backend
python train_model.py
```

**Output:**
```
📊 Đang lấy dữ liệu lịch sử từ InfluxDB...

📈 Thống kê dữ liệu:
  BTCUSDT: 8640 điểm dữ liệu
  ETHUSDT: 8640 điểm dữ liệu
  BNBUSDT: 8640 điểm dữ liệu
  ...

🔧 Đang huấn luyện mô hình XGBoost...
✅ Mô hình XGBoost đã được huấn luyện trên 25920 samples
💾 Model đã được lưu vào model.pkl
```

### 3️⃣ Chạy Backend với Mô hình Đã Huấn luyện

```bash
cd backend
python main.py
```

Backend sẽ:
- ✅ Load `model.pkl` (nếu có)
- ✅ Bắt đầu dự đoán với XGBoost
- ✅ Cập nhật price buffer cho mỗi coin
- ✅ Cung cấp predictions qua WebSocket và API

---

## 🔍 Cơ Chế Hoạt động

### Real-time Prediction Flow

```
1. Frontend gọi WebSocket: /ws/live-price/{symbol}
                    ↓
2. Backend nhận giá thực: real_price từ InfluxDB
                    ↓
3. update_price_buffer(symbol, real_price)
   → Lưu giá vào bộ đệm (120 điểm gần nhất)
                    ↓
4. create_features(price_history)
   → Tạo 9 đặc trưng từ lịch sử giá
                    ↓
5. model.predict(features)
   → XGBoost dự đoán giá tiếp theo
                    ↓
6. Kiểm soát ngoại lệ (±5%)
   → Đảm bảo prediction hợp lý
                    ↓
7. Gửi {real_price, predicted_price} về Frontend
```

---

## 📊 Ví dụ Kết quả

```json
{
  "time": "14:25:30",
  "real_price": 45230.50,
  "predicted_price": 45245.23
}
```

**Giải thích:**
- Giá thực tế: $45,230.50
- Giá dự đoán: $45,245.23
- Thay đổi dự kiến: +$14.73 (+0.03%)

---

## ⚙️ Cấu hình (Tùy chỉnh)

Sửa `ml_service.py` để thay đổi:

```python
# Kích thước buffer (số điểm giữ lại)
MAX_BUFFER_SIZE = 120  # 2 tiếng (1 điểm/phút)

# Độ lệch tối đa cho prediction (kiểm soát ngoại lệ)
max_deviation = current_price * 0.05  # 5%

# Tham số XGBoost
XGBRegressor(
    n_estimators=100,      # Tăng → chính xác hơn nhưng chậm hơn
    max_depth=6,           # Tăng → học chuỗi phức tạp, nhưng dễ overfit
    learning_rate=0.1,     # Giảm → học chậm hơn, chính xác hơn
)
```

---

## 🐛 Troubleshooting

### "⚠️ Sử dụng mô hình XGBoost chưa được huấn luyện"

**Nguyên nhân:** `model.pkl` chưa tồn tại hoặc InfluxDB chưa có dữ liệu  
**Giải pháp:**
```bash
# 1. Đảm bảo InfluxDB chạy
docker compose ps

# 2. Chờ dữ liệu tích lũy (5-10 phút)

# 3. Huấn luyện mô hình
python train_model.py

# 4. Chạy backend
python main.py
```

### Predictions quá ngẫu nhiên

**Nguyên nhân:** Chưa đủ dữ liệu lịch sử (< 20 điểm)  
**Giải pháp:** Mô hình sẽ tự động dự đoán chính xác hơn khi có dữ liệu.

---

## 📈 Performance Tips

1. **Tăng tần suất huấn luyện**: Chạy `python train_model.py` hàng ngày
2. **Giảm MAX_BUFFER_SIZE** nếu cần tiết kiệm RAM
3. **Tăng n_estimators** nếu muốn độ chính xác cao hơn

---

## 📚 Thêm Thông tin

- [XGBoost Docs](https://xgboost.readthedocs.io/)
- [Scikit-learn Preprocessing](https://scikit-learn.org/stable/modules/preprocessing.html)
- [Feature Engineering Best Practices](https://github.com/Idiot-Alex/feature-engineering)

---

**✅ Dự đoán bằng XGBoost sẵn sàng!** 🚀
