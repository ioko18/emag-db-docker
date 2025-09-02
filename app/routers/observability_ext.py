from __future__ import annotations

import os
import sys
import time
import platform
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/observability/v2", tags=["observability"])

APP_STARTED_TS = int(os.getenv("APP_STARTED_TS", str(int(time.time()))))
APP_VERSION = os.getenv("APP_VERSION", "unknown")

@router.get("/summary")
def obs_summary() -> Dict[str, Any]:
    return {
        "app_version": APP_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pid": os.getpid(),
        "started_at": APP_STARTED_TS,
        "uptime_s": time.time() - APP_STARTED_TS,
        "env": {
            "root_path": os.getenv("ROOT_PATH", ""),
            "log_level": os.getenv("LOG_LEVEL", ""),
        }
    }

@router.get("/health")
def obs_health() -> Dict[str, Any]:
    return {"ok": True, "ts": int(time.time())}

@router.get("/hints")
def obs_hints() -> Dict[str, Any]:
    """
    Endpoint „static” cu sugestii de configurare (util cînd rulezi în containere).
    """
    hints = []
    if not os.getenv("TRUSTED_HOSTS"):
        hints.append("Setează TRUSTED_HOSTS pentru a restricționa Host header.")
    if not os.getenv("CORS_ORIGINS"):
        hints.append("Setează CORS_ORIGINS dacă apelezi API din browser.")
    if os.getenv("DISABLE_DOCS","").lower() in {"1","true","yes"}:
        hints.append("Docs sunt dezactivate (DISABLE_DOCS=1).")
    return {"hints": hints}
