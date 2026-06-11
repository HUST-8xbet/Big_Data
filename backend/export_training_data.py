#!/usr/bin/env python3
"""
Export dữ liệu lịch sử từ InfluxDB (local) ra file training_data.npz
Sau đó scp file này lên server (RTX 4090) để train, không cần cài InfluxDB trên server.

Chạy: python export_training_data.py
"""

import numpy as np
from influxdb_client import InfluxDBClient
import warnings

warnings.simplefilter("ignore")

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "super-secret-token-12345"
INFLUX_ORG = "crypto_org"
INFLUX_BUCKET = "crypto_prices"

OUTPUT_FILE = "training_data.npz"


def main():
    print("=" * 60)
    print("📊 Export dữ liệu lịch sử từ InfluxDB → training_data.npz")
    print("=" * 60)

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -60d)
        |> filter(fn: (r) => r["_measurement"] == "market_data")
        |> filter(fn: (r) => r["_field"] == "price")
        |> sort(columns: ["_time"])
    '''

    historical_data = {}

    tables = query_api.query(query, org=INFLUX_ORG)
    for table in tables:
        for record in table.records:
            symbol = record.values.get("symbol")
            price = record.get_value()
            if symbol and price is not None:
                historical_data.setdefault(symbol, []).append(price)

    client.close()

    if not historical_data:
        print("❌ Không lấy được dữ liệu nào từ InfluxDB")
        return

    print("\n📈 Thống kê dữ liệu:")
    for symbol, prices in historical_data.items():
        print(f"  {symbol}: {len(prices)} điểm")

    arrays = {symbol: np.array(prices, dtype=np.float64) for symbol, prices in historical_data.items()}
    np.savez_compressed(OUTPUT_FILE, **arrays)

    print("\n" + "=" * 60)
    print(f"✅ Đã lưu {len(arrays)} coin vào {OUTPUT_FILE}")
    print("💡 Bước tiếp theo:")
    print(f"   scp {OUTPUT_FILE} user@server:~/Big_Data/backend/")
    print("   # trên server: python train_from_file.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
