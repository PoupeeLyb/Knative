#!/bin/bash

# =========================
# 配置区
# =========================

KSVC_NAME="track-algorithm"
NAMESPACE="default"

URL="http://track-algorithm.default.local.com:31631"

ITERATIONS=1
INTERVAL=540

OUTPUT="cold_start/cold_start_${KSVC_NAME}.csv"
LOG_DIR="logs_${KSVC_NAME}"

mkdir -p "$LOG_DIR"

# =========================
# CSV 表头
# =========================

echo "iteration,request_id,curl_time,pod_name,pod_create_time,container_start_time,pod_ready_time,program_main_start,program_logic_start,program_logic_end,program_main_end" > "$OUTPUT"


# =========================
# 实验主循环
# =========================

for i in $(seq 1 $ITERATIONS); do

  echo "[INFO] ===== iteration $i ====="

  # 唯一请求ID（防止日志污染）
  REQUEST_ID="cold-${i}-$(date +%s%N)"

  # ⭐ 稳定性等待（避免 gateway 队列波动）
  sleep 1

  # 记录 curl 时间
  CURL_TIME=$(date '+%H:%M:%S.%3N')

  echo "[INFO] curl trigger request_id=$REQUEST_ID"

  # HTTP 触发 Knative Service
  curl -s "$URL?id=$REQUEST_ID" > /dev/null &


  # =========================
  # 等待 Pod 创建（Cold start 核心）
  # =========================

  while true; do
    POD=$(kubectl get pods -n $NAMESPACE \
      -l serving.knative.dev/service=$KSVC_NAME \
      -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$POD" ]; then
        break
    fi

    sleep 0.5
  done

  echo "[INFO] pod = $POD"


  # =========================
  # 获取 Kubernetes 生命周期时间
  # =========================

  POD_CREATE_TIME=$(kubectl get pod $POD -n $NAMESPACE \
    -o jsonpath='{.metadata.creationTimestamp}')

  POD_READY_TIME=$(kubectl get pod $POD -n $NAMESPACE \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].lastTransitionTime}')

  CONTAINER_START_TIME=$(kubectl get pod $POD -n $NAMESPACE \
    -o jsonpath='{.status.containerStatuses[?(@.name=="user-container")].state.running.startedAt}')


  # =========================
  # 等待 Program end（Request 级精确匹配）
  # =========================

  while true; do

    LOG=$(kubectl logs $POD \
      -n $NAMESPACE \
      -c user-container)

    if echo "$LOG" | grep -q "Program end.*$REQUEST_ID"; then
        break
    fi

    sleep 0.2
  done


  # =========================
  # 保存日志
  # =========================

  LOG_FILE="$LOG_DIR/cold_start_iter_${i}.log"
  echo "$LOG" > "$LOG_FILE"


  # =========================
  # 提取程序执行时间（带 request_id）
  # =========================

  PROGRAM_MAIN_START=$(echo "$LOG" | grep "Program start.*$REQUEST_ID" | tail -n 1 | awk -F': ' '{print $2}')

  PROGRAM_LOGIC_START=$(echo "$LOG" | grep "程序启动" | tail -n 1 | awk -F'时间: ' '{print $2}')

  PROGRAM_LOGIC_END=$(echo "$LOG" | grep "程序结束" | tail -n 1 | awk -F'时间: ' '{print $2}')

  PROGRAM_MAIN_END=$(echo "$LOG" | grep "Program end.*$REQUEST_ID" | tail -n 1 | awk -F': ' '{print $2}')


  # =========================
  # 写入 CSV
  # =========================

  echo "$i,$REQUEST_ID,$CURL_TIME,$POD,$POD_CREATE_TIME,$CONTAINER_START_TIME,$POD_READY_TIME,$PROGRAM_MAIN_START,$PROGRAM_LOGIC_START,$PROGRAM_LOGIC_END,$PROGRAM_MAIN_END" >> "$OUTPUT"


  echo "[INFO] iteration $i done"

  # 实验间隔
  if [ "$i" -lt "$ITERATIONS" ]; then
    sleep "$INTERVAL"
  fi

done


echo "[INFO] experiment finished, results saved to $OUTPUT"
