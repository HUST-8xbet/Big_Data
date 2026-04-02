import sys
import os 

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 1. Nạp các module tự viết từ thư mục cha
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import KAFKA_BROKER, KAFKA_TOPIC_PRICES, INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
from utils.schemas import BINANCE_SCHEMA
# [CHANGED] SCHEMA được định nghĩa trong utils/schemas.py để tái sử dụng cho nhiều job khác nhau

# 1. Khởi tạo Spark Session
spark = SparkSession.builder \
    .appName("Crypto_SpeedLayer_InfluxDB") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("🚀 [SPARK] Đã khởi động! Bắt đầu hút dữ liệu và bơm vào InfluxDB...")

# 2. Đọc dữ liệu từ Kafka
raw_stream = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC_PRICES) \
    .option("startingOffsets", "latest") \
    .load()

# 3. Parse JSON
parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), BINANCE_SCHEMA).alias("data")) \
    .select("data.*")

# ==========================================
# 4. HÀM GHI DỮ LIỆU VÀO INFLUXDB THEO LÔ
# ==========================================
def write_to_influxdb(batch_df, batch_id):
    # Kéo dữ liệu của lô hiện tại về Driver để xử lý
    records = batch_df.collect()
    if not records:
        return

    # Khởi tạo Client
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    points = []
    for row in records:
        # Nặn từng dòng dữ liệu thành dạng Point của InfluxDB
        p = Point("market_data") \
            .tag("symbol", row["symbol"]) \
            .field("price", float(row["price"])) \
            .field("volume", float(row["volume"])) \
            .time(row["timestamp"], write_precision='ms')
        points.append(p)

    # Bơm cả mẻ vào DB
    write_api.write(bucket=INFLUX_BUCKET, record=points)
    write_api.close()
    client.close()
    
    print(f"✅ Đã chốt thành công {len(points)} bản ghi vào InfluxDB (Lô số {batch_id})")

# 6. Kích hoạt vòi xả
query = parsed_stream \
    .writeStream \
    .outputMode("append") \
    .foreachBatch(write_to_influxdb) \
    .start()

query.awaitTermination()