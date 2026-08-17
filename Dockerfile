FROM python:3.13-slim

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Install Python deps. NOTE: local embeddings ([embeddings] extra) are intentionally
# NOT installed here — the all-MiniLM index build takes ~50 min on Railway's CPU, far
# exceeding the healthcheck window (crash loop). DEV runs with embeddings gracefully
# disabled; PROD (bare-metal) installs the extra and serves a prebuilt cache.
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir .

# Download spaCy model
# Pinned model wheel: `spacy download` fetches a compatibility table that
# rate-limits (429) on shared build IPs; the release asset URL does not.
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# Copy backend application code
COPY backend/app/ app/

# Copy frontend (served by FastAPI at / and /static)
COPY frontend/ /app/frontend/

# Create non-root user with writable job storage
RUN useradd -m -r appuser && \
    mkdir -p /home/appuser/.folio-enrich/jobs && \
    chown -R appuser:appuser /home/appuser
USER appuser

ENV FOLIO_ENRICH_JOBS_DIR=/home/appuser/.folio-enrich/jobs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')"

# Most PaaS platforms inject PORT; fall back to 8000 for local use
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
