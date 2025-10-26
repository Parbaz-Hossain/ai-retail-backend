"""merge_approval_branches

Revision ID: fcba8ce3521b
Revises: 0aa2bca22012, f5bef56e33e0
Create Date: 2025-10-26 07:49:55.636952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcba8ce3521b'
down_revision: Union[str, None] = ('0aa2bca22012', 'f5bef56e33e0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
