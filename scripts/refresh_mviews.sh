# scripts/refresh_mviews.sh
#!/usr/bin/env bash
# Refresh materialized views (CONCURRENTLY) cu timeouts sigure.

set -Eeuo pipefail

PGUSER="${PGUSER:-appuser}"
PGDATABASE="${PGDATABASE:-appdb}"
PGSCHEMA="${PGSCHEMA:-app}"
SERVICE_DB="${SERVICE_DB:-db}"

# Alege docker compose
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  echo "ERROR: nici «docker compose», nici «docker-compose» nu sunt în PATH." >&2
  exit 1
fi

# psql în containerul DB
psql_db(){
  $COMPOSE exec -T "$SERVICE_DB" \
    psql -X -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDATABASE" "$@"
}

# Listează aici MVs de refresh-uit (în ordinea dorită)
MVS=(
  "mv_emag_stock_summary"
  "mv_emag_best_offer"
)

# timeouts sigure pentru a nu bloca
SET_TIMEOUTS="SET lock_timeout='3s'; SET statement_timeout='2min';"

echo "[refresh_mviews] start"
psql_db -c "SELECT 'ok:db';" >/dev/null

for mv in "${MVS[@]}"; do
  echo "[refresh_mviews] refreshing ${PGSCHEMA}.${mv} ..."
  psql_db -c "${SET_TIMEOUTS} REFRESH MATERIALIZED VIEW CONCURRENTLY ${PGSCHEMA}.${mv};"
done

echo "[refresh_mviews] done"
