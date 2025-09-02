from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------- Enum-uri de bază ----------
class Account(str, Enum):
    main = "main"
    fbe = "fbe"


class Country(str, Enum):
    ro = "ro"
    bg = "bg"
    hu = "hu"


class OrderStatus(int, Enum):
    canceled = 0
    new = 1
    in_progress = 2
    prepared = 3
    finalized = 4
    returned = 5


class AwbFormat(str, Enum):
    PDF = "PDF"
    ZPL = "ZPL"


class CharSchema(str, Enum):
    mass = "mass"          # g, Kg
    length = "length"      # nm, mm, cm, m, inch
    voltage = "voltage"    # µV, V, kV, MV
    noise = "noise"        # dB
    integer = "integer"
    text = "text"
    range_text = "range_text"  # ex: "0 - 10 mm"


# ---------- Input/Output Models (categorii / produse) ----------
class CategoriesIn(BaseModel):
    page: int = Field(1, ge=1, description="Pagina (>=1)")
    limit: int = Field(100, ge=1, le=4000, description="Câte elemente/pagină (1..4000)")
    language: Optional[str] = Field(
        None, description="Locale eMAG (ex. ro_RO / bg_BG / hu_HU / en_GB). Dacă lipsește, se deduce din țară."
    )

    @field_validator("language")
    @classmethod
    def _lang_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", v):
            raise ValueError("language trebuie sub forma xx_XX (ex: ro_RO).")
        return v


# ---------- Product Offer: Save / Stock Update ----------
class ProductOfferStock(BaseModel):
    warehouse_id: int = Field(..., gt=0, description="ID depozit (>0)")
    value: int = Field(..., ge=0, description="Stoc (>=0)")


class ProductOfferSaveIn(BaseModel):
    id: int = Field(..., gt=0, description="seller product id (internal id)")
    status: int = Field(..., ge=0, le=3, description="0=inactive,1=active,2=pending,3=deleted")
    sale_price: Decimal
    min_sale_price: Decimal
    max_sale_price: Decimal
    vat_id: int = Field(..., gt=0)
    handling_time: int = Field(..., ge=0)
    stock: List[ProductOfferStock]
    part_number_key: Optional[str] = Field(None, description="PNK (mutual exclusiv cu ean)")
    ean: Optional[str] = Field(None, description="EAN (mutual exclusiv cu PNK)")

    @field_validator("ean")
    @classmethod
    def _ean_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.strip()
        if not re.fullmatch(r"\d{8}|\d{13}", vv):  # EAN-8 sau EAN-13
            raise ValueError("EAN trebuie să fie numeric (8 sau 13 cifre).")
        return vv

    @model_validator(mode="after")
    def _validate_business_rules(self):
        if not self.stock:
            raise ValueError("Lista 'stock' nu poate fi goală.")
        if self.part_number_key and self.ean:
            raise ValueError("Folosește fie part_number_key (PNK), fie ean — nu ambele.")
        wh = [s.warehouse_id for s in self.stock]
        if len(set(wh)) != len(wh):
            raise ValueError("Lista 'stock' nu poate conține warehouse_id duplicate.")

        q = Decimal("0.01")
        self.min_sale_price = self.min_sale_price.quantize(q, rounding=ROUND_HALF_UP)
        self.sale_price = self.sale_price.quantize(q, rounding=ROUND_HALF_UP)
        self.max_sale_price = self.max_sale_price.quantize(q, rounding=ROUND_HALF_UP)
        if any(p < 0 for p in (self.min_sale_price, self.sale_price, self.max_sale_price)):
            raise ValueError("Prețurile trebuie să fie ≥ 0.")
        if not (self.min_sale_price <= self.sale_price <= self.max_sale_price):
            raise ValueError("sale_price trebuie să fie în [min_sale_price, max_sale_price].")
        return self


class OfferStockUpdateIn(BaseModel):
    id: int = Field(..., gt=0, description="seller product id (internal id)")
    warehouse_id: int = Field(..., gt=0)
    value: int = Field(..., ge=0)


