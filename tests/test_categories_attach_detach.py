# tests/test_categories_attach_detach.py
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
    """Diagnostic compact despre răspunsul HTTP (status, URL, fragment body/JSON)."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = r.text[:500].replace("\n", "\\n")
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
    """Așteaptă /health să raporteze 200 OK înainte de a rula testele."""
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
def create_category(c: httpx.Client, *, name: Optional[str] = None, description: str = "tmp") -> Dict[str, Any]:
    payload = {"name": name or f"Cat_{uuid.uuid4().hex[:8]}", "description": description}
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["name"] == payload["name"], j
    return j


def create_product(c: httpx.Client, *, name: str = "Tmp Product", price: float = 1.23) -> Dict[str, Any]:
    payload = {"name": name, "price": price, "sku": f"SKU-TST-{uuid.uuid4().hex[:10]}"}
    r = _post_with_retry(c, "/products", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["sku"] == payload["sku"], j
    return j


def list_products_for_category(c: httpx.Client, category_id: int, *, limit: int = 50) -> list[Dict[str, Any]]:
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
def test_attach_detach_idempotent(client: httpx.Client):
    cat = create_category(client)
    prod = create_product(client)
    cid, pid = cat["id"], prod["id"]

    # attach de 2 ori -> ambele 204 (idempotent)
    attach_product(client, cid, pid)
    attach_product(client, cid, pid)

    # apare în listare după attach (exact o singură dată)
    items = list_products_for_category(client, cid)
    ids = [p.get("id") for p in items]
    assert pid in ids, items
    assert ids.count(pid) == 1, f"Product appears duplicated after idempotent attach: {items}"

    # detach de 2 ori -> ambele 204 (idempotent)
    detach_product(client, cid, pid)
    detach_product(client, cid, pid)

    # nu mai apare în listare după detach
    items_after = list_products_for_category(client, cid)
    assert all(p.get("id") != pid for p in items_after), items_after
