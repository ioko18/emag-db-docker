from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, List

_num_unit = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([A-Za-zµ\"u]+)?\s*$")

# normalizări unități (lowercase)
_UNIT_ALIASES = {
    "kg": "kg",
    "g": "g",
    "mg": "mg",

    "v": "v",
    "kv": "kv",
    "mv": "mv",
    "uv": "uv",
    "µv": "uv",

    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "nm": "nm",
    "inch": "in",
    '"': "in",
    "in": "in",
}

# conversii „țintă” → factori
_CONV = {
    # masă
    ("kg", "g"): 1000.0,
    ("g", "g"): 1.0,
    ("mg", "g"): 0.001,

    # tensiune
    ("kv", "v"): 1000.0,
    ("v", "v"): 1.0,
    ("mv", "v"): 0.001,
    ("uv", "v"): 1e-6,

    # lungime
    ("m", "mm"): 1000.0,
    ("cm", "mm"): 10.0,
    ("mm", "mm"): 1.0,
    ("in", "mm"): 25.4,
    ("nm", "mm"): 1e-6,
}


@dataclass(frozen=True)
class ParsedValue:
    number: float
    unit: str  # already normalized (lower)


def _normalize_unit(u: Optional[str]) -> str:
    if not u:
        return ""
    u = u.strip()
    # micro semnul µ → u
    u = u.replace("µ", "u")
    return _UNIT_ALIASES.get(u.lower(), u.lower())


def parse_num_unit(s: str) -> Tuple[Optional[ParsedValue], bool]:
    """
    Returnează (ParsedValue|None, ok_parse_bool).
    Acceptă '12.3 V', '12,3 V', '125 mm', '12"'.
    """
    if s is None:
        return (None, False)
    raw = s.strip()
    if not raw:
        return (None, False)
    m = _num_unit.match(raw)
    if not m:
        return (None, False)
    n = float(m.group(1).replace(",", "."))
    unit = _normalize_unit(m.group(2))
    return (ParsedValue(n, unit), True)


def _pick_target_unit(allowed: Iterable[str]) -> str:
    """Alege unitatea „majoritară” din allowed, pentru comparații coerente."""
    counts: dict[str, int] = {}
    for a in allowed:
        pv, ok = parse_num_unit(a)
        if ok and pv and pv.unit:
            counts[pv.unit] = counts.get(pv.unit, 0) + 1
    if not counts:
        return ""  # fără unitate
    return max(counts, key=counts.get)


def _convert(p: ParsedValue, target_unit: str) -> Optional[float]:
    if not target_unit or p.unit == target_unit:
        return p.number
    key = (p.unit, target_unit)
    if key in _CONV:
        return p.number * _CONV[key]
    return None


def exact_match(user_value: str, allowed: Iterable[str]) -> Optional[str]:
    # match „textual” identic (case-sensitive, ca la API)
    for a in allowed:
        if user_value == a:
            return a
    return None


def closest_allowed(user_value: str, allowed: List[str]) -> Optional[str]:
    """Găsește valoarea permisă cu numerică cea mai apropiată (+ conversii unități)."""
    pv_in, ok_in = parse_num_unit(user_value)
    if not ok_in or pv_in is None:
        return None

    target = _pick_target_unit(allowed)
    xin = _convert(pv_in, target)
    if xin is None:
        return None

    best_idx = -1
    best_diff = math.inf
    parsed_allowed: List[Optional[ParsedValue]] = []
    for a in allowed:
        pv, ok = parse_num_unit(a)
        parsed_allowed.append(pv if ok else None)

    for idx, (raw, pv) in enumerate(zip(allowed, parsed_allowed)):
        if pv is None:
            continue
        xv = _convert(pv, target)
        if xv is None:
            continue
        d = abs(xv - xin)
        if d < best_diff:
            best_idx = idx
            best_diff = d

    return allowed[best_idx] if best_idx >= 0 else None


def map_value_for_emag(
    user_value: str,
    allowed: List[str],
    allow_new_value: bool,
    prefer_exact: bool = True,
) -> Tuple[str, str]:
    """
    Întoarce (label_de_trimis, source), unde source ∈ {"exact","closest","new"}.
    Ridică ValueError dacă nu se poate mapa și nu e voie valoare nouă.
    """
    user_value = (user_value or "").strip()
    if not user_value:
        raise ValueError("Valoarea este goală.")

    if prefer_exact:
        ex = exact_match(user_value, allowed)
        if ex is not None:
