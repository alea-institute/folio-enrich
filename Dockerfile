FROM python:3.13-slim

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Install Python deps (with local embeddings — semantic FOLIO matching)
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir ".[embeddings]"

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy backend application code
COPY backend/app/ app/

# Copy frontend (served by FastAPI at / and /static)
COPY frontend/ /app/frontend/

# Create non-root user with writable job storage
RUN useradd -m -r appuser && \
    mkdir -p /home/appuser/.folio-enrich/jobs && \
    chown -R appuser:appuser /home/appuser

# Entrypoint runs as root to fix Railway volume ownership (volumes mount root-owned),
# then drops to appuser via gosu. Volume is mounted at /home/appuser/.folio-enrich.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

ENV FOLIO_ENRICH_JOBS_DIR=/home/appuser/.folio-enrich/jobs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')"

# Most PaaS platforms inject PORT; fall back to 8000 for local use
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
