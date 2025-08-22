# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Build tools (safe to keep; needed for some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# IMPORTANT: clean conda/local/mac-specific lines before pip install
RUN pip install --upgrade pip && \
    sed -E '/(@ file:|^file:|\/Users\/|\/private\/|\/opt\/conda\/|\/tmp\/build\/|\/croot\/|\/work\/|macosx_|^tf[-_]?keras\b)/d' requirements.txt \
      > requirements.clean.txt && \
    pip install --no-cache-dir -r requirements.clean.txt
COPY . .

EXPOSE 8080

# Gunicorn entrypoint; PORT is set by Cloud Run (defaults to 8080 locally)
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} app:app"]