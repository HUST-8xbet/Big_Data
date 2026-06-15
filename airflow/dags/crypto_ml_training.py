from __future__ import annotations

from datetime import datetime, timedelta
import os

from airflow import DAG
from airflow.operators.bash import BashOperator


DEFAULT_ARGS = {
    "owner": "crypto-team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/opt/project")


with DAG(
    dag_id="crypto_train_lstm_from_minio",
    description="Train LSTM model from MinIO raw batch files and upload model artifact.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="30 0 * * *",
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=2),
    tags=["crypto", "ml", "minio"],
) as dag:
    train_model = BashOperator(
        task_id="train_lstm_from_minio",
        bash_command=f"cd {PROJECT_ROOT} && python3 spark_scripts/ml/train_from_minio.py",
        env={
            "PYTHONPATH": PROJECT_ROOT,
            "MINIO_ENDPOINT": "http://minio:9000",
            "MINIO_ROOT_USER": "admin",
            "MINIO_ROOT_PASSWORD": "password123",
            "MINIO_TRAIN_BUCKET": "raw-data",
            "MINIO_TRAIN_PREFIX": "binance/",
            "MINIO_MODEL_BUCKET": "ml-models",
            "MINIO_MODEL_KEY": "lstm/model.pt",
            "MODEL_PATH": f"{PROJECT_ROOT}/spark_scripts/ml/artifacts/model.pt",
            "TRAIN_DAYS": "7",
            "UPLOAD_MODEL_TO_MINIO": "1",
        },
    )

