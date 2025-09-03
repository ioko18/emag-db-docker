# Code bundle — emag-db-docker

> Generat automat pentru depanare. Ordinea: cale relativă în repo.


# path-ul fisierului: .dockerignore  (size=1047 bytes)

```
# ========== VCS ==========
.git/
.gitignore
.gitattributes

# ========== Python ==========
__pycache__/
**/__pycache__/
*.py[cod]
*.pyo
*.pyd
*.egg-info/
.eggs/
pip-wheel-metadata/
build/
dist/
*.whl

# ========== Virtualenvs ==========
.venv/
venv/
.envrc

# ========== Test & Lint caches ==========
.pytest_cache/
.coverage*
coverage.xml
htmlcov/
.tox/
.nox/
.pyre/
.mypy_cache/
.ruff_cache/
.bandit

# ========== Editors / OS ==========
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp
*.swo
*~

# ========== Logs & temp ==========
logs/
*.log
tmp/
temp/
.cache/

# ========== Local data / DB artefacts ==========
*.db
*.sqlite
*.sqlite3
data/
storage/
uploads/

# ========== Node/Frontend (dacă apar) ==========
node_modules/
npm-debug.log*
yarn-error.log*

# ========== Docker/Compose & secrete ==========
docker-compose.override.yml
.env
.env.*
.secrets
*.secret

# ========== Keep: artefacte necesare build-ului ==========
!app/
!migrations/
!alembic.ini
!requirements.txt
!requirements-dev.txt
!docker/
!Dockerfile
!docker-compose.yml
!README*

```

# path-ul fisierului: .github/workflows/quick-check.yml  (size=4071 bytes)

```yaml
# .github/workflows/quick-check.yml
name: Quick Check

on:
  push:
    branches: ["**"]
  pull_request:

concurrency:
  group: quick-check-${{ github.ref }}
  cancel-in-progress: true

jobs:
  qc:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      # Asigură că .env există pentru docker compose (env_file: .env)
      - name: Ensure .env for Compose
        shell: bash
        run: |
          set -euo pipefail
          if [[ -f .env.ci ]]; then
            echo "[CI] Using .env.ci -> .env"
            cp .env.ci .env
          elif [[ -f .env.example ]]; then
            echo "[CI] Using .env.example -> .env"
            cp .env.example .env
          else
            echo "[CI] Creating minimal .env"
            {
              echo "# --- minimal CI defaults ---"
              echo "APP_PORT=8010"
              echo "DB_PORT=5434"
              echo "POSTGRES_DB=appdb"
              echo "POSTGRES_USER=appuser"
              echo "POSTGRES_PASSWORD=appsecret"
              echo "DB_SCHEMA=app"
            } > .env
          fi
          echo "[CI] .env ready:"
          sed -E 's/(POSTGRES_PASSWORD=).*/\1*** (redacted)/' .env || true

      # Buildx + cache (înlocuiește compose build)
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build app image (runtime) with cache
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          target: runtime
          tags: emagdb-app:latest          # trebuie să corespundă cu 'image:' din docker-compose.yml
          load: true                       # încarcă imaginea în daemon pentru compose
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            APP_UID=10001
            APP_GID=10001

      # Pornește serviciile fără rebuild (folosește imaginea deja construită)
      - name: Start compose (no build)
        shell: bash
        run: |
          set -euo pipefail
          docker compose up -d --no-build --force-recreate
          docker compose ps

      # STRICT doar pe main; psql are nevoie de PG* + PGPASSWORD.
      # Dezactivăm pager-ul și eliminăm PGOPTIONS (cauza erorii „invalid argument: -c”).
      - name: Quick check (STRICT on main)
        if: github.ref == 'refs/heads/main'
        shell: bash
        run: |
          set -euo pipefail
          set -a; source .env; set +a
          export PGPASSWORD="${POSTGRES_PASSWORD:-}"
          export PGHOST="${PGHOST:-127.0.0.1}"
          export PGPORT="${PGPORT:-${DB_PORT:-5434}}"
          export PGUSER="${PGUSER:-${POSTGRES_USER:-appuser}}"
          export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-appdb}}"
          export SMOKE_STRICT=1
          export PAGER=; export PSQL_PAGER=; unset PGOPTIONS
          make ci

      - name: Quick check
        if: github.ref != 'refs/heads/main'
        shell: bash
        run: |
          set -euo pipefail
          set -a; source .env; set +a
          export PGPASSWORD="${POSTGRES_PASSWORD:-}"
          export PGHOST="${PGHOST:-127.0.0.1}"
          export PGPORT="${PGPORT:-${DB_PORT:-5434}}"
          export PGUSER="${PGUSER:-${POSTGRES_USER:-appuser}}"
          export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-appdb}}"
          export PAGER=; export PSQL_PAGER=; unset PGOPTIONS
          make ci

      - name: Dump logs on failure
        if: failure()
        shell: bash
        run: |
          docker compose ps || true
          docker compose logs --no-color > compose.log || true
          echo "---- last 200 lines of logs ----"
          tail -n 200 compose.log || true

      - name: Upload logs artifact
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: compose-logs
          path: compose.log

      - name: Teardown
        if: always()
        shell: bash
        run: |
          [[ -f .env ]] || : > .env
          docker compose down -v --remove-orphans || true

```

# path-ul fisierului: .gitignore  (size=688 bytes)

```
# --- Python ---
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so

# --- Virtual envs ---
.venv/
venv/
env/
.python-version
.envrc

# --- Packaging / build artifacts ---
build/
dist/
*.egg-info/
.eggs/

# --- Caches ---
.pytest_cache/
.mypy_cache/
.ruff_cache/
.hypothesis/
.cache/

# --- Coverage ---
.coverage
.coverage.*
coverage.xml
htmlcov/

# --- Logs & runtime data ---
logs/
*.log
*.pid
tmp/
data/

# --- Local databases ---
*.sqlite
*.sqlite3
*.db

# --- Environment files (keep examples) ---
.env
.env.*
!.env.example
!.env.sample
!.env.template
!.env.local.example

# --- Docker / Compose ---
docker-compose.override.yml

# --- Editors / OS junk ---
.DS_Store
.idea/
.vscode/
Thumbs.db

```

# path-ul fisierului: .vscode/launch.json  (size=309 bytes)

```json
{
  "version": "0.2.0",
  "configurations": [
    
    {
      "name": "uvicorn (dev)",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8010"],
      "envFile": "${workspaceFolder}/.env",
      "justMyCode": true
    }
  ]
}

```

# path-ul fisierului: .vscode/settings.json  (size=1111 bytes)

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.envFile": "${workspaceFolder}/.env",

  // Pylance
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.autoImportCompletions": true,
  "python.analysis.inlayHints.variableTypes": true,
  "python.analysis.inlayHints.functionReturnTypes": true,

  // Teste
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.pytestArgs": ["-q"],

  // Formatare & imports
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
  },
  "isort.args": ["--profile", "black"],
  "python.sortImports.args": ["--profile", "black"],

  // Explorer mai curat
  "files.exclude": {
    "**/.venv": true,
    "**/__pycache__": true,
    "**/.pytest_cache": true
  },

  // Ajută la importuri relative când rulezi tool-uri din VS Code
  "terminal.integrated.env.osx": {
    "PYTHONPATH": "${workspaceFolder}"
  }
}

```

# path-ul fisierului: alembic.ini  (size=2053 bytes)

```ini
# Alembic config pentru proiect

[alembic]
# unde sunt scripturile de migrație
script_location = %(here)s/migrations

# asigură importul pachetelor din proiect (app/*)
prepend_sys_path = .

# prefixează fișierele de revizie cu data (ordine clară în PR-uri)
file_template = %%(year)d_%%(month).2d_%%(day).2d-%%(rev)s_%%(slug)s

# limitează lungimea slug-ului (evită nume de fișiere foarte lungi)
truncate_slug_length = 40

# separarea căilor depinde de OS
path_separator = os

# timestamp-urile din fișierele de migrație în UTC
timezone = UTC

# rulează env.py și la comanda "revision" (nu doar la "upgrade/downgrade")
revision_environment = true

# encoding pentru fișierele generate
output_encoding = utf-8

# URL-ul DB – lăsat gol intenționat; îl citește env.py din variabila de mediu DATABASE_URL
# Dacă vrei un fallback local, decomentează și setează:
# sqlalchemy.url = postgresql+psycopg2://appuser:appsecret@127.0.0.1:5434/appdb
sqlalchemy.url =

[post_write_hooks]
# Formatare automată cu black pentru fișierele nou generate (dacă black e instalat)
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -l 100 REVISION_SCRIPT_FILENAME

# (Opțional) Activează și ruff auto-fix dacă îl folosești.
# hooks = black,ruff
# ruff.type = console_scripts
# ruff.entrypoint = ruff
# ruff.options = --fix --exit-zero REVISION_SCRIPT_FILENAME

# -------------------------
# Logging
# -------------------------
[loggers]
keys = root, sqlalchemy, alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console

# Schimbă în INFO dacă vrei să vezi SQL-urile efective.
[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine
propagate = 1

[logger_alembic]
level = INFO
handlers = console
qualname = alembic
propagate = 0

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(asctime)s %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S

```

# path-ul fisierului: app/__init__.py  (size=67 bytes)

```python
# app/__init__.py
# Intenționat gol – marchează pachetul 'app'

```

# path-ul fisierului: app/core/logging.py  (size=396 bytes)

```python
import logging, sys

def setup_logging(level: str = "INFO"):
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)
    h = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    h.setFormatter(fmt)
    root.addHandler(h)

```

# path-ul fisierului: app/core/settings.py  (size=1103 bytes)

```python
from __future__ import annotations
from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    # App
    APP_ENV: str = Field("dev")
    OBS_KEY: Optional[str] = None

    # DB
    DATABASE_URL: st…******************************************************************************
    # eMAG accounts (placeholders)
    EMAG_MAIN_USERNAME: Optional[str] = None
    EMAG_MAIN_PASSWORD: Optional[str] = None
    EMAG_FBE_USERNAME: Optional[str] = None
    EMAG_FBE_PASSWORD: Optional[str] = None
    EMAG_PLATFORM_CODE_MAIN: str = "ro"
    EMAG_PLATFORM_CODE_FBE: str = "ro"

    # Offers toggles (aliniat cu contractul tău)
    EMAG_OFFERS_DEFAULT_LIMIT: int = 25
    EMAG_OFFERS_MAX_LIMIT: int = 50
    EMAG_OFFERS_DEFAULT_COMPACT: int = 1
    EMAG_OFFERS_DEFAULT_FIELDS: str = "id,sku,name,sale_price,stock_total"
    EMAG_OFFERS_RETURN_META: int = 0
    EMAG_OFFERS_STRICT_FILTER: int = 0
    EMAG_OFFERS_TOTAL_MODE: str = "upstream"  # upstream|filtered|both

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

```

# path-ul fisierului: app/crud/category.py  (size=6778 bytes)

```python
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

```

# path-ul fisierului: app/crud/product.py  (size=5615 bytes)

```python
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

```

# path-ul fisierului: app/database.py  (size=8275 bytes)

```python
# app/database.py
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, List

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

# Încarcă variabilele din .env (pe host). În Docker vin din env_file/environment.
load_dotenv()

# -----------------------------
# Helpers
# -----------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}

def _mask_url(url: str) -> str:
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest or ":" not in rest.split("@", 1)[0]:
        return url
    creds, tail = rest.split("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{tail}"

_IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]*"

def _sanitize_search_path(raw: str, fallback: str) -> str:
    """
    Acceptă doar identificatori ne-citați separați prin virgulă.
    Ex. 'app,public'. Dacă nu trece validarea, întoarce fallback.
    """
    if not raw:
        return fallback
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return fallback
    for p in parts:
        # nu permitem ghilimele duble sau caractere exotice
        # (dacă ai nevoie de identifer quoted, mai bine setezi prin config DSN)
        import re
        if not re.fullmatch(_IDENT_RE, p):
            return fallback
    # elimină duplicate păstrând ordinea
    seen = set()
    uniq: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return ",".join(uniq)

# -----------------------------
# Config din environment
# -----------------------------
DATABASE_URL = (o…************************************************************
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL este gol. Setează o valoare validă.")

DEFAULT_SCHEMA = (os.getenv("DB_SCHEMA", "app") or "app").strip()

# Logs SQL la nevoie: DB_ECHO=1 / true / yes / on
ECHO_SQL = _env_bool("DB_ECHO", False)

# Postgres: setări opționale
_raw_search_path = (os.getenv("DB_SEARCH_PATH", f"{DEFAULT_SCHEMA},public") or "").strip()
PG_SEARCH_PATH = _sanitize_search_path(_raw_search_path, f"{DEFAULT_SCHEMA},public")

PG_STATEMENT_TIMEOUT_MS = (os.getenv("DB_STATEMENT_TIMEOUT_MS") or "").strip()  # ex: "30000"
PG_APP_NAME = (os.getenv("DB_APPLICATION_NAME") or "").strip()

# Pooling
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # sec (30 min)
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))    # sec
POOL_USE_LIFO = _env_bool("DB_POOL_LIFO", True)

# Dacă rulezi prin pgbouncer (transaction pooling), de obicei vrei NullPool:
USE_NULLPOOL = _env_bool("DB_USE_NULLPOOL", False)

# Dezactivează pre_ping dacă e nevoie (ex. anumite setup-uri pgbouncer)
DISABLE_PRE_PING = _env_bool("DB_DISABLE_PRE_PING", False)

# Creează schema la pornire, dacă lipsește (util în dev/CI)
CREATE_SCHEMA_IF_MISSING = _env_bool("DB_CREATE_SCHEMA_IF_MISSING", False)

# -----------------------------
# Naming convention pentru Alembic/op.f()
# -----------------------------
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(schema=DEFAULT_SCHEMA, naming_convention=NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)  # schema implicită pentru toate modelele

# -----------------------------
# Engine factory
# -----------------------------
def _build_engine_kwargs() -> dict:
    kwargs: dict = {
        "echo": ECHO_SQL,
        "pool_pre_ping": not DISABLE_PRE_PING,
        "pool_use_lifo": POOL_USE_LIFO,
    }

    if DATABASE_URL.startswith("sqlite"):
        # SQLite: single-thread în driver → dezactivează check_same_thread
        kwargs["connect_args"] = {"check_same_thread": False}
        # In-memory → StaticPool (altfel fiecare conexiune are DB separat)
        if DATABASE_URL in {"sqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
        else:
            # Pentru fișiere, NullPool e ok (pooling are beneficii reduse la SQLite)
            kwargs["poolclass"] = NullPool
    else:
        # Postgres / MySQL
        if USE_NULLPOOL:
            kwargs["poolclass"] = NullPool
        else:
            kwargs.update(
                {
                    "pool_size": POOL_SIZE,
                    "max_overflow": MAX_OVERFLOW,
                    "pool_recycle": POOL_RECYCLE,
                    "pool_timeout": POOL_TIMEOUT,
                }
            )

        # ---- Postgres: libpq options (NU ca statements) ----
        pg_options = []
        if PG_SEARCH_PATH:
            pg_options.append(f"-c search_path={PG_SEARCH_PATH}")
        if PG_STATEMENT_TIMEOUT_MS.isdigit():
            pg_options.append(f"-c statement_timeout={PG_STATEMENT_TIMEOUT_MS}")

        if pg_options or PG_APP_NAME:
            kwargs.setdefault("connect_args", {})

        # Parametrii -c merg prin 'options' (nu apar în pg_stat_statements)
        if pg_options:
            existing_options = kwargs["connect_args"].get("options")
            opts = " ".join(pg_options)
            kwargs["connect_args"]["options"] = (
                f"{existing_options} {opts}".strip() if existing_options else opts
            )

        # application_name → parametru de conexiune (nu ca SET)
        if PG_APP_NAME:
            # atât psycopg2 cât și psycopg3 acceptă application_name în conninfo
            kwargs["connect_args"]["application_name"] = PG_APP_NAME

    return kwargs

engine: Engine = create_engine(DATABASE_URL, **_build_engine_kwargs())

# -----------------------------
# Session factory
# -----------------------------
# expire_on_commit=False → obiectele rămân utilizabile după commit (evită re-load imediat)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency pentru o sesiune SQLAlchemy închisă garantat.
    Face rollback automat dacă apare o excepție în request handler.
    """
    db: Session = SessionLocal()
    try:
        yield db
        # commit-ul e responsabilitatea endpoint-ului/serviciului;
        # dacă vrei auto-commit la finalul fiecărui request, îl poți face aici.
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager util în scripturi/servicii (non-FastAPI).
    Exemplu:
        with session_scope() as db:
            db.add(obj)
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _ensure_schema() -> None:
    """
    Creează schema DEFAULT_SCHEMA dacă lipsește (doar dacă DB_CREATE_SCHEMA_IF_MISSING=1).
    Alembic o poate crea și el; activarea acestui hook e utilă în dev/CI.
    """
    if CREATE_SCHEMA_IF_MISSING and DEFAULT_SCHEMA:
        with engine.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{DEFAULT_SCHEMA}"')

def init_db_if_requested() -> None:
    """
    Opțional: creează tabelele din modele când SQLALCHEMY_CREATE_ALL=1.
    Util în prototip/demo; în producție folosește Alembic.
    """
    _ensure_schema()
    if _env_bool("SQLALCHEMY_CREATE_ALL", False):
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=engine)

__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "session_scope",
    "init_db_if_requested",
]

```

# path-ul fisierului: app/docker/app-entrypoint.sh  (size=4145 bytes, exec)

```bash
# docker/app-entrypoint.sh
#!/usr/bin/env sh
set -eu

log() { printf >&2 '[%s] %s\n' "$(date +%FT%T%z)" "$*"; }
die() { log "FATAL: $*"; exit 1; }
istrue() {
  v="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "$v" in 1|true|t|yes|y|on) return 0;; *) return 1;; esac
}

# -------- defaults (aliniat cu docker-compose.yml) --------
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8001}"           # ✅ healthcheck-ul tău ascultă pe 8001
: "${UVICORN_WORKERS:=1}"
: "${APP_MODULE:=app.main:app}"
: "${APP_RELOAD:=0}"

: "${RUN_MIGRATIONS_ON_START:=1}"
: "${WAIT_FOR_DB:=auto}"            # auto | 1 | 0
: "${WAIT_RETRIES:=60}"
: "${WAIT_SLEEP_SECS:=1}"

: "${ALEMBIC_CONFIG:=/app/alembic.ini}"

# Siguranță pe FS read-only (evită .pyc)
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

show_env_summary() {
  log "App starting…"
  log " - APP_MODULE=$APP_MODULE  reload=${APP_RELOAD}  workers=${UVICORN_WORKERS}"
  log " - RUN_MIGRATIONS_ON_START=${RUN_MIGRATIONS_ON_START}"
  log " - WAIT_FOR_DB=${WAIT_FOR_DB}  retries=${WAIT_RETRIES}  sleep=${WAIT_SLEEP_SECS}s"
  log " - ALEMBIC_CONFIG=${ALEMBIC_CONFIG}"
  log " - DB_SCHEMA=${DB_SCHEMA:-app}  PGOPTIONS=${PGOPTIONS:-}"
}

wait_for_db() {
  # decide dacă așteptăm
  case "${WAIT_FOR_DB}" in
    0|false|no) log "WAIT_FOR_DB=${WAIT_FOR_DB} → nu aștept DB."; return 0;;
    auto) if ! istrue "${RUN_MIGRATIONS_ON_START}"; then
            log "WAIT_FOR_DB=auto & RUN_MIGRATIONS_ON_START!=1 → sar peste wait."; return 0
          fi ;;
  esac

  if [ -z "${DATABASE_URL:-}" ]; then
    log "DATABASE_URL este gol → nu aștept DB."
    return 0
  fi

  log "Aștept DB (cu psycopg SELECT 1; fallback TCP)…"
  # Folosim un script mic Python pentru retry/backoff
  # (suportă și DSN-uri SQLAlchemy gen postgresql+psycopg2://)
  python - <<'PY'
import os, sys, time, re, socket, urllib.parse
retries = int(os.getenv("WAIT_RETRIES", "60"))
sleep_s = float(os.getenv("WAIT_SLEEP_SECS", "1"))
url = os.getenv("DATABASE_URL")
if not url:
    sys.exit(0)

# normalizează dialectul pentru psycopg (postgresql://…)
pg_url = re.sub(r'^postgresql\+\w+://', 'postgresql://', url)

def tcp_ping(u: str) -> bool:
    p = urllib.parse.urlsplit(u)
    host, port = p.hostname or "db", int(p.port or 5432)
    s = socket.socket()
    s.settimeout(2.0)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

# încearcă cu psycopg dacă e disponibil
try:
    import psycopg
    for i in range(retries):
        try:
            with psycopg.connect(pg_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    sys.exit(0)
        except Exception:
            time.sleep(sleep_s)
    print("DB not reachable via psycopg after retries", file=sys.stderr)
    sys.exit(1)
except Exception:
    # fallback TCP
    for i in range(retries):
        if tcp_ping(pg_url):
            sys.exit(0)
        time.sleep(sleep_s)
    print("DB TCP not reachable after retries", file=sys.stderr)
    sys.exit(1)
PY
  log "DB este gata."
}

run_migrations() {
  if ! istrue "${RUN_MIGRATIONS_ON_START}"; then
    log "RUN_MIGRATIONS_ON_START=0 → sar peste migrații."
    return 0
  fi
  [ -f "${ALEMBIC_CONFIG}" ] || die "Lipsește ${ALEMBIC_CONFIG}"
  log "Rulez migrațiile Alembic…"
  alembic -c "${ALEMBIC_CONFIG}" upgrade head
  log "Migrațiile au fost aplicate."
}

start_uvicorn() {
  if istrue "${APP_RELOAD}"; then
    log "Pornesc Uvicorn în mod RELOAD…"
    exec python -m uvicorn "${APP_MODULE}" \
      --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" \
      --reload --reload-dir /app/app --proxy-headers --no-access-log
  else
    log "Pornesc Uvicorn (workers=${UVICORN_WORKERS})…"
    exec python -m uvicorn "${APP_MODULE}" \
      --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" \
      --workers "${UVICORN_WORKERS}" --proxy-headers --no-access-log
  fi
}

main() {
  show_env_summary
  wait_for_db
  run_migrations
  start_uvicorn
}

main "$@"

```

# path-ul fisierului: app/docker/initdb-test/00_schema.sql  (size=311 bytes)

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
    EXECUTE format('CREATE SCHEMA %I AUTHORIZATION %I', 'app', current_user);
  END IF;
END $$;

ALTER DATABASE appdb_test SET search_path = app, public;
ALTER ROLE appuser IN DATABASE appdb_test SET search_path = app, public;

```

# path-ul fisierului: app/docker/initdb/00_schema.sql  (size=295 bytes)

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
    EXECUTE format('CREATE SCHEMA app AUTHORIZATION %I', current_user);
  END IF;
END $$;

ALTER DATABASE appdb SET search_path = app, public;
ALTER ROLE appuser IN DATABASE appdb SET search_path = app, public;

```

# path-ul fisierului: app/integrations/emag_sdk.py  (size=20220 bytes)

```python
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import hashlib
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Callable, Awaitable, List

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

# =========================
# Config & constante
# =========================

EMAG_BASE_URLS = {
    "ro": os.getenv("EMAG_BASE_URL_RO", "https://marketplace-api.emag.ro/api-3"),
    "bg": os.getenv("EMAG_BASE_URL_BG", "https://marketplace-api.emag.bg/api-3"),
    "hu": os.getenv("EMAG_BASE_URL_HU", "https://marketplace-api.emag.hu/api-3"),
}

DEFAULT_CONNECT_TIMEOUT = float(os.getenv("EMAG_CONNECT_TIMEOUT_S", "10"))
DEFAULT_READ_TIMEOUT = float(os.getenv("EMAG_READ_TIMEOUT_S", "30"))
DEFAULT_HTTP2 = os.getenv("EMAG_HTTP2", "1").strip().lower() not in {"0", "false", "no"}

DEFAULT_UA = os.getenv("EMAG_USER_AGENT", f"emag-db-api/{os.getenv('APP_VERSION', 'unknown')}")
DEFAULT_ORDERS_RPS = int(os.getenv("EMAG_ORDERS_RPS", "12"))
DEFAULT_OTHER_RPS = int(os.getenv("EMAG_DEFAULT_RPS", "3"))

# Pool/keepalive (httpx)
MAX_CONNECTIONS = int(os.getenv("EMAG_MAX_CONNECTIONS", "20"))
MAX_KEEPALIVE = int(os.getenv("EMAG_MAX_KEEPALIVE", "10"))
KEEPALIVE_EXPIRY_S = float(os.getenv("EMAG_KEEPALIVE_EXPIRY_S", "60"))

# Logging flags
EMAG_HTTP_LOG = os.getenv("EMAG_HTTP_LOG", "").strip().lower() in {"1", "true", "yes", "on"}
# NOTE: ținem logurile concise (nu logăm body-uri complete în mod implicit)
logger_http = logging.getLogger("emag-db-api.emag_http")

# =========================
# Erori specifice
# =========================

class EmagRateLimitError(Exception):
    """429 sau throttling local."""
    pass


class EmagApiError(Exception):
    """Răspuns eMAG cu isError=true sau status != 2xx."""
    def __init__(self, message: str, status_code: int = 0, payload: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}

# =========================
# Modele config
# =========================

@dataclass(frozen=True)
class EmagAuth:
    username: str
    password: st…***
@dataclass(frozen=True)
class EmagConfig:
    account: str          # "main" | "fbe"
    country: str          # "ro" | "bg" | "hu"
    base_url: str
    auth: EmagAuth
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    read_timeout: float = DEFAULT_READ_TIMEOUT
    http2: bool = DEFAULT_HTTP2
    user_agent: str = DEFAULT_UA
    orders_rps: int = DEFAULT_ORDERS_RPS
    default_rps: int = DEFAULT_OTHER_RPS

# =========================
# Limiter per secundă
# =========================

class _PerSecondLimiter:
    """Limiter simplu: max N apeluri/1s per 'grup' (async-safe)."""
    def __init__(self):
        # group -> (deque of timestamps, limit)
        self._buckets: dict[str, Tuple[deque, int]] = {}
        self._lock = asyncio.Lock()

    def set_limit(self, group: str, rps: int):
        if group not in self._buckets:
            self._buckets[group] = (deque(), rps)
        else:
            q, _ = self._buckets[group]
            self._buckets[group] = (q, rps)

    async def acquire(self, group: str):
        # asigură existența bucket-ului
        if group not in self._buckets:
            self.set_limit(group, DEFAULT_OTHER_RPS)

        async with self._lock:
            q, limit = self._buckets[group]
            now = time.monotonic()
            # curățăm intrări mai vechi de 1s
            while q and now - q[0] >= 1.0:
                q.popleft()
            if len(q) >= limit and q:
                sleep_for = max(0.0, 1.0 - (now - q[0]))
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                # după sleep, curăță din nou
                now = time.monotonic()
                while q and now - q[0] >= 1.0:
                    q.popleft()
            q.append(time.monotonic())

# =========================
# Helpers diverse
# =========================

_LANG_BY_COUNTRY = {"ro": "ro_RO", "bg": "bg_BG", "hu": "hu_HU"}

def _derive_lang(cty: str) -> str:
    return _LANG_BY_COUNTRY.get(cty.lower(), "en_GB")


def _merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    out.update(b)
    return out


def _normalize_base_url(url: str) -> str:
    # asigurăm trailing slash, ca join-ul cu 'resource/action' (fără leading slash) să păstreze /api-3
    return url.rstrip("/") + "/"


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        # unele răspunsuri de eroare pot fi text/html
        return {"raw": resp.text, "status": resp.status_code}


def _is_success_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    # cel mai frecvent contract
    if payload.get("isError") is False:
        return True
    # fallback: dacă nu avem isError dar avem 'data' semnificativ
    if "isError" not in payload and "data" in payload:
        return True
    # alt fallback: unele endpoint-uri folosesc 'success' sau 'status' textual
    if payload.get("success") is True:
        return True
    return False


def _extract_error_details(payload: Any) -> Dict[str, Any]:
    """
    Normalizează câmpurile de eroare des întâlnite în răspunsurile eMAG.
    """
    if not isinstance(payload, dict):
        return {"raw": payload}
    details: Dict[str, Any] = {}
    for key in ("messages", "errors", "error", "message"):
        if key in payload and payload[key]:
            details[key] = payload[key]
    if "data" in payload and isinstance(payload["data"], dict):
        for key in ("errors", "messages"):
            if key in payload["data"] and payload["data"][key]:
                details[f"data.{key}"] = payload["data"][key]
    return details or payload


def make_idempotency_key(obj: Any) -> str:
    """
    Creează un idempotency key determinist din payload.
    Util când clientul nu furnizează unul explicit.
    """
    try:
        normalized = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    except Exception:
        normalized = str(obj)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

# =========================
# Client
# =========================

class EmagClient:
    """
    Client minimal pentru eMAG Marketplace.
    - Auth: Basic (httpx.BasicAuth) pe fiecare cerere.
    - Body: POST JSON (fără wrapper 'data')
    - Succes: payload.get("isError") == False OR ("isError" inexistent & "data" prezent)
    - Rate-limit local: 'orders' -> cfg.orders_rps; 'default' -> cfg.default_rps
    - Retry: httpx.HTTPError & EmagRateLimitError cu backoff + jitter (+ log înainte de retry)
    - Idempotency: header 'X-Idempotency-Key' (opțional)
    """

    def __init__(self, cfg: EmagConfig):
        self.cfg = cfg
        self._limiter = _PerSecondLimiter()
        self._limiter.set_limit("orders", cfg.orders_rps)
        self._limiter.set_limit("default", cfg.default_rps)

        # Fallback elegant la HTTP/1.1 dacă lipsește pachetul h2
        http2 = cfg.http2
        if http2:
            try:
                import h2  # noqa: F401
            except Exception:
                http2 = False  # dezactivează dacă nu e disponibil

        # IMPORTANT: setează toate cele 3 timeouts explicite + default (evită eroarea httpx)
        timeout = httpx.Timeout(
            timeout=self.cfg.read_timeout,      # default (safe fallback)
            connect=self.cfg.connect_timeout,
            read=self.cfg.read_timeout,
            write=self.cfg.read_timeout,
            pool=self.cfg.connect_timeout,
        )

        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE,
            keepalive_expiry=KEEPALIVE_EXPIRY_S,
        )

        self._client = httpx.AsyncClient(
            base_url=_normalize_base_url(cfg.base_url),
            timeout=timeout,
            http2=http2,
            limits=limits,
            headers=self._build_base_headers(cfg),
            auth=httpx.BasicAuth(cfg.auth.username, cfg.auth.password),
        )

    # --- context manager async ---
    async def __aenter__(self) -> "EmagClient":
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    # --- helpers ---

    def _build_base_headers(self, cfg: EmagConfig) -> Dict[str, str]:
        # Authorization e oferit de httpx.BasicAuth
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": cfg.user_agent,
            "Accept-Language": _derive_lang(cfg.country),
        }

    def _group_for(self, resource: str) -> str:
        r = resource.strip().lower()
        return "orders" if r in {"order", "orders"} else "default"

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, EmagRateLimitError)),
        wait=wait_exponential_jitter(initial=0.3, max=5.0),  # backoff + jitter
        stop=stop_after_attempt(5),
        reraise=True,
        before_sleep=before_sleep_log(logger_http, logging.WARNING),
    )
    async def _req_with_retry(
        self,
        fn: Callable[..., Awaitable[httpx.Response]],
        *args,
        **kwargs,
    ) -> httpx.Response:
        resp = await fn(*args, **kwargs)
        # 429 -> ridică EmagRateLimitError (tenacity va reîncerca)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    # limitează la max 10s ca să nu blocheze exagerat
                    delay = min(float(retry_after), 10.0)
                    await asyncio.sleep(delay)
                except ValueError:
                    pass
            raise EmagRateLimitError(
                f"Rate limited by eMAG (429). Retry-After={resp.headers.get('Retry-After')}"
            )
        # 204 -> considerăm succes "fără conținut"
        if resp.status_code == 204:
            return resp
        # 5xx -> httpx.raise_for_status() ridică HTTPStatusError (retry)
        if 500 <= resp.status_code:
            resp.raise_for_status()
        return resp

    async def _post(
        self,
        resource: str,
        action: str,
        data: dict,
        *,
        idempotency_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> dict:
        group = self._group_for(resource)
        await self._limiter.acquire(group)

        # IMPORTANT: fără leading slash; păstrăm /api-3 din base_url
        url = f"{resource.strip('/')}/{action.strip('/')}"
        req_id = os.urandom(12).hex()
        headers: Dict[str, str] = {"X-Request-Id": req_id}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        if extra_headers:
            headers = _merge_dicts(headers, extra_headers)

        started = time.perf_counter()
        if EMAG_HTTP_LOG:
            # ținem logul concis: metoda, url, grup, chei payload, are_idempotency
            logger_http.info(
                "POST %s group=%s rid=%s keys=%s idem=%s",
                url,
                group,
                req_id,
                ",".join(sorted(data.keys())),
                "yes" if "X-Idempotency-Key" in headers else "no",
            )

        resp = await self._req_with_retry(self._client.post, url, json=data, headers=headers)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if EMAG_HTTP_LOG:
            ra = resp.headers.get("Retry-After")
            srv_rid = resp.headers.get("X-Request-Id") or resp.headers.get("X-Request-ID")
            log_msg = (
                f"POST {url} -> {resp.status_code} in {elapsed_ms:.1f}ms "
                f"(retry_after={ra}, srv_rid={srv_rid}, cli_rid={req_id})"
            )
            if resp.status_code >= 400:
                logger_http.warning(log_msg)
            else:
                logger_http.info(log_msg)

        # 204 No Content -> succes “gol”
        if resp.status_code == 204:
            return {"isError": False, "data": None}

        # 4xx (≠429) -> EmagApiError (nu retry)
        if 400 <= resp.status_code < 500 and resp.status_code != 429:
            payload = _safe_json(resp)
            raise EmagApiError(
                f"eMAG API client error {resp.status_code} on {resource}/{action}",
                status_code=resp.status_code,
                payload=_extract_error_details(payload),
            )

        payload = _safe_json(resp)
        if _is_success_payload(payload):
            return payload

        # Nu e succes -> EmagApiError cu detalii
        raise EmagApiError(
            f"eMAG API error on {resource}/{action}",
            status_code=resp.status_code,
            payload=_extract_error_details(payload),
        )

    # ====== API helpers uzuale ======

    async def category_read(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        language: Optional[str] = None,
    ) -> dict:
        data: Dict[str, Any] = {"page": page, "limit": limit}
        data["language"] = language or _derive_lang(self.cfg.country)
        return await self._post("category", "read", data)

    async def product_offer_save(self, offer: dict, *, idempotency_key: Optional[str] = None) -> dict:
        # 'offer' trebuie să conțină câmpurile cerute de documentație
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(offer)
        return await self._post("product_offer", "save", offer, idempotency_key=idempotency_key)

    async def product_offer_read(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        status: Optional[int] = None,
        sku: Optional[str] = None,
        ean: Optional[str] = None,
        part_number_key: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Citește ofertele vânzătorului.
        Observație: contractul eMAG pentru filtrare poate varia; păstrăm top-level clasic
        (status/sku/ean/part_number_key) și permitem 'extra' pentru câmpuri suplimentare.
        """
        data: Dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            data["status"] = status
        if sku:
            data["sku"] = sku
        if ean:
            data["ean"] = ean
        if part_number_key:
            data["part_number_key"] = part_number_key
        if extra:
            data.update(extra)

        # idempotency e rar necesar pe read, dar acceptăm pentru simetrie
        return await self._post("product_offer", "read", data, idempotency_key=idempotency_key)

    async def offer_stock_update(
        self,
        *,
        item_id: int,
        warehouse_id: int,
        value: int,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        # actualizare rapidă de stoc (via product_offer/save)
        payload = {"id": item_id, "stock": [{"warehouse_id": warehouse_id, "value": value}]}
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(payload)
        return await self._post("product_offer", "save", payload, idempotency_key=idempotency_key)

    async def order_read(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        status: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> dict:
        data: Dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            data.setdefault("filters", {})["status"] = status
        if filters:
            data.setdefault("filters", {}).update(filters)
        return await self._post("order", "read", data)

    async def order_ack(self, order_ids: List[int], *, idempotency_key: Optional[str] = None) -> dict:
        data = {"orders": [{"id": oid} for oid in order_ids]}
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(data)
        return await self._post("order", "acknowledge", data, idempotency_key=idempotency_key)

    async def awb_save(
        self,
        *,
        order_id: int,
        courier: str,
        service: str,
        cod: bool = False,
        idempotency_key: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> dict:
        data = {
            "order_id": order_id,
            "courier": courier,
            "service": service,
            "cash_on_delivery": 1 if cod else 0,
        }
        if extra:
            data.update(extra)
        if idempotency_key is None:
            idempotency_key = make_idempotency_key(data)
        return await self._post("awb", "save", data, idempotency_key=idempotency_key)

    async def awb_read(self, awb_id: int, *, format_: str = "PDF") -> dict:
        data = {"id": awb_id, "format": format_}
        return await self._post("awb", "read", data)

    # Helper generic (pentru extensii ulterioare)
    async def call(self, resource: str, action: str, data: dict, *, idempotency_key: Optional[str] = None) -> dict:
        return await self._post(resource, action, data, idempotency_key=idempotency_key)

    # Conveniență: construiește clientul din ENV
    @classmethod
    def from_env(cls, account: str, country: str) -> "EmagClient":
        return cls(get_config_from_env(account, country))

# =========================
# Rezolvarea config din ENV
# =========================

def get_config_from_env(account: str, country: str) -> EmagConfig:
    """
    Rezolvă credențialele din ENV în ordinea:
      1) per-țară:   EMAG_{ACC}_{CTY}_{USER,PASS}
      2) per-cont:   EMAG_{ACC}_{USER,PASS}
      3) global:     EMAG_GLOBAL_{USER,PASS}
    + suprascrieri opționale pe timeouts/RPS/http2/user-agent cu aceeași ordine.
    """
    acc = account.strip().lower()   # "main" | "fbe"
    cty = country.strip().lower()   # "ro" | "bg" | "hu"

    if cty not in EMAG_BASE_URLS:
        raise RuntimeError(f"Țară invalidă pentru eMAG: {cty!r}")

    base_url = EMAG_BASE_URLS[cty]

    # Prefixuri pentru căutare
    p_country = f"EMAG_{acc.upper()}_{cty.upper()}"
    p_account = f"EMAG_{acc.upper()}"
    p_global = "EMAG_GLOBAL"
    prefixes = (p_country, p_account, p_global)

    def _get_first(suffix: str, default: Optional[str] = None) -> Optional[str]:
        for p in prefixes:
            v = os.getenv(f"{p}_{suffix}")
            if v is not None and v.strip() != "":
                return v.strip()
        return default

    user = _get_first("USER", "")
    pwd = _get_first("PASS", "")

    if not user or not pwd:
        raise RuntimeError(
            "Lipsește utilizatorul/parola eMAG. Setează fie EMAG_MAIN_USER/EMAG_MAIN_PASS sau EMAG_FBE_USER/EMAG_FBE_PASS, "
            "eventual override per țară (ex. EMAG_MAIN_RO_USER/EMAG_MAIN_RO_PASS)."
        )

    # Suprascrieri opționale
    connect_timeout = float(_get_first("CONNECT_TIMEOUT_S", str(DEFAULT_CONNECT_TIMEOUT)))
    read_timeout = float(_get_first("READ_TIMEOUT_S", str(DEFAULT_READ_TIMEOUT)))
    http2 = (_get_first("HTTP2", "1") or "1").lower() not in {"0", "false", "no"}
    user_agent = _get_first("USER_AGENT", DEFAULT_UA) or DEFAULT_UA

    try:
        orders_rps = int(_get_first("ORDERS_RPS", str(DEFAULT_ORDERS_RPS)))
    except Exception:
        orders_rps = DEFAULT_ORDERS_RPS
    try:
        default_rps = int(_get_first("DEFAULT_RPS", str(DEFAULT_OTHER_RPS)))
    except Exception:
        default_rps = DEFAULT_OTHER_RPS

    return EmagConfig(
        account=acc,
        country=cty,
        base_url=base_url,
        auth=EmagAuth(username=user, password=pwd),
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        http2=http2,
        user_agent=user_agent,
        orders_rps=orders_rps,
        default_rps=default_rps,
    )

```

# path-ul fisierului: app/main.py  (size=22964 bytes)

```python
# app/main.py
from __future__ import annotations

import os
import re
import time
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Sequence, cast, List, Tuple, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from app.database import get_db, SessionLocal
from app.routers.product import router as products_router           # required
from app.routers.category import router as categories_router        # required

# --- Config din ENV ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_TITLE = os.getenv("APP_TITLE", "emag-db-api")
ROOT_PATH = (os.getenv("ROOT_PATH", "").strip() or None)
DB_SCHEMA = os.getenv("DB_SCHEMA", "app")
ALEMBIC_VERSION_TABLE = os.getenv("ALEMBIC_VERSION_TABLE", "alembic_version")
ALEMBIC_INI = os.getenv("ALEMBIC_CONFIG", "/app/alembic.ini")
DISABLE_DOCS = os.getenv("DISABLE_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}
BUILD_SHA = os.getenv("GIT_SHA", "") or os.getenv("BUILD_SHA", "")

# Docs/OpenAPI URL overrides (opțional)
OPENAPI_URL = None if DISABLE_DOCS else os.getenv("OPENAPI_URL", "/openapi.json")
DOCS_URL = None if DISABLE_DOCS else os.getenv("DOCS_URL", "/docs")
REDOC_URL = None if DISABLE_DOCS else os.getenv("REDOC_URL", "/redoc")
OPENAPI_ADD_ROOT_SERVER = os.getenv("OPENAPI_ADD_ROOT_SERVER", "1").strip().lower() in {"1", "true", "yes", "on"}

# Securitate
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "").strip().lower() in {"1", "true", "yes", "on"}
OBS_KEY = os.getenv("OBS_KEY", "")  # dacă e setat, protejează prefixele de mai jos
OBS_PROTECT_PREFIXES = [p.strip() for p in os.getenv("OBS_PROTECT_PREFIXES", "/observability,/observability/v2").split(",") if p.strip()]

# Limitare body (bazată pe Content-Length, non-intruzivă)
try:
    MAX_BODY_SIZE_BYTES = int(os.getenv("MAX_BODY_SIZE_BYTES", "0"))  # 0 = dezactivat
except Exception:
    MAX_BODY_SIZE_BYTES = 0

APP_STARTED_MONO = time.monotonic()
APP_STARTED_TS = int(time.time())

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("emag-db-api")
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_name).setLevel(LOG_LEVEL)

tags_metadata = [
    {"name": "health", "description": "Liveness/Readiness checks"},
    {"name": "products", "description": "Product CRUD & search"},
    {"name": "categories", "description": "Category CRUD & linking"},
    {"name": "observability", "description": "DB & performance insights (pg_stat_statements)"},
    {"name": "integrations", "description": "Integrări externe (eMAG etc.)"},
]

# Observability: opțional (nu blocăm aplicația dacă fișierul lipsește)
observability_router = None
try:
    from app.routers.observability import router as observability_router  # type: ignore
except Exception as e:
    observability_router = None
    logger.warning("Observability router not loaded: %s", e)

# Observability v2 extins – opțional
observability_ext_router = None
try:
    from app.routers.observability_ext import router as observability_ext_router  # type: ignore
except Exception as e:
    observability_ext_router = None
    logger.info("Observability v2 router not loaded: %s", e)

# Integrare eMAG – opțional (prefixul este stabilit în app/routers/emag/__init__.py)
emag_router = None
try:
    from app.routers.emag import router as emag_router  # type: ignore
except Exception as e:
    emag_router = None
    logger.info("eMAG router not loaded: %s", e)

# Pentru mapare 409 la duplicate (SKU/nume categorie)
try:
    from app.crud.product import DuplicateSKUError  # type: ignore
except Exception:  # pragma: no cover
    class DuplicateSKUError(Exception):
        ...

try:
    from app.crud.category import DuplicateCategoryNameError  # type: ignore
except Exception:  # pragma: no cover
    class DuplicateCategoryNameError(Exception):
        ...

# --- Utilitare ---
_ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _safe_ident(name: str, fallback: str) -> str:
    if _ident_re.fullmatch(name or ""):
        return name
    logger.warning("Invalid SQL identifier from env: %r. Using fallback: %r", name, fallback)
    return fallback

DB_SCHEMA = _safe_ident(DB_SCHEMA, "app")
ALEMBIC_VERSION_TABLE = _safe_ident(ALEMBIC_VERSION_TABLE, "alembic_version")

def _get_req_id_from_headers(request: Request) -> str:
    # Prefer X-Request-ID, apoi X-Correlation-ID; dacă lipsesc, generează unul.
    return (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or uuid.uuid4().hex[:12]
    )

# --- Middleware func (registered after app is created) ---
async def request_context_mw(request: Request, call_next):
    """
    - Generează/propagă X-Request-ID
    - Aplică headers de securitate + HSTS (opțional)
    - Limitează mărimea corpului când Content-Length e disponibil
    - Server-Timing / X-Process-Time
    - (opțional) Protejează prefixe cu X-Obs-Key (ține cont de ROOT_PATH)
    """
    req_id = _get_req_id_from_headers(request)

    # Body-size guard (non-intruziv, pe Content-Length)
    if MAX_BODY_SIZE_BYTES > 0:
        cl = request.headers.get("content-length")
        try:
            if cl is not None and int(cl) > MAX_BODY_SIZE_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Payload too large", "max_bytes": MAX_BODY_SIZE_BYTES},
                    headers={"X-Request-ID": req_id},
                )
        except Exception:
            pass

    # Protecție X-Obs-Key (dacă OBS_KEY e setat). Ține cont de ROOT_PATH.
    if OBS_KEY:
        path = request.url.path
        root_prefix = ROOT_PATH or ""
        def _is_protected(p: str) -> bool:
            return path.startswith(p) or (root_prefix and path.startswith(f"{root_prefix.rstrip('/')}{p}"))
        if any(_is_protected(p) for p in OBS_PROTECT_PREFIXES):
            if request.headers.get("x-obs-key") != OBS_KEY:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Missing or invalid X-Obs-Key"},
                    headers={"X-Request-ID": req_id},
                )

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    # Security + perf headers
    response.headers.setdefault("X-Request-ID", req_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    # CSP minim care nu rupe API (și nici /docs când sunt activate)
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("X-App-Version", APP_VERSION)
    if ENABLE_HSTS:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")

    response.headers.setdefault("Server-Timing", f"app;dur={duration_ms:.1f}")
    response.headers.setdefault("X-Process-Time", f"{duration_ms:.1f}ms")
    return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: sanity check DB și configurație de migrații / search_path
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            sp = db.execute(text("SHOW search_path")).scalar_one()
            in_public = db.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            if in_public:
                logger.error("alembic_version prezent în schema PUBLIC! Verifică env.py și ALEMBIC_VERSION_TABLE_SCHEMA.")
            else:
                logger.info("alembic_version NU este în public (ok).")
            try:
                shared_libs = db.execute(text("SHOW shared_preload_libraries")).scalar_one()
                taqs = db.execute(text("SHOW track_activity_query_size")).scalar_one()
                logger.info(
                    "DB startup check OK (search_path=%s, schema=%s, version_table=%s, shared_preload_libraries=%s, track_activity_query_size=%s)",
                    sp, DB_SCHEMA, ALEMBIC_VERSION_TABLE, shared_libs, taqs
                )
            except Exception:
                logger.info("DB startup check OK (search_path=%s, schema=%s, version_table=%s)", sp, DB_SCHEMA, ALEMBIC_VERSION_TABLE)
            try:
                cfg = AlembicConfig(ALEMBIC_INI)
                script = ScriptDirectory.from_config(cfg)
                heads = list(script.get_heads())
                logger.info("Alembic heads: %s", heads or [])
            except Exception as e:
                logger.warning("Nu pot obține Alembic heads (%s): %s", ALEMBIC_INI, e)
    except Exception:
        logger.exception("DB startup check FAILED")

    if observability_router is None and observability_ext_router is None:
        logger.warning("Observability routers absente. Creează app/routers/observability*.py pentru /observability endpoints.")

    # Ready to serve
    yield

    # Shutdown: închide clienții eMAG cache-uiți (dacă există)
    try:
        from app.routers.emag.deps import close_emag_clients  # import lazy
        await close_emag_clients()
    except Exception as e:  # pragma: no cover
        logger.warning("While closing Emag clients on shutdown: %s", e)

# --- App factory (create app BEFORE registering middleware) ---
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    root_path=ROOT_PATH,
    docs_url=DOCS_URL,
    redoc_url=REDOC_URL,
    openapi_url=OPENAPI_URL,
)

# Register middleware now that app exists
app.middleware("http")(request_context_mw)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Trusted hosts (opțional): TRUSTED_HOSTS="localhost,127.0.0.1,.example.com"
_trusted = [h.strip() for h in os.getenv("TRUSTED_HOSTS", "").split(",") if h.strip()]
if _trusted:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=cast(Sequence[str], _trusted))  # type: ignore[arg-type]

