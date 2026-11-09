"""cascade_clip_foreign_keys

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-25 21:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Update task_executions.clip_id foreign key constraint to ON DELETE SET NULL
    op.drop_constraint('task_executions_clip_id_fkey', 'task_executions', type_='foreignkey')
    op.create_foreign_key(
        'task_executions_clip_id_fkey',
        'task_executions', 'clips',
        ['clip_id'], ['id'],
        ondelete='SET NULL'
    )

    # 2. Update child plan tables to ON DELETE CASCADE
    cascade_tables = [
        ('clip_variants', 'clip_variants_clip_id_fkey', 'clip_id'),
        ('clip_retention', 'clip_retention_clip_id_fkey', 'clip_id'),
        ('clip_sfx_plans', 'clip_sfx_plans_clip_id_fkey', 'clip_id'),
        ('clip_visual_plans', 'clip_visual_plans_clip_id_fkey', 'clip_id'),
        ('clip_hook_plans', 'clip_hook_plans_clip_id_fkey', 'clip_id'),
        ('dubbing_plans', 'dubbing_plans_clip_id_fkey', 'clip_id'),
        ('video_tracking_queue', 'video_tracking_queue_clip_id_fkey', 'clip_id'),
        ('publish_records', 'publish_records_clip_id_fkey', 'clip_id'),
    ]

    for table, fk_name, col in cascade_tables:
        op.drop_constraint(fk_name, table, type_='foreignkey')
        op.create_foreign_key(
            fk_name,
            table, 'clips',
            [col], ['id'],
            ondelete='CASCADE'
        )

    # 3. Update dubbing_segments to ON DELETE CASCADE with dubbing_plans
    op.drop_constraint('dubbing_segments_plan_id_fkey', 'dubbing_segments', type_='foreignkey')
    op.create_foreign_key(
        'dubbing_segments_plan_id_fkey',
        'dubbing_segments', 'dubbing_plans',
        ['plan_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('dubbing_segments_plan_id_fkey', 'dubbing_segments', type_='foreignkey')
    op.create_foreign_key(
        'dubbing_segments_plan_id_fkey',
        'dubbing_segments', 'dubbing_plans',
        ['plan_id'], ['id']
    )

    cascade_tables = [
        ('publish_records', 'publish_records_clip_id_fkey', 'clip_id'),
        ('video_tracking_queue', 'video_tracking_queue_clip_id_fkey', 'clip_id'),
        ('dubbing_plans', 'dubbing_plans_clip_id_fkey', 'clip_id'),
        ('clip_hook_plans', 'clip_hook_plans_clip_id_fkey', 'clip_id'),
        ('clip_visual_plans', 'clip_visual_plans_clip_id_fkey', 'clip_id'),
        ('clip_sfx_plans', 'clip_sfx_plans_clip_id_fkey', 'clip_id'),
        ('clip_retention', 'clip_retention_clip_id_fkey', 'clip_id'),
        ('clip_variants', 'clip_variants_clip_id_fkey', 'clip_id'),
    ]

    for table, fk_name, col in cascade_tables:
        op.drop_constraint(fk_name, table, type_='foreignkey')
        op.create_foreign_key(
            fk_name,
            table, 'clips',
            [col], ['id']
        )

    op.drop_constraint('task_executions_clip_id_fkey', 'task_executions', type_='foreignkey')
    op.create_foreign_key(
        'task_executions_clip_id_fkey',
        'task_executions', 'clips',
        ['clip_id'], ['id']
    )
