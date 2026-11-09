"""add_channel_profiles_and_video_decisions

Revision ID: f4c5d6e7f8a9
Revises: f3b4c5d6e7f8
Create Date: 2026-10-13 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'f4c5d6e7f8a9'
down_revision: Union[str, None] = 'f3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    tables = inspector.get_table_names()

    # 1. Add processing_profile to channels
    if 'channels' in tables:
        ch_cols = [c['name'] for c in inspector.get_columns('channels')]
        if 'processing_profile' not in ch_cols:
            op.add_column('channels', sa.Column('processing_profile', sa.JSON(), nullable=True))

    # 2. Add pipeline_started_at, completed_at, channel_id to jobs
    if 'jobs' in tables:
        job_cols = [c['name'] for c in inspector.get_columns('jobs')]
        if 'pipeline_started_at' not in job_cols:
            op.add_column('jobs', sa.Column('pipeline_started_at', sa.DateTime(timezone=True), nullable=True))
        if 'completed_at' not in job_cols:
            op.add_column('jobs', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
        if 'channel_id' not in job_cols:
            op.add_column('jobs', sa.Column('channel_id', sa.String(length=100), nullable=True))
            op.create_index('ix_jobs_channel_id', 'jobs', ['channel_id'])

    # 3. Create video_decisions table
    if 'video_decisions' not in tables:
        op.create_table(
            'video_decisions',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('channel_id', sa.String(length=100), sa.ForeignKey('channels.id', ondelete='SET NULL'), nullable=True),
            sa.Column('video_id', sa.String(), nullable=True),
            sa.Column('youtube_id', sa.String(length=50), nullable=False),
            sa.Column('youtube_url', sa.String(length=500), nullable=False),
            sa.Column('video_title', sa.String(length=500), nullable=False, server_default='Untitled'),
            sa.Column('video_thumbnail', sa.String(length=500), nullable=True),
            sa.Column('channel_profile_snapshot', sa.JSON(), nullable=False),
            sa.Column('overrides', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='awaiting_settings'),
            sa.Column('decision_deadline', sa.DateTime(timezone=True), nullable=False),
            sa.Column('customization_lease_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('job_id', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint('channel_id', 'youtube_id', name='uix_video_decisions_channel_yt')
        )
        op.create_index('ix_video_decisions_status_deadline', 'video_decisions', ['status', 'decision_deadline'])
        op.create_index('ix_video_decisions_status_lease', 'video_decisions', ['status', 'customization_lease_expires_at'])
        op.create_index('ix_video_decisions_youtube_id', 'video_decisions', ['youtube_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    tables = inspector.get_table_names()

    # Downgrade Data Protection Guard: Refuse downgrade if nonempty data exists
    if 'video_decisions' in tables:
        count = bind.execute(sa.text("SELECT count(*) FROM video_decisions")).scalar() or 0
        if count > 0:
            raise RuntimeError(
                f"[Alembic Downgrade Guard] Refusing downgrade: 'video_decisions' contains {count} records. "
                "Data loss prevention rule forbids dropping nonempty decision records."
            )

    if 'channels' in tables:
        prof_count = bind.execute(sa.text("SELECT count(*) FROM channels WHERE processing_profile IS NOT NULL")).scalar() or 0
        if prof_count > 0:
            raise RuntimeError(
                f"[Alembic Downgrade Guard] Refusing downgrade: {prof_count} channels have active processing profiles. "
                "Data loss prevention rule forbids dropping channel profiles."
            )

    # Clean downgrade operations
    if 'video_decisions' in tables:
        op.drop_index('ix_video_decisions_youtube_id', table_name='video_decisions')
        op.drop_index('ix_video_decisions_status_lease', table_name='video_decisions')
        op.drop_index('ix_video_decisions_status_deadline', table_name='video_decisions')
        op.drop_table('video_decisions')

    if 'jobs' in tables:
        job_indexes = [i['name'] for i in inspector.get_indexes('jobs')]
        if 'ix_jobs_channel_id' in job_indexes:
            op.drop_index('ix_jobs_channel_id', table_name='jobs')
        job_cols = [c['name'] for c in inspector.get_columns('jobs')]
        if 'channel_id' in job_cols:
            op.drop_column('jobs', 'channel_id')
        if 'completed_at' in job_cols:
            op.drop_column('jobs', 'completed_at')
        if 'pipeline_started_at' in job_cols:
            op.drop_column('jobs', 'pipeline_started_at')

    if 'channels' in tables:
        ch_cols = [c['name'] for c in inspector.get_columns('channels')]
        if 'processing_profile' in ch_cols:
            op.drop_column('channels', 'processing_profile')
