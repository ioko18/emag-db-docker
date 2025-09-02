# app/crud/product.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple, Literal, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.models.category import ProductCategory  # pentru filtrare după categorie

OrderBy = Literal["id", "name", "price", "sku"]
OrderDir = Literal["asc", "desc"]


class DuplicateSKUError(Exception):
    """Ridicată când încalcă unicitatea SKU (partial unique WHERE sku IS NOT NULL)."""
    pass


def _normalize_pagination(page: int, page_size: int, *, max_size: int = 200) -> tuple[int, int]:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), max_size))
    return page, page_size


def _resolve_order(order_by: OrderBy, order_dir: OrderDir):
    """Mapează parametrii de sortare pe coloanele modelului."""
    col_map: Dict[str, object] = {
        "id": Product.id,
        "name": Product.name,
        "price": Product.price,
        "sku": Product.sku,
    }
    col = col_map.get(order_by, Product.id)
    return col.desc() if order_dir == "desc" else col.asc()


def list_products(
    db: Session,
    *,
    name_contains: Optional[str] = None,
    sku_prefix: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    category_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    order_by: OrderBy = "id",
    order_dir: OrderDir = "asc",
) -> Tuple[List[Product], int]:
    """
    Listează produse cu filtrare, paginare și sortare.

    Filtre:
      - name_contains: ILIKE pe lower(name) (exploatează ix_products_name_lower).
      - sku_prefix: ILIKE prefix (ignoră NULL implicit).
      - min_price/max_price: interval inclusiv.
      - category_id: filtrează produsele care aparțin unei categorii.

    Returnează: (items, total)
    """
    page, page_size = _normalize_pagination(page, page_size)

    # Construim condițiile explicit (ușurează calculul de total)
    conditions = []

    if name_contains:
        pattern = f"%{name_contains.lower()}%"
        conditions.append(func.lower(Product.name).like(pattern))

    if sku_prefix:
        # pentru indexuri parțiale (sku IS NOT NULL) e util să excludem NULL
        conditions.append(Product.sku.is_not(None))
        conditions.append(Product.sku.ilike(f"{sku_prefix}%"))

    if min_price is not None:
        conditions.append(Product.price >= min_price)

    if max_price is not None:
        conditions.append(Product.price <= max_price)

    base = select(Product)

    if category_id is not None:
        # join pe M2M când filtrăm după categorie
        base = base.join(
            ProductCategory,
            ProductCategory.product_id == Product.id,
        ).where(ProductCategory.category_id == category_id)

    if conditions:
        base = base.where(*conditions)

    # Total (folosim subquery doar pe ID-uri pentru planner prietenos)
    if conditions or category_id is not None:
        total_stmt = select(func.count()).select_from(
            select(Product.id).select_from(base.subquery()).subquery()
        )
    else:
        total_stmt = select(func.count(Product.id))

    total = db.scalar(total_stmt) or 0

    # Sortare + tiebreaker pe id pentru stabilitate
    order_clause = _resolve_order(order_by, order_dir)
    stmt = base.order_by(order_clause, Product.id.asc())

    # Paginare
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    items = db.execute(stmt).scalars().all()
    return items, int(total)


def get(db: Session, product_id: int) -> Optional[Product]:
    """Returnează produsul după ID (sau None)."""
    return db.get(Product, product_id)


def get_by_sku(db: Session, sku: str) -> Optional[Product]:
    """Returnează produsul după SKU (sau None)."""
    if not sku:
        return None
    q = select(Product).where(Product.sku == sku)
    return db.execute(q).scalar_one_or_none()


def create(db: Session, data: ProductCreate) -> Product:
    """
    Creează produs; ridică DuplicateSKUError pe conflict (ex. SKU duplicat non-NULL).
    """
    obj = Product(
        name=data.name,
        description=data.description,
        price=data.price,
        sku=data.sku,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # partial unique pe sku -> mapăm la excepție specifică
        raise DuplicateSKUError("SKU already exists.") from e
    db.refresh(obj)
    return obj


def update(db: Session, obj: Product, data: ProductUpdate) -> Product:
    """
    Actualizează câmpurile **furnizate** (inclusiv către None).
    Folosește model_dump(exclude_unset=True) ca să permită "clear" explicit (ex: description=None).
    """
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(obj, k, v)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise DuplicateSKUError("SKU already exists.") from e
    db.refresh(obj)
    return obj


def delete(db: Session, obj: Product) -> None:
    """Șterge un produs existent."""
    db.delete(obj)
    db.commit()


def delete_by_id(db: Session, product_id: int) -> bool:
    """Șterge produsul după ID. Returnează True dacă s-a șters ceva."""
    obj = get(db, product_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True
