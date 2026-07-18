#!/bin/bash

set -u
set -o pipefail

# =========================
# Config
# =========================
NAMESPACE="default"
COOLDOWN_BEFORE_COLD=600        # First check happens 10 minutes after the previous request
POD_RECHECK_INTERVAL=60         # If a pod still exists, wait 1 minute and check again
HOT_ITERATIONS=10
COLD_ITERATIONS=10
HOT_INTERVAL=1
LOG_POLL_INTERVAL=0.2

SERVICES=(
  "attitude-determination"
  "core-network"
  "cpu-cpp"
  "cpu-java"
  "cpu-python"
  "object-detect"
  "track-algorithm"
)

BASE_URL="http://%s.default.local.com:31631"

OUTPUT_DIR="power4/measure_results_combined"
COLD_CSV="${OUTPUT_DIR}/cold_start_all.csv"
HOT_CSV="${OUTPUT_DIR}/hot_start_all.csv"
LOG_DIR="${OUTPUT_DIR}/logs"

mkdir -p "$LOG_DIR"

echo "service_name,iteration,request_id,pod_name,curl_time,program_main_start,program_logic_start,program_logic_end,program_main_end" > "$COLD_CSV"
echo "service_name,iteration,request_id,pod_name,curl_time,program_main_start,program_logic_start,program_logic_end,program_main_end" > "$HOT_CSV"

now_local() {
    date '+%H:%M:%S.%3N'
}

now_utc() {
    date -u '+%Y-%m-%dT%H:%M:%S.%3NZ'
}

extract_main_start() {
    grep "Program start.*$2" "$1" | tail -n 1 | sed -E 's/.*Program start: *//'
}

extract_main_end() {
    grep "Program end.*$2" "$1" | tail -n 1 | sed -E 's/.*Program end: *//'
}

extract_logic_start() {
    awk '
        /Program start time:/ {
            sub(/^.*Program start time: */, "")
            print
        }
        /\[程序启动\]/ {
            line=$0
            if (match(line, /\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9][^)]*\)/)) {
                value=substr(line, RSTART + 1, RLENGTH - 2)
                sub(/ 北京时间$/, "", value)
                print value
            } else if (match(line, /时间: *[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9]/)) {
                value=substr(line, RSTART)
                sub(/^时间: */, "", value)
                print value
            }
        }
    ' "$1" | tail -n 1
}

extract_logic_end() {
    awk '
        /Program end time:/ {
            sub(/^.*Program end time: */, "")
            print
        }
        /\[程序结束\]/ {
            line=$0
            if (match(line, /\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9][^)]*\)/)) {
                value=substr(line, RSTART + 1, RLENGTH - 2)
                sub(/ 北京时间$/, "", value)
                print value
            } else if (match(line, /时间: *[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9]/)) {
                value=substr(line, RSTART)
                sub(/^时间: */, "", value)
                print value
            }
        }
    ' "$1" | tail -n 1
}

normalize_logic_time() {
    local logic_time=$1
    local main_time=$2
    local main_date

    if [[ "$logic_time" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}$ ]]; then
        main_date=$(echo "$main_time" | sed -E 's/.*time: *([0-9]{4}-[0-9]{2}-[0-9]{2}).*/\1/')
        if [ -n "$main_date" ] && [ "$main_date" != "$main_time" ]; then
            echo "$main_date $logic_time"
            return
        fi
    fi

    echo "$logic_time"
}

