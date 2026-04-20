# Kubernetes Deployment Guide

## 📋 Những gì cần sửa cho Kubernetes

### ✅ Đã làm:

1. **Backend (FastAPI)**
   - ✅ Dùng environment variables thay vì hardcoded
   - ✅ Thêm `/health` và `/ready` endpoints
   - ✅ Sẽ bind `0.0.0.0:8000` thay vì `localhost`

2. **Frontend (React/Vite)**
   - ✅ Tạo Dockerfile với Nginx
   - ✅ Nginx config hỗ trợ SPA routing
   - ✅ API proxy được cấu hình

3. **Kubernetes Manifests**
   - ✅ ConfigMap cho config
   - ✅ Secret cho tokens
   - ✅ Deployment + Service cho backend & frontend
   - ✅ Ingress cho frontend
   - ✅ Health checks (liveness + readiness probes)

---

## 🚀 Cách deploy lên Kubernetes

### Step 1: Build Docker images

```bash
# Build backend
docker build -f Dockerfile.backend-k8s -t crypto-backend:latest .

# Build frontend
docker build -f Dockerfile.frontend-k8s -t crypto-frontend:latest .
```

### Step 2: Load images vào Minikube (nếu dùng minikube)

```bash
# Nếu dùng minikube
minikube image load crypto-backend:latest
minikube image load crypto-frontend:latest

# Hoặc nếu dùng Docker Desktop Kubernetes
docker image tag crypto-backend:latest crypto-backend:latest
```

### Step 3: Deploy lên Kubernetes

```bash
# Tạo namespace
kubectl apply -f k8s/00-namespace.yaml

# Tạo ConfigMap & Secret
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secret.yaml

# Deploy backend
kubectl apply -f k8s/03-backend-deployment.yaml

# Deploy frontend
kubectl apply -f k8s/04-frontend-deployment.yaml
```

### Step 4: Verify deployment

```bash
# Kiểm tra pods
kubectl get pods -n crypto-system

# Xem logs
kubectl logs -n crypto-system -l app=backend -f
kubectl logs -n crypto-system -l app=frontend -f

# Port forward (testing)
kubectl port-forward -n crypto-system svc/backend 8000:8000
kubectl port-forward -n crypto-system svc/frontend 3000:80
```

---

## 🔧 Những gì cần chỉnh sửa thêm

### 1. **Frontend - Cần cập nhật API URL**
Hiện tại Frontend có thể hardcode API URL. Cần kiểm tra và cập nhật:

```jsx
// frontend/src/api.js (file này có thể chưa tồn tại)
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const fetchMarketSummary = () =>
  fetch(`${API_BASE}/api/market-summary`).then(r => r.json());
```

Thêm vào `frontend/.env`:
```
VITE_API_URL=http://backend:8000
```

### 2. **Backend - Cần cập nhật PostgreSQL connection**
Nếu dùng PostgreSQL trong Kubernetes:

```python
# backend/main.py
PG_HOST = os.getenv("PG_HOST", "postgres")  # Service name
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "admin")
PG_PASSWORD = os.getenv("PG_PASSWORD")  # Từ Secret
```

### 3. **Docker Compose → Docker file cần update**
File `Dockerfile.backend` và `Dockerfile.spark` có thể cần cập nhật:

```dockerfile
# Đảm bảo base image compatible
FROM python:3.11-slim
```

---

## 🔐 Bảo mật - Cần làm

### ⚠️ CHÍNH: Cập nhật Secret tokens

```bash
# Generate base64 token
echo -n "your-actual-influx-token" | base64
# Kết quả paste vào k8s/02-secret.yaml
```

### Tạo Secret từ .env file

```bash
kubectl create secret generic backend-secrets \
  --from-literal=INFLUX_TOKEN=your-token \
  --from-literal=POSTGRES_PASSWORD=your-password \
  -n crypto-system
```

---

## 📊 Monitoring & Logs

```bash
# Kiểm tra status
kubectl get deployments -n crypto-system
kubectl get services -n crypto-system
kubectl get ingress -n crypto-system

# Describe pod để debug
kubectl describe pod <pod-name> -n crypto-system

# Real-time logs
kubectl logs -f deployment/backend -n crypto-system
```

---

## 🚨 Troubleshooting

| Lỗi | Nguyên nhân | Cách fix |
|-----|-----------|---------|
| ImagePullBackOff | Không tìm thấy image | Load image vào minikube hoặc push lên registry |
| CrashLoopBackOff | App crashed | `kubectl logs <pod-name>` để xem error |
| Connection refused | Backend không sẵn sàng | Kiểm tra readiness probe |
| API call failed | Frontend → backend lỗi | Kiểm tra service DNS resolution |

---

## 📝 Checklist trước khi deploy

- [ ] Backend: Build & test locally
- [ ] Frontend: Build & test locally  
- [ ] Docker images: Build thành công
- [ ] ConfigMap: Update đúng service names
- [ ] Secret: Update đúng tokens
- [ ] Ingress: Update đúng domain
- [ ] InfluxDB pod: Running (nếu dùng)
- [ ] PostgreSQL pod: Running (nếu dùng)

---

## 💡 Best Practices

1. **Never hardcode secrets** - Luôn dùng Kubernetes Secrets
2. **Use namespace** - Organize resources theo namespace
3. **Set resource limits** - Prevent resource hogging
4. **Health checks** - Implement liveness & readiness probes
5. **Graceful shutdown** - Handle SIGTERM properly
