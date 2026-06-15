#!/usr/bin/env python3
"""
Script để huấn luyện mô hình LSTM trên dữ liệu lịch sử
Chạy: python train_model.py
"""

from influxdb_client import InfluxDBClient
from ml_service import train_model_on_historical_data
import warnings
import os

warnings.simplefilter("ignore")

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "super-secret-token-12345"
INFLUX_ORG = "crypto_org"
INFLUX_BUCKET = "crypto_prices"
TRAIN_DAYS = float(os.getenv("TRAIN_DAYS", "7"))
TRAIN_MINUTES = max(1, int(TRAIN_DAYS * 24 * 60))

def fetch_all_historical_data():
    """
    Lấy toàn bộ dữ liệu lịch sử từ InfluxDB
    """
    print("📊 Đang lấy dữ liệu lịch sử từ InfluxDB...")
    
    influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = influx_client.query_api()
    
    # Lấy dữ liệu theo nến 1 phút. Realtime trade stream có thể rất dày,
    # còn LSTM đang giả định mỗi timestep là 1 phút.
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -{TRAIN_MINUTES}m)
        |> filter(fn: (r) => r["_measurement"] == "market_data")
        |> filter(fn: (r) => r["_field"] == "price")
        |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
        |> sort(columns: ["_time"])
    '''
    
    historical_data = {}
    
    try:
        tables = query_api.query(query, org=INFLUX_ORG)
        
        for table in tables:
            for record in table.records:
                symbol = record.values.get("symbol")
                price = record.get_value()
                
                if symbol and price is not None:
                    if symbol not in historical_data:
                        historical_data[symbol] = []
                    historical_data[symbol].append(price)
        
        # Thống kê dữ liệu
        print("\n📈 Thống kê dữ liệu:")
        for symbol, prices in historical_data.items():
            print(f"  {symbol}: {len(prices)} điểm dữ liệu")
        
        print(f"\n✅ Tổng cộng {len(historical_data)} coin")
        
        influx_client.close()
        return historical_data
        
    except Exception as e:
        print(f"❌ Lỗi lấy dữ liệu: {e}")
        influx_client.close()
        return {}

def main():
    print("=" * 60)
    print("🤖 LSTM Model Training Script")
    print("=" * 60)
    
    # Lấy dữ liệu
    historical_data = fetch_all_historical_data()
    
    if not historical_data:
        print("\n❌ Không có dữ liệu để huấn luyện. Vui lòng kiểm tra InfluxDB.")
        return
    
    # Huấn luyện mô hình
    print("\n🔧 Đang huấn luyện mô hình LSTM...")
    train_model_on_historical_data(historical_data)

    print("\n" + "=" * 60)
    print("✅ Huấn luyện hoàn tất! Bạn có thể khởi động backend ngay.")
    print("=" * 60)

if __name__ == "__main__":
    main()
