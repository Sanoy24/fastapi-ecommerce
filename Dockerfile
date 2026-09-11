# --- Builder stage: compile/download dependencies with build tools ---
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- Runtime stage: slim image, no compilers, non-root user ---
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser \
    && chown appuser:appuser /app

COPY --from=builder /install /usr/local

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# start-period/timeout are generous on purpose: app startup (lifespan, in
# app/main.py) retries its Elasticsearch connection for up to ~50s when ES
# isn't already reachable, and request logging emits to Loki synchronously
# (no queueing, unlike the stdout/file sinks — see app/core/logger.py),
# adding real per-request latency if Loki is unreachable. Both are
# pre-existing app-level characteristics, not something to paper over here —
# in the docker-compose topology the app only starts once Elasticsearch is
# already healthy (depends_on: condition: service_healthy), so this is a
# safety margin for slow/adverse conditions, not the expected steady state.
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
