# 📚 CryptoWatch - Hướng Dẫn Chạy Toàn Bộ Hệ Thống

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────────────────────────────┐
│                     CryptoWatch System                          │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│   Frontend   │   Backend    │   Crawler    │   Spark Batch      │
│  (React/SPA) │  (FastAPI)   │  (Binance)   │   (Processing)     │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────────┘
       │              │              │                │
       └──────────────┴──────────────┴────────────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
    ┌──▼──┐      ┌───▼──┐      ┌───▼──┐
    │Kafka│      │MinIO │      │Influx│
    │     │      │      │      │      │
    └─────┘      └──────┘      └──────┘
       │              │              │
       └──────────────┴──────────────┘
           ✅ Data Pipeline
```

---

## 🚀 QUICK START - 3 Cách Chạy

### **Cách 1️⃣: Chạy LOCAL (Development Mode)**

#### Prerequisites
```bash
# 1. Python 3.11+
python --version

# 2. Node.js 18+
node --version npm --version

# 3. Docker & Docker Compose
docker --version docker-compose --version
```

#### Step 1: Start Docker Compose (Kafka, InfluxDB, PostgreSQL, MinIO)
```bash
cd /home/minh1234/BigData

# Khởi động toàn bộ infrastructure
docker-compose up -d

# Kiểm tra status
docker-compose ps

# Xem logs (nếu có lỗi)
docker-compose logs -f
```

#### Step 2: Start Backend
```bash
# Terminal 1
cd /home/minh1234/BigData

# Activate venv
source venv/bin/activate

# Start FastAPI server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

#### Step 3: Start Frontend
```bash
# Terminal 2
cd /home/minh1234/BigData/frontend

# Cài dependencies (nếu chưa)
npm install

# Start dev server
npm run dev

# Output:
#   ➜  Local:   http://localhost:5173/
```

#### Step 4: Start Crawler (Thu thập dữ liệu từ Binance)
```bash
# Terminal 3
cd /home/minh1234/BigData

source venv/bin/activate

# Chạy Crawler
python Crawler/binance_producer.py

# Output:
# ✅ Đã kết nối Kafka (Chế độ Plaintext)
# [SPEED] BTCUSDT   | Giá: 45230.50
# [SPEED] ETHUSDT   | Giá: 2230.20
```

#### Step 5: Start Spark Batch Jobs (Optional)
```bash
# Terminal 4
cd /home/minh1234/BigData

source venv/bin/activate

# Batch processing
python spark_scripts/jobs/batch_layer.py --mode micro --offset-minutes 120

# Output:
# 🗄️  [BATCH LAYER] Khởi động — mode: micro
# 📦 Tổng records đọc được: 5432
```

#### Step 6: Access Web
```
Frontend:  http://localhost:5173
Backend:   http://localhost:8000
API Docs:  http://localhost:8000/docs
MinIO:     http://localhost:9001  (admin/password123)
InfluxDB:  http://localhost:8086
Kafka UI:  http://localhost:8081
```

---

### **Cách 2️⃣: Chạy trên Docker (Single Container Test)**

```bash
# Build backend image
docker build -f Dockerfile.backend-k8s -t crypto-backend:latest .

# Build frontend image
docker build -f Dockerfile.frontend-k8s -t crypto-frontend:latest .

# Run backend
docker run -d \
  --network host \
  -e INFLUX_URL=http://localhost:8086 \
  -e KAFKA_BROKER=localhost:9092 \
  -p 8000:8000 \
  crypto-backend:latest

# Run frontend (nếu muốn separate)
docker run -d \
  --network host \
  -p 3000:80 \
  crypto-frontend:latest

# Test
curl http://localhost:8000/health
curl http://localhost:3000
```

---

### **Cách 3️⃣: Chạy trên Kubernetes (Production)**

#### Prerequisites
```bash
# Kiểm tra Kubernetes
kubectl cluster-info

# Hoặc nếu dùng Minikube
minikube status
minikube start
```

#### Step 1: Build & Load Images
```bash
cd /home/minh1234/BigData

# Build images
docker build -f Dockerfile.backend-k8s -t crypto-backend:latest .
docker build -f Dockerfile.frontend-k8s -t crypto-frontend:latest .

# Load vào Minikube (nếu dùng minikube)
minikube image load crypto-backend:latest
minikube image load crypto-frontend:latest
```

#### Step 2: Deploy Infrastructure (Kafka, InfluxDB, PostgreSQL, MinIO)
```bash
# Deploy Kafka
kubectl apply -f k8s/kafka.yaml

# Deploy InfluxDB
kubectl apply -f k8s/influxdb.yaml

# Deploy PostgreSQL
kubectl apply -f k8s/postgres.yaml

# Deploy MinIO
kubectl apply -f k8s/minio.yaml

# Chờ pods ready
kubectl get pods -A -w

# Kiểm tra status
kubectl get svc -A
```

