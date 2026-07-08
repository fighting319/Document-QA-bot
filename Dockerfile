# Document QA Bot — API / Gradio
FROM python:3.10-slim

WORKDIR /app

# 系统依赖（编译部分 Python 包 + 健康检查 curl）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 可选：国内构建加速，例如 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=
RUN if [ -n "$PIP_INDEX_URL" ]; then pip config set global.index-url "$PIP_INDEX_URL"; fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY first_problem/ first_problem/
COPY api_server.py main.py Bot-main.py load_embedding_models.py download_rerank_model.py ./
COPY scripts/ scripts/

RUN chmod +x scripts/entrypoint.sh \
    && mkdir -p models storage uploads

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_MODE=api \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    GRADIO_HOST=0.0.0.0 \
    GRADIO_PORT=7860

EXPOSE 8000 7860

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
