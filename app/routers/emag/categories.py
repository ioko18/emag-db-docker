# app/routers/emag/categories.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from .deps import emag_client_dependency
from .schemas import CategoriesIn
from .utils import LANG_BY_COUNTRY, call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/categories/read")
async def categories_read(
    payload: CategoriesIn,
    compact: Annotated[bool, Query(alias="compact", description="Returnează schema compactă {total,items}")] = False,
    fields: Annotated[Optional[str], Query(description="Listează câmpurile din items (ex: id,name,parent_id,leaf)")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    lang = payload.language or LANG_BY_COUNTRY.get(client.cfg.country, None)
    resp = await call_emag(client.category_read, page=payload.page, limit=payload.limit, language=lang)

    if not compact:
        return resp

    if isinstance(resp, list):
        data = resp
    elif isinstance(resp, dict):
        data = (
            resp.get("data")
            or resp.get("results")
            or resp.get("items")
            or (resp.get("payload") or {}).get("data")
            or (resp.get("response") or {}).get("data")
            or resp.get("categories")
            or []
        )
    else:
        data = []
    if not isinstance(data, list):
        data = []

    def _pick(d: dict, *keys):
        for k in keys:
            if k in d:
                return d[k]
        return None

    norm: list[dict[str, Any]] = []
    for it in data[: payload.limit]:
        item = {
            "id": _pick(it, "id", "category_id", "categoryId"),
            "name": _pick(it, "name", "label", "title"),
            "parent_id": _pick(it, "parent_id", "parentId", "parent_category_id", "parentCategoryId"),
            "leaf": _pick(it, "is_leaf", "leaf", "isLeaf"),
        }
        norm.append(item)

    if fields:
        allowed = {f.strip() for f in fields.split(",") if f.strip()}
        norm = [{k: v for k, v in it.items() if k in allowed} for it in norm]

    return {"total": len(data), "items": norm}
