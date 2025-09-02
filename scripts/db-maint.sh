# scripts/db-maint.sh
#!/usr/bin/env bash
# Întreținere DB eMAG:
# - reachability + versiune alembic
# - asigurare partiții pentru luna următoare (create dacă lipsesc)
# - verificare partiții (există + atașate la părinți)
# - indexuri unice pe MVs
# - test REFRESH MATERIALIZED VIEW CONCURRENTLY

set -Eeuo pipefail

###############################################################################
# Config
###############################################################################
PGUSER="${PGUSER:-appuser}"
PGDATABASE="${PGDATABASE:-appdb}"
PGSCHEMA="${PGSCHEMA:-app}"
SERVICE_DB="${SERVICE_DB:-db}"
SERVICE_APP="${SERVICE_APP:-app}"
TZ_REGION="${TZ_REGION:-Europe/Bucharest}"

###############################################################################
# Utilitare
###############################################################################
log(){ printf '[%s] %s\n' "$(date '+%F %T %Z')" "$*"; }

# Alege docker compose
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  log "ERROR: nici «docker compose», nici «docker-compose» nu sunt în PATH."
  exit 1
fi

# psql în containerul DB: -X (nu încărca ~/.psqlrc), -A/-t (unaligned, tuples only), -F '|' (separator stabil)
psql_db(){
  $COMPOSE exec -T "$SERVICE_DB" \
    psql -X -A -t -F '|' -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDATABASE" "$@"
}

# (opțional) heads din aplicație
alembic_heads(){
  $COMPOSE exec -T "$SERVICE_APP" alembic heads -v 2>/dev/null || true
}

fail=0

###############################################################################
# 0) Reachability + Alembic
###############################################################################
log "health: DB reachability"
psql_db -c "SELECT 'ok:db'" | sed -n '1p' || { log "FAIL: DB not reachable"; exit 1; }

ALEMBIC_DB="$(psql_db -c "SELECT version_num FROM ${PGSCHEMA}.alembic_version" || echo 'n/a')"
log "alembic (DB): ${ALEMBIC_DB:-n/a}"

HEADS="$(alembic_heads | sed -n 's/^Rev: \([^ ]*\).*/\1/p' | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"
if [[ -n "$HEADS" ]]; then
  log "alembic (app): $HEADS"
else
  log "INFO: nu pot obține «alembic heads» din serviciul app (opțional)."
fi

###############################################################################
# 1) Asigură partițiile pentru luna următoare (creează dacă lipsesc)
###############################################################################
log "health: next-month partitions (ensure & check)"

# Creează părțile pentru luna următoare, DST-aware pe Europe/Bucharest
psql_db <<SQL >/dev/null
DO \$\$
DECLARE
  nm date := (date_trunc('month', (now() AT TIME ZONE '${TZ_REGION}')) + interval '1 month')::date;
  nx date := (date_trunc('month', (now() AT TIME ZONE '${TZ_REGION}')) + interval '2 months')::date;
  y  int := extract(year  from nm);
  m  int := extract(month from nm);
  y2 int := extract(year  from nx);
  m2 int := extract(month from nx);

  p_start timestamptz := make_timestamptz(y,  m,  1, 0,0,0, '${TZ_REGION}');
  p_end   timestamptz := make_timestamptz(y2, m2, 1, 0,0,0, '${TZ_REGION}');

  p_name text := format('p_y%sm%02s', y, m);
  s_name text := format('s_y%sm%02s', y, m);
BEGIN
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS ${PGSCHEMA}.%I PARTITION OF ${PGSCHEMA}.emag_offer_prices_hist FOR VALUES FROM (%L) TO (%L)',
    p_name, p_start, p_end
  );
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS ${PGSCHEMA}.%I PARTITION OF ${PGSCHEMA}.emag_offer_stock_hist  FOR VALUES FROM (%L) TO (%L)',
    s_name, p_start, p_end
  );
END
\$\$;
SQL

