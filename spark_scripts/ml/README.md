# LSTM Model Training

Backend dung LSTM de du doan return 1 phut tiep theo. Training nen doc du lieu batch tu MinIO de dung voi vai tro data lake cua pipeline; train tu InfluxDB chi nen coi la cach dev nhanh.

## File ML Va Backend

- `backend/ml_service.py`: dinh nghia LSTM, feature engineering, train/save/load model, realtime forecast.
- `spark_scripts/ml/train_from_minio.py`: doc batch JSON trong MinIO `raw-data/binance/*.json`, gom thanh nen 1 phut, train LSTM.
- `spark_scripts/ml/train_model.py`: cach phu, train tu InfluxDB da aggregate 1 phut.
- `spark_scripts/ml/backfill_history.py`: nap du lieu lich su tu Binance vao InfluxDB khi can co data nhanh.
- `spark_scripts/ml/export_training_data.py` va `spark_scripts/ml/train_from_file.py`: cach phu de train tren may GPU khac bang file `.npz`.

`model.pt` va `training_data.npz` la artifact, khong nen coi la source code. Neu train lai, model mac dinh se ghi vao `MODEL_PATH` hoac `spark_scripts/ml/artifacts/model.pt`.

## Train Tu MinIO

Chay local:

```bash
source venv/bin/activate
pip install -r backend/requirements.txt
python3 spark_scripts/ml/train_from_minio.py
```

Chay bang Docker Compose:

```bash
docker compose -f docker/docker-compose.yml --profile training run --rm model-trainer-minio
```

Bien moi truong quan trong:

- `MINIO_ENDPOINT`: mac dinh `http://localhost:9000`.
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: mac dinh `admin/password123`.
- `MINIO_TRAIN_BUCKET`: mac dinh `raw-data`.
- `MINIO_TRAIN_PREFIX`: mac dinh `binance/`.
- `TRAIN_DAYS`: so ngay du lieu gan nhat de train, mac dinh `7`.
- `MAX_MINIO_OBJECTS`: gioi han so file doc, `0` la khong gioi han.
- `MODEL_PATH`: noi ghi model local, mac dinh `spark_scripts/ml/artifacts/model.pt`.
- `UPLOAD_MODEL_TO_MINIO`: `1` de upload model sau train.
- `MINIO_MODEL_BUCKET`: mac dinh `ml-models`.
- `MINIO_MODEL_KEY`: mac dinh `lstm/model.pt`.

## Thong So LSTM

Thong so nam trong `ml_service.py`:

- `WINDOW_SIZE = 60`: moi sample dung 60 phut lich su.
- `WARMUP = 20`: bo 20 diem dau de MA20/RSI/volatility on dinh.
- `NUM_FEATURES = 5`: return, MA5 ratio, MA20 ratio, volatility, RSI.
- `HIDDEN_SIZE = 128`: kich thuoc hidden state cua LSTM.
- `NUM_LAYERS = 2`: so layer LSTM.
- `BATCH_SIZE = 512`: batch size khi train.
- `EPOCHS = 20`: so epoch.
- `MAX_BUFFER_SIZE = 120`: backend giu 120 diem gia gan nhat moi symbol de forecast realtime.
- `MAX_MINUTE_RETURN = 0.002`: cap return du doan moi phut toi da 0.2%.
- `PREDICTION_DAMPING = 0.25`: giam bien do raw output cua model.
- `MODEL_RETURN_WEIGHT = 0.35`, `TECHNICAL_RETURN_WEIGHT = 0.65`: tron LSTM voi baseline ky thuat de forecast on dinh hon.

## Luong Du Lieu Train Tu MinIO

1. `Crawler/binance_producer.py` gom 100 trade thanh 1 file JSON.
2. File duoc ghi vao `raw-data/binance/trades_YYYYmmdd_HHMMSS.json`.
3. `train_from_minio.py` doc cac file nay, loc theo `TRAIN_DAYS`.
4. Trade day duoc aggregate thanh gia trung binh 1 phut theo tung symbol.
5. `ml_service.train_model_on_historical_data()` tao feature va train LSTM.
6. Model duoc luu vao `MODEL_PATH`, optionally upload len `ml-models/lstm/model.pt`.

Backend khi start se load model local tu `MODEL_PATH`. Neu `LOAD_MODEL_FROM_MINIO=1` va local model chua ton tai, backend se thu download `s3://MINIO_MODEL_BUCKET/MINIO_MODEL_KEY` ve `MODEL_PATH` truoc khi load model.
