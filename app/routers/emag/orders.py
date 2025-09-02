# app/routers/emag/orders.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Header
from .deps import emag_client_dependency
from .schemas import OrdersReadIn, OrdersAckIn, OrderStatus
from .utils import call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/orders/read")
async def orders_read(
    payload: OrdersReadIn,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    status_int = int(payload.status) if isinstance(payload.status, OrderStatus) else payload.status
    return await call_emag(client.order_read, page=payload.page, limit=payload.limit, status=status_int)

@router.post("/orders/ack")
async def orders_ack(
    payload: OrdersAckIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(client.order_ack, payload.order_ids, idempotency_key=idem)
