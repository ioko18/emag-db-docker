# syntax=docker/dockerfile:1.6
# ==========================
# Dockerfile (multi-stage)
# ==========================

# --- Bază comună ---
FROM python:3.11-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# --- Builder: produce wheels pentru dependențe ---
FROM base AS builder
ARG DEBIAN_FRONTEND=noninteractive
# Toolchain minim pentru pachete care compilează (ex: psycopg2 fără binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Cache pip între build-uri (BuildKit)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir=/wheels -r requirements.txt

# --- Runtime: imagine finală mică, non-root, doar runtime deps ---
FROM base AS runtime
ARG DEBIAN_FRONTEND=noninteractive
# libpq5 e util dacă folosești drivere care se leagă la libpq din sistem
# (poți să-l elimini dacă rămâi exclusiv pe *-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

# User non-root (configurabil prin ARG)
ARG APP_UID=10001
ARG APP_GID=10001
RUN groupadd -g ${APP_GID} app && useradd -u ${APP_UID} -g ${APP_GID} -m -s /usr/sbin/nologin app

# Instalează dependențele din wheels (fără toolchain)
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels

# Copiază aplicația și migrațiile (direct cu proprietar corect)
COPY --chown=app:app alembic.ini alembic.ini
COPY --chown=app:app migrations/ migrations/
COPY --chown=app:app app ./app
COPY --chown=app:app docker/app-entrypoint.sh /app/docker/app-entrypoint.sh
RUN chmod +x /app/docker/app-entrypoint.sh

# Env-uri aplicație
ENV PYTHONPATH=/app \
    APP_PORT=8001

# Expune portul pe care pornește Uvicorn din entrypoint (APP_PORT)
EXPOSE 8001

# Rulează ca non-root
USER app

# Rulează entrypoint-ul (wait-for-db + alembic + uvicorn)
# Dacă în docker-compose.yml ai deja command:, acesta e doar default-ul imaginii.
CMD ["/app/docker/app-entrypoint.sh"]