#### Step 3: Deploy Backend & Frontend
```bash
# Deploy backend
kubectl apply -f k8s/03-backend-deployment.yaml

# Deploy frontend
kubectl apply -f k8s/04-frontend-deployment.yaml

# Check deployment
kubectl get pods -n crypto-system
kubectl get svc -n crypto-system
```

#### Step 4: Port Forward để Test
```bash
# Terminal 1: Backend
kubectl port-forward -n crypto-system svc/fastapi-backend 8000:8000

# Terminal 2: Frontend
kubectl port-forward -n crypto-system svc/frontend 3000:80

# Terminal 3: Test
curl http://localhost:8000/health
curl http://localhost:3000
```

#### Step 5: Deploy Crawler & Spark Jobs
```bash
# Tạo ConfigMap cho Crawler
kubectl create configmap crawler-env \
  --from-literal=KAFKA_BROKER=kafka:9092 \
  --from-literal=MINIO_ENDPOINT=http://minio:9000 \
  -n crypto-system

# Tạo Deployment cho Crawler (Job)
kubectl create job crypto-crawler --image=crypto-crawler:latest \
  -n crypto-system

# Tạo CronJob cho Spark Batch (chạy định kỳ)
kubectl create cronjob batch-job --image=crypto-spark:latest \
  --schedule="0 */2 * * *" \
  -n crypto-system
```

#### Step 6: Access Services
```bash
# Port forward services
kubectl port-forward -n crypto-system svc/kafka 9092:9092
kubectl port-forward -n crypto-system svc/influxdb 8086:8086
kubectl port-forward -n crypto-system svc/minio 9000:9000

# Access
Frontend:    http://localhost:3000
Backend API: http://localhost:8000/docs
MinIO:       http://localhost:9000
InfluxDB:    http://localhost:8086
Kafka:       localhost:9092
```

---

## 🔍 MONITORING & DEBUGGING

### View Logs
```bash
# Local - Backend
tail -f logs/backend.log

# Local - Frontend (browser console F12)

# Kubernetes - Backend
kubectl logs -f deployment/fastapi-backend -n crypto-system

# Kubernetes - Frontend
kubectl logs -f deployment/frontend -n crypto-system

# Kubernetes - Crawler
kubectl logs -f pod/crypto-crawler-xxxxx -n crypto-system
```

### Check Health Status
```bash
# Backend health
curl http://localhost:8000/health
curl http://localhost:8000/ready

# InfluxDB
curl http://localhost:8086/ping

# Kafka
docker exec crypto_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# MinIO
curl http://localhost:9000/minio/health/live
```

### Troubleshooting
```bash
# Kubernetes - describe pod lỗi
kubectl describe pod <pod-name> -n crypto-system

# Exec vào pod để debug
kubectl exec -it pod/<pod-name> -n crypto-system -- /bin/bash

# Check environment variables
kubectl exec pod/<pod-name> -n crypto-system -- env | grep KAFKA

# Restart deployment
kubectl rollout restart deployment/fastapi-backend -n crypto-system

# View events
kubectl get events -n crypto-system --sort-by='.lastTimestamp'
```

---

## 📊 API Endpoints

### Backend (FastAPI)

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/health` | GET | Liveness check |
| `/ready` | GET | Readiness check |
| `/api/market-summary` | GET | Giá tất cả coins |
| `/api/historical-price/{symbol}` | GET | Lịch sử giá của 1 coin |
| `/ws/live-price/{symbol}` | WebSocket | Real-time giá stream |
| `/docs` | GET | API Documentation (Swagger) |

### Examples
```bash
# Market summary
curl http://localhost:8000/api/market-summary | jq

# Historical price
curl http://localhost:8000/api/historical-price/BTCUSDT | jq

