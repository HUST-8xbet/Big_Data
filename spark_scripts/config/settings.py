import os

# ✅ Kafka Config (Support Kubernetes DNS)
# Local: localhost:9092, K8s: kafka:9092
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC_PRICES = os.getenv('KAFKA_TOPIC_PRICES', 'raw_prices')
KAFKA_TOPIC_ALERTS = os.getenv('KAFKA_TOPIC_ALERTS', 'user_alerts_topic')

# ✅ InfluxDB Config (Support Kubernetes DNS)
# Local: localhost:8086, K8s: influxdb:8086
INFLUX_URL = os.getenv('INFLUX_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', 'super-secret-token-12345')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'crypto_org')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'crypto_prices')

# ✅ PostgreSQL Config (Support Kubernetes DNS)
# Local: localhost:5432, K8s: postgres:5432
PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_DB = os.getenv('PG_DB', 'cryptodb')
PG_USER = os.getenv('PG_USER', 'admin')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'admin123')
PG_DRIVER = os.getenv('PG_DRIVER', 'org.postgresql.Driver')

# JDBC URL format
PG_URL = f"jdbc:postgresql://{PG_HOST}:{PG_PORT}/{PG_DB}"
# ✅ MinIO Config
# Local: localhost:9000, K8s: minio-service:9000
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://localhost:9000')
MINIO_ROOT_USER = os.getenv('MINIO_ROOT_USER', 'minioadmin')
MINIO_ROOT_PASSWORD = os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin123')