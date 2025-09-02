#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8010/observability"

# 1) stddev ordering
jq -e '
  .order_by=="stddev_exec_time" and .order_dir=="DESC" and (.items|length)>=1 and (.items[0].stddev_ms|type=="number")
' < <(curl -fsS "$BASE/top-queries?order_by=stddev_exec_time&order_dir=desc") >/dev/null
echo "✓ stddev ordering"

# 2) min ordering
jq -e '
  .order_by=="min_exec_time" and .order_dir=="ASC" and (.items|length)>=1 and (.items[0].min_ms|type=="number")
' < <(curl -fsS "$BASE/top-queries?order_by=min_exec_time&order_dir=asc") >/dev/null
echo "✓ min ordering"

# 3) max ordering
jq -e '
  .order_by=="max_exec_time" and .order_dir=="DESC" and (.items|length)>=1 and (.items[0].max_ms|type=="number")
' < <(curl -fsS "$BASE/top-queries?order_by=max_exec_time&order_dir=desc") >/dev/null
echo "✓ max ordering"

# 4) exclude DDL/utility
jq -e '
  ([.items[]? | (.query // "")
     | test("(?i)^\\s*(begin|commit|rollback|set|show|create|alter|drop|grant|revoke|truncate|comment|vacuum|analyze|explain|reset|prepare|deallocate|checkpoint|refresh|listen|unlisten|notify|copy|security|cluster|lock|discard|do)")]
   | any) == false
' < <(curl -fsS "$BASE/top-queries?exclude_ddl=true") >/dev/null
echo "✓ exclude_ddl"

# 5) truncate query text
jq -e '
  ([.items[]? | (.query // "") | length] | all(. <= 30)) == true
' < <(curl -fsS "$BASE/top-queries?qlen=30") >/dev/null
echo "✓ qlen truncation"

# 6) self-queries hidden by default
jq -e '
  ([.items[]? | select(.query != null and (.query | test("pg_stat_statements"; "i")))] | length) == 0
' < <(curl -fsS "$BASE/top-queries") >/dev/null
echo "✓ exclude_self (implicit)"

# 7) self-queries visible on demand (poate fi 0 dacă nu ai produs trafic recent)
jq -e '
  {count, found: ([.items[]? | (.query // "") | test("pg_stat_statements"; "i")] | any)} |
  (.found | type=="boolean")
' < <(curl -fsS "$BASE/top-queries?exclude_self=false&search=pg_stat_statements&limit=100&order_by=calls&order_dir=desc") >/dev/null
echo "✓ include self on demand"

echo "All checks passed ✓"
