cat > scripts/quick_check.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail

echo "[QC] Build & (re)start..."
docker compose build app
docker compose up -d --force-recreate
docker compose ps

echo "[QC] Wait for DB to be healthy..."
for i in {1..60}; do
  if docker compose exec -T db pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[QC] Run migrations (alembic upgrade head)..."
docker compose exec -T app bash -lc "alembic upgrade head"

echo "[QC] Prime materialized views..."
# Dacă scriptul tău face REFRESH (chiar și CONCURRENTLY), e ok;
# important e să ruleze după migrări, înainte de health.
scripts/refresh_mviews.sh || true

echo "[QC] Seed demo offer..."
scripts/seed_demo_offer.sh

echo "[QC] DB health..."
scripts/db-health.sh

echo "[QC] SQL + API smoke..."
scripts/smoke.sh

echo "[QC] OK — everything looks good ✅"
BASH
chmod +x scripts/quick_check.sh
