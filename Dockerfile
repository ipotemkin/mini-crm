FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

RUN useradd --create-home --uid 1000 appuser \
    && apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN mkdir -p /data /backups \
    && chmod +x /entrypoint.sh \
    && chown -R appuser:appuser /app /data /backups

USER appuser
ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/crm.sqlite3 \
    BACKUP_DIR=/backups

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
