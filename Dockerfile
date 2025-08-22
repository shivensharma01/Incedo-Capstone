# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Build tools (needed for some scientific wheels); keep minimal
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# ----- Dependencies -----
COPY requirements.txt .

# Clean conda/local/mac-specific entries, install deps, then guarantee Flask
RUN pip install --upgrade pip setuptools wheel && \
    sed -E '/(@ file:|^file:|\/Users\/|\/private\/|\/opt\/conda\/|\/tmp\/build\/|\/croot\/|\/work\/|macosx_|^tf[-_]?keras\b)/d' requirements.txt \
      > requirements.clean.txt && \
    pip install --no-cache-dir -r requirements.clean.txt && \
    pip install --no-cache-dir Flask

# ----- App code -----
COPY . .

EXPOSE 8080

# Gunicorn entrypoint (Flask app object is `app` in app.py)
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} app:app"]