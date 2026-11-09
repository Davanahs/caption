"""Add destination fields to Channel

Revision ID: d7546ac12261
Revises: a94463c56fb5
Create Date: 2026-09-22 20:13:26.787758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7546ac12261'
down_revision: Union[str, None] = 'a94463c56fb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns
    op.add_column('channels', sa.Column('is_destination', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('channels', sa.Column('is_default_destination', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('channels', sa.Column('default_destination_expires_at', sa.DateTime(timezone=True), nullable=True))

    # Repair orphaned Video.channel_id
    # Set to NULL where the channel_id does not exist in channels table
    op.execute("""
        UPDATE videos 
        SET channel_id = NULL 
        WHERE channel_id IS NOT NULL 
          AND channel_id NOT IN (SELECT id FROM channels)
    """)


def downgrade() -> None:
    op.drop_column('channels', 'default_destination_expires_at')
    op.drop_column('channels', 'is_default_destination')
    op.drop_column('channels', 'is_destination')
