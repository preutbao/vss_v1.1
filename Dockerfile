# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — IDX Smart Screener
# Target: Hugging Face Spaces (Docker SDK)
#
# Lưu ý Hugging Face Spaces:
#   - App PHẢI listen port 7860 (HF default)
#   - User trong container là non-root (uid=1000)
#   - /data được mount persistent nếu Space có storage enabled
#   - Không có internet access khi build (pip phải xong trong build stage)
#   - Biến môi trường HF_SPACE=1 được set tự động bởi platform
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Cài build tools cần thiết (pyarrow, scipy cần compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements trước để tận dụng Docker layer cache
COPY requirements.txt .

# Cài vào /install để copy sang stage runtime
RUN pip install --upgrade pip --quiet \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# Metadata
LABEL maintainer="Vietcap Smart Screener"
LABEL description="Vietnamese Stock Screener — Dash + Gunicorn"

# Biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Hugging Face Spaces yêu cầu port 7860
    PORT=7860 \
    # Gunicorn workers: 1 để tiết kiệm RAM trên free tier
    # Tăng lên 2-4 nếu dùng paid tier hoặc RAM >= 16GB
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=120

WORKDIR /app

# Copy installed packages từ builder stage
COPY --from=builder /install /usr/local

# Copy toàn bộ source code
COPY . .

# Tạo thư mục data — dữ liệu parquet sẽ ở đây
# Nếu HF Space có persistent storage: mount /data vào đây
# Nếu không: data được ship trong image (xem hướng dẫn bên dưới)
RUN mkdir -p data/raw data/processed assets \
 && chmod -R 755 data assets

# Hugging Face chạy container với user non-root (uid 1000)
# Tạo user trước để đảm bảo quyền ghi vào /app/data
RUN useradd -m -u 1000 appuser \
 && chown -R appuser:appuser /app

USER appuser

# Expose port cho HF Spaces
EXPOSE 7860

# Health check — HF dùng để biết app đã sẵn sàng chưa
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

# Chạy bằng gunicorn (production WSGI server)
# main:server — "main" là tên file main.py, "server" là app.server trong app_instance.py
CMD gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --worker-class gthread \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --preload \
    "main:server"