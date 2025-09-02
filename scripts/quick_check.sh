# scripts/quick_check.sh
#!/usr/bin/env bash
set -euo pipefail

log() { printf '[QC] %s\n' "$*"; }

log "Build & (re)start..."
docker compose build app >/dev/null
docker compose up -d --force-recreate >/dev/null
docker compose ps

log "DB health..."
scripts/db-health.sh

log "SQL + API smoke..."
scripts/smoke.sh

log "Seed demo offer (idempotent, pe zi)..."
scripts/seed_demo_offer.sh

log "Refresh MVs..."
scripts/refresh_mviews.sh

log "Checks pe rezultate..."
best=$(docker compose exec -T db psql -U appuser -d appdb -t -A -c \
  "SELECT count(*) FROM app.mv_emag_best_offer WHERE offer_id=900000001;")
stockmv=$(docker compose exec -T db psql -U appuser -d appdb -t -A -c \
  "SELECT count(*) FROM app.mv_emag_stock_summary WHERE offer_id=900000001;")
prices_future=$(docker compose exec -T db psql -U appuser -d appdb -t -A -c \
  "SELECT count(*) FROM app.emag_offer_prices_hist
   WHERE recorded_at::date > (CURRENT_DATE + INTERVAL '1 day')::date;")
stock_future=$(docker compose exec -T db psql -U appuser -d appdb -t -A -c \
  "SELECT count(*) FROM app.emag_offer_stock_hist
   WHERE recorded_at::date > (CURRENT_DATE + INTERVAL '1 day')::date;")

if [[ "$best" != "1" ]]; then
  echo "[QC] FAIL: mv_emag_best_offer ar trebui să aibă 1 rând pt oferta demo (are $best)"; exit 1
fi
if [[ "$stockmv" != "1" ]]; then
  echo "[QC] FAIL: mv_emag_stock_summary ar trebui să aibă 1 rând pt oferta demo (are $stockmv)"; exit 1
fi
if [[ "$prices_future" != "0" ]]; then
  echo "[QC] FAIL: prices_hist are rânduri > mâine ($prices_future)"; exit 1
fi
if [[ "$stock_future" != "0" ]]; then
  echo "[QC] FAIL: stock_hist are rânduri > mâine ($stock_future)"; exit 1
fi

log "OK — everything looks good ✅"
