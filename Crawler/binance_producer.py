import os
import json
import logging
import websocket
import boto3 # Thư viện để làm việc với MinIO/S3
from kafka import KafkaProducer
from dotenv import load_dotenv
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# --- CẤU HÌNH KAFKA (✅ Support Kubernetes) ---
# Trên K8s: kafka:9092 (service name)
# Local dev: localhost:9092
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'raw_prices')
KAFKA_USER = os.getenv('KAFKA_USER', 'admin')
KAFKA_PASS = os.getenv('KAFKA_PASS', 'admin123')

# --- CẤU HÌNH MINIO (✅ Support Kubernetes) ---
# Trên K8s: minio:9000 (service name)
# Local dev: localhost:9000
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('MINIO_ENDPOINT', 'http://localhost:9000'),
    aws_access_key_id=os.getenv('MINIO_ROOT_USER', os.getenv('MINIO_ACCESS_KEY', 'minioadmin')),
    aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD', os.getenv('MINIO_SECRET_KEY', 'minioadmin123'))
)
RAW_BUCKET = 'raw-data'

COINS = ['btcusdt', 'ethusdt', 'solusdt', 'bnbusdt'] # Thu gọn danh sách để test nhanh
streams = '/'.join([f"{coin}@trade" for coin in COINS])
BINANCE_SOCKET = f"wss://stream.binance.com:9443/stream?streams={streams}"

# # Khởi tạo Kafka Producer với bảo mật SASL
# try:
#     producer = KafkaProducer(
#         bootstrap_servers=[KAFKA_BROKER],
#         value_serializer=lambda v: json.dumps(v).encode('utf-8'),
#         security_protocol="SASL_PLAINTEXT",
#         sasl_mechanism="SCRAM-SHA-256",
#         sasl_plain_username=KAFKA_USER,
#         sasl_plain_password=KAFKA_PASS,
#         retries=5
#     )
#     logger.info("✅ Đã kết nối Kafka (Secure)")
# except Exception as e:
#     logger.error(f"❌ Lỗi kết nối Kafka: {e}")
#     exit(1)

# # Biến tạm để buffer dữ liệu trước khi đẩy lên MinIO (tránh ghi quá nhiều file nhỏ)

# Khởi tạo Kafka Producer ở chế độ không mật khẩu (PLAINTEXT)
try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        retries=5
    )
    logger.info("✅ Đã kết nối Kafka (Chế độ Plaintext)")
except Exception as e:
    logger.error(f"❌ Lỗi kết nối Kafka: {e}")
    exit(1)

data_buffer = []

def save_to_minio(data_list):
    """Lưu gói dữ liệu thô vào MinIO để phục vụ Batch Layer"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"binance/trades_{timestamp}.json"
        
        s3_client.put_object(
            Bucket=RAW_BUCKET,
            Key=file_name,
            Body=json.dumps(data_list)
        )
        logger.info(f"💾 Đã lưu {len(data_list)} bản ghi vào MinIO: {file_name}")
    except Exception as e:
        logger.error(f"❌ Lỗi lưu MinIO: {e}")

def on_message(ws, message):
    global data_buffer
    try:
        raw_message = json.loads(message)
        data = raw_message.get('data')
        
        if data:
            payload = {
                'symbol': data.get('s'),
                'price': float(data.get('p')),
                'volume': float(data.get('q')),
                'timestamp': data.get('E')
            }
            
            # 1. Đẩy vào Kafka (Real-time Speed Layer)
            producer.send(KAFKA_TOPIC, value=payload)
            
            # 2. Thêm vào buffer để lưu MinIO (Batch Layer)
            data_buffer.append(payload)
            
            # Cứ mỗi 100 bản ghi thì đẩy lên MinIO 1 lần
            if len(data_buffer) >= 100:
                save_to_minio(data_buffer)
                data_buffer = []
                
            logger.info(f"[SPEED] {payload['symbol']:<8} | Giá: {payload['price']}")
            
    except Exception as e:
        logger.error(f"Lỗi xử lý dữ liệu: {e}")

def on_error(ws, error): logger.error(f"Lỗi Websocket: {error}")
def on_close(ws, *args):
    if data_buffer: save_to_minio(data_buffer) # Lưu nốt dữ liệu còn sót
    producer.flush()
    producer.close()

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        BINANCE_SOCKET, on_message=on_message,
        on_error=on_error, on_close=on_close
    )
    ws.run_forever()