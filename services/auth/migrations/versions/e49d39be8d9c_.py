"""empty message

Revision ID: e49d39be8d9c
Revises: 2aea379bf569
Create Date: 2026-01-14 13:52:27.848881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e49d39be8d9c'
down_revision: Union[str, Sequence[str], None] = '2aea379bf569'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
