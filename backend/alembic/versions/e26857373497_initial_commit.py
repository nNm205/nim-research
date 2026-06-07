"""initial commit (deduplicated)

Revision ID: e26857373497
Revises: acd48066cb11
Create Date: 2026-05-29 09:46:11.392447

This file used to be a parallel "initial schema" migration that created the
same tables as ``acd48066cb11_initial_schema.py`` — the artefact of running
``alembic revision --autogenerate`` twice on a clean DB. On Supabase that
went unnoticed because only one branch was ever applied, but a fresh
Postgres container surfaces the duplication immediately:

    psycopg2.errors.DuplicateTable: relation "users" already exists

Fix: make this revision a no-op that chains *after* ``acd48066cb11`` so
downstream revisions (``add_kb_admin_001`` → …) still resolve, and the
migration graph linearises into a single chain.
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "e26857373497"
down_revision: Union[str, Sequence[str], None] = "acd48066cb11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op — schema already created by ``acd48066cb11``."""
    pass


def downgrade() -> None:
    """No-op — paired with no-op ``upgrade``."""
    pass
