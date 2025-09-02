# app/models/category.py
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Category(Base):
    """
    Tabelul 'app.categories'.
    - Unicitate case-insensitive pe nume via index funcțional (Postgres).
    - Schema 'app' setată explicit pentru stabilitatea autogenerate-ului.
    """
    __tablename__ = "categories"
    __table_args__ = (
        # Unicitate case-insensitive (PG): UNIQUE ON lower(name)
        Index("ix_categories_name_lower", func.lower(text("name")), unique=True),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        name_preview = (self.name[:32] + "…") if self.name and len(self.name) > 33 else self.name
        return f"<Category id={self.id!r} name={name_preview!r}>"


class ProductCategory(Base):
    """
    Tabelul M2M 'app.product_categories' (PK compus).
    - Păstrăm indexul existent pe category_id.
    - Adăugăm index compus (category_id, product_id) pentru interogări inverse eficiente.
    """
    __tablename__ = "product_categories"
    __table_args__ = (
        Index("ix_product_categories_category_id", "category_id"),
        Index("ix_product_categories_category_id_product_id", "category_id", "product_id"),
        {"schema": "app"},
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app.products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app.categories.id", ondelete="CASCADE"),
        primary_key=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProductCategory product_id={self.product_id} category_id={self.category_id}>"