get_pod() {
    local svc=$1

    kubectl get pods -n "$NAMESPACE" \
        -l serving.knative.dev/service="$svc" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

existing_test_pods() {
    local svc pod found=false

    for svc in "${SERVICES[@]}"; do
        pod=$(get_pod "$svc")
        if [ -n "$pod" ]; then
            echo "$svc:$pod"
            found=true
        fi
    done

    [ "$found" = "true" ]
}

wait_no_existing_pod_before_cold() {
    local svc=$1
    local need_cooldown=$2
    local existing

    if [ "$need_cooldown" = "true" ]; then
        echo "[INFO] wait 10 minutes before checking $svc for cold start..."
        sleep "$COOLDOWN_BEFORE_COLD"
    fi

    while existing=$(existing_test_pods); do
        echo "[INFO] existing test pod(s) before $svc cold start:"
        echo "$existing"
        echo "[INFO] wait 1 minute and check again..."
        sleep "$POD_RECHECK_INTERVAL"
    done
}

wait_pod() {
    local svc=$1
    local pod

    while true; do
        pod=$(get_pod "$svc")

        if [ -n "$pod" ]; then
            echo "$pod"
            return
        fi

        sleep 0.5
    done
}

wait_log_finish() {
    local pod=$1
    local req=$2
    local since=$3
    local log

    while true; do
        log=$(kubectl logs "$pod" -n "$NAMESPACE" -c user-container --since-time="$since")

        if echo "$log" | grep -q "Program end.*$req"; then
            echo "$log"
            return
        fi

        sleep "$LOG_POLL_INTERVAL"
    done
}

write_result() {
    local csv=$1
    local svc=$2
    local iteration=$3
    local req=$4
    local pod=$5
    local curl_time=$6
    local log_file=$7
    local main_start main_end logic_start logic_end

    main_start=$(extract_main_start "$log_file" "$req")
    main_end=$(extract_main_end "$log_file" "$req")
    logic_start=$(extract_logic_start "$log_file" "$req")
    logic_end=$(extract_logic_end "$log_file" "$req")
    logic_start=$(normalize_logic_time "$logic_start" "$main_start")
    logic_end=$(normalize_logic_time "$logic_end" "$main_start")

    echo "$svc,$iteration,$req,$pod,$curl_time,$main_start,$logic_start,$logic_end,$main_end" >> "$csv"
}

has_previous_request=false

for svc in "${SERVICES[@]}"
do
    url=$(printf "$BASE_URL" "$svc")

    echo "======================================"
    echo "[INFO] testing service: $svc"
    echo "======================================"

    for cold_i in $(seq 1 "$COLD_ITERATIONS")
    do
        wait_no_existing_pod_before_cold "$svc" "$has_previous_request"

        req="cold-${svc}-${cold_i}-$(date +%s%N)"
        curl_time=$(now_local)
        log_time=$(now_utc)

        echo "[INFO] cold start iteration $cold_i trigger: $req"

        curl -s "$url?id=$req" > /dev/null

        pod=$(wait_pod "$svc")
        kubectl wait pod "$pod" -n "$NAMESPACE" --for=condition=Ready --timeout=120s > /dev/null 2>&1 || true

        log=$(wait_log_finish "$pod" "$req" "$log_time")
        log_file="${LOG_DIR}/${svc}_cold_${cold_i}.log"
        echo "$log" > "$log_file"
        write_result "$COLD_CSV" "$svc" "$cold_i" "$req" "$pod" "$curl_time" "$log_file"

        echo "[INFO] cold iteration $cold_i done"

        if [ "$cold_i" -eq 1 ]; then
            for hot_i in $(seq 1 "$HOT_ITERATIONS")
            do
                current_pod=$(get_pod "$svc")
                if [ -z "$current_pod" ]; then
                    echo "[ERROR] $svc pod disappeared before hot iteration $hot_i; cannot measure hot start"
                    exit 1
                fi

                req="hot-${svc}-${hot_i}-$(date +%s%N)"
                curl_time=$(now_local)
                log_time=$(now_utc)

                echo "[INFO] hot start iteration $hot_i trigger: $req"

                curl -s "$url?id=$req" > /dev/null

                log=$(wait_log_finish "$current_pod" "$req" "$log_time")
                log_file="${LOG_DIR}/${svc}_hot_${hot_i}.log"
                echo "$log" > "$log_file"
                write_result "$HOT_CSV" "$svc" "$hot_i" "$req" "$current_pod" "$curl_time" "$log_file"

                echo "[INFO] hot iteration $hot_i done"

                if [ "$hot_i" -lt "$HOT_ITERATIONS" ]; then
                    sleep "$HOT_INTERVAL"
                fi
            done
        fi

        has_previous_request=true
    done
done

echo "[INFO] ALL DONE"
