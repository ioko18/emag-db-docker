# app/routers/emag/awb.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, Path, Query
from .deps import emag_client_dependency
from .schemas import AwbSaveIn, AwbFormat
from .utils import call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/awb/save")
async def awb_save(
    payload: AwbSaveIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(
        client.awb_save,
        order_id=payload.order_id,
        courier=payload.courier,
        service=payload.service,
        cod=payload.cod,
        idempotency_key=idem,
    )

@router.get("/awb/{awb_id}")
async def awb_read(
    awb_id: Annotated[int, Path(ge=1, description="AWB ID (>0)")],
    awb_format: Annotated[AwbFormat, Query(alias="format", description="Format AWB (PDF/ZPL)")] = AwbFormat.PDF,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(client.awb_read, awb_id, format_=awb_format.value)
