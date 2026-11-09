"""add_is_test_to_jobs_and_normalize_cancellations

Revision ID: a1b2c3d4e5f6
Revises: f4c5d6e7f8a9
Create Date: 2026-10-13 16:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    tables = inspector.get_table_names()

    if 'jobs' in tables:
        job_cols = [c['name'] for c in inspector.get_columns('jobs')]
        if 'is_test' not in job_cols:
            op.add_column('jobs', sa.Column('is_test', sa.Boolean(), server_default='false', nullable=False))
            op.create_index('ix_jobs_is_test', 'jobs', ['is_test'])

        # 1. Non-destructive classification: Mark synthetic test jobs with is_test = True
        bind.execute(sa.text("""
            UPDATE jobs
            SET is_test = true
            WHERE (
                channel_id LIKE 'ch_dec_%' OR
                channel_id LIKE 'ch_cust_%' OR
                channel_id LIKE 'ch_race_%' OR
                channel_id LIKE 'ch_iso_%' OR
                channel_id LIKE 'ch_dup_%' OR
                channel_id LIKE 'ch_restart_%' OR
                channel_id LIKE 'ch_err_%' OR
                channel_id LIKE 'ch_combo_%' OR
                source_url LIKE '%stale1%' OR
                source_url LIKE '%stale2%' OR
                source_url LIKE '%errvid%' OR
                source_url LIKE '%combo%' OR
                source_url LIKE '%yt_vid_%' OR
                source_url LIKE '%yt_cust_%' OR
                source_url LIKE '%yt_race_%' OR
                source_url LIKE '%yt_a_%' OR
                source_url LIKE '%yt_b_%' OR
                source_url LIKE '%yt_dup_%' OR
                (status = 'pending' AND channel_id IS NULL AND source_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' AND created_at >= '2026-10-13 08:00:00+00')
            )
        """))

        # 2. Normalize legacy cancelled jobs stored as failed
        bind.execute(sa.text("""
            UPDATE jobs
            SET status = 'cancelled'
            WHERE status = 'failed' AND error_message = 'Cancelled by user'
        """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    tables = inspector.get_table_names()

    if 'jobs' in tables:
        job_cols = [c['name'] for c in inspector.get_columns('jobs')]
        if 'is_test' in job_cols:
            op.drop_index('ix_jobs_is_test', table_name='jobs')
            op.drop_column('jobs', 'is_test')