# CORS din env: CORS_ORIGINS="http://localhost:3000,https://example.com"
_cors = os.getenv("CORS_ORIGINS")
if _cors:
    origins = [o.strip() for o in _cors.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Total-Count",
            "X-Request-ID",
            "Server-Timing",
            "X-Process-Time",
            "Content-Disposition",  # pt. download CSV/NDJSON
            "X-App-Version",
        ],
    )

# --- OpenAPI customization & caching ---
def _custom_openapi():
    """
    Generează schema OpenAPI on-demand și o cache-uiește.
    Opțional adaugă ROOT_PATH ca server → ajută tooling-ul din spatele unui reverse proxy.
    """
    if getattr(app, "openapi_schema", None):
        return app.openapi_schema
    schema = get_openapi(
        title=APP_TITLE,
        version=APP_VERSION,
        routes=app.routes,
        description=None,
    )
    if OPENAPI_ADD_ROOT_SERVER:
        rp = ROOT_PATH or ""
        if rp and rp != "/":
            schema["servers"] = [{"url": rp}]
    # Include build SHA în info.x-build-sha (dacă există)
    if BUILD_SHA:
        schema.setdefault("info", {})["x-build-sha"] = BUILD_SHA
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = _custom_openapi  # type: ignore[assignment]

# Alias stabil pentru /api/openapi.json (folosit în tool-urile tale)
if not DISABLE_DOCS and OPENAPI_URL != "/api/openapi.json":
    @app.get("/api/openapi.json", include_in_schema=False)
    def _openapi_alias():
        return JSONResponse(app.openapi())

# --- Exception handlers (ops-friendly) ---
@app.exception_handler(DuplicateSKUError)
async def _dup_sku_handler(request: Request, exc: DuplicateSKUError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

@app.exception_handler(DuplicateCategoryNameError)
async def _dup_category_handler(request: Request, exc: DuplicateCategoryNameError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

try:
    from sqlalchemy.exc import IntegrityError  # type: ignore
except Exception:  # pragma: no cover
    IntegrityError = Exception  # type: ignore[misc]

@app.exception_handler(IntegrityError)
async def _integrity_handler(request: Request, exc: IntegrityError):
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None)
    mapping = {
        "23505": (status.HTTP_409_CONFLICT, "Unique constraint violated."),
        "23503": (status.HTTP_409_CONFLICT, "Foreign key violation."),
        "23514": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Check constraint violated."),
        "23502": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Not-null constraint violated."),
        "22P02": (status.HTTP_400_BAD_REQUEST, "Invalid text representation."),
    }
    if pgcode in mapping:
        code, msg = mapping[pgcode]
        return JSONResponse(
            status_code=code,
            content={"detail": msg, "pgcode": pgcode},
            headers={"X-Request-ID": _get_req_id_from_headers(request)},
        )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Integrity error."},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

# Prinde 404/405 Starlette și răspunde JSON unitar
@app.exception_handler(StarletteHTTPException)
async def _starlette_http_exc_handler(request: Request, exc: StarletteHTTPException):
    headers = dict(exc.headers or {})
    headers.setdefault("X-Request-ID", _get_req_id_from_headers(request))
    detail = exc.detail
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        detail = {"message": "Not Found", "path": str(request.url.path)}
    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        detail = {"message": "Method Not Allowed", "path": str(request.url.path)}
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=headers)

@app.exception_handler(HTTPException)
async def _http_exc_handler(request: Request, exc: HTTPException):
    headers = dict(exc.headers or {})
    headers.setdefault("X-Request-ID", _get_req_id_from_headers(request))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

@app.exception_handler(Exception)
async def _unhandled_exc_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

# --- Helpers Alembic/health ---
def _get_db_alembic_version(db: Session) -> Tuple[Optional[str], bool]:
    try:
        version = db.execute(
            text(f'SELECT version_num FROM "{DB_SCHEMA}"."{ALEMBIC_VERSION_TABLE}"')
        ).scalar_one_or_none()
        return version, True
    except Exception:
        return None, False

def _get_pkg_alembic_heads() -> List[str]:
    cfg = AlembicConfig(ALEMBIC_INI)
    script = ScriptDirectory.from_config(cfg)
    return list(script.get_heads())

# --- Routes: health ---
@app.get("/", tags=["health"])
def root():
    payload = {"name": APP_TITLE, "version": APP_VERSION}
    if BUILD_SHA:
        payload["build_sha"] = BUILD_SHA
    return payload

@app.get("/__version__", tags=["health"])
def version_meta():
    payload = {"app_version": APP_VERSION, "started_at": APP_STARTED_TS}
    if BUILD_SHA:
        payload["build_sha"] = BUILD_SHA
    return payload

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

@app.get("/health/uptime", tags=["health"])
def health_uptime():
    return {"uptime_seconds": round(time.monotonic() - APP_STARTED_MONO, 3), "started_at": APP_STARTED_TS}

@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)):
    try:
        search_path = db.execute(text("SHOW search_path")).scalar_one()
        version = db.execute(text("SHOW server_version")).scalar_one()
        current_db = db.execute(text("SELECT current_database()")).scalar_one()
        current_user = db.execute(text("SELECT current_user")).scalar_one()
        application_name = db.execute(text("SHOW application_name")).scalar_one()
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "db": "up",
            "search_path": search_path,
            "server_version": version,
            "database": current_db,
            "user": current_user,
            "application_name": application_name,
        }
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DB not ready")

@app.get("/health/migrations", tags=["health"])
def health_migrations(db: Session = Depends(get_db)):
    version, present = _get_db_alembic_version(db)
    return {"alembic_version": version, "present": present}

@app.get("/health/migrations/status", tags=["health"])
def health_migrations_status(db: Session = Depends(get_db)):
    db_version, present = _get_db_alembic_version(db)
    try:
        heads = _get_pkg_alembic_heads()
    except Exception as e:  # pragma: no cover
        return {"db_version": db_version, "present": present, "pkg_heads_error": str(e), "in_sync": False if present else None}
    head = heads[0] if heads else None
    return {"db_version": db_version, "present": present, "pkg_heads": heads, "pkg_head": head, "in_sync": bool(db_version and head and db_version == head)}

@app.get("/health/ready", tags=["health"])
def health_ready(db: Session = Depends(get_db)):
    """
    Consideră aplicația ready dacă:
      - DB răspunde
      - tabelul alembic_version există în schema configurată
    """
    try:
        db.execute(text("SELECT 1"))
        present = db.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema=:s AND table_name=:t)"
            ),
            {"s": DB_SCHEMA, "t": ALEMBIC_VERSION_TABLE},
        ).scalar_one()
        if not present:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready (migrations table missing)")
        return {"ready": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready")

@app.get("/health/pg", tags=["health"])
def health_pg(db: Session = Depends(get_db)):
    tz = db.execute(text("SHOW TimeZone")).scalar_one()
    sv = db.execute(text("SHOW server_version")).scalar_one()
    sp = db.execute(text("SHOW search_path")).scalar_one()
    return {"server_version": sv, "timezone": tz, "search_path": sp}

@app.get("/health/extensions", tags=["health"])
def health_extensions(db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT e.extname, n.nspname AS schema
              FROM pg_extension e
              JOIN pg_namespace n ON n.oid = e.extnamespace
             WHERE e.extname IN ('pg_stat_statements','pg_trgm')
             ORDER BY e.extname;
        """)
    ).mappings().all()
    return {"extensions": [dict(r) for r in rows]}

@app.get("/health/settings", tags=["health"])
def health_settings(db: Session = Depends(get_db)):
    """Expune rapid setările cheie pentru observability."""
    settings = {}
    for key in (
        "shared_preload_libraries",
        "pg_stat_statements.max",
        "pg_stat_statements.save",
        "pg_stat_statements.track",
        "pg_stat_statements.track_utility",
        "track_activity_query_size",
    ):
        try:
            val = db.execute(text(f"SHOW {key}")).scalar_one()
            settings[key] = val
        except Exception:
            settings[key] = None
    return {"settings": settings}

@app.get("/health/schema", tags=["health"])
def health_schema(db: Session = Depends(get_db)):
    public_has = db.execute(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")).scalar_one()
    sp = db.execute(text("SHOW search_path")).scalar_one()
    ok_sp = sp.replace(" ", "").lower().startswith(f"{DB_SCHEMA},")
    return {"public_alembic_version_present": bool(public_has), "search_path": sp, "search_path_ok": ok_sp}

@app.get("/health/version", tags=["health"])
def health_version(db: Session = Depends(get_db)):
    v, present = _get_db_alembic_version(db)
    payload = {"app_version": APP_VERSION, "db_alembic_version": v, "version_table_present": present}
    if BUILD_SHA:
        payload["build_sha"] = BUILD_SHA
    return payload

# --- Routers ---
app.include_router(products_router)
app.include_router(categories_router)
if observability_router is not None:
    app.include_router(observability_router)
if observability_ext_router is not None:
    app.include_router(observability_ext_router)
if emag_router is not None:
    # IMPORTANT: emag_router are deja prefix intern "/integrations/emag" (în app/routers/emag/__init__.py).
    # Nu adăuga prefix aici ca să eviți dublarea!
    app.include_router(emag_router)

# asigură-te că schema OpenAPI se regenerează dacă a fost accesată prematur
app.openapi_schema = None  # invalidare cache, util dacă /openapi.json a fost cerut înainte de include_router

# dev-reload marker
# Tue Sep 2 09:00:00 EEST 2025

```

# path-ul fisierului: app/models.py  (size=799 bytes)

```python
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

```

# path-ul fisierului: app/models/__init__.py  (size=86 bytes)

```python
from .product import Product  # sau cum se numește modelul tău
__all__ = ["Product"]
```

# path-ul fisierului: app/models/category.py  (size=2043 bytes)

```python
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

```

# path-ul fisierului: app/models/emag.py  (size=4358 bytes)

```python
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

```

# path-ul fisierului: app/models/product.py  (size=2292 bytes)

```python
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

```

# path-ul fisierului: app/repositories/emag_offers.py  (size=1192 bytes)

```python
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


```

# path-ul fisierului: app/routers/__init__.py  (size=83 bytes)

```python
# app/routers/__init__.py
# Intenționat gol – marchează pachetul 'app.routers'

```

# path-ul fisierului: app/routers/category.py  (size=4834 bytes)

```python
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

```

# path-ul fisierului: app/routers/emag/__init__.py  (size=2025 bytes)

```python
# app/routers/emag/__init__.py
from __future__ import annotations

import logging
from fastapi import APIRouter

logger = logging.getLogger("emag-db-api.emag")

# IMPORTANT: setăm O SINGURĂ dată prefixul de top-level
router = APIRouter(prefix="/integrations/emag", tags=["emag"])

# Subrouterele NU trebuie să aibă prefixul /integrations/emag în ele.
# Fiecare definește doar propriile segmente (ex: "/product_offer/read").
from .offers_read import router as offers_read_router  # noqa: E402
from .offers_write import router as offers_write_router  # noqa: E402
from .orders import router as orders_router  # noqa: E402
from .awb import router as awb_router  # noqa: E402
from .categories import router as categories_router  # noqa: E402
from .characteristics import router as characteristics_router  # noqa: E402
from .meta import router as meta_router  # noqa: E402


def _warn_if_hardcoded_prefix(name: str, subrouter: APIRouter) -> None:
    """Avertizează dacă subrouterul are rute cu prefix hard-codat /integrations/emag."""
    bad_paths = []
    for r in getattr(subrouter, "routes", []):
        path = getattr(r, "path", "")
        if isinstance(path, str) and path.startswith("/integrations/emag"):
            bad_paths.append(path)
    if bad_paths:
        logger.warning(
            "Subrouter '%s' conține rute cu prefix hard-codat '/integrations/emag': %s. "
            "Elimină prefixul din subrouter (prefixul se aplică doar aici, în __init__).",
            name,
            ", ".join(bad_paths),
        )


# Include toate subrouterele (fără prefix suplimentar)
for name, sub in [
    ("offers_read", offers_read_router),
    ("offers_write", offers_write_router),
    ("orders", orders_router),
    ("awb", awb_router),
    ("categories", categories_router),
    ("characteristics", characteristics_router),
    ("meta", meta_router),
]:
    _warn_if_hardcoded_prefix(name, sub)
    router.include_router(sub)
    logger.info("Loaded eMAG subrouter: %s", name)

__all__ = ["router"]

```

# path-ul fisierului: app/routers/emag/awb.py  (size=1240 bytes)

```python
# app/routers/emag/awb.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, Path, Query
from .deps import emag_client_dependency
from .schemas import AwbSaveIn, AwbFormat
from .utils import call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/awb/save")
async def awb_save(
    payload: AwbSaveIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(
        client.awb_save,
        order_id=payload.order_id,
        courier=payload.courier,
        service=payload.service,
        cod=payload.cod,
        idempotency_key=idem,
    )

@router.get("/awb/{awb_id}")
async def awb_read(
    awb_id: Annotated[int, Path(ge=1, description="AWB ID (>0)")],
    awb_format: Annotated[AwbFormat, Query(alias="format", description="Format AWB (PDF/ZPL)")] = AwbFormat.PDF,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(client.awb_read, awb_id, format_=awb_format.value)

```

# path-ul fisierului: app/routers/emag/categories.py  (size=2252 bytes)

```python
# app/routers/emag/categories.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from .deps import emag_client_dependency
from .schemas import CategoriesIn
from .utils import LANG_BY_COUNTRY, call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/categories/read")
async def categories_read(
    payload: CategoriesIn,
    compact: Annotated[bool, Query(alias="compact", description="Returnează schema compactă {total,items}")] = False,
    fields: Annotated[Optional[str], Query(description="Listează câmpurile din items (ex: id,name,parent_id,leaf)")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    lang = payload.language or LANG_BY_COUNTRY.get(client.cfg.country, None)
    resp = await call_emag(client.category_read, page=payload.page, limit=payload.limit, language=lang)

    if not compact:
        return resp

    if isinstance(resp, list):
        data = resp
    elif isinstance(resp, dict):
        data = (
            resp.get("data")
            or resp.get("results")
            or resp.get("items")
            or (resp.get("payload") or {}).get("data")
            or (resp.get("response") or {}).get("data")
            or resp.get("categories")
            or []
        )
    else:
        data = []
    if not isinstance(data, list):
        data = []

    def _pick(d: dict, *keys):
        for k in keys:
            if k in d:
                return d[k]
        return None

    norm: list[dict[str, Any]] = []
    for it in data[: payload.limit]:
        item = {
            "id": _pick(it, "id", "category_id", "categoryId"),
            "name": _pick(it, "name", "label", "title"),
            "parent_id": _pick(it, "parent_id", "parentId", "parent_category_id", "parentCategoryId"),
            "leaf": _pick(it, "is_leaf", "leaf", "isLeaf"),
        }
        norm.append(item)

    if fields:
        allowed = {f.strip() for f in fields.split(",") if f.strip()}
        norm = [{k: v for k, v in it.items() if k in allowed} for it in norm]

    return {"total": len(data), "items": norm}

```

# path-ul fisierului: app/routers/emag/characteristics.py  (size=3020 bytes)

```python
# app/routers/emag/characteristics.py
from __future__ import annotations
from typing import Dict, List, Optional

from fastapi import APIRouter

from .schemas import (
    CharValidateIn, CharValidateOut, CharValidateOutItem,
    CharSchema
)
from .utils import (
    normalize_ws, infer_schema_from_allowed, match_exact_or_ci,
    match_quantitative, suggest
)

router = APIRouter()

_NUMERIC_SCHEMAS = {"mass", "length", "voltage", "noise"}

def _to_enum_or_none(name: Optional[str]) -> Optional[CharSchema]:
    if not name:
        return None
    try:
        return CharSchema(name)
    except Exception:
        return None

@router.post("/characteristics/validate-map", response_model=CharValidateOut)
async def characteristics_validate_map(payload: CharValidateIn) -> CharValidateOut:
    allowed_map: Dict[int, List[str]] = {a.characteristic_id: a.values for a in payload.allowed}

    results: List[CharValidateOutItem] = []
    for item in payload.items:
        char_id = item.characteristic_id
        value_in = normalize_ws(item.value)
        allowed = allowed_map.get(char_id, [])

        if not allowed:
            results.append(
                CharValidateOutItem(
                    characteristic_id=char_id,
                    input_value=value_in,
                    valid=False,
                    reason="Nu există o listă de valori permise pentru acest characteristic_id.",
                )
            )
            continue

        exact = match_exact_or_ci(value_in, allowed)
        if exact:
            results.append(
                CharValidateOutItem(
                    characteristic_id=char_id,
                    input_value=value_in,
                    valid=True,
                    matched_value=exact,
                    schema_used=item.schema_name,
                )
            )
            continue

        schema_name: Optional[str] = item.schema_name.value if item.schema_name else infer_schema_from_allowed(allowed)
        matched = None
        reason = None

        if schema_name in _NUMERIC_SCHEMAS:
            matched, reason = match_quantitative(value_in, allowed, schema_name)

        if matched:
            results.append(
                CharValidateOutItem(
                    characteristic_id=char_id,
                    input_value=value_in,
                    valid=True,
                    matched_value=matched,
                    schema_used=_to_enum_or_none(schema_name),
                )
            )
            continue

        suggestions = suggest(value_in, allowed, n=5) if allowed else None
        results.append(
            CharValidateOutItem(
                characteristic_id=char_id,
                input_value=value_in,
                valid=False,
                suggestions=suggestions,
                schema_used=_to_enum_or_none(schema_name),
                reason=reason or "Nu s-a găsit o potrivire în valorile permise.",
            )
        )

    return CharValidateOut(results=results)

```

# path-ul fisierului: app/routers/emag/deps.py  (size=2423 bytes)

```python
# app/routers/emag/deps.py
from __future__ import annotations

from typing import Annotated, AsyncIterator
from fastapi import HTTPException, Query, status


# Notă: NU importăm SDK-ul la nivel de modul ca să evităm circulare la import.
# Îl importăm în interiorul funcției de dependency.

_VALID_ACCOUNTS = frozenset({"main", "fbe"})
_VALID_COUNTRIES = frozenset({"ro", "bg", "hu"})


async def emag_client_dependency(
    account: Annotated[str, Query(description="Cont eMAG (main|fbe)")] = "main",
    country: Annotated[str, Query(description="Țara (ro|bg|hu)")] = "ro",
) -> AsyncIterator[object]:
    """
    Construieste un EmagClient pe baza variabilelor de mediu pentru (account, country).

    - Validează parametrii (422 la valori invalide).
    - Importă SDK-ul târziu (evită importuri circulare).
    - Închide clientul după finalizarea request-ului.
    """
    acct = (account or "").strip().lower()
    ctry = (country or "").strip().lower()

    if acct not in _VALID_ACCOUNTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid account: {acct!r}. Allowed: {sorted(_VALID_ACCOUNTS)}",
        )
    if ctry not in _VALID_COUNTRIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid country: {ctry!r}. Allowed: {sorted(_VALID_COUNTRIES)}",
        )

    # Import târziu ca să nu introducem dependențe de la import-time.
    try:
        from app.integrations.emag_sdk import EmagClient, get_config_from_env  # type: ignore
    except Exception as e:  # pragma: no cover
        # 500 - server misconfigured (nu găsim SDK)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import Emag SDK: {e}",
        )

    try:
        cfg = get_config_from_env(acct, ctry)
    except Exception as e:
        # 503 - lipsesc credențiale
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"eMAG credentials missing or invalid for account={acct}, country={ctry}: {e}",
        )

    client = EmagClient(cfg)
    try:
        yield client
    finally:
        try:
            await client.aclose()
        except Exception:
            # best-effort; nu mascăm excepții
            pass


__all__ = ("emag_client_dependency",)

```

# path-ul fisierului: app/routers/emag/meta.py  (size=873 bytes)

```python
# app/routers/emag/meta.py
from __future__ import annotations
from typing import Any, TYPE_CHECKING

from fastapi import APIRouter, Depends
from .deps import emag_client_dependency

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.get("/health")
async def health(client: "EmagClient" = Depends(emag_client_dependency)) -> dict[str, Any]:
    return {"ok": True, "account": client.cfg.account, "country": client.cfg.country, "base_url": client.cfg.base_url}

@router.get("/meta")
async def meta(client: "EmagClient" = Depends(emag_client_dependency)) -> dict[str, Any]:
    return {
        "account": client.cfg.account,
        "country": client.cfg.country,
        "base_url": client.cfg.base_url,
        "timeouts": {"connect": client.cfg.connect_timeout, "read": client.cfg.read_timeout},
    }

```

# path-ul fisierului: app/routers/emag/offers_read.py  (size=16247 bytes)

```python
# app/routers/emag/offers_read.py
from __future__ import annotations

import os
import csv
import io
import json
from typing import Any, Dict, List, Optional, Iterable, Tuple

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.routers.emag.deps import emag_client_dependency
from app.integrations.emag_sdk import EmagClient, EmagApiError

# IMPORTANT: prefixul /integrations/emag este aplicat în app/routers/emag/__init__.py
router = APIRouter(tags=["emag offers"])

# ==== ENV ====
DEFAULT_LIMIT = int(os.getenv("EMAG_OFFERS_DEFAULT_LIMIT", "25"))
MAX_LIMIT = int(os.getenv("EMAG_OFFERS_MAX_LIMIT", "50"))
DEFAULT_COMPACT = (os.getenv("EMAG_OFFERS_DEFAULT_COMPACT", "1").strip().lower()
                   not in {"0", "false", "no"})
DEFAULT_FIELDS_STR = os.getenv(
    "EMAG_OFFERS_DEFAULT_FIELDS",
    "id,sku,name,sale_price,stock_total",
)
RETURN_META_BY_DEFAULT = (os.getenv("EMAG_OFFERS_RETURN_META", "0").strip().lower()
                          not in {"0", "false", "no"})

# STRICT FILTER & TOTALS MODE
STRICT_FILTER = (os.getenv("EMAG_OFFERS_STRICT_FILTER", "").strip().lower()
                 not in {"", "0", "false", "no"})
TOTAL_MODE = os.getenv("EMAG_OFFERS_TOTAL_MODE", "upstream").strip().lower()
if TOTAL_MODE not in {"upstream", "filtered", "both"}:
    TOTAL_MODE = "upstream"

# câmpuri permise (inclusiv proiecții „flatten”)
ALLOWED_FIELDS: set[str] = {
    "id", "sku", "emag_sku", "name", "product_id", "category_id",
    "status", "status_text",
    "sale_price", "min_sale_price", "max_sale_price", "best_offer_sale_price",
    "currency", "vat_id", "handling_time",
    "ean", "ean_list", "part_number_key", "part_number",
    "general_stock", "estimated_stock", "stock_total",
    "warehouses", "stock_debug",
    "brand", "brand_name",
    "supply_lead_time",
    "validation_status_value", "validation_status_text",
    "images_count",
}
ALLOWED_SORT: set[str] = {"id", "sku", "name", "sale_price", "stock_total"}


def _safe_default_fields() -> str:
    req = [f.strip() for f in DEFAULT_FIELDS_STR.split(",") if f.strip()]
    valid = [f for f in req if f in ALLOWED_FIELDS]
    if not valid:
        valid = ["id", "sku", "name", "sale_price", "stock_total"]
    return ",".join(valid)


DEFAULT_FIELDS = _safe_default_fields()


def _project_item(item: Dict[str, Any], fields: Optional[List[str]]) -> Dict[str, Any]:
    if not fields:
        return item
    return {k: item.get(k) for k in fields}


def _flatten(it: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact=1: normalizează câteva câmpuri comune.
    - sku              := part_number (seller SKU)
    - emag_sku         := part_number_key (eMAG SKU)
    - ean              := primul din listă (dacă e listă) sau stringul direct
    - ean_list         := lista completă (dacă există)
    - handling_time    := handling_time[0].value (dacă există)
    - supply_lead_time := offer_details.supply_lead_time
    - validation_status_{value,text} := din validation_status[0]
    - images_count     := len(images)
    - stock_total      := fallback din stock[0].value / general_stock / estimated_stock dacă lipsește
    """
    out = dict(it)

    # SKU semantici
    out["sku"] = it.get("part_number")           # seller SKU
    out["emag_sku"] = it.get("part_number_key")  # eMAG SKU

    # EAN
    ean_val = None
    ean_list = it.get("ean")
    if isinstance(ean_list, list):
        out["ean_list"] = ean_list
        if ean_list:
            ean_val = ean_list[0]
    elif isinstance(ean_list, str):
        ean_val = ean_list
    if ean_val is not None:
        out["ean"] = ean_val

    # handling_time
    ht = it.get("handling_time")
    if isinstance(ht, list) and ht and isinstance(ht[0], dict):
        out["handling_time"] = ht[0].get("value")

    # supply_lead_time
    od = it.get("offer_details") or {}
    if isinstance(od, dict):
        out["supply_lead_time"] = od.get("supply_lead_time")

    # validation_status
    vs = it.get("validation_status")
    if isinstance(vs, list) and vs and isinstance(vs[0], dict):
        out["validation_status_value"] = vs[0].get("value")
        out["validation_status_text"] = vs[0].get("description")

    # images_count
    imgs = it.get("images")
    if isinstance(imgs, list):
        out["images_count"] = len(imgs)

    # stock_total fallback
    if out.get("stock_total") is None:
        st_list = it.get("stock")
        st_val = None
        if isinstance(st_list, list) and st_list and isinstance(st_list[0], dict):
            st_val = st_list[0].get("value")
        if st_val is None:
            st_val = it.get("general_stock")
        if st_val is None:
            st_val = it.get("estimated_stock")
        out["stock_total"] = st_val

    return out


def _iter_ndjson(items: Iterable[Dict[str, Any]]) -> Iterable[bytes]:
    for row in items:
        yield (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")


def _csv_response(fields: List[str], rows: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    # folosim lineterminator="\n" ca să evităm CRLF și surprize în testele cu `grep -x`
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        w.writerow([r.get(col) for col in fields])
    data = buf.getvalue().encode("utf-8")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(data), media_type="text/csv; charset=utf-8", headers=headers)



def _strict_match(
    flat: Dict[str, Any],
    sku: Optional[str],
    part_number_key: Optional[str],
    ean: Optional[str],
) -> bool:
    """AND pe toate filtrele prezente."""
    if sku is not None and flat.get("sku") != sku:
        return False
    if part_number_key is not None and flat.get("emag_sku") != part_number_key:
        return False
    if ean is not None:
        ean_ok = False
        if flat.get("ean") == ean:
            ean_ok = True
        else:
            lst = flat.get("ean_list") or []
            if isinstance(lst, list) and ean in lst:
                ean_ok = True
        if not ean_ok:
            return False
    return True


# ---------- modele I/O (fără validatori pydantic – validăm explicit în endpoint) ----------
class OffersReadQuery(BaseModel):
    account: str = Field(..., description="Cont configurat (ex: main, fbe)")
    country: str = Field(..., description="Țara eMAG (ro|bg|hu)")
    compact: bool = Field(default=DEFAULT_COMPACT, description="Proiectează câmpurile (flatten) și folosește `fields`.")
    items_only: bool = Field(default=False, description="Dacă e 1, întoarce doar `items`.")
    fields: Optional[str] = Field(default=DEFAULT_FIELDS, description="Listă separată prin virgulă (ordinea e păstrată la CSV).")
    sort: Optional[str] = Field(default=None, description="Ex: name, -sale_price, stock_total")
    # export
    format: Optional[str] = Field(default=None, description="Format export: json|csv|ndjson")
    filename: Optional[str] = Field(default=None, description="Numele fișierului la export (ex: offers.csv)")


class OffersReadBody(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    status: Optional[int] = None
    # IMPORTANT: sku == part_number (seller SKU)
    sku: Optional[str] = Field(None, description="Filtrează după seller SKU (eMAG `part_number`).")
    # Compatibilitate: acceptăm și `part_number` (deprecated) => mapăm la `sku` dacă e folosit.
    part_number: Optional[str] = Field(
        None,
        description="DEPRECATED alias pentru `sku` (seller SKU / eMAG `part_number`). Folosește `sku`.",
    )
    ean: Optional[str] = None
    # eMAG SKU (alias intern): part_number_key
    part_number_key: Optional[str] = Field(None, description="Filtru după eMAG SKU (`part_number_key`).")
    extra: Optional[Dict[str, Any]] = None


# ---------- validări explicite (independente de versiunea Pydantic) ----------
def _parse_fields(fields_str: Optional[str]) -> Optional[List[str]]:
    if not fields_str:
        return None
    req = [p.strip() for p in fields_str.split(",") if p.strip()]
    invalid = [f for f in req if f not in ALLOWED_FIELDS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown field(s): {', '.join(invalid)}. Allowed: {', '.join(sorted(ALLOWED_FIELDS))}",
        )
    return req


def _parse_sort(sort_expr: Optional[str]) -> Optional[str]:
    if not sort_expr:
        return None
    desc = sort_expr.startswith("-")
    key = sort_expr[1:] if desc else sort_expr
    if key not in ALLOWED_SORT:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort: {sort_expr!r}. Allowed: {', '.join(sorted(ALLOWED_SORT))} (prefix '-' for desc).",
        )
    return sort_expr


def _parse_format(fmt: Optional[str]) -> Optional[str]:
    if not fmt:
        return None
    fmt2 = fmt.lower()
    if fmt2 not in {"json", "csv", "ndjson"}:
        raise HTTPException(status_code=422, detail="format must be one of: json, csv, ndjson")
    return fmt2


@router.post(
    "/product_offer/read",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "filter_by_sku": {
                            "summary": "Filtrare după seller SKU (part_number)",
                            "value": {"page": 1, "limit": 5, "sku": "ADS206"},
                        },
                        "filter_by_emag_sku": {
                            "summary": "Filtrare după eMAG SKU (part_number_key)",
                            "value": {"page": 1, "limit": 5, "part_number_key": "DL0WVYYBM"},
                        },
                        "export_minimal_csv": {
                            "summary": "Export CSV (câmpuri minimale)",
                            "value": {"page": 1, "limit": 10},
                        },
                    }
                }
            }
        }
    },
)
async def product_offer_read(
    q: OffersReadQuery = Depends(),
    body: OffersReadBody = Body(...),
    client: EmagClient = Depends(emag_client_dependency),
    debug: bool = Query(False, description="Include meta de debug"),
):
    """
    Passthrough + UX local:
    - validare fields/sort/format (422, mesaj clar)
    - filtrare strictă opțională (ENV) înainte de sort+pagina­re
    - sort înainte de paginare (determinist)
    - compact + fields
    - export CSV/NDJSON
    - semantici: `sku` = part_number (seller), `emag_sku` = part_number_key (eMAG)
    """
    # Validări explicite pentru query
    fields_list = _parse_fields(q.fields)
    sort_expr = _parse_sort(q.sort)
    fmt = _parse_format(q.format)

    try:
        # === build payload upstream ===
        payload: Dict[str, Any] = {"page": body.page, "limit": body.limit}
        if body.status is not None:
            payload["status"] = body.status

        # compat: dacă user a trimis `part_number` dar nu `sku`, mapăm la `sku`
        eff_sku = body.sku or body.part_number  # seller SKU
        if eff_sku:
            payload["sku"] = eff_sku  # SDK așteaptă 'sku' (mapat intern la eMAG part_number)

        if body.ean:
            payload["ean"] = body.ean
        if body.part_number_key:
            payload["part_number_key"] = body.part_number_key  # eMAG SKU
        if body.extra:
            payload.update(body.extra)

        # apel SDK
        resp = await client.product_offer_read(
            page=payload["page"],
            limit=payload["limit"],
            status=payload.get("status"),
            sku=payload.get("sku"),
            ean=payload.get("ean"),
            part_number_key=payload.get("part_number_key"),
            extra=body.extra,
        )
    except EmagApiError as e:
        status_code = e.status_code or 502
        detail = {"message": "eMAG API error", "status_code": e.status_code, "details": e.payload}
        raise HTTPException(status_code=status_code if 400 <= status_code < 500 else 502, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"message": "Upstream error", "error": str(e)})

    # Normalizează lista de oferte
    raw_items: List[Dict[str, Any]] = (
        resp.get("data")
        or resp.get("results")
        or resp.get("items")
        or (resp.get("payload", {}) or {}).get("data")
        or (resp.get("response", {}) or {}).get("data")
        or resp.get("offers")
        or []
    )
    if not isinstance(raw_items, list):
        raw_items = []

    # perechi (raw, flat) → sortăm după flat, returnăm raw/flat în funcție de compact
    pairs_all: List[Tuple[Dict[str, Any], Dict[str, Any]]] = [(it, _flatten(it)) for it in raw_items]

    # filtrare strictă locală (dacă e activată din ENV)
    if STRICT_FILTER:
        pairs_use = [
            p for p in pairs_all
            if _strict_match(p[1], eff_sku, body.part_number_key, body.ean)
        ]
    else:
        pairs_use = pairs_all

    # sort (cheie în flat; susține 'sku', etc.)
    if sort_expr:
        desc = sort_expr.startswith("-")
        key = sort_expr[1:] if desc else sort_expr
        def _k(p: Tuple[Dict[str, Any], Dict[str, Any]]):
            v = p[1].get(key)  # ia din flat
            return (v is None, v)
        pairs_use.sort(key=_k, reverse=desc)

    # paginare
    start = (body.page - 1) * body.limit
    end = start + body.limit
    if len(pairs_use) > body.limit:
        sliced_pairs = pairs_use[start:end] if start < len(pairs_use) else []
    else:
        sliced_pairs = pairs_use[: body.limit]

    # alege reprezentarea în funcție de compact
    items: List[Dict[str, Any]] = [fp if q.compact else rp for (rp, fp) in sliced_pairs]

    # proiecție pe fields
    if fields_list:
        items = [_project_item(it, fields_list) for it in items]

    # total upstream și total filtrat (pe lista completă din răspuns)
    upstream_total = resp.get("total")
    if not isinstance(upstream_total, int):
        upstream_total = resp.get("count") or len(raw_items)
    upstream_total = int(upstream_total or 0)
    filtered_total = len(pairs_use)

    # alegerea totalului expus
    if TOTAL_MODE == "filtered":
        total = filtered_total
    else:  # "upstream" sau "both" (compat – total = upstream)
        total = upstream_total

    # === Export? ===
    if fmt in {"csv", "ndjson"}:
        if fmt == "csv":
            cols = fields_list or ["id", "sku", "name", "sale_price", "stock_total"]
            fname = q.filename or "offers.csv"
            return _csv_response(cols, items, fname)
        else:
            headers = {}
            if q.filename:
                headers["Content-Disposition"] = f'attachment; filename="{q.filename}"'
            return StreamingResponse(_iter_ndjson(items), media_type="application/x-ndjson", headers=headers)

    # JSON normal
    out: Dict[str, Any] = {"total": total, "items": items}
    if q.items_only:
        out = {"items": items}

    if debug or RETURN_META_BY_DEFAULT:
        meta: Dict[str, Any] = {
            "page": body.page,
            "requested_limit": body.limit,
            "max_limit": MAX_LIMIT,
            "returned_raw_len": len(raw_items),
            "sliced": len(pairs_use) > body.limit,
            "compact": q.compact,
            "fields": fields_list,
            "sku_semantics": {
                "sku": "part_number",           # seller SKU
                "emag_sku": "part_number_key",  # eMAG SKU
            },
            "strict_filter": STRICT_FILTER,
            "total_mode": TOTAL_MODE,
            "total_upstream": upstream_total,
            "total_filtered": filtered_total,
        }
        out["meta"] = meta

        # opțional: în modul "both", expune ambele totaluri și în root (în plus față de meta)
        if TOTAL_MODE == "both":
            out["total_upstream"] = upstream_total
            out["total_filtered"] = filtered_total

    return JSONResponse(out)

