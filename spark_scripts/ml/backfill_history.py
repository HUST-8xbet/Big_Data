#!/usr/bin/env python3
"""
Backfill dữ liệu lịch sử (nến 1 phút) từ Binance Klines API → InfluxDB
Giúp có đủ data để train_model.py chạy ngay, không cần đợi crawler.
Chạy: python spark_scripts/ml/backfill_history.py
"""

import time
import os
from datetime import datetime, timedelta, timezone

import requests
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "super-secret-token-12345")
INFLUX_ORG = os.getenv("INFLUX_ORG", "crypto_org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "crypto_prices")

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
INTERVAL = "1m"
LIMIT = 1000  # tối đa Binance cho phép mỗi request
SLEEP_SECONDS = float(os.getenv("BACKFILL_SLEEP_SECONDS", "0.2"))
DAYS_BACK = float(os.getenv("BACKFILL_DAYS", "60"))

DEFAULT_COINS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'ADAUSDT', 'DOGEUSDT', 'TRXUSDT', 'LINKUSDT', 'AVAXUSDT',
    'XLMUSDT', 'SUIUSDT', 'TONUSDT', 'HBARUSDT', 'SHIBUSDT',
    'LTCUSDT', 'DOTUSDT', 'BCHUSDT', 'UNIUSDT', 'NEARUSDT',
    'APTUSDT', 'AAVEUSDT', 'ETCUSDT', 'ICPUSDT', 'FILUSDT',
    'ARBUSDT', 'OPUSDT', 'INJUSDT', 'ATOMUSDT', 'POLUSDT',
]
COINS = [
    coin.strip().upper()
    for coin in os.getenv("BINANCE_COINS", ",".join(DEFAULT_COINS)).split(",")
    if coin.strip()
]


def fetch_klines(symbol, start_ms, end_ms):
    """Lấy toàn bộ nến 1 phút trong khoảng [start_ms, end_ms], tự phân trang."""
    all_klines = []
    cur_start = start_ms

    while cur_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": INTERVAL,
            "startTime": cur_start,
            "endTime": end_ms,
            "limit": LIMIT,
        }

        for attempt in range(5):
            try:
                resp = requests.get(BINANCE_KLINES_URL, params=params, timeout=15)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                wait = 2 ** attempt
                print(f"  ⏳ Lỗi mạng ({e.__class__.__name__}), thử lại sau {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 429:
                print("  ⏳ Rate limit, chờ 5s...")
                time.sleep(5)
                continue

            resp.raise_for_status()
            break
        else:
            raise RuntimeError(f"Không thể lấy dữ liệu cho {symbol} sau nhiều lần thử")

        klines = resp.json()
        if not klines:
            break

        all_klines.extend(klines)
        cur_start = klines[-1][6] + 1  # bắt đầu sau close_time của nến cuối

        if len(klines) < LIMIT:
            break

        time.sleep(SLEEP_SECONDS)

    return all_klines


def main():
    print("=" * 60)
    print("📥 Backfill dữ liệu lịch sử từ Binance Klines API")
    print("=" * 60)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=DAYS_BACK)
    end_ms = int(end_time.timestamp() * 1000)
    start_ms = int(start_time.timestamp() * 1000)

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    total_points = 0
    for symbol in COINS:
        print(f"\n📊 {symbol}: đang lấy {DAYS_BACK} ngày dữ liệu...")
        try:
            klines = fetch_klines(symbol, start_ms, end_ms)
        except Exception as e:
            print(f"  ❌ Lỗi: {e}")
            continue

        points = []
        for k in klines:
            close_time_ms = k[6]
            close_price = float(k[4])
            volume = float(k[5])
            points.append(
                Point("market_data")
                .tag("symbol", symbol)
                .field("price", close_price)
                .field("volume", volume)
                .time(close_time_ms, write_precision="ms")
            )

        if points:
            write_api.write(bucket=INFLUX_BUCKET, record=points)
            total_points += len(points)
            print(f"  ✅ Đã ghi {len(points)} điểm vào InfluxDB")

    write_api.close()
    client.close()

    print("\n" + "=" * 60)
    print(f"✅ Hoàn tất! Tổng cộng {total_points} điểm cho {len(COINS)} coin")
    print("💡 Bây giờ có thể chạy: python spark_scripts/ml/train_model.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
