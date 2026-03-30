from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, struct
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

# 1. Khởi tạo Spark Session (Kèm theo Driver để kết nối PostgreSQL)
spark = SparkSession.builder \
    .appName("Crypto_Dynamic_Alerts") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.5.4") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("🔥 [SPARK] Đã bật Radar Cảnh Báo Động! Đang liên tục quét luật từ PostgreSQL...")

# 2. Schema dữ liệu Live từ Kafka
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("timestamp", LongType(), True)
])

# 3. Đọc dữ liệu Real-time từ Kafka
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "binance_live_prices") \
    .load()

parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), schema).alias("data")).select("data.*")

# ==========================================
# 4. HÀM XỬ LÝ LÔ DỮ LIỆU ĐỘNG (Stream-Static Join)
# ==========================================
def process_dynamic_alerts(batch_df, batch_id):
    # Nếu lô dữ liệu trống (không có giao dịch mới), bỏ qua cho đỡ tốn tài nguyên
    if batch_df.isEmpty():
        return

    try:
        # BƯỚC A: Đọc bảng "Luật Cảnh Báo" (user_alerts) từ PostgreSQL mới nhất
        # Lưu ý: Sửa user/password/db_name cho khớp với file docker-compose của bạn
        rules_df = spark.read \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/crypto_db") \
            .option("dbtable", "user_alerts") \
            .option("user", "admin") \
            .option("password", "password123") \
            .option("driver", "org.postgresql.Driver") \
            .load()

        # BƯỚC B: Chập dữ liệu (Join) - Tìm những luật có chung symbol với giá Live
        joined_df = batch_df.join(rules_df, "symbol", "inner")

        # BƯỚC C: Logic Khớp Lệnh (Bộ lọc sấm sét)
        # Bảng rules_df có cột 'condition' (điều kiện) là 'UP' (Vượt ngưỡng) hoặc 'DOWN' (Thủng đáy)
        matched_alerts = joined_df.filter(
            # 1. Nếu luật là canh GIÁ (PRICE)
            ((col("alert_type") == "PRICE") & (col("condition") == "UP") & (col("price") >= col("target_value"))) |
            ((col("alert_type") == "PRICE") & (col("condition") == "DOWN") & (col("price") <= col("target_value"))) |
            
            # 2. Nếu luật là săn CÁ MẬP (VOLUME) - Khối lượng giao dịch đột biến
            ((col("alert_type") == "VOLUME") & (col("condition") == "UP") & (col("volume") >= col("target_value")))
        )
        
        # BƯỚC D: Đóng gói và gửi vào Kafka nếu có người khớp lệnh
        if not matched_alerts.isEmpty():
            alert_count = matched_alerts.count()
            print(f"🚨 PHÁT HIỆN {alert_count} CẢNH BÁO KHỚP LỆNH! (Lô {batch_id}) - Đang đẩy vào Kafka...")
            
            # Ép kiểu thành JSON để Kafka hiểu được
            kafka_output = matched_alerts.selectExpr(
                "CAST(alert_id AS STRING) AS key", 
                "to_json(struct(*)) AS value"
            )

            # Bơm vào Topic user_alerts_topic
            kafka_output.write \
                .format("kafka") \
                .option("kafka.bootstrap.servers", "kafka:29092") \
                .option("topic", "user_alerts_topic") \
                .save()
            
    except Exception as e:
        # Bắt lỗi nếu PostgreSQL chưa có bảng, sai pass,...
        print(f"⚠️ Lỗi khi xử lý Lô {batch_id}: {str(e)}")

# 5. Kích hoạt vòi xả
query = parsed_stream.writeStream \
    .foreachBatch(process_dynamic_alerts) \
    .start()

query.awaitTermination()