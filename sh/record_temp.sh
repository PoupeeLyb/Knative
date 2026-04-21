#!/bin/bash

INTERVAL=0.5   # 采样间隔（秒，可调）
OUT=temp_log.csv

echo "timestamp,temp_celsius" > $OUT

while true
do
    ts=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    temp_raw=$(cat /sys/class/thermal/thermal_zone0/temp)
    temp_c=$(awk "BEGIN {printf \"%.3f\", $temp_raw/1000}")
    echo "$ts,$temp_c" >> $OUT
    sleep $INTERVAL
done

