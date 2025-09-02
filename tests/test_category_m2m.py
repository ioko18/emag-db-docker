# tests/test_category_m2m.py
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env (cu fallback-uri sigure) ---------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST imediat după pornire (curse init/migrări)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Diagnostic compact: status, URL, fragment body/JSON."""
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
    """Așteaptă /health să fie 200 OK înainte de testare."""
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


def _mk(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --- Helper-e API -------------------------------------------------------------
def create_product(c: httpx.Client, *, name: str | None = None, price: float = 1.0) -> Dict[str, Any]:
    payload = {"name": name or _mk("pytest-prod"), "price": price, "sku": f"SKU-{uuid.uuid4().hex[:10]}"}
    r = _post_with_retry(c, "/products", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert isinstance(j.get("id"), int), j
    assert j.get("sku") == payload["sku"], j
    return j


def create_category(c: httpx.Client, *, name: str | None = None, description: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name or _mk("pytest-cat")}
    if description is not None:
        payload["description"] = description
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert isinstance(j.get("id"), int), j
    assert j.get("name") == payload["name"], j
    return j


def products_in_category(c: httpx.Client, category_id: int, *, limit: int = 50) -> list[Dict[str, Any]]:
    r = c.get("/products", params={"category_id": category_id, "limit": limit})
    _assert_status(r, 200)
    j = r.json()
    assert isinstance(j.get("items"), list), j
    return j["items"]


def attach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.post(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


def detach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.delete(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP către API-ul deja pornit (containerul app-test)."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_m2m_attach_two_categories_and_idempotent(client: httpx.Client):
    prod = create_product(client)
    cat1 = create_category(client)
    cat2 = create_category(client)
    pid, c1, c2 = prod["id"], cat1["id"], cat2["id"]

    # attach la ambele categorii (și idempotent pe c1)
    attach_product(client, c1, pid)
    attach_product(client, c2, pid)
    attach_product(client, c1, pid)  # idempotent

    # prezent în listările filtrate (fără duplicate)
    items_c1 = products_in_category(client, c1)
    items_c2 = products_in_category(client, c2)
    ids_c1 = [p.get("id") for p in items_c1]
    ids_c2 = [p.get("id") for p in items_c2]
    assert pid in ids_c1, items_c1
    assert pid in ids_c2, items_c2
    assert ids_c1.count(pid) == 1, f"Product appears duplicated in c1: {items_c1}"
    assert ids_c2.count(pid) == 1, f"Product appears duplicated in c2: {items_c2}"

    # detach din c1 de două ori -> 204 ambele (idempotent)
    detach_product(client, c1, pid)
    detach_product(client, c1, pid)

    # nu mai apare în c1, încă apare în c2
    items_c1 = products_in_category(client, c1)
    items_c2 = products_in_category(client, c2)
    assert all(p.get("id") != pid for p in items_c1), items_c1
    assert any(p.get("id") == pid for p in items_c2), items_c2

    # cleanup: detașează și din c2 (idempotent)
    detach_product(client, c2, pid)
    detach_product(client, c2, pid)
