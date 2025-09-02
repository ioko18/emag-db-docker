# docker/app-entrypoint.sh
#!/usr/bin/env sh
set -eu

log() { printf >&2 '[%s] %s\n' "$(date +%FT%T%z)" "$*"; }
die() { log "FATAL: $*"; exit 1; }
istrue() {
  v="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "$v" in 1|true|t|yes|y|on) return 0;; *) return 1;; esac
}

# -------- defaults (aliniat cu docker-compose.yml) --------
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8001}"           # ✅ healthcheck-ul tău ascultă pe 8001
: "${UVICORN_WORKERS:=1}"
: "${APP_MODULE:=app.main:app}"
: "${APP_RELOAD:=0}"

: "${RUN_MIGRATIONS_ON_START:=1}"
: "${WAIT_FOR_DB:=auto}"            # auto | 1 | 0
: "${WAIT_RETRIES:=60}"
: "${WAIT_SLEEP_SECS:=1}"

: "${ALEMBIC_CONFIG:=/app/alembic.ini}"

# Siguranță pe FS read-only (evită .pyc)
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

show_env_summary() {
  log "App starting…"
  log " - APP_MODULE=$APP_MODULE  reload=${APP_RELOAD}  workers=${UVICORN_WORKERS}"
  log " - RUN_MIGRATIONS_ON_START=${RUN_MIGRATIONS_ON_START}"
  log " - WAIT_FOR_DB=${WAIT_FOR_DB}  retries=${WAIT_RETRIES}  sleep=${WAIT_SLEEP_SECS}s"
  log " - ALEMBIC_CONFIG=${ALEMBIC_CONFIG}"
  log " - DB_SCHEMA=${DB_SCHEMA:-app}  PGOPTIONS=${PGOPTIONS:-}"
}

wait_for_db() {
  # decide dacă așteptăm
  case "${WAIT_FOR_DB}" in
    0|false|no) log "WAIT_FOR_DB=${WAIT_FOR_DB} → nu aștept DB."; return 0;;
    auto) if ! istrue "${RUN_MIGRATIONS_ON_START}"; then
            log "WAIT_FOR_DB=auto & RUN_MIGRATIONS_ON_START!=1 → sar peste wait."; return 0
          fi ;;
  esac

  if [ -z "${DATABASE_URL:-}" ]; then
    log "DATABASE_URL este gol → nu aștept DB."
    return 0
  fi

  log "Aștept DB (cu psycopg SELECT 1; fallback TCP)…"
  # Folosim un script mic Python pentru retry/backoff
  # (suportă și DSN-uri SQLAlchemy gen postgresql+psycopg2://)
  python - <<'PY'
import os, sys, time, re, socket, urllib.parse
retries = int(os.getenv("WAIT_RETRIES", "60"))
sleep_s = float(os.getenv("WAIT_SLEEP_SECS", "1"))
url = os.getenv("DATABASE_URL")
if not url:
    sys.exit(0)

# normalizează dialectul pentru psycopg (postgresql://…)
pg_url = re.sub(r'^postgresql\+\w+://', 'postgresql://', url)

def tcp_ping(u: str) -> bool:
    p = urllib.parse.urlsplit(u)
    host, port = p.hostname or "db", int(p.port or 5432)
    s = socket.socket()
    s.settimeout(2.0)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

# încearcă cu psycopg dacă e disponibil
try:
    import psycopg
    for i in range(retries):
        try:
            with psycopg.connect(pg_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    sys.exit(0)
        except Exception:
            time.sleep(sleep_s)
    print("DB not reachable via psycopg after retries", file=sys.stderr)
    sys.exit(1)
except Exception:
    # fallback TCP
    for i in range(retries):
        if tcp_ping(pg_url):
            sys.exit(0)
        time.sleep(sleep_s)
    print("DB TCP not reachable after retries", file=sys.stderr)
    sys.exit(1)
PY
  log "DB este gata."
}

run_migrations() {
  if ! istrue "${RUN_MIGRATIONS_ON_START}"; then
    log "RUN_MIGRATIONS_ON_START=0 → sar peste migrații."
    return 0
  fi
  [ -f "${ALEMBIC_CONFIG}" ] || die "Lipsește ${ALEMBIC_CONFIG}"
  log "Rulez migrațiile Alembic…"
  alembic -c "${ALEMBIC_CONFIG}" upgrade head
  log "Migrațiile au fost aplicate."
}

start_uvicorn() {
  if istrue "${APP_RELOAD}"; then
    log "Pornesc Uvicorn în mod RELOAD…"
    exec python -m uvicorn "${APP_MODULE}" \
      --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" \
      --reload --reload-dir /app/app --proxy-headers --no-access-log
  else
    log "Pornesc Uvicorn (workers=${UVICORN_WORKERS})…"
    exec python -m uvicorn "${APP_MODULE}" \
      --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" \
      --workers "${UVICORN_WORKERS}" --proxy-headers --no-access-log
  fi
}

main() {
  show_env_summary
  wait_for_db
  run_migrations
  start_uvicorn
}

main "$@"
