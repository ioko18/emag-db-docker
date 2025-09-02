from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import hashlib
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Callable, Awaitable, List

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

# =========================
# Config & constante
# =========================

EMAG_BASE_URLS = {
    "ro": os.getenv("EMAG_BASE_URL_RO", "https://marketplace-api.emag.ro/api-3"),
    "bg": os.getenv("EMAG_BASE_URL_BG", "https://marketplace-api.emag.bg/api-3"),
    "hu": os.getenv("EMAG_BASE_URL_HU", "https://marketplace-api.emag.hu/api-3"),
}

DEFAULT_CONNECT_TIMEOUT = float(os.getenv("EMAG_CONNECT_TIMEOUT_S", "10"))
DEFAULT_READ_TIMEOUT = float(os.getenv("EMAG_READ_TIMEOUT_S", "30"))
DEFAULT_HTTP2 = os.getenv("EMAG_HTTP2", "1").strip().lower() not in {"0", "false", "no"}

DEFAULT_UA = os.getenv("EMAG_USER_AGENT", f"emag-db-api/{os.getenv('APP_VERSION', 'unknown')}")
DEFAULT_ORDERS_RPS = int(os.getenv("EMAG_ORDERS_RPS", "12"))
DEFAULT_OTHER_RPS = int(os.getenv("EMAG_DEFAULT_RPS", "3"))

# Pool/keepalive (httpx)
MAX_CONNECTIONS = int(os.getenv("EMAG_MAX_CONNECTIONS", "20"))
MAX_KEEPALIVE = int(os.getenv("EMAG_MAX_KEEPALIVE", "10"))
KEEPALIVE_EXPIRY_S = float(os.getenv("EMAG_KEEPALIVE_EXPIRY_S", "60"))

# Logging flags
EMAG_HTTP_LOG = os.getenv("EMAG_HTTP_LOG", "").strip().lower() in {"1", "true", "yes", "on"}
# NOTE: ținem logurile concise (nu logăm body-uri complete în mod implicit)
logger_http = logging.getLogger("emag-db-api.emag_http")

# =========================
# Erori specifice
# =========================

class EmagRateLimitError(Exception):
    """429 sau throttling local."""
    pass


class EmagApiError(Exception):
    """Răspuns eMAG cu isError=true sau status != 2xx."""
    def __init__(self, message: str, status_code: int = 0, payload: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}

# =========================
# Modele config
# =========================

@dataclass(frozen=True)
class EmagAuth:
    username: str
    password: str


@dataclass(frozen=True)
class EmagConfig:
    account: str          # "main" | "fbe"
    country: str          # "ro" | "bg" | "hu"
    base_url: str
    auth: EmagAuth
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    read_timeout: float = DEFAULT_READ_TIMEOUT
    http2: bool = DEFAULT_HTTP2
    user_agent: str = DEFAULT_UA
    orders_rps: int = DEFAULT_ORDERS_RPS
    default_rps: int = DEFAULT_OTHER_RPS

# =========================
# Limiter per secundă
# =========================

class _PerSecondLimiter:
    """Limiter simplu: max N apeluri/1s per 'grup' (async-safe)."""
    def __init__(self):
        # group -> (deque of timestamps, limit)
        self._buckets: dict[str, Tuple[deque, int]] = {}
        self._lock = asyncio.Lock()

    def set_limit(self, group: str, rps: int):
        if group not in self._buckets:
            self._buckets[group] = (deque(), rps)
        else:
            q, _ = self._buckets[group]
            self._buckets[group] = (q, rps)

    async def acquire(self, group: str):
        # asigură existența bucket-ului
        if group not in self._buckets:
            self.set_limit(group, DEFAULT_OTHER_RPS)

        async with self._lock:
            q, limit = self._buckets[group]
            now = time.monotonic()
            # curățăm intrări mai vechi de 1s
            while q and now - q[0] >= 1.0:
                q.popleft()
            if len(q) >= limit and q:
                sleep_for = max(0.0, 1.0 - (now - q[0]))
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                # după sleep, curăță din nou
                now = time.monotonic()
                while q and now - q[0] >= 1.0:
                    q.popleft()
            q.append(time.monotonic())

# =========================
# Helpers diverse
# =========================

_LANG_BY_COUNTRY = {"ro": "ro_RO", "bg": "bg_BG", "hu": "hu_HU"}

def _derive_lang(cty: str) -> str:
    return _LANG_BY_COUNTRY.get(cty.lower(), "en_GB")


def _merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    out.update(b)
    return out


