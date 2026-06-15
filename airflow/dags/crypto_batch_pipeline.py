from __future__ import annotations

from datetime import datetime, timedelta
import os

import boto3
from airflow import DAG
from airflow.exceptions import AirflowSkipException
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator


DEFAULT_ARGS = {
    "owner": "crypto-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/opt/project")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "password123")
RAW_BUCKET = os.getenv("MINIO_RAW_BUCKET", "raw-data")
RAW_PREFIX = os.getenv("MINIO_RAW_PREFIX", "binance/")


def assert_minio_has_recent_raw_data(**context):
    """Skip the batch run when the data lake has no raw Binance files yet."""
    client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )
    response = client.list_objects_v2(Bucket=RAW_BUCKET, Prefix=RAW_PREFIX, MaxKeys=1)
    if response.get("KeyCount", 0) == 0:
        raise AirflowSkipException(f"No raw files found at s3://{RAW_BUCKET}/{RAW_PREFIX}")


with DAG(
    dag_id="crypto_micro_batch_layer",
    description="Run Spark micro-batch from Kafka to PostgreSQL and MinIO.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=30),
    tags=["crypto", "batch", "spark", "minio"],
) as dag:
    check_raw_data = PythonOperator(
        task_id="check_minio_raw_data",
        python_callable=assert_minio_has_recent_raw_data,
    )

    run_micro_batch = SparkSubmitOperator(
        task_id="run_spark_micro_batch",
        conn_id="spark_default",
        application=f"{PROJECT_ROOT}/spark_scripts/jobs/batch_layer.py",
        application_args=["--mode", "micro", "--offset-minutes", "180"],
        conf={
            "spark.executorEnv.PYTHONPATH": PROJECT_ROOT,
            "spark.executorEnv.KAFKA_BROKER": "kafka:29092",
            "spark.executorEnv.KAFKA_TOPIC_PRICES": "binance_live_prices",
            "spark.executorEnv.PG_HOST": "postgres",
            "spark.executorEnv.PG_PORT": "5432",
            "spark.executorEnv.PG_DB": "cryptodb",
            "spark.executorEnv.PG_USER": "admin",
            "spark.executorEnv.PG_PASSWORD": "password123",
            "spark.executorEnv.MINIO_ENDPOINT": "http://minio:9000",
            "spark.executorEnv.MINIO_ROOT_USER": "admin",
            "spark.executorEnv.MINIO_ROOT_PASSWORD": "password123",
        },
        env_vars={
            "PYTHONPATH": PROJECT_ROOT,
            "KAFKA_BROKER": "kafka:29092",
            "KAFKA_TOPIC_PRICES": "binance_live_prices",
            "PG_HOST": "postgres",
            "PG_PORT": "5432",
            "PG_DB": "cryptodb",
            "PG_USER": "admin",
            "PG_PASSWORD": "password123",
            "MINIO_ENDPOINT": "http://minio:9000",
            "MINIO_ROOT_USER": "admin",
            "MINIO_ROOT_PASSWORD": "password123",
        },
        name="crypto-airflow-micro-batch",
        verbose=True,
    )

    check_raw_data >> run_micro_batch

