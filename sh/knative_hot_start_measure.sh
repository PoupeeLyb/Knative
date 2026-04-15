#!/bin/bash

# =========================
# 配置
# =========================
KSVC_NAME="track-algorithm"
NAMESPACE="default"
URL="http://track-algorithm.default.local.com:31631"

ITERATIONS=1

OUTPUT="hot_start/hot_start_${KSVC_NAME}.csv"

LOG_DIR="logs_${KSVC_NAME}"
mkdir -p $LOG_DIR

# =========================
# CSV 表头
# =========================
echo "iteration,request_id,pod_name,curl_time,program_main_start,program_logic_start,program_logic_end,program_main_end" > $OUTPUT


# =========================
# 获取 Pod
# =========================
echo "[INFO] searching for Pod..."

while true
do
    POD=$(kubectl get pods -n $NAMESPACE \
        -l serving.knative.dev/service=$KSVC_NAME \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$POD" ]; then
        break
    fi

    sleep 0.5
done

echo "[INFO] pod found: $POD"


# =========================
# 等待 Pod Ready
# =========================
echo "[INFO] waiting for Pod Ready..."

kubectl wait pod $POD \
    -n $NAMESPACE \
    --for=condition=Ready \
    --timeout=120s > /dev/null

echo "[INFO] pod ready"


# =========================
# 热启动循环
# =========================
for i in $(seq 1 $ITERATIONS)
do

    echo "[INFO] iteration $i trigger"

    # 唯一 request id
    REQ_ID="req-${i}-$(date +%s%N)"

    # 触发时间
    CURL_TIME=$(date '+%H:%M:%S.%3N')
    LOG_TIME=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)

    # =========================
    # curl 触发 Knative
    # =========================
    curl -s "$URL?id=$REQ_ID" > /dev/null


    # =========================
    # 等待当前 request 的 Program end
    # =========================
    while true
    do

        LOG=$(kubectl logs $POD \
            -n $NAMESPACE \
            -c user-container \
            --since-time=$LOG_TIME)

        if echo "$LOG" | grep -q "Program end.*$REQ_ID"
        then
            break
        fi

        sleep 0.2

    done
    # =========================
    # 保存本次 request 日志
    # =========================

    echo "$LOG" > ${LOG_DIR}/hot_start_iteration_${i}.log

    # =========================
    # 提取日志
    # =========================
    PROGRAM_MAIN_START=$(echo "$LOG" | grep "Program start.*$REQ_ID" | tail -n 1 | awk -F': ' '{print $2}')

    PROGRAM_LOGIC_START=$(echo "$LOG" | grep "程序启动.*$REQ_ID" | tail -n 1 | awk -F'时间: ' '{print $2}')

    PROGRAM_LOGIC_END=$(echo "$LOG" | grep "程序结束.*$REQ_ID" | tail -n 1 | awk -F'时间: ' '{print $2}')

    PROGRAM_MAIN_END=$(echo "$LOG" | grep "Program end.*$REQ_ID" | tail -n 1 | awk -F': ' '{print $2}')


    # =========================
    # 写入 CSV
    # =========================
    echo "$i,$REQ_ID,$POD,$CURL_TIME,$PROGRAM_MAIN_START,$PROGRAM_LOGIC_START,$PROGRAM_LOGIC_END,$PROGRAM_MAIN_END" >> $OUTPUT


    echo "[INFO] iteration $i done"

    # 稍微间隔一下避免日志堆叠
    sleep 1

done


echo "[INFO] all results saved to $OUTPUT"
