"""add is_test to channels and sync authorized destination

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-13 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add is_test column to channels
    op.add_column(
        'channels',
        sa.Column('is_test', sa.Boolean(), server_default='0', nullable=False)
    )
    op.create_index('ix_channels_is_test', 'channels', ['is_test'], unique=False)

    # 2. Non-destructively tag any test channels that might linger
    op.execute("""
        UPDATE channels
        SET is_test = true
        WHERE id LIKE 'test_%'
           OR id LIKE 'dest_%'
           OR id LIKE 'ch_cust_%'
           OR id LIKE 'ch_race_%'
           OR id LIKE 'ch_iso_%'
           OR id LIKE 'ch_dup_%'
           OR id LIKE 'ch_dec_%'
           OR id LIKE 'ch_cancel_%'
           OR id LIKE 'ch_err_%'
           OR id LIKE 'ch_combo_%'
           OR id LIKE 'ch_restart_%'
           OR channel_name LIKE 'Dest Channel%'
           OR channel_name LIKE '%Test%'
           OR channel_url LIKE '%@Dest_%';
    """)

    # 3. Synchronize authorized destination for verified YouTube channel 'clipse'
    op.execute("""
        INSERT INTO channels (
            id, youtube_channel_id, channel_name, channel_url, thumbnail_url,
            is_active, auto_clip, auto_publish, auto_pilot, clips_generated,
            is_destination, is_default_destination, is_test, created_at
        )
        SELECT
            'dest_clipse_auth_01', 'UCH90024qrJHA4amGRxnTldw', 'clipse', 'https://youtube.com/channel/UCH90024qrJHA4amGRxnTldw',
            'https://yt3.ggpht.com/9XIpgbTNH6jT1yAzjcNaJP9RJNEXMPtpYmyWPSlGaJWz34cwxbAOnznB58vqe_nV1IISFY3jLEI=s88-c-k-c0x00ffffff-no-rj',
            true, false, false, false, 0,
            true, true, false, NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM channels WHERE youtube_channel_id = 'UCH90024qrJHA4amGRxnTldw'
        );
    """)


def downgrade() -> None:
    op.drop_index('ix_channels_is_test', table_name='channels')
    op.drop_column('channels', 'is_test')
