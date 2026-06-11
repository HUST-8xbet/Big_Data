import sys
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

# Thêm đường dẫn để import được config.settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config.settings import KAFKA_BROKER, KAFKA_TOPIC_PRICES
except ImportError:
    # Fallback cho local nếu chưa có settings
    KAFKA_BROKER = "localhost:9092"
    KAFKA_TOPIC_PRICES = "raw_prices"

# 1. Khởi tạo Spark Session
spark = SparkSession.builder \
    .appName("Crypto_SpeedLayer") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print(f"🚀 [SPEED LAYER] Đang lắng nghe luồng giá từ {KAFKA_TOPIC_PRICES} tại {KAFKA_BROKER}...")

# 2. Schema
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("timestamp", LongType(), True)
])

# 3. Đọc luồng dữ liệu
raw_stream = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC_PRICES) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

# 4. Parse JSON
parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), schema).alias("data")) \
    .select("data.*")

# 5. Output
query = parsed_stream \
    .writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", "false") \
    .start()

query.awaitTermination()