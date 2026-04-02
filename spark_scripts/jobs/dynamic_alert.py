import sys 
import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, struct

# 1. Nạp module từ thư mục cha
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import KAFKA_BROKER, KAFKA_TOPIC_PRICES, KAFKA_TOPIC_ALERTS, PG_URL, PG_USER, PG_PASSWORD, PG_DRIVER
from utils.schemas import BINANCE_SCHEMA
# [CHANGED] SCHEMA được định nghĩa trong utils/schemas.py để tái sử dụng cho nhiều job khác nhau

# 1. Khởi tạo Spark Session (Kèm theo Driver để kết nối PostgreSQL)
spark = SparkSession.builder \
    .appName("Crypto_Dynamic_Alerts") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.5.4") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("🔥 [SPARK] Đã bật Radar Cảnh Báo Động! Đang liên tục quét luật từ PostgreSQL...")


# 3. Đọc dữ liệu Real-time từ Kafka
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC_PRICES) \
    .load()

parsed_stream = raw_stream.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), BINANCE_SCHEMA).alias("data")).select("data.*")

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
            .option("url", PG_URL) \
            .option("dbtable", "user_alerts") \
            .option("user", PG_USER) \
            .option("password", PG_PASSWORD) \
            .option("driver", PG_DRIVER) \
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
            print(f"
             PHÁT HIỆN {alert_count} CẢNH BÁO KHỚP LỆNH! (Lô {batch_id}) - Đang đẩy vào Kafka...")
            
            # Ép kiểu thành JSON để Kafka hiểu được
            kafka_output = matched_alerts.selectExpr(
                "CAST(alert_id AS STRING) AS key", 
                "to_json(struct(*)) AS value"
            )

            # Bơm vào Topic user_alerts_topic
            kafka_output.write \
                .format("kafka") \
                .option("kafka.bootstrap.servers", KAFKA_BROKER) \
                .option("topic", KAFKA_TOPIC_ALERTS) \
                .save()
            
    except Exception as e:
        # Bắt lỗi nếu PostgreSQL chưa có bảng, sai pass,...
        print(f"⚠️ Lỗi khi xử lý Lô {batch_id}: {str(e)}")

# 5. Kích hoạt vòi xả
query = parsed_stream.writeStream \
    .foreachBatch(process_dynamic_alerts) \
    .start()

query.awaitTermination()