# Afișează ce e atașat sub părinți (util când DEBUG=1)
if [[ "${DEBUG:-0}" != "0" ]]; then
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_prices_hist:"
  psql_db -c "
    SELECT '  - '||c.relname
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='${PGSCHEMA}' AND p.relname='emag_offer_prices_hist'
    ORDER BY c.relname;" | sed '/^$/d'
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_stock_hist:"
  psql_db -c "
    SELECT '  - '||c.relname
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='${PGSCHEMA}' AND p.relname='emag_offer_stock_hist'
    ORDER BY c.relname;" | sed '/^$/d'
fi

# Verificare ca în db-health.sh
row="$(
  psql_db <<'SQL'
WITH base AS (
  SELECT (date_trunc('month', now()) + interval '1 month')::date AS d
), names AS (
  SELECT
    to_char(d, '"p_y"YYYY"m"MM') AS p_name,
    to_char(d, '"s_y"YYYY"m"MM') AS s_name
  FROM base
)
SELECT
  n.p_name,
  (to_regclass('app.'||n.p_name) IS NOT NULL),
  EXISTS (
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='app' AND p.relname='emag_offer_prices_hist' AND c.relname=n.p_name
  ),
  n.s_name,
  (to_regclass('app.'||n.s_name) IS NOT NULL),
  EXISTS (
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='app' AND p.relname='emag_offer_stock_hist' AND c.relname=n.s_name
  )
FROM names n;
SQL
)"
IFS='|' read -r p_name price_exists price_attached s_name stock_exists stock_attached <<<"$row"

if [[ "${DEBUG:-0}" != "0" ]]; then
  log "DEBUG: expected price part: $p_name"
  log "DEBUG: expected stock  part: $s_name"
fi

if [[ "$price_exists" == "t" ]];   then log "OK  : price partition exists ($p_name)"; else log "FAIL: price partition missing"; ((fail++)); fi
if [[ "$price_attached" == "t" ]]; then log "OK  : price partition attached";         else log "FAIL: price partition NOT attached"; ((fail++)); fi
if [[ "$stock_exists" == "t" ]];   then log "OK  : stock partition exists ($s_name)"; else log "FAIL: stock partition missing"; ((fail++)); fi
if [[ "$stock_attached" == "t" ]]; then log "OK  : stock partition attached";         else log "FAIL: stock partition NOT attached"; ((fail++)); fi

###############################################################################
# 2) MV unique index pe (offer_id)
###############################################################################
log "health: MV unique indexes"

check_mv_unique(){
  local mv="$1"
  local ok
  ok="$(psql_db <<SQL
SELECT EXISTS (
  SELECT 1
  FROM pg_index x
  JOIN pg_class t  ON t.oid=x.indrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname='${PGSCHEMA}' AND t.relname='${mv}'
    AND x.indisunique
    AND (
      SELECT string_agg(a.attname, ', ' ORDER BY a.attnum)
      FROM unnest(x.indkey) WITH ORDINALITY AS k(attnum, ord)
      JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
    ) = 'offer_id'
);
SQL
)"
  if [[ "$ok" == "t" ]]; then
    log "OK  : ${mv} has unique index on (offer_id)"
  else
    log "FAIL: ${mv} missing unique index (offer_id)"
    ((fail++))
  fi
}

check_mv_unique "mv_emag_stock_summary"
check_mv_unique "mv_emag_best_offer"

###############################################################################
# 3) Test REFRESH CONCURRENTLY
###############################################################################
log "health: test REFRESH CONCURRENTLY (lock_timeout=3s, statement_timeout=2min)"

refresh_mv_test(){
  local mv="$1"
  if psql_db -c "SET lock_timeout='3s'; SET statement_timeout='2min'; REFRESH MATERIALIZED VIEW CONCURRENTLY ${PGSCHEMA}.${mv};" >/dev/null; then
    log "OK  : refresh concurrently ${mv}"
  else
    log "FAIL: refresh concurrently ${mv}"
    ((fail++))
  fi
}
refresh_mv_test "mv_emag_stock_summary"
refresh_mv_test "mv_emag_best_offer"

###############################################################################
# Rezultat final
###############################################################################
if (( fail > 0 )); then
  log "HEALTH: PROBLEME (exit 1)"
  exit 1
else
  log "HEALTH: OK"
fi
