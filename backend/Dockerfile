FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend RUFF_CACHE_DIR=/tmp/ruff
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN useradd --create-home --uid 10001 ipbot && mkdir -p /data/documents && chown ipbot:ipbot /data/documents
COPY backend backend
COPY pyproject.toml ./
USER ipbot
