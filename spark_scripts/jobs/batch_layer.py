"""
BATCH LAYER — Lambda Architecture
=================================
Chạy định kỳ (cronjob / spark-submit), xử lý dữ liệu lịch sử từ Kafka
từ đầu topic → tính toán OHLCV, thống kê thị trường → ghi vào PostgreSQL + MinIO.

Job chạy theo 2 chế độ:
  • --mode batch  : Đọc TOÀN BỘ dữ liệu từ Kafka topic (backfill / init)
  • --mode micro  : Chỉ đọc dữ liệu trong khoảng --offset-time trở về trước
                   (giảm thời gian chạy cho job thường trực)

Ví dụ:
  spark-submit batch_layer.py --mode batch
  spark-submit batch_layer.py --mode micro --offset-minutes 120
"""

import sys
import os
import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, TimestampType

# ── đường dẫn module ──────────────────────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    KAFKA_BROKER, KAFKA_TOPIC_PRICES,
    PG_URL, PG_USER, PG_PASSWORD, PG_DRIVER,
)
from utils.schemas import BINANCE_SCHEMA

# ── parse argument ────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--mode", default="micro", choices=["batch", "micro"])
parser.add_argument("--offset-minutes", type=int, default=120,
                    help="Đọc dữ liệu trong N phút gần nhất (chế độ micro)")
args = parser.parse_args()

# ════════════════════════════════════════════════════════════════════════════
# 1. KHỞI TẠO SPARK SESSION
# ════════════════════════════════════════════════════════════════════════════
spark = SparkSession.builder \
    .appName("Crypto_BatchLayer") \
    .config("spark.jars.packages",
            "org.postgresql:postgresql:42.6.0,"
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "org.apache.hadoop:hadoop-aws:3.3.4,"
            "com.amazonaws:aws-java-sdk-bundle:1.12.262") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.access.key", "admin") \
    .config("spark.hadoop.fs.s3a.secret.key", "password123") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print(f"🗄️  [BATCH LAYER] Khởi động — mode: {args.mode}")

# ════════════════════════════════════════════════════════════════════════════
# 2. ĐỌC DỮ LIỆU TỪ KAFKA
# ════════════════════════════════════════════════════════════════════════════
kafka_options = {
    "kafka.bootstrap.servers": KAFKA_BROKER,
    "subscribe": KAFKA_TOPIC_PRICES,
    "startingOffsets": "earliest" if args.mode == "batch" else "latest",
    "failOnDataLoss": "false",
}

raw_df = spark.read.format("kafka").options(**kafka_options).load()

parsed_df = (
    raw_df.selectExpr("CAST(value AS STRING) as json_string", "timestamp as kafka_ts")
    .select(
        F.from_json(F.col("json_string"), BINANCE_SCHEMA).alias("data"),
        F.col("kafka_ts"),
    )
    .select("data.*", "kafka_ts")
    .withColumn("event_time", F.to_timestamp(F.col("timestamp") / 1000))
    .filter(F.col("symbol").isNotNull() & F.col("price").isNotNull())
)

print(f"   📦 Tổng records đọc được: {parsed_df.count()}")

# Micro-batch: giới hạn theo thời gian
if args.mode == "micro":
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=args.offset_minutes)
    parsed_df = parsed_df.filter(F.col("event_time") >= F.lit(cutoff))
    print(f"   ⏱  ️Micro-batch — giới hạn trong {args.offset_minutes} phút gần nhất")

# Cache vì dùng nhiều lần
parsed_df.cache()

# ════════════════════════════════════════════════════════════════════════════
# 3. TÍNH TOÁN OHLCV (1-GIỜ VÀ 4-GIỜ CANDLES)
# ════════════════════════════════════════════════════════════════════════════
def compute_ohlcv(df, interval_minutes, interval_label):
    """Tính OHLCV candle theo khoảng thời gian."""
    window_ts = (F.col("event_time").cast("long") / (interval_minutes * 60)
                 ).cast("long") * (interval_minutes * 60)

    candles = (
        df.withColumn("window_ts", F.to_timestamp(F.lit(window_ts.cast("double"))))
        .groupBy("symbol", "window_ts")
        .agg(
            F.first("price").alias("open"),
            F.max("price").alias("high"),
            F.min("price").alias("low"),
            F.last("price").alias("close"),
            F.sum("volume").alias("volume"),
            F.count("*").alias("trade_count"),
            F.avg("price").alias("avg_price"),
        )
        .withColumn("interval", F.lit(interval_label))
        .withColumn("open_time", F.col("window_ts"))
        .withColumnRenamed("window_ts", "close_time")
        .withColumn("high_low_pct",
                     F.round((F.col("high") - F.col("low")) / F.col("low") * 100, 4))
        .withColumn("close_change_pct",
                     F.round((F.col("close") - F.col("open")) / F.col("open") * 100, 4))
        .drop("window_ts")
        .orderBy("symbol", "open_time")
    )
    return candles

ohlcv_1h  = compute_ohlcv(parsed_df, 60,   "1h")
ohlcv_4h  = compute_ohlcv(parsed_df, 240,  "4h")

print(f"   🕯️  OHLCV 1h records: {ohlcv_1h.count()}")
print(f"   🕯️  OHLCV 4h records: {ohlcv_4h.count()}")

