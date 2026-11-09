"""add_multi_destination_phase1

Revision ID: e1a2b3c4d5e6
Revises: 3d39d71a2820
Create Date: 2026-10-11 10:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5e6'
down_revision: Union[str, None] = '3d39d71a2820'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create channel_destinations table
    op.create_table(
        'channel_destinations',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('source_channel_id', sa.String(length=100), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('destination_channel_id', sa.String(length=100), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('source_channel_id', 'destination_channel_id', name='uix_source_dest')
    )

    # 2. Create publish_targets table
    op.create_table(
        'publish_targets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('clip_id', sa.String(), sa.ForeignKey('clips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('destination_id', sa.String(length=100), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('youtube_video_id', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('privacy', sa.String(length=50), nullable=False, server_default='public'),
        sa.Column('made_for_kids', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('age_restricted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('clip_id', 'destination_id', name='uix_clip_destination')
    )

    conn = op.get_bind()

    # 3. Migrate Channel -> ChannelDestination (source->dest relationships)
    conn.execute(text("""
        INSERT INTO channel_destinations
            (id, source_channel_id, destination_channel_id,
             is_default, expires_at, created_at, updated_at)
        SELECT
            gen_random_uuid()::text,
            c.id,
            c.publish_destination_id,
            TRUE,
            NULL,
            c.created_at,
            NOW()
        FROM channels c
        JOIN channels dest ON dest.id = c.publish_destination_id
        WHERE c.publish_destination_id IS NOT NULL
        ON CONFLICT (source_channel_id, destination_channel_id) DO NOTHING
    """))

    # 4. Migrate Clip -> PublishTarget
    status_values = conn.execute(text(
        "SELECT DISTINCT publish_status FROM clips "
        "WHERE publish_destination_id IS NOT NULL"
    )).scalars().all()

    KNOWN_STATUSES = {'draft', 'pending', 'publishing', 'published',
                      'failed', 'queued', 'scheduled', 'completed'}
    unknown = set(status_values) - KNOWN_STATUSES
    if unknown:
        raise RuntimeError(
            f"MIGRATION ABORT: Unknown publish_status values found: {unknown}."
        )

    # Insert only valid references (excluding orphaned references to non-existent channels)
    conn.execute(text("""
        INSERT INTO publish_targets
            (id, clip_id, destination_id, status,
             youtube_video_id, privacy, made_for_kids, age_restricted,
             scheduled_at, published_at, created_at, updated_at)
        SELECT
            gen_random_uuid()::text,
            c.id,
            c.publish_destination_id,
            CASE c.publish_status
                WHEN 'completed' THEN 'success'
                WHEN 'published' THEN 'success'
                WHEN 'publishing' THEN 'publishing'
                WHEN 'failed' THEN 'failed'
                WHEN 'queued' THEN 'pending'
                WHEN 'scheduled' THEN 'pending'
                ELSE 'pending'
            END,
            c.youtube_short_id,
            c.privacy,
            c.made_for_kids,
            c.age_restricted,
            c.scheduled_at,
            c.published_at,
            c.created_at,
            NOW()
        FROM clips c
        JOIN channels ch ON ch.id = c.publish_destination_id
        WHERE c.publish_destination_id IS NOT NULL
        ON CONFLICT (clip_id, destination_id) DO NOTHING
    """))

    # 5. Row-level verification & orphan auditing
    valid_legacy_count = conn.execute(text("""
        SELECT COUNT(*) FROM clips c
        JOIN channels ch ON c.publish_destination_id = ch.id
    """)).scalar()

    migrated_count = conn.execute(text("SELECT COUNT(*) FROM publish_targets")).scalar()

    if valid_legacy_count != migrated_count:
        raise RuntimeError(
            f"MIGRATION FAILED: valid_legacy_count ({valid_legacy_count}) "
            f"!= migrated_publish_target_count ({migrated_count})"
        )

    # Generic orphan audit (isolate without aborting)
    orphans = conn.execute(text("""
        SELECT c.id AS clip_id, c.publish_destination_id
        FROM clips c
        LEFT JOIN channels ch ON c.publish_destination_id = ch.id
        WHERE c.publish_destination_id IS NOT NULL AND ch.id IS NULL
    """)).fetchall()

    if orphans:
        print(f"[AUDIT] Preserved {len(orphans)} orphaned legacy clip destinations in legacy column:")
        for o in orphans:
            print(f"  Clip {o.clip_id} -> missing destination {o.publish_destination_id}")

    # DO NOT drop legacy columns in Phase 1


def downgrade() -> None:
    op.drop_table('publish_targets')
    op.drop_table('channel_destinations')
