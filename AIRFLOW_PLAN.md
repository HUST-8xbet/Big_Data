# Airflow Batch Plan

Airflow nen dieu phoi cac viec theo lo, khong thay crawler realtime. Crawler van chay lien tuc de day trade vao Kafka va MinIO. Airflow chi nen lo:

- Kiem tra MinIO co raw batch moi.
- Chay Spark batch layer theo dinh ky.
- Train LSTM tu MinIO theo lich rieng.
- Co the them data quality checks sau batch.

## Lich Chay De Xuat

| Workflow | Lich | Ly do |
|---|---:|---|
| Crawler Binance -> Kafka/MinIO | chay lien tuc | Gia crypto realtime, khong nen dung Airflow de poll tung phut |
| Spark speed layer Kafka -> InfluxDB | chay lien tuc | Phuc vu chart/live API |
| Airflow micro-batch Spark | moi 15 phut | Du nhanh cho dashboard/statistics, khong tao qua nhieu Spark jobs |
| Micro-batch lookback | 180 phut | Co overlap de bu late data/restart; Postgres upsert giam trung lap |
| Full batch/backfill | moi ngay 00:10 UTC | Doi ngay moi on dinh, tinh lai aggregate neu can |
| Train LSTM tu MinIO | moi ngay 00:30 UTC | Sau daily batch, du lieu ngay truoc da kha day du |
| Data quality check | sau moi micro-batch | Kiem tra so record, symbol count, gia null/negative |

Voi do an/du an sinh vien, lich 15 phut la can bang tot. Neu may yeu, doi micro-batch thanh moi 30 phut. Neu can dashboard gan realtime hon, giu speed layer streaming va khong nen day batch xuong 1-5 phut vi Spark startup overhead se lon.

## DAG Da Them

- `airflow/dags/crypto_batch_pipeline.py`: DAG `crypto_micro_batch_layer`, chay moi 15 phut, check raw data tren MinIO roi submit Spark batch `--mode micro --offset-minutes 180`.
- `airflow/dags/crypto_ml_training.py`: DAG `crypto_train_lstm_from_minio`, chay moi ngay 00:30 UTC, train LSTM tu MinIO va upload model len bucket `ml-models`.

## Ket Noi Airflow Can Co

Airflow can cai provider:

```bash
pip install apache-airflow-providers-apache-spark boto3
```

Tao Spark connection trong Airflow UI:

- Conn Id: `spark_default`
- Conn Type: `Spark`
- Host: `spark://spark-master`
- Port: `7077`

Mount repo vao Airflow container tai `/opt/project`, va mount DAGs:

```text
./airflow/dags:/opt/airflow/dags
../:/opt/project
```

Airflow container phai nam cung Docker network `crypto-network` de thay `spark-master`, `minio`, `postgres`, `kafka`.

## Huong Code Nen Di

1. Giu `Crawler/binance_producer.py` de ghi raw JSON vao `raw-data/binance/`.
2. Them Airflow DAG check raw data truoc khi batch.
3. Chay `spark_scripts/jobs/batch_layer.py --mode micro --offset-minutes 180` bang `SparkSubmitOperator`.
4. Sau batch, co the them task kiem tra Postgres co records moi.
5. Train model bang `spark_scripts/ml/train_from_minio.py`, upload len `ml-models/lstm/model.pt`.
6. Restart backend hoac de backend rollout lai de load model moi tu MinIO.

