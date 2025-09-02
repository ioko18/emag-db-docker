# scripts/db-health.sh
#!/usr/bin/env bash
# Verificări sănătate DB eMAG:
# - reachability + versiune alembic
# - partițiile pentru luna următoare (există + atașate la părinți)
# - indexurile unice pe MVs
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
  log "alembic (app heads): $HEADS"
else
  log "INFO: nu pot obține «alembic heads» din serviciul app (opțional)."
fi

###############################################################################
# 1) Partițiile pentru luna următoare
###############################################################################
log "health: next-month partitions"

# Query robust: folosim heredoc *citat* și variabilă psql :schema
row="$(
  psql_db -v "schema=${PGSCHEMA}" <<'SQL'
WITH d AS (
  SELECT (date_trunc('month', now()) + interval '1 month')::date AS d
), names AS (
  SELECT
    to_char(d, '"p_y"YYYY"m"MM') AS p_name,
    to_char(d, '"s_y"YYYY"m"MM') AS s_name
  FROM d
)
SELECT
  n.p_name,
  EXISTS (  -- price_exists
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.p_name
  ),
  EXISTS (  -- price_attached
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c  ON c.oid=i.inhrelid
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    JOIN pg_class p  ON p.oid=i.inhparent
    JOIN pg_namespace nsp ON nsp.oid=p.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.p_name
      AND nsp.nspname=:'schema' AND p.relname='emag_offer_prices_hist'
  ),
  n.s_name,
  EXISTS (  -- stock_exists
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.s_name
  ),
  EXISTS (  -- stock_attached
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c  ON c.oid=i.inhrelid
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    JOIN pg_class p  ON p.oid=i.inhparent
    JOIN pg_namespace nsp ON nsp.oid=p.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.s_name
      AND nsp.nspname=:'schema' AND p.relname='emag_offer_stock_hist'
  )
FROM names n;
SQL
)"

# row are 6 câmpuri separate prin |
IFS='|' read -r p_name price_exists price_attached s_name stock_exists stock_attached <<<"$row"

if [[ "${DEBUG:-0}" != "0" ]]; then
  log "DEBUG: expected price part: $p_name"
  log "DEBUG: expected stock  part: $s_name"
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_prices_hist:"
  psql_db -v "schema=${PGSCHEMA}" <<'SQL' | sed '/^$/d'
SELECT '  - '||c.relname
FROM pg_inherits i
JOIN pg_class c ON c.oid=i.inhrelid
JOIN pg_class p ON p.oid=i.inhparent
JOIN pg_namespace np ON np.oid=p.relnamespace
WHERE np.nspname=:'schema' AND p.relname='emag_offer_prices_hist'
ORDER BY c.relname;
SQL
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_stock_hist:"
  psql_db -v "schema=${PGSCHEMA}" <<'SQL' | sed '/^$/d'
SELECT '  - '||c.relname
FROM pg_inherits i
JOIN pg_class c ON c.oid=i.inhrelid
JOIN pg_class p ON p.oid=i.inhparent
JOIN pg_namespace np ON np.oid=p.relnamespace
WHERE np.nspname=:'schema' AND p.relname='emag_offer_stock_hist'
ORDER BY c.relname;
SQL
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
  ok="$(psql_db -v "schema=${PGSCHEMA}" <<'SQL'
SELECT EXISTS (
  SELECT 1
  FROM pg_index x
  JOIN pg_class t  ON t.oid=x.indrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname=:'schema' AND t.relname=: 'mv'
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
# psql nu știe variabile din shell în heredoc-ul citat; folosim -c aici simplu:
check_mv_unique(){
  local mv="$1"
  local ok
  ok="$(psql_db -c "
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
);")"
  [[ "$ok" == "t" ]] && log "OK  : ${mv} has unique index on (offer_id)" || { log "FAIL: ${mv} missing unique index (offer_id)"; ((fail++)); }
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
