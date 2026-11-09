"""add_upload_studio_phase1

Revision ID: f1b2c3d4e5f6
Revises: e1a2b3c4d5e6
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pathlib import Path
import os
import uuid

# revision identifiers, used by Alembic.
revision: str = 'f1b2c3d4e5f6'
down_revision: Union[str, None] = 'e1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create storage_reservation_coordinators table
    op.create_table(
        'storage_reservation_coordinators',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('reserved_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('volume_id', sa.String(length=128), nullable=False),
        sa.Column('volume_hmac', sa.String(length=128), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )

    # Provision storage identity token if missing, and seed 'global' coordinator
    from backend.core.config import settings
    from backend.core.storage_identity import provision_storage_identity, TOKEN_FILENAME
    import json

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    token_file = upload_root / TOKEN_FILENAME
    
    if token_file.exists():
        try:
            with open(token_file, "r", encoding="utf-8") as tf:
                tok_data = json.load(tf)
            vol_id = tok_data.get("volume_id", str(uuid.uuid4()))
            vol_hmac = tok_data.get("hmac_sha256", "preprovisioned")
        except Exception:
            token_data = provision_storage_identity(
                upload_dir=upload_root,
                volume_id=str(uuid.uuid4()),
                secret_key=getattr(settings, "STORAGE_IDENTITY_SECRET", None) or getattr(settings, "SECRET_KEY", None)
            )
            vol_id = token_data["volume_id"]
            vol_hmac = token_data["hmac_sha256"]
    else:
        token_data = provision_storage_identity(
            upload_dir=upload_root,
            volume_id=str(uuid.uuid4()),
            secret_key=getattr(settings, "STORAGE_IDENTITY_SECRET", None) or getattr(settings, "SECRET_KEY", None)
        )
        vol_id = token_data["volume_id"]
        vol_hmac = token_data["hmac_sha256"]

    conn = op.get_bind()
    conn.execute(
        sa.text("""
            INSERT INTO storage_reservation_coordinators (id, reserved_bytes, volume_id, volume_hmac)
            VALUES ('global', 0, :vol_id, :vol_hmac)
            ON CONFLICT (id) DO NOTHING
        """),
        {"vol_id": vol_id, "vol_hmac": vol_hmac}
    )

    # 2. Create upload_batches table
    op.create_table(
        'upload_batches',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='staging'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reserved_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('idempotency_key', name='uq_upload_batches_idempotency_key'),
        sa.CheckConstraint(
            "status IN ('staging', 'uploading', 'validating', 'completed', 'failed', 'cancelled', 'deleting')",
            name='ck_upload_batch_status'
        )
    )
    op.create_index('ix_upload_batches_status', 'upload_batches', ['status'])

    # 3. Add columns to videos table
    op.add_column('videos', sa.Column('is_manual_upload', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('videos', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('videos', sa.Column('resolution', sa.String(length=50), nullable=True))
    op.add_column('videos', sa.Column('source_filename', sa.String(length=500), nullable=True))
    op.add_column('videos', sa.Column('file_size', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('upload_batch_id', sa.String(length=64), nullable=True))
    op.add_column('videos', sa.Column('queue_position', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('upload_status', sa.String(length=30), nullable=True))
    op.add_column('videos', sa.Column('uploaded_bytes', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('client_item_id', sa.String(length=64), nullable=True))
    op.add_column('videos', sa.Column('upload_lease_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('reservation_state', sa.String(length=30), nullable=False, server_default='none'))
    op.add_column('videos', sa.Column('reserved_bytes', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('active_writer_token', sa.String(length=64), nullable=True))
    op.add_column('videos', sa.Column('part_disposition', sa.String(length=30), nullable=False, server_default='none'))
    op.add_column('videos', sa.Column('final_disposition', sa.String(length=30), nullable=False, server_default='none'))

    # 4. Add constraints and indexes on videos
    op.create_foreign_key(
        'fk_videos_upload_batch_id',
        'videos', 'upload_batches',
        ['upload_batch_id'], ['id'],
        ondelete='RESTRICT'
    )
    op.create_check_constraint(
        'ck_video_upload_status',
        'videos',
        "upload_status IN ('queued', 'uploading', 'validating', 'uploaded', 'failed', 'cancelled') OR upload_status IS NULL"
    )
    op.create_check_constraint(
        'ck_video_reservation_state',
        'videos',
        "reservation_state IN ('none', 'initial', 'headroom_only', 'released')"
    )
    op.create_check_constraint(
        'ck_video_part_disposition',
        'videos',
        "part_disposition IN ('none', 'promote_to_final', 'delete')"
    )
    op.create_check_constraint(
        'ck_video_final_disposition',
        'videos',
        "final_disposition IN ('none', 'retain_valid', 'delete')"
    )
    op.create_check_constraint(
        'ck_video_size_consistency',
        'videos',
        "file_size = total_bytes"
    )

    op.create_index('ix_videos_upload_batch_id', 'videos', ['upload_batch_id'])
    
    # Deferrable unique constraint for batch reordering
    op.create_unique_constraint(
        'uq_batch_queue_pos',
        'videos',
        ['upload_batch_id', 'queue_position'],
        deferrable=True,
        initially='DEFERRED'
    )
    
    # Unique index for client_item_id per batch
    op.create_index(
        'uq_batch_client_item',
        'videos',
        ['upload_batch_id', 'client_item_id'],
        unique=True,
        postgresql_where=sa.text('client_item_id IS NOT NULL')
    )


def downgrade() -> None:
    conn = op.get_bind()
    from backend.core.config import settings
    from backend.core.storage_identity import verify_storage_root_identity
    from pathlib import Path
    import os

    # -------------------------------------------------------------------------
    # 1. Database Precondition Checks (Studio-specific vs legacy separation)
    # -------------------------------------------------------------------------
    try:
        batch_count = conn.execute(sa.text("SELECT COUNT(*) FROM upload_batches")).scalar() or 0
        studio_video_count = conn.execute(sa.text("""
            SELECT COUNT(*) FROM videos
            WHERE upload_batch_id IS NOT NULL
               OR is_manual_upload = TRUE
               OR upload_status IS NOT NULL
               OR reserved_bytes > 0
               OR reservation_state != 'none'
               OR part_disposition != 'none'
               OR final_disposition != 'none'
               OR active_writer_token IS NOT NULL
               OR client_item_id IS NOT NULL
        """)).scalar() or 0
        video_reserved_bytes = conn.execute(
            sa.text("SELECT COALESCE(SUM(reserved_bytes), 0) FROM videos")
        ).scalar() or 0
        coordinator_reserved_bytes = conn.execute(
            sa.text("SELECT COALESCE(reserved_bytes, 0) FROM storage_reservation_coordinators WHERE id = 'global'")
        ).scalar() or 0
        db_volume_id = conn.execute(
            sa.text("SELECT volume_id FROM storage_reservation_coordinators WHERE id = 'global'")
        ).scalar() or ""
    except Exception as exc:
        raise RuntimeError(f"Downgrade refused: Database inspection failed ({exc}). Aborting.") from exc

    # -------------------------------------------------------------------------
    # 2. Genuine Storage-Root & Mount Identity Verification
    # -------------------------------------------------------------------------
    upload_root = Path(settings.UPLOAD_DIR)
    secret_key = getattr(settings, "STORAGE_IDENTITY_SECRET", None) or getattr(settings, "SECRET_KEY", None)
    
    # If environment explicitly sets BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST=1 (used strictly in mock unit tests)
    bypass_mount = os.environ.get("BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST") == "1"
    
    is_valid_storage, reason = verify_storage_root_identity(
        upload_dir=upload_root,
        expected_volume_id=db_volume_id,
        secret_key=secret_key,
        skip_mount_check=bypass_mount
    )
    if not is_valid_storage:
        raise RuntimeError(f"Downgrade refused: Storage identity verification failed: {reason}. Aborting.")

    # -------------------------------------------------------------------------
    # 3. Fail-Closed Directory Traversal
    # -------------------------------------------------------------------------
    studio_dir = upload_root.resolve() / "studio"
    physical_file_count = 0

    def fail_closed_walk_error(err: OSError) -> None:
        raise RuntimeError(f"Downgrade refused: Inaccessible path during storage traversal: {err.filename} ({err})") from err

    if studio_dir.exists():
        if not os.access(studio_dir, os.R_OK):
            raise RuntimeError(f"Downgrade refused: Studio directory {studio_dir} is not readable.")

        try:
            for root, dirs, files in os.walk(studio_dir, onerror=fail_closed_walk_error):
                root_path = Path(root)
                for d in dirs:
                    d_path = root_path / d
                    if d_path.is_symlink():
                        raise RuntimeError(f"Downgrade refused: Symlink detected in storage hierarchy: {d_path}")
                    if not os.access(d_path, os.R_OK):
                        raise RuntimeError(f"Downgrade refused: Inaccessible directory: {d_path}")
                for f in files:
                    f_path = root_path / f
                    if f_path.is_symlink():
                        raise RuntimeError(f"Downgrade refused: Symlink detected in storage hierarchy: {f_path}")
                    if not os.access(f_path, os.R_OK):
                        raise RuntimeError(f"Downgrade refused: Inaccessible file: {f_path}")
                    physical_file_count += 1
        except Exception as exc:
            raise RuntimeError(f"Downgrade refused: Storage traversal failed ({exc}). Aborting.") from exc

    # -------------------------------------------------------------------------
    # 4. Strict Fail-Closed Verification
    # -------------------------------------------------------------------------
    if (
        batch_count > 0
        or studio_video_count > 0
        or video_reserved_bytes > 0
        or coordinator_reserved_bytes > 0
        or physical_file_count > 0
    ):
        raise RuntimeError(
            f"Downgrade refused: Active Upload Studio state detected "
            f"(batches: {batch_count}, studio_videos: {studio_video_count}, "
            f"video_reserved_bytes: {video_reserved_bytes}, "
            f"coordinator_reserved_bytes: {coordinator_reserved_bytes}, "
            f"physical_studio_files: {physical_file_count}). "
            f"All Studio batches, videos, reservations, and files must be cleared before downgrade is permitted."
        )

    # -------------------------------------------------------------------------
    # 5. Safe DDL Execution (Strictly executed when all checks pass)
    # -------------------------------------------------------------------------
    op.drop_index('uq_batch_client_item', table_name='videos')
    op.drop_constraint('uq_batch_queue_pos', 'videos', type_='unique')
    op.drop_index('ix_videos_upload_batch_id', table_name='videos')

    op.drop_constraint('ck_video_size_consistency', 'videos', type_='check')
    op.drop_constraint('ck_video_final_disposition', 'videos', type_='check')
    op.drop_constraint('ck_video_part_disposition', 'videos', type_='check')
    op.drop_constraint('ck_video_reservation_state', 'videos', type_='check')
    op.drop_constraint('ck_video_upload_status', 'videos', type_='check')
    op.drop_constraint('fk_videos_upload_batch_id', 'videos', type_='foreignkey')

    op.drop_column('videos', 'final_disposition')
    op.drop_column('videos', 'part_disposition')
    op.drop_column('videos', 'active_writer_token')
    op.drop_column('videos', 'reserved_bytes')
    op.drop_column('videos', 'reservation_state')
    op.drop_column('videos', 'upload_lease_until')
    op.drop_column('videos', 'client_item_id')
    op.drop_column('videos', 'total_bytes')
    op.drop_column('videos', 'uploaded_bytes')
    op.drop_column('videos', 'upload_status')
    op.drop_column('videos', 'queue_position')
    op.drop_column('videos', 'upload_batch_id')
    op.drop_column('videos', 'file_size')
    op.drop_column('videos', 'source_filename')
    op.drop_column('videos', 'resolution')
    op.drop_column('videos', 'is_archived')
    op.drop_column('videos', 'is_manual_upload')

    op.drop_index('ix_upload_batches_status', table_name='upload_batches')
    op.drop_table('upload_batches')
    op.drop_table('storage_reservation_coordinators')
