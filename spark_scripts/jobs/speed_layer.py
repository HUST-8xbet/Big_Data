from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

# 1. Khởi tạo Spark Session (Bộ não chính)
spark = SparkSession.builder \
    .appName("Crypto_SpeedLayer") \
    .getOrCreate()

# Giảm bớt các dòng log rác để màn hình dễ nhìn hơn
spark.sparkContext.setLogLevel("WARN")
print("🚀 [SPARK] Đã khởi động thành công! Đang lắng nghe luồng giá từ Kafka...")

# 2. Định nghĩa cấu trúc khung xương (Schema) cho JSON từ Binance
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("timestamp", LongType(), True)
])

# 3. Đọc luồng dữ liệu liên tục từ Topic Kafka (Streaming)
raw_stream = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "binance_live_prices") \
    .option("startingOffsets", "latest") \
    .load()

# 4. Gọt giũa dữ liệu (Parse JSON)
# Kafka lưu dữ liệu dạng nhị phân, ta cần chuyển thành String rồi ốp Schema vào
parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), schema).alias("data")) \
    .select("data.*")

# 5. In thẳng ra màn hình Console để Test luồng chạy
query = parsed_stream \
    .writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", "false") \
    .start()

query.awaitTermination()