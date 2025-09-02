# app/crud/category.py
from __future__ import annotations

from typing import Optional, Literal

from sqlalchemy import func, select, delete
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.category import Category, ProductCategory


# Excepție specifică pentru încălcarea unicității (lower(name))
class DuplicateCategoryNameError(Exception):
    """Ridicată când numele de categorie (case-insensitive) există deja."""
    pass


# -------------------------- Helpers --------------------------

def _normalize_pagination(page: int, page_size: int, *, max_size: int = 200) -> tuple[int, int]:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), max_size))
    return page, page_size


def _sanitize_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    name = name.strip()
    return name if name else None


# -------------------------- Reads / listing --------------------------

def list_categories(
    db: Session,
    *,
    name_contains: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    order_by: Literal["id", "name"] = "id",
    order: Literal["asc", "desc"] = "asc",
    with_products: bool = False,
) -> tuple[list[Category], int]:
    """
    Listează categorii cu filtrare case-insensitive după 'name', sortare și paginare.
    - with_products=True -> eager load cu selectinload(Category.products) dacă relația există.
    """
    page, page_size = _normalize_pagination(page, page_size)

    # Construim condițiile o singură dată (fără a accesa atribute private de pe Select)
    conditions = []
    if name_contains:
        conditions.append(func.lower(Category.name).like(f"%{name_contains.lower()}%"))

    # total count pe subquery simplu
    ids_q = select(Category.id).where(*conditions)
    total = int(db.execute(select(func.count()).select_from(ids_q.subquery())).scalar_one() or 0)

    # sortare stabilă
    sort_col = Category.id if order_by == "id" else Category.name
    sort_expr = sort_col.desc() if order == "desc" else sort_col.asc()

    stmt = select(Category).where(*conditions).order_by(sort_expr, Category.id.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size)

    if with_products and hasattr(Category, "products"):
        stmt = stmt.options(selectinload(Category.products))  # type: ignore[arg-type]

    items = db.execute(stmt).scalars().all()
    return items, total


def get(db: Session, category_id: int, *, with_products: bool = False) -> Optional[Category]:
    if with_products and hasattr(Category, "products"):
        stmt = select(Category).options(selectinload(Category.products)).where(Category.id == category_id)
        return db.execute(stmt).scalars().first()
    return db.get(Category, category_id)


def get_by_name_ci(db: Session, name: str) -> Optional[Category]:
    """Găsește categorie după nume (case-insensitive). Exploatează ix_categories_name_lower."""
    if not name:
        return None
    stmt = select(Category).where(func.lower(Category.name) == name.lower())
    return db.execute(stmt).scalar_one_or_none()


# -------------------------- Mutations --------------------------

def create(db: Session, data: dict) -> Category:
    # protecție app-level: unicitate case-insensitive + normalizare nume
    name = _sanitize_name(data.get("name"))
    if name is None:
        # lăsăm DB/Pydantic să valideze required, dar încercăm să fim expliciți
        raise IntegrityError("name is required", params=None, orig=None)  # type: ignore[arg-type]
    if get_by_name_ci(db, name):
        raise DuplicateCategoryNameError("Category name must be unique (case-insensitive).")

    obj = Category(name=name, description=data.get("description"))
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # dacă există UNIQUE index pe lower(name), mapăm la 409
        raise DuplicateCategoryNameError("Category name must be unique (case-insensitive).") from e
    db.refresh(obj)
    return obj


def update(db: Session, obj: Category, data: dict) -> Category:
    if "name" in data:
        new_name = _sanitize_name(data["name"])
        if new_name is not None:
            other = get_by_name_ci(db, new_name)
            if other and other.id != obj.id:
                raise DuplicateCategoryNameError("Category name must be unique (case-insensitive).")
            obj.name = new_name

    if "description" in data:
        # poate fi None => ștergere descriere
        obj.description = data["description"]

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise DuplicateCategoryNameError("Category name must be unique (case-insensitive).") from e
    db.refresh(obj)
    return obj


def delete(db: Session, obj: Category) -> None:
    db.delete(obj)
    db.commit()


# -------------------------- M2M helpers (attach/detach) --------------------------

def attach_product(db: Session, category_id: int, product_id: int) -> bool:
    """
    Atașează idempotent un product la categorie.
    Returnează True dacă legătura exista deja sau a fost creată; False dacă FK invalide.
    Folosește INSERT ... ON CONFLICT DO NOTHING pe PK compus (product_id, category_id).
    """
    t = ProductCategory.__table__
    try:
        db.execute(
            pg_insert(t)
            .values(product_id=product_id, category_id=category_id)
            .on_conflict_do_nothing(index_elements=["product_id", "category_id"])
        )
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        # cel mai probabil FK invalid (prod sau cat nu există)
        return False


def detach_product(db: Session, category_id: int, product_id: int) -> bool:
    """
    Șterge legătura (idempotent). Returnează True dacă a fost șters vreun rând.
    Încearcă DELETE core; la orice problemă, cade pe ștergere ORM.
    """
    t = ProductCategory.__table__
    # 1) încercare core (rapid)
    try:
        res = db.execute(
            delete(t)
            .where(t.c.product_id == product_id)
            .where(t.c.category_id == category_id)
        )
        db.commit()
        return bool(getattr(res, "rowcount", 0))
    except Exception:
        db.rollback()

    # 2) fallback ORM (sigur, dar un round-trip în plus)
    pc = db.execute(
        select(ProductCategory).where(
            ProductCategory.product_id == product_id,
            ProductCategory.category_id == category_id,
        )
    ).scalar_one_or_none()
    if not pc:
        return False
    db.delete(pc)
    db.commit()
    return True
