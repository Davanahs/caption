"""add_live_stream_jobs

Revision ID: 0e5c1875af6a
Revises: f1a2b3c4d5e6
Create Date: 2026-11-18 04:15:23.331550

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e5c1875af6a'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'live_stream_jobs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('video_id', sa.String(), nullable=True),
        sa.Column('youtube_url', sa.String(500), nullable=False),
        sa.Column('youtube_id', sa.String(50), nullable=False),
        sa.Column('video_title', sa.String(500), nullable=False, server_default='Live Stream'),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('channel_name', sa.String(200), nullable=True),
        sa.Column('channel_id', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='monitoring'),
        sa.Column('live_status', sa.String(50), nullable=False, server_default='is_live'),
        sa.Column('current_step', sa.String(300), nullable=True),
        sa.Column('total_duration', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('processed_until', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('newly_detected_duration', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('clips_count', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('clip_generation_mode', sa.String(50), nullable=False, server_default='ai_highlights'),
        sa.Column('monitoring_interval_minutes', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stop_requested', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('active_task_id', sa.String(200), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_live_stream_jobs_youtube_id', 'live_stream_jobs', ['youtube_id'])
    op.create_index('ix_live_stream_jobs_status', 'live_stream_jobs', ['status'])

    op.create_table(
        'live_stream_segments',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('job_id', sa.String(), sa.ForeignKey('live_stream_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('segment_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('start_time', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('end_time', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('duration', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('clips_generated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_live_stream_segments_job_id', 'live_stream_segments', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_live_stream_segments_job_id', table_name='live_stream_segments')
    op.drop_table('live_stream_segments')
    op.drop_index('ix_live_stream_jobs_status', table_name='live_stream_jobs')
    op.drop_index('ix_live_stream_jobs_youtube_id', table_name='live_stream_jobs')
    op.drop_table('live_stream_jobs')

