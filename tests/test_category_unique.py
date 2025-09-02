# tests/test_category_unique.py
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env -----------------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST (curse inițializare/migrări imediat după boot)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Diagnostic compact pentru mesaje de aserție."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = (r.text or "")[:500].replace("\n", "\\n")
    return (
        f"status={r.status_code} {r.request.method} {r.request.url} "
        f"json={j!r} text='{snippet}...'"
    )


def _assert_status(r: httpx.Response, expected: int | tuple[int, ...]):
    if isinstance(expected, int):
        ok = r.status_code == expected
        exp_str = str(expected)
    else:
        ok = r.status_code in expected
        exp_str = "|".join(map(str, expected))
    assert ok, f"expected {exp_str} but got: {_dump_response(r)}"


def _wait_until_healthy(c: httpx.Client):
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _post_with_retry(
    c: httpx.Client, url: str, json: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for _ in range(1, POST_RETRIES + 1):
        try:
            return c.post(url, json=json)
        except Exception as exc:
            last_exc = exc
            time.sleep(POST_RETRY_SLEEP)
    raise AssertionError(f"POST {url} failed after {POST_RETRIES} retries: {last_exc!r}")


# --- Helper-e API -------------------------------------------------------------
def create_category(c: httpx.Client, name: str, description: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name}
    if description is not None:
        payload["description"] = description
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert isinstance(j.get("id"), int), j
    assert j.get("name") == name, j
    return j


def update_category_name(c: httpx.Client, cid: int, new_name: str) -> httpx.Response:
    r = c.put(f"/categories/{cid}", json={"name": new_name})
    return r


def delete_category(c: httpx.Client, cid: int) -> None:
    try:
        c.delete(f"/categories/{cid}")
    except Exception:
        pass


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_category_name_unique_case_insensitive(client: httpx.Client):
    created_ids: list[int] = []
    try:
        base = f"PyTest Uniq {uuid.uuid4().hex[:6]}"

        # 1) creare inițială
        c1 = create_category(client, base)
        created_ids.append(c1["id"])

        # 1.1) update idempotent la același nume -> acceptat (200 sau 204)
        r_same = update_category_name(client, c1["id"], base)
        _assert_status(r_same, (200, 204))

        # 2) același nume cu caz diferit -> 409 Conflict
        dup = base.swapcase()
        r_dup_create = client.post("/categories", json={"name": dup})
        _assert_status(r_dup_create, 409)

        # 3) altă categorie, apoi rename către numele existent (case-insensitive) -> 409
        other = create_category(client, f"{base}-other")
        created_ids.append(other["id"])
        r_conflict = update_category_name(client, other["id"], base)
        _assert_status(r_conflict, 409)

        # 3.1) (opțional) rename către o altă variantă de caz a aceluiași nume -> tot 409
        r_conflict_case = update_category_name(client, other["id"], base.lower())
        _assert_status(r_conflict_case, 409)

    finally:
        for cid in created_ids:
            delete_category(client, cid)
