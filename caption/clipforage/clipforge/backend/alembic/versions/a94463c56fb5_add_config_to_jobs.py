"""add config to jobs

Revision ID: a94463c56fb5
Revises: 7bf7d87f0907
Create Date: 2026-09-21 19:19:40.375959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a94463c56fb5'
down_revision: Union[str, None] = '7bf7d87f0907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('config', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'config')
