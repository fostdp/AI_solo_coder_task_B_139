# ============================================
# Stage 1: builder - 安装编译依赖
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ============================================
# Stage 2: runtime - 仅运行时依赖
# ============================================
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    libopenblas0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false

COPY backend ./backend
COPY microservices ./microservices
COPY config ./config
COPY alembic.ini .
COPY alembic ./alembic 2>/dev/null || true

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", \
     "backend.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:8000", \
     "--worker-connections", "1024", \
     "--max-requests", "5000", \
     "--max-requests-jitter", "500", \
     "--timeout", "120", \
     "--keep-alive", "10", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