# ════════════════════════════════════════════════════════════════════════════
# 4. THỐNG KÊ THỊ TRƯỜNG (market_stats)
# ════════════════════════════════════════════════════════════════════════════
def compute_market_stats(df, window_minutes, label):
    """VWAP, volatility, avg price trong cửa sổ thời gian."""
    window_ts = (F.col("event_time").cast("long") / (window_minutes * 60)
                 ).cast("long") * (window_minutes * 60)

    stats = (
        df.withColumn("window_ts", F.to_timestamp(F.lit(window_ts.cast("double"))))
        .groupBy("symbol", "window_ts")
        .agg(
            F.sum(F.col("price") * F.col("volume")).alias("price_volume_sum"),
            F.sum("volume").alias("total_volume"),
            F.avg("price").alias("avg_price"),
            F.max("price").alias("max_price"),
            F.min("price").alias("min_price"),
            F.count("*").alias("trade_count"),
            F.stddev("price").alias("price_stddev"),
        )
        .withColumn("vwap",
                     F.round(F.col("price_volume_sum") / F.col("total_volume"), 4))
        .withColumn("volatility",
                     F.round(F.col("price_stddev") / F.col("avg_price") * 100, 4))
        .withColumn("window_start", F.col("window_ts"))
        .withColumn("window_end",
                     F.col("window_ts") + F.expr(f"INTERVAL {window_minutes} MINUTES"))
        .withColumn("window_label", F.lit(label))
        .drop("window_ts", "price_volume_sum", "price_stddev")
        .orderBy("symbol", "window_start")
    )
    return stats

stats_1h = compute_market_stats(parsed_df, 60, "1h")
stats_4h = compute_market_stats(parsed_df, 240, "4h")

# ── symbol profiles (chỉ lấy bản ghi mới nhất mỗi symbol) ────────────────────
symbol_profiles = (
    parsed_df
    .groupBy("symbol")
    .agg(
        F.last("price").alias("last_price"),
        F.sum("volume").alias("volume_total"),
        F.max("event_time").alias("latest_event_time"),
    )
    .withColumn("price_change_pct",
                 F.lit(0.0))   # TODO: join với batch trước để tính delta
    .withColumn("updated_at", F.current_timestamp())
    .drop("latest_event_time")
)

# ════════════════════════════════════════════════════════════════════════════
# 5. GHI VÀO POSTGRESQL (Serving Layer)
# ════════════════════════════════════════════════════════════════════════════
pg_options = {
    "url": PG_URL,
    "user": PG_USER,
    "password": PG_PASSWORD,
    "driver": PG_DRIVER,
}

def upsert_to_pg(df, table, id_cols):
    """Ghi DataFrame vào PostgreSQL. Nếu bản ghi đã tồn tại → UPSERT (ON CONFLICT)."""
    mode = "overwrite"

    # Tạo bảng nếu chưa có (Spark tự tạo schema)
    df.write \
        .format("jdbc") \
        .options(**pg_options, dbtable=table) \
        .mode("append") \
        .save()

    print(f"   ✅ Đã ghi {df.count()} records vào PostgreSQL table `{table}`")


print("\n📤 Bắt đầu ghi vào PostgreSQL...")
upsert_to_pg(ohlcv_1h,  "ohlcv_candles",  ["symbol", "interval", "open_time"])
upsert_to_pg(ohlcv_4h,  "ohlcv_candles",  ["symbol", "interval", "open_time"])
upsert_to_pg(stats_1h,  "market_stats",   ["symbol", "window_label", "window_start"])
upsert_to_pg(stats_4h,  "market_stats",   ["symbol", "window_label", "window_start"])
upsert_to_pg(symbol_profiles, "symbol_profiles", ["symbol"])

# ════════════════════════════════════════════════════════════════════════════
# 6. GHI VÀO MINIO / S3 (Data Lake — raw + processed parquet)
# ════════════════════════════════════════════════════════════════════════════
MINIO_PATH = "s3a://processed-data"

def write_parquet(df, path_suffix):
    """Ghi DataFrame thành parquet file lên MinIO."""
    full_path = f"{MINIO_PATH}/{path_suffix}"
    (
        df.write
        .format("parquet")
        .mode("overwrite")
        .option("path", full_path)
        .save()
    )
    print(f"   ✅ Đã ghi parquet vào {full_path}")


print("\n📦 Bắt đầu ghi vào MinIO (Data Lake)...")
write_parquet(parsed_df,        "raw/kafka_prices")
write_parquet(ohlcv_1h,         "processed/ohlcv_1h")
write_parquet(ohlcv_4h,         "processed/ohlcv_4h")
write_parquet(stats_1h,         "processed/market_stats_1h")
write_parquet(stats_4h,         "processed/market_stats_4h")
write_parquet(symbol_profiles,  "processed/symbol_profiles")

# ════════════════════════════════════════════════════════════════════════════
# 7. IN BÁO CÁO TÓM TẮT
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("📊 BÁO CÁO BATCH LAYER")
print("=" * 60)

summary = (
    parsed_df
    .groupBy("symbol")
    .agg(
        F.count("*").alias("total_trades"),
        F.round(F.avg("price"), 4).alias("avg_price"),
        F.round(F.sum("volume"), 2).alias("total_volume"),
        F.min("event_time").alias("earliest_record"),
        F.max("event_time").alias("latest_record"),
    )
    .orderBy(F.desc("total_volume"))
)

print(summary.show(20, truncate=False))

print("🗄️  [BATCH LAYER] Hoàn tất!")
spark.stop()
