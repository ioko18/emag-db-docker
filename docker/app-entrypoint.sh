#!/usr/bin/env sh
set -eu

log() { printf '[entrypoint] %s\n' "$*"; }
to_bool() {
  case "${1:-}" in 1|true|TRUE|yes|on|On|YES) return 0;; *) return 1;; esac
}

# --- Defaults (override prin env) ---
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

APP_MODULE="${APP_MODULE:-app.main:app}"
UVICORN_HOST="${UVICORN_HOST:-0.0.0.0}"
UVICORN_PORT="${UVICORN_PORT:-8001}"           # <- implicit 8001 ca să se potrivească cu ports: 8001:8001
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"
UVICORN_ACCESS_LOG="${UVICORN_ACCESS_LOG:-0}"
LOG_LEVEL="${LOG_LEVEL:-info}"

ALEMBIC_CONFIG="${ALEMBIC_CONFIG:-/app/alembic.ini}"
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-1}"  # 1/true pentru a rula migrațiile la start
WAIT_FOR_DB="${WAIT_FOR_DB:-auto}"                       # auto => așteaptă doar dacă DATABASE_URL este setat

WAIT_RETRIES="${WAIT_RETRIES:-60}"
WAIT_SLEEP_SECS="${WAIT_SLEEP_SECS:-1}"
MIGRATION_RETRIES="${MIGRATION_RETRIES:-20}"
MIGRATION_SLEEP_SECS="${MIGRATION_SLEEP_SECS:-2}"

# --- Wait for DB (TCP) ---
if { [ "${WAIT_FOR_DB}" = "auto" ] && [ -n "${DATABASE_URL:-}" ]; } || to_bool "${WAIT_FOR_DB}"; then
  if [ -n "${DATABASE_URL:-}" ]; then
    log "Waiting for DB: ${DATABASE_URL}"
    python - <<'PY'
import os, time, socket, sys, urllib.parse
url=os.environ["DATABASE_URL"].replace("postgresql+psycopg2","postgresql")
p=urllib.parse.urlsplit(url)
host=p.hostname or "db"
port=int(p.port or 5432)
retries=int(os.getenv("WAIT_RETRIES","60"))
sleep=float(os.getenv("WAIT_SLEEP_SECS","1"))
for i in range(retries):
    try:
        s=socket.create_connection((host,port),2); s.close()
        print(f"DB reachable at {host}:{port}")
        sys.exit(0)
    except Exception:
        time.sleep(sleep)
print(f"DB not reachable at {host}:{port} after {retries} tries")
sys.exit(1)
PY
  else
    log "WAIT_FOR_DB activ, dar DATABASE_URL nu este setat; sar peste wait."
  fi
fi

# --- Alembic migrations (cu retry) ---
if to_bool "${RUN_MIGRATIONS_ON_START}"; then
  i=0
  while : ; do
    i=$((i+1))
    log "Running: alembic -c ${ALEMBIC_CONFIG} upgrade head (attempt ${i})"
    if alembic -c "${ALEMBIC_CONFIG}" upgrade head; then
      log "Migrations applied."
      break
    fi
    if [ "${i}" -ge "${MIGRATION_RETRIES}" ]; then
      log "Alembic failed after ${MIGRATION_RETRIES} attempts. Exiting."
      exit 1
    fi
    log "Alembic failed. Retrying in ${MIGRATION_SLEEP_SECS}s ..."
    sleep "${MIGRATION_SLEEP_SECS}"
  done
else
  log "RUN_MIGRATIONS_ON_START=0 → skipping migrations."
fi

# --- Start Uvicorn (build argv în siguranță) ---
set -- python -m uvicorn "${APP_MODULE}" --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" --log-level "${LOG_LEVEL}"
if ! to_bool "${UVICORN_ACCESS_LOG}"; then
  set -- "$@" --no-access-log
fi
# Workers >1 doar dacă e setat
case "${UVICORN_WORKERS}" in
  ''|0|1) : ;;
  *) set -- "$@" --workers "${UVICORN_WORKERS}" ;;
esac

log "Starting: $*"
exec "$@"
