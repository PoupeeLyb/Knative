FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV PORT=8080

# 基础依赖 + Python（HTTP Server 必须）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 拷贝源码
COPY origin/ /app/

# 编译 core_nf_simulation
RUN gcc \
    main.c \
    amf/amf_sim.c \
    smf/smf_sim.c \
    upf/upf_sim.c \
    -Icommon -Iamf -Ismf -Iupf \
    -O2 \
    -o core_nf_simulation

# 拷贝 HTTP 包装器
COPY http_trigger.py /app/
COPY run-with-http.sh /app/
RUN chmod +x /app/run-with-http.sh

EXPOSE 8080

# 使用 HTTP 包装器启动
ENTRYPOINT ["/app/run-with-http.sh"]
