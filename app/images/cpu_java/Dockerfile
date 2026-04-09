# 基础镜像
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 安装 Java、Python3、curl
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jdk python3 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 下载 commons-math3
RUN curl -L -o commons-math3-3.6.1.jar \
    https://repo1.maven.org/maven2/org/apache/commons/commons-math3/3.6.1/commons-math3-3.6.1.jar

# 拷贝 Java 源码
COPY main.java /app/main.java

# 拷贝 HTTP 包装器
COPY http_trigger.py /app/http_trigger.py
COPY run-with-http.sh /app/run-with-http.sh

# 编译 Java 文件
RUN javac -encoding UTF-8 -cp commons-math3-3.6.1.jar main.java && \
    chmod +x /app/run-with-http.sh

# 限制 Java CPU 核心数 + UTF-8
ENV JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount=1 -Dfile.encoding=UTF-8"
ENV PORT=8080
EXPOSE 8080

# 启动脚本
ENTRYPOINT ["/app/run-with-http.sh"]
