# app/routers/emag/meta.py
from __future__ import annotations
from typing import Any, TYPE_CHECKING

from fastapi import APIRouter, Depends
from .deps import emag_client_dependency

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.get("/health")
async def health(client: "EmagClient" = Depends(emag_client_dependency)) -> dict[str, Any]:
    return {"ok": True, "account": client.cfg.account, "country": client.cfg.country, "base_url": client.cfg.base_url}

@router.get("/meta")
async def meta(client: "EmagClient" = Depends(emag_client_dependency)) -> dict[str, Any]:
    return {
        "account": client.cfg.account,
        "country": client.cfg.country,
        "base_url": client.cfg.base_url,
        "timeouts": {"connect": client.cfg.connect_timeout, "read": client.cfg.read_timeout},
    }