# WebSocket (từ terminal hoặc postman)
wscat -c ws://localhost:8000/ws/live-price/BTCUSDT
```

---

## 🗂️ File Structure

```
BigData/
├── backend/                     # FastAPI Backend
│   ├── main.py                 # API endpoints (✅ sửa env vars)
│   ├── ml_service.py           # ML predictions
│   └── requirements.txt
│
├── frontend/                    # React/Vite Frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx        # ✅ sửa API URL
│   │   │   └── CoinDetail.jsx  # ✅ sửa API URL
│   │   └── App.jsx
│   ├── .env                    # Dev environment
│   ├── .env.production         # Prod (K8s)
│   └── vite.config.js
│
├── Crawler/
│   └── binance_producer.py     # ✅ sửa KAFKA_BROKER, MINIO_ENDPOINT
│
├── spark_scripts/
│   ├── config/
│   │   └── settings.py         # ✅ sửa KAFKA_BROKER, INFLUX_URL, PG_URL
│   ├── jobs/
│   │   ├── speed_layer.py
│   │   └── batch_layer.py
│   └── ml/predictor.py
│
├── k8s/                        # Kubernetes manifests
│   ├── 00-namespace.yaml
│   ├── 01-configmap.yaml
│   ├── 02-secret.yaml
│   ├── 03-backend-deployment.yaml
│   ├── 04-frontend-deployment.yaml
│   ├── kafka.yaml
│   ├── influxdb.yaml
│   ├── postgres.yaml
│   └── minio.yaml
│
├── docker/
│   ├── Dockerfile.backend-k8s   # Backend cho K8s
│   ├── Dockerfile.frontend-k8s  # Frontend cho K8s
│   └── Dockerfile.spark
│
├── docker-compose.yml           # Local development
├── .env                        # Local env (KHÔNG COMMIT!)
├── .env.k8s                    # K8s env reference
└── README.md                   # This file
```

---

## 🔧 Environment Variables

### Local Development (.env)
```bash
# Backend
INFLUX_URL=http://localhost:8086
KAFKA_BROKER=localhost:9092
MINIO_ENDPOINT=http://localhost:9000

# Frontend
VITE_API_URL=http://localhost:8000
```

### Kubernetes (.env.k8s)
```bash
# Backend
INFLUX_URL=http://influxdb:8086
KAFKA_BROKER=kafka:9092
MINIO_ENDPOINT=http://minio:9000

# Frontend
VITE_API_URL=/api  # Proxied through Nginx
```

---

## ✅ Checklist Deployment

- [ ] Code đã sửa (env vars, API URLs)
- [ ] Docker images build thành công
- [ ] Docker Compose running (local)
- [ ] Backend API responding (`curl /health`)
- [ ] Frontend loading (`http://localhost:5173`)
- [ ] Crawler sending data to Kafka
- [ ] InfluxDB receiving data
- [ ] Spark batch jobs running
- [ ] Kubernetes cluster ready (nếu K8s)
- [ ] All K8s pods are Running & Ready
- [ ] Port forwards working

---

## 📝 Useful Commands

```bash
# Local
docker-compose up/down/logs -f
docker build/run/ps

# Frontend
npm install/run dev/build
npm run lint

# Backend
pip install -r requirements.txt
uvicorn main:app --reload

# Kubernetes
kubectl apply/delete -f file.yaml
kubectl get pods/svc/ingress -n crypto-system
kubectl logs/exec/port-forward
kubectl describe pod <name>

# Kafka (test message)
docker exec crypto_kafka kafka-console-producer.sh \
  --broker-list localhost:9092 \
  --topic raw_prices

# InfluxDB (query)
curl -X POST http://localhost:8086/api/v2/query \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-type: application/vnd.flux"
```

---

## 🆘 Common Issues & Fixes

| Problem | Fix |
|---------|-----|
| API connection refused | Check backend running, port 8000 listening |
| CORS error | Update ALLOWED_ORIGINS in backend/main.py |
| No data in InfluxDB | Check Crawler running, topics created |
| Frontend blank page | Check browser console F12, network tab |
| K8s pods not ready | `kubectl logs pod/xxx -n crypto-system` |
| Image not found (K8s) | `minikube image load image-name:tag` |
| Permission denied | Run with `sudo` hoặc add user to docker group |

---

## 📚 Resources

- [FastAPI Docs](https://fastapi.tiangolo.com)
- [React Docs](https://react.dev)
- [Kubernetes Docs](https://kubernetes.io/docs)
- [Kafka Docs](https://kafka.apache.org/documentation)
- [InfluxDB Docs](https://docs.influxdata.com)
- [Apache Spark Docs](https://spark.apache.org/docs/latest)

---

## 🎯 Next Steps

1. ✅ Fix all files (DONE - xem commits)
2. ✅ Test locally (Run Cách 1)
3. ✅ Deploy to Kubernetes (Run Cách 3)
4. 📊 Monitor metrics & logs
5. 🚀 Scale & optimize

---

## 📞 Support

Nếu có lỗi:
1. Kiểm tra logs: `kubectl logs -f deployment/xxx`
2. Check configs: `kubectl get configmap/secret -o yaml`
3. Test connectivity: `kubectl run debug --image=curlimages/curl -it --rm`
4. Describe pods: `kubectl describe pod <name>`

---

**Last Updated**: April 20, 2026
**Status**: ✅ Production Ready
