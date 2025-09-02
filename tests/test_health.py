# tests/test_health.py
from __future__ import annotations

import os
import time
from typing import Any, Dict

import httpx
import pytest

# --- Config din env -----------------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
MIGR_PATH = os.getenv("TEST_MIGR_PATH", "/health/migrations")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))
# Latență maximă acceptată pentru /health (secunde)
MAX_HEALTH_LATENCY = float(os.getenv("TEST_HEALTH_MAX_LATENCY", "1.5"))
# Dacă vrei să forțezi ca migrațiile să fie prezente (True/1/yes)
EXPECT_MIGRATIONS = os.getenv("TEST_EXPECT_MIGRATIONS_PRESENT", "").lower() in {"1", "true", "yes"}


# --- Utilitare ----------------------------------------------------------------
def _wait_until_healthy(c: httpx.Client):
    """Așteaptă ca endpoint-ul /health să devină 200."""
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _dump_response(r: httpx.Response) -> str:
    """Diagnostic scurt pentru mesaje de aserție."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = (r.text or "")[:400].replace("\n", "\\n")
    return f"status={r.status_code} {r.request.method} {r.request.url} json={j!r} text='{snippet}...'"


def _is_json(r: httpx.Response) -> bool:
    return r.headers.get("content-type", "").lower().startswith("application/json")


def _get_json(r: httpx.Response) -> Dict[str, Any]:
    assert _is_json(r), f"unexpected content-type: {r.headers.get('content-type')} | {_dump_response(r)}"
    try:
        return r.json()  # type: ignore[return-value]
    except Exception as exc:
        pytest.fail(f"invalid JSON: {exc!r} | {_dump_response(r)}")


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP de sesiune + warm-up health."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(5)
def test_health_ok(client: httpx.Client):
    t0 = time.perf_counter()
    r = client.get(HEALTH_PATH)
    dt = time.perf_counter() - t0

    assert r.status_code == 200, _dump_response(r)
    assert dt <= MAX_HEALTH_LATENCY, f"/health too slow: {dt:.3f}s > {MAX_HEALTH_LATENCY:.3f}s"
    body = _get_json(r)

    # Contract minim: {"status": "ok"}
    assert body.get("status") == "ok", body


@pytest.mark.timeout(5)
def test_health_is_stable_twice(client: httpx.Client):
    """Două apeluri consecutive ar trebui să fie consistente și rapide."""
    r1 = client.get(HEALTH_PATH)
    r2 = client.get(HEALTH_PATH)

    assert r1.status_code == 200, _dump_response(r1)
    assert r2.status_code == 200, _dump_response(r2)

    b1, b2 = _get_json(r1), _get_json(r2)
    assert b1.get("status") == "ok", b1
    assert b2.get("status") == "ok", b2


@pytest.mark.timeout(5)
def test_health_head_or_options_do_not_error(client: httpx.Client):
    """Acceptăm 200/204/405/404 pentru HEAD/OPTIONS, dar nu 5xx."""
    r_head = client.head(HEALTH_PATH)
    r_opt = client.options(HEALTH_PATH)

    assert r_head.status_code < 500, _dump_response(r_head)
    assert r_opt.status_code < 500, _dump_response(r_opt)


@pytest.mark.timeout(5)
def test_migrations_endpoint(client: httpx.Client):
    """Verifică endpoint-ul migrations; opțional impune 'present=True' prin env."""
    r = client.get(MIGR_PATH)

    # Dacă nu există implementare, marchează testul ca xfail (contract minim opțional).
    if r.status_code in (404, 501):
        pytest.xfail(f"{MIGR_PATH} not implemented: {_dump_response(r)}")

    assert r.status_code == 200, _dump_response(r)
    body = _get_json(r)

    # contract minim: câmpul "present" există și e boolean
    assert "present" in body, body
    assert isinstance(body["present"], bool), f"'present' must be bool, got {type(body['present'])}"

    if EXPECT_MIGRATIONS:
        assert body["present"] is True, f"migrations expected to be present, got: {body!r}"
