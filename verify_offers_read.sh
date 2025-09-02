#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8010"
ACC="fbe"
CTY="ro"

pass() { echo "✔ $*"; }
fail() { echo "✘ $*"; exit 1; }

req() { curl -sS "$@"; }
status() { curl -sS -o /dev/null -w "%{http_code}" "$@"; }

# 0) Health & OpenAPI
[ "$(status "$BASE/health/ready")" = "200" ] || fail "/health/ready nu răspunde 200"
pass "health/ready OK"

PATH_OKAPI=$(req "$BASE/openapi.json" | jq -r '.paths | keys[]' | sort)
echo "$PATH_OKAPI" | grep -qx "/integrations/emag/product_offer/read" || fail "ruta /integrations/emag/product_offer/read lipsește din OpenAPI"
! echo "$PATH_OKAPI" | grep -q "/integrations/emag/integrations/emag/product_offer/read" || fail "dublu-prefix detectat în OpenAPI"
pass "OpenAPI rute OK"

# 1) Semantica SKU/emag_sku în meta (debug)
REQ='{"page":1,"limit":1}'
MAP=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&debug=1" \
      -H 'Content-Type: application/json' -d "$REQ" | jq -r '.meta.sku_semantics | "\(.sku)|\(.emag_sku)"')
[ "$MAP" = "part_number|part_number_key" ] || fail "sku_semantics incorect: $MAP"
pass "sku_semantics OK (sku=part_number, emag_sku=part_number_key)"

# 2) Filtrare după SKU
CNT=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&compact=1&fields=sku" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":50,"sku":"ADS206"}' \
     | jq '.items | map(select(.sku=="ADS206")) | length')
[ "$CNT" = "1" ] || fail "filtrarea după sku nu e strictă (ADS206 găsit de $CNT ori)"
pass "filtrare sku OK"

# 3) Filtrare după part_number_key (eMAG SKU)
CNT=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&compact=1&fields=emag_sku" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":50,"part_number_key":"DL0WVYYBM"}' \
     | jq '.items | map(select(.emag_sku=="DL0WVYYBM")) | length')
[ "$CNT" = "1" ] || fail "filtrarea după part_number_key nu e strictă"
pass "filtrare part_number_key OK"

# 4) Compact=0: arată raw keys (sku null, part_number prezent)
RAW=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&compact=0&fields=sku,part_number,part_number_key" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}' \
     | jq -r '.items[0] | (.sku|tostring)+ "|" + .part_number + "|" + .part_number_key')
[[ "$RAW" =~ ^null\|.+\|.+$ ]] || fail "non-compact nu păstrează cheile raw (obținut: $RAW)"
pass "compact=0 OK (chei raw vizibile)"

# 5) Sortare asc/desc deterministă
ASC=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&fields=sku&sort=sku" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":10}' | jq -r '.items[].sku')
echo "$ASC" | sort -c 2>/dev/null || fail "lista nu e sortată ascendent după sku"
DESC=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&fields=sku&sort=-sku" \
      -H 'Content-Type: application/json' -d '{"page":1,"limit":10}' | jq -r '.items[].sku')
echo "$DESC" | sort -r -c 2>/dev/null || fail "lista nu e sortată descendent după sku"
pass "sort asc/desc OK"

# 6) Export CSV: header + content-type + dispoziție fișier
TMPH=$(mktemp)
CSV=$(curl -sS -D "$TMPH" -X POST \
      "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&format=csv&filename=offers.csv&compact=1&fields=id,sku,emag_sku,name,sale_price,stock_total" \
      -H 'Content-Type: application/json' -d '{"page":1,"limit":5}')
head -n1 <<< "$CSV" | grep -qx "id,sku,emag_sku,name,sale_price,stock_total" || fail "CSV header greșit"
grep -qi '^content-type: text/csv' "$TMPH" || fail "CSV content-type lipsă/greșit"
grep -qi 'content-disposition: attachment; filename="offers.csv"' "$TMPH" || fail "CSV Content-Disposition greșit"
rm -f "$TMPH"
pass "CSV OK (header + headers HTTP)"

# 7) Export NDJSON: număr linii corect
NDJ_LINES=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&format=ndjson&compact=1&fields=id,sku,name" \
           -H 'Content-Type: application/json' -d '{"page":1,"limit":3}' | wc -l | tr -d ' ')
[ "$NDJ_LINES" = "3" ] || fail "NDJSON are $NDJ_LINES linii, așteptat 3"
pass "NDJSON OK"

# 8) items_only returnează doar cheia items
KEYS=$(req -X POST "$BASE/integrations/emag/product_offer/read?items_only=1&account=$ACC&country=$CTY&compact=1&fields=id,sku" \
      -H 'Content-Type: application/json' -d '{"page":1,"limit":2}' | jq -r 'keys|join(",")')
[ "$KEYS" = "items" ] || fail "items_only nu a ascuns meta/total (chei: $KEYS)"
pass "items_only OK"

# 9) Validări de input (așteptăm 422)
SC=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
     "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&fields=id,sku,NU_EXISTA" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}')
[ "$SC" = "422" ] || fail "fields invalid ar fi trebuit să dea 422, a dat $SC"
SC=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
     "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&sort=pret" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}')
[ "$SC" = "422" ] || fail "sort invalid ar fi trebuit să dea 422, a dat $SC"
SC=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
     "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&format=xml" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}')
[ "$SC" = "422" ] || fail "format invalid ar fi trebuit să dea 422, a dat $SC"
pass "validări input OK (422)"

echo
pass "Toate testele au trecut 🎉"
