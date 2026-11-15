"""add_destination_outros_and_multi_target_publishing

Revision ID: e7f8a9b0c1d2
Revises: e6f7a8b9c0d1
Create Date: 2026-11-11 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create destination_outros table
    op.create_table(
        'destination_outros',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('channel_id', sa.String(length=100), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('outro_type', sa.String(length=20), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('has_audio', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_destination_outros_channel_id', 'destination_outros', ['channel_id'])
    op.create_index('ix_destination_outros_is_active', 'destination_outros', ['is_active'])

    # 2. Add active_outro_id to channels table with foreign key and index
    op.add_column('channels', sa.Column('active_outro_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_channels_active_outro_id',
        'channels', 'destination_outros',
        ['active_outro_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_channels_active_outro_id', 'channels', ['active_outro_id'])

    # 3. Add multi-destination publishing and lifecycle tracking columns to publish_targets
    op.add_column('publish_targets', sa.Column('rendered_video_path', sa.String(), nullable=True))
    op.add_column('publish_targets', sa.Column('artifact_storage_key', sa.String(), nullable=True))
    op.add_column('publish_targets', sa.Column('outro_applied_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_publish_targets_outro_applied_id',
        'publish_targets', 'destination_outros',
        ['outro_applied_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_publish_targets_outro_applied_id', 'publish_targets', ['outro_applied_id'])

    op.add_column('publish_targets', sa.Column('publish_stage', sa.String(length=50), nullable=False, server_default='pending'))
    op.add_column('publish_targets', sa.Column('publish_progress', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('publish_targets', sa.Column('publish_task_id', sa.String(length=100), nullable=True))
    op.add_column('publish_targets', sa.Column('publish_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('publish_targets', sa.Column('publish_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('publish_targets', sa.Column('idempotency_key', sa.String(length=100), nullable=True))
    op.create_index('ix_publish_targets_idempotency_key', 'publish_targets', ['idempotency_key'])
    op.add_column('publish_targets', sa.Column('upload_session_uri', sa.Text(), nullable=True))

    # 4. Backfill historical publish_targets data for state alignment
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE publish_targets
        SET publish_stage = CASE
            WHEN status IN ('completed', 'success', 'published') THEN 'published'
            WHEN status = 'failed' THEN 'failed'
            WHEN status = 'publishing' THEN 'uploading'
            ELSE 'pending'
        END,
        publish_progress = CASE
            WHEN status IN ('completed', 'success', 'published') THEN 100.0
            ELSE 0.0
        END,
        idempotency_key = 'pub_' || clip_id || '_' || destination_id
        WHERE idempotency_key IS NULL;
    """))


def downgrade() -> None:
    # 1. Drop constraints, indices, and added columns on publish_targets
    op.drop_index('ix_publish_targets_idempotency_key', table_name='publish_targets')
    op.drop_index('ix_publish_targets_outro_applied_id', table_name='publish_targets')
    op.drop_constraint('fk_publish_targets_outro_applied_id', 'publish_targets', type_='foreignkey')

    op.drop_column('publish_targets', 'upload_session_uri')
    op.drop_column('publish_targets', 'idempotency_key')
    op.drop_column('publish_targets', 'publish_completed_at')
    op.drop_column('publish_targets', 'publish_started_at')
    op.drop_column('publish_targets', 'publish_task_id')
    op.drop_column('publish_targets', 'publish_progress')
    op.drop_column('publish_targets', 'publish_stage')
    op.drop_column('publish_targets', 'outro_applied_id')
    op.drop_column('publish_targets', 'artifact_storage_key')
    op.drop_column('publish_targets', 'rendered_video_path')

    # 2. Drop constraint, index, and column on channels
    op.drop_index('ix_channels_active_outro_id', table_name='channels')
    op.drop_constraint('fk_channels_active_outro_id', 'channels', type_='foreignkey')
    op.drop_column('channels', 'active_outro_id')

    # 3. Drop indices and destination_outros table
    op.drop_index('ix_destination_outros_is_active', table_name='destination_outros')
    op.drop_index('ix_destination_outros_channel_id', table_name='destination_outros')
    op.drop_table('destination_outros')
