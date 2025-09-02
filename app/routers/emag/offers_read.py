# app/routers/emag/offers_read.py
from __future__ import annotations

import os
import csv
import io
import json
from typing import Any, Dict, List, Optional, Iterable, Tuple

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.routers.emag.deps import emag_client_dependency
from app.integrations.emag_sdk import EmagClient, EmagApiError

# IMPORTANT: prefixul /integrations/emag este aplicat în app/routers/emag/__init__.py
router = APIRouter(tags=["emag offers"])

# ==== ENV ====
DEFAULT_LIMIT = int(os.getenv("EMAG_OFFERS_DEFAULT_LIMIT", "25"))
MAX_LIMIT = int(os.getenv("EMAG_OFFERS_MAX_LIMIT", "50"))
DEFAULT_COMPACT = (os.getenv("EMAG_OFFERS_DEFAULT_COMPACT", "1").strip().lower()
                   not in {"0", "false", "no"})
DEFAULT_FIELDS_STR = os.getenv(
    "EMAG_OFFERS_DEFAULT_FIELDS",
    "id,sku,name,sale_price,stock_total",
)
RETURN_META_BY_DEFAULT = (os.getenv("EMAG_OFFERS_RETURN_META", "0").strip().lower()
                          not in {"0", "false", "no"})

# STRICT FILTER & TOTALS MODE
STRICT_FILTER = (os.getenv("EMAG_OFFERS_STRICT_FILTER", "").strip().lower()
                 not in {"", "0", "false", "no"})
TOTAL_MODE = os.getenv("EMAG_OFFERS_TOTAL_MODE", "upstream").strip().lower()
if TOTAL_MODE not in {"upstream", "filtered", "both"}:
    TOTAL_MODE = "upstream"

# câmpuri permise (inclusiv proiecții „flatten”)
ALLOWED_FIELDS: set[str] = {
    "id", "sku", "emag_sku", "name", "product_id", "category_id",
    "status", "status_text",
    "sale_price", "min_sale_price", "max_sale_price", "best_offer_sale_price",
    "currency", "vat_id", "handling_time",
    "ean", "ean_list", "part_number_key", "part_number",
    "general_stock", "estimated_stock", "stock_total",
    "warehouses", "stock_debug",
    "brand", "brand_name",
    "supply_lead_time",
    "validation_status_value", "validation_status_text",
    "images_count",
}
ALLOWED_SORT: set[str] = {"id", "sku", "name", "sale_price", "stock_total"}


def _safe_default_fields() -> str:
    req = [f.strip() for f in DEFAULT_FIELDS_STR.split(",") if f.strip()]
    valid = [f for f in req if f in ALLOWED_FIELDS]
    if not valid:
        valid = ["id", "sku", "name", "sale_price", "stock_total"]
    return ",".join(valid)


DEFAULT_FIELDS = _safe_default_fields()


def _project_item(item: Dict[str, Any], fields: Optional[List[str]]) -> Dict[str, Any]:
    if not fields:
        return item
    return {k: item.get(k) for k in fields}


