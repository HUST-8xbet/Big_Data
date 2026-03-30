from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 1. Khởi tạo Spark Session
spark = SparkSession.builder \
    .appName("Crypto_SpeedLayer_InfluxDB") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("🚀 [SPARK] Đã khởi động! Bắt đầu hút dữ liệu và bơm vào InfluxDB...")

# 2. Định nghĩa Schema JSON
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("timestamp", LongType(), True)
])

# 3. Đọc dữ liệu từ Kafka
raw_stream = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "binance_live_prices") \
    .option("startingOffsets", "latest") \
    .load()

# 4. Parse JSON
parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), schema).alias("data")) \
    .select("data.*")

# ==========================================
# 5. HÀM GHI DỮ LIỆU VÀO INFLUXDB THEO LÔ
# ==========================================
def write_to_influxdb(batch_df, batch_id):
    # Kéo dữ liệu của lô hiện tại về Driver để xử lý
    records = batch_df.collect()
    if not records:
        return

    # Thông tin kết nối InfluxDB (Lấy từ docker-compose.yml)
    url = "http://influxdb:8086"
    token = "super-secret-token-12345"
    org = "crypto_org"
    bucket = "crypto_prices"

    # Khởi tạo Client
    client = InfluxDBClient(url=url, token=token, org=org)
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
    write_api.write(bucket=bucket, record=points)
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