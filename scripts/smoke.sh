# scripts/smoke.sh
#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Config DB (override prin env)
# ─────────────────────────────────────────────────────────────────────────────
: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5434}"
: "${PGUSER:=appuser}"
: "${PGDATABASE:=appdb}"
: "${PGCONNECT_TIMEOUT:=5}"

# Dacă PGPASSWORD nu e setat, încearcă să-l iei din POSTGRES_PASSWORD (sau APP_DB_PASSWORD)
if [ -z "${PGPASSWORD:-}" ]; then
  if [ -n "${POSTGRES_PASSWORD:-}" ]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
  elif [ -n "${APP_DB_PASSWORD:-}" ]; then
    export PGPASSWORD="$APP_DB_PASSWORD"
  fi
fi

# Unele medii pot seta PGOPTIONS problematic (ex: "-csearch_path=...").
# Pentru a evita eroarea "invalid command-line argument for server process: -c",
# resetăm explicit pentru acest script.
unset PGOPTIONS || true

# ─────────────────────────────────────────────────────────────────────────────
# Config API (override prin env)
# ─────────────────────────────────────────────────────────────────────────────
: "${APP_PORT:=8001}"
: "${API_WAIT_RETRIES:=60}"
: "${API_WAIT_SLEEP_SECS:=1}"
: "${CURL_CONNECT_TIMEOUT:=2}"
: "${CURL_MAX_TIME:=5}"

have_cmd() { command -v "$1" >/dev/null 2>&1; }
log()      { printf '[SMOKE] %s\n' "$*"; }
die()      { printf '[SMOKE][ERR] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  local ok=1
  for c in "$@"; do
    if ! have_cmd "$c"; then
      printf '[SMOKE][ERR] missing command: %s\n' "$c" >&2
      ok=0
    fi
  done
  [ "$ok" -eq 1 ] || die "Install the commands above and retry."
}

# Uneltele minime
require_cmd curl psql

# ─────────────────────────────────────────────────────────────────────────────
# STRICT flag pentru psql
# ─────────────────────────────────────────────────────────────────────────────
: "${SMOKE_STRICT:=1}"   # 1 = ON (default), 0 = OFF
PSQL_STRICT=()
if [ "${SMOKE_STRICT}" = "1" ]; then
  PSQL_STRICT=(-v STRICT=1)
fi

# ─────────────────────────────────────────────────────────────────────────────
# Detectează BASE_URL (docker compose port, apoi fallback)
# ─────────────────────────────────────────────────────────────────────────────
detect_base_url() {
  if [ -n "${BASE_URL:-}" ]; then
    echo "$BASE_URL"
    return 0
  fi

  if have_cmd docker; then
    local mapped=""
    if docker compose version >/dev/null 2>&1; then
      mapped="$(docker compose port app 8001 2>/dev/null | tail -n1 || true)"
    elif have_cmd docker-compose; then
      mapped="$(docker-compose port app 8001 2>/dev/null | tail -n1 || true)"
    fi
    if [ -n "$mapped" ]; then
      local host_port="${mapped##*:}"
      echo "http://127.0.0.1:${host_port}"
      return 0
    fi
  fi

  echo "http://127.0.0.1:${APP_PORT}"
}

BASE_URL="$(detect_base_url)"

wait_for_api() {
  local url="${1}"
  local retries="${API_WAIT_RETRIES}"
  local sleep_s="${API_WAIT_SLEEP_SECS}"
  log "Wait for API @ ${url} (retries=${retries})..."
  for _ in $(seq 1 "${retries}"); do
    if curl -fsS --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" "$url" >/dev/null 2>&1; then
      log "API is up."
      return 0
    fi
    printf '.' >&2
    sleep "${sleep_s}"
  done
  printf '\n' >&2
  return 1
}

json_get() {
  local url="$1"; shift
  local jqexpr="${1:-.}"
  if have_cmd jq; then
    curl -fsS --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" \
      -H 'Accept: application/json' "$url" | jq -r "${jqexpr}"
  else
    log "jq not found; printing raw body for: $url"
    curl -fsS --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" \
      -H 'Accept: application/json' "$url"
  fi
}

diagnose_if_down() {
  log "docker compose ps:"
  if have_cmd docker && docker compose ps >/dev/null 2>&1; then
    docker compose ps || true
    log "Last 120 log lines from app:"
    docker compose logs --tail=120 app || true
  elif have_cmd docker-compose; then
    docker-compose ps || true
    log "Last 120 log lines from app:"
    docker-compose logs --tail=120 app || true
  fi
  log "Try manual curl (verbose):"
  curl -v --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" "${BASE_URL}/health" || true
}

# ─────────────────────────────────────────────────────────────────────────────
# 1) Rulează SQL smoke (idempotent)
# ─────────────────────────────────────────────────────────────────────────────
log "Running SQL smoke..."

# Conexiune libpq clară, fără să scurgem parola în CLI
psql -X -w \
  --set=ON_ERROR_STOP=1 \
  "${PSQL_STRICT[@]}" \
  "host=${PGHOST} port=${PGPORT} user=${PGUSER} dbname=${PGDATABASE} connect_timeout=${PGCONNECT_TIMEOUT}" \
  -f scripts/smoke.sql

# ─────────────────────────────────────────────────────────────────────────────
# 2) Așteaptă API-ul să fie ready (cu auto-detect pe port)
# ─────────────────────────────────────────────────────────────────────────────
if ! wait_for_api "${BASE_URL}/health"; then
  log "API did not become ready in time."
  diagnose_if_down
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3) Checks API
# ─────────────────────────────────────────────────────────────────────────────
log "Health:"
json_get "${BASE_URL}/health" '.'

log "Alembic migrations:"
json_get "${BASE_URL}/health/migrations" '.'

log "GET /categories?name=arduino"
json_get "${BASE_URL}/categories?name=arduino&page=1&page_size=5" '.total, .items[0]'

log "GET /products?name=senzor&sku_prefix=SKU-SMOKE&order_by=price&order_dir=desc&page_size=5"
json_get "${BASE_URL}/products?name=senzor&sku_prefix=SKU-SMOKE&order_by=price&order_dir=desc&page_size=5" '.total'

log "Done."
