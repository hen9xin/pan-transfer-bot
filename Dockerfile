# ==========================================
# 基础运行镜像 (Python 3.11 Slim)
# ==========================================
FROM python:3.11-slim

# 设置环境变量，避免生成 .pyc 并保证实时标准输出
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置容器工作目录
WORKDIR /app

# 安装基础依赖与健康检查工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 利用 Docker 缓存层，先拷贝并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目源代码与静态资源
COPY config.py app.py ./
COPY services/ ./services/
COPY static/ ./static/

# 暴露服务端口
EXPOSE 8000

# 容器健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动服务
CMD ["python", "app.py"]