```

# path-ul fisierului: app/routers/emag/offers_write.py  (size=1235 bytes)

```python
# app/routers/emag/offers_write.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Header
from .deps import emag_client_dependency
from .schemas import ProductOfferSaveIn, OfferStockUpdateIn
from .utils import call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/product_offer/save")
async def product_offer_save(
    payload: ProductOfferSaveIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(client.product_offer_save, payload.model_dump(), idempotency_key=idem)

@router.post("/offer/stock-update")
async def offer_stock_update(
    payload: OfferStockUpdateIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(
        client.offer_stock_update,
        item_id=payload.id,
        warehouse_id=payload.warehouse_id,
        value=payload.value,
        idempotency_key=idem,
    )

```

# path-ul fisierului: app/routers/emag/orders.py  (size=1102 bytes)

```python
# app/routers/emag/orders.py
from __future__ import annotations
from typing import Any, Optional, Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Header
from .deps import emag_client_dependency
from .schemas import OrdersReadIn, OrdersAckIn, OrderStatus
from .utils import call_emag

if TYPE_CHECKING:
    from app.integrations.emag_sdk import EmagClient  # only for typing

router = APIRouter()

@router.post("/orders/read")
async def orders_read(
    payload: OrdersReadIn,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    status_int = int(payload.status) if isinstance(payload.status, OrderStatus) else payload.status
    return await call_emag(client.order_read, page=payload.page, limit=payload.limit, status=status_int)

@router.post("/orders/ack")
async def orders_ack(
    payload: OrdersAckIn,
    idem: Annotated[Optional[str], Header(alias="X-Idempotency-Key")] = None,
    client: "EmagClient" = Depends(emag_client_dependency),
) -> dict[str, Any]:
    return await call_emag(client.order_ack, payload.order_ids, idempotency_key=idem)

```

# path-ul fisierului: app/routers/emag/schemas.py  (size=9237 bytes)

```python
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------- Enum-uri de bază ----------
class Account(str, Enum):
    main = "main"
    fbe = "fbe"


class Country(str, Enum):
    ro = "ro"
    bg = "bg"
    hu = "hu"


class OrderStatus(int, Enum):
    canceled = 0
    new = 1
    in_progress = 2
    prepared = 3
    finalized = 4
    returned = 5


class AwbFormat(str, Enum):
    PDF = "PDF"
    ZPL = "ZPL"


class CharSchema(str, Enum):
    mass = "mass"          # g, Kg
    length = "length"      # nm, mm, cm, m, inch
    voltage = "voltage"    # µV, V, kV, MV
    noise = "noise"        # dB
    integer = "integer"
    text = "text"
    range_text = "range_text"  # ex: "0 - 10 mm"


# ---------- Input/Output Models (categorii / produse) ----------
class CategoriesIn(BaseModel):
    page: int = Field(1, ge=1, description="Pagina (>=1)")
    limit: int = Field(100, ge=1, le=4000, description="Câte elemente/pagină (1..4000)")
    language: Optional[str] = Field(
        None, description="Locale eMAG (ex. ro_RO / bg_BG / hu_HU / en_GB). Dacă lipsește, se deduce din țară."
    )

    @field_validator("language")
    @classmethod
    def _lang_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", v):
            raise ValueError("language trebuie sub forma xx_XX (ex: ro_RO).")
        return v


# ---------- Product Offer: Save / Stock Update ----------
class ProductOfferStock(BaseModel):
    warehouse_id: int = Field(..., gt=0, description="ID depozit (>0)")
    value: int = Field(..., ge=0, description="Stoc (>=0)")


class ProductOfferSaveIn(BaseModel):
    id: int = Field(..., gt=0, description="seller product id (internal id)")
    status: int = Field(..., ge=0, le=3, description="0=inactive,1=active,2=pending,3=deleted")
    sale_price: Decimal
    min_sale_price: Decimal
    max_sale_price: Decimal
    vat_id: int = Field(..., gt=0)
    handling_time: int = Field(..., ge=0)
    stock: List[ProductOfferStock]
    part_number_key: Optional[str] = Field(None, description="PNK (mutual exclusiv cu ean)")
    ean: Optional[str] = Field(None, description="EAN (mutual exclusiv cu PNK)")

    @field_validator("ean")
    @classmethod
    def _ean_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.strip()
        if not re.fullmatch(r"\d{8}|\d{13}", vv):  # EAN-8 sau EAN-13
            raise ValueError("EAN trebuie să fie numeric (8 sau 13 cifre).")
        return vv

    @model_validator(mode="after")
    def _validate_business_rules(self):
        if not self.stock:
            raise ValueError("Lista 'stock' nu poate fi goală.")
        if self.part_number_key and self.ean:
            raise ValueError("Folosește fie part_number_key (PNK), fie ean — nu ambele.")
        wh = [s.warehouse_id for s in self.stock]
        if len(set(wh)) != len(wh):
            raise ValueError("Lista 'stock' nu poate conține warehouse_id duplicate.")

        q = Decimal("0.01")
        self.min_sale_price = self.min_sale_price.quantize(q, rounding=ROUND_HALF_UP)
        self.sale_price = self.sale_price.quantize(q, rounding=ROUND_HALF_UP)
        self.max_sale_price = self.max_sale_price.quantize(q, rounding=ROUND_HALF_UP)
        if any(p < 0 for p in (self.min_sale_price, self.sale_price, self.max_sale_price)):
            raise ValueError("Prețurile trebuie să fie ≥ 0.")
        if not (self.min_sale_price <= self.sale_price <= self.max_sale_price):
            raise ValueError("sale_price trebuie să fie în [min_sale_price, max_sale_price].")
        return self


class OfferStockUpdateIn(BaseModel):
    id: int = Field(..., gt=0, description="seller product id (internal id)")
    warehouse_id: int = Field(..., gt=0)
    value: int = Field(..., ge=0)


# ---------- Orders / AWB ----------
class OrdersReadIn(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(100, ge=1, le=4000)
    status: Optional[OrderStatus] = Field(None, description="Filtru status (opțional)")


class OrdersAckIn(BaseModel):
    order_ids: List[int] = Field(..., min_items=1, description="Lista de ID-uri comenzi (>0, unice)")

    @model_validator(mode="after")
    def _validate_ids(self):
        if any(i <= 0 for i in self.order_ids):
            raise ValueError("Toate order_ids trebuie > 0.")
        if len(set(self.order_ids)) != len(self.order_ids):
            raise ValueError("order_ids conține duplicate.")
        return self


class AwbSaveIn(BaseModel):
    order_id: int = Field(..., gt=0)
    courier: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1)
    cod: bool = False

    @model_validator(mode="after")
    def _strip_nonempty(self):
        self.courier = self.courier.strip()
        self.service = self.service.strip()
        if not self.courier:
            raise ValueError("courier nu poate fi gol.")
        if not self.service:
            raise ValueError("service nu poate fi gol.")
        return self


# ---------- Caracteristici ----------
class CharAllowed(BaseModel):
    characteristic_id: int = Field(..., gt=0)
    values: List[str] = Field(default_factory=list, description="Lista valorilor permise (exact cum vin din eMAG)")


class CharValidateItem(BaseModel):
    characteristic_id: int = Field(..., gt=0)
    value: str = Field(..., min_length=1, description="Valoarea de intrare (ex: '2.5 Kg')")
    # alias compat 'schema'
    schema_name: Optional[CharSchema] = Field(
        default=None,
        alias="schema",
        description="Tip de mărime (mass/length/voltage/noise/integer/text/range_text). Dacă lipsește, se încearcă auto-detect."
    )

    @model_validator(mode="after")
    def _strip(self):
        self.value = " ".join(self.value.split()).strip()
        return self

    class Config:
        populate_by_name = True


class CharValidateIn(BaseModel):
    items: List[CharValidateItem] = Field(..., min_items=1)
    allowed: List[CharAllowed] = Field(..., min_items=1)


class CharValidateOutItem(BaseModel):
    characteristic_id: int
    input_value: str
    valid: bool
    matched_value: Optional[str] = None
    suggestions: Optional[List[str]] = None
    schema_used: Optional[CharSchema] = None
    reason: Optional[str] = None


class CharValidateOut(BaseModel):
    results: List[CharValidateOutItem]


# ---------- Product Offer: Read (filtre + item normalizat) ----------
STATUS_TEXT_ALLOWED = {"inactive", "active", "eol"}


class OfferReadFilters(BaseModel):
    # request to eMAG
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=400)
    status: Optional[int] = Field(None, description="0=inactive,1=active,2=eol")
    sku: Optional[str] = None
    ean: Optional[str] = None
    part_number_key: Optional[str] = None

    # filtre locale (client-side)
    after_id: Optional[int] = Field(None, ge=0)
    name_contains: Optional[str] = None
    category_id: Optional[int] = Field(None, ge=0)
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    status_text: Optional[str] = Field(None, description="inactive|active|eol")

    @field_validator("ean")
    @classmethod
    def _ean_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.strip()
        if not re.fullmatch(r"\d{8}|\d{13}", vv):
            raise ValueError("EAN trebuie 8 sau 13 cifre.")
        return vv

    @field_validator("status_text")
    @classmethod
    def _status_text_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        vv = v.strip().lower()
        if vv not in STATUS_TEXT_ALLOWED:
            raise ValueError("status_text trebuie să fie: inactive|active|eol")
        return vv

    @model_validator(mode="after")
    def _validate_prices(self):
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price nu poate fi > max_price")
        return self


class OfferNormalized(BaseModel):
    id: Optional[int] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    status: Optional[int] = None
    status_text: Optional[str] = None

    sale_price: Optional[Decimal] = None
    min_sale_price: Optional[Decimal] = None
    max_sale_price: Optional[Decimal] = None
    best_offer_sale_price: Optional[Decimal] = None
    currency: Optional[str] = None
    vat_id: Optional[int] = None
    handling_time: Optional[int] = None

    ean: Optional[str] = None
    part_number_key: Optional[str] = None

    general_stock: Optional[int] = None
    estimated_stock: Optional[int] = None
    stock_total: Optional[int] = None

    # câmpuri opționale, expuse doar dacă sunt cerute
    warehouses: Optional[List[Dict[str, Any]]] = None
    stock_debug: Optional[Dict[str, Any]] = None

```

# path-ul fisierului: app/routers/emag/utils.py  (size=6046 bytes)

```python
from __future__ import annotations

import difflib
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Callable, Awaitable

import httpx
from fastapi import HTTPException, status

# Limbă implicită per țară
LANG_BY_COUNTRY: Dict[str, str] = {"ro": "ro_RO", "bg": "bg_BG", "hu": "hu_HU"}

_QUANT_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-zµ]+)\s*$")


def normalize_ws(s: str) -> str:
    return " ".join(s.split()).strip()


def infer_schema_from_allowed(allowed: List[str]) -> str:
    units = set()
    numerics = 0
    for v in allowed:
        m = _QUANT_RE.match(v)
        if m:
            units.add(m.group(2))
        elif v.strip().isdigit():
            numerics += 1
    u_low = {u.lower() for u in units}
    if {"kg", "g"} & u_low:
        return "mass"
    if {"mm", "cm", "m", "inch", "nm"} & u_low:
        return "length"
    if {"v", "kv", "mv", "µv", "μv", "uv"} & u_low:
        return "voltage"
    if {"db"} & u_low:
        return "noise"
    if numerics == len(allowed) and numerics > 0:
        return "integer"
    return "text"


def _to_base(value: Decimal, unit: str, schema_name: str) -> Tuple[Decimal, str]:
    u = unit.lower()
    if schema_name == "mass":
        if u == "kg":
            return (value * Decimal("1000"), "g")
        if u == "g":
            return (value, "g")
    elif schema_name == "length":
        if u == "nm":
            return (value / Decimal("1_000_000"), "mm")
        if u == "mm":
            return (value, "mm")
        if u == "cm":
            return (value * Decimal("10"), "mm")
        if u == "m":
            return (value * Decimal("1000"), "mm")
        if u in {"inch", "in"}:
            return (value * Decimal("25.4"), "mm")
    elif schema_name == "voltage":
        if u in {"µv", "μv", "uv"}:
            return (value / Decimal("1_000_000"), "V")
        if u == "v":
            return (value, "V")
        if u == "kv":
            return (value * Decimal("1000"), "V")
        if u == "mv":
            return (value * Decimal("1_000_000"), "V")
    elif schema_name == "noise":
        if u == "db":
            return (value, "dB")
    return (value, unit)


def _parse_quantity(s: str) -> Optional[Tuple[Decimal, str]]:
    m = _QUANT_RE.match(s)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    unit = m.group(2)
    try:
        return (Decimal(num), unit)
    except Exception:
        return None


def _nearly_equal(a: Decimal, b: Decimal, rel_tol: Decimal = Decimal("1e-9")) -> bool:
    da = abs(a)
    db = abs(b)
    return abs(a - b) <= rel_tol * max(Decimal(1), da, db)


def match_quantitative(input_value: str, allowed: List[str], schema_name: str) -> Tuple[Optional[str], Optional[str]]:
    parsed_in = _parse_quantity(input_value)
    if not parsed_in:
        return (None, "Valoarea nu pare cantitativă (număr + unitate).")
    vin, uin = parsed_in
    vin_base, _ = _to_base(vin, uin, schema_name)
    for canonical in allowed:
        parsed_allowed = _parse_quantity(canonical)
        if not parsed_allowed:
            continue
        va, ua = parsed_allowed
        va_base, _ = _to_base(va, ua, schema_name)
        if _nearly_equal(vin_base, va_base):
            return (canonical, None)
    return (None, "Nu există corespondent numeric în lista permisă (după conversia unităților).")


def match_exact_or_ci(input_value: str, allowed: List[str]) -> Optional[str]:
    if input_value in allowed:
        return input_value
    norm_in = normalize_ws(input_value).lower()
    by_norm = {normalize_ws(v).lower(): v for v in allowed}
    return by_norm.get(norm_in)


def suggest(input_value: str, allowed: List[str], n: int = 5) -> List[str]:
    candidates = difflib.get_close_matches(input_value, allowed, n=n, cutoff=0.75)
    if candidates:
        return candidates
    low_map = {v.lower(): v for v in allowed}
    low_candidates = difflib.get_close_matches(input_value.lower(), list(low_map.keys()), n=n, cutoff=0.75)
    return [low_map[c] for c in low_candidates]


# ---------- invocator comun (erori uniforme) ----------
try:  # pragma: no cover
    from app.integrations.emag_sdk import EmagApiError, EmagRateLimitError  # type: ignore
except Exception:  # pragma: no cover
    class EmagApiError(Exception):
        def __init__(self, message: str, status_code: int = 0, payload: Optional[dict] = None):
            super().__init__(message)
            self.status_code = status_code
            self.payload = payload or {}

    class EmagRateLimitError(Exception):
        ...


async def call_emag(
    fn: Callable[..., Awaitable[dict]],
    *args,
    idempotency_key: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Invocator defensiv:
    - trece X-Idempotency-Key dacă funcția o acceptă;
    - convertește erorile din SDK/transport în HTTPException cu statusuri utile;
    - dacă metoda lipsește din SDK → 501 Not Implemented (mesaj clar).
    """
    try:
        if idempotency_key:
            try:
                return await fn(*args, idempotency_key=idempotency_key, **kwargs)
            except TypeError:
                return await fn(*args, **kwargs)
        return await fn(*args, **kwargs)
    except EmagRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except EmagApiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": str(e),
                "status_code": getattr(e, "status_code", 0),
                "payload": getattr(e, "payload", {}),
            },
        )
    except AttributeError as e:
        # metoda din SDK nu există
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"SDK method missing: {e}",
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"http transport error: {e!s}")

```

# path-ul fisierului: app/routers/observability.py  (size=18251 bytes)

```python
# app/routers/observability.py
from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


# -----------------------------------------------------------------------------
# Helpers & constants
# -----------------------------------------------------------------------------
_DDL_DCL_UTILITY = (
    "begin,commit,rollback,start,savepoint,release,"
    "prepare,deallocate,"
    "set,reset,show,"
    "explain,analyze,vacuum,checkpoint,refresh,discard,"
    "listen,unlisten,notify,lock,copy,security,cluster,"
    "create,alter,drop,grant,revoke,truncate,comment,"
    "call,do,declare,fetch,close"
)
_DDL_LIST = [x.strip().lower() for x in _DDL_DCL_UTILITY.split(",") if x.strip()]
# regex de început de linie (după normalizare) pentru utilitare/DDL.
# Folosim operatorul ~* (case-insensitive), deci nu mai punem (?i) în pattern.
DDL_BOL_RX = r"^\s*(?:" + "|".join(_DDL_LIST) + r")\b"

# regex robust pentru referințe la pg_stat_statements
_SELF_RX = r"(?is)\bpg_stat_statements(?:_info|_reset)?\b"


def _sql_quote_list_csv(csv_values: str) -> str:
    """
    Transformă 'a, b, a' -> 'a','b'
    (lowercase, unic, escaped pentru Postgres)
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in csv_values.split(","):
        v = raw.strip().lower()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append("'" + v.replace("'", "''") + "'")
    return ", ".join(out)


def _pgss_installed(db: Session) -> bool:
    return bool(
        db.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements')")
        ).scalar_one()
    )


def _pgss_view_present(db: Session) -> bool:
    return bool(
        db.execute(
            text(
                """
                SELECT EXISTS (
                  SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE c.relname = 'pg_stat_statements'
                     AND c.relkind IN ('v','m')
                )
                """
            )
        ).scalar_one()
    )


def _ensure_pgss(db: Session) -> None:
    if not _pgss_installed(db) or not _pgss_view_present(db):
        raise HTTPException(
            status_code=503,
            detail=(
                "pg_stat_statements not available. "
                "Pornește Postgres cu shared_preload_libraries=pg_stat_statements, "
                "apoi rulează: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
            ),
        )


def _obs_guard(x_obs_key: str | None = Header(default=None, alias="X-Obs-Key")) -> None:
    expected = os.getenv("OBS_API_KEY")
    if expected and x_obs_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Obs-Key")


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------
router = APIRouter(
    prefix="/observability",
    tags=["observability"],
    dependencies=[Depends(_obs_guard)],
)


# -----------------------------------------------------------------------------
# Endpoints generale
# -----------------------------------------------------------------------------
@router.get("/extensions")
def list_extensions(db: Session = Depends(get_db)):
    rows = (
        db.execute(
            text(
                """
                SELECT e.extname, n.nspname AS schema
                  FROM pg_extension e
                  JOIN pg_namespace n ON n.oid = e.extnamespace
                 WHERE e.extname IN ('pg_stat_statements','pg_trgm')
                 ORDER BY e.extname;
                """
            )
        )
        .mappings()
        .all()
    )
    return {"extensions": [dict(r) for r in rows]}


@router.get("/pgss/available")
def pgss_available(db: Session = Depends(get_db)):
    installed = _pgss_installed(db)
    view_present = _pgss_view_present(db)
    return {
        "pg_stat_statements_installed": installed,
        "pg_stat_statements_view_present": view_present,
        "pg_stat_statements_available": installed and view_present,
    }


@router.get("/pgss/info")
def pgss_info(db: Session = Depends(get_db)):
    _ensure_pgss(db)
    row = db.execute(text("SELECT * FROM pg_stat_statements_info()")).mappings().one()
    return {"info": dict(row)}


