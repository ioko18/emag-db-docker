# app/models.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base  # Base are metadata cu schema implicită

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(sa.String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    price: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(12, 2), nullable=True)

    # nou:
    sku: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True, index=True)

    def __repr__(self) -> str:  # opțional
        return f"<Product id={self.id} name={self.name!r} sku={self.sku!r}>"
