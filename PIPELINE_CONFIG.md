# Pipeline Module Parameters

Tai lieu nay tom tat cac module chinh, thong so dang dung, file cau hinh va y nghia.

## Crawler

File: `Crawler/binance_producer.py`

| Thong so | Gia tri mac dinh | Y nghia |
|---|---:|---|
| `BINANCE_COINS` | 30 cap USDT | Danh sach coin lay realtime, cach nhau bang dau phay |
| `KAFKA_BROKER` | `localhost:9092` | Kafka bootstrap server |
| `KAFKA_TOPIC` | `binance_live_prices` | Topic ghi raw trade |
| `MINIO_ENDPOINT` | `http://localhost:9000` | Endpoint MinIO/S3 |
| `MINIO_ROOT_USER` | `admin` | Access key MinIO |
| `MINIO_ROOT_PASSWORD` | `password123` | Secret key MinIO |
| `RAW_BUCKET` | `raw-data` | Bucket raw trade |
| `data_buffer` flush | 100 records | Moi 100 trade ghi 1 file JSON len MinIO |
| MinIO key | `binance/trades_%Y%m%d_%H%M%S.json` | Duong dan object raw batch |

## Kafka

File: `docker/docker-compose.yml`, `k8s/kafka.yaml`

| Thong so | Docker Compose | K8S |
|---|---:|---:|
| Image | `apache/kafka:3.7.0` | `apache/kafka:3.7.0` |
| Mode | KRaft broker/controller | KRaft broker/controller |
| External listener | `localhost:9092` | service `kafka:9092` |
| Internal listener | `kafka:29092` | `kafka:9092` |
| Topic gia | `binance_live_prices` | `binance_live_prices` |
| Partitions gia | 3 | tao rieng neu dung job init |
| Replication factor | 1 | 1 node dev |

## MinIO

File: `docker/docker-compose.yml`, `k8s/minio.yaml`

| Thong so | Gia tri | Y nghia |
|---|---:|---|
| Image | `minio/minio:latest` | Object storage/data lake |
| API port | `9000` | S3-compatible API |
| Console port | `9001` | UI quan tri |
| User/password | `admin/password123` | Dev credentials |
| Buckets | `raw-data`, `processed-data`, `ml-models` | Raw trade, parquet batch output, model artifact |

## Spark Speed Layer

File: `spark_scripts/jobs/speed_layer_influx.py`

| Thong so | Gia tri mac dinh | Y nghia |
|---|---:|---|
| Spark app | `Crypto_SpeedLayer_InfluxDB` | Ten job |
| Kafka format | `readStream` | Doc streaming tu Kafka |
| `KAFKA_BROKER` | `localhost:9092` local, `kafka:29092` Docker | Bootstrap server |
| `KAFKA_TOPIC_PRICES` | `binance_live_prices` | Topic input |
| Starting offsets | `latest` | Chi doc du lieu moi |
| Output mode | `append` | Ghi batch moi vao Influx |
| Influx measurement | `market_data` | Measurement chua gia |
| Tag | `symbol` | Coin symbol |
| Fields | `price`, `volume` | Gia va khoi luong |
| Time precision | `ms` | Timestamp Binance theo millisecond |

## Spark Batch Layer

File: `spark_scripts/jobs/batch_layer.py`

| Thong so | Gia tri mac dinh | Y nghia |
|---|---:|---|
| `--mode` | `micro` | `batch` doc full topic, `micro` loc N phut gan nhat |
| `--offset-minutes` | `120` | Khoang du lieu micro-batch |
| Kafka `startingOffsets` | `earliest` | Doc tu dau topic de tinh batch |
| OHLCV windows | `1h`, `4h` | Nen gia ghi Postgres/MinIO |
| Market stats windows | `1h`, `4h` | VWAP, volume, volatility |
| Postgres tables | `ohlcv_candles`, `market_stats`, `symbol_profiles` | Output quan he |
| MinIO path | `s3a://processed-data/...` | Output parquet |
| Upsert key OHLCV | `symbol`, `interval`, `open_time` | Chong trung du lieu |

## InfluxDB