@router.get("/settings")
def pg_settings(db: Session = Depends(get_db)):
    rows = (
        db.execute(
            text(
                """
                SELECT name, setting
                  FROM pg_settings
                 WHERE name IN (
                   'pg_stat_statements.max',
                   'pg_stat_statements.save',
                   'pg_stat_statements.track',
                   'pg_stat_statements.track_utility',
                   'shared_preload_libraries',
                   'track_activity_query_size'
                 )
                 ORDER BY name;
                """
            )
        )
        .mappings()
        .all()
    )
    return {"settings": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# Activitate curentă
# -----------------------------------------------------------------------------
@router.get("/active")
def active(
    min_ms: int = Query(1000, ge=0, description="Durată minimă a query-ului activ, în ms"),
    state: str = Query(
        "active",
        pattern=r"^(active|idle in transaction|idle in transaction \(aborted\))$",
    ),
    limit: int = Query(50, ge=1, le=200),
    qlen: int = Query(500, ge=1, le=2000),
    application_name: str | None = Query(None, description="Filtru exact pe application_name"),
    db: Session = Depends(get_db),
):
    where = [
        "pid <> pg_backend_pid()",
        "state = :state",
        "now() - query_start >= (:min_ms || ' milliseconds')::interval",
    ]
    params: dict[str, object] = {"min_ms": min_ms, "state": state, "limit": limit, "qlen": qlen}

    if application_name:
        where.append("application_name = :appname")
        params["appname"] = application_name

    sql = f"""
        SELECT pid,
               now() - query_start                  AS duration,
               backend_type,
               client_addr::text                    AS client_addr,
               xact_start,
               query_start,
               wait_event_type,
               wait_event,
               state,
               left(query, :qlen)                   AS query,
               application_name,
               usename                               AS username,
               datname                               AS dbname
          FROM pg_stat_activity
         WHERE {' AND '.join(where)}
      ORDER BY duration DESC
         LIMIT :limit
    """
    rows = db.execute(text(sql), params).mappings().all()
    return {"count": len(rows), "items": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# Top queries din pg_stat_statements
# -----------------------------------------------------------------------------
@router.get("/top-queries")
def top_queries(
    limit: int = Query(20, ge=1, le=200),
    order_by: str = Query(
        "total_exec_time",
        pattern=r"^(total_exec_time|mean_exec_time|min_exec_time|max_exec_time|stddev_exec_time|calls|rows|rows_per_call)$",
    ),
    order_dir: str = Query("desc", pattern=r"^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    decimals: int = Query(2, ge=0, le=6),
    min_calls: int = Query(1, ge=1),
    min_mean_ms: float | None = Query(None, ge=0),
    min_total_ms: float | None = Query(None, ge=0),
    exclude_ddl: bool = Query(False, description="Exclude DDL/DCL/utility (best-effort)"),
    exclude_self: bool = Query(True, description="Exclude interogările de observabilitate (self)"),
    search: str | None = Query(None, description="Filtru ILIKE în textul query-ului"),
    username: str | None = Query(None, description="Filtrează după rol (pg_roles.rolname)"),
    dbname: str | None = Query(None, description="Filtrează după baza de date (pg_database.datname)"),
    include_query_text: bool = Query(True, description="Dacă false, nu include textul query-ului"),
    qlen: int = Query(500, ge=1, le=2000, description="Lungime maximă query în răspuns"),
    db: Session = Depends(get_db),
):
    _ensure_pgss(db)

    order_by_map = {
        "total_exec_time":  "total_ms",
        "mean_exec_time":   "mean_ms",
        "min_exec_time":    "min_ms",
        "max_exec_time":    "max_ms",
        "stddev_exec_time": "stddev_ms",
        "calls":            "calls",
        "rows":             "rows",
        "rows_per_call":    "rows_per_call",
    }
    order_sql = order_by_map[order_by]
    order_dir_sql = "ASC" if order_dir.lower() == "asc" else "DESC"

    where = ["s.calls >= :min_calls"]
    params: dict[str, object] = {
        "min_calls": min_calls,
        # IMPORTANT: ddl_bol_rx e folosit în CTE → îl legăm întotdeauna
        "ddl_bol_rx": DDL_BOL_RX,
    }

    if min_mean_ms is not None:
        where.append("s.mean_exec_time >= :min_mean_ms")
        params["min_mean_ms"] = min_mean_ms
    if min_total_ms is not None:
        where.append("s.total_exec_time >= :min_total_ms")
        params["min_total_ms"] = min_total_ms

    if search:
        where.append("COALESCE(s.query,'') ILIKE ('%' || :search || '%')")
        params["search"] = search

    if exclude_ddl:
        # folosim marcajul calculat în CTE
        where.append("NOT s.is_utility")

    if exclude_self:
        params["self_rx"] = _SELF_RX
        where.append("COALESCE(s.norm,'') !~* :self_rx")

    if username:
        where.append("r.rolname = :username")
        params["username"] = username
    if dbname:
        where.append("d.datname = :dbname")
        params["dbname"] = dbname

    query_col = "left(s.query, :qlen) AS query" if include_query_text else "NULL::text AS query"

    sql = f"""
        WITH s AS (
            SELECT
                queryid,
                dbid,
                userid,
                calls,
                total_exec_time,
                min_exec_time,
                max_exec_time,
                stddev_exec_time,
                mean_exec_time,
                rows,
                CASE WHEN calls > 0 THEN rows::numeric / calls ELSE 0 END AS rows_per_call,
                query,
                -- normalizez: scot comentariile și tai spațiile la stânga
                ltrim(
                    regexp_replace(
                        regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                        '--[^\\n]*', '', 'g'
                    )
                ) AS norm,
                -- primul cuvânt (lowercased) din query-ul normalizat
                COALESCE(
                    lower(substring(
                        ltrim(
                            regexp_replace(
                                regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                                '--[^\\n]*', '', 'g'
                            )
                        )
                        from '^([a-z]+)'
                    )),
                    ''
                ) AS first_kw,
                -- marcaj utility/DDL: fie primul cuvânt e în listă, fie începe cu acel cuvânt (regex)
                (
                  COALESCE(
                    lower(substring(
                        ltrim(
                            regexp_replace(
                                regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                                '--[^\\n]*', '', 'g'
                            )
                        )
                        from '^([a-z]+)'
                    )),
                    ''
                  ) IN ({_sql_quote_list_csv(_DDL_DCL_UTILITY)})
                  OR
                  ltrim(
                    regexp_replace(
                        regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                        '--[^\\n]*', '', 'g'
                    )
                  ) ~* :ddl_bol_rx
                ) AS is_utility
            FROM pg_stat_statements
        )
        SELECT
            s.queryid,
            s.calls,
            round(s.total_exec_time::numeric,  :d) AS total_ms,
            round(s.mean_exec_time::numeric,   :d) AS mean_ms,
            round(s.min_exec_time::numeric,    :d) AS min_ms,
            round(s.max_exec_time::numeric,    :d) AS max_ms,
            round(s.stddev_exec_time::numeric, :d) AS stddev_ms,
            s.rows,
            round(s.rows_per_call::numeric,    :d) AS rows_per_call,
            {query_col},
            r.rolname AS username,
            d.datname AS dbname
          FROM s
          JOIN pg_roles    r ON r.oid = s.userid
          JOIN pg_database d ON d.oid = s.dbid
         WHERE {' AND '.join(where)}
      ORDER BY {order_sql} {order_dir_sql}, s.queryid ASC
         LIMIT :limit
        OFFSET :offset
    """

    params.update({
        "d": decimals,
        "limit": limit,
        "offset": offset,
        "qlen": qlen,
    })

    rows = db.execute(text(sql), params).mappings().all()
    return {
        "count": len(rows),
        "order_by": order_by,
        "order_dir": order_dir_sql,
        "items": [dict(r) for r in rows],
    }


@router.post("/pgss/reset", status_code=204)
def pgss_reset(db: Session = Depends(get_db)):
    _ensure_pgss(db)
    db.execute(text("SELECT pg_stat_statements_reset()"))
    return None


# -----------------------------------------------------------------------------
# Waiters ↔ Blockers (locks)
# -----------------------------------------------------------------------------
@router.get("/locks")
def locks(
    min_wait_ms: int = Query(0, ge=0, description="Durata minimă a așteptării (ms)"),
    only_blocked: bool = Query(True, description="Afișează doar procese efectiv blocate"),
    qlen: int = Query(300, ge=1, le=2000),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    base_where = []
    if only_blocked:
        base_where.append("w.wait_event_type = 'Lock'")
    if min_wait_ms > 0:
        base_where.append("now() - w.query_start >= (:min_wait_ms || ' milliseconds')::interval")
    if not base_where:
        base_where.append("TRUE")

    sql = f"""
    WITH waiting AS (
      SELECT l.*,
             a.query_start,
             a.usename,
             a.datname,
             a.application_name,
             a.client_addr::text AS client_addr,
             a.state,
             a.wait_event_type,
             a.query
        FROM pg_locks l
        JOIN pg_stat_activity a ON a.pid = l.pid
       WHERE NOT l.granted
    ),
    blocking AS (
      SELECT l.*,
             a.query_start,
             a.usename,
             a.datname,
             a.application_name,
             a.client_addr::text AS client_addr,
             a.state,
             a.query
        FROM pg_locks l
        JOIN pg_stat_activity a ON a.pid = l.pid
       WHERE l.granted
    )
    SELECT
      w.pid                               AS waiting_pid,
      now() - w.query_start               AS waiting_duration,
      w.state                             AS waiting_state,
      left(w.query, :qlen)                AS waiting_query,
      w.usename                           AS waiting_username,
      w.datname                           AS waiting_dbname,
      w.application_name                  AS waiting_app,
      w.client_addr                       AS waiting_client,
      b.pid                               AS blocking_pid,
      b.state                             AS blocking_state,
      left(b.query, :qlen)                AS blocking_query,
      b.usename                           AS blocking_username,
      b.datname                           AS blocking_dbname,
      b.application_name                  AS blocking_app,
      b.client_addr                       AS blocking_client,
      w.locktype,
      w.mode                              AS waiting_mode,
      b.mode                              AS blocking_mode
    FROM waiting w
    JOIN blocking b
      ON b.locktype = w.locktype
     AND b.database IS NOT DISTINCT FROM w.database
     AND b.relation IS NOT DISTINCT FROM w.relation
     AND b.page     IS NOT DISTINCT FROM w.page
     AND b.tuple    IS NOT DISTINCT FROM w.tuple
     AND b.classid  IS NOT DISTINCT FROM w.classid
     AND b.objid    IS NOT DISTINCT FROM w.objid
     AND b.objsubid IS NOT DISTINCT FROM w.objsubid
     AND b.transactionid IS NOT DISTINCT FROM w.transactionid
    WHERE {" AND ".join(base_where)}
    ORDER BY waiting_duration DESC
    LIMIT :limit
    """
    params = {"qlen": qlen, "limit": limit, "min_wait_ms": min_wait_ms}
    rows = db.execute(text(sql), params).mappings().all()
    return {"count": len(rows), "items": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# Generator simplu de trafic (dev utility)
# -----------------------------------------------------------------------------
@router.post("/sample-load")
def sample_load(
    n: int = Query(200, ge=1, le=10_000, description="Număr de interogări generate"),
    search: str | None = Query(None, description="Pattern pentru ILIKE pe products.name"),
    db: Session = Depends(get_db),
):
    _ensure_pgss(db)
    pat = f"%{(search or '').lower()}%"
    for i in range(n):
        db.execute(text("SELECT current_schema()"))
        db.execute(text("SELECT pg_catalog.version()"))
        try:
            db.execute(
                text(
                    "SELECT count(*) FROM app.products "
                    "WHERE (:s) IS NULL OR lower(name) ILIKE :pat"
                ),
                {"s": search, "pat": pat},
            )
        except Exception:
            # tabela poate lipsi; ignorăm
            pass
        if (i + 1) % 200 == 0:
            db.flush()
    return {"generated": n}

```

# path-ul fisierului: app/routers/observability_ext.py  (size=1472 bytes)

```python
from __future__ import annotations

import os
import sys
import time
import platform
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/observability/v2", tags=["observability"])

APP_STARTED_TS = int(os.getenv("APP_STARTED_TS", str(int(time.time()))))
APP_VERSION = os.getenv("APP_VERSION", "unknown")

@router.get("/summary")
def obs_summary() -> Dict[str, Any]:
    return {
        "app_version": APP_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pid": os.getpid(),
        "started_at": APP_STARTED_TS,
        "uptime_s": time.time() - APP_STARTED_TS,
        "env": {
            "root_path": os.getenv("ROOT_PATH", ""),
            "log_level": os.getenv("LOG_LEVEL", ""),
        }
    }

@router.get("/health")
def obs_health() -> Dict[str, Any]:
    return {"ok": True, "ts": int(time.time())}

@router.get("/hints")
def obs_hints() -> Dict[str, Any]:
    """
    Endpoint „static” cu sugestii de configurare (util cînd rulezi în containere).
    """
    hints = []
    if not os.getenv("TRUSTED_HOSTS"):
        hints.append("Setează TRUSTED_HOSTS pentru a restricționa Host header.")
    if not os.getenv("CORS_ORIGINS"):
        hints.append("Setează CORS_ORIGINS dacă apelezi API din browser.")
    if os.getenv("DISABLE_DOCS","").lower() in {"1","true","yes"}:
        hints.append("Docs sunt dezactivate (DISABLE_DOCS=1).")
    return {"hints": hints}

```

# path-ul fisierului: app/routers/product.py  (size=4651 bytes)

```python
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

```

# path-ul fisierului: app/schemas/__init__.py  (size=0 bytes)

```python

```

# path-ul fisierului: app/schemas/category.py  (size=2642 bytes)

```python
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

```

# path-ul fisierului: app/schemas/product.py  (size=3964 bytes)

```python
# app/schemas/product.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
import re

from pydantic import BaseModel, Field, ConfigDict, field_validator

# SKU: litere/cifre + . _ - ; max 64; fără spații
SKU_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _quantize_price(v: Decimal) -> Decimal:
    # Aliniază la NUMERIC(12,2) și evită erori de reprezentare
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProductBase(BaseModel):
    """Câmpuri comune pentru produs; folosit la create/read."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    sku: Optional[str] = Field(None, min_length=1, max_length=64)

    # --- Validators ---
    @field_validator("name")
    @classmethod
    def _name_strip_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description")
    @classmethod
    def _descr_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("sku")
    @classmethod
    def _sku_validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not SKU_RE.match(v):
            raise ValueError("Invalid SKU (allowed: letters, digits, . _ -, max 64)")
        return v

    @field_validator("price")
    @classmethod
    def _price_quantize(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("price must be >= 0")
        return _quantize_price(v)

    model_config = ConfigDict(
        # oferă exemple utile în OpenAPI
        json_schema_extra={
            "examples": [
                {
                    "name": "Amplificator audio TPA3116",
                    "description": "2x50W, radiator aluminiu",
                    "price": "129.90",
                    "sku": "TPA3116-2x50W-BLUE",
                }
            ]
        }
    )


class ProductCreate(ProductBase):
    """Payload pentru creare produs."""
    pass


class ProductUpdate(BaseModel):
    """Payload pentru update; toate câmpurile sunt opționale."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    sku: Optional[str] = Field(None, min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def _name_strip_nonempty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description")
    @classmethod
    def _descr_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("sku")
    @classmethod
    def _sku_validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not SKU_RE.match(v):
            raise ValueError("Invalid SKU (allowed: letters, digits, . _ -, max 64)")
        return v

    @field_validator("price")
    @classmethod
    def _price_quantize(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("price must be >= 0")
        return _quantize_price(v)


class ProductRead(ProductBase):
    """Răspuns pentru produs."""
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProductPage(BaseModel):
    """Răspuns paginat: listă + meta."""
    items: List[ProductRead]
    total: int
    page: int
    page_size: int

```

# path-ul fisierului: app/services/emag_value_map.py  (size=4066 bytes)

```python
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, List

_num_unit = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([A-Za-zµ\"u]+)?\s*$")

# normalizări unități (lowercase)
_UNIT_ALIASES = {
    "kg": "kg",
    "g": "g",
    "mg": "mg",

    "v": "v",
    "kv": "kv",
    "mv": "mv",
    "uv": "uv",
    "µv": "uv",

    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "nm": "nm",
    "inch": "in",
    '"': "in",
    "in": "in",
}

# conversii „țintă” → factori
_CONV = {
    # masă
    ("kg", "g"): 1000.0,
    ("g", "g"): 1.0,
    ("mg", "g"): 0.001,

    # tensiune
    ("kv", "v"): 1000.0,
    ("v", "v"): 1.0,
    ("mv", "v"): 0.001,
    ("uv", "v"): 1e-6,

    # lungime
    ("m", "mm"): 1000.0,
    ("cm", "mm"): 10.0,
    ("mm", "mm"): 1.0,
    ("in", "mm"): 25.4,
    ("nm", "mm"): 1e-6,
}


@dataclass(frozen=True)
class ParsedValue:
    number: float
    unit: str  # already normalized (lower)


def _normalize_unit(u: Optional[str]) -> str:
    if not u:
        return ""
    u = u.strip()
    # micro semnul µ → u
    u = u.replace("µ", "u")
    return _UNIT_ALIASES.get(u.lower(), u.lower())


def parse_num_unit(s: str) -> Tuple[Optional[ParsedValue], bool]:
    """
    Returnează (ParsedValue|None, ok_parse_bool).
    Acceptă '12.3 V', '12,3 V', '125 mm', '12"'.
    """
    if s is None:
        return (None, False)
    raw = s.strip()
    if not raw:
        return (None, False)
    m = _num_unit.match(raw)
    if not m:
        return (None, False)
    n = float(m.group(1).replace(",", "."))
    unit = _normalize_unit(m.group(2))
    return (ParsedValue(n, unit), True)


def _pick_target_unit(allowed: Iterable[str]) -> str:
    """Alege unitatea „majoritară” din allowed, pentru comparații coerente."""
    counts: dict[str, int] = {}
    for a in allowed:
        pv, ok = parse_num_unit(a)
        if ok and pv and pv.unit:
            counts[pv.unit] = counts.get(pv.unit, 0) + 1
    if not counts:
        return ""  # fără unitate
    return max(counts, key=counts.get)


def _convert(p: ParsedValue, target_unit: str) -> Optional[float]:
    if not target_unit or p.unit == target_unit:
        return p.number
    key = (p.unit, target_unit)
    if key in _CONV:
        return p.number * _CONV[key]
    return None


def exact_match(user_value: str, allowed: Iterable[str]) -> Optional[str]:
    # match „textual” identic (case-sensitive, ca la API)
    for a in allowed:
        if user_value == a:
            return a
    return None


def closest_allowed(user_value: str, allowed: List[str]) -> Optional[str]:
    """Găsește valoarea permisă cu numerică cea mai apropiată (+ conversii unități)."""
    pv_in, ok_in = parse_num_unit(user_value)
    if not ok_in or pv_in is None:
        return None

    target = _pick_target_unit(allowed)
    xin = _convert(pv_in, target)
    if xin is None:
        return None

    best_idx = -1
    best_diff = math.inf
    parsed_allowed: List[Optional[ParsedValue]] = []
    for a in allowed:
        pv, ok = parse_num_unit(a)
        parsed_allowed.append(pv if ok else None)

    for idx, (raw, pv) in enumerate(zip(allowed, parsed_allowed)):
        if pv is None:
            continue
        xv = _convert(pv, target)
        if xv is None:
            continue
        d = abs(xv - xin)
        if d < best_diff:
            best_idx = idx
            best_diff = d

    return allowed[best_idx] if best_idx >= 0 else None


def map_value_for_emag(
    user_value: str,
    allowed: List[str],
    allow_new_value: bool,
    prefer_exact: bool = True,
) -> Tuple[str, str]:
    """
    Întoarce (label_de_trimis, source), unde source ∈ {"exact","closest","new"}.
    Ridică ValueError dacă nu se poate mapa și nu e voie valoare nouă.
    """
    user_value = (user_value or "").strip()
    if not user_value:
        raise ValueError("Valoarea este goală.")

    if prefer_exact:
        ex = exact_match(user_value, allowed)
        if ex is not None:

```

# path-ul fisierului: docker-compose.dev.yml  (size=2314 bytes)

```yaml
# Folosește împreună cu fișierul principal:
#   docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev up --build
#
# Scop:
# - Montează codul local în container (hot-reload)
# - Expune un port de dev (APP_PORT_DEV) separat de portul de prod
# - Log level detaliat și watcher stabil pe macOS/Windows
# - Opțional: pgweb pentru interfață SQL în browser

services:
  app:
    profiles: ["dev"]
    # Folosește aceleași build/image ca în fișierul principal
    environment:
      LOG_LEVEL: debug
      APP_RELOAD: "1"                  # entrypoint va porni uvicorn --reload
      WATCHFILES_FORCE_POLLING: "true" # fix pt. watcher în Docker Desktop
      UVICORN_HOST: "0.0.0.0"
      UVICORN_PORT: "8000"             # port intern în mod dev
    # Poți seta aici temporar credențiale de test dacă nu vrei să atingi .env
    # EMAG_MAIN_USER: ${EMAG_MAIN_USER}
    # EMAG_MAIN_PASS: ${EMAG_MAIN_PASS}
    ports:
      - "${APP_PORT_DEV:-8000}:8000"
    volumes:
      # Montează tot proiectul peste /app ca să vezi imediat modificările
      - ./:/app:cached
      # (opțional) accesează testele din container în read-only
      - ./tests:/app/tests:ro
    # Creează un cache pentru pip (nu e obligatoriu)
    # - pip-cache:/root/.cache/pip
    read_only: false                    # necesar când montăm codul
    tmpfs: []                           # dezactivează tmpfs din prod
    security_opt: []                    # fără restricții suplimentare în dev
    cap_drop: []                        # păstrează capabilitățile default
    depends_on:
      db:
        condition: service_healthy
        required: true
    extra_hosts:
      - "host.docker.internal:host-gateway"  # acces la servicii de pe host
    env_file:
      - .env   # încarcă variabilele din .env pe lângă cele din 'environment'

  # Interfață web opțională pentru Postgres
  pgweb:
    profiles: ["dev"]
    image: sosedoff/pgweb:0.14.3
    depends_on:
      db:
        condition: service_healthy
    environment:
      # Conexiune directă la serviciul 'db' din rețeaua compose
      DATABASE_URL: po…*******************************************************
    ports:
      - "8081:8081"
    command: ["--listen=0.0.0.0", "--listen-port=8081"]

# volumes:
#   pip-cache:

```

# path-ul fisierului: docker-compose.override.yml  (size=1150 bytes)

```yaml
# docker-compose.override.yml — folosit doar local, peste docker-compose.yml
services:
  worker:
    # Nu pornește implicit; îl lansezi doar cu: docker compose --profile worker up -d worker
    profiles: ["worker"]
    restart: "no"

    # Așteaptă DB (healthy) și API (pornit); evită erorile de conectare la start.
    depends_on:
      db:
        condition: service_healthy
      app:
        condition: service_started

    # Variante de comandă:
    #
    # 1) NOOP sigur (default) — containerul pornește și stă "adormit", util pt. test wiring/logs.
    command: bash -lc "echo 'worker (noop) — override command to run real jobs'; exec sleep infinity"

    # 2) Testează un modul existent (decomentează dacă modulul are un entrypoint rulabil):
    # command: bash -lc "python -m app.services.emag_value_map"

    # 3) Când vei avea worker-ul real:
    # command: bash -lc "python -m app.services.sync_emag_offers"

    # Opțional: un healthcheck simplu, ca să vezi rapid status-ul containerului.
    healthcheck:
      test: ["CMD-SHELL", "printf 'ok\n' > /dev/null"]
      interval: 30s
      timeout: 3s
      retries: 3

```

# path-ul fisierului: docker-compose.yml  (size=10067 bytes)

```yaml
name: emagdb

# --- reusable anchors --------------------------------------------------------
x-logging: &default-logging
  driver: json-file
  options: { max-size: "10m", max-file: "3" }

x-app-env: &app-env
  TZ: Europe/Bucharest
  PYTHONUNBUFFERED: "1"
  PYTHONDONTWRITEBYTECODE: "1"
  PYTHONFAULTHANDLER: "1"
  LOG_LEVEL: info
  HOME: /tmp

  # App meta / docs & OpenAPI (match app/main.py)
  APP_TITLE: emag-db-api
  APP_VERSION: ${APP_VERSION:-0.1.0}
  ROOT_PATH: ${ROOT_PATH:-}
  DISABLE_DOCS: ${DISABLE_DOCS:-0}
  OPENAPI_URL: ${OPENAPI_URL:-/openapi.json}
  DOCS_URL: ${DOCS_URL:-/docs}
  REDOC_URL: ${REDOC_URL:-/redoc}
  OPENAPI_ADD_ROOT_SERVER: ${OPENAPI_ADD_ROOT_SERVER:-1}
  CORS_ORIGINS: ${CORS_ORIGINS:-}
  TRUSTED_HOSTS: ${TRUSTED_HOSTS:-}
  BUILD_SHA: ${BUILD_SHA:-}
  GIT_SHA: ${GIT_SHA:-}

  # Observability guard (optional)
  OBS_KEY: ${OBS_KEY:-}
  OBS_PROTECT_PREFIXES: ${OBS_PROTECT_PREFIXES:-/observability}

  # --- Schema & Alembic ---
  DB_SCHEMA: ${DB_SCHEMA:-app}
  DB_CREATE_SCHEMA_IF_MISSING: "1"
  ALEMBIC_CONFIG: /app/alembic.ini
  ALEMBIC_USE_SCHEMA_TRANSLATE: "1"
  ALEMBIC_ONLY_DEFAULT_SCHEMA: "0"
  ALEMBIC_MAP_PUBLIC_TO_DEFAULT_SCHEMA: "0"
  ALEMBIC_VERSION_TABLE: alembic_version
  ALEMBIC_SET_LOCAL_SEARCH_PATH: "1"

  # ✔ diagnostic/fail-fast (suportate în env.py)
  ALEMBIC_VERIFY_WITH_NEW_CONNECTION: "1"
  ALEMBIC_ASSERT_TABLES: "products,categories,product_categories"
  ALEMBIC_FAIL_IF_PUBLIC_VERSION_TABLE: "1"
  ALEMBIC_SQL_ECHO: ${ALEMBIC_SQL_ECHO:-0}

  # Extensii Postgres (opțional, folosite de initdb)
  DB_EXTENSIONS: ${DB_EXTENSIONS:-}
  DB_EXTENSIONS_STRICT: ${DB_EXTENSIONS_STRICT:-0}

  # --- Pool ---
  DB_POOL_SIZE: ${DB_POOL_SIZE:-5}
  DB_MAX_OVERFLOW: ${DB_MAX_OVERFLOW:-10}

  # --- boot ---
  RUN_MIGRATIONS_ON_START: "1"
  WAIT_FOR_DB: "auto"
  WAIT_RETRIES: "60"
  WAIT_SLEEP_SECS: "1"

  # --- Uvicorn ---
  UVICORN_HOST: 0.0.0.0
  UVICORN_PORT: "8001"
  UVICORN_WORKERS: ${UVICORN_WORKERS:-1}

  # 🔒 Forțează search_path pentru TOATE conexiunile libpq/psycopg (incl. Alembic)
  PGOPTIONS: "-c search_path=${DB_SCHEMA:-app},public"

  # (opțional) Nume de aplicație în PG (vizibil în pg_stat_activity)
  DB_APPLICATION_NAME: "emagdb-api"

x-app-healthcheck: &app-healthcheck
  test:
    [
      "CMD-SHELL",
      "python - <<'PY'\nimport sys,urllib.request\nu='http://127.0.0.1:8001/health/ready'\ntry:\n  with urllib.request.urlopen(u, timeout=2) as r:\n    sys.exit(0 if r.status==200 else 1)\nexcept Exception:\n  sys.exit(1)\nPY",
    ]
  interval: 10s
  timeout: 3s
  retries: 12
  start_period: 20s

# Securitate comună pentru containerele app-like
x-secure-app: &secure-app
  init: true
  security_opt: ["no-new-privileges:true"]
  cap_drop: [ALL]
  read_only: true
  tmpfs: ["/tmp:rw,noexec,nosuid,size=64m"]
  logging: *default-logging
  networks: [backend]
  ulimits:
    nofile: { soft: 65536, hard: 65536 }
    nproc: 4096

# Env Postgres
x-pg-env: &pg-env
  TZ: Europe/Bucharest
  POSTGRES_USER: ${POSTGRES_USER:-appuser}
  POSTGRES_PASSWORD: ${…****************************
  POSTGRES_DB: ${POSTGRES_DB:-appdb}
  POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C.UTF-8"

# Healthcheck PG comun
x-pg-health: &pg-health
  test: ["CMD-SHELL", 'pg_isready -q -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -h localhost']
  interval: 5s
  timeout: 3s
  retries: 15
  start_period: 15s

# Centralizăm comanda Postgres (search_path + pg_stat_statements preload)
x-pg-command: &pg-command
  - "postgres"
  - "-c"
  - "search_path=${DB_SCHEMA:-app},public"
  - "-c"
  - "shared_preload_libraries=pg_stat_statements"
  - "-c"
  - "pg_stat_statements.track=all"
  - "-c"
  - "pg_stat_statements.track_utility=off"
  - "-c"
  - "pg_stat_statements.max=5000"
  - "-c"
  - "pg_stat_statements.save=on"
  - "-c"
  - "track_activity_query_size=4096"

# Build & image anchors
x-app-build: &app-build
  context: .
  dockerfile: Dockerfile
  target: runtime

x-app-image: &app-image ${APP_IMAGE:-emagdb-app:latest}

# Refolosim URL-urile DB (psycopg3) — includem application_name + search_path
x-db-url: &db-url "postgresql+psycopg://${POSTGRES_USER:-appuser}:${POSTGRES_PASSWORD:-appsecret}@db:5432/${POSTGRES_DB:-appdb}?application_name=${DB_APPLICATION_NAME:-emagdb-api}&options=-csearch_path%3D${DB_SCHEMA:-app}%2Cpublic"
x-db-url-test: &db-url-test "postgresql+psycopg://${POSTGRES_USER:-appuser}:${POSTGRES_PASSWORD:-appsecret}@db_test:5432/${POSTGRES_DB_TEST:-appdb_test}?application_name=${DB_APPLICATION_NAME:-emagdb-api}-test&options=-csearch_path%3D${DB_SCHEMA:-app}%2Cpublic"

# --- services ---------------------------------------------------------------
services:
  db:
    image: postgres:16
    pull_policy: missing
    container_name: emagdb_pg
    command: *pg-command
    # securizat: expune doar local
    ports: ["127.0.0.1:${DB_PORT:-5434}:5432"]
    environment: *pg-env
    healthcheck: *pg-health
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/initdb:/docker-entrypoint-initdb.d:ro
    restart: unless-stopped
    stop_grace_period: 30s
    init: true
    logging: *default-logging
    networks: [backend]
    ulimits:
      nofile: { soft: 65536, hard: 65536 }
      nproc: 4096

  app:
    build: *app-build
    image: *app-image
    pull_policy: missing
    container_name: emagdb_app
    depends_on:
      db: { condition: service_healthy }
    env_file: [.env]
    environment:
      <<: *app-env
      DATABASE_URL: *d…*******************************
      ALEMBIC_VERSION_TABLE_SCHEMA: ${DB_SCHEMA:-app}
    user: "10001:10001"
    # Bind doar pe localhost; APP_PORT e configurabil (default 8010)
    ports: ["127.0.0.1:${APP_PORT:-8010}:8001"]
    healthcheck: *app-healthcheck
    command: ["/app/docker/app-entrypoint.sh"]
    restart: unless-stopped
    stop_grace_period: 15s
    stop_signal: SIGTERM
    <<: *secure-app

  # --- Worker de sync (pasul 3) ----------------------------------------------
  worker:
    build: *app-build
    image: *app-image
    pull_policy: missing
    container_name: emagdb_worker
    depends_on:
      db: { condition: service_healthy }
    env_file: [.env]
    environment:
      <<: *app-env
      DATABASE_URL: *d…****
    command: >
      bash -lc "python -m app.services.sync_emag_offers --interval 300"
    restart: unless-stopped
    stop_grace_period: 15s
    <<: *secure-app

  # --- DEV ONLY --------------------------------------------------------------
  app-dev:
    extends: { service: app }
    profiles: ["dev"]
    container_name: emagdb_app_dev
    environment:
      <<: *app-env
      LOG_LEVEL: debug
      APP_RELOAD: "1"
      WATCHFILES_FORCE_POLLING: "true"
      ALEMBIC_SQL_ECHO: "1"
      DATABASE_URL: *d…****
    volumes:
      - ./:/app
      - ./tests:/app/tests:ro
    ports: ["${APP_PORT_DEV:-8002}:8001"]
    read_only: false
    extra_hosts: ["host.docker.internal:host-gateway"]

  # --- PgBouncer (opțional) --------------------------------------------------
  pgbouncer:
    profiles: ["pool"]
    image: edoburu/pgbouncer:1.22.1
    pull_policy: missing
    depends_on:
      db: { condition: service_healthy }
    environment:
      DB_USER: ${POSTGRES_USER:-appuser}
      DB_PASSWORD: ${…****************************
      DB_HOST: db
      DB_PORT: 5432
      AUTH_TYPE: md5
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 200
      DEFAULT_POOL_SIZE: 20
      RESERVE_POOL_SIZE: 5
      RESERVE_POOL_TIMEOUT: 5
      SERVER_RESET_QUERY: "DISCARD ALL"
      LOG_CONNECTIONS: 0
      LOG_DISCONNECTIONS: 0
    ports:
      - "127.0.0.1:${PGBOUNCER_PORT:-6432}:6432"
    networks: [backend]
    restart: unless-stopped
    logging: *default-logging

  # --- TEST DB izolată -------------------------------------------------------
  db_test:
    profiles: ["test"]
    image: postgres:16
    pull_policy: missing
    container_name: emagdb_pg_test
    command: *pg-command
    environment:
      <<: *pg-env
      POSTGRES_DB: ${POSTGRES_DB_TEST:-appdb_test}
    healthcheck: *pg-health
    tmpfs: ["/var/lib/postgresql/data:rw,size=1024m"]
    volumes:
      - ./docker/initdb-test:/docker-entrypoint-initdb.d:ro
    restart: "no"
    init: true
    logging: *default-logging
    networks: [backend]
    ulimits:
      nofile: { soft: 65536, hard: 65536 }
      nproc: 4096

  # --- API pentru test -------------------------------------------------------
  app-test:
    profiles: ["test"]
    build: *app-build
    image: *app-image
    pull_policy: missing
    depends_on:
      db_test: { condition: service_healthy }
    environment:
      <<: *app-env
      DATABASE_URL: *d…*********
      LOG_LEVEL: warning
      ALEMBIC_VERSION_TABLE_SCHEMA: ${DB_SCHEMA:-app}
      ALEMBIC_TRANSACTION_PER_MIGRATION: "1"
      ALEMBIC_SQL_ECHO: "1"
    user: "10001:10001"
    healthcheck: *app-healthcheck
    command: ["/app/docker/app-entrypoint.sh"]
    restart: "no"
    <<: *secure-app

  # --- Runner de teste -------------------------------------------------------
  test:
    profiles: ["test"]
    image: *app-image
    pull_policy: missing
    depends_on:
      app-test: { condition: service_healthy }
    environment:
      <<: *app-env
      DATABASE_URL: *d…*********
      BASE_URL: http://app-test:8001
      PYTEST_ADDOPTS: "-q -o cache_dir=/tmp/.pytest_cache"
      PYTHONUNBUFFERED: "1"
    volumes: ["./tests:/app/tests:ro"]
    command: ["pytest"]
    restart: "no"
    <<: *secure-app

  # --- optional: pgweb -------------------------------------------------------
  pgweb:
    profiles: ["dev"]
    image: sosedoff/pgweb:0.15.0
    pull_policy: missing
    depends_on: { db: { condition: service_healthy } }
    environment:
      DATABASE_URL: "p…*****************************************************************************************************************
    ports: ["${PGWEB_PORT:-8081}:8081"]
    restart: unless-stopped
    logging: *default-logging
    networks: [backend]

# --- storage ----------------------------------------------------------------
volumes:
  pgdata:

networks:
  backend:
    name: emagdb_backend

```

# path-ul fisierului: docker/app-entrypoint.sh  (size=2945 bytes, exec)

```bash
#!/usr/bin/env sh
set -eu

log() { printf '[entrypoint] %s\n' "$*"; }
to_bool() {
  case "${1:-}" in 1|true|TRUE|yes|on|On|YES) return 0;; *) return 1;; esac
}

# --- Defaults (override prin env) ---
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

APP_MODULE="${APP_MODULE:-app.main:app}"
UVICORN_HOST="${UVICORN_HOST:-0.0.0.0}"
UVICORN_PORT="${UVICORN_PORT:-8001}"           # <- implicit 8001 ca să se potrivească cu ports: 8001:8001
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"
UVICORN_ACCESS_LOG="${UVICORN_ACCESS_LOG:-0}"
LOG_LEVEL="${LOG_LEVEL:-info}"

ALEMBIC_CONFIG="${ALEMBIC_CONFIG:-/app/alembic.ini}"
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-1}"  # 1/true pentru a rula migrațiile la start
WAIT_FOR_DB="${WAIT_FOR_DB:-auto}"                       # auto => așteaptă doar dacă DATABASE_URL este setat

WAIT_RETRIES="${WAIT_RETRIES:-60}"
WAIT_SLEEP_SECS="${WAIT_SLEEP_SECS:-1}"
MIGRATION_RETRIES="${MIGRATION_RETRIES:-20}"
MIGRATION_SLEEP_SECS="${MIGRATION_SLEEP_SECS:-2}"

# --- Wait for DB (TCP) ---
if { [ "${WAIT_FOR_DB}" = "auto" ] && [ -n "${DATABASE_URL:-}" ]; } || to_bool "${WAIT_FOR_DB}"; then
  if [ -n "${DATABASE_URL:-}" ]; then
    log "Waiting for DB: ${DATABASE_URL}"
    python - <<'PY'
import os, time, socket, sys, urllib.parse
url=os.environ["DATABASE_URL"].replace("postgresql+psycopg2","postgresql")
p=urllib.parse.urlsplit(url)
host=p.hostname or "db"
port=int(p.port or 5432)
retries=int(os.getenv("WAIT_RETRIES","60"))
sleep=float(os.getenv("WAIT_SLEEP_SECS","1"))
for i in range(retries):
    try:
        s=socket.create_connection((host,port),2); s.close()
        print(f"DB reachable at {host}:{port}")
        sys.exit(0)
    except Exception:
        time.sleep(sleep)
print(f"DB not reachable at {host}:{port} after {retries} tries")
sys.exit(1)
PY
  else
    log "WAIT_FOR_DB activ, dar DATABASE_URL nu este setat; sar peste wait."
  fi
fi

# --- Alembic migrations (cu retry) ---
if to_bool "${RUN_MIGRATIONS_ON_START}"; then
  i=0
  while : ; do
    i=$((i+1))
    log "Running: alembic -c ${ALEMBIC_CONFIG} upgrade head (attempt ${i})"
    if alembic -c "${ALEMBIC_CONFIG}" upgrade head; then
      log "Migrations applied."
      break
    fi
    if [ "${i}" -ge "${MIGRATION_RETRIES}" ]; then
      log "Alembic failed after ${MIGRATION_RETRIES} attempts. Exiting."
      exit 1
    fi
    log "Alembic failed. Retrying in ${MIGRATION_SLEEP_SECS}s ..."
    sleep "${MIGRATION_SLEEP_SECS}"
  done
else
  log "RUN_MIGRATIONS_ON_START=0 → skipping migrations."
fi

# --- Start Uvicorn (build argv în siguranță) ---
set -- python -m uvicorn "${APP_MODULE}" --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" --log-level "${LOG_LEVEL}"
if ! to_bool "${UVICORN_ACCESS_LOG}"; then
  set -- "$@" --no-access-log
fi
# Workers >1 doar dacă e setat
case "${UVICORN_WORKERS}" in
  ''|0|1) : ;;
  *) set -- "$@" --workers "${UVICORN_WORKERS}" ;;
esac

log "Starting: $*"
exec "$@"

```

# path-ul fisierului: docker/initdb-test/00_schema.sql  (size=362 bytes)

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
    EXECUTE format('CREATE SCHEMA %I AUTHORIZATION %I', 'app', current_user);
  END IF;
END $$;

-- Asigură search_path implicit în DB-ul de test
ALTER DATABASE appdb_test SET search_path = app, public;
ALTER ROLE appuser IN DATABASE appdb_test SET search_path = app, public;

```

# path-ul fisierului: docker/initdb/00_schema.sql  (size=3508 bytes)

```sql
-- app/docker/initdb/00_schema.sql
-- Bootstrap inițial pentru clusterul nou (rulat de postgres:16 la init).
-- Idempotent: folosim IF NOT EXISTS și DO-blocks defensive.

-- 0) Siguranță & claritate
SET client_min_messages = warning;

-- 1) Creează schema aplicatiei și setează proprietarul pe rolul curent
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_namespace WHERE nspname = 'app'
  ) THEN
    EXECUTE 'CREATE SCHEMA app AUTHORIZATION CURRENT_USER';
  ELSE
    -- asigură proprietarul (dacă rulăm ca superuser)
    BEGIN
      EXECUTE 'ALTER SCHEMA app OWNER TO CURRENT_USER';
    EXCEPTION WHEN insufficient_privilege THEN
      -- ignoră dacă nu avem drepturi (ex: deja deținută de alt rol non-superuser)
      NULL;
    END;
  END IF;
END$$;

-- 2) Setări persistente de search_path
--    a) la nivel de BAZĂ DE DATE (se aplică tuturor conexiunilor către acest DB)
DO $$
DECLARE
  dbname text := current_database();
BEGIN
  EXECUTE format('ALTER DATABASE %I SET search_path = app, public', dbname);
END$$;

--    b) la nivel de ROL curent, dar DOAR pentru acest DB
DO $$
DECLARE
  dbname text := current_database();
BEGIN
  EXECUTE format('ALTER ROLE CURRENT_USER IN DATABASE %I SET search_path = app, public', dbname);
END$$;

-- 3) Hardening minim pe schema public (evită CREATE arbitrar de la PUBLIC)
DO $$
BEGIN
  BEGIN
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
  EXCEPTION WHEN insufficient_privilege THEN
    -- dacă nu suntem superuser / owner de 'public', ignorăm
    NULL;
  END;
  -- păstrează USAGE (implicit oricum)
  BEGIN
    GRANT USAGE ON SCHEMA public TO PUBLIC;
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;
END$$;

-- 4) Extensii pentru observabilitate & căutare

-- 4.1) pg_stat_statements (în public; necesită shared_preload_libraries configurat)
--      Dacă preload-ul nu este activ, comanda reușește, dar view-ul devine disponibil după restart.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 4.2) pg_trgm relocat în schema 'app'
--      Dacă există deja în altă schemă (ex: public), îl mutăm; altfel îl creăm direct în 'app'.
DO $$
DECLARE
  ext_schema text;
BEGIN
  SELECT n.nspname
    INTO ext_schema
  FROM pg_extension e
  JOIN pg_namespace n ON n.oid = e.extnamespace
  WHERE e.extname = 'pg_trgm';

  IF ext_schema IS NULL THEN
    -- nu e instalată -> instalează în schema 'app'
    EXECUTE 'CREATE EXTENSION pg_trgm WITH SCHEMA app';
  ELSIF ext_schema <> 'app' THEN
    -- instalată în altă parte -> mută în 'app'
    EXECUTE 'ALTER EXTENSION pg_trgm SET SCHEMA app';
  END IF;
END$$;

-- 5) Comentarii utile (documentare)
COMMENT ON SCHEMA app IS 'Schema aplicației (sursă de adevăr). Obiectiv: totul în app; public doar pentru extensii standard.';

-- 6) Verificări rapide (opțional: inofensive)
--    (Aceste SELECT-uri nu opresc init-ul; sunt doar informative în logs.)
DO $$
DECLARE
  msg text;
BEGIN
  SELECT 'search_path (DB) set to: ' || current_setting('search_path') INTO msg;
  RAISE NOTICE '%', msg;
EXCEPTION WHEN others THEN
  NULL;
END$$;

-- 7) Asigură-te că sesiunile curente folosesc schema corectă (în acest script)
SET search_path TO app, public;

-- 8) (Loc rezervat) – dacă vrei în viitor bootstrap minim de obiecte în app,
--    le poți crea explicit prefixate cu app. (ex: app.example_table)
--    Exemplu comentat:
-- CREATE TABLE IF NOT EXISTS app.__bootstrap_marker(
--   id int PRIMARY KEY,
--   created_at timestamptz DEFAULT now()
--);

```

# path-ul fisierului: Dockerfile  (size=2153 bytes)

```dockerfile
# syntax=docker/dockerfile:1.6
# ==========================
# Dockerfile (multi-stage)
# ==========================

# --- Bază comună ---
FROM python:3.11-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# --- Builder: produce wheels pentru dependențe ---
FROM base AS builder
ARG DEBIAN_FRONTEND=noninteractive
# Toolchain minim pentru pachete care compilează (ex: psycopg2 fără binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Cache pip între build-uri (BuildKit)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir=/wheels -r requirements.txt

# --- Runtime: imagine finală mică, non-root, doar runtime deps ---
FROM base AS runtime
ARG DEBIAN_FRONTEND=noninteractive
# libpq5 e util dacă folosești drivere care se leagă la libpq din sistem
# (poți să-l elimini dacă rămâi exclusiv pe *-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

# User non-root (configurabil prin ARG)
ARG APP_UID=10001
ARG APP_GID=10001
RUN groupadd -g ${APP_GID} app && useradd -u ${APP_UID} -g ${APP_GID} -m -s /usr/sbin/nologin app

# Instalează dependențele din wheels (fără toolchain)
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels

# Copiază aplicația și migrațiile (direct cu proprietar corect)
COPY --chown=app:app alembic.ini alembic.ini
COPY --chown=app:app migrations/ migrations/
COPY --chown=app:app app ./app
COPY --chown=app:app docker/app-entrypoint.sh /app/docker/app-entrypoint.sh
RUN chmod +x /app/docker/app-entrypoint.sh

# Env-uri aplicație
ENV PYTHONPATH=/app \
    APP_PORT=8001

# Expune portul pe care pornește Uvicorn din entrypoint (APP_PORT)
EXPOSE 8001

# Rulează ca non-root
USER app

# Rulează entrypoint-ul (wait-for-db + alembic + uvicorn)
# Dacă în docker-compose.yml ai deja command:, acesta e doar default-ul imaginii.
CMD ["/app/docker/app-entrypoint.sh"]

```

# path-ul fisierului: Makefile  (size=127 bytes)

```makefile
.PHONY: qc ci

qc:
	@bash scripts/quick_check.sh

ci:
	@API_WAIT_RETRIES=120 API_WAIT_SLEEP_SECS=2 bash scripts/quick_check.sh

```

# path-ul fisierului: migrations/env.py  (size=17882 bytes)

```python
# migrations/env.py
from __future__ import annotations

import importlib
import logging
import os
import re
from logging.config import fileConfig
from typing import Any, Dict, Optional, Sequence, Set, Tuple, List

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import URL, make_url

# ------------------------------------------------------------
# Alembic config & logging
# ------------------------------------------------------------
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
log = logging.getLogger("alembic.env")

# ------------------------------------------------------------
# .env (opțional)
# ------------------------------------------------------------
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)
except Exception:
    pass

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}

def _csv_env(name: str) -> Sequence[str]:
    raw = os.getenv(name, "") or ""
    return tuple(s.strip() for s in raw.split(",") if s.strip())

def _csv_env_extensions(name: str) -> Sequence[str]:
    raw = os.getenv(name, "") or ""
    if not raw:
        return ()
    out: list[str] = []
    for token in raw.split(","):
        t = token.strip()
        if not t:
            continue
        if "#" in t:
            t = t.split("#", 1)[0].strip()
        if not t:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_]+", t):
            log.warning("Ignoring invalid PostgreSQL extension name %r from %s", t, name)
            continue
        if t not in out:
            out.append(t)
    return tuple(out)

def _mask_url(url: str) -> str:
    try:
        u = make_url(url)
        if u.password:
            u = u.set(password="***")
        return str(u)
    except Exception:
        return url

def _quote_ident(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'

def _build_url_from_parts() -> Optional[str]:
    driver = (os.getenv("DB_DRIVER") or "").strip()
    host = (os.getenv("DB_HOST") or "").strip()
    port = os.getenv("DB_PORT")
    user = (os.getenv("DB_USER") or "").strip()
    password = (o…*************************************
    dbname = (os.getenv("DB_NAME") or "").strip()
    if not (driver and host and dbname):
        return None
    try:
        url = URL.create(
            drivername=driver,
            username=user or None,
            password=pa…**************
            host=host,
            port=int(port) if port else None,
            database=dbname,
        )
        return str(url)
    except Exception:
        return None

def _get_database_url() -> str:
    env_url = (os.getenv("DATABASE_URL") or "").strip()
    if env_url and "driver://user:pass@localhost/dbname" not in env_url:
        return env_url
    ini_url = (config.get_main_option("sqlalchemy.url") or "").strip()
    if ini_url and "driver://user:pass@localhost/dbname" not in ini_url:
        return ini_url
    built = _build_url_from_parts()
    if built:
        return built
    raise RuntimeError(
        "Nu am găsit URL-ul DB. Setează DATABASE_URL sau sqlalchemy.url în alembic.ini "
        "sau folosește DB_DRIVER/DB_HOST/DB_NAME (+ opțional DB_USER/DB_PASSWORD/DB_PORT)."
    )

# ------------------------------------------------------------
# Config general
# ------------------------------------------------------------
DEFAULT_SCHEMA = (os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app").strip()
VERSION_TABLE = (os.getenv("ALEMBIC_VERSION_TABLE") or "alembic_version").strip()
VERSION_TABLE_SCHEMA = (os.getenv("ALEMBIC_VERSION_TABLE_SCHEMA") or DEFAULT_SCHEMA).strip()

AUTO_CREATE_SCHEMA = _env_bool("AUTO_CREATE_SCHEMA", True)
USE_SCHEMA_TRANSLATE = _env_bool("ALEMBIC_USE_SCHEMA_TRANSLATE", True)
MAP_PUBLIC_TO_DEFAULT = _env_bool("ALEMBIC_MAP_PUBLIC_TO_DEFAULT_SCHEMA", False)
ONLY_DEFAULT_SCHEMA = _env_bool("ALEMBIC_ONLY_DEFAULT_SCHEMA", False)
FORCE_BATCH_SQLITE = _env_bool("ALEMBIC_RENDER_AS_BATCH", False)
TX_PER_MIGRATION = _env_bool("ALEMBIC_TRANSACTION_PER_MIGRATION", False)
SKIP_EMPTY_MIGRATIONS = _env_bool("ALEMBIC_SKIP_EMPTY", True)

# ✔ verificări/diag suplimentare
ASSERT_TABLES: Sequence[str] = _csv_env("ALEMBIC_ASSERT_TABLES")
FAIL_IF_PUBLIC_VERSION_TABLE = _env_bool("ALEMBIC_FAIL_IF_PUBLIC_VERSION_TABLE", False)
VERIFY_WITH_NEW_CONN = _env_bool("ALEMBIC_VERIFY_WITH_NEW_CONNECTION", True)
SQL_ECHO = _env_bool("ALEMBIC_SQL_ECHO", False)

EXCLUDE_TABLES: Set[str] = set(_csv_env("ALEMBIC_EXCLUDE_TABLES"))
EXCLUDE_SCHEMAS: Set[str] = set(_csv_env("ALEMBIC_EXCLUDE_SCHEMAS"))

PG_EXTENSIONS: Sequence[str] = _csv_env_extensions("DB_EXTENSIONS")
PG_EXTENSIONS_STRICT = _env_bool("DB_EXTENSIONS_STRICT", False)

# Import modele pentru autogenerate
# poți trece pachete suplimentare prin ALEMBIC_MODEL_PACKAGES=app.models,app.models.emag
MODEL_PACKAGES: Sequence[str] = _csv_env("ALEMBIC_MODEL_PACKAGES") or ("app.models", "app.models.emag")

# ------------------------------------------------------------
# Import metadata + modele (rezilient, agregăm mai multe MetaData)
# ------------------------------------------------------------
metadatas: List[sa.MetaData] = []

def _try_collect_metadata(import_path: str) -> None:
    try:
        mod = importlib.import_module(import_path)
        # Convenții uzuale:
        candidates = [
            getattr(mod, "Base", None),
            getattr(mod, "metadata", None),
        ]
        added = False
        for cand in candidates:
            md = getattr(cand, "metadata", None) if cand is not None else None
            if isinstance(md, sa.MetaData) and md not in metadatas:
                metadatas.append(md)
                added = True
        if added:
            log.info("Loaded metadata from %s", import_path)
        else:
            log.info("Imported %s (no direct metadata found; relying on side effects)", import_path)
    except Exception as exc:
        log.warning("Could not import %r: %s", import_path, exc)

# încearcă întâi câteva căi comune
for path in ("app.database", "app.models", "app.models.emag"):
    _try_collect_metadata(path)

# apoi pachetele declarate în env
for pkg in MODEL_PACKAGES:
    _try_collect_metadata(pkg)

# Fallback dacă nu am găsit nimic
if not metadatas:
    log.warning("No metadata collected; using empty MetaData().")
    metadatas = [sa.MetaData()]

# Alembic acceptă o listă de MetaData în target_metadata
target_metadata: Sequence[sa.MetaData] = metadatas

# ------------------------------------------------------------
# Tx helpers
# ------------------------------------------------------------
def _end_open_tx(conn: sa.engine.Connection, tag: str) -> None:
    """Închide curat o tranzacție implicită dacă există (commit sau rollback)."""
    try:
        in_tx = conn.in_transaction()
    except Exception:
        in_tx = False
    if in_tx:
        try:
            conn.commit()
            log.info("[tx:%s] committed", tag)
        except Exception as exc:
            log.warning("[tx:%s] commit failed: %s; rolling back", tag, exc)
            conn.rollback()

# ------------------------------------------------------------
# Bootstrap PG: schema + extensii
# ------------------------------------------------------------
def _ensure_schema_and_extensions(connection: sa.engine.Connection, schema: str) -> None:
    """Creează schema/extension-urile în aceeași conexiune gestionată de Alembic."""
    if connection.dialect.name != "postgresql" or not schema:
        return
    if AUTO_CREATE_SCHEMA:
        connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}")
    for ext in PG_EXTENSIONS:
        try:
            connection.exec_driver_sql(f"CREATE EXTENSION IF NOT EXISTS {_quote_ident(ext)}")
        except Exception as exc:
            if PG_EXTENSIONS_STRICT:
                raise
            log.warning(
                "Skipping unavailable PostgreSQL extension %r (error: %s). "
                "Set DB_EXTENSIONS_STRICT=1 to fail hard.",
                ext, exc,
            )

def _set_session_search_path(connection: sa.engine.Connection, schema: str) -> None:
    if connection.dialect.name != "postgresql" or not schema:
        return
    connection.exec_driver_sql(f"SET search_path = {_quote_ident(schema)}, public")
    sp = connection.exec_driver_sql("SHOW search_path").scalar()
    log.info("Using SESSION search_path for migrations: %s", sp)

def _diag_connection(connection: sa.engine.Connection, tag: str) -> None:
    try:
        row = connection.exec_driver_sql(
            "select current_database(), current_user, "
            "inet_server_addr()::text, inet_server_port(), "
            "version();"
        ).first()
        sp = connection.exec_driver_sql("show search_path").scalar()
        log.info(
            "[diag:%s] db=%s user=%s addr=%s port=%s sp=%s",
            tag, row[0], row[1], row[2], row[3], sp
        )
    except Exception as exc:
        log.warning("[diag:%s] failed: %s", tag, exc)

def _log_version_tables(connection: sa.engine.Connection, when: str) -> Tuple[bool, bool]:
    if connection.dialect.name != "postgresql":
        return (False, False)
    res = connection.exec_driver_sql(
        """
        SELECT
          to_regclass(%(app)s) AS app_ver,
          to_regclass(%(pub)s) AS public_ver
        """,
        {"app": f'{_quote_ident(VERSION_TABLE_SCHEMA)}.{_quote_ident(VERSION_TABLE)}',
         "pub": f'public.{_quote_ident(VERSION_TABLE)}'},
    ).first()
    app_ver = bool(res[0]) if res else False
    public_ver = bool(res[1]) if res else False
    log.info("[%s] alembic_version in %s=%s, public=%s", when, VERSION_TABLE_SCHEMA, app_ver, public_ver)
    if FAIL_IF_PUBLIC_VERSION_TABLE and public_ver and not app_ver:
        raise RuntimeError(
            f"Found {VERSION_TABLE!r} in public but not in {VERSION_TABLE_SCHEMA!r}. "
            "Probabil migrațiile au rulat cu search_path greșit."
        )
    return (app_ver, public_ver)

# ------------------------------------------------------------
# Verificări post-migrare
# ------------------------------------------------------------
_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _split_table_name(name: str) -> Tuple[str, str]:
    if "." in name:
        s, t = name.split(".", 1)
        s, t = s.strip() or VERSION_TABLE_SCHEMA, t.strip()
    else:
        s, t = VERSION_TABLE_SCHEMA, name.strip()
    if not (_VALID_IDENT.fullmatch(s) and _VALID_IDENT.fullmatch(t)):
        raise ValueError(f"Nume invalid de tabel pentru verificare: {name!r}")
    return s, t

def _assert_tables_exist_url(url: str, schema: str, tables: Sequence[str]) -> None:
    """Verifică existența tabelelor pe o conexiune NOUĂ (după commit)."""
    if not tables:
        return
    eng = sa.create_engine(url, poolclass=pool.NullPool)
    try:
        with eng.connect() as conn:
            _set_session_search_path(conn, schema)
            missing: list[str] = []
            for raw in tables:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    s, t = _split_table_name(raw)
                except ValueError as exc:
                    log.warning("%s", exc)
                    continue
                qn = f"{_quote_ident(s)}.{_quote_ident(t)}"
                ok = bool(conn.exec_driver_sql(
                    "SELECT to_regclass(%(qn)s) IS NOT NULL", {"qn": qn}
                ).scalar())
                if not ok:
                    missing.append(f"{s}.{t}")
            if missing:
                raise RuntimeError("După migrare lipsesc tabelele așteptate: " + ", ".join(missing))
    finally:
        eng.dispose()

# ------------------------------------------------------------
# Filtrări autogenerate
# ------------------------------------------------------------
def include_name(name: str, type_: str, parent_names: Dict[str, Optional[str]]) -> bool:
    if type_ == "schema":
        if not ONLY_DEFAULT_SCHEMA:
            return name not in EXCLUDE_SCHEMAS
        allowed = {VERSION_TABLE_SCHEMA, "public"} if VERSION_TABLE_SCHEMA != "public" else {"public"}
        return (name in allowed) and (name not in EXCLUDE_SCHEMAS)

    schema = parent_names.get("schema_name") or parent_names.get("schema")
    if schema and schema in EXCLUDE_SCHEMAS:
        return False
    if ONLY_DEFAULT_SCHEMA and schema and schema not in {VERSION_TABLE_SCHEMA, "public"}:
        return False
    return True

def include_object(object_: Any, name: str, type_: str, reflected: bool, compare_to: Any) -> bool:
    if type_ == "table":
        if name == VERSION_TABLE or name in EXCLUDE_TABLES:
            return False
        obj_schema = getattr(object_, "schema", None)
        if ONLY_DEFAULT_SCHEMA and obj_schema and obj_schema not in {VERSION_TABLE_SCHEMA, "public"}:
            return False
    return True

def process_revision_directives(context_, revision, directives):
    if not SKIP_EMPTY_MIGRATIONS:
        return
    autogen = bool(getattr(getattr(config, "cmd_opts", object()), "autogenerate", False))
    if autogen and directives:
        script = directives[0]
        if getattr(script, "upgrade_ops", None) and script.upgrade_ops.is_empty():
            directives[:] = []
            log.info("No schema changes detected; skipping empty migration.")

# ------------------------------------------------------------
# Offline migrations
# ------------------------------------------------------------
def run_migrations_offline() -> None:
    url = _get_database_url()
    log.info(
        "[alembic] offline url=%s | schema=%s | version_table=%s (%s) | extensions=%s",
        _mask_url(url), DEFAULT_SCHEMA, VERSION_TABLE, VERSION_TABLE_SCHEMA, ", ".join(PG_EXTENSIONS) or "-",
    )

    configure_kwargs: Dict[str, Any] = dict(
        url=url,
        target_metadata=target_metadata,
        include_name=include_name,
        include_object=include_object,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        version_table=VERSION_TABLE,
        version_table_schema=VERSION_TABLE_SCHEMA,
        process_revision_directives=process_revision_directives,
        transaction_per_migration=TX_PER_MIGRATION,
    )

    if USE_SCHEMA_TRANSLATE and DEFAULT_SCHEMA:
        schema_map: Dict[Optional[str], Optional[str]] = {None: DEFAULT_SCHEMA}
        if MAP_PUBLIC_TO_DEFAULT and DEFAULT_SCHEMA:
            schema_map["public"] = DEFAULT_SCHEMA
        configure_kwargs["schema_translate_map"] = schema_map

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()

# ------------------------------------------------------------
# Online migrations
# ------------------------------------------------------------
def run_migrations_online() -> None:
    url = _get_database_url()
    log.info(
        "[alembic] online url=%s | schema=%s | version_table=%s (%s) | extensions=%s",
        _mask_url(url), DEFAULT_SCHEMA, VERSION_TABLE, VERSION_TABLE_SCHEMA, ", ".join(PG_EXTENSIONS) or "-",
    )

    engine = sa.create_engine(url, poolclass=pool.NullPool, echo=SQL_ECHO)

    with engine.connect() as connection:
        _diag_connection(connection, "pre")

        _ensure_schema_and_extensions(connection, DEFAULT_SCHEMA)
        _set_session_search_path(connection, DEFAULT_SCHEMA)
        _log_version_tables(connection, when="before")

        # ★ Închide BEGIN(implicit) creat de apelurile anterioare
        _end_open_tx(connection, "pre")

        render_as_batch = FORCE_BATCH_SQLITE or (connection.dialect.name == "sqlite")

        configure_kwargs: Dict[str, Any] = dict(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            render_as_batch=render_as_batch,
            version_table=VERSION_TABLE,
            version_table_schema=VERSION_TABLE_SCHEMA,
            process_revision_directives=process_revision_directives,
            transaction_per_migration=TX_PER_MIGRATION,
        )

        if USE_SCHEMA_TRANSLATE and DEFAULT_SCHEMA:
            schema_map: Dict[Optional[str], Optional[str]] = {None: DEFAULT_SCHEMA}
            if MAP_PUBLIC_TO_DEFAULT and DEFAULT_SCHEMA:
                schema_map["public"] = DEFAULT_SCHEMA
            configure_kwargs["schema_translate_map"] = schema_map

        context.configure(**configure_kwargs)

        with context.begin_transaction():
            context.run_migrations()

        _end_open_tx(connection, "alembic")

        _log_version_tables(connection, when="after")
        _diag_connection(connection, "post")

        # curățăm orice tranzacție implicită deschisă de diag
        try:
            connection.rollback()
        except Exception:
            pass

    # ✅ verificăm DOAR DUPĂ ce s-a închis conexiunea de migrare
    if VERIFY_WITH_NEW_CONN and ASSERT_TABLES:
        _assert_tables_exist_url(url, DEFAULT_SCHEMA, ASSERT_TABLES)

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

```

# path-ul fisierului: migrations/README  (size=38 bytes)

```
Generic single-database configuration.
```

# path-ul fisierului: migrations/script.py.mako  (size=704 bytes)

```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}

```

# path-ul fisierului: migrations/versions/2025_09_02-cb8d65506439_merge_emag_mvs_concurrent_perf_indexes.py  (size=582 bytes)

```python
"""merge: eMAG MVs concurrent + perf indexes

Revision ID: cb8d65506439
Revises: a3b4c5d6e7f8, a3b4c5d6e7f9
Create Date: 2025-09-02
"""
from __future__ import annotations

from alembic import op  # noqa: F401  (păstrat pt. consistență cu template-ul)
import sqlalchemy as sa  # noqa: F401

# Alembic identifiers
revision = "cb8d65506439"
down_revision = ("a3b4c5d6e7f8", "a3b4c5d6e7f9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op merge: doar unește cele două heads într-un singur head.
    pass


def downgrade() -> None:
    # No-op
    pass

```

# path-ul fisierului: migrations/versions/7786bc4a4177_baseline_models.py  (size=1641 bytes)

```python
"""baseline models: create products (if missing)"""

from __future__ import annotations

import os
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision: str = "7786bc4a4177"
down_revision: Union[str, Sequence[str], None] = "89a0ef6bfc2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
IDX_NAME = "ix_products_name"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # create table if missing
    if TABLE not in set(insp.get_table_names(schema=SCHEMA)):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("price", sa.Numeric(12, 2), nullable=True),
            schema=SCHEMA,
        )

    # non-unique index on name
    idx_names = {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}
    if IDX_NAME not in idx_names:
        op.create_index(IDX_NAME, TABLE, ["name"], schema=SCHEMA, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    idx_names = {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}
    if IDX_NAME in idx_names:
        op.drop_index(IDX_NAME, table_name=TABLE, schema=SCHEMA)

    if TABLE in set(insp.get_table_names(schema=SCHEMA)):
        op.drop_table(TABLE, schema=SCHEMA)

```

# path-ul fisierului: migrations/versions/89a0ef6bfc2b_init_schema.py  (size=1489 bytes)

```python
"""Initialize target schema and session search_path (PostgreSQL only).

Revision ID: 89a0ef6bfc2b
Revises:
Create Date: 2025-08-31 01:09:03.503954
"""
from __future__ import annotations

import os
from typing import Sequence, Union
from alembic import op

# --- Alembic identifiers ---
revision: str = "89a0ef6bfc2b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    schema = (DEFAULT_SCHEMA or "app").strip() or "app"

    # 1) Creează schema dacă lipsește (idempotent)
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_qi(schema)};")

    # 2) Setează search_path în sesiunea curentă (util și la rulări manuale)
    op.execute(f"SET search_path TO {_qi(schema)}, public;")


def downgrade() -> None:
    # Nu ștergem schema by default (evităm pierderea de obiecte).
    # Activează explicit prin env dacă vrei să o dai jos controlat.
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if os.getenv("DROP_SCHEMA_ON_DOWNGRADE") == "1":
        schema = (DEFAULT_SCHEMA or "app").strip() or "app"
        op.execute(f"DROP SCHEMA IF EXISTS {_qi(schema)} CASCADE;")

```

# path-ul fisierului: migrations/versions/a1f2e3d4c5f6_add_price_and_lower_name_indexes.py  (size=2316 bytes)

```python
"""Add indexes for products (price, lower(name)).

- ix_products_price: btree on (price), all dialects
- ix_products_name_lower: functional index on lower(name), PostgreSQL only
"""

from __future__ import annotations

import os
from typing import Optional
from alembic import op
import sqlalchemy as sa

revision = "a1f2e3d4c5f6"
down_revision = "c98b7cf3c0cf"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
IDX_PRICE = "ix_products_price"
IDX_NAME_LOWER = "ix_products_name_lower"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _qt(schema: str | None, table: str) -> str:
    return f'{_qi(schema)}.{_qi(table)}' if schema else _qi(table)


def _index_exists(bind, schema: Optional[str], table: str, name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return name in {ix["name"] for ix in insp.get_indexes(table, schema=schema)}
    except NotImplementedError:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    schema = (SCHEMA or "").strip() or None

    # price index
    if dialect == "postgresql":
        if not _index_exists(bind, schema, TABLE, IDX_PRICE):
            op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS "{IDX_PRICE}" ON {_qt(schema, TABLE)} (price)'))
        # lower(name) functional index
        if not _index_exists(bind, schema, TABLE, IDX_NAME_LOWER):
            op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS "{IDX_NAME_LOWER}" ON {_qt(schema, TABLE)} (lower(name))'))
    else:
        if not _index_exists(bind, schema, TABLE, IDX_PRICE):
            op.create_index(IDX_PRICE, TABLE, ["price"], schema=schema, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    schema = (SCHEMA or "").strip() or None

    if dialect == "postgresql":
        # drop functional index first, then price
        op.execute(sa.text(f'DROP INDEX IF EXISTS {(_qi(schema) + ".") if schema else ""}"{IDX_NAME_LOWER}"'))
        op.execute(sa.text(f'DROP INDEX IF EXISTS {(_qi(schema) + ".") if schema else ""}"{IDX_PRICE}"'))
    else:
        if _index_exists(bind, schema, TABLE, IDX_PRICE):
            op.drop_index(IDX_PRICE, table_name=TABLE, schema=schema)

```

# path-ul fisierului: migrations/versions/a2b3c4d5e6f7_emag_core_schema.py  (size=18453 bytes)

```python
# migrations/versions/a2b3c4d5e6f7_emag_core_schema.py
"""eMAG core schema (accounts, map, offers, stock/price history, images, mviews)

Revision ID: a2b3c4d5e6f7
Revises: f0e1d2c3b4a5
Create Date: 2025-09-02
"""
from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa


# Alembic identifiers
revision = "a2b3c4d5e6f7"
down_revision = "f0e1d2c3b4a5"
branch_labels = None
depends_on = None


# --------------------------- Helpers ---------------------------

def _qi(s: str) -> str:
    """Quote identifier."""
    return '"' + s.replace('"', '""') + '"'


def _qn(schema: str, name: str) -> str:
    """Qualified name schema.name (or just name for public)."""
    return f"{_qi(schema)}.{_qi(name)}" if schema and schema != "public" else _qi(name)


def _set_local_search_path(schema: str) -> None:
    op.execute(f"SET LOCAL search_path TO {_qi(schema)}, public")


def _ensure_country_code_enum(schema: str) -> None:
    """Create ENUM schema.country_code and ensure values exist (idempotent)."""
    # NOTE: use EXECUTE format with %I (identifier) / %L (literal) to avoid quoting bugs
    op.execute(f"""
    DO $$
    DECLARE typ_oid oid;
    BEGIN
      SELECT t.oid
        INTO typ_oid
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
      WHERE t.typname = 'country_code' AND n.nspname = '{schema}';

      IF typ_oid IS NULL THEN
        EXECUTE format('CREATE TYPE %I.%I AS ENUM (%L, %L, %L)',
                       '{schema}', 'country_code', 'RO', 'BG', 'HU');
      END IF;

      -- add values defensively, in case type exists but values differ
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L', '{schema}','country_code','RO');
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L', '{schema}','country_code','BG');
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L', '{schema}','country_code','HU');
    END$$;
    """)


def _cast_country_to_enum(schema: str, table: str, default: str = "RO") -> None:
    """Cast TEXT country -> schema.country_code, keeping DEFAULT."""
    tbl = _qn(schema, table)
    enum_t = _qn(schema, "country_code")
    op.execute(f"ALTER TABLE {tbl} ALTER COLUMN country DROP DEFAULT;")
    op.execute(f"ALTER TABLE {tbl} ALTER COLUMN country TYPE {enum_t} USING country::text::{enum_t};")
    op.execute(f"ALTER TABLE {tbl} ALTER COLUMN country SET DEFAULT '{default}'::{enum_t};")


def _drop_enum_if_unused(schema: str, name: str) -> None:
    """Drop ENUM schema.name iff no columns still use it."""
    op.execute(f"""
    DO $$
    DECLARE typ_oid oid;
    DECLARE cnt int;
    BEGIN
      SELECT t.oid
        INTO typ_oid
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
      WHERE t.typname = '{name}' AND n.nspname = '{schema}';

      IF typ_oid IS NOT NULL THEN
        SELECT count(*) INTO cnt
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE a.atttypid = typ_oid AND a.attnum > 0 AND NOT a.attisdropped;

        IF cnt = 0 THEN
          EXECUTE format('DROP TYPE %I.%I', '{schema}', '{name}');
        END IF;
      END IF;
    END$$;
    """)


# -------------------------------- Upgrade --------------------------------

def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Determine target schema at runtime (safe: no op.get_context() at module import)
    ctx = op.get_context()
    schema = ctx.version_table_schema or os.getenv("DB_SCHEMA", "app")

    if dialect == "postgresql":
        _set_local_search_path(schema)
        _ensure_country_code_enum(schema)

    # emag_account
    op.create_table(
        "emag_account",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=schema,
        comment="Conturi eMAG (MAIN/FBE).",
    )

    # trigger utilitar: set_updated_at()
    if dialect == "postgresql":
        op.execute(f"""
        CREATE OR REPLACE FUNCTION {_qn(schema, "set_updated_at")}() RETURNS trigger AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

    # emag_product_map (country ca TEXT, apoi CAST la ENUM pentru a evita CREATE TYPE implicit)
    op.create_table(
        "emag_product_map",
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.SmallInteger(), sa.ForeignKey(f"{schema}.emag_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.Text(), nullable=False, server_default=sa.text("'RO'")),
        sa.Column("emag_sku", sa.Text(), nullable=False),
        sa.Column("ean", sa.Text(), nullable=True),
        sa.Column("ean_list", sa.ARRAY(sa.Text()), nullable=True) if dialect == "postgresql" else sa.Column("ean_list", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("account_id", "country", "emag_sku", name="pk_emag_product_map"),
        schema=schema,
    )
    op.create_unique_constraint(
        "ux_emag_product_map_acc_country_product",
        "emag_product_map",
        ["account_id", "country", "product_id"],
        schema=schema,
    )
    op.create_index("ix_emag_product_map_product_id", "emag_product_map", ["product_id"], schema=schema)
    if dialect == "postgresql":
        op.create_index(
            "ix_emag_product_map_emag_sku_lower",
            "emag_product_map",
            [sa.text("lower(emag_sku)")],
            schema=schema,
        )
        op.execute(f"""
        CREATE TRIGGER trg_emag_product_map_updated_at
          BEFORE UPDATE ON {_qn(schema, "emag_product_map")}
          FOR EACH ROW EXECUTE FUNCTION {_qn(schema, "set_updated_at")}();
        """)
        _cast_country_to_enum(schema, "emag_product_map")
    else:
        op.create_index("ix_emag_product_map_emag_sku", "emag_product_map", ["emag_sku"], schema=schema)

    # emag_offers (country ca TEXT, apoi CAST la ENUM)
    op.create_table(
        "emag_offers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("account_id", sa.SmallInteger(), sa.ForeignKey(f"{schema}.emag_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.Text(), nullable=False, server_default=sa.text("'RO'")),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=True),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("handling_time", sa.Integer(), nullable=True),
        sa.Column("supply_lead_time", sa.Integer(), nullable=True),
        sa.Column("validation_status_value", sa.SmallInteger(), nullable=True),
        sa.Column("validation_status_text", sa.Text(), nullable=True),
        sa.Column("images_count", sa.Integer(), nullable=True),
        sa.Column("stock_total", sa.Integer(), nullable=True),
        sa.Column("general_stock", sa.Integer(), nullable=True),
        sa.Column("estimated_stock", sa.Integer(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=True),
        sa.Column("ean", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "country", "product_id", name="ux_emag_offers_acc_country_product"),
        schema=schema,
    )
    op.create_index(
        "ix_emag_offers_acc_country_prod",
        "emag_offers",
        ["account_id", "country", "product_id"],
        schema=schema,
    )
    op.create_index(
        "ix_emag_offers_acc_country_price",
        "emag_offers",
        ["account_id", "country", "sale_price", "product_id"],
        schema=schema,
    )
    op.create_index(
        "ix_emag_offers_stock_total",
        "emag_offers",
        ["stock_total"],
        schema=schema,
    )
    if dialect == "postgresql":
        op.execute(f"""
        CREATE TRIGGER trg_emag_offers_updated_at
          BEFORE UPDATE ON {_qn(schema, "emag_offers")}
          FOR EACH ROW EXECUTE FUNCTION {_qn(schema, "set_updated_at")}();
        """)
        _cast_country_to_enum(schema, "emag_offers")

    # stoc curent pe depozit
    op.create_table(
        "emag_offer_stock_by_wh",
        sa.Column("offer_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.emag_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_code", sa.Text(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("incoming", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("offer_id", "warehouse_code", name="pk_emag_offer_stock_by_wh"),
        schema=schema,
    )
    op.create_index(
        "ix_emag_offer_stock_by_wh_offer",
        "emag_offer_stock_by_wh",
        ["offer_id"],
        schema=schema,
    )
    if dialect == "postgresql":
        op.execute(f"""
        CREATE TRIGGER trg_emag_offer_stock_by_wh_updated_at
          BEFORE UPDATE ON {_qn(schema, "emag_offer_stock_by_wh")}
          FOR EACH ROW EXECUTE FUNCTION {_qn(schema, "set_updated_at")}();
        """)

    # istorice (partitioned, PG only)
    if dialect == "postgresql":
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {_qn(schema, "emag_offer_prices_hist")} (
          offer_id    BIGINT NOT NULL REFERENCES {_qn(schema, "emag_offers")}(id) ON DELETE CASCADE,
          recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          currency    CHAR(3) NOT NULL,
          sale_price  NUMERIC(12,2) NOT NULL CHECK (sale_price >= 0),
          PRIMARY KEY (offer_id, recorded_at)
        ) PARTITION BY RANGE (recorded_at);

        CREATE TABLE IF NOT EXISTS {_qn(schema, "emag_offer_stock_hist")} (
          offer_id       BIGINT NOT NULL REFERENCES {_qn(schema, "emag_offers")}(id) ON DELETE CASCADE,
          warehouse_code TEXT NOT NULL,
          recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
          stock          INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
          reserved       INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
          incoming       INTEGER NOT NULL DEFAULT 0 CHECK (incoming >= 0),
          PRIMARY KEY (offer_id, warehouse_code, recorded_at)
        ) PARTITION BY RANGE (recorded_at);
        """)

        # creează două partiții: luna curentă și luna următoare
        op.execute(f"""
        DO $$
        DECLARE
          start_curr date := date_trunc('month', now())::date;
          start_next date := (date_trunc('month', now()) + interval '1 month')::date;
          start_next2 date := (date_trunc('month', now()) + interval '2 month')::date;
          nm text;
        BEGIN
          nm := to_char(start_curr, '"p_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_prices_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_curr, start_next);
          nm := to_char(start_next, '"p_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_prices_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_next, start_next2);

          nm := to_char(start_curr, '"s_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_stock_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_curr, start_next);
          nm := to_char(start_next, '"s_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_stock_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_next, start_next2);
        END$$;
        """)

    # imagini & istoric validare
    op.create_table(
        "emag_images",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=schema,
    )
    op.create_unique_constraint(
        "ux_emag_images_product_url",
        "emag_images",
        ["product_id", "url"],
        schema=schema,
    )
    if dialect == "postgresql":
        op.create_index(
            "ix_emag_images_main",
            "emag_images",
            ["product_id"],
            schema=schema,
            postgresql_where=sa.text("is_main"),
        )
    else:
        op.create_index("ix_emag_images_product", "emag_images", ["product_id"], schema=schema)

    op.create_table(
        "emag_validation_status_hist",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("offer_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.emag_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=schema,
    )
    op.create_index(
        "ix_emag_validation_status_hist_offer_time",
        "emag_validation_status_hist",
        ["offer_id", "occurred_at"],
        unique=False,
        schema=schema,
    )

    # materialized views
    if dialect == "postgresql":
        op.execute(f"""
        CREATE MATERIALIZED VIEW IF NOT EXISTS {_qn(schema, "mv_emag_stock_summary")} AS
        SELECT
          offer_id,
          SUM(stock)    AS stock_total,
          SUM(reserved) AS reserved_total,
          MAX(updated_at) AS last_update
        FROM {_qn(schema, "emag_offer_stock_by_wh")}
        GROUP BY offer_id
        WITH NO DATA;

        CREATE MATERIALIZED VIEW IF NOT EXISTS {_qn(schema, "mv_emag_best_offer")} AS
        SELECT
          o.id AS offer_id,
          o.account_id,
          o.country,
          o.product_id,
          o.currency,
          o.sale_price,
          COALESCE(s.stock_total, o.stock_total) AS stock_total,
          GREATEST(o.updated_at, COALESCE(s.last_update, o.updated_at)) AS as_of
        FROM {_qn(schema, "emag_offers")} o
        LEFT JOIN {_qn(schema, "mv_emag_stock_summary")} s ON s.offer_id = o.id
        WITH NO DATA;
        """)


# -------------------------------- Downgrade -------------------------------

def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    ctx = op.get_context()
    schema = ctx.version_table_schema or os.getenv("DB_SCHEMA", "app")

    if dialect == "postgresql":
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {_qn(schema, 'mv_emag_best_offer')};")
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {_qn(schema, 'mv_emag_stock_summary')};")

    op.drop_index("ix_emag_validation_status_hist_offer_time", table_name="emag_validation_status_hist", schema=schema)
    op.drop_table("emag_validation_status_hist", schema=schema)

    if dialect == "postgresql":
        op.drop_index("ix_emag_images_main", table_name="emag_images", schema=schema)
    else:
        op.drop_index("ix_emag_images_product", table_name="emag_images", schema=schema)

    op.drop_constraint("ux_emag_images_product_url", "emag_images", type_="unique", schema=schema)
    op.drop_table("emag_images", schema=schema)

    if dialect == "postgresql":
        op.execute(f"DROP TABLE IF EXISTS {_qn(schema, 'emag_offer_stock_hist')} CASCADE;")
        op.execute(f"DROP TABLE IF EXISTS {_qn(schema, 'emag_offer_prices_hist')} CASCADE;")

    op.drop_index("ix_emag_offer_stock_by_wh_offer", table_name="emag_offer_stock_by_wh", schema=schema)
    op.drop_table("emag_offer_stock_by_wh", schema=schema)

    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS trg_emag_offers_updated_at ON {_qn(schema, 'emag_offers')};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_emag_product_map_updated_at ON {_qn(schema, 'emag_product_map')};")

    op.drop_index("ix_emag_offers_stock_total", table_name="emag_offers", schema=schema)
    op.drop_index("ix_emag_offers_acc_country_price", table_name="emag_offers", schema=schema)
    op.drop_index("ix_emag_offers_acc_country_prod", table_name="emag_offers", schema=schema)
    op.drop_table("emag_offers", schema=schema)

    if dialect == "postgresql":
        op.drop_index("ix_emag_product_map_emag_sku_lower", table_name="emag_product_map", schema=schema)
    else:
        op.drop_index("ix_emag_product_map_emag_sku", table_name="emag_product_map", schema=schema)

    op.drop_index("ix_emag_product_map_product_id", table_name="emag_product_map", schema=schema)
    op.drop_constraint("ux_emag_product_map_acc_country_product", "emag_product_map", type_="unique", schema=schema)
    op.drop_table("emag_product_map", schema=schema)

    op.drop_table("emag_account", schema=schema)

    if dialect == "postgresql":
        op.execute(f"DROP FUNCTION IF EXISTS {_qn(schema, 'set_updated_at')}();")
        _drop_enum_if_unused(schema, "country_code")

```

# path-ul fisierului: migrations/versions/a3b4c5d6e7f8_mv_concurrent_refresh.py  (size=2967 bytes)

```python
# migrations/versions/a3b4c5d6e7f8_mv_concurrent_refresh.py
"""Enable concurrent refresh for eMAG MVs"""
from alembic import op, context
from sqlalchemy import text
import os

# Alembic identifiers
revision = "a3b4c5d6e7f8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

# Materialized views we manage here
MVS = ("mv_emag_stock_summary", "mv_emag_best_offer")


def _schema() -> str:
    """Allow overriding with `alembic -x schema=...`; else use alembic/env/DEFAULT."""
    return (
        context.get_x_argument(as_dictionary=True).get("schema")
        or op.get_context().version_table_schema
        or os.getenv("DB_SCHEMA", "app")
    )


def _is_populated(conn, schema: str, mv: str) -> bool:
    q = text(
        """
        SELECT ispopulated
        FROM pg_matviews
        WHERE schemaname = :schema AND matviewname = :mv
        """
    )
    return bool(conn.execute(q, {"schema": schema, "mv": mv}).scalar())


def _has_unique_index(conn, schema: str, mv: str) -> bool:
    # CONCURRENTLY requires a UNIQUE, non-partial index on the MV
    q = text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname = :schema
            AND c.relname  = :mv
            AND i.indisunique
            AND i.indpred IS NULL
        )
        """
    )
    return bool(conn.execute(q, {"schema": schema, "mv": mv}).scalar())


def _ensure_unique_indexes(schema: str) -> None:
    # Create the required UNIQUE indexes (regular create is fine inside txn)
    op.execute(
        text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_stock_summary_offer '
            f'ON "{schema}".mv_emag_stock_summary (offer_id);'
        )
    )
    op.execute(
        text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_best_offer_offer '
            f'ON "{schema}".mv_emag_best_offer (offer_id);'
        )
    )


def _refresh_mv(schema: str, mv: str) -> None:
    conn = op.get_bind()
    populated = _is_populated(conn, schema, mv)
    has_uq = _has_unique_index(conn, schema, mv)

    if populated and has_uq:
        # CONCURRENTLY must be outside the migration txn
        with op.get_context().autocommit_block():
            op.execute(text(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{schema}".{mv};'))
    else:
        # First population (or missing UNIQUE) -> plain refresh in txn
        op.execute(text(f'REFRESH MATERIALIZED VIEW "{schema}".{mv};'))


def upgrade() -> None:
    schema = _schema()
    _ensure_unique_indexes(schema)
    for mv in MVS:
        _refresh_mv(schema, mv)


def downgrade() -> None:
    schema = _schema()
    # Drop indexes created in this migration
    op.execute(text(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_best_offer_offer;'))
    op.execute(text(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_stock_summary_offer;'))

```

# path-ul fisierului: migrations/versions/a3b4c5d6e7f9_perf_indexes.py  (size=835 bytes)

```python
# migrations/versions/a3b4c5d6e7f9_perf_indexes.py
"""Perf indexes for eMAG tables"""
from alembic import op
import os

revision = "a3b4c5d6e7f9"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

def upgrade():
    schema = op.get_context().version_table_schema or os.getenv("DB_SCHEMA", "app")
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_emag_offers_acc_country ON "{schema}".emag_offers (account_id, country);')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_emag_product_map_acc_country ON "{schema}".emag_product_map (account_id, country);')

def downgrade():
    schema = op.get_context().version_table_schema or os.getenv("DB_SCHEMA", "app")
    op.execute(f'DROP INDEX IF EXISTS "{schema}".ix_emag_product_map_acc_country;')
    op.execute(f'DROP INDEX IF EXISTS "{schema}".ix_emag_offers_acc_country;')

```

# path-ul fisierului: migrations/versions/c98b7cf3c0cf_add_sku_to_products.py  (size=1845 bytes)

```python
"""add sku column to products + partial unique index (PG)"""

from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa

revision = "c98b7cf3c0cf"
down_revision = "7786bc4a4177"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
COL = "sku"
IDX = "ix_products_sku"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _qt(schema: str | None, table: str) -> str:
    return f'{_qi(schema)}.{_qi(table)}' if schema else _qi(table)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    insp = sa.inspect(bind)

    # 1) add column if missing
    cols = {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}
    if COL not in cols:
        with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
            batch_op.add_column(sa.Column(COL, sa.String(64), nullable=True))

    # 2) index
    idx_names = {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}
    if IDX not in idx_names:
        if dialect == "postgresql":
            op.execute(
                sa.text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "{IDX}" '
                    f"ON {_qt(SCHEMA, TABLE)} ({_qi(COL)}) WHERE {_qi(COL)} IS NOT NULL"
                )
            )
        else:
            op.create_index(IDX, TABLE, [COL], unique=False, schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if IDX in {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}:
        op.drop_index(IDX, table_name=TABLE, schema=SCHEMA)

    if COL in {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}:
        with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
            batch_op.drop_column(COL)

```

# path-ul fisierului: migrations/versions/cc1e2f3a4b5c_add_check_price_nonnegative.py  (size=1779 bytes)

```python
"""Add CHECK constraint for non-negative price on products (NOT VALID first)."""

from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa

# Alembic revision identifiers
revision = "cc1e2f3a4b5c"
down_revision = "a1f2e3d4c5f6"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
CK_NAME = "ck_products_price_nonnegative"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Add NOT VALID if missing, then best-effort VALIDATE
        op.execute(
            f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE c.conname = '{CK_NAME}'
          AND n.nspname = '{SCHEMA}'
          AND t.relname = '{TABLE}'
    ) THEN
        EXECUTE 'ALTER TABLE "{SCHEMA}"."{TABLE}" '
                'ADD CONSTRAINT "{CK_NAME}" CHECK (price IS NULL OR price >= 0) NOT VALID';
        BEGIN
            EXECUTE 'ALTER TABLE "{SCHEMA}"."{TABLE}" VALIDATE CONSTRAINT "{CK_NAME}"';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END IF;
END$$;
"""
        )
    else:
        # generic path for non-PG
        insp = sa.inspect(bind)
        existing = {ck["name"] for ck in insp.get_check_constraints(TABLE, schema=SCHEMA)}
        if CK_NAME not in existing:
            with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
                batch_op.create_check_constraint(CK_NAME, "price IS NULL OR price >= 0")


def downgrade() -> None:
    op.execute(f'ALTER TABLE "{SCHEMA}"."{TABLE}" DROP CONSTRAINT IF EXISTS "{CK_NAME}";')

```

# path-ul fisierului: migrations/versions/d2c3b4a5f6e7_add_categories_and_product_categories.py  (size=3569 bytes)

```python
"""Add categories and product_categories tables with indexes and FK CASCADE."""

from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = "d2c3b4a5f6e7"
down_revision = "cc1e2f3a4b5c"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"

T_CAT = "categories"
T_PC = "product_categories"
IX_CAT_NAME_LOWER = "ix_categories_name_lower"
IX_PC_CAT = "ix_product_categories_category_id"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _qt(schema: str | None, table: str) -> str:
    return f'{_qi(schema)}.{_qi(table)}' if schema else _qi(table)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    tables = set(insp.get_table_names(schema=SCHEMA))

    # 1) categories
    if T_CAT not in tables:
        op.create_table(
            T_CAT,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            schema=SCHEMA,
        )

    # Unique pe nume: functional (PG) sau constraint clasic pe alte dialecte
    idx_cat = {ix["name"] for ix in insp.get_indexes(T_CAT, schema=SCHEMA)}
    if dialect == "postgresql":
        if IX_CAT_NAME_LOWER not in idx_cat:
            op.execute(sa.text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "{IX_CAT_NAME_LOWER}" '
                f"ON {_qt(SCHEMA, T_CAT)} (lower(name))"
            ))
    else:
        uqs = {uc["name"] for uc in insp.get_unique_constraints(T_CAT, schema=SCHEMA)}
        if "uq_categories_name" not in uqs:
            with op.batch_alter_table(T_CAT, schema=SCHEMA) as batch_op:
                batch_op.create_unique_constraint("uq_categories_name", ["name"])

    # 2) product_categories (M2M)
    if T_PC not in tables:
        op.create_table(
            T_PC,
            sa.Column("product_id", sa.Integer, nullable=False),
            sa.Column("category_id", sa.Integer, nullable=False),
            sa.PrimaryKeyConstraint("product_id", "category_id", name="pk_product_categories"),
            sa.ForeignKeyConstraint(
                ["product_id"],
                [f"{SCHEMA}.products.id"],
                ondelete="CASCADE",
                name="fk_product_categories_product_id_products",
            ),
            sa.ForeignKeyConstraint(
                ["category_id"],
                [f"{SCHEMA}.categories.id"],
                ondelete="CASCADE",
                name="fk_product_categories_category_id_categories",
            ),
            schema=SCHEMA,
        )

    # index util pentru filtrări după categorii
    idx_pc = {ix["name"] for ix in insp.get_indexes(T_PC, schema=SCHEMA)}
    if IX_PC_CAT not in idx_pc:
        op.create_index(IX_PC_CAT, T_PC, ["category_id"], schema=SCHEMA)


def downgrade() -> None:
    # Drop în ordinea inversă a dependențelor
    op.drop_index(IX_PC_CAT, table_name=T_PC, schema=SCHEMA)
    op.drop_table(T_PC, schema=SCHEMA)

    # PG: functional unique index
    op.execute(sa.text(f'DROP INDEX IF EXISTS {(_qi(SCHEMA) + ".") if SCHEMA else ""}"{IX_CAT_NAME_LOWER}"'))
    # non-PG: unique constraint clasic (dacă a fost creat)
    try:
        with op.batch_alter_table(T_CAT, schema=SCHEMA) as batch_op:
            batch_op.drop_constraint("uq_categories_name", type_="unique")
    except Exception:
        pass

    op.drop_table(T_CAT, schema=SCHEMA)

```

# path-ul fisierului: migrations/versions/e7f8a9b0c1d2_validate_check_and_m2m_index.py  (size=2701 bytes)

```python
"""validate CHECK(price>=0) and add composite index on product_categories

Revision ID: e7f8a9b0c1d2
Revises: d2c3b4a5f6e7
Create Date: 2025-08-31
"""
from alembic import op
import os
import re

# Alembic identifiers
revision = "e7f8a9b0c1d2"
down_revision = "d2c3b4a5f6e7"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DB_SCHEMA", "app")

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _assert_safe_schema(schema: str) -> None:
    if not _SAFE_IDENT.match(schema):
        raise ValueError(f"Unsafe schema name: {schema!r}")


def upgrade() -> None:
    _assert_safe_schema(SCHEMA)

    # 1) Asigură existența și VALIDATE pentru CHECK (price >= 0) pe app.products
    op.execute(
        f"""
        DO $$
        DECLARE
          v_exists boolean;
          v_convalidated boolean;
        BEGIN
          -- există deja constraint-ul?
          SELECT EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = '{SCHEMA}'
              AND t.relname = 'products'
              AND c.conname = 'ck_products_price_nonnegative'
          ) INTO v_exists;

          -- dacă nu există, îl adăugăm NOT VALID (idempotent)
          IF NOT v_exists THEN
            EXECUTE format(
              'ALTER TABLE %I.products ADD CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0) NOT VALID',
              '{SCHEMA}'
            );
          END IF;

          -- validăm dacă încă e NOT VALID
          SELECT c.convalidated
          INTO v_convalidated
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
          WHERE n.nspname = '{SCHEMA}'
            AND t.relname = 'products'
            AND c.conname = 'ck_products_price_nonnegative';

          IF NOT v_convalidated THEN
            EXECUTE format(
              'ALTER TABLE %I.products VALIDATE CONSTRAINT ck_products_price_nonnegative',
              '{SCHEMA}'
            );
          END IF;
        END$$;
        """
    )

    # 2) Index compus pe M2M pentru interogări inverse category->products
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS ix_product_categories_category_id_product_id
        ON "{SCHEMA}".product_categories (category_id, product_id);
        """
    )


def downgrade() -> None:
    _assert_safe_schema(SCHEMA)
    # Nu "de-validăm" constraint-ul; doar eliminăm indexul (idempotent)
    op.execute(
        f"""
        DROP INDEX IF EXISTS "{SCHEMA}".ix_product_categories_category_id_product_id;
        """
    )

```

# path-ul fisierului: migrations/versions/f0e1d2c3b4a5_observability_audit_trgm.py  (size=5756 bytes)

```python
from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f0e1d2c3b4a5"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def _set_search_path():
    op.execute("SET LOCAL search_path TO app, public;")


def upgrade():
    _set_search_path()

    # 1) Extensia trgm în schema app (relocatable, sigur să fie IF NOT EXISTS)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA app;")

    # 2) Coloane audit + backfill + default + check validate (fără rewrite)
    tables = ["products", "categories", "product_categories"]
    for t in tables:
        op.execute(f"ALTER TABLE app.{t} ADD COLUMN IF NOT EXISTS created_at timestamptz;")
        op.execute(f"ALTER TABLE app.{t} ADD COLUMN IF NOT EXISTS updated_at timestamptz;")
        # backfill sigur
        op.execute(
            f"""
            UPDATE app.{t}
               SET created_at = COALESCE(created_at, now()),
                   updated_at = COALESCE(updated_at, now())
             WHERE created_at IS NULL OR updated_at IS NULL;
            """
        )
        # default-uri pentru noi rânduri
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN created_at SET DEFAULT now();")
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN updated_at SET DEFAULT now();")

        # NOT NULL ca CHECK VALIDATED (evită lock puternic al SET NOT NULL)
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_{t}_created_at_nn'
              ) THEN
                ALTER TABLE app.{t}
                  ADD CONSTRAINT ck_{t}_created_at_nn CHECK (created_at IS NOT NULL) NOT VALID;
                ALTER TABLE app.{t} VALIDATE CONSTRAINT ck_{t}_created_at_nn;
              END IF;
            END$$;
            """
        )
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_{t}_updated_at_nn'
              ) THEN
                ALTER TABLE app.{t}
                  ADD CONSTRAINT ck_{t}_updated_at_nn CHECK (updated_at IS NOT NULL) NOT VALID;
                ALTER TABLE app.{t} VALIDATE CONSTRAINT ck_{t}_updated_at_nn;
              END IF;
            END$$;
            """
        )

    # 3) Trigger generic pentru audit
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.tg_set_timestamps()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          NEW.updated_at = now();
          IF NEW.created_at IS NULL THEN
            NEW.created_at = now();
          END IF;
          RETURN NEW;
        END$$;
        """
    )

    for t in tables:
        tg = f"tg_{t}_set_timestamps"
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                  FROM pg_trigger
                 WHERE tgname = '{tg}'
                   AND tgrelid = 'app.{t}'::regclass
              ) THEN
                CREATE TRIGGER {tg}
                BEFORE INSERT OR UPDATE ON app.{t}
                FOR EACH ROW EXECUTE FUNCTION app.tg_set_timestamps();
              END IF;
            END$$;
            """
        )

    # 4) Comentarii utile (documentare în catalog)
    op.execute("COMMENT ON TABLE app.products IS 'Catalog products. Time columns are UTC (timestamptz).';")
    op.execute("COMMENT ON COLUMN app.products.created_at IS 'UTC creation timestamp.';")
    op.execute("COMMENT ON COLUMN app.products.updated_at IS 'UTC last update timestamp.';")
    op.execute("COMMENT ON TABLE app.categories IS 'Product categories.';")
    op.execute("COMMENT ON TABLE app.product_categories IS 'M2M between products and categories.';")

    # 5) Indexuri GIN trigram pentru căutare (CONCURRENTLY + IF NOT EXISTS)
    #    Notă: gin_trgm_ops este creat în schema app (pentru că am pus extensia în app).
    with context.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_name_trgm
            ON app.products
            USING gin ((lower(name)) app.gin_trgm_ops);
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_sku_trgm
            ON app.products
            USING gin ((lower(sku)) app.gin_trgm_ops)
            WHERE sku IS NOT NULL;
            """
        )


def downgrade():
    _set_search_path()

    # 1) Drop indexuri (CONCURRENTLY)
    with context.get_context().autocommit_block():
        op.execute("DROP INDEX IF EXISTS app.ix_products_name_trgm;")
        op.execute("DROP INDEX IF EXISTS app.ix_products_sku_trgm;")

    # 2) Drop triggere & funcție
    for t in ["products", "categories", "product_categories"]:
        tg = f"tg_{t}_set_timestamps"
        op.execute(f"DROP TRIGGER IF EXISTS {tg} ON app.{t};")
    op.execute("DROP FUNCTION IF EXISTS app.tg_set_timestamps();")

    # 3) Drop default/check/coloane
    for t in ["products", "categories", "product_categories"]:
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN created_at DROP DEFAULT;")
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN updated_at DROP DEFAULT;")
        op.execute(f"ALTER TABLE app.{t} DROP CONSTRAINT IF EXISTS ck_{t}_created_at_nn;")
        op.execute(f"ALTER TABLE app.{t} DROP CONSTRAINT IF EXISTS ck_{t}_updated_at_nn;")
        op.execute(f"ALTER TABLE app.{t} DROP COLUMN IF EXISTS created_at;")
        op.execute(f"ALTER TABLE app.{t} DROP COLUMN IF EXISTS updated_at;")

    # Extensia pg_trgm rămâne instalată (nerecomandat să o ștergem implicit).

```

# path-ul fisierului: requirements.txt  (size=1114 bytes)

```
# --- Runtime core ------------------------------------------------------------
alembic==1.16.5
fastapi==0.116.1
starlette==0.47.3            # aliniat cu FastAPI 0.116.x
httpx[http2]==0.27.2         # necesar pentru Emag SDK; include h2
h2==4.1.0                    # pin explicit pt. http2 stabil
anyio==4.10.0                # compat cu starlette 0.47.x
typing-extensions==4.15.0

SQLAlchemy==2.0.43
psycopg2-binary==2.9.10
pydantic==2.11.7
pydantic-core==2.33.2        # pin pt. reproducibilitate
tenacity==9.1.2
requests==2.32.3
Mako==1.3.10
python-dotenv==1.0.1
uvicorn[standard]==0.30.6    # include uvloop, httptools, websockets, watchfiles

# --- (opțional) Performanță / QoL -------------------------------------------
# orjson==3.10.7             # FastAPI îl folosește automat dacă e prezent (JSON mai rapid)
# python-multipart==0.0.9    # necesar DOAR dacă expui upload de fișiere

# --- Teste (poți muta într-un requirements-dev.txt dacă vrei imagini mai mici) ---
pytest==8.4.1
pytest-asyncio==0.23.8     # util dacă adaugi teste async
cachetools>=5.3
respx>=0.21

psycopg[binary]==3.2.1
```

# path-ul fisierului: run_dev.sh  (size=143 bytes, exec)

```bash
#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8001

```

# path-ul fisierului: scripts/db-health.sh  (size=8153 bytes, exec)

```bash
# scripts/db-health.sh
#!/usr/bin/env bash
# Verificări sănătate DB eMAG:
# - reachability + versiune alembic
# - partițiile pentru luna următoare (există + atașate la părinți)
# - indexurile unice pe MVs
# - test REFRESH MATERIALIZED VIEW CONCURRENTLY

set -Eeuo pipefail

###############################################################################
# Config
###############################################################################
PGUSER="${PGUSER:-appuser}"
PGDATABASE="${PGDATABASE:-appdb}"
PGSCHEMA="${PGSCHEMA:-app}"
SERVICE_DB="${SERVICE_DB:-db}"
SERVICE_APP="${SERVICE_APP:-app}"

###############################################################################
# Utilitare
###############################################################################
log(){ printf '[%s] %s\n' "$(date '+%F %T %Z')" "$*"; }

# Alege docker compose
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  log "ERROR: nici «docker compose», nici «docker-compose» nu sunt în PATH."
  exit 1
fi

# psql în containerul DB: -X (nu încărca ~/.psqlrc), -A/-t (unaligned, tuples only), -F '|' (separator stabil)
psql_db(){
  $COMPOSE exec -T "$SERVICE_DB" \
    psql -X -A -t -F '|' -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDATABASE" "$@"
}

# (opțional) heads din aplicație
alembic_heads(){
  $COMPOSE exec -T "$SERVICE_APP" alembic heads -v 2>/dev/null || true
}

fail=0

###############################################################################
# 0) Reachability + Alembic
###############################################################################
log "health: DB reachability"
psql_db -c "SELECT 'ok:db'" | sed -n '1p' || { log "FAIL: DB not reachable"; exit 1; }

ALEMBIC_DB="$(psql_db -c "SELECT version_num FROM ${PGSCHEMA}.alembic_version" || echo 'n/a')"
log "alembic (DB): ${ALEMBIC_DB:-n/a}"

HEADS="$(alembic_heads | sed -n 's/^Rev: \([^ ]*\).*/\1/p' | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"
if [[ -n "$HEADS" ]]; then
  log "alembic (app heads): $HEADS"
else
  log "INFO: nu pot obține «alembic heads» din serviciul app (opțional)."
fi

###############################################################################
# 1) Partițiile pentru luna următoare
###############################################################################
log "health: next-month partitions"

# Query robust: folosim heredoc *citat* și variabilă psql :schema
row="$(
  psql_db -v "schema=${PGSCHEMA}" <<'SQL'
WITH d AS (
  SELECT (date_trunc('month', now()) + interval '1 month')::date AS d
), names AS (
  SELECT
    to_char(d, '"p_y"YYYY"m"MM') AS p_name,
    to_char(d, '"s_y"YYYY"m"MM') AS s_name
  FROM d
)
SELECT
  n.p_name,
  EXISTS (  -- price_exists
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.p_name
  ),
  EXISTS (  -- price_attached
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c  ON c.oid=i.inhrelid
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    JOIN pg_class p  ON p.oid=i.inhparent
    JOIN pg_namespace nsp ON nsp.oid=p.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.p_name
      AND nsp.nspname=:'schema' AND p.relname='emag_offer_prices_hist'
  ),
  n.s_name,
  EXISTS (  -- stock_exists
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.s_name
  ),
  EXISTS (  -- stock_attached
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c  ON c.oid=i.inhrelid
    JOIN pg_namespace ns ON ns.oid=c.relnamespace
    JOIN pg_class p  ON p.oid=i.inhparent
    JOIN pg_namespace nsp ON nsp.oid=p.relnamespace
    WHERE ns.nspname=:'schema' AND c.relname=n.s_name
      AND nsp.nspname=:'schema' AND p.relname='emag_offer_stock_hist'
  )
FROM names n;
SQL
)"

# row are 6 câmpuri separate prin |
IFS='|' read -r p_name price_exists price_attached s_name stock_exists stock_attached <<<"$row"

if [[ "${DEBUG:-0}" != "0" ]]; then
  log "DEBUG: expected price part: $p_name"
  log "DEBUG: expected stock  part: $s_name"
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_prices_hist:"
  psql_db -v "schema=${PGSCHEMA}" <<'SQL' | sed '/^$/d'
SELECT '  - '||c.relname
FROM pg_inherits i
JOIN pg_class c ON c.oid=i.inhrelid
JOIN pg_class p ON p.oid=i.inhparent
JOIN pg_namespace np ON np.oid=p.relnamespace
WHERE np.nspname=:'schema' AND p.relname='emag_offer_prices_hist'
ORDER BY c.relname;
SQL
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_stock_hist:"
  psql_db -v "schema=${PGSCHEMA}" <<'SQL' | sed '/^$/d'
SELECT '  - '||c.relname
FROM pg_inherits i
JOIN pg_class c ON c.oid=i.inhrelid
JOIN pg_class p ON p.oid=i.inhparent
JOIN pg_namespace np ON np.oid=p.relnamespace
WHERE np.nspname=:'schema' AND p.relname='emag_offer_stock_hist'
ORDER BY c.relname;
SQL
fi

if [[ "$price_exists" == "t" ]];   then log "OK  : price partition exists ($p_name)"; else log "FAIL: price partition missing"; ((fail++)); fi
if [[ "$price_attached" == "t" ]]; then log "OK  : price partition attached";         else log "FAIL: price partition NOT attached"; ((fail++)); fi
if [[ "$stock_exists" == "t" ]];   then log "OK  : stock partition exists ($s_name)"; else log "FAIL: stock partition missing"; ((fail++)); fi
if [[ "$stock_attached" == "t" ]]; then log "OK  : stock partition attached";         else log "FAIL: stock partition NOT attached"; ((fail++)); fi

###############################################################################
# 2) MV unique index pe (offer_id)
###############################################################################
log "health: MV unique indexes"

check_mv_unique(){
  local mv="$1"
  local ok
  ok="$(psql_db -v "schema=${PGSCHEMA}" <<'SQL'
SELECT EXISTS (
  SELECT 1
  FROM pg_index x
  JOIN pg_class t  ON t.oid=x.indrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname=:'schema' AND t.relname=: 'mv'
    AND x.indisunique
    AND (
      SELECT string_agg(a.attname, ', ' ORDER BY a.attnum)
      FROM unnest(x.indkey) WITH ORDINALITY AS k(attnum, ord)
      JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
    ) = 'offer_id'
);
SQL
)"
  if [[ "$ok" == "t" ]]; then
    log "OK  : ${mv} has unique index on (offer_id)"
  else
    log "FAIL: ${mv} missing unique index (offer_id)"
    ((fail++))
  fi
}
# psql nu știe variabile din shell în heredoc-ul citat; folosim -c aici simplu:
check_mv_unique(){
  local mv="$1"
  local ok
  ok="$(psql_db -c "
SELECT EXISTS (
  SELECT 1
  FROM pg_index x
  JOIN pg_class t  ON t.oid=x.indrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname='${PGSCHEMA}' AND t.relname='${mv}'
    AND x.indisunique
    AND (
      SELECT string_agg(a.attname, ', ' ORDER BY a.attnum)
      FROM unnest(x.indkey) WITH ORDINALITY AS k(attnum, ord)
      JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
    ) = 'offer_id'
);")"
  [[ "$ok" == "t" ]] && log "OK  : ${mv} has unique index on (offer_id)" || { log "FAIL: ${mv} missing unique index (offer_id)"; ((fail++)); }
}

check_mv_unique "mv_emag_stock_summary"
check_mv_unique "mv_emag_best_offer"

###############################################################################
# 3) Test REFRESH CONCURRENTLY
###############################################################################
log "health: test REFRESH CONCURRENTLY (lock_timeout=3s, statement_timeout=2min)"

refresh_mv_test(){
  local mv="$1"
  if psql_db -c "SET lock_timeout='3s'; SET statement_timeout='2min'; REFRESH MATERIALIZED VIEW CONCURRENTLY ${PGSCHEMA}.${mv};" >/dev/null; then
    log "OK  : refresh concurrently ${mv}"
  else
    log "FAIL: refresh concurrently ${mv}"
    ((fail++))
  fi
}
refresh_mv_test "mv_emag_stock_summary"
refresh_mv_test "mv_emag_best_offer"

###############################################################################
# Rezultat final
###############################################################################
if (( fail > 0 )); then
  log "HEALTH: PROBLEME (exit 1)"
  exit 1
else
  log "HEALTH: OK"
fi

```

# path-ul fisierului: scripts/db-maint.sh  (size=8170 bytes, exec)

```bash
# scripts/db-maint.sh
#!/usr/bin/env bash
# Întreținere DB eMAG:
# - reachability + versiune alembic
# - asigurare partiții pentru luna următoare (create dacă lipsesc)
# - verificare partiții (există + atașate la părinți)
# - indexuri unice pe MVs
# - test REFRESH MATERIALIZED VIEW CONCURRENTLY

set -Eeuo pipefail

###############################################################################
# Config
###############################################################################
PGUSER="${PGUSER:-appuser}"
PGDATABASE="${PGDATABASE:-appdb}"
PGSCHEMA="${PGSCHEMA:-app}"
SERVICE_DB="${SERVICE_DB:-db}"
SERVICE_APP="${SERVICE_APP:-app}"
TZ_REGION="${TZ_REGION:-Europe/Bucharest}"

###############################################################################
# Utilitare
###############################################################################
log(){ printf '[%s] %s\n' "$(date '+%F %T %Z')" "$*"; }

# Alege docker compose
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  log "ERROR: nici «docker compose», nici «docker-compose» nu sunt în PATH."
  exit 1
fi

# psql în containerul DB: -X (nu încărca ~/.psqlrc), -A/-t (unaligned, tuples only), -F '|' (separator stabil)
psql_db(){
  $COMPOSE exec -T "$SERVICE_DB" \
    psql -X -A -t -F '|' -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDATABASE" "$@"
}

# (opțional) heads din aplicație
alembic_heads(){
  $COMPOSE exec -T "$SERVICE_APP" alembic heads -v 2>/dev/null || true
}

fail=0

###############################################################################
# 0) Reachability + Alembic
###############################################################################
log "health: DB reachability"
psql_db -c "SELECT 'ok:db'" | sed -n '1p' || { log "FAIL: DB not reachable"; exit 1; }

ALEMBIC_DB="$(psql_db -c "SELECT version_num FROM ${PGSCHEMA}.alembic_version" || echo 'n/a')"
log "alembic (DB): ${ALEMBIC_DB:-n/a}"

HEADS="$(alembic_heads | sed -n 's/^Rev: \([^ ]*\).*/\1/p' | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"
if [[ -n "$HEADS" ]]; then
  log "alembic (app): $HEADS"
else
  log "INFO: nu pot obține «alembic heads» din serviciul app (opțional)."
fi

###############################################################################
# 1) Asigură partițiile pentru luna următoare (creează dacă lipsesc)
###############################################################################
log "health: next-month partitions (ensure & check)"

# Creează părțile pentru luna următoare, DST-aware pe Europe/Bucharest
psql_db <<SQL >/dev/null
DO \$\$
DECLARE
  nm date := (date_trunc('month', (now() AT TIME ZONE '${TZ_REGION}')) + interval '1 month')::date;
  nx date := (date_trunc('month', (now() AT TIME ZONE '${TZ_REGION}')) + interval '2 months')::date;
  y  int := extract(year  from nm);
  m  int := extract(month from nm);
  y2 int := extract(year  from nx);
  m2 int := extract(month from nx);

  p_start timestamptz := make_timestamptz(y,  m,  1, 0,0,0, '${TZ_REGION}');
  p_end   timestamptz := make_timestamptz(y2, m2, 1, 0,0,0, '${TZ_REGION}');

  p_name text := format('p_y%sm%02s', y, m);
  s_name text := format('s_y%sm%02s', y, m);
BEGIN
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS ${PGSCHEMA}.%I PARTITION OF ${PGSCHEMA}.emag_offer_prices_hist FOR VALUES FROM (%L) TO (%L)',
    p_name, p_start, p_end
  );
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS ${PGSCHEMA}.%I PARTITION OF ${PGSCHEMA}.emag_offer_stock_hist  FOR VALUES FROM (%L) TO (%L)',
    s_name, p_start, p_end
  );
END
\$\$;
SQL

# Afișează ce e atașat sub părinți (util când DEBUG=1)
if [[ "${DEBUG:-0}" != "0" ]]; then
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_prices_hist:"
  psql_db -c "
    SELECT '  - '||c.relname
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='${PGSCHEMA}' AND p.relname='emag_offer_prices_hist'
    ORDER BY c.relname;" | sed '/^$/d'
  log "DEBUG: attached under ${PGSCHEMA}.emag_offer_stock_hist:"
  psql_db -c "
    SELECT '  - '||c.relname
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='${PGSCHEMA}' AND p.relname='emag_offer_stock_hist'
    ORDER BY c.relname;" | sed '/^$/d'
fi

# Verificare ca în db-health.sh
row="$(
  psql_db <<'SQL'
WITH base AS (
  SELECT (date_trunc('month', now()) + interval '1 month')::date AS d
), names AS (
  SELECT
    to_char(d, '"p_y"YYYY"m"MM') AS p_name,
    to_char(d, '"s_y"YYYY"m"MM') AS s_name
  FROM base
)
SELECT
  n.p_name,
  (to_regclass('app.'||n.p_name) IS NOT NULL),
  EXISTS (
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='app' AND p.relname='emag_offer_prices_hist' AND c.relname=n.p_name
  ),
  n.s_name,
  (to_regclass('app.'||n.s_name) IS NOT NULL),
  EXISTS (
    SELECT 1
    FROM pg_inherits i
    JOIN pg_class c ON c.oid=i.inhrelid
    JOIN pg_class p ON p.oid=i.inhparent
    JOIN pg_namespace np ON np.oid=p.relnamespace
    WHERE np.nspname='app' AND p.relname='emag_offer_stock_hist' AND c.relname=n.s_name
  )
FROM names n;
SQL
)"
IFS='|' read -r p_name price_exists price_attached s_name stock_exists stock_attached <<<"$row"

if [[ "${DEBUG:-0}" != "0" ]]; then
  log "DEBUG: expected price part: $p_name"
  log "DEBUG: expected stock  part: $s_name"
fi

if [[ "$price_exists" == "t" ]];   then log "OK  : price partition exists ($p_name)"; else log "FAIL: price partition missing"; ((fail++)); fi
if [[ "$price_attached" == "t" ]]; then log "OK  : price partition attached";         else log "FAIL: price partition NOT attached"; ((fail++)); fi
if [[ "$stock_exists" == "t" ]];   then log "OK  : stock partition exists ($s_name)"; else log "FAIL: stock partition missing"; ((fail++)); fi
if [[ "$stock_attached" == "t" ]]; then log "OK  : stock partition attached";         else log "FAIL: stock partition NOT attached"; ((fail++)); fi

###############################################################################
# 2) MV unique index pe (offer_id)
###############################################################################
log "health: MV unique indexes"

check_mv_unique(){
  local mv="$1"
  local ok
  ok="$(psql_db <<SQL
SELECT EXISTS (
  SELECT 1
  FROM pg_index x
  JOIN pg_class t  ON t.oid=x.indrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname='${PGSCHEMA}' AND t.relname='${mv}'
    AND x.indisunique
    AND (
      SELECT string_agg(a.attname, ', ' ORDER BY a.attnum)
      FROM unnest(x.indkey) WITH ORDINALITY AS k(attnum, ord)
      JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
    ) = 'offer_id'
);
SQL
)"
  if [[ "$ok" == "t" ]]; then
    log "OK  : ${mv} has unique index on (offer_id)"
  else
    log "FAIL: ${mv} missing unique index (offer_id)"
    ((fail++))
  fi
}

check_mv_unique "mv_emag_stock_summary"
check_mv_unique "mv_emag_best_offer"

###############################################################################
# 3) Test REFRESH CONCURRENTLY
###############################################################################
log "health: test REFRESH CONCURRENTLY (lock_timeout=3s, statement_timeout=2min)"

refresh_mv_test(){
  local mv="$1"
  if psql_db -c "SET lock_timeout='3s'; SET statement_timeout='2min'; REFRESH MATERIALIZED VIEW CONCURRENTLY ${PGSCHEMA}.${mv};" >/dev/null; then
    log "OK  : refresh concurrently ${mv}"
  else
    log "FAIL: refresh concurrently ${mv}"
    ((fail++))
  fi
}
refresh_mv_test "mv_emag_stock_summary"
refresh_mv_test "mv_emag_best_offer"

###############################################################################
# Rezultat final
###############################################################################
if (( fail > 0 )); then
  log "HEALTH: PROBLEME (exit 1)"
  exit 1
else
  log "HEALTH: OK"
fi

```

# path-ul fisierului: scripts/quick_check.sh  (size=1671 bytes, exec)

```bash
# scripts/quick_check.sh
#!/usr/bin/env bash
set -Eeuo pipefail

# Lucrăm din rădăcina repo-ului (indiferent de unde rulezi scriptul)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

die() { echo "❌ $*" >&2; exit 1; }

# La orice eroare: arată starea containerelor și ultimele loguri din app & db
trap '
  code=$?
  echo
  echo "[QC] Last status & logs (tail) ↓"
  docker compose ps || true
  docker compose logs --no-color --tail=200 db app || true
  exit $code
' ERR

echo "[QC] Build app image..."
docker compose build app

echo "[QC] (Re)start services..."
docker compose up -d --force-recreate db app
docker compose ps

echo "[QC] Wait for DB to be healthy..."
DB_CID="$(docker compose ps -q db)"
for i in {1..60}; do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CID" 2>/dev/null || echo unknown)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done
status="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CID" 2>/dev/null || echo unknown)"
if [[ "$status" != "healthy" ]]; then
  echo "[QC] DB status: $status"
  # fallback de diagnostic: pg_isready din container
  docker compose exec -T db pg_isready -h localhost -p 5432 || true
  die "DB did not become healthy in time"
fi

echo "[QC] Run migrations (alembic upgrade head)..."
docker compose exec -T app bash -lc 'alembic -c /app/alembic.ini upgrade head'

echo "[QC] Prime materialized views..."
bash scripts/refresh_mviews.sh

echo "[QC] Seed demo offer..."
bash scripts/seed_demo_offer.sh

echo "[QC] DB health..."
bash scripts/db-health.sh

echo "[QC] SQL + API smoke..."
bash scripts/smoke.sh

echo "[QC] OK — everything looks good ✅"

```

# path-ul fisierului: scripts/refresh_mviews.sh  (size=2197 bytes, exec)

```bash
# scripts/refresh_mviews.sh
#!/usr/bin/env bash
# Refresh materialized views cu timeouts sigure.
# Dacă MV nu e populat încă, face REFRESH normal; altfel CONCURRENTLY.

set -Eeuo pipefail

PGUSER="${PGUSER:-appuser}"
PGDATABASE="${PGDATABASE:-appdb}"
PGSCHEMA="${PGSCHEMA:-app}"
SERVICE_DB="${SERVICE_DB:-db}"
LOCK_TIMEOUT="${LOCK_TIMEOUT:-3s}"
STMT_TIMEOUT="${STMT_TIMEOUT:-2min}"

# Alege docker compose
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  echo "ERROR: nici «docker compose», nici «docker-compose» nu sunt în PATH." >&2
  exit 1
fi

# helper psql în containerul DB
psql_db() {
  $COMPOSE exec -T "$SERVICE_DB" \
    psql -X -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDATABASE" "$@"
}

# Listează MVs în ordinea dorită
MVS=(
  "mv_emag_stock_summary"
  "mv_emag_best_offer"
)

exists_mv() {
  local mv="$1"
  psql_db -Atqc "select exists(
    select 1 from pg_matviews
    where schemaname='${PGSCHEMA}' and matviewname='${mv}'
  );"
}

is_populated() {
  local mv="$1"
  psql_db -Atqc "select coalesce((
    select c.relispopulated
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='${PGSCHEMA}'
      and c.relname='${mv}'
      and c.relkind='m'
  ), false);"
}

refresh_mv() {
  local mv="$1"

  if [[ "$(exists_mv "$mv")" != "t" ]]; then
    echo "[refresh_mviews] skip ${PGSCHEMA}.${mv} (nu există)"
    return 0
  fi

  if [[ "$(is_populated "$mv")" == "t" ]]; then
    echo "[refresh_mviews] refreshing CONCURRENTLY ${PGSCHEMA}.${mv} ..."
    psql_db <<SQL
SET lock_timeout='${LOCK_TIMEOUT}';
SET statement_timeout='${STMT_TIMEOUT}';
REFRESH MATERIALIZED VIEW CONCURRENTLY ${PGSCHEMA}.${mv};
SQL
  else
    echo "[refresh_mviews] first populate (non-concurrently) ${PGSCHEMA}.${mv} ..."
    psql_db <<SQL
SET lock_timeout='${LOCK_TIMEOUT}';
SET statement_timeout='${STMT_TIMEOUT}';
REFRESH MATERIALIZED VIEW ${PGSCHEMA}.${mv};
SQL
  fi
}

echo "[refresh_mviews] start"
psql_db -c "select 'ok:db';" >/dev/null

for mv in "${MVS[@]}"; do
  refresh_mv "$mv"
done

echo "[refresh_mviews] done"

```

# path-ul fisierului: scripts/repo-tree.sh  (size=2751 bytes, exec)

```bash
# scripts/repo-tree.sh
#!/usr/bin/env bash
set -euo pipefail

# repo-tree.sh — generează structura repo-ului ca "tree", cu fallback în Python
# Usage:
#   ./scripts/repo-tree.sh                   # tree pentru directorul curent
#   ./repo-tree.sh -r /path/repo     # alt root
#   ./repo-tree.sh -o REPO_TREE.md   # salvează în fișier
#   ./repo-tree.sh -d 3              # limitează adâncimea
#   ./repo-tree.sh --no-ignore       # afișează tot (fără exclude)
#
DEFAULT_IGNORE='.git|.hg|.svn|.DS_Store|__pycache__|.mypy_cache|.pytest_cache|.tox|.venv|venv|node_modules|dist|build|*.pyc|*.pyo|*.log|*.egg-info|*.sqlite|*.db'

ROOT='.'
OUT=''
DEPTH=''
IGNORE="$DEFAULT_IGNORE"
USE_IGNORE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -r|--root)      ROOT="${2:-.}"; shift 2;;
    -o|--output)    OUT="${2:-}"; shift 2;;
    -d|--depth)     DEPTH="${2:-}"; shift 2;;
    --ignore)       IGNORE="${2:-}"; shift 2;;
    --no-ignore)    USE_IGNORE=0; shift;;
    -h|--help)
      sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "Arg necunoscut: $1"; exit 2;;
  esac
done

ROOT="${ROOT%/}"

emit() {
  if [[ -n "$OUT" ]]; then tee "$OUT"; else cat; fi
}

if command -v tree >/dev/null 2>&1; then
  args=(-a)
  [[ -n "$DEPTH" ]] && args+=(-L "$DEPTH")
  if [[ "$USE_IGNORE" -eq 1 && -n "$IGNORE" ]]; then
    args+=(-I "$IGNORE")
  fi
  args+=("$ROOT")
  tree "${args[@]}" | emit
  exit 0
fi

# Fallback în Python (fără sed; fără dependențe externe)
python3 - "$ROOT" "$DEPTH" "$IGNORE" "$USE_IGNORE" <<'PY' | emit
import os, sys, fnmatch

root = sys.argv[1]
depth = sys.argv[2]
ignore_pat = sys.argv[3]
use_ignore = sys.argv[4] == "1"

max_depth = int(depth) if depth and depth.isdigit() else None
ignore_globs = [p for p in ignore_pat.split('|') if p] if use_ignore else []

def is_ignored(name: str) -> bool:
    if not use_ignore:
        return False
    for pat in ignore_globs:
        if fnmatch.fnmatch(name, pat):
            return True
    return False

def walk(top: str, prefix: str = "", level: int = 0):
    try:
        entries = sorted(os.scandir(top),
                         key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
    except FileNotFoundError:
        return
    entries = [e for e in entries if not is_ignored(e.name)]
    for i, e in enumerate(entries):
        conn = "└── " if i == len(entries)-1 else "├── "
        print(prefix + conn + e.name)
        if e.is_dir(follow_symlinks=False):
            if max_depth is None or level+1 < max_depth:
                ext = "    " if i == len(entries)-1 else "│   "
                walk(os.path.join(top, e.name), prefix + ext, level+1)

print(os.path.basename(os.path.abspath(root)) or root)
walk(root)
PY

```

# path-ul fisierului: scripts/seed_demo_offer.sh  (size=6800 bytes, exec)

```bash
# scripts/seed_demo_offer.sh
#!/usr/bin/env bash
set -euo pipefail

echo "[$(date '+%F %T %Z')] Seeding demo offer data..."

docker compose exec -T db psql -v ON_ERROR_STOP=1 -U appuser -d appdb <<'SQL'
-- lucrăm pe schema app
SET search_path TO app, public;

DO $$
DECLARE
  -- coloane posibile (tolerăm diferențe de schemă)
  has_code    boolean;
  has_country boolean;
  has_active  boolean;
  has_created boolean;
  has_updated boolean;

  has_sku     boolean;
  has_price   boolean;

  v_prod_id   int    := 1;
  v_offer_id  bigint := 900000001;

  v_today     timestamptz := date_trunc('day', now());               -- ora 00:00 a zilei curente
  v_tomorrow  timestamptz := date_trunc('day', now() + interval '1 day'); -- ora 00:00 a zilei de mâine
BEGIN
  --------------------------------------------------------------------
  -- 1) Asigură contul (id=1), tolerând diferențe de schemă
  --------------------------------------------------------------------
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='code')       INTO has_code;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='country')    INTO has_country;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='active')     INTO has_active;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='created_at') INTO has_created;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='updated_at') INTO has_updated;

  IF NOT EXISTS (SELECT 1 FROM app.emag_account WHERE id=1) THEN
    IF has_code AND has_country AND has_active AND has_created AND has_updated THEN
      INSERT INTO app.emag_account (id, code, name, country, active, created_at, updated_at)
      VALUES (1, 'demo', 'demo', 'RO', true, now(), now());
    ELSIF has_code AND has_country AND has_active THEN
      INSERT INTO app.emag_account (id, code, name, country, active)
      VALUES (1, 'demo', 'demo', 'RO', true);
    ELSIF has_code THEN
      INSERT INTO app.emag_account (id, code, name)
      VALUES (1, 'demo', 'demo');
    ELSE
      -- dacă schema cere "code" NOT NULL, inserarea asta ar eșua; în schema ta actuală e OK
      INSERT INTO app.emag_account (id, name)
      VALUES (1, 'demo');
    END IF;
  END IF;

  --------------------------------------------------------------------
  -- 2) Asigură un produs demo (id=1), tolerând diferențe de schemă
  --------------------------------------------------------------------
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='products' AND column_name='sku')   INTO has_sku;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='products' AND column_name='price') INTO has_price;

  IF NOT EXISTS (SELECT 1 FROM app.products WHERE id=v_prod_id) THEN
    IF has_sku AND has_price THEN
      INSERT INTO app.products (id, name, sku, price, created_at, updated_at)
      VALUES (v_prod_id, 'Prod demo', 'SKU-DEMO', 19.99, now(), now());
    ELSIF has_sku THEN
      INSERT INTO app.products (id, name, sku, created_at, updated_at)
      VALUES (v_prod_id, 'Prod demo', 'SKU-DEMO', now(), now());
    ELSE
      INSERT INTO app.products (id, name, created_at, updated_at)
      VALUES (v_prod_id, 'Prod demo', now(), now());
    END IF;
  END IF;

  --------------------------------------------------------------------
  -- 3) Asigură oferta demo (id=900000001) – fallback dacă lipsesc coloane
  --------------------------------------------------------------------
  IF NOT EXISTS (SELECT 1 FROM app.emag_offers WHERE id=v_offer_id) THEN
    BEGIN
      INSERT INTO app.emag_offers (id, product_id, account_id, country, currency, sale_price, stock_total, updated_at)
      VALUES (v_offer_id, v_prod_id, 1, 'RO', 'RON', 19.99, 0, now());
    EXCEPTION WHEN undefined_column THEN
      INSERT INTO app.emag_offers (id, product_id, account_id)
      VALUES (v_offer_id, v_prod_id, 1)
      ON CONFLICT (id) DO NOTHING;
    END;
  END IF;

  --------------------------------------------------------------------
  -- 4) Stoc curent pe depozit, upsert pe (offer_id, warehouse_code)
  --------------------------------------------------------------------
  INSERT INTO app.emag_offer_stock_by_wh (offer_id, warehouse_code, updated_at, stock, reserved, incoming)
  VALUES (v_offer_id, 'WH-TEST', now(), 7, 1, 0)
  ON CONFLICT (offer_id, warehouse_code)
  DO UPDATE SET
    updated_at = EXCLUDED.updated_at,
    stock      = EXCLUDED.stock,
    reserved   = EXCLUDED.reserved,
    incoming   = EXCLUDED.incoming;

  --------------------------------------------------------------------
  -- 5) Istorice „pe zi” (azi și mâine), idempotent pe PK
  --    NOTĂ: folosim orele 00:00 (date_trunc('day', ...)) ca să fie stabil pentru ON CONFLICT.
  --------------------------------------------------------------------
  INSERT INTO app.emag_offer_prices_hist (offer_id, recorded_at, currency, sale_price)
  VALUES
    (v_offer_id, v_today,    'RON', 19.99),
    (v_offer_id, v_tomorrow, 'RON', 21.99)
  ON CONFLICT (offer_id, recorded_at)
  DO UPDATE SET
    currency   = EXCLUDED.currency,
    sale_price = EXCLUDED.sale_price;

  INSERT INTO app.emag_offer_stock_hist (offer_id, warehouse_code, recorded_at, stock, reserved, incoming)
  VALUES
    (v_offer_id, 'WH-TEST', v_today,    5, 0, 0),
    (v_offer_id, 'WH-TEST', v_tomorrow, 6, 1, 0)
  ON CONFLICT (offer_id, warehouse_code, recorded_at)
  DO UPDATE SET
    stock    = EXCLUDED.stock,
    reserved = EXCLUDED.reserved,
    incoming = EXCLUDED.incoming;
END
$$;

-- 6) REFRESH MVs cu timeouts (în tranzacție pentru SET LOCAL)
BEGIN;
  SET LOCAL lock_timeout = '3s';
  SET LOCAL statement_timeout = '2min';
  REFRESH MATERIALIZED VIEW app.mv_emag_stock_summary;
  REFRESH MATERIALIZED VIEW app.mv_emag_best_offer;
COMMIT;
SQL

# sumar după seed
docker compose exec -T db psql -U appuser -d appdb -c "
SELECT 'by_wh' src, count(*) FROM app.emag_offer_stock_by_wh
UNION ALL
SELECT 'offers',      count(*) FROM app.emag_offers
UNION ALL
SELECT 'prices_hist', count(*) FROM app.emag_offer_prices_hist
UNION ALL
SELECT 'stock_hist',  count(*) FROM app.emag_offer_stock_hist
UNION ALL
SELECT 'mv_stock',    count(*) FROM app.mv_emag_stock_summary
UNION ALL
SELECT 'mv_best',     count(*) FROM app.mv_emag_best_offer;
"

echo "[$(date '+%F %T %Z')] Seed done."

```

# path-ul fisierului: scripts/smoke.sh  (size=8251 bytes, exec)

```bash
# scripts/smoke.sh
#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Config DB (override prin env)
# ─────────────────────────────────────────────────────────────────────────────
: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5434}"
: "${PGUSER:=appuser}"
: "${PGDATABASE:=appdb}"
: "${PGCONNECT_TIMEOUT:=5}"

# Dacă PGPASSWORD nu e setat, încearcă să-l iei din POSTGRES_PASSWORD (sau APP_DB_PASSWORD)
if [ -z "${PGPASSWORD:-}" ]; then
  if [ -n "${POSTGRES_PASSWORD:-}" ]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
  elif [ -n "${APP_DB_PASSWORD:-}" ]; then
    export PGPASSWORD="$APP_DB_PASSWORD"
  fi
fi

# Unele medii pot seta PGOPTIONS problematic (ex: "-csearch_path=...").
# Ca să evităm eroarea "invalid command-line argument for server process: -c",
# resetăm explicit PGOPTIONS la nimic pentru acest script.
unset PGOPTIONS || true

# ─────────────────────────────────────────────────────────────────────────────
# Config API (override prin env)
# ─────────────────────────────────────────────────────────────────────────────
: "${APP_PORT:=8001}"
: "${API_WAIT_RETRIES:=60}"
: "${API_WAIT_SLEEP_SECS:=1}"
: "${CURL_CONNECT_TIMEOUT:=2}"
: "${CURL_MAX_TIME:=5}"

have_cmd() { command -v "$1" >/dev/null 2>&1; }
log()      { printf '[SMOKE] %s\n' "$*"; }
die()      { printf '[SMOKE][ERR] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  local ok=1
  for c in "$@"; do
    if ! have_cmd "$c"; then
      printf '[SMOKE][ERR] missing command: %s\n' "$c" >&2
      ok=0
    fi
  done
  [ "$ok" -eq 1 ] || die "Install the commands above and retry."
}

# Uneltele minime
require_cmd curl psql

# Diagnostic automat la exit pe eroare
on_err() {
  local ec=$?
  [ $ec -eq 0 ] && return 0
  log "Last status & logs (tail) ↓"
  if have_cmd docker; then
    if docker compose ps >/dev/null 2>&1; then
      docker compose ps || true
      docker compose logs --tail=120 || true
    elif have_cmd docker-compose; then
      docker-compose ps || true
      docker-compose logs --tail=120 || true
    fi
  fi
  exit $ec
}
trap on_err EXIT

# ─────────────────────────────────────────────────────────────────────────────
# Determine BASE_URL (auto-detect host port if not provided)
# ─────────────────────────────────────────────────────────────────────────────
detect_base_url() {
  # 1) Dacă e deja setat din env, îl păstrăm
  if [ -n "${BASE_URL:-}" ]; then
    echo "$BASE_URL"
    return 0
  fi

  # 2) Încearcă docker compose port (service 'app', container port 8001)
  if have_cmd docker; then
    local mapped=""
    if docker compose version >/dev/null 2>&1; then
      mapped="$(docker compose port app 8001 2>/dev/null | tail -n1 || true)"
    elif have_cmd docker-compose; then
      mapped="$(docker-compose port app 8001 2>/dev/null | tail -n1 || true)"
    fi
    if [ -n "$mapped" ]; then
      # formate tipice: "0.0.0.0:8010", "[::]:8010" sau "127.0.0.1:8010"
      local host_port="${mapped##*:}"
      echo "http://127.0.0.1:${host_port}"
      return 0
    fi
  fi

  # 3) Fallback la APP_PORT (sau 8001)
  echo "http://127.0.0.1:${APP_PORT}"
}

BASE_URL="$(detect_base_url)"

wait_for_api() {
  local url="${1}"
  local retries="${API_WAIT_RETRIES}"
  local sleep_s="${API_WAIT_SLEEP_SECS}"
  log "Wait for API @ ${url} (retries=${retries})..."
  for _ in $(seq 1 "${retries}"); do
    if curl -fsS --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" "$url" >/dev/null 2>&1; then
      log "API is up."
      return 0
    fi
    printf '.' >&2
    sleep "${sleep_s}"
  done
  printf '\n' >&2
  return 1
}

json_get() {
  # Usage: json_get "<url>" "<jq expr>"
  local url="$1"; shift
  local jqexpr="${1:-.}"
  if have_cmd jq; then
    curl -fsS --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" \
      -H 'Accept: application/json' "$url" | jq -r "${jqexpr}"
  else
    log "jq not found; printing raw body for: $url"
    curl -fsS --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" \
      -H 'Accept: application/json' "$url"
  fi
}

diagnose_if_down() {
  log "docker compose ps:"
  if have_cmd docker && docker compose ps >/dev/null 2>&1; then
    docker compose ps || true
    log "Last 120 log lines from app:"
    docker compose logs --tail=120 app || true
  elif have_cmd docker-compose; then
    docker-compose ps || true
    log "Last 120 log lines from app:"
    docker-compose logs --tail=120 app || true
  fi
  log "Try manual curl (verbose):"
  curl -v --connect-timeout "${CURL_CONNECT_TIMEOUT}" --max-time "${CURL_MAX_TIME}" "${BASE_URL}/health" || true
}

# ─────────────────────────────────────────────────────────────────────────────
# 1) Rulează SQL smoke (idempotent)
#    -X = nu citi ~/.psqlrc (pentru a evita setări locale neprevăzute)
#    -w = nu cere parolă (fail fast dacă lipsește PGPASSWORD)
#    STRICT: dacă SMOKE_STRICT=1, trimitem variabila către psql/sql
# ─────────────────────────────────────────────────────────────────────────────
log "Running SQL smoke..."
PSQL_STRICT=()
if [ "${SMOKE_STRICT:-0}" = "1" ]; then
  PSQL_STRICT+=( -v STRICT=1 )
fi

# Conexiune libpq clară, fără să scurgem parola în CLI
psql -X -w \
  --set=ON_ERROR_STOP=1 \
  "${PSQL_STRICT[@]}" \
  "host=${PGHOST} port=${PGPORT} user=${PGUSER} dbname=${PGDATABASE} connect_timeout=${PGCONNECT_TIMEOUT}" \
  -f scripts/smoke.sql

# ─────────────────────────────────────────────────────────────────────────────
# 2) Așteaptă API-ul să fie ready (cu auto-detect pe port)
# ─────────────────────────────────────────────────────────────────────────────
if ! wait_for_api "${BASE_URL}/health"; then
  log "API did not become ready in time."
  diagnose_if_down
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3) Checks API
# ─────────────────────────────────────────────────────────────────────────────
log "Health:"
json_get "${BASE_URL}/health" '.'

log "Alembic migrations:"
json_get "${BASE_URL}/health/migrations" '.'

log "GET /categories?name=arduino"
json_get "${BASE_URL}/categories?name=arduino&page=1&page_size=5" '.total, .items[0]'

log "GET /products?name=senzor&sku_prefix=SKU-SMOKE&order_by=price&order_dir=desc&page_size=5"
json_get "${BASE_URL}/products?name=senzor&sku_prefix=SKU-SMOKE&order_by=price&order_dir=desc&page_size=5" '.total'

log "Done."

```

# path-ul fisierului: scripts/smoke.sql  (size=13491 bytes)

```sql
-- scripts/smoke.sql
-- Smoke test idempotent pentru schema "app".
-- Rulabil de oricâte ori; pregătit pentru CI.

\pset pager off
\set ON_ERROR_STOP on
\timing off

-- Activează verificări stricte doar dacă setezi în psql: \set STRICT 1
-- (altfel rulează doar informativ fără să fail-uiască pe planuri)
\if :{?STRICT}
\echo '[smoke] STRICT mode: ON'
\else
\echo '[smoke] STRICT mode: OFF'
\endif

SET application_name = 'smoke.sql';
SET client_min_messages = warning;
SET statement_timeout = '30s';
SET lock_timeout = '2s';
SET search_path TO app, public;

-- ─────────────────────────────────────────────────────────────────────────────
-- 0) Context: versiuni, search_path, extensii, alembic_version
-- ─────────────────────────────────────────────────────────────────────────────
SELECT now() AT TIME ZONE 'UTC' AS utc_now;

SHOW search_path;
SHOW server_version;

SELECT e.extname, n.nspname AS schema
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
WHERE e.extname IN ('pg_stat_statements','pg_trgm')
ORDER BY e.extname;

SELECT to_regclass('app.alembic_version')    IS NOT NULL AS app_version_table_present,
       to_regclass('public.alembic_version') IS NULL     AS public_version_table_absent;

SELECT current_database() AS db, current_schema;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Seed idempotent – întâi inserările CU ID fix (nu folosesc secvența),
--    apoi reglăm secvențele, apoi inserările fără ID.
-- ─────────────────────────────────────────────────────────────────────────────

-- categorie fixă (ID stabil)
INSERT INTO app.categories (id, name, description)
SELECT 9001, 'Teste Electronica', 'Smoke category'
WHERE NOT EXISTS (SELECT 1 FROM app.categories WHERE id = 9001);

-- produs cu ID fix (nu folosește secvența)
INSERT INTO app.products (id, name, description, price, sku)
SELECT 9101, 'Amplificator audio TPA3116', '2x50W', 129.90, 'SKU-SMOKE-TPA3116'
WHERE NOT EXISTS (SELECT 1 FROM app.products WHERE id = 9101);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) Ajustează secvențele ACUM (după inserările cu ID fix)
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  seq text;
  max_id bigint;
BEGIN
  -- products.id
  SELECT pg_get_serial_sequence('app.products','id') INTO seq;
  IF seq IS NOT NULL THEN
    SELECT COALESCE(MAX(id), 0) INTO max_id FROM app.products;
    EXECUTE format('SELECT setval(%L, %s, true);', seq, max_id);
  END IF;

  -- categories.id
  SELECT pg_get_serial_sequence('app.categories','id') INTO seq;
  IF seq IS NOT NULL THEN
    SELECT COALESCE(MAX(id), 0) INTO max_id FROM app.categories;
    EXECUTE format('SELECT setval(%L, %s, true);', seq, max_id);
  END IF;
END$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) Inserări idempotente fără ID + legături categorie-produs
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO app.categories (name, description)
SELECT 'Arduino', 'MCU boards'
WHERE NOT EXISTS (
  SELECT 1 FROM app.categories WHERE lower(name) = lower('Arduino')
);

INSERT INTO app.products (name, description, price, sku)
SELECT 'Senzor DS18B20', 'temperatura', 19.90, 'SKU-SMOKE-DS18B20'
WHERE NOT EXISTS (SELECT 1 FROM app.products WHERE sku = 'SKU-SMOKE-DS18B20');

INSERT INTO app.products (name, description, price, sku)
SELECT 'Arduino UNO R3 compatibil', 'placa MCU compatibila', 89.90, 'SKU-SMOKE-ARDUINO'
WHERE NOT EXISTS (SELECT 1 FROM app.products WHERE sku = 'SKU-SMOKE-ARDUINO');

INSERT INTO app.product_categories (product_id, category_id)
SELECT p.id, 9001
FROM app.products p
WHERE p.sku = 'SKU-SMOKE-TPA3116'
  AND NOT EXISTS (
    SELECT 1 FROM app.product_categories pc
    WHERE pc.product_id = p.id AND pc.category_id = 9001
  );

INSERT INTO app.product_categories (product_id, category_id)
SELECT p.id, c.id
FROM app.products p
JOIN app.categories c ON lower(c.name) = 'arduino'
WHERE p.sku = 'SKU-SMOKE-ARDUINO'
  AND NOT EXISTS (
    SELECT 1 FROM app.product_categories pc
    WHERE pc.product_id = p.id AND pc.category_id = c.id
  );

-- ANALYZE pentru planuri mai stabile la EXPLAIN
ANALYZE app.products;
ANALYZE app.categories;
ANALYZE app.product_categories;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) Verificări audit & trigger – existență coloane și trigger
-- ─────────────────────────────────────────────────────────────────────────────
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='app'
  AND table_name IN ('products','categories','product_categories')
  AND column_name IN ('created_at','updated_at')
ORDER BY table_name, column_name;

SELECT relname AS table, tgname AS trigger_name
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname='app' AND tgname IN (
  'tg_products_set_timestamps',
  'tg_categories_set_timestamps',
  'tg_product_categories_set_timestamps'
)
ORDER BY relname;

SELECT 'products' AS tbl,
       SUM((created_at IS NULL)::int) AS created_at_nulls,
       SUM((updated_at IS NULL)::int) AS updated_at_nulls
FROM app.products
UNION ALL
SELECT 'categories',
       SUM((created_at IS NULL)::int),
       SUM((updated_at IS NULL)::int)
FROM app.categories
UNION ALL
SELECT 'product_categories',
       SUM((created_at IS NULL)::int),
       SUM((updated_at IS NULL)::int)
FROM app.product_categories;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5) Indexuri relevante (inclusiv trigram)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='app' AND tablename='products'
  AND indexname IN ('ix_products_name_trgm','ix_products_sku_trgm',
                    'ix_products_name','ix_products_name_lower','ix_products_price')
ORDER BY indexname;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6) EXPLAIN ANALYZE – demonstrează folosirea indexurilor trigram
-- ─────────────────────────────────────────────────────────────────────────────

-- a) name CONTAINS 'arduino' (trigram)
BEGIN;
  SET LOCAL enable_seqscan = off;
  EXPLAIN (ANALYZE, COSTS, SUMMARY)
  SELECT id, name
  FROM app.products
  WHERE lower(name) LIKE '%arduino%';
ROLLBACK;

-- b) sku prefix 'SKU-SMOKE-A%' (trigram cu WHERE sku IS NOT NULL)
BEGIN;
  SET LOCAL enable_seqscan = off;
  EXPLAIN (ANALYZE, COSTS, SUMMARY)
  SELECT id, sku
  FROM app.products
  WHERE sku IS NOT NULL
    AND lower(sku) LIKE 'sku-smoke-a%';
ROLLBACK;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6.1) STRICT mode: aserțiuni pe planuri și volum minim de date (opțional)
-- ─────────────────────────────────────────────────────────────────────────────
\if :{?STRICT}
DO $$
DECLARE
  plan json;
  ok   boolean;
BEGIN
  -- Forțează preferința de index în tranzacția curentă a DO-ului
  PERFORM set_config('enable_seqscan',  'off',  true);
  PERFORM set_config('enable_indexscan','on',   true);
  PERFORM set_config('enable_bitmapscan','on',  true);

  -- verifică folosirea indexului trigram pe name (sau, cel puțin, un Bitmap Index Scan)
  EXECUTE $q$
    EXPLAIN (ANALYZE, FORMAT JSON)
    SELECT id, name FROM app.products WHERE lower(name) LIKE '%arduino%'
  $q$ INTO plan;
  ok := plan::text ILIKE '%ix_products_name_trgm%' OR plan::text ILIKE '%Bitmap%Index%Scan%';
  IF NOT ok THEN
    RAISE EXCEPTION 'Expected trigram/bitmap on name plan, got: %', plan::text;
  END IF;

  -- verifică filtrul pe SKU: acceptă trigram, bitmap sau btree funcțional
  EXECUTE $q$
    EXPLAIN (ANALYZE, FORMAT JSON)
    SELECT id, sku FROM app.products WHERE sku IS NOT NULL AND lower(sku) LIKE 'sku-smoke-a%'
  $q$ INTO plan;
  ok := plan::text ILIKE '%ix_products_sku_trgm%'
        OR plan::text ILIKE '%Bitmap%Index%Scan%'
        OR plan::text ILIKE '%Index Scan using ix_products_sku%';
  IF NOT ok THEN
    RAISE EXCEPTION 'Expected trigram/bitmap/btree on SKU plan, got: %', plan::text;
  END IF;

  -- praguri minime de date
  PERFORM 1;
  IF (SELECT COUNT(*) FROM app.products)  < 5 THEN
    RAISE EXCEPTION 'Expected >=5 products';
  END IF;
  IF (SELECT COUNT(*) FROM app.categories) < 2 THEN
    RAISE EXCEPTION 'Expected >=2 categories';
  END IF;
END$$;
\endif

-- ─────────────────────────────────────────────────────────────────────────────
-- 7) Agregări/rapoarte rapide
-- ─────────────────────────────────────────────────────────────────────────────
SELECT COUNT(*) AS products_total FROM app.products;
SELECT COUNT(*) AS categories_total FROM app.categories;

SELECT c.id, c.name, COUNT(pc.product_id) AS products_in_cat
FROM app.categories c
LEFT JOIN app.product_categories pc ON pc.category_id = c.id
GROUP BY c.id, c.name
ORDER BY c.name;

SELECT id, name, sku, price, created_at, updated_at
FROM app.products
ORDER BY id DESC
LIMIT 5;

-- ─────────────────────────────────────────────────────────────────────────────
-- 8) Observabilitate: există pg_stat_statements (în app sau public)?
-- ─────────────────────────────────────────────────────────────────────────────
SELECT to_regclass('pg_stat_statements') IS NOT NULL AS pg_stat_statements_available;

DO $$
BEGIN
  IF to_regclass('pg_stat_statements') IS NOT NULL THEN
    RAISE NOTICE 'pg_stat_statements e disponibil.';
    PERFORM 1 FROM pg_stat_statements LIMIT 1;
  END IF;
EXCEPTION WHEN undefined_table THEN
  NULL;
END$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 9) Validări finale „OK flags”
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  (SELECT to_regclass('app.alembic_version') IS NOT NULL)  AS ok_alembic_in_app,
  (SELECT to_regclass('public.alembic_version') IS NULL)   AS ok_no_public_version,
  (SELECT current_setting('search_path'))                  AS effective_search_path;

-- EOF

```

# path-ul fisierului: services/worker_dummy.py  (size=214 bytes)

```python
# app/services/worker_dummy.py
import sys, time

def main():
    print("worker dummy: container OK, waiting for jobs…", flush=True)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()

```

# path-ul fisierului: smoke_obs.sh  (size=2071 bytes, exec)

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8010/observability"

# 1) stddev ordering
jq -e '
  .order_by=="stddev_exec_time" and .order_dir=="DESC" and (.items|length)>=1 and (.items[0].stddev_ms|type=="number")
' < <(curl -fsS "$BASE/top-queries?order_by=stddev_exec_time&order_dir=desc") >/dev/null
echo "✓ stddev ordering"

# 2) min ordering
jq -e '
  .order_by=="min_exec_time" and .order_dir=="ASC" and (.items|length)>=1 and (.items[0].min_ms|type=="number")
' < <(curl -fsS "$BASE/top-queries?order_by=min_exec_time&order_dir=asc") >/dev/null
echo "✓ min ordering"

# 3) max ordering
jq -e '
  .order_by=="max_exec_time" and .order_dir=="DESC" and (.items|length)>=1 and (.items[0].max_ms|type=="number")
' < <(curl -fsS "$BASE/top-queries?order_by=max_exec_time&order_dir=desc") >/dev/null
echo "✓ max ordering"

# 4) exclude DDL/utility
jq -e '
  ([.items[]? | (.query // "")
     | test("(?i)^\\s*(begin|commit|rollback|set|show|create|alter|drop|grant|revoke|truncate|comment|vacuum|analyze|explain|reset|prepare|deallocate|checkpoint|refresh|listen|unlisten|notify|copy|security|cluster|lock|discard|do)")]
   | any) == false
' < <(curl -fsS "$BASE/top-queries?exclude_ddl=true") >/dev/null
echo "✓ exclude_ddl"

# 5) truncate query text
jq -e '
  ([.items[]? | (.query // "") | length] | all(. <= 30)) == true
' < <(curl -fsS "$BASE/top-queries?qlen=30") >/dev/null
echo "✓ qlen truncation"

# 6) self-queries hidden by default
jq -e '
  ([.items[]? | select(.query != null and (.query | test("pg_stat_statements"; "i")))] | length) == 0
' < <(curl -fsS "$BASE/top-queries") >/dev/null
echo "✓ exclude_self (implicit)"

# 7) self-queries visible on demand (poate fi 0 dacă nu ai produs trafic recent)
jq -e '
  {count, found: ([.items[]? | (.query // "") | test("pg_stat_statements"; "i")] | any)} |
  (.found | type=="boolean")
' < <(curl -fsS "$BASE/top-queries?exclude_self=false&search=pg_stat_statements&limit=100&order_by=calls&order_dir=desc") >/dev/null
echo "✓ include self on demand"

echo "All checks passed ✓"

```

# path-ul fisierului: tests/test_api.py  (size=5323 bytes)

```python
# tests/test_api.py
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env (cu valori implicite bune pt rulare locală/CI) ----------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST-uri imediat după pornire (în caz de curse init/migrări)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Returnează un diagnostic compact & util despre răspunsul HTTP."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = r.text[:500].replace("\n", "\\n")
    return (
        f"status={r.status_code} url={r.request.method} {r.request.url} "
        f"json={j!r} text='{snippet}...'"
    )


def _assert_status(r: httpx.Response, expected: int | tuple[int, ...]):
    if isinstance(expected, int):
        ok = r.status_code == expected
        exp_str = str(expected)
    else:
        ok = r.status_code in expected
        exp_str = "|".join(map(str, expected))
    assert ok, f"expected {exp_str} but got: {_dump_response(r)}"


def _wait_until_healthy(c: httpx.Client):
    """Așteaptă /health să raporteze 200 OK."""
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _post_with_retry(
    c: httpx.Client, url: str, json: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for i in range(1, POST_RETRIES + 1):
        try:
            r = c.post(url, json=json)
            return r
        except Exception as exc:  # rețele/flakiness rare
            last_exc = exc
            time.sleep(POST_RETRY_SLEEP)
    # Dacă am eșuat de tot, ridicăm cu context
    raise AssertionError(f"POST {url} failed after {POST_RETRIES} retries: {last_exc!r}")


def create_category(
    c: httpx.Client, name: Optional[str] = None, description: Optional[str] = None
) -> Dict[str, Any]:
    payload = {"name": name or f"Cat_{uuid.uuid4().hex[:8]}"}
    if description is not None:
        payload["description"] = description
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["name"] == payload["name"], j
    return j


def create_product(
    c: httpx.Client,
    name: Optional[str] = None,
    price: float = 10.5,
    sku: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "name": name or f"Prod_{uuid.uuid4().hex[:8]}",
        "price": price,
        "sku": sku or f"SKU-TST-{uuid.uuid4().hex[:10]}",
    }
    r = _post_with_retry(c, "/products", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["sku"] == payload["sku"], j
    return j


def list_products_by_category(
    c: httpx.Client, category_id: int, limit: int = 10
) -> Dict[str, Any]:
    r = c.get("/products", params={"category_id": category_id, "limit": limit})
    _assert_status(r, 200)
    j = r.json()
    assert isinstance(j.get("total"), int), j
    assert isinstance(j.get("items"), list), j
    return j


def attach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.post(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


def detach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.delete(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


# --- Client fixură ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP către API-ul deja pornit (containerul app-test)."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_categories_crud_and_attach_flow(client: httpx.Client):
    # 1) create category
    cat = create_category(client, description="test")
    cid = cat["id"]

    # 2) create product
    prod = create_product(client)
    pid = prod["id"]

    # 3) attach (idempotent expected 204)
    attach_product(client, cid, pid)

    # 4) list products filtered by category => conține produsul
    data = list_products_by_category(client, cid, limit=10)
    assert any(p.get("id") == pid for p in data.get("items", [])), data

    # 5) detach (idempotent)
    detach_product(client, cid, pid)

    # 6) list again => nu mai conține produsul
    data2 = list_products_by_category(client, cid, limit=10)
    assert not any(p.get("id") == pid for p in data2.get("items", [])), data2

```

# path-ul fisierului: tests/test_categories_attach_detach.py  (size=5225 bytes)

```python
# tests/test_categories_attach_detach.py
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env (cu fallback-uri sigure) ---------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST imediat după pornire (curse init/migrări)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Diagnostic compact despre răspunsul HTTP (status, URL, fragment body/JSON)."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = r.text[:500].replace("\n", "\\n")
    return (
        f"status={r.status_code} {r.request.method} {r.request.url} "
        f"json={j!r} text='{snippet}...'"
    )


def _assert_status(r: httpx.Response, expected: int | tuple[int, ...]):
    if isinstance(expected, int):
        ok = r.status_code == expected
        exp_str = str(expected)
    else:
        ok = r.status_code in expected
        exp_str = "|".join(map(str, expected))
    assert ok, f"expected {exp_str} but got: {_dump_response(r)}"


def _wait_until_healthy(c: httpx.Client):
    """Așteaptă /health să raporteze 200 OK înainte de a rula testele."""
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _post_with_retry(
    c: httpx.Client, url: str, json: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for _ in range(1, POST_RETRIES + 1):
        try:
            return c.post(url, json=json)
        except Exception as exc:
            last_exc = exc
            time.sleep(POST_RETRY_SLEEP)
    raise AssertionError(f"POST {url} failed after {POST_RETRIES} retries: {last_exc!r}")


# --- Helper-e API -------------------------------------------------------------
def create_category(c: httpx.Client, *, name: Optional[str] = None, description: str = "tmp") -> Dict[str, Any]:
    payload = {"name": name or f"Cat_{uuid.uuid4().hex[:8]}", "description": description}
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["name"] == payload["name"], j
    return j


def create_product(c: httpx.Client, *, name: str = "Tmp Product", price: float = 1.23) -> Dict[str, Any]:
    payload = {"name": name, "price": price, "sku": f"SKU-TST-{uuid.uuid4().hex[:10]}"}
    r = _post_with_retry(c, "/products", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert "id" in j and isinstance(j["id"], int), j
    assert j["sku"] == payload["sku"], j
    return j


def list_products_for_category(c: httpx.Client, category_id: int, *, limit: int = 50) -> list[Dict[str, Any]]:
    r = c.get("/products", params={"category_id": category_id, "limit": limit})
    _assert_status(r, 200)
    j = r.json()
    assert isinstance(j.get("items"), list), j
    return j["items"]


def attach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.post(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


def detach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.delete(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP către API-ul deja pornit (containerul app-test)."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_attach_detach_idempotent(client: httpx.Client):
    cat = create_category(client)
    prod = create_product(client)
    cid, pid = cat["id"], prod["id"]

    # attach de 2 ori -> ambele 204 (idempotent)
    attach_product(client, cid, pid)
    attach_product(client, cid, pid)

    # apare în listare după attach (exact o singură dată)
    items = list_products_for_category(client, cid)
    ids = [p.get("id") for p in items]
    assert pid in ids, items
    assert ids.count(pid) == 1, f"Product appears duplicated after idempotent attach: {items}"

    # detach de 2 ori -> ambele 204 (idempotent)
    detach_product(client, cid, pid)
    detach_product(client, cid, pid)

    # nu mai apare în listare după detach
    items_after = list_products_for_category(client, cid)
    assert all(p.get("id") != pid for p in items_after), items_after

```

# path-ul fisierului: tests/test_category_m2m.py  (size=5906 bytes)

```python
# tests/test_category_m2m.py
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env (cu fallback-uri sigure) ---------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST imediat după pornire (curse init/migrări)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Diagnostic compact: status, URL, fragment body/JSON."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = (r.text or "")[:500].replace("\n", "\\n")
    return (
        f"status={r.status_code} {r.request.method} {r.request.url} "
        f"json={j!r} text='{snippet}...'"
    )


def _assert_status(r: httpx.Response, expected: int | tuple[int, ...]):
    if isinstance(expected, int):
        ok = r.status_code == expected
        exp_str = str(expected)
    else:
        ok = r.status_code in expected
        exp_str = "|".join(map(str, expected))
    assert ok, f"expected {exp_str} but got: {_dump_response(r)}"


def _wait_until_healthy(c: httpx.Client):
    """Așteaptă /health să fie 200 OK înainte de testare."""
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _post_with_retry(
    c: httpx.Client, url: str, json: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for _ in range(1, POST_RETRIES + 1):
        try:
            return c.post(url, json=json)
        except Exception as exc:
            last_exc = exc
            time.sleep(POST_RETRY_SLEEP)
    raise AssertionError(f"POST {url} failed after {POST_RETRIES} retries: {last_exc!r}")


def _mk(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --- Helper-e API -------------------------------------------------------------
def create_product(c: httpx.Client, *, name: str | None = None, price: float = 1.0) -> Dict[str, Any]:
    payload = {"name": name or _mk("pytest-prod"), "price": price, "sku": f"SKU-{uuid.uuid4().hex[:10]}"}
    r = _post_with_retry(c, "/products", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert isinstance(j.get("id"), int), j
    assert j.get("sku") == payload["sku"], j
    return j


def create_category(c: httpx.Client, *, name: str | None = None, description: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name or _mk("pytest-cat")}
    if description is not None:
        payload["description"] = description
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert isinstance(j.get("id"), int), j
    assert j.get("name") == payload["name"], j
    return j


def products_in_category(c: httpx.Client, category_id: int, *, limit: int = 50) -> list[Dict[str, Any]]:
    r = c.get("/products", params={"category_id": category_id, "limit": limit})
    _assert_status(r, 200)
    j = r.json()
    assert isinstance(j.get("items"), list), j
    return j["items"]


def attach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.post(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


def detach_product(c: httpx.Client, category_id: int, product_id: int):
    r = c.delete(f"/categories/{category_id}/products/{product_id}")
    _assert_status(r, 204)


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP către API-ul deja pornit (containerul app-test)."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_m2m_attach_two_categories_and_idempotent(client: httpx.Client):
    prod = create_product(client)
    cat1 = create_category(client)
    cat2 = create_category(client)
    pid, c1, c2 = prod["id"], cat1["id"], cat2["id"]

    # attach la ambele categorii (și idempotent pe c1)
    attach_product(client, c1, pid)
    attach_product(client, c2, pid)
    attach_product(client, c1, pid)  # idempotent

    # prezent în listările filtrate (fără duplicate)
    items_c1 = products_in_category(client, c1)
    items_c2 = products_in_category(client, c2)
    ids_c1 = [p.get("id") for p in items_c1]
    ids_c2 = [p.get("id") for p in items_c2]
    assert pid in ids_c1, items_c1
    assert pid in ids_c2, items_c2
    assert ids_c1.count(pid) == 1, f"Product appears duplicated in c1: {items_c1}"
    assert ids_c2.count(pid) == 1, f"Product appears duplicated in c2: {items_c2}"

    # detach din c1 de două ori -> 204 ambele (idempotent)
    detach_product(client, c1, pid)
    detach_product(client, c1, pid)

    # nu mai apare în c1, încă apare în c2
    items_c1 = products_in_category(client, c1)
    items_c2 = products_in_category(client, c2)
    assert all(p.get("id") != pid for p in items_c1), items_c1
    assert any(p.get("id") == pid for p in items_c2), items_c2

    # cleanup: detașează și din c2 (idempotent)
    detach_product(client, c2, pid)
    detach_product(client, c2, pid)

```

# path-ul fisierului: tests/test_category_unique.py  (size=4751 bytes)

```python
# tests/test_category_unique.py
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# --- Config din env -----------------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))

# Retries scurte pentru POST (curse inițializare/migrări imediat după boot)
POST_RETRIES = int(os.getenv("TEST_POST_RETRIES", "3"))
POST_RETRY_SLEEP = float(os.getenv("TEST_POST_RETRY_SLEEP", "0.2"))


# --- Utilitare ----------------------------------------------------------------
def _dump_response(r: httpx.Response) -> str:
    """Diagnostic compact pentru mesaje de aserție."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = (r.text or "")[:500].replace("\n", "\\n")
    return (
        f"status={r.status_code} {r.request.method} {r.request.url} "
        f"json={j!r} text='{snippet}...'"
    )


def _assert_status(r: httpx.Response, expected: int | tuple[int, ...]):
    if isinstance(expected, int):
        ok = r.status_code == expected
        exp_str = str(expected)
    else:
        ok = r.status_code in expected
        exp_str = "|".join(map(str, expected))
    assert ok, f"expected {exp_str} but got: {_dump_response(r)}"


def _wait_until_healthy(c: httpx.Client):
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _post_with_retry(
    c: httpx.Client, url: str, json: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for _ in range(1, POST_RETRIES + 1):
        try:
            return c.post(url, json=json)
        except Exception as exc:
            last_exc = exc
            time.sleep(POST_RETRY_SLEEP)
    raise AssertionError(f"POST {url} failed after {POST_RETRIES} retries: {last_exc!r}")


# --- Helper-e API -------------------------------------------------------------
def create_category(c: httpx.Client, name: str, description: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name}
    if description is not None:
        payload["description"] = description
    r = _post_with_retry(c, "/categories", json=payload)
    _assert_status(r, 201)
    j = r.json()
    assert isinstance(j.get("id"), int), j
    assert j.get("name") == name, j
    return j


def update_category_name(c: httpx.Client, cid: int, new_name: str) -> httpx.Response:
    r = c.put(f"/categories/{cid}", json={"name": new_name})
    return r


def delete_category(c: httpx.Client, cid: int) -> None:
    try:
        c.delete(f"/categories/{cid}")
    except Exception:
        pass


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(10)
def test_category_name_unique_case_insensitive(client: httpx.Client):
    created_ids: list[int] = []
    try:
        base = f"PyTest Uniq {uuid.uuid4().hex[:6]}"

        # 1) creare inițială
        c1 = create_category(client, base)
        created_ids.append(c1["id"])

        # 1.1) update idempotent la același nume -> acceptat (200 sau 204)
        r_same = update_category_name(client, c1["id"], base)
        _assert_status(r_same, (200, 204))

        # 2) același nume cu caz diferit -> 409 Conflict
        dup = base.swapcase()
        r_dup_create = client.post("/categories", json={"name": dup})
        _assert_status(r_dup_create, 409)

        # 3) altă categorie, apoi rename către numele existent (case-insensitive) -> 409
        other = create_category(client, f"{base}-other")
        created_ids.append(other["id"])
        r_conflict = update_category_name(client, other["id"], base)
        _assert_status(r_conflict, 409)

        # 3.1) (opțional) rename către o altă variantă de caz a aceluiași nume -> tot 409
        r_conflict_case = update_category_name(client, other["id"], base.lower())
        _assert_status(r_conflict_case, 409)

    finally:
        for cid in created_ids:
            delete_category(client, cid)

```

# path-ul fisierului: tests/test_emag_offers_read.py  (size=1194 bytes)

```python
# tests/test_emag_offers_read.py
import httpx

BASE = "http://127.0.0.1:8010"

def _post(path, **json):
    url = f"{BASE}{path}"
    r = httpx.post(url, json=json)
    r.raise_for_status()
    return r.json()

def test_filter_by_sku_maps_to_part_number():
    q = "?account=fbe&country=ro&compact=1&fields=id,sku,name"
    data = _post(f"/integrations/emag/product_offer/read{q}", page=1, limit=5, sku="ADS206")
    assert data["total"] == 1
    it = data["items"][0]
    assert it["sku"] == "ADS206"

def test_filter_by_part_number_key_exposes_emag_sku():
    q = "?account=fbe&country=ro&compact=1&fields=id,emag_sku,name"
    data = _post(f"/integrations/emag/product_offer/read{q}", page=1, limit=5, part_number_key="DL0WVYYBM")
    assert data["total"] == 1
    it = data["items"][0]
    assert it["emag_sku"] == "DL0WVYYBM"

def test_openapi_has_params():
    r = httpx.get(f"{BASE}/openapi.json")
    r.raise_for_status()
    schema = r.json()
    params = [p["name"] for p in schema["paths"]["/integrations/emag/product_offer/read"]["post"]["parameters"]]
    for expected in ["format", "filename", "account", "country", "compact", "fields", "sort"]:
        assert expected in params

```

# path-ul fisierului: tests/test_health.py  (size=4554 bytes)

```python
# tests/test_health.py
from __future__ import annotations

import os
import time
from typing import Any, Dict

import httpx
import pytest

# --- Config din env -----------------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
REQ_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "5"))
HEALTH_PATH = os.getenv("TEST_HEALTH_PATH", "/health")
MIGR_PATH = os.getenv("TEST_MIGR_PATH", "/health/migrations")
RETRY_ATTEMPTS = int(os.getenv("TEST_HEALTH_RETRIES", "10"))
RETRY_SLEEP = float(os.getenv("TEST_HEALTH_SLEEP", "0.5"))
# Latență maximă acceptată pentru /health (secunde)
MAX_HEALTH_LATENCY = float(os.getenv("TEST_HEALTH_MAX_LATENCY", "1.5"))
# Dacă vrei să forțezi ca migrațiile să fie prezente (True/1/yes)
EXPECT_MIGRATIONS = os.getenv("TEST_EXPECT_MIGRATIONS_PRESENT", "").lower() in {"1", "true", "yes"}


# --- Utilitare ----------------------------------------------------------------
def _wait_until_healthy(c: httpx.Client):
    """Așteaptă ca endpoint-ul /health să devină 200."""
    for _ in range(RETRY_ATTEMPTS):
        try:
            r = c.get(HEALTH_PATH)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(RETRY_SLEEP)
    pytest.fail(f"API at {BASE_URL} not healthy after {RETRY_ATTEMPTS} attempts")


def _dump_response(r: httpx.Response) -> str:
    """Diagnostic scurt pentru mesaje de aserție."""
    try:
        j = r.json()
    except Exception:
        j = None
    snippet = (r.text or "")[:400].replace("\n", "\\n")
    return f"status={r.status_code} {r.request.method} {r.request.url} json={j!r} text='{snippet}...'"


def _is_json(r: httpx.Response) -> bool:
    return r.headers.get("content-type", "").lower().startswith("application/json")


def _get_json(r: httpx.Response) -> Dict[str, Any]:
    assert _is_json(r), f"unexpected content-type: {r.headers.get('content-type')} | {_dump_response(r)}"
    try:
        return r.json()  # type: ignore[return-value]
    except Exception as exc:
        pytest.fail(f"invalid JSON: {exc!r} | {_dump_response(r)}")


# --- Fixură client ------------------------------------------------------------
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP de sesiune + warm-up health."""
    with httpx.Client(base_url=BASE_URL, timeout=REQ_TIMEOUT) as c:
        _wait_until_healthy(c)
        yield c


# --- Teste --------------------------------------------------------------------
@pytest.mark.timeout(5)
def test_health_ok(client: httpx.Client):
    t0 = time.perf_counter()
    r = client.get(HEALTH_PATH)
    dt = time.perf_counter() - t0

    assert r.status_code == 200, _dump_response(r)
    assert dt <= MAX_HEALTH_LATENCY, f"/health too slow: {dt:.3f}s > {MAX_HEALTH_LATENCY:.3f}s"
    body = _get_json(r)

    # Contract minim: {"status": "ok"}
    assert body.get("status") == "ok", body


@pytest.mark.timeout(5)
def test_health_is_stable_twice(client: httpx.Client):
    """Două apeluri consecutive ar trebui să fie consistente și rapide."""
    r1 = client.get(HEALTH_PATH)
    r2 = client.get(HEALTH_PATH)

    assert r1.status_code == 200, _dump_response(r1)
    assert r2.status_code == 200, _dump_response(r2)

    b1, b2 = _get_json(r1), _get_json(r2)
    assert b1.get("status") == "ok", b1
    assert b2.get("status") == "ok", b2


@pytest.mark.timeout(5)
def test_health_head_or_options_do_not_error(client: httpx.Client):
    """Acceptăm 200/204/405/404 pentru HEAD/OPTIONS, dar nu 5xx."""
    r_head = client.head(HEALTH_PATH)
    r_opt = client.options(HEALTH_PATH)

    assert r_head.status_code < 500, _dump_response(r_head)
    assert r_opt.status_code < 500, _dump_response(r_opt)


@pytest.mark.timeout(5)
def test_migrations_endpoint(client: httpx.Client):
    """Verifică endpoint-ul migrations; opțional impune 'present=True' prin env."""
    r = client.get(MIGR_PATH)

    # Dacă nu există implementare, marchează testul ca xfail (contract minim opțional).
    if r.status_code in (404, 501):
        pytest.xfail(f"{MIGR_PATH} not implemented: {_dump_response(r)}")

    assert r.status_code == 200, _dump_response(r)
    body = _get_json(r)

    # contract minim: câmpul "present" există și e boolean
    assert "present" in body, body
    assert isinstance(body["present"], bool), f"'present' must be bool, got {type(body['present'])}"

    if EXPECT_MIGRATIONS:
        assert body["present"] is True, f"migrations expected to be present, got: {body!r}"

```

# path-ul fisierului: verify_offers_read.sh  (size=5594 bytes, exec)

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8010"
ACC="fbe"
CTY="ro"

pass() { echo "✔ $*"; }
fail() { echo "✘ $*"; exit 1; }

req() { curl -sS "$@"; }
status() { curl -sS -o /dev/null -w "%{http_code}" "$@"; }

# 0) Health & OpenAPI
[ "$(status "$BASE/health/ready")" = "200" ] || fail "/health/ready nu răspunde 200"
pass "health/ready OK"

PATH_OKAPI=$(req "$BASE/openapi.json" | jq -r '.paths | keys[]' | sort)
echo "$PATH_OKAPI" | grep -qx "/integrations/emag/product_offer/read" || fail "ruta /integrations/emag/product_offer/read lipsește din OpenAPI"
! echo "$PATH_OKAPI" | grep -q "/integrations/emag/integrations/emag/product_offer/read" || fail "dublu-prefix detectat în OpenAPI"
pass "OpenAPI rute OK"

# 1) Semantica SKU/emag_sku în meta (debug)
REQ='{"page":1,"limit":1}'
MAP=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&debug=1" \
      -H 'Content-Type: application/json' -d "$REQ" | jq -r '.meta.sku_semantics | "\(.sku)|\(.emag_sku)"')
[ "$MAP" = "part_number|part_number_key" ] || fail "sku_semantics incorect: $MAP"
pass "sku_semantics OK (sku=part_number, emag_sku=part_number_key)"

# 2) Filtrare după SKU
CNT=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&compact=1&fields=sku" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":50,"sku":"ADS206"}' \
     | jq '.items | map(select(.sku=="ADS206")) | length')
[ "$CNT" = "1" ] || fail "filtrarea după sku nu e strictă (ADS206 găsit de $CNT ori)"
pass "filtrare sku OK"

# 3) Filtrare după part_number_key (eMAG SKU)
CNT=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&compact=1&fields=emag_sku" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":50,"part_number_key":"DL0WVYYBM"}' \
     | jq '.items | map(select(.emag_sku=="DL0WVYYBM")) | length')
[ "$CNT" = "1" ] || fail "filtrarea după part_number_key nu e strictă"
pass "filtrare part_number_key OK"

# 4) Compact=0: arată raw keys (sku null, part_number prezent)
RAW=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&compact=0&fields=sku,part_number,part_number_key" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}' \
     | jq -r '.items[0] | (.sku|tostring)+ "|" + .part_number + "|" + .part_number_key')
[[ "$RAW" =~ ^null\|.+\|.+$ ]] || fail "non-compact nu păstrează cheile raw (obținut: $RAW)"
pass "compact=0 OK (chei raw vizibile)"

# 5) Sortare asc/desc deterministă
ASC=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&fields=sku&sort=sku" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":10}' | jq -r '.items[].sku')
echo "$ASC" | sort -c 2>/dev/null || fail "lista nu e sortată ascendent după sku"
DESC=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&fields=sku&sort=-sku" \
      -H 'Content-Type: application/json' -d '{"page":1,"limit":10}' | jq -r '.items[].sku')
echo "$DESC" | sort -r -c 2>/dev/null || fail "lista nu e sortată descendent după sku"
pass "sort asc/desc OK"

# 6) Export CSV: header + content-type + dispoziție fișier
TMPH=$(mktemp)
CSV=$(curl -sS -D "$TMPH" -X POST \
      "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&format=csv&filename=offers.csv&compact=1&fields=id,sku,emag_sku,name,sale_price,stock_total" \
      -H 'Content-Type: application/json' -d '{"page":1,"limit":5}')
head -n1 <<< "$CSV" | grep -qx "id,sku,emag_sku,name,sale_price,stock_total" || fail "CSV header greșit"
grep -qi '^content-type: text/csv' "$TMPH" || fail "CSV content-type lipsă/greșit"
grep -qi 'content-disposition: attachment; filename="offers.csv"' "$TMPH" || fail "CSV Content-Disposition greșit"
rm -f "$TMPH"
pass "CSV OK (header + headers HTTP)"

# 7) Export NDJSON: număr linii corect
NDJ_LINES=$(req -X POST "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&format=ndjson&compact=1&fields=id,sku,name" \
           -H 'Content-Type: application/json' -d '{"page":1,"limit":3}' | wc -l | tr -d ' ')
[ "$NDJ_LINES" = "3" ] || fail "NDJSON are $NDJ_LINES linii, așteptat 3"
pass "NDJSON OK"

# 8) items_only returnează doar cheia items
KEYS=$(req -X POST "$BASE/integrations/emag/product_offer/read?items_only=1&account=$ACC&country=$CTY&compact=1&fields=id,sku" \
      -H 'Content-Type: application/json' -d '{"page":1,"limit":2}' | jq -r 'keys|join(",")')
[ "$KEYS" = "items" ] || fail "items_only nu a ascuns meta/total (chei: $KEYS)"
pass "items_only OK"

# 9) Validări de input (așteptăm 422)
SC=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
     "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&fields=id,sku,NU_EXISTA" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}')
[ "$SC" = "422" ] || fail "fields invalid ar fi trebuit să dea 422, a dat $SC"
SC=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
     "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&sort=pret" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}')
[ "$SC" = "422" ] || fail "sort invalid ar fi trebuit să dea 422, a dat $SC"
SC=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
     "$BASE/integrations/emag/product_offer/read?account=$ACC&country=$CTY&format=xml" \
     -H 'Content-Type: application/json' -d '{"page":1,"limit":1}')
[ "$SC" = "422" ] || fail "format invalid ar fi trebuit să dea 422, a dat $SC"
pass "validări input OK (422)"

echo
pass "Toate testele au trecut 🎉"

```
