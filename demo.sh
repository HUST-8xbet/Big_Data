#!/bin/bash

echo "🚀 Đang khởi động hệ thống Demo cho Minh..."

# 1. Thêm đường dẫn để Python không bị lỗi ModuleNotFoundError
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 2. Dọn dẹp các tiến trình cũ để tránh chiếm dụng Port
echo "🧹 Đang dọn dẹp các kết nối cũ..."
pkill -f "port-forward"
sleep 2

# 3. Mở các đường ống Port-forward (Đã chỉnh theo svc -A và influxdb mới)
echo "🔗 Đang kết nối vào các dịch vụ K8s..."

# Nhóm dịch vụ ở namespace 'default'
kubectl port-forward service/minio-service 9000:9000 -n default &
kubectl port-forward service/kafka 9092:9092 -n default &
kubectl port-forward service/postgres 5432:5432 -n default &

# Nhóm dịch vụ ở namespace 'crypto-system'
kubectl port-forward service/influxdb 8086:8086 -n crypto-system &
# THÊM DÒNG NÀY VÀO:
kubectl port-forward service/backend 8000:8000 -n crypto-system &
# Đợi 5 giây để các đường ống thông suốt
sleep 5

# 4. Kích hoạt Pipeline dữ liệu (Chạy ngầm và lưu log)
# 4. Kích hoạt Pipeline dữ liệu (Đã chia nhỏ theo module mới)
echo "📈 Đang bật Producer (Crawler)..."
python3 Crawler/binance_producer.py > producer.log 2>&1 &

# ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT CHO WEB DASHBOARD
echo "⚡ Đang bật Speed Layer (Real-time to InfluxDB)..."
python3 spark_scripts/speed_layer_influx.py > spark_speed.log 2>&1 &

echo "🚨 Đang bật Hệ thống Cảnh báo Động (Alerts)..."
python3 spark_scripts/dynamic_alert.py > spark_alerts.log 2>&1 &

echo "📊 Đang khởi động Batch Layer Scheduler..."
# Sử dụng file .sh bạn Minh vừa tạo để chạy định kỳ
bash spark_scripts/batch_scheduler.sh > batch.log 2>&1 &

# 5. Mở giao diện Frontend bằng Minikube Tunnel
echo "🌐 Đang mở Website Frontend..."
minikube service frontend -n crypto-system