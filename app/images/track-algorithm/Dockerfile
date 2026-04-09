FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libopencv-dev \
    python3 \
    python3-pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app

COPY data/ /data
COPY origin/ /app/

# 编译 main.cpp
RUN g++ -O2 main.cpp -o ovx1_app_cn `pkg-config --cflags --libs opencv4`

# 添加 HTTP 包装器脚本
COPY http_trigger.py /app/
COPY run-with-http.sh /app/
RUN chmod +x /app/run-with-http.sh

ENV DISPLAY=:0
ENV PORT=8080
EXPOSE 8080

# 使用包装器启动
ENTRYPOINT ["/app/run-with-http.sh"]

