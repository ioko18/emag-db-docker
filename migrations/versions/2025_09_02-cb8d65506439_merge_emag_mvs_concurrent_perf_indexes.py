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
