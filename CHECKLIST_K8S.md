# ⚠️ CHECKLIST - CẦN SỬA NGAY

## 🔴 ĐỐI VỚI FRONTEND - VẬN ĐỀ HẬN

### 1. **API URL chưa được cấu hình**
Frontend cần biết cách kết nối tới backend API. Hiện tại chưa thấy file cấu hình API.

**Cần tạo:** `frontend/src/api.js`
```javascript
const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000';

export const api = {
  getMarketSummary: () => 
    fetch(`${API_BASE}/api/market-summary`).then(r => r.json()),
  
  getHistoricalPrice: (symbol) =>
    fetch(`${API_BASE}/api/historical-price/${symbol}`).then(r => r.json()),
  
  connectWebSocket: (symbol, onMessage) => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/live-price/${symbol}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    return ws;
  }
};
```

**Cần tạo:** `frontend/.env`
```
VITE_API_URL=http://localhost:8000
```

**Cần tạo:** `frontend/.env.production`
```
VITE_API_URL=/api
```

### 2. **Vite config cần cập nhật**
```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})
```

### 3. **Kiểm tra React components**
- App.jsx có dùng API chưa?
- CoinDetail.jsx & Home.jsx có fetch data không?
- Nếu chưa, cần kết nối API

---

## 🔴 ĐỐI VỚI BACKEND - VẬN ĐỀ HẬN

### 1. **PostgreSQL connection string**
Backend không có config cho PostgreSQL. Nếu dùng PG, cần thêm:

```python
# backend/main.py - thêm sau các import
from sqlalchemy import create_engine

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "admin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "admin123")
PG_DB = os.getenv("PG_DB", "cryptodb")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
engine = create_engine(DATABASE_URL)
```

### 2. **Thêm vào requirements.txt**
```
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
```

---

## 🟡 DOCKER FILES - CẦN TEST

### 1. **Dockerfile.backend-k8s**
Chứa `requests` trong healthcheck - cần thêm vào requirements.txt:
```
requests==2.31.0
```

### 2. **Dockerfile.frontend-k8s**
Nginx config dùng `${BACKEND_HOST}` - cần hỗ trợ environment variable substitution.

**Fix:**
```dockerfile
# Thêm tạo runtime nginx config từ env
RUN cat > /docker-entrypoint.d/10-subst-env-vars.sh << 'EOF'
#!/bin/sh
export BACKEND_HOST="${BACKEND_HOST:-backend}"
envsubst '$BACKEND_HOST' < /etc/nginx/nginx.conf.tpl > /etc/nginx/nginx.conf
EOF
chmod +x /docker-entrypoint.d/10-subst-env-vars.sh
```

---

## ✅ STEPS ĐỂ DEPLOY THÀNH CÔNG

### Bước 1: Fix Frontend
```bash
# 1. Tạo api.js
# 2. Tạo .env files
# 3. Update vite.config.js
# 4. Cập nhật App.jsx/CoinDetail.jsx/Home.jsx để dùng API
```

### Bước 2: Fix Backend
```bash
# 1. Cập nhật requirements.txt (thêm requests, sqlalchemy, psycopg2)
# 2. Cập nhật Dockerfile.backend-k8s (nếu cần PG)
```

### Bước 3: Build & Test Locally
```bash
# Test backend
docker build -f Dockerfile.backend-k8s -t crypto-backend:latest .
docker run -p 8000:8000 \
  -e INFLUX_URL=http://host.docker.internal:8086 \
  crypto-backend:latest

# Test frontend
docker build -f Dockerfile.frontend-k8s -t crypto-frontend:latest .
docker run -p 3000:80 \
  -e BACKEND_HOST=host.docker.internal \
  crypto-frontend:latest
```

### Bước 4: Deploy to K8s
```bash
chmod +x build-deploy.sh
./build-deploy.sh all minikube
```

---

## 🐛 DEBUGGING TIPS

```bash
# Xem logs real-time
kubectl logs -f deployment/backend -n crypto-system

# Exec vào pod
kubectl exec -it pod/backend-xxx -n crypto-system -- /bin/bash

# Kiểm tra env vars
kubectl exec pod/backend-xxx -n crypto-system -- env | grep INFLUX

# Test API từ pod khác
kubectl run debug --image=curlimages/curl -it --rm \
  -- curl http://backend:8000/health -n crypto-system
```

---

## 📱 TESTING ENDPOINTS

```bash
# Health check
curl http://localhost:8000/health

# Market summary
curl http://localhost:8000/api/market-summary

# Historical price
curl http://localhost:8000/api/historical-price/BTCUSDT

# WebSocket (từ browser console)
ws = new WebSocket('ws://localhost:8000/ws/live-price/BTCUSDT')
ws.onmessage = e => console.log(e.data)
```

---

## ⚡ QUICK START

1. **Fix Frontend** (tạo api.js)
2. **Fix requirements.txt** (thêm requests)
3. **Run script:**
   ```bash
   chmod +x build-deploy.sh
   ./build-deploy.sh all minikube
   ```
4. **Verify:**
   ```bash
   kubectl get pods -n crypto-system
   kubectl port-forward svc/backend 8000:8000 -n crypto-system
   ```
