#!/bin/bash

echo "🚀 Đang khởi động hệ thống Demo cho Minh..."

# 1. Thêm dòng này để Python tìm thấy các thư mục trong project
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 2. Xóa các port-forward cũ (đề phòng Minh đã chạy trước đó mà chưa tắt)
echo "🧹 Đang dọn dẹp các kết nối cũ..."
pkill -f "port-forward"
sleep 2

# 3. Mở các đường ống Port-forward chạy ngầm
echo "🔗 Đang mở các cổng kết nối vào K8s..."
kubectl port-forward service/minio-service 9000:9000 -n crypto-system &
kubectl port-forward service/kafka-service 9092:9092 -n crypto-system &
kubectl port-forward service/influxdb 8086:8086 -n crypto-system &
kubectl port-forward service/postgres 5432:5432 -n crypto-system &

# Đợi 5 giây để các đường ống kịp thông suốt
sleep 5

# 4. Kích hoạt Pipeline dữ liệu
# Lưu ý: Minh nhớ phải ở trong (venv) khi chạy script này nhé!
echo "📈 Đang bật Producer (Crawler)..."
python3 Crawler/binance_producer.py > producer.log 2>&1 &

echo "⚡ Đang bật Speed Layer (Spark)..."
python3 spark_scripts/spark_streaming.py > spark.log 2>&1 &

echo "📊 Đang bật Batch Layer..."
python3 backend/batch_layer.py > batch.log 2>&1 &

# 5. Mở giao diện Frontend
echo "🌐 Đang mở Website Frontend..."
minikube service frontend -n crypto-system

echo "✅ TẤT CẢ ĐÃ SẴN SÀNG! Chúc Minh báo cáo rực rỡ!"