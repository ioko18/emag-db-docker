#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8001