# ---------- Orders / AWB ----------
class OrdersReadIn(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(100, ge=1, le=4000)
    status: Optional[OrderStatus] = Field(None, description="Filtru status (opțional)")


class OrdersAckIn(BaseModel):
    order_ids: List[int] = Field(..., min_items=1, description="Lista de ID-uri comenzi (>0, unice)")

    @model_validator(mode="after")
    def _validate_ids(self):
        if any(i <= 0 for i in self.order_ids):
            raise ValueError("Toate order_ids trebuie > 0.")
        if len(set(self.order_ids)) != len(self.order_ids):
            raise ValueError("order_ids conține duplicate.")
        return self


class AwbSaveIn(BaseModel):
    order_id: int = Field(..., gt=0)
    courier: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1)
    cod: bool = False

    @model_validator(mode="after")
    def _strip_nonempty(self):
        self.courier = self.courier.strip()
        self.service = self.service.strip()
        if not self.courier:
            raise ValueError("courier nu poate fi gol.")
        if not self.service:
            raise ValueError("service nu poate fi gol.")
        return self


# ---------- Caracteristici ----------
class CharAllowed(BaseModel):
    characteristic_id: int = Field(..., gt=0)
    values: List[str] = Field(default_factory=list, description="Lista valorilor permise (exact cum vin din eMAG)")


class CharValidateItem(BaseModel):
    characteristic_id: int = Field(..., gt=0)
    value: str = Field(..., min_length=1, description="Valoarea de intrare (ex: '2.5 Kg')")
    # alias compat 'schema'
    schema_name: Optional[CharSchema] = Field(
        default=None,
        alias="schema",
        description="Tip de mărime (mass/length/voltage/noise/integer/text/range_text). Dacă lipsește, se încearcă auto-detect."
    )

    @model_validator(mode="after")
    def _strip(self):
        self.value = " ".join(self.value.split()).strip()
        return self

    class Config:
        populate_by_name = True


class CharValidateIn(BaseModel):
    items: List[CharValidateItem] = Field(..., min_items=1)
    allowed: List[CharAllowed] = Field(..., min_items=1)


class CharValidateOutItem(BaseModel):
    characteristic_id: int
    input_value: str
    valid: bool
    matched_value: Optional[str] = None
    suggestions: Optional[List[str]] = None
    schema_used: Optional[CharSchema] = None
    reason: Optional[str] = None


class CharValidateOut(BaseModel):
    results: List[CharValidateOutItem]


# ---------- Product Offer: Read (filtre + item normalizat) ----------
STATUS_TEXT_ALLOWED = {"inactive", "active", "eol"}


class OfferReadFilters(BaseModel):
    # request to eMAG
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=400)
    status: Optional[int] = Field(None, description="0=inactive,1=active,2=eol")
    sku: Optional[str] = None
    ean: Optional[str] = None
    part_number_key: Optional[str] = None

    # filtre locale (client-side)
    after_id: Optional[int] = Field(None, ge=0)
    name_contains: Optional[str] = None
    category_id: Optional[int] = Field(None, ge=0)
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    status_text: Optional[str] = Field(None, description="inactive|active|eol")

    @field_validator("ean")
    @classmethod
    def _ean_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.strip()
        if not re.fullmatch(r"\d{8}|\d{13}", vv):
            raise ValueError("EAN trebuie 8 sau 13 cifre.")
        return vv

    @field_validator("status_text")
    @classmethod
    def _status_text_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.strip().lower()
        if vv not in STATUS_TEXT_ALLOWED:
            raise ValueError("status_text trebuie să fie: inactive|active|eol")
        return vv

    @model_validator(mode="after")
    def _validate_prices(self):
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price nu poate fi > max_price")
        return self


class OfferNormalized(BaseModel):
    id: Optional[int] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    status: Optional[int] = None
    status_text: Optional[str] = None

    sale_price: Optional[Decimal] = None
    min_sale_price: Optional[Decimal] = None
    max_sale_price: Optional[Decimal] = None
    best_offer_sale_price: Optional[Decimal] = None
    currency: Optional[str] = None
    vat_id: Optional[int] = None
    handling_time: Optional[int] = None

    ean: Optional[str] = None
    part_number_key: Optional[str] = None

    general_stock: Optional[int] = None
    estimated_stock: Optional[int] = None
    stock_total: Optional[int] = None

    # câmpuri opționale, expuse doar dacă sunt cerute
    warehouses: Optional[List[Dict[str, Any]]] = None
    stock_debug: Optional[Dict[str, Any]] = None
