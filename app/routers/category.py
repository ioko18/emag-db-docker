# app/routers/category.py
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryRead,
    CategoryPage,
)
from app.crud import category as crud
from app.crud import product as product_crud  # pentru validarea product_id

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    response_model=CategoryPage,
    summary="List categories (filter/sort/paginate)",
)
def list_categories(
    response: Response,
    name: str | None = Query(
        default=None,
        min_length=1,
        description="Substring case-insensitive în name",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    order_by: Literal["id", "name"] = Query("id", description="Câmp de sortare"),
    order: Literal["asc", "desc"] = Query("asc", description="Direcție sortare"),
    with_products: bool = Query(
        False,
        description="Eager-load al relației products (selectinload)",
    ),
    db: Session = Depends(get_db),
):
    items, total = crud.list_categories(
        db,
        name_contains=name,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order,
        with_products=with_products,
    )
    # antet util pentru UI-uri/tabele
    response.headers["X-Total-Count"] = str(total)
    return CategoryPage(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Get category by id",
)
def get_category(category_id: int, db: Session = Depends(get_db)):
    obj = crud.get(db, category_id, with_products=False)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return obj


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    try:
        obj = crud.create(db, payload.model_dump(exclude_unset=True))
    except crud.DuplicateCategoryNameError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return obj


@router.put(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Update category",
)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)):
    obj = crud.get(db, category_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        obj = crud.update(db, obj, payload.model_dump(exclude_unset=True))
    except crud.DuplicateCategoryNameError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return obj


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete category",
)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    obj = crud.get(db, category_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    crud.delete(db, obj)
    return None


# ---------- M2M: attach / detach ----------

@router.post(
    "/{category_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Attach product to category (idempotent)",
    description="404 dacă Category sau Product nu există; 204 dacă legătura există deja sau a fost creată.",
)
def attach_product(category_id: int, product_id: int, db: Session = Depends(get_db)):
    # Validăm existența entităților pentru mesaje 404 clare
    cat = crud.get(db, category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    prod = product_crud.get(db, product_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    ok = crud.attach_product(db, category_id=category_id, product_id=product_id)
    if not ok:
        # Ar fi surprinzător aici (FK validate), dar păstrăm fallback
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attach failed.")
    return None


@router.delete(
    "/{category_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach product from category (idempotent)",
)
def detach_product(category_id: int, product_id: int, db: Session = Depends(get_db)):
    """
    Detach idempotent: întoarce 204 chiar dacă legătura nu exista.
    """
    crud.detach_product(db, category_id=category_id, product_id=product_id)
    return None
