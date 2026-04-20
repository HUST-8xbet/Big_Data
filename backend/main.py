from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
from datetime import datetime
from influxdb_client import InfluxDBClient
try:
    from influxdb_client.client.warnings import MissingPivotFunction
except (ImportError, ModuleNotFoundError):
    # Nếu không tìm thấy, gán bằng None để tránh sập hệ thống
    MissingPivotFunction = None
    print("⚠️  Cảnh báo: Bỏ qua MissingPivotFunction do phiên bản thư viện mới.")

from ml_service import load_ml_model, predict_future_price

app = FastAPI(title="Crypto Price Prediction API")

# ✅ CORS cho Kubernetes (frontend sẽ có host khác)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

my_ml_model = load_ml_model()

# ✅ Dùng environment variables - mặc định cho localhost (dev mode)
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "super-secret-token-12345")
INFLUX_ORG = os.getenv("INFLUX_ORG", "crypto_org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "crypto_prices")

import warnings
warnings.simplefilter("ignore", MissingPivotFunction)
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = influx_client.query_api()

# ✅ Health Check endpoints cho Kubernetes
@app.get("/health")
@app.get("/healthz")
def health_check():
    """Liveness probe - kiểm tra app đang chạy"""
    return {"status": "alive", "service": "crypto-backend"}

@app.get("/ready")
def readiness_check():
    """Readiness probe - kiểm tra app sẵn sàng nhận request"""
    try:
        # Test kết nối InfluxDB
        influx_client.ping()
        return {"status": "ready", "influxdb": "connected"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}, 503

@app.get("/api/market-summary")
def get_market_summary():
    summary_data = []
    # Lấy dữ liệu 15 phút qua, cứ mỗi 1 phút chốt 1 điểm giá (để vẽ biểu đồ cho nhẹ)
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -2h)  
        |> filter(fn: (r) => r["_measurement"] == "market_data")
        |> filter(fn: (r) => r["_field"] == "price")
        |> aggregateWindow(every: 1m, fn: last, createEmpty: false)
        |> yield(name: "last")
    '''
    try:
        tables = query_api.query(query, org=INFLUX_ORG)
        
        # Gom nhóm dữ liệu giá thành mảng theo từng đồng coin
        coin_dict = {}
        for table in tables:
            for record in table.records:
                symbol = record.values.get("symbol")
                val = record.get_value()
                if val is not None:
                    if symbol not in coin_dict:
                        coin_dict[symbol] = []
                    coin_dict[symbol].append(val)
        
        # Xử lý tính toán
        for symbol, prices in coin_dict.items():
            if len(prices) > 0:
                current_price = prices[-1] # Giá mới nhất (cuối mảng)
                old_price = prices[0]      # Giá lúc bắt đầu (đầu mảng)
                
                # Tính % biến động
                change_pct = ((current_price - old_price) / old_price) * 100 if old_price > 0 else 0
                
                summary_data.append({
                    "id": symbol,
                    "name": symbol.replace("USDT", ""),
                    "symbol": symbol.lower(),
                    "current_price": round(current_price, 2),
                    "price_change_percentage_24h": change_pct, # Trả về số thật
                    "sparkline": prices # Tranh thủ gửi luôn mảng giá để FE vẽ biểu đồ
                })
    except Exception as e:
        print(f"Lỗi lấy dữ liệu tổng quan InfluxDB: {e}")
        
    return summary_data

# 1. API Lấy lịch sử (Thêm {symbol} vào đường dẫn)
@app.get("/api/historical-price/{symbol}")
def get_historical_price(symbol: str):
    history_data = []
    
    # ĐÃ SỬA: Lấy lịch sử 2 tiếng (-2h) và gộp mỗi 1 phút 1 điểm (every: 1m)
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -2h)
        |> filter(fn: (r) => r["_measurement"] == "market_data")
        |> filter(fn: (r) => r["symbol"] == "{symbol}")
        |> filter(fn: (r) => r["_field"] == "price")
        |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
        |> yield(name: "mean")
    '''
    try:
        tables = query_api.query(query, org=INFLUX_ORG)
        for table in tables:
            for record in table.records:
                time_point = record.get_time()
                real_price = record.get_value()
                if real_price is None: continue
                
                predicted = predict_future_price(my_ml_model, real_price)
                history_data.append({
                    "time": time_point.strftime("%H:%M:%S"),
                    "real_price": round(real_price, 2),
                    "predicted_price": predicted
                })
    except Exception as e:
        print(f"Lỗi lấy lịch sử InfluxDB: {e}")
    return history_data

# 2. WebSocket Streaming (Thêm {symbol} vào đường dẫn)
@app.websocket("/ws/live-price/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await websocket.accept()
    try:
        while True:
            # Thay cứng "BTCUSDT" bằng biến {symbol}
            query = f'''
                from(bucket: "{INFLUX_BUCKET}")
                |> range(start: -10s)
                |> filter(fn: (r) => r["_measurement"] == "market_data")
                |> filter(fn: (r) => r["symbol"] == "{symbol}")
                |> filter(fn: (r) => r["_field"] == "price")
                |> last()
            '''
            tables = query_api.query(query, org=INFLUX_ORG)
            
            now_str = datetime.now().strftime("%H:%M:%S")
            real_price = None
            
            for table in tables:
                for record in table.records:
                    real_price = record.get_value()
                    now_str = record.get_time().strftime("%H:%M:%S")
            
            if real_price is not None:
                predicted = predict_future_price(my_ml_model, real_price)
                data_packet = {
                    "time": now_str,
                    "real_price": round(real_price, 2),
                    "predicted_price": predicted
                }
                await websocket.send_json(data_packet)
                
            await asyncio.sleep(2)
    except Exception as e:
        print(f"Bị ngắt kết nối WebSocket đồng {symbol}: {e}")