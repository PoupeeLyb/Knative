FROM node:18-bullseye

WORKDIR /app

# 安装 Python3 和 bash（HTTP 包装器需要）
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 bash && \
    rm -rf /var/lib/apt/lists/*

# 先拷贝依赖描述文件，利用缓存
COPY origin/package*.json ./
RUN npm install

# 拷贝项目源码
COPY origin/ /app/

# 拷贝 HTTP 包装器
COPY http_trigger.py /app/
COPY run-with-http.sh /app/
RUN chmod +x /app/run-with-http.sh

ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/app/run-with-http.sh"]
