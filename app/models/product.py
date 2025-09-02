# app/models/product.py
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    """
    Model simplu pentru produse (schema: app).

    Note:
    - Fără index separat pe PK: Postgres creează implicit pentru PRIMARY KEY.
    - `name` rămâne NOT NULL + index btree clasic (`ix_products_name`) pentru ordine/filtrări.
    - `sku` este opțional; pe Postgres folosim index UNIC parțial doar pe valori non-NULL.
    - `price` permite NULL, dar când e setat trebuie să fie >= 0 (CHECK la nivel DB).
    - Legăm explicit de schema 'app' ca să evităm drift-ul când `search_path` se schimbă.
    """
    __tablename__ = "products"
    __table_args__ = (
        # 1) UNIC parțial pentru PostgreSQL; pe alte dialecte devine index normal
        Index(
            "ix_products_sku",
            "sku",
            unique=True,
            postgresql_where=text("sku IS NOT NULL"),
        ),
        # 2) BTREE pe preț (filtrări/sortări după preț)
        Index("ix_products_price", "price"),
        # 3) Index funcțional pentru căutări case-insensitive (LIKE pe lower(name))
        Index("ix_products_name_lower", func.lower(text("name"))),
        # 4) Constrângere: preț nenegativ când nu e NULL
        CheckConstraint("price IS NULL OR price >= 0", name="ck_products_price_nonnegative"),
        # 5) Leagă tabelul explicit de schema țintă
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # implicit: integer + PK
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        sku_val = getattr(self, "sku", None)
        # scurtează numele în repr pentru loguri mai curate
        name_preview = (self.name[:32] + "…") if self.name and len(self.name) > 33 else self.name
        return f"<Product id={self.id!r} name={name_preview!r} sku={sku_val!r}>"
