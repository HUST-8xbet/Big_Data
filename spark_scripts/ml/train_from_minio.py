#!/usr/bin/env python3
"""
Train LSTM from batched raw trade files in MinIO.

Expected object format, written by Crawler/binance_producer.py:
  bucket: raw-data
  key:    binance/trades_YYYYmmdd_HHMMSS.json
  body:   [{"symbol": "BTCUSDT", "price": 123.4, "volume": 0.01, "timestamp": 1710000000000}, ...]

The trainer aggregates dense trades into 1-minute mean prices because the LSTM
uses one timestep per minute.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
import sys
import warnings

import boto3
from botocore.config import Config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.ml_service import MODEL_PATH, train_model_on_historical_data

warnings.simplefilter("ignore")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", os.getenv("MINIO_ACCESS_KEY", "admin"))
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", os.getenv("MINIO_SECRET_KEY", "password123"))
MINIO_BUCKET = os.getenv("MINIO_TRAIN_BUCKET", os.getenv("MINIO_RAW_BUCKET", "raw-data"))
MINIO_PREFIX = os.getenv("MINIO_TRAIN_PREFIX", "binance/")
MODEL_BUCKET = os.getenv("MINIO_MODEL_BUCKET", "ml-models")
MODEL_KEY = os.getenv("MINIO_MODEL_KEY", "lstm/model.pt")
TRAIN_DAYS = float(os.getenv("TRAIN_DAYS", "7"))
MAX_MINIO_OBJECTS = int(os.getenv("MAX_MINIO_OBJECTS", "0"))
UPLOAD_MODEL_TO_MINIO = os.getenv("UPLOAD_MODEL_TO_MINIO", "0").lower() in {"1", "true", "yes"}


def create_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def iter_object_keys(s3_client):
    paginator = s3_client.get_paginator("list_objects_v2")
    seen = 0

    for page in paginator.paginate(Bucket=MINIO_BUCKET, Prefix=MINIO_PREFIX):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not key.endswith(".json"):
                continue

            yield key
            seen += 1
            if MAX_MINIO_OBJECTS and seen >= MAX_MINIO_OBJECTS:
                return


def load_json_object(s3_client, key):
    response = s3_client.get_object(Bucket=MINIO_BUCKET, Key=key)
    body = response["Body"].read()
    return json.loads(body)


def fetch_minio_historical_data():
    print("📦 Đang lấy dữ liệu batch từ MinIO...")
    print(f"   endpoint={MINIO_ENDPOINT}")
    print(f"   bucket={MINIO_BUCKET}")
    print(f"   prefix={MINIO_PREFIX}")
    print(f"   train_days={TRAIN_DAYS}")

    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=TRAIN_DAYS)).timestamp() * 1000)
    s3_client = create_s3_client()
    minute_buckets = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))

    object_count = 0
    record_count = 0
    kept_count = 0

    for key in iter_object_keys(s3_client):
        object_count += 1
        try:
            records = load_json_object(s3_client, key)
        except Exception as exc:
            print(f"  ⚠️  Bỏ qua {key}: {exc}")
            continue

        if not isinstance(records, list):
            print(f"  ⚠️  Bỏ qua {key}: body không phải JSON list")
            continue

        for record in records:
            record_count += 1
            try:
                symbol = str(record["symbol"]).upper()
                price = float(record["price"])
                timestamp_ms = int(record["timestamp"])
            except (KeyError, TypeError, ValueError):
                continue

            if timestamp_ms < cutoff_ms:
                continue

            minute_ms = timestamp_ms - (timestamp_ms % 60000)
            bucket = minute_buckets[symbol][minute_ms]
            bucket[0] += price
            bucket[1] += 1
            kept_count += 1

    historical_data = {}
    for symbol, minute_values in minute_buckets.items():
        prices = [
            total / count
            for _, (total, count) in sorted(minute_values.items())
            if count > 0
        ]
        if prices:
            historical_data[symbol] = prices

    print("\n📈 Thống kê dữ liệu MinIO:")
    print(f"  objects đọc: {object_count}")
    print(f"  records đọc: {record_count}")
    print(f"  records dùng sau cutoff: {kept_count}")
    for symbol, prices in sorted(historical_data.items()):
        print(f"  {symbol}: {len(prices)} nến 1 phút")

    return historical_data, s3_client


def upload_model_to_minio(s3_client):
    if not UPLOAD_MODEL_TO_MINIO:
        return

    if not os.path.exists(MODEL_PATH):
        print(f"⚠️  Không thấy model tại {MODEL_PATH}, bỏ qua upload")
        return

    s3_client.upload_file(MODEL_PATH, MODEL_BUCKET, MODEL_KEY)
    print(f"☁️  Đã upload model lên s3://{MODEL_BUCKET}/{MODEL_KEY}")


def main():
    print("=" * 60)
    print("🤖 LSTM Training From MinIO Batch Data")
    print("=" * 60)

    historical_data, s3_client = fetch_minio_historical_data()
    if not historical_data:
        print("\n❌ Không có dữ liệu MinIO để train. Kiểm tra crawler và bucket raw-data.")
        return

    print("\n🔧 Đang huấn luyện mô hình LSTM...")
    train_model_on_historical_data(historical_data)
    upload_model_to_minio(s3_client)

    print("\n" + "=" * 60)
    print(f"✅ Huấn luyện hoàn tất. Model local: {MODEL_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
