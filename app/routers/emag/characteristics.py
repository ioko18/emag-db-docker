# app/routers/emag/characteristics.py
from __future__ import annotations
from typing import Dict, List, Optional

from fastapi import APIRouter

from .schemas import (
    CharValidateIn, CharValidateOut, CharValidateOutItem,
    CharSchema
)
from .utils import (
    normalize_ws, infer_schema_from_allowed, match_exact_or_ci,
    match_quantitative, suggest
)

router = APIRouter()

_NUMERIC_SCHEMAS = {"mass", "length", "voltage", "noise"}

def _to_enum_or_none(name: Optional[str]) -> Optional[CharSchema]:
    if not name:
        return None
    try:
        return CharSchema(name)
    except Exception:
        return None

@router.post("/characteristics/validate-map", response_model=CharValidateOut)
async def characteristics_validate_map(payload: CharValidateIn) -> CharValidateOut:
    allowed_map: Dict[int, List[str]] = {a.characteristic_id: a.values for a in payload.allowed}

    results: List[CharValidateOutItem] = []
    for item in payload.items:
        char_id = item.characteristic_id
        value_in = normalize_ws(item.value)
        allowed = allowed_map.get(char_id, [])

        if not allowed:
            results.append(
                CharValidateOutItem(
                    characteristic_id=char_id,
                    input_value=value_in,
                    valid=False,
                    reason="Nu există o listă de valori permise pentru acest characteristic_id.",
                )
            )
            continue

        exact = match_exact_or_ci(value_in, allowed)
        if exact:
            results.append(
                CharValidateOutItem(
                    characteristic_id=char_id,
                    input_value=value_in,
                    valid=True,
                    matched_value=exact,
                    schema_used=item.schema_name,
                )
            )
            continue

        schema_name: Optional[str] = item.schema_name.value if item.schema_name else infer_schema_from_allowed(allowed)
        matched = None
        reason = None

        if schema_name in _NUMERIC_SCHEMAS:
            matched, reason = match_quantitative(value_in, allowed, schema_name)

        if matched:
            results.append(
                CharValidateOutItem(
                    characteristic_id=char_id,
                    input_value=value_in,
                    valid=True,
                    matched_value=matched,
                    schema_used=_to_enum_or_none(schema_name),
                )
            )
            continue

        suggestions = suggest(value_in, allowed, n=5) if allowed else None
        results.append(
            CharValidateOutItem(
                characteristic_id=char_id,
                input_value=value_in,
                valid=False,
                suggestions=suggestions,
                schema_used=_to_enum_or_none(schema_name),
                reason=reason or "Nu s-a găsit o potrivire în valorile permise.",
            )
        )

    return CharValidateOut(results=results)
