# app/schemas/product.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
import re

from pydantic import BaseModel, Field, ConfigDict, field_validator

# SKU: litere/cifre + . _ - ; max 64; fără spații
SKU_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _quantize_price(v: Decimal) -> Decimal:
    # Aliniază la NUMERIC(12,2) și evită erori de reprezentare
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProductBase(BaseModel):
    """Câmpuri comune pentru produs; folosit la create/read."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    sku: Optional[str] = Field(None, min_length=1, max_length=64)

    # --- Validators ---
    @field_validator("name")
    @classmethod
    def _name_strip_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description")
    @classmethod
    def _descr_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("sku")
    @classmethod
    def _sku_validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not SKU_RE.match(v):
            raise ValueError("Invalid SKU (allowed: letters, digits, . _ -, max 64)")
        return v

    @field_validator("price")
    @classmethod
    def _price_quantize(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("price must be >= 0")
        return _quantize_price(v)

    model_config = ConfigDict(
        # oferă exemple utile în OpenAPI
        json_schema_extra={
            "examples": [
                {
                    "name": "Amplificator audio TPA3116",
                    "description": "2x50W, radiator aluminiu",
                    "price": "129.90",
                    "sku": "TPA3116-2x50W-BLUE",
                }
            ]
        }
    )


class ProductCreate(ProductBase):
    """Payload pentru creare produs."""
    pass


class ProductUpdate(BaseModel):
    """Payload pentru update; toate câmpurile sunt opționale."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    sku: Optional[str] = Field(None, min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def _name_strip_nonempty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description")
    @classmethod
    def _descr_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("sku")
    @classmethod
    def _sku_validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not SKU_RE.match(v):
            raise ValueError("Invalid SKU (allowed: letters, digits, . _ -, max 64)")
        return v

    @field_validator("price")
    @classmethod
    def _price_quantize(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("price must be >= 0")
        return _quantize_price(v)


class ProductRead(ProductBase):
    """Răspuns pentru produs."""
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProductPage(BaseModel):
    """Răspuns paginat: listă + meta."""
    items: List[ProductRead]
    total: int
    page: int
    page_size: int
