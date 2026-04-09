# 使用 GCC 镜像
FROM gcc:12.3.0-bullseye

# 安装必要库
RUN apt-get update && apt-get install -y --no-install-recommends \
    libeigen3-dev \
    cmake \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 拷贝 C++ 源文件
COPY cpu_linear_equations.cpp /app/cpu_linear_equations.cpp

# 拷贝 HTTP 包装器
COPY http_trigger.py /app/http_trigger.py
COPY run-with-http.sh /app/run-with-http.sh

# 编译 C++ 程序
RUN g++ -O2 -std=c++17 cpu_linear_equations.cpp -I /usr/include/eigen3 -o cpu_linear_equations && \
    chmod +x /app/run-with-http.sh /app/cpu_linear_equations

ENV PORT=8080
EXPOSE 8080

# 启动脚本作为入口
ENTRYPOINT ["/app/run-with-http.sh"]