def _normalize_base_url(url: str) -> str:
    # asigurăm trailing slash, ca join-ul cu 'resource/action' (fără leading slash) să păstreze /api-3
    return url.rstrip("/") + "/"


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        # unele răspunsuri de eroare pot fi text/html
        return {"raw": resp.text, "status": resp.status_code}


def _is_success_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    # cel mai frecvent contract
    if payload.get("isError") is False:
        return True
    # fallback: dacă nu avem isError dar avem 'data' semnificativ
    if "isError" not in payload and "data" in payload:
        return True
    # alt fallback: unele endpoint-uri folosesc 'success' sau 'status' textual
    if payload.get("success") is True:
        return True
    return False


def _extract_error_details(payload: Any) -> Dict[str, Any]:
    """
    Normalizează câmpurile de eroare des întâlnite în răspunsurile eMAG.
    """
    if not isinstance(payload, dict):
        return {"raw": payload}
    details: Dict[str, Any] = {}
    for key in ("messages", "errors", "error", "message"):
        if key in payload and payload[key]:
            details[key] = payload[key]
    if "data" in payload and isinstance(payload["data"], dict):
        for key in ("errors", "messages"):
            if key in payload["data"] and payload["data"][key]:
                details[f"data.{key}"] = payload["data"][key]
    return details or payload


def make_idempotency_key(obj: Any) -> str:
    """
    Creează un idempotency key determinist din payload.
    Util când clientul nu furnizează unul explicit.
    """
    try:
        normalized = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    except Exception:
        normalized = str(obj)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

# =========================
# Client
# =========================

