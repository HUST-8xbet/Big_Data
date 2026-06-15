# CryptoWatch Big Data Pipeline

CryptoWatch la pipeline theo huong Lambda Architecture cho du lieu gia crypto:

- `Crawler/`: lay trade realtime tu Binance, day vao Kafka va luu raw JSON vao MinIO.
- `spark_scripts/jobs/`: speed layer ghi Kafka -> InfluxDB, batch layer tinh OHLCV/market stats -> PostgreSQL va MinIO.
- `backend/`: FastAPI doc InfluxDB va phuc vu API/forecast bang LSTM.
- `frontend/`: React + Vite dashboard.
- `docker/`: Dockerfile va Docker Compose cho moi truong local.
- `k8s/`: manifest Kubernetes cho namespace `crypto-system`.

## Yeu Cau

- Python 3.11+.
- Node.js 20+ va npm.
- Docker Desktop/Engine + Docker Compose neu chay bang container.
- Java/Spark local neu muon chay Spark job ngoai Docker.
- Kubernetes/minikube va `kubectl` neu deploy K8S.

## Chay Chinh Bang Kubernetes

Day la cach chay dung de thoa man yeu cau Kubernetes.

### 1. Start Minikube nhe hon cho WSL

```bash
minikube start --driver=docker --cpus=4 --memory=6144 --disk-size=30g
```

Neu may it RAM, dung `--memory=4096` va chay tung phan pipeline, nhung Spark/ML se cham hon.

### 2. Build images truc tiep trong Minikube

Khuyen nghi dung cach nay tren WSL de tranh `minikube image load` lam treo may:

```bash
cd /home/minh1234/BigData
eval "$(minikube docker-env)"
```

Sau lenh nay, cac lenh `docker build` se build image vao Docker daemon cua Minikube. Khong can chay `minikube image load`.

```bash
docker build -f docker/Dockerfile.backend-k8s -t crypto-backend:latest .
docker build -f docker/Dockerfile.frontend-k8s -t crypto-frontend:latest .
docker build -f docker/Dockerfile.crawler -t crypto-crawler:latest .
docker build -f docker/Dockerfile.spark -t crypto-spark:latest .
docker build -f docker/Dockerfile.ml-trainer -t crypto-ml-trainer:latest .
```

Hoac dung script:

```bash
./build-deploy.sh all minikube-docker
```

Chi dung cach `minikube image load` khi may du RAM:

```bash
./build-deploy.sh all load
```

### 3. Deploy Kubernetes manifests

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secret.yaml

kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/kafka.yaml
kubectl apply -f k8s/minio.yaml
kubectl apply -f k8s/influxdb.yaml

kubectl apply -f k8s/05-init-jobs.yaml

kubectl apply -f k8s/03-backend-deployment.yaml
kubectl apply -f k8s/04-frontend-deployment.yaml
kubectl apply -f k8s/06-crawler-deployment.yaml
kubectl apply -f k8s/07-spark-speed-deployment.yaml
kubectl apply -f k8s/08-spark-batch-cronjob.yaml
kubectl apply -f k8s/09-ml-train-cronjob.yaml
```

### 4. Kiem tra pods/services

```bash
kubectl get pods -n crypto-system
kubectl get svc -n crypto-system
kubectl get cronjob -n crypto-system
```

Cho cac deployment san sang:

```bash
kubectl rollout status deployment/backend -n crypto-system
kubectl rollout status deployment/frontend -n crypto-system
kubectl rollout status deployment/crawler -n crypto-system
kubectl rollout status deployment/spark-speed-layer -n crypto-system
```

### 5. Mo app

```bash
kubectl port-forward -n crypto-system svc/backend 8000:8000
kubectl port-forward -n crypto-system svc/frontend 3000:80
```

Mo:

- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`
- Backend ready: `http://localhost:8000/ready`

### 6. Trigger batch/train thu cong khi can

Batch CronJob tu chay moi 15 phut. Muon chay ngay:

```bash
kubectl create job -n crypto-system --from=cronjob/spark-batch-micro spark-batch-manual
```

ML train CronJob tu chay moi ngay 00:30 UTC. Muon train ngay:

```bash
kubectl create job -n crypto-system --from=cronjob/ml-train-lstm ml-train-manual
```

Sau khi train xong, restart backend de load model moi tu MinIO:

```bash
kubectl rollout restart deployment/backend -n crypto-system
```

### 7. Xem logs

```bash
kubectl logs -f deployment/crawler -n crypto-system
kubectl logs -f deployment/spark-speed-layer -n crypto-system
kubectl logs -f deployment/backend -n crypto-system
kubectl logs -f job/spark-batch-manual -n crypto-system
kubectl logs -f job/ml-train-manual -n crypto-system
```

