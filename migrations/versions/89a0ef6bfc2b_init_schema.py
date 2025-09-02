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