class EmagClient:
    """
    Client minimal pentru eMAG Marketplace.
    - Auth: Basic (httpx.BasicAuth) pe fiecare cerere.
    - Body: POST JSON (fără wrapper 'data')
    - Succes: payload.get("isError") == False OR ("isError" inexistent & "data" prezent)
    - Rate-limit local: 'orders' -> cfg.orders_rps; 'default' -> cfg.default_rps
    - Retry: httpx.HTTPError & EmagRateLimitError cu backoff + jitter (+ log înainte de retry)
    - Idempotency: header 'X-Idempotency-Key' (opțional)
    """

    def __init__(self, cfg: EmagConfig):
        self.cfg = cfg
        self._limiter = _PerSecondLimiter()
        self._limiter.set_limit("orders", cfg.orders_rps)
        self._limiter.set_limit("default", cfg.default_rps)

        # Fallback elegant la HTTP/1.1 dacă lipsește pachetul h2
        http2 = cfg.http2
        if http2:
            try:
                import h2  # noqa: F401
            except Exception:
                http2 = False  # dezactivează dacă nu e disponibil

        # IMPORTANT: setează toate cele 3 timeouts explicite + default (evită eroarea httpx)
        timeout = httpx.Timeout(
            timeout=self.cfg.read_timeout,      # default (safe fallback)
            connect=self.cfg.connect_timeout,
            read=self.cfg.read_timeout,
            write=self.cfg.read_timeout,
            pool=self.cfg.connect_timeout,
        )

        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE,
            keepalive_expiry=KEEPALIVE_EXPIRY_S,
        )

        self._client = httpx.AsyncClient(
            base_url=_normalize_base_url(cfg.base_url),
            timeout=timeout,
            http2=http2,
            limits=limits,
            headers=self._build_base_headers(cfg),
            auth=httpx.BasicAuth(cfg.auth.username, cfg.auth.password),
        )

    # --- context manager async ---
    async def __aenter__(self) -> "EmagClient":
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    # --- helpers ---

    def _build_base_headers(self, cfg: EmagConfig) -> Dict[str, str]:
        # Authorization e oferit de httpx.BasicAuth
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": cfg.user_agent,
            "Accept-Language": _derive_lang(cfg.country),
        }

    def _group_for(self, resource: str) -> str:
        r = resource.strip().lower()
        return "orders" if r in {"order", "orders"} else "default"

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, EmagRateLimitError)),
        wait=wait_exponential_jitter(initial=0.3, max=5.0),  # backoff + jitter
        stop=stop_after_attempt(5),
        reraise=True,
        before_sleep=before_sleep_log(logger_http, logging.WARNING),
    )
    async def _req_with_retry(
        self,
        fn: Callable[..., Awaitable[httpx.Response]],
        *args,
        **kwargs,
    ) -> httpx.Response:
        resp = await fn(*args, **kwargs)
        # 429 -> ridică EmagRateLimitError (tenacity va reîncerca)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    # limitează la max 10s ca să nu blocheze exagerat
                    delay = min(float(retry_after), 10.0)
                    await asyncio.sleep(delay)
                except ValueError:
                    pass
            raise EmagRateLimitError(
                f"Rate limited by eMAG (429). Retry-After={resp.headers.get('Retry-After')}"
            )
        # 204 -> considerăm succes "fără conținut"
        if resp.status_code == 204:
            return resp
        # 5xx -> httpx.raise_for_status() ridică HTTPStatusError (retry)
        if 500 <= resp.status_code:
            resp.raise_for_status()
        return resp

    async def _post(
        self,
        resource: str,
        action: str,
        data: dict,
        *,
        idempotency_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> dict:
        group = self._group_for(resource)
        await self._limiter.acquire(group)

        # IMPORTANT: fără leading slash; păstrăm /api-3 din base_url
        url = f"{resource.strip('/')}/{action.strip('/')}"
        req_id = os.urandom(12).hex()
        headers: Dict[str, str] = {"X-Request-Id": req_id}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        if extra_headers:
            headers = _merge_dicts(headers, extra_headers)

        started = time.perf_counter()
        if EMAG_HTTP_LOG:
            # ținem logul concis: metoda, url, grup, chei payload, are_idempotency
            logger_http.info(
                "POST %s group=%s rid=%s keys=%s idem=%s",
                url,
                group,
                req_id,
                ",".join(sorted(data.keys())),
                "yes" if "X-Idempotency-Key" in headers else "no",
            )

        resp = await self._req_with_retry(self._client.post, url, json=data, headers=headers)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if EMAG_HTTP_LOG:
            ra = resp.headers.get("Retry-After")
            srv_rid = resp.headers.get("X-Request-Id") or resp.headers.get("X-Request-ID")
            log_msg = (
                f"POST {url} -> {resp.status_code} in {elapsed_ms:.1f}ms "
                f"(retry_after={ra}, srv_rid={srv_rid}, cli_rid={req_id})"
            )
            if resp.status_code >= 400:
                logger_http.warning(log_msg)
            else:
                logger_http.info(log_msg)

        # 204 No Content -> succes “gol”
        if resp.status_code == 204:
            return {"isError": False, "data": None}

        # 4xx (≠429) -> EmagApiError (nu retry)
        if 400 <= resp.status_code < 500 and resp.status_code != 429:
            payload = _safe_json(resp)
            raise EmagApiError(
                f"eMAG API client error {resp.status_code} on {resource}/{action}",
                status_code=resp.status_code,
                payload=_extract_error_details(payload),
            )

        payload = _safe_json(resp)
        if _is_success_payload(payload):
            return payload

        # Nu e succes -> EmagApiError cu detalii
        raise EmagApiError(
            f"eMAG API error on {resource}/{action}",
            status_code=resp.status_code,
            payload=_extract_error_details(payload),
        )

    # ====== API helpers uzuale ======

    async def category_read(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        language: Optional[str] = None,
    ) -> dict:
        data: Dict[str, Any] = {"page": page, "limit": limit}
        data["language"] = language or _derive_lang(self.cfg.country)
        return await self._post("category", "read", data)

    async def product_offer_save(self, offer: dict, *, idempotency_key: Optional[str] = None) -> dict:
        # 'offer' trebuie să conțină câmpurile cerute de documentație
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(offer)
        return await self._post("product_offer", "save", offer, idempotency_key=idempotency_key)

    async def product_offer_read(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        status: Optional[int] = None,
        sku: Optional[str] = None,
        ean: Optional[str] = None,
        part_number_key: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Citește ofertele vânzătorului.
        Observație: contractul eMAG pentru filtrare poate varia; păstrăm top-level clasic
        (status/sku/ean/part_number_key) și permitem 'extra' pentru câmpuri suplimentare.
        """
        data: Dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            data["status"] = status
        if sku:
            data["sku"] = sku
        if ean:
            data["ean"] = ean
        if part_number_key:
            data["part_number_key"] = part_number_key
        if extra:
            data.update(extra)

        # idempotency e rar necesar pe read, dar acceptăm pentru simetrie
        return await self._post("product_offer", "read", data, idempotency_key=idempotency_key)

    async def offer_stock_update(
        self,
        *,
        item_id: int,
        warehouse_id: int,
        value: int,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        # actualizare rapidă de stoc (via product_offer/save)
        payload = {"id": item_id, "stock": [{"warehouse_id": warehouse_id, "value": value}]}
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(payload)
        return await self._post("product_offer", "save", payload, idempotency_key=idempotency_key)

    async def order_read(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        status: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> dict:
        data: Dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            data.setdefault("filters", {})["status"] = status
        if filters:
            data.setdefault("filters", {}).update(filters)
        return await self._post("order", "read", data)

    async def order_ack(self, order_ids: List[int], *, idempotency_key: Optional[str] = None) -> dict:
        data = {"orders": [{"id": oid} for oid in order_ids]}
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(data)
        return await self._post("order", "acknowledge", data, idempotency_key=idempotency_key)

    async def awb_save(
        self,
        *,
        order_id: int,
        courier: str,
        service: str,
        cod: bool = False,
        idempotency_key: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> dict:
        data = {
            "order_id": order_id,
            "courier": courier,
            "service": service,
            "cash_on_delivery": 1 if cod else 0,
        }
        if extra:
            data.update(extra)
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(data)
        return await self._post("awb", "save", data, idempotency_key=idempotency_key)

    async def awb_read(self, awb_id: int, *, format_: str = "PDF") -> dict:
        data = {"id": awb_id, "format": format_}
        return await self._post("awb", "read", data)

    # Helper generic (pentru extensii ulterioare)
    async def call(self, resource: str, action: str, data: dict, *, idempotency_key: Optional[str] = None) -> dict:
        return await self._post(resource, action, data, idempotency_key=idempotency_key)

    # Conveniență: construiește clientul din ENV
    @classmethod
    def from_env(cls, account: str, country: str) -> "EmagClient":
        return cls(get_config_from_env(account, country))

# =========================
# Rezolvarea config din ENV
# =========================

def get_config_from_env(account: str, country: str) -> EmagConfig:
    """
    Rezolvă credențialele din ENV în ordinea:
      1) per-țară:   EMAG_{ACC}_{CTY}_{USER,PASS}
      2) per-cont:   EMAG_{ACC}_{USER,PASS}
      3) global:     EMAG_GLOBAL_{USER,PASS}
    + suprascrieri opționale pe timeouts/RPS/http2/user-agent cu aceeași ordine.
    """
    acc = account.strip().lower()   # "main" | "fbe"
    cty = country.strip().lower()   # "ro" | "bg" | "hu"

    if cty not in EMAG_BASE_URLS:
        raise RuntimeError(f"Țară invalidă pentru eMAG: {cty!r}")

    base_url = EMAG_BASE_URLS[cty]

    # Prefixuri pentru căutare
    p_country = f"EMAG_{acc.upper()}_{cty.upper()}"
    p_account = f"EMAG_{acc.upper()}"
    p_global = "EMAG_GLOBAL"
    prefixes = (p_country, p_account, p_global)

    def _get_first(suffix: str, default: Optional[str] = None) -> Optional[str]:
        for p in prefixes:
            v = os.getenv(f"{p}_{suffix}")
            if v is not None and v.strip() != "":
                return v.strip()
        return default

    user = _get_first("USER", "")
    pwd = _get_first("PASS", "")

    if not user or not pwd:
        raise RuntimeError(
            "Lipsește utilizatorul/parola eMAG. Setează fie EMAG_MAIN_USER/EMAG_MAIN_PASS sau EMAG_FBE_USER/EMAG_FBE_PASS, "
            "eventual override per țară (ex. EMAG_MAIN_RO_USER/EMAG_MAIN_RO_PASS)."
        )

    # Suprascrieri opționale
    connect_timeout = float(_get_first("CONNECT_TIMEOUT_S", str(DEFAULT_CONNECT_TIMEOUT)))
    read_timeout = float(_get_first("READ_TIMEOUT_S", str(DEFAULT_READ_TIMEOUT)))
    http2 = (_get_first("HTTP2", "1") or "1").lower() not in {"0", "false", "no"}
    user_agent = _get_first("USER_AGENT", DEFAULT_UA) or DEFAULT_UA

    try:
        orders_rps = int(_get_first("ORDERS_RPS", str(DEFAULT_ORDERS_RPS)))
    except Exception:
        orders_rps = DEFAULT_ORDERS_RPS
    try:
        default_rps = int(_get_first("DEFAULT_RPS", str(DEFAULT_OTHER_RPS)))
    except Exception:
        default_rps = DEFAULT_OTHER_RPS

    return EmagConfig(
        account=acc,
        country=cty,
        base_url=base_url,
        auth=EmagAuth(username=user, password=pwd),
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        http2=http2,
        user_agent=user_agent,
        orders_rps=orders_rps,
        default_rps=default_rps,
    )