File: `docker/docker-compose.yml`, `k8s/influxdb.yaml`

| Thong so | Gia tri |
|---|---:|
| Image | `influxdb:2.7` |
| URL local | `http://localhost:8086` |
| Org | `crypto_org` |
| Bucket | `crypto_prices` |
| Token dev | `super-secret-token-12345` |
| Measurement | `market_data` |
| Fields | `price`, `volume` |

## PostgreSQL

File: `docker/docker-compose.yml`, `k8s/postgres.yaml`

| Thong so | Gia tri |
|---|---:|
| Image | `postgres:15` / `postgres:15-alpine` |
| DB | `cryptodb` |
| User/password | `admin/password123` |
| Port | `5432` |
| JDBC driver | `org.postgresql.Driver` |

## Backend API

File: `backend/main.py`, `backend/ml_service.py`

| Thong so | Gia tri mac dinh | Y nghia |
|---|---:|---|
| Framework | FastAPI | API + WebSocket |
| Port | `8000` | HTTP server |
| `ALLOWED_ORIGINS` | `*` | CORS dev |
| `DISPLAY_TZ` | `Asia/Ho_Chi_Minh` | Time hien thi |
| Market summary range | `-2h` | API trang chu |
| History range | 15-240 phut | Gioi han query detail |
| Forecast steps | 1-60, mac dinh 15 | So phut du doan |
| WebSocket interval | 2 giay | Poll gia moi de push frontend |
| `MODEL_PATH` | local `spark_scripts/ml/artifacts/model.pt`, container `/app/model.pt` | File model local backend load |
| `LOAD_MODEL_FROM_MINIO` | `0` local, `1` Docker/K8S | Tu tai model tu MinIO neu local file chua co |
| `MINIO_MODEL_BUCKET` | `ml-models` | Bucket chua model artifact |
| `MINIO_MODEL_KEY` | `lstm/model.pt` | Object key cua model |

## ML Training

File: `backend/ml_service.py`, `spark_scripts/ml/train_from_minio.py`

| Thong so | Gia tri mac dinh | Y nghia |
|---|---:|---|
| Model | LSTM | Sequence model |
| `WINDOW_SIZE` | 60 | 60 phut lich su / sample |
| `WARMUP` | 20 | So diem bo qua cho indicator on dinh |
| `NUM_FEATURES` | 5 | return, MA5 ratio, MA20 ratio, volatility, RSI |
| `HIDDEN_SIZE` | 128 | LSTM hidden units |
| `NUM_LAYERS` | 2 | LSTM layers |
| `BATCH_SIZE` | 512 | Train batch size |
| `EPOCHS` | 20 | So epoch |
| `TRAIN_DAYS` | 7 | So ngay doc tu MinIO/Influx |
| `MAX_MINIO_OBJECTS` | 0 | 0 la khong gioi han |
| `UPLOAD_MODEL_TO_MINIO` | 0 | 1 de upload model len MinIO |

## Frontend

File: `frontend/src/pages/Home.jsx`, `frontend/src/pages/CoinDetail.jsx`

| Thong so | Gia tri mac dinh | Y nghia |
|---|---:|---|
| Framework | React + Vite | SPA dashboard |
| Dev port | `5173` | Vite dev |
| Docker port | `3000:80` | Nginx serve static |
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL |
| Market refresh | 10 giay | Poll trang chu |
| Detail history poll | 60 giay | Cap nhat chart detail |
| Forecast refresh | 60 giay | Cap nhat forecast |
| Forecast horizon | 15 buoc | 15 phut |

## Kubernetes

File: `k8s/*.yaml`

| Module | Thong so | Gia tri |
|---|---|---:|
| Namespace | name | `crypto-system` |
| Backend | replicas | 2 |
| Backend | resources request | `100m CPU`, `256Mi` |
| Backend | resources limit | `500m CPU`, `512Mi` |
| Frontend | replicas | 2 |
| Frontend | resources request | `50m CPU`, `128Mi` |
| Frontend | resources limit | `200m CPU`, `256Mi` |
| Backend probes | liveness/readiness | `/health`, `/ready` |
| Frontend probe | path | `/` |
