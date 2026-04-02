# Đọc config và thư viện nội bộ (Module hóa)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, udf, schema_of_json
from pyspark.sql.types import StringType
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from config.settings import KAFKA_BROKER, KAFKA_TOPIC_PRICES, INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
from utils.schemas import BINANCE_SCHEMA
from ml.predictor import apply_ml_prediction

# 1. Đăng ký hàm ML thành Spark UDF (User Defined Function) để chạy song song
ml_predict_udf = udf(apply_ml_prediction, StringType())

# 2. Khởi tạo Spark Session
spark = SparkSession.builder \
    .appName("Crypto_ML_Predictor") \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")
print("🤖 [SPARK ML] Đã nạp Mô hình AI. Đang dự đoán giá theo thời gian thực...")

# 3. Đọc dữ liệu Real-time
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC_PRICES) \
    .load()

# 4. Parse JSON và Thêm cột Dự đoán (Feature Injection)
df_parsed = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), BINANCE_SCHEMA).alias("data")).select("data.*")

# Đưa dữ liệu qua hàm suy luận ML
df_with_predictions = df_parsed.withColumn(
    "ml_result_json", 
    ml_predict_udf(col("price"), col("volume"))
)

# Bóc tách JSON kết quả từ ML ra thành các cột riêng biệt
prediction_schema = schema_of_json('{"predicted_price": 0.0, "trend": "UP", "confidence_score": 0.0}')
final_df = df_with_predictions.withColumn(
    "ml_result", from_json(col("ml_result_json"), prediction_schema)
).select(
    "symbol", "price", "volume", "timestamp",
    col("ml_result.predicted_price").alias("predicted_price"),
    col("ml_result.trend").alias("trend"),
    col("ml_result.confidence_score").alias("confidence_score")
)

# 5. Hàm ghi dữ liệu dự đoán vào InfluxDB (Lưu ở bảng ml_predictions)
def write_predictions_to_influx(batch_df, batch_id):
    records = batch_df.collect()
    if not records: return

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    points = []
    
    for row in records:
        p = Point("ml_predictions") \
            .tag("symbol", row["symbol"]) \
            .tag("trend_direction", row["trend"]) \
            .field("current_price", float(row["price"])) \
            .field("predicted_price", float(row["predicted_price"])) \
            .field("confidence", float(row["confidence_score"])) \
            .time(row["timestamp"], write_precision='ms')
        points.append(p)

    write_api.write(bucket=INFLUX_BUCKET, record=points)
    write_api.close()
    client.close()
    print(f"🎯 Đã chốt {len(points)} dự đoán ML vào InfluxDB (Lô số {batch_id})")

# 6. Kích hoạt vòi xả
query = final_df.writeStream \
    .foreachBatch(write_predictions_to_influx) \
    .start()

query.awaitTermination()