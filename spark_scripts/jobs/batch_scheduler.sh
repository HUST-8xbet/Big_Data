#!/usr/bin/env bash
# ============================================================
# BATCH SCHEDULER — Chạy micro-batch mỗi 10 phút
# ============================================================
# Mặc định: chạy mỗi 10 phút
# Sửa CRON_INTERVAL nếu muốn thay đổi tần suất
#
# Ví dụ:
#   CRON_INTERVAL=600   → mỗi 10 phút  (mặc định)
#   CRON_INTERVAL=3600  → mỗi 1 giờ
#   CRON_INTERVAL=1800  → mỗi 30 phút
# ============================================================

set -e

SPARK_MASTER="spark://spark-master:7077"
JOB_PATH="/opt/project/spark_scripts/jobs/batch_layer.py"
CRON_INTERVAL=${CRON_INTERVAL:-600}   # giây
OFFSET_MINUTES=${OFFSET_MINUTES:-120} # đọc 2 giờ gần nhất

echo "[BATCH-SCHEDULER] Khởi động — interval: ${CRON_INTERVAL}s, offset: ${OFFSET_MINUTES} phút"
echo "[BATCH-SCHEDULER] Spark Master: ${SPARK_MASTER}"
echo "[BATCH-SCHEDULER] Job path: ${JOB_PATH}"

while true; do
    echo "[BATCH-SCHEDULER] ⏰ Bắt đầu micro-batch job lúc $(date '+%Y-%m-%d %H:%M:%S')"

    spark-submit \
        --master "${SPARK_MASTER}" \
        --deploy-mode client \
        --conf "spark.executor.memory=1g" \
        --conf "spark.driver.memory=1g" \
        "${JOB_PATH}" \
        --mode micro \
        --offset-minutes "${OFFSET_MINUTES}"

    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[BATCH-SCHEDULER] ✅ Micro-batch hoàn tất — ngủ ${CRON_INTERVAL}s"
    else
        echo "[BATCH-SCHEDULER] ❌ Micro-batch thất bại (exit code: ${EXIT_CODE}) — vẫn tiếp tục sau ${CRON_INTERVAL}s"
    fi

    sleep "${CRON_INTERVAL}"
done
