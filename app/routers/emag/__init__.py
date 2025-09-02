# app/routers/emag/__init__.py
from __future__ import annotations

import logging
from fastapi import APIRouter

logger = logging.getLogger("emag-db-api.emag")

# IMPORTANT: setăm O SINGURĂ dată prefixul de top-level
router = APIRouter(prefix="/integrations/emag", tags=["emag"])

# Subrouterele NU trebuie să aibă prefixul /integrations/emag în ele.
# Fiecare definește doar propriile segmente (ex: "/product_offer/read").
from .offers_read import router as offers_read_router  # noqa: E402
from .offers_write import router as offers_write_router  # noqa: E402
from .orders import router as orders_router  # noqa: E402
from .awb import router as awb_router  # noqa: E402
from .categories import router as categories_router  # noqa: E402
from .characteristics import router as characteristics_router  # noqa: E402
from .meta import router as meta_router  # noqa: E402


def _warn_if_hardcoded_prefix(name: str, subrouter: APIRouter) -> None:
    """Avertizează dacă subrouterul are rute cu prefix hard-codat /integrations/emag."""
    bad_paths = []
    for r in getattr(subrouter, "routes", []):
        path = getattr(r, "path", "")
        if isinstance(path, str) and path.startswith("/integrations/emag"):
            bad_paths.append(path)
    if bad_paths:
        logger.warning(
            "Subrouter '%s' conține rute cu prefix hard-codat '/integrations/emag': %s. "
            "Elimină prefixul din subrouter (prefixul se aplică doar aici, în __init__).",
            name,
            ", ".join(bad_paths),
        )


# Include toate subrouterele (fără prefix suplimentar)
for name, sub in [
    ("offers_read", offers_read_router),
    ("offers_write", offers_write_router),
    ("orders", orders_router),
    ("awb", awb_router),
    ("categories", categories_router),
    ("characteristics", characteristics_router),
    ("meta", meta_router),
]:
    _warn_if_hardcoded_prefix(name, sub)
    router.include_router(sub)
    logger.info("Loaded eMAG subrouter: %s", name)

__all__ = ["router"]
