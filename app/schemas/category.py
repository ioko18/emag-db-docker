# app/schemas/category.py
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

_WS_RE = re.compile(r"\s+")


def _norm_spaces(v: str) -> str:
    # Colapsează whitespace intern și face strip la capete
    return _WS_RE.sub(" ", v).strip()


class CategoryBase(BaseModel):
    """Câmpuri comune pentru categorie (create/read)."""
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)

    # Normalizează și validează `name`
    @field_validator("name")
    @classmethod
    def _name_normalize(cls, v: str) -> str:
        v = _norm_spaces(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    # Normalizează `description` ("" -> None; spații multiple -> un singur spațiu)
    @field_validator("description")
    @classmethod
    def _description_normalize(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _norm_spaces(v)
        return v or None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Arduino & Microcontrolere",
                    "description": "Plăci și accesorii pentru prototipare.",
                }
            ]
        },
    )


class CategoryCreate(CategoryBase):
    """Payload pentru creare categorie."""
    pass


class CategoryUpdate(BaseModel):
    """Payload pentru update; toate câmpurile sunt opționale."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def _name_normalize(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _norm_spaces(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description")
    @classmethod
    def _description_normalize(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _norm_spaces(v)
        return v or None


class CategoryRead(BaseModel):
    """Răspuns pentru categorie."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]


class CategoryPage(BaseModel):
    """Răspuns paginat pentru categorii."""
    items: list[CategoryRead]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
