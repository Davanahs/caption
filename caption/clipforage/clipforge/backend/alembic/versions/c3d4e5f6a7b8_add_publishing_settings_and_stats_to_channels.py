"""add publishing_settings and cached_stats to channels

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-13 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add publishing_settings and cached_stats JSON columns to channels
    op.add_column(
        'channels',
        sa.Column('publishing_settings', sa.JSON(), nullable=True)
    )
    op.add_column(
        'channels',
        sa.Column('cached_stats', sa.JSON(), nullable=True)
    )

    # 2. Seed default publishing settings for existing verified destination channels
    op.execute("""
        UPDATE channels
        SET publishing_settings = json_build_object(
            'default_privacy', 'public',
            'default_category', '22',
            'default_license', 'youtube',
            'default_made_for_kids', false,
            'default_age_restricted', false,
            'default_tags', 'shorts, viral',
            'watermark_url', watermark_url,
            'brand_color_primary', brand_color_primary,
            'brand_logo_position', brand_logo_position
        )
        WHERE is_destination = true AND publishing_settings IS NULL;
    """)


def downgrade() -> None:
    op.drop_column('channels', 'cached_stats')
    op.drop_column('channels', 'publishing_settings')
