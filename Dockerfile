# ==========================
# Dockerfile (multi-stage)
# ==========================

# --- Bază comună (env-uri utile) ---
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# --- Builder: produce wheels pentru dependențe (izolează toolchain-ul) ---
FROM base AS builder
# Toolchain minim pentru pachete care compilează (ex: psycopg2 fără binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

# --- Runtime: imagine finală mică, non-root, doar runtime deps ---
FROM base AS runtime
# Runtime libs ușoare (libpq5 pentru drivere Postgres clasice)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# User non-root (configurabil prin ARG dacă vrei)
ARG APP_UID=10001
ARG APP_GID=10001
RUN groupadd -g ${APP_GID} app && useradd -u ${APP_UID} -g ${APP_GID} -m -s /usr/sbin/nologin app

# Instalează dependențele din wheels (fără toolchain)
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels

# Copiază aplicația și migrațiile
COPY alembic.ini alembic.ini
COPY migrations/ migrations/
COPY app ./app
COPY docker/app-entrypoint.sh /app/docker/app-entrypoint.sh

# Permisiuni și exec
RUN chmod +x /app/docker/app-entrypoint.sh && chown -R app:app /app

# Env-uri sensibile aplicației
ENV PYTHONPATH=/app \
    APP_PORT=8001

# Expune portul pe care pornește Uvicorn din entrypoint (APP_PORT)
EXPOSE 8001

# Rulează ca non-root
USER app

# Rulează entrypoint-ul (care se ocupă de wait-for-db + alembic + uvicorn)
# Dacă în docker-compose.ai l-ai setat deja în `command:`, poți lăsa și acolo;
# acesta e doar defaultul imaginii.
CMD ["/app/docker/app-entrypoint.sh"]
