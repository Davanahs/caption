"""add_upload_studio_phase2

Revision ID: f2a3b4c5d6e7
Revises: f1b2c3d4e5f6
Create Date: 2026-10-12 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'f1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update upload_batches status check constraint to include processing lifecycles
    op.drop_constraint('ck_upload_batch_status', 'upload_batches', type_='check')
    op.create_check_constraint(
        'ck_upload_batch_status',
        'upload_batches',
        "status IN ('staging', 'uploading', 'validating', 'completed', 'queued', 'processing', 'failed', 'cancelling', 'cancelled', 'deleting')"
    )

    # 2. Add Phase 2 columns to upload_batches
    op.add_column('upload_batches', sa.Column('active_video_id', sa.String(length=64), nullable=True))
    op.add_column('upload_batches', sa.Column('active_task_id', sa.String(length=200), nullable=True))
    op.add_column('upload_batches', sa.Column('worker_heartbeat', sa.DateTime(timezone=True), nullable=True))
    op.add_column('upload_batches', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('upload_batches', sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('upload_batches', sa.Column('batch_error', sa.Text(), nullable=True))

    # 3. Add Phase 2 columns to videos
    op.add_column('videos', sa.Column('processing_status', sa.String(length=30), nullable=False, server_default='none'))
    op.add_column('videos', sa.Column('processing_progress', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('processing_step', sa.String(length=200), nullable=True))
    op.add_column('videos', sa.Column('processing_error', sa.Text(), nullable=True))
    op.add_column('videos', sa.Column('processing_job_id', sa.String(length=64), nullable=True))
    op.add_column('videos', sa.Column('processing_attempt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True))

    # 4. Add check constraint and index on videos.processing_status
    op.create_check_constraint(
        'ck_video_processing_status',
        'videos',
        "processing_status IN ('none', 'queued', 'processing', 'completed', 'failed', 'cancelling', 'cancelled', 'retry_queued')"
    )
    op.create_index('ix_videos_processing_status', 'videos', ['processing_status'])


def downgrade() -> None:
    # 1. Drop index and constraint on videos.processing_status
    op.drop_index('ix_videos_processing_status', table_name='videos')
    op.drop_constraint('ck_video_processing_status', 'videos', type_='check')

    # 2. Drop Phase 2 columns from videos
    op.drop_column('videos', 'processing_completed_at')
    op.drop_column('videos', 'processing_started_at')
    op.drop_column('videos', 'processing_attempt')
    op.drop_column('videos', 'processing_job_id')
    op.drop_column('videos', 'processing_error')
    op.drop_column('videos', 'processing_step')
    op.drop_column('videos', 'processing_progress')
    op.drop_column('videos', 'processing_status')

    # 3. Drop Phase 2 columns from upload_batches
    op.drop_column('upload_batches', 'batch_error')
    op.drop_column('upload_batches', 'processing_completed_at')
    op.drop_column('upload_batches', 'processing_started_at')
    op.drop_column('upload_batches', 'worker_heartbeat')
    op.drop_column('upload_batches', 'active_task_id')
    op.drop_column('upload_batches', 'active_video_id')

    # 4. Restore original Phase 1 status check constraint on upload_batches
    op.drop_constraint('ck_upload_batch_status', 'upload_batches', type_='check')
    op.create_check_constraint(
        'ck_upload_batch_status',
        'upload_batches',
        "status IN ('staging', 'uploading', 'validating', 'completed', 'failed', 'cancelled', 'deleting')"
    )