## Chay Nhanh Bang Docker Compose (chi de dev local)

Lenh duoc chay tu root repo:

```bash
cd /home/minh1234/BigData
docker compose -f docker/docker-compose.yml up -d kafka minio postgres influxdb redpanda-console
docker compose -f docker/docker-compose.yml up -d crawler spark-submit backend frontend
```

Kiem tra:

```bash
docker compose -f docker/docker-compose.yml ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Dia chi dich vu:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Kafka UI: `http://localhost:8081`
- MinIO console: `http://localhost:9001` voi `admin/password123`
- InfluxDB: `http://localhost:8086` voi org `crypto_org`, bucket `crypto_prices`, token `super-secret-token-12345`

Neu chi muon chay lai job batch:

```bash
docker compose -f docker/docker-compose.yml run --rm batch-micro
docker compose -f docker/docker-compose.yml run --rm batch-init
```

## Chay Local De Dev

Khoi dong ha tang bang Docker:

```bash
cd /home/minh1234/BigData
docker compose -f docker/docker-compose.yml up -d kafka minio postgres influxdb redpanda-console
```

Tao Python env va cai dependency:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirement.txt
```

Chay backend:

```bash
export INFLUX_URL=http://localhost:8086
export INFLUX_TOKEN=super-secret-token-12345
export INFLUX_ORG=crypto_org
export INFLUX_BUCKET=crypto_prices
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Chay frontend:

```bash
cd frontend
npm install
npm run dev
```

Chay crawler:

```bash
source venv/bin/activate
python3 Crawler/binance_producer.py
```

Chay speed layer local:

```bash
source venv/bin/activate
export PYTHONPATH=/home/minh1234/BigData/spark_scripts
python3 spark_scripts/jobs/speed_layer_influx.py
```

Chay batch layer local:

```bash
source venv/bin/activate
export PYTHONPATH=/home/minh1234/BigData
python3 spark_scripts/jobs/batch_layer.py --mode micro --offset-minutes 120
```

## Train Model

Nen train tu du lieu batch trong MinIO de dung vai tro data lake:

```bash
source venv/bin/activate
pip install -r backend/requirements.txt
python3 spark_scripts/ml/train_from_minio.py
```

Hoac chay bang Docker Compose:

```bash
docker compose -f docker/docker-compose.yml --profile training run --rm model-trainer-minio
```

Neu can nap du lieu lich su Binance vao InfluxDB truoc de dev nhanh:

```bash
source venv/bin/activate
BACKFILL_DAYS=7 python3 spark_scripts/ml/backfill_history.py
python3 spark_scripts/ml/train_model.py
```

Neu train tren server GPU khac:

```bash
python3 spark_scripts/ml/export_training_data.py
scp spark_scripts/ml/artifacts/training_data.npz user@server:~/BigData/spark_scripts/ml/artifacts/
# tren server
python3 spark_scripts/ml/train_from_file.py
```

Model local mac dinh duoc luu tai `spark_scripts/ml/artifacts/model.pt`. Backend van chay khi thieu Torch/Numpy, nhung forecast se dung fallback thay vi LSTM.
Khi train bang Docker Compose, model se duoc upload len `ml-models/lstm/model.pt`; restart backend de backend tai va load model moi.

Thong so chi tiet cua tung module nam trong `PIPELINE_CONFIG.md`.
Ke hoach bo sung Airflow nam trong `AIRFLOW_PLAN.md`.

## Bien Moi Truong Quan Trong

- `KAFKA_BROKER`: local `localhost:9092`, Docker `kafka:29092`, K8S `kafka:9092`.
- `KAFKA_TOPIC_PRICES`: mac dinh `binance_live_prices`.
- `INFLUX_URL`: local `http://localhost:8086`, Docker/K8S `http://influxdb:8086`.
- `INFLUX_TOKEN`: mac dinh `super-secret-token-12345`.
- `INFLUX_ORG`: `crypto_org`.
- `INFLUX_BUCKET`: `crypto_prices`.
- `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`: dung cho batch layer.
- `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: dung cho crawler va batch layer.
- `BINANCE_COINS`: danh sach coin cach nhau bang dau phay neu muon doi tap coin.

## Ghi Chu Van Hanh

- Lan dau chay nen cho crawler va speed layer ghi du lieu vao InfluxDB vai phut truoc khi mo dashboard.
- Neu frontend hien bang trong, kiem tra `curl http://localhost:8000/api/market-summary`.
- Neu `/ready` tra 503, backend dang khong ket noi duoc InfluxDB.
- Neu train model khong du du lieu, chay `spark_scripts/ml/backfill_history.py` hoac tang thoi gian thu thap realtime.
