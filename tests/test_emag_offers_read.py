# tests/test_emag_offers_read.py
import httpx

BASE = "http://127.0.0.1:8010"

def _post(path, **json):
    url = f"{BASE}{path}"
    r = httpx.post(url, json=json)
    r.raise_for_status()
    return r.json()

def test_filter_by_sku_maps_to_part_number():
    q = "?account=fbe&country=ro&compact=1&fields=id,sku,name"
    data = _post(f"/integrations/emag/product_offer/read{q}", page=1, limit=5, sku="ADS206")
    assert data["total"] == 1
    it = data["items"][0]
    assert it["sku"] == "ADS206"

def test_filter_by_part_number_key_exposes_emag_sku():
    q = "?account=fbe&country=ro&compact=1&fields=id,emag_sku,name"
    data = _post(f"/integrations/emag/product_offer/read{q}", page=1, limit=5, part_number_key="DL0WVYYBM")
    assert data["total"] == 1
    it = data["items"][0]
    assert it["emag_sku"] == "DL0WVYYBM"

def test_openapi_has_params():
    r = httpx.get(f"{BASE}/openapi.json")
    r.raise_for_status()
    schema = r.json()
    params = [p["name"] for p in schema["paths"]["/integrations/emag/product_offer/read"]["post"]["parameters"]]
    for expected in ["format", "filename", "account", "country", "compact", "fields", "sort"]:
        assert expected in params
