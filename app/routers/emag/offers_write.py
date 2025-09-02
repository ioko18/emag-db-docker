# app/routers/emag/offers_write.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Header
from .deps import emag_client_dependency
from .schemas import ProductOfferSaveIn, OfferStockUpdateIn
from .utils import call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/product_offer/save")
async def product_offer_save(
    payload: ProductOfferSaveIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(client.product_offer_save, payload.model_dump(), idempotency_key=idem)

@router.post("/offer/stock-update")
async def offer_stock_update(
    payload: OfferStockUpdateIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(
        client.offer_stock_update,
        item_id=payload.id,
        warehouse_id=payload.warehouse_id,
        value=payload.value,
        idempotency_key=idem,
    )
