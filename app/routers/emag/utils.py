from __future__ import annotations

import difflib
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Callable, Awaitable

import httpx
from fastapi import HTTPException, status

# Limbă implicită per țară
LANG_BY_COUNTRY: Dict[str, str] = {"ro": "ro_RO", "bg": "bg_BG", "hu": "hu_HU"}

_QUANT_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-zµ]+)\s*$")


def normalize_ws(s: str) -> str:
    return " ".join(s.split()).strip()


def infer_schema_from_allowed(allowed: List[str]) -> str:
    units = set()
    numerics = 0
    for v in allowed:
        m = _QUANT_RE.match(v)
        if m:
            units.add(m.group(2))
        elif v.strip().isdigit():
            numerics += 1
    u_low = {u.lower() for u in units}
    if {"kg", "g"} & u_low:
        return "mass"
    if {"mm", "cm", "m", "inch", "nm"} & u_low:
        return "length"
    if {"v", "kv", "mv", "µv", "μv", "uv"} & u_low:
        return "voltage"
    if {"db"} & u_low:
        return "noise"
    if numerics == len(allowed) and numerics > 0:
        return "integer"
    return "text"


def _to_base(value: Decimal, unit: str, schema_name: str) -> Tuple[Decimal, str]:
    u = unit.lower()
    if schema_name == "mass":
        if u == "kg":
            return (value * Decimal("1000"), "g")
        if u == "g":
            return (value, "g")
    elif schema_name == "length":
        if u == "nm":
            return (value / Decimal("1_000_000"), "mm")
        if u == "mm":
            return (value, "mm")
        if u == "cm":
            return (value * Decimal("10"), "mm")
        if u == "m":
            return (value * Decimal("1000"), "mm")
        if u in {"inch", "in"}:
            return (value * Decimal("25.4"), "mm")
    elif schema_name == "voltage":
        if u in {"µv", "μv", "uv"}:
            return (value / Decimal("1_000_000"), "V")
        if u == "v":
            return (value, "V")
        if u == "kv":
            return (value * Decimal("1000"), "V")
        if u == "mv":
            return (value * Decimal("1_000_000"), "V")
    elif schema_name == "noise":
        if u == "db":
            return (value, "dB")
    return (value, unit)


def _parse_quantity(s: str) -> Optional[Tuple[Decimal, str]]:
    m = _QUANT_RE.match(s)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    unit = m.group(2)
    try:
        return (Decimal(num), unit)
    except Exception:
        return None


def _nearly_equal(a: Decimal, b: Decimal, rel_tol: Decimal = Decimal("1e-9")) -> bool:
    da = abs(a)
    db = abs(b)
    return abs(a - b) <= rel_tol * max(Decimal(1), da, db)


def match_quantitative(input_value: str, allowed: List[str], schema_name: str) -> Tuple[Optional[str], Optional[str]]:
    parsed_in = _parse_quantity(input_value)
    if not parsed_in:
        return (None, "Valoarea nu pare cantitativă (număr + unitate).")
    vin, uin = parsed_in
    vin_base, _ = _to_base(vin, uin, schema_name)
    for canonical in allowed:
        parsed_allowed = _parse_quantity(canonical)
        if not parsed_allowed:
            continue
        va, ua = parsed_allowed
        va_base, _ = _to_base(va, ua, schema_name)
        if _nearly_equal(vin_base, va_base):
            return (canonical, None)
    return (None, "Nu există corespondent numeric în lista permisă (după conversia unităților).")


def match_exact_or_ci(input_value: str, allowed: List[str]) -> Optional[str]:
    if input_value in allowed:
        return input_value
    norm_in = normalize_ws(input_value).lower()
    by_norm = {normalize_ws(v).lower(): v for v in allowed}
    return by_norm.get(norm_in)


def suggest(input_value: str, allowed: List[str], n: int = 5) -> List[str]:
    candidates = difflib.get_close_matches(input_value, allowed, n=n, cutoff=0.75)
    if candidates:
        return candidates
    low_map = {v.lower(): v for v in allowed}
    low_candidates = difflib.get_close_matches(input_value.lower(), list(low_map.keys()), n=n, cutoff=0.75)
    return [low_map[c] for c in low_candidates]


# ---------- invocator comun (erori uniforme) ----------
try:  # pragma: no cover
    from app.integrations.emag_sdk import EmagApiError, EmagRateLimitError  # type: ignore
except Exception:  # pragma: no cover
    class EmagApiError(Exception):
        def __init__(self, message: str, status_code: int = 0, payload: Optional[dict] = None):
            super().__init__(message)
            self.status_code = status_code
            self.payload = payload or {}

    class EmagRateLimitError(Exception):
        ...


async def call_emag(
    fn: Callable[..., Awaitable[dict]],
    *args,
    idempotency_key: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Invocator defensiv:
    - trece X-Idempotency-Key dacă funcția o acceptă;
    - convertește erorile din SDK/transport în HTTPException cu statusuri utile;
    - dacă metoda lipsește din SDK → 501 Not Implemented (mesaj clar).
    """
    try:
        if idempotency_key:
            try:
                return await fn(*args, idempotency_key=idempotency_key, **kwargs)
            except TypeError:
                return await fn(*args, **kwargs)
        return await fn(*args, **kwargs)
    except EmagRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except EmagApiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": str(e),
                "status_code": getattr(e, "status_code", 0),
                "payload": getattr(e, "payload", {}),
            },
        )
    except AttributeError as e:
        # metoda din SDK nu există
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"SDK method missing: {e}",
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"http transport error: {e!s}")
