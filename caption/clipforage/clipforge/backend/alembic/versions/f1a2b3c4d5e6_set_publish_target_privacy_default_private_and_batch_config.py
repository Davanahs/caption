"""set_publish_target_privacy_default_private_and_batch_config

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('publish_targets', 'privacy', server_default='private')
    op.add_column('upload_batches', sa.Column('config', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('upload_batches', 'config')
    # Preserve private-publishing security policy on rollback (do not restore 'public').
    op.alter_column('publish_targets', 'privacy', server_default=None)

