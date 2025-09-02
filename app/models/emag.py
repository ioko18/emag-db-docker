from __future__ import annotations
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional

Base = declarative_base()
SCHEMA = "app"

class Country(Base):
    __tablename__ = "countries"
    __table_args__ = {"schema": SCHEMA}
    code: Mapped[str] = mapped_column(primary_key=True)  # 'RO','BG','HU'
    name: Mapped[str]

class EmagAccount(Base):
    __tablename__ = "emag_accounts"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)       # 'main','fbe'
    name: Mapped[str]
    active: Mapped[bool] = mapped_column(server_default=text("true"))

class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    # unique(lower(name)) este în migrație

class ValidationStatus(Base):
    __tablename__ = "validation_status"
    __table_args__ = {"schema": SCHEMA}
    value: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str]

class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = {"schema": SCHEMA}
    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]

class EmagOffer(Base):
    __tablename__ = "emag_offers"
    __table_args__ = (
        UniqueConstraint("account_id", "country_code", "seller_sku", name="emag_offers_selleruniq"),
        UniqueConstraint("account_id", "country_code", "offer_id", name="emag_offers_offeriduniq"),
        {"schema": SCHEMA},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.emag_accounts.id", ondelete="RESTRICT"), index=True)
    country_code: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.countries.code", ondelete="RESTRICT"), index=True)
    offer_id: Mapped[Optional[int]]
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey(f"{SCHEMA}.products.id", ondelete="SET NULL"), index=True)
    seller_sku: Mapped[str]          # = part_number
    emag_sku: Mapped[Optional[str]]  # = part_number_key
    name: Mapped[Optional[str]]
    sale_price: Mapped[Optional[float]]
    currency: Mapped[Optional[str]]
    buy_button_rank: Mapped[Optional[int]]
    status: Mapped[Optional[int]]
    validation_status_value: Mapped[Optional[int]] = mapped_column(ForeignKey(f"{SCHEMA}.validation_status.value"))
    validation_status_text: Mapped[Optional[str]]
    handling_time: Mapped[Optional[int]]
    supply_lead_time: Mapped[Optional[int]]
    images_count: Mapped[Optional[int]]
    stock_total: Mapped[Optional[int]]
    general_stock: Mapped[Optional[int]]
    estimated_stock: Mapped[Optional[int]]
    raw: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[str]] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[Optional[str]] = mapped_column(server_default=text("now()"))

class EmagOfferImage(Base):
    __tablename__ = "emag_offer_images"
    __table_args__ = {"schema": SCHEMA}
    offer_pk: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.emag_offers.id", ondelete="CASCADE"), primary_key=True)
    pos: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str]

class EmagSkuMap(Base):
    __tablename__ = "emag_sku_map"
    __table_args__ = {"schema": SCHEMA}
    account_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.emag_accounts.id", ondelete="CASCADE"), primary_key=True)
    country_code: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.countries.code"), primary_key=True)
    seller_sku: Mapped[str] = mapped_column(primary_key=True)
    emag_sku: Mapped[str]
    updated_at: Mapped[Optional[str]] = mapped_column(server_default=text("now()"))

class EmagStockByWarehouse(Base):
    __tablename__ = "emag_stock_by_warehouse"
    __table_args__ = {"schema": SCHEMA}
    offer_pk: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.emag_offers.id", ondelete="CASCADE"), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.warehouses.code", ondelete="RESTRICT"), primary_key=True)
    qty: Mapped[int]
    updated_at: Mapped[Optional[str]] = mapped_column(server_default=text("now()"))
