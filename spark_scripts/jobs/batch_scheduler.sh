#!/usr/bin/env bash
set -e

# Tự động lấy đường dẫn tuyệt đối của folder chứa script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SPARK_MASTER="spark://spark-master:7077"
# Sử dụng SCRIPT_DIR để trỏ đúng file batch_layer.py cùng folder
JOB_PATH="$SCRIPT_DIR/batch_layer.py"

CRON_INTERVAL=${CRON_INTERVAL:-600}
OFFSET_MINUTES=${OFFSET_MINUTES:-120}

echo "[BATCH-SCHEDULER] Khởi động..."
echo "[BATCH-SCHEDULER] Job path xác định: ${JOB_PATH}"

while true; do
    echo "[BATCH-SCHEDULER] ⏰ Bắt đầu job lúc $(date '+%Y-%m-%d %H:%M:%S')"

    # Thêm export PYTHONPATH để Spark nhận diện được folder config
    export PYTHONPATH=$PYTHONPATH:$(dirname "$SCRIPT_DIR")

    spark-submit \
        --master "${SPARK_MASTER}" \
        --deploy-mode client \
        --packages org.postgresql:postgresql:42.6.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        --conf "spark.executor.memory=1g" \
        --conf "spark.driver.memory=1g" \
        "${JOB_PATH}" \
        --mode micro \
        --offset-minutes "${OFFSET_MINUTES}"

    sleep "${CRON_INTERVAL}"
done