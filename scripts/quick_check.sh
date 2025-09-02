#!/usr/bin/env bash
set -euo pipefail

echo "[QC] Build & (re)start..."
docker compose build app
docker compose up -d --force-recreate
docker compose ps

echo "[QC] Seed demo offer (idempotent, pre-health)..."
scripts/seed_demo_offer.sh

echo "[QC] Refresh MVs..."
scripts/refresh_mviews.sh

echo "[QC] DB health..."
scripts/db-health.sh

echo "[QC] SQL + API smoke..."
scripts/smoke.sh

echo "[QC] Checks pe rezultate..."
echo "[QC] OK — everything looks good ✅"
