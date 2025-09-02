# app/routers/emag/deps.py
from __future__ import annotations

from typing import Annotated, AsyncIterator
from fastapi import HTTPException, Query, status


# Notă: NU importăm SDK-ul la nivel de modul ca să evităm circulare la import.
# Îl importăm în interiorul funcției de dependency.

_VALID_ACCOUNTS = frozenset({"main", "fbe"})
_VALID_COUNTRIES = frozenset({"ro", "bg", "hu"})


async def emag_client_dependency(
    account: Annotated[str, Query(description="Cont eMAG (main|fbe)")] = "main",
    country: Annotated[str, Query(description="Țara (ro|bg|hu)")] = "ro",
) -> AsyncIterator[object]:
    """
    Construieste un EmagClient pe baza variabilelor de mediu pentru (account, country).

    - Validează parametrii (422 la valori invalide).
    - Importă SDK-ul târziu (evită importuri circulare).
    - Închide clientul după finalizarea request-ului.
    """
    acct = (account or "").strip().lower()
    ctry = (country or "").strip().lower()

    if acct not in _VALID_ACCOUNTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid account: {acct!r}. Allowed: {sorted(_VALID_ACCOUNTS)}",
        )
    if ctry not in _VALID_COUNTRIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid country: {ctry!r}. Allowed: {sorted(_VALID_COUNTRIES)}",
        )

    # Import târziu ca să nu introducem dependențe de la import-time.
    try:
        from app.integrations.emag_sdk import EmagClient, get_config_from_env  # type: ignore
    except Exception as e:  # pragma: no cover
        # 500 - server misconfigured (nu găsim SDK)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import Emag SDK: {e}",
        )

    try:
        cfg = get_config_from_env(acct, ctry)
    except Exception as e:
        # 503 - lipsesc credențiale
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"eMAG credentials missing or invalid for account={acct}, country={ctry}: {e}",
        )

    client = EmagClient(cfg)
    try:
        yield client
    finally:
        try:
            await client.aclose()
        except Exception:
            # best-effort; nu mascăm excepții
            pass


__all__ = ("emag_client_dependency",)
