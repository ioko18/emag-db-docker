# scripts/quick_check.sh
#!/usr/bin/env bash
set -Eeuo pipefail

# Lucrăm din rădăcina repo-ului (indiferent de unde rulezi scriptul)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

die() { echo "❌ $*" >&2; exit 1; }

# La orice eroare, arată ultimii ~200 de loguri din app și db
trap 'echo "[QC] Last logs (tail) ↓"; docker compose logs --no-color --tail=200 app db || true' ERR

echo "[QC] Build app image..."
docker compose build app

echo "[QC] (Re)start services..."
docker compose up -d --force-recreate db app
docker compose ps

echo "[QC] Wait for DB to be healthy..."
DB_CID="$(docker compose ps -q db)"
for i in {1..60}; do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CID" 2>/dev/null || echo unknown)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done
status="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CID" 2>/dev/null || echo unknown)"
if [[ "$status" != "healthy" ]]; then
  # fallback de diagnostic: pg_isready din container
  docker compose exec -T db pg_isready -h localhost -p 5432 || true
  die "DB did not become healthy in time (status: $status)"
fi

echo "[QC] Run migrations (alembic upgrade head)..."
docker compose exec -T app bash -lc 'alembic -c /app/alembic.ini upgrade head'

echo "[QC] Prime materialized views..."
bash scripts/refresh_mviews.sh

echo "[QC] Seed demo offer..."
bash scripts/seed_demo_offer.sh

echo "[QC] DB health..."
bash scripts/db-health.sh

echo "[QC] SQL + API smoke..."
bash scripts/smoke.sh

echo "[QC] OK — everything looks good ✅"
