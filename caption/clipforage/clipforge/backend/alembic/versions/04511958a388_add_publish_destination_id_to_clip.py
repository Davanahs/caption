"""Add publish_destination_id to Clip

Revision ID: 04511958a388
Revises: d7546ac12261
Create Date: 2026-09-22 20:44:37.554164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04511958a388'
down_revision: Union[str, None] = 'd7546ac12261'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clips', sa.Column('publish_destination_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('clips', 'publish_destination_id')
