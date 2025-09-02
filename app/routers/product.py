# app/routers/product.py
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import product as crud
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    ProductPage,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=ProductPage,
    summary="List products with filtering, pagination & sorting",
)
def list_products(
    response: Response,
    name: str | None = Query(
        default=None,
        description="Substring (case-insensitive) to match in product name",
        min_length=1,
    ),
    sku_prefix: str | None = Query(
        default=None,
        description="Case-insensitive prefix for SKU",
        min_length=1,
        max_length=64,
    ),
    category_id: int | None = Query(
        default=None,
        description="Filter by category id (M2M)",
    ),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    order_by: Literal["id", "name", "price", "sku"] = Query(
        default="id", description="Sort key"
    ),
    order_dir: Literal["asc", "desc"] = Query(
        default="asc", description="Sort direction"
    ),
    db: Session = Depends(get_db),
):
    """
    Returnează produse paginate cu filtre opționale + sortare.
    - `name`: substring case-insensitive în `name`
    - `sku_prefix`: prefix case-insensitive pentru `sku`
    - `category_id`: filtrează produsele care aparțin unei categorii
    - `min_price`, `max_price`: interval de preț (inclusiv)
    - `order_by`: una dintre `id|name|price|sku`
    - `order_dir`: `asc|desc`
    """
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price cannot be greater than max_price.",
        )

    items, total = crud.list_products(
        db,
        name_contains=name,
        sku_prefix=sku_prefix,
        min_price=min_price,
        max_price=max_price,
        category_id=category_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order_dir=order_dir,
    )
    # Header util pentru UI-uri/tablere
    response.headers["X-Total-Count"] = str(total)
    return ProductPage(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Get a product by id",
)
def get_product(product_id: int, db: Session = Depends(get_db)):
    obj = crud.get(db, product_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return obj


@router.get(
    "/by-sku/{sku}",
    response_model=ProductRead,
    summary="Get a product by SKU",
)
def get_product_by_sku(sku: str, db: Session = Depends(get_db)):
    obj = crud.get_by_sku(db, sku)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return obj


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    try:
        obj = crud.create(db, payload)
    except crud.DuplicateSKUError as e:
        # index unic parțial: SKU duplicat când nu e NULL
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return obj


@router.put(
    "/{product_id}",
    response_model=ProductRead,
    summary="Update a product",
)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    obj = crud.get(db, product_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        obj = crud.update(db, obj, payload)
    except crud.DuplicateSKUError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return obj


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product",
)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    obj = crud.get(db, product_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    crud.delete(db, obj)
    return None
