# scripts/refresh_mviews.sh
#!/usr/bin/env bash
# Refresh materialized views cu timeouts sigure.
# Dacă MV nu e populat încă, face REFRESH normal; altfel CONCURRENTLY.

set -Eeuo pipefail

PGUSER="${PGUSER:-appuser}"
PGDATABASE="${PGDATABASE:-appdb}"
PGSCHEMA="${PGSCHEMA:-app}"
SERVICE_DB="${SERVICE_DB:-db}"
LOCK_TIMEOUT="${LOCK_TIMEOUT:-3s}"
STMT_TIMEOUT="${STMT_TIMEOUT:-2min}"

# Alege docker compose
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  echo "ERROR: nici «docker compose», nici «docker-compose» nu sunt în PATH." >&2
  exit 1
fi

# helper psql în containerul DB
psql_db() {
  $COMPOSE exec -T "$SERVICE_DB" \
    psql -X -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDATABASE" "$@"
}

# Listează MVs în ordinea dorită
MVS=(
  "mv_emag_stock_summary"
  "mv_emag_best_offer"
)

exists_mv() {
  local mv="$1"
  psql_db -Atqc "select exists(
    select 1 from pg_matviews
    where schemaname='${PGSCHEMA}' and matviewname='${mv}'
  );"
}

is_populated() {
  local mv="$1"
  psql_db -Atqc "select coalesce((
    select c.relispopulated
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='${PGSCHEMA}'
      and c.relname='${mv}'
      and c.relkind='m'
  ), false);"
}

refresh_mv() {
  local mv="$1"

  if [[ "$(exists_mv "$mv")" != "t" ]]; then
    echo "[refresh_mviews] skip ${PGSCHEMA}.${mv} (nu există)"
    return 0
  fi

  if [[ "$(is_populated "$mv")" == "t" ]]; then
    echo "[refresh_mviews] refreshing CONCURRENTLY ${PGSCHEMA}.${mv} ..."
    psql_db <<SQL
SET lock_timeout='${LOCK_TIMEOUT}';
SET statement_timeout='${STMT_TIMEOUT}';
REFRESH MATERIALIZED VIEW CONCURRENTLY ${PGSCHEMA}.${mv};
SQL
  else
    echo "[refresh_mviews] first populate (non-concurrently) ${PGSCHEMA}.${mv} ..."
    psql_db <<SQL
SET lock_timeout='${LOCK_TIMEOUT}';
SET statement_timeout='${STMT_TIMEOUT}';
REFRESH MATERIALIZED VIEW ${PGSCHEMA}.${mv};
SQL
  fi
}

echo "[refresh_mviews] start"
psql_db -c "select 'ok:db';" >/dev/null

for mv in "${MVS[@]}"; do
  refresh_mv "$mv"
done

echo "[refresh_mviews] done"
