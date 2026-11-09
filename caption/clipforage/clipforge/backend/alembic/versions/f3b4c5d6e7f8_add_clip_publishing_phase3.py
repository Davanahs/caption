"""add_clip_publishing_phase3

Revision ID: f3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-13 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3b4c5d6e7f8'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Phase 3 columns to clips
    op.add_column('clips', sa.Column('publish_error', sa.Text(), nullable=True))
    op.add_column('clips', sa.Column('publish_task_id', sa.String(length=200), nullable=True))
    op.add_column('clips', sa.Column('publish_attempt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('clips', sa.Column('publish_progress', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('clips', sa.Column('publish_stage', sa.String(length=50), nullable=True))
    op.add_column('clips', sa.Column('publish_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('clips', sa.Column('publish_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('clips', sa.Column('publish_idempotency_key', sa.String(length=128), nullable=True))
    op.add_column('clips', sa.Column('upload_session_uri', sa.String(length=500), nullable=True))

    # 2. Normalize legacy publish_status values
    op.execute("UPDATE clips SET publish_status = 'published' WHERE publish_status = 'completed'")
    op.execute("UPDATE clips SET publish_status = 'draft' WHERE publish_status IS NULL")

    # 3. Add check constraint and index on clips.publish_status
    op.create_check_constraint(
        'ck_clip_publish_status',
        'clips',
        "publish_status IN ('draft', 'queued', 'uploading', 'finalizing', 'publishing', 'published', 'failed', 'manual_review', 'cancelling', 'cancelled', 'scheduled')"
    )
    op.create_index('ix_clips_publish_status', 'clips', ['publish_status'])


def downgrade() -> None:
    # 1. Drop index and constraint on clips.publish_status
    op.drop_index('ix_clips_publish_status', table_name='clips')
    op.drop_constraint('ck_clip_publish_status', 'clips', type_='check')

    # 2. Drop Phase 3 columns from clips
    op.drop_column('clips', 'upload_session_uri')
    op.drop_column('clips', 'publish_idempotency_key')
    op.drop_column('clips', 'publish_completed_at')
    op.drop_column('clips', 'publish_started_at')
    op.drop_column('clips', 'publish_stage')
    op.drop_column('clips', 'publish_progress')
    op.drop_column('clips', 'publish_attempt')
    op.drop_column('clips', 'publish_task_id')
    op.drop_column('clips', 'publish_error')
