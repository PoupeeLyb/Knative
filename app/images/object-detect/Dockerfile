# 使用 Python 3.12 slim
FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm

# 安装依赖
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.5.1 && \
    pip install --no-cache-dir Pillow numpy

# 设置工作目录
WORKDIR /app

# 拷贝目标检测程序
COPY 6.object_detect_no_record.py /app/6.object_detect.py

# 拷贝模型与输入文件
COPY model /app/model

# 拷贝 HTTP 包装器
COPY http_trigger.py /app/
COPY run-with-http.sh /app/
RUN chmod +x /app/run-with-http.sh


# 创建非 root 用户运行
RUN groupadd -r app && \
    useradd -r -g app appuser && \
    chown -R appuser:app /app

USER appuser

# 暴露端口
ENV PORT=8080
EXPOSE 8080

# 使用包装器启动
ENTRYPOINT ["/app/run-with-http.sh"]
