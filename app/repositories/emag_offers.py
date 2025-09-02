from __future__ import annotations
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from typing import Optional, Iterable, Dict, Any

from app.models.emag import EmagOffer

def get_offer_by_key(db: Session, account_id: int, country_code: str, seller_sku: str) -> Optional[EmagOffer]:
    stmt = select(EmagOffer).where(
        EmagOffer.account_id == account_id,
        EmagOffer.country_code == country_code,
        EmagOffer.seller_sku == seller_sku,
    )
    return db.execute(stmt).scalars().first()

def upsert_offer(db: Session, payload: Dict[str, Any]) -> int:
    """Upsert atomic pe (account_id, country_code, seller_sku). Returnează PK-ul."""
    cols = {k: v for k, v in payload.items() if k in EmagOffer.__table__.c}
    stmt = pg_insert(EmagOffer).values(**cols)
    update_cols = {k: stmt.excluded[k] for k in cols.keys() if k not in ("id", "created_at")}
    stmt = stmt.on_conflict_do_update(
        index_elements=[EmagOffer.account_id, EmagOffer.country_code, EmagOffer.seller_sku],
        set_=update_cols,
    ).returning(EmagOffer.id)
    return db.execute(stmt).scalar_one()

