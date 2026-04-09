FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

WORKDIR /app

# 拷贝计算程序
COPY 1.cpu_linear_equations_no_record.py /app/1.cpu_linear_equations.py

# 拷贝 HTTP 包装器
COPY http_trigger.py /app/http_trigger.py
COPY run-with-http.sh /app/run-with-http.sh

# 安装依赖
RUN python -m pip install -U pip \
 && pip install --only-binary=:all: numpy scipy \
 && chmod +x /app/run-with-http.sh

# 非 root 用户
RUN groupadd -r app && useradd -r -g app appuser \
 && chown -R appuser:app /app
USER appuser

ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/app/run-with-http.sh"]
