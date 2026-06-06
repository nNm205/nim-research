"""merge kb and section_insights branches

Revision ID: 604d16dec77c
Revises: add_kb_admin_001, add_section_insights_001
Create Date: 2026-06-04 09:53:09.433090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '604d16dec77c'
down_revision: Union[str, Sequence[str], None] = ('add_kb_admin_001', 'add_section_insights_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
