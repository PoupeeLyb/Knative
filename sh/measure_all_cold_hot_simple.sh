#!/bin/bash

set -u
set -o pipefail

# =========================
# 配置
# =========================
NAMESPACE="default"
INTERVAL_BETWEEN_SERVICES=600   # 10分钟
LOG_POLL_INTERVAL=0.2

SERVICES=(
  "track-algorithm"
  "object-detect"
  "attitude-determination"
  "core-network"
  "cpu-cpp"
  "cpu-java"
  "cpu-python"
)

BASE_URL="http://%s.default.local.com:31631"

OUTPUT_DIR="power4/measure_results"

COLD_CSV="${OUTPUT_DIR}/cold_start_all.csv"
HOT_CSV="${OUTPUT_DIR}/hot_start_all.csv"

LOG_DIR="${OUTPUT_DIR}/logs"
mkdir -p "$LOG_DIR"

# =========================
# CSV 表头（新增 service_name）
# =========================
echo "service_name,iteration,request_id,pod_name,curl_time,program_main_start,program_logic_start,program_logic_end,program_main_end" > "$COLD_CSV"
echo "service_name,iteration,request_id,pod_name,curl_time,program_main_start,program_logic_start,program_logic_end,program_main_end" > "$HOT_CSV"

# =========================
# 时间函数
# =========================
now_local() {
    date '+%H:%M:%S.%3N'
}

now_utc() {
    date -u '+%Y-%m-%dT%H:%M:%S.%3NZ'
}

# =========================
# 提取函数（通用版）
# =========================
extract_main_start() {
    grep "Program start.*$2" "$1" | tail -n 1 | sed -E 's/.*Program start: *//'
}

extract_main_end() {
    grep "Program end.*$2" "$1" | tail -n 1 | sed -E 's/.*Program end: *//'
}

extract_logic_start() {
    grep "程序启动.*$2" "$1" | tail -n 1 | sed -E 's/.*时间: *//'
}

extract_logic_end() {
    grep "程序结束.*$2" "$1" | tail -n 1 | sed -E 's/.*时间: *//'
}

# =========================
# 等待 Pod 消失（冷启动）
# =========================
wait_scale_to_zero() {
    local svc=$1
    echo "[INFO] waiting $svc scale to zero..."

    while true; do
        PODS=$(kubectl get pods -n $NAMESPACE -l serving.knative.dev/service=$svc --no-headers 2>/dev/null)
        if [ -z "$PODS" ]; then
            break
        fi
        sleep 2
    done
}

# =========================
# 等待 Pod 出现
# =========================
wait_pod() {
    local svc=$1

    while true; do
        POD=$(kubectl get pods -n $NAMESPACE \
            -l serving.knative.dev/service=$svc \
            -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

        if [ -n "$POD" ]; then
            echo "$POD"
            return
        fi

        sleep 0.5
    done
}

# =========================
# 等待日志结束
# =========================
wait_log_finish() {
    local pod=$1
    local req=$2
    local since=$3

    while true; do
        LOG=$(kubectl logs $pod -n $NAMESPACE -c user-container --since-time=$since)

        if echo "$LOG" | grep -q "Program end.*$req"; then
            echo "$LOG"
            return
        fi

        sleep $LOG_POLL_INTERVAL
    done
}

# =========================
# 主循环
# =========================
for idx in "${!SERVICES[@]}"
do
    svc=${SERVICES[$idx]}
    url=$(printf "$BASE_URL" "$svc")

    echo "======================================"
    echo "[INFO] testing service: $svc"
    echo "======================================"

    # =========================
    # 冷启动
    # =========================
    wait_scale_to_zero "$svc"

    REQ="cold-${svc}-$(date +%s%N)"
    CURL_TIME=$(now_local)
    LOG_TIME=$(now_utc)

    echo "[INFO] cold start trigger: $REQ"

    curl -s "$url?id=$REQ" > /dev/null

    POD=$(wait_pod "$svc")

    kubectl wait pod $POD -n $NAMESPACE --for=condition=Ready --timeout=120s > /dev/null 2>&1 || true

    LOG=$(wait_log_finish "$POD" "$REQ" "$LOG_TIME")

    echo "$LOG" > "${LOG_DIR}/${svc}_cold.log"

    MAIN_START=$(extract_main_start "${LOG_DIR}/${svc}_cold.log" "$REQ")
    MAIN_END=$(extract_main_end "${LOG_DIR}/${svc}_cold.log" "$REQ")
    LOGIC_START=$(extract_logic_start "${LOG_DIR}/${svc}_cold.log" "$REQ")
    LOGIC_END=$(extract_logic_end "${LOG_DIR}/${svc}_cold.log" "$REQ")

    echo "$svc,1,$REQ,$POD,$CURL_TIME,$MAIN_START,$LOGIC_START,$LOGIC_END,$MAIN_END" >> "$COLD_CSV"

    echo "[INFO] cold done"

    # =========================
    # 热启动
    # =========================
    sleep 2

    REQ="hot-${svc}-$(date +%s%N)"
    CURL_TIME=$(now_local)
    LOG_TIME=$(now_utc)

    echo "[INFO] hot start trigger: $REQ"

    curl -s "$url?id=$REQ" > /dev/null

    LOG=$(wait_log_finish "$POD" "$REQ" "$LOG_TIME")

    echo "$LOG" > "${LOG_DIR}/${svc}_hot.log"

    MAIN_START=$(extract_main_start "${LOG_DIR}/${svc}_hot.log" "$REQ")
    MAIN_END=$(extract_main_end "${LOG_DIR}/${svc}_hot.log" "$REQ")
    LOGIC_START=$(extract_logic_start "${LOG_DIR}/${svc}_hot.log" "$REQ")
    LOGIC_END=$(extract_logic_end "${LOG_DIR}/${svc}_hot.log" "$REQ")

    echo "$svc,1,$REQ,$POD,$CURL_TIME,$MAIN_START,$LOGIC_START,$LOGIC_END,$MAIN_END" >> "$HOT_CSV"

    echo "[INFO] hot done"

    # =========================
    # 等待 10 分钟
    # =========================
    if [ "$idx" -lt $((${#SERVICES[@]} - 1)) ]; then
        echo "[INFO] sleep 10 minutes..."
        sleep $INTERVAL_BETWEEN_SERVICES
    fi

done

echo "[INFO] ALL DONE"
