# tests/test_api.py
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env (cu valori implicite bune pt rulare locală/CI) ----------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST-uri imediat după pornire (în caz de curse init/migrări)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Returnează un diagnostic compact & util despre răspunsul HTTP."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = r.text[:500].replace("\n", "\\n")
    return (
        f"status={r.status_code} url={r.request.method} {r.request.url} "
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
    """Așteaptă /health să raporteze 200 OK."""
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
    for i in range(1, POST_RETRIES + 1):
        try:
            r = c.post(url, json=json)
            return r
        except Exception as exc:  # rețele/flakiness rare
            last_exc = exc
            time.sleep(POST_RETRY_SLEEP)
    # Dacă am eșuat de tot, ridicăm cu context
    raise AssertionError(f"POST {url} failed after {POST_RETRIES} retries: {last_exc!r}")


def create_category(
    c: httpx.Client, name: Optional[str] = None, description: Optional[str] = None
) -> Dict[str, Any]:
    payload = {"name": name or f"Cat_{uuid.uuid4().hex[:8]}"}
    if description is not None:
        payload["description"] = description
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["name"] == payload["name"], j
    return j


def create_product(
    c: httpx.Client,
    name: Optional[str] = None,
    price: float = 10.5,
    sku: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "name": name or f"Prod_{uuid.uuid4().hex[:8]}",
        "price": price,
        "sku": sku or f"SKU-TST-{uuid.uuid4().hex[:10]}",
    }
    r = _post_with_retry(c, "/products", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["sku"] == payload["sku"], j
    return j


def list_products_by_category(
    c: httpx.Client, category_id: int, limit: int = 10
) -> Dict[str, Any]:
    r = c.get("/products", params={"category_id": category_id, "limit": limit})
    _assert_status(r, 200)
    j = r.json()
    assert isinstance(j.get("total"), int), j
    assert isinstance(j.get("items"), list), j
    return j


def attach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.post(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


def detach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.delete(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


# --- Client fixură ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP către API-ul deja pornit (containerul app-test)."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_categories_crud_and_attach_flow(client: httpx.Client):
    # 1) create category
    cat = create_category(client, description="test")
    cid = cat["id"]

    # 2) create product
    prod = create_product(client)
    pid = prod["id"]

    # 3) attach (idempotent expected 204)
    attach_product(client, cid, pid)

    # 4) list products filtered by category => conține produsul
    data = list_products_by_category(client, cid, limit=10)
    assert any(p.get("id") == pid for p in data.get("items", [])), data

    # 5) detach (idempotent)
    detach_product(client, cid, pid)

    # 6) list again => nu mai conține produsul
    data2 = list_products_by_category(client, cid, limit=10)
    assert not any(p.get("id") == pid for p in data2.get("items", [])), data2
