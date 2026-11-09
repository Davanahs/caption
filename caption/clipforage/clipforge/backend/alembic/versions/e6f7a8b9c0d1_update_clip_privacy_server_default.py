"""update_clip_privacy_server_default_to_private

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-10-26 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f7a8b9c0d1'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set server_default for clips.privacy column to 'private'
    op.alter_column('clips', 'privacy', server_default='private')


def downgrade() -> None:
    # OPERATIONAL ROLLBACK SAFETY ASSESSMENT:
    # Conventionally, reverting this migration might restore server_default='public'.
    # However, reverting to 'public' violates the permanent private-publishing requirement
    # by silently reintroducing the unsafe default that caused historical public uploads (CF-DEF-013).
    #
    # SAFE ROLLBACK STRATEGY:
    # We remove the server default (server_default=None). Because clips.privacy is NOT NULL,
    # any INSERT omitting privacy will raise a NOT NULL constraint violation at the database level
    # instead of silently inserting 'public'.
    # If an operator specifically requires restoring the legacy 'public' default during disaster recovery,
    # it must be executed as an explicit, deliberate manual DDL action:
    #   ALTER TABLE clips ALTER COLUMN privacy SET DEFAULT 'public';
    op.alter_column('clips', 'privacy', server_default=None)