def _flatten(it: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact=1: normalizează câteva câmpuri comune.
    - sku              := part_number (seller SKU)
    - emag_sku         := part_number_key (eMAG SKU)
    - ean              := primul din listă (dacă e listă) sau stringul direct
    - ean_list         := lista completă (dacă există)
    - handling_time    := handling_time[0].value (dacă există)
    - supply_lead_time := offer_details.supply_lead_time
    - validation_status_{value,text} := din validation_status[0]
    - images_count     := len(images)
    - stock_total      := fallback din stock[0].value / general_stock / estimated_stock dacă lipsește
    """
    out = dict(it)

    # SKU semantici
    out["sku"] = it.get("part_number")           # seller SKU
    out["emag_sku"] = it.get("part_number_key")  # eMAG SKU

    # EAN
    ean_val = None
    ean_list = it.get("ean")
    if isinstance(ean_list, list):
        out["ean_list"] = ean_list
        if ean_list:
            ean_val = ean_list[0]
    elif isinstance(ean_list, str):
        ean_val = ean_list
    if ean_val is not None:
        out["ean"] = ean_val

    # handling_time
    ht = it.get("handling_time")
    if isinstance(ht, list) and ht and isinstance(ht[0], dict):
        out["handling_time"] = ht[0].get("value")

    # supply_lead_time
    od = it.get("offer_details") or {}
    if isinstance(od, dict):
        out["supply_lead_time"] = od.get("supply_lead_time")

    # validation_status
    vs = it.get("validation_status")
    if isinstance(vs, list) and vs and isinstance(vs[0], dict):
        out["validation_status_value"] = vs[0].get("value")
        out["validation_status_text"] = vs[0].get("description")

    # images_count
    imgs = it.get("images")
    if isinstance(imgs, list):
        out["images_count"] = len(imgs)

    # stock_total fallback
    if out.get("stock_total") is None:
        st_list = it.get("stock")
        st_val = None
        if isinstance(st_list, list) and st_list and isinstance(st_list[0], dict):
            st_val = st_list[0].get("value")
        if st_val is None:
            st_val = it.get("general_stock")
        if st_val is None:
            st_val = it.get("estimated_stock")
        out["stock_total"] = st_val

    return out


def _iter_ndjson(items: Iterable[Dict[str, Any]]) -> Iterable[bytes]:
    for row in items:
        yield (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")


def _csv_response(fields: List[str], rows: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    # folosim lineterminator="\n" ca să evităm CRLF și surprize în testele cu `grep -x`
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        w.writerow([r.get(col) for col in fields])
    data = buf.getvalue().encode("utf-8")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(data), media_type="text/csv; charset=utf-8", headers=headers)



def _strict_match(
    flat: Dict[str, Any],
    sku: Optional[str],
    part_number_key: Optional[str],
    ean: Optional[str],
) -> bool:
    """AND pe toate filtrele prezente."""
    if sku is not None and flat.get("sku") != sku:
        return False
    if part_number_key is not None and flat.get("emag_sku") != part_number_key:
        return False
    if ean is not None:
        ean_ok = False
        if flat.get("ean") == ean:
            ean_ok = True
        else:
            lst = flat.get("ean_list") or []
            if isinstance(lst, list) and ean in lst:
                ean_ok = True
        if not ean_ok:
            return False
    return True


# ---------- modele I/O (fără validatori pydantic – validăm explicit în endpoint) ----------
class OffersReadQuery(BaseModel):
    account: str = Field(..., description="Cont configurat (ex: main, fbe)")
    country: str = Field(..., description="Țara eMAG (ro|bg|hu)")
    compact: bool = Field(default=DEFAULT_COMPACT, description="Proiectează câmpurile (flatten) și folosește `fields`.")
    items_only: bool = Field(default=False, description="Dacă e 1, întoarce doar `items`.")
    fields: Optional[str] = Field(default=DEFAULT_FIELDS, description="Listă separată prin virgulă (ordinea e păstrată la CSV).")
    sort: Optional[str] = Field(default=None, description="Ex: name, -sale_price, stock_total")
    # export
    format: Optional[str] = Field(default=None, description="Format export: json|csv|ndjson")
    filename: Optional[str] = Field(default=None, description="Numele fișierului la export (ex: offers.csv)")


class OffersReadBody(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    status: Optional[int] = None
    # IMPORTANT: sku == part_number (seller SKU)
    sku: Optional[str] = Field(None, description="Filtrează după seller SKU (eMAG `part_number`).")
    # Compatibilitate: acceptăm și `part_number` (deprecated) => mapăm la `sku` dacă e folosit.
    part_number: Optional[str] = Field(
        None,
        description="DEPRECATED alias pentru `sku` (seller SKU / eMAG `part_number`). Folosește `sku`.",
    )
    ean: Optional[str] = None
    # eMAG SKU (alias intern): part_number_key
    part_number_key: Optional[str] = Field(None, description="Filtru după eMAG SKU (`part_number_key`).")
    extra: Optional[Dict[str, Any]] = None


# ---------- validări explicite (independente de versiunea Pydantic) ----------
def _parse_fields(fields_str: Optional[str]) -> Optional[List[str]]:
    if not fields_str:
        return None
    req = [p.strip() for p in fields_str.split(",") if p.strip()]
    invalid = [f for f in req if f not in ALLOWED_FIELDS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown field(s): {', '.join(invalid)}. Allowed: {', '.join(sorted(ALLOWED_FIELDS))}",
        )
    return req


def _parse_sort(sort_expr: Optional[str]) -> Optional[str]:
    if not sort_expr:
        return None
    desc = sort_expr.startswith("-")
    key = sort_expr[1:] if desc else sort_expr
    if key not in ALLOWED_SORT:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort: {sort_expr!r}. Allowed: {', '.join(sorted(ALLOWED_SORT))} (prefix '-' for desc).",
        )
    return sort_expr


def _parse_format(fmt: Optional[str]) -> Optional[str]:
    if not fmt:
        return None
    fmt2 = fmt.lower()
    if fmt2 not in {"json", "csv", "ndjson"}:
        raise HTTPException(status_code=422, detail="format must be one of: json, csv, ndjson")
    return fmt2


@router.post(
    "/product_offer/read",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "filter_by_sku": {
                            "summary": "Filtrare după seller SKU (part_number)",
                            "value": {"page": 1, "limit": 5, "sku": "ADS206"},
                        },
                        "filter_by_emag_sku": {
                            "summary": "Filtrare după eMAG SKU (part_number_key)",
                            "value": {"page": 1, "limit": 5, "part_number_key": "DL0WVYYBM"},
                        },
                        "export_minimal_csv": {
                            "summary": "Export CSV (câmpuri minimale)",
                            "value": {"page": 1, "limit": 10},
                        },
                    }
                }
            }
        }
    },
)
async def product_offer_read(
    q: OffersReadQuery = Depends(),
    body: OffersReadBody = Body(...),
    client: EmagClient = Depends(emag_client_dependency),
    debug: bool = Query(False, description="Include meta de debug"),
):
    """
    Passthrough + UX local:
    - validare fields/sort/format (422, mesaj clar)
    - filtrare strictă opțională (ENV) înainte de sort+pagina­re
    - sort înainte de paginare (determinist)
    - compact + fields
    - export CSV/NDJSON
    - semantici: `sku` = part_number (seller), `emag_sku` = part_number_key (eMAG)
    """
    # Validări explicite pentru query
    fields_list = _parse_fields(q.fields)
    sort_expr = _parse_sort(q.sort)
    fmt = _parse_format(q.format)

    try:
        # === build payload upstream ===
        payload: Dict[str, Any] = {"page": body.page, "limit": body.limit}
        if body.status is not None:
            payload["status"] = body.status

        # compat: dacă user a trimis `part_number` dar nu `sku`, mapăm la `sku`
        eff_sku = body.sku or body.part_number  # seller SKU
        if eff_sku:
            payload["sku"] = eff_sku  # SDK așteaptă 'sku' (mapat intern la eMAG part_number)

        if body.ean:
            payload["ean"] = body.ean
        if body.part_number_key:
            payload["part_number_key"] = body.part_number_key  # eMAG SKU
        if body.extra:
            payload.update(body.extra)

        # apel SDK
        resp = await client.product_offer_read(
            page=payload["page"],
            limit=payload["limit"],
            status=payload.get("status"),
            sku=payload.get("sku"),
            ean=payload.get("ean"),
            part_number_key=payload.get("part_number_key"),
            extra=body.extra,
        )
    except EmagApiError as e:
        status_code = e.status_code or 502
        detail = {"message": "eMAG API error", "status_code": e.status_code, "details": e.payload}
        raise HTTPException(status_code=status_code if 400 <= status_code < 500 else 502, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"message": "Upstream error", "error": str(e)})

    # Normalizează lista de oferte
    raw_items: List[Dict[str, Any]] = (
        resp.get("data")
        or resp.get("results")
        or resp.get("items")
        or (resp.get("payload", {}) or {}).get("data")
        or (resp.get("response", {}) or {}).get("data")
        or resp.get("offers")
        or []
    )
    if not isinstance(raw_items, list):
        raw_items = []

    # perechi (raw, flat) → sortăm după flat, returnăm raw/flat în funcție de compact
    pairs_all: List[Tuple[Dict[str, Any], Dict[str, Any]]] = [(it, _flatten(it)) for it in raw_items]

    # filtrare strictă locală (dacă e activată din ENV)
    if STRICT_FILTER:
        pairs_use = [
            p for p in pairs_all
            if _strict_match(p[1], eff_sku, body.part_number_key, body.ean)
        ]
    else:
        pairs_use = pairs_all

    # sort (cheie în flat; susține 'sku', etc.)
    if sort_expr:
        desc = sort_expr.startswith("-")
        key = sort_expr[1:] if desc else sort_expr
        def _k(p: Tuple[Dict[str, Any], Dict[str, Any]]):
            v = p[1].get(key)  # ia din flat
            return (v is None, v)
        pairs_use.sort(key=_k, reverse=desc)

    # paginare
    start = (body.page - 1) * body.limit
    end = start + body.limit
    if len(pairs_use) > body.limit:
        sliced_pairs = pairs_use[start:end] if start < len(pairs_use) else []
    else:
        sliced_pairs = pairs_use[: body.limit]

    # alege reprezentarea în funcție de compact
    items: List[Dict[str, Any]] = [fp if q.compact else rp for (rp, fp) in sliced_pairs]

    # proiecție pe fields
    if fields_list:
        items = [_project_item(it, fields_list) for it in items]

    # total upstream și total filtrat (pe lista completă din răspuns)
    upstream_total = resp.get("total")
    if not isinstance(upstream_total, int):
        upstream_total = resp.get("count") or len(raw_items)
    upstream_total = int(upstream_total or 0)
    filtered_total = len(pairs_use)

    # alegerea totalului expus
    if TOTAL_MODE == "filtered":
        total = filtered_total
    else:  # "upstream" sau "both" (compat – total = upstream)
        total = upstream_total

    # === Export? ===
    if fmt in {"csv", "ndjson"}:
        if fmt == "csv":
            cols = fields_list or ["id", "sku", "name", "sale_price", "stock_total"]
            fname = q.filename or "offers.csv"
            return _csv_response(cols, items, fname)
        else:
            headers = {}
            if q.filename:
                headers["Content-Disposition"] = f'attachment; filename="{q.filename}"'
            return StreamingResponse(_iter_ndjson(items), media_type="application/x-ndjson", headers=headers)

    # JSON normal
    out: Dict[str, Any] = {"total": total, "items": items}
    if q.items_only:
        out = {"items": items}

    if debug or RETURN_META_BY_DEFAULT:
        meta: Dict[str, Any] = {
            "page": body.page,
            "requested_limit": body.limit,
            "max_limit": MAX_LIMIT,
            "returned_raw_len": len(raw_items),
            "sliced": len(pairs_use) > body.limit,
            "compact": q.compact,
            "fields": fields_list,
            "sku_semantics": {
                "sku": "part_number",           # seller SKU
                "emag_sku": "part_number_key",  # eMAG SKU
            },
            "strict_filter": STRICT_FILTER,
            "total_mode": TOTAL_MODE,
            "total_upstream": upstream_total,
            "total_filtered": filtered_total,
        }
        out["meta"] = meta

        # opțional: în modul "both", expune ambele totaluri și în root (în plus față de meta)
        if TOTAL_MODE == "both":
            out["total_upstream"] = upstream_total
            out["total_filtered"] = filtered_total

    return JSONResponse(out)
