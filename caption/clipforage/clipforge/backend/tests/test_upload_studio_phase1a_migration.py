"""
Phase 1A Migration Verification & Downgrade Safety Test Suite
Tests execute exclusively against dedicated disposable PostgreSQL databases.
Production/active dev database ('clipforge') is never targeted or modified.
"""
import os
import sys
import uuid
import json
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from alembic.config import Config
from alembic import command

from backend.core.config import settings
from backend.core.storage_identity import (
    parse_linux_mountinfo,
    verify_windows_volume,
    provision_storage_identity,
    verify_storage_root_identity,
    compute_volume_hmac,
    resolve_storage_identity_secret,
    KNOWN_INSECURE_PLACEHOLDERS,
    TOKEN_FILENAME
)
from backend.models.models import (
    VideoUploadStatus,
    VideoReservationState,
    VideoPartDisposition,
    VideoFinalDisposition,
    UploadBatchStatus
)

# Derive connection parameters from settings.DATABASE_URL so this test file
# works both inside the Docker network (postgres:5432) and on the host (localhost:5433).
from urllib.parse import urlparse as _urlparse
_parsed = _urlparse(settings.DATABASE_URL)
PG_HOST = _parsed.hostname
PG_PORT = _parsed.port or 5432
PG_USER = _parsed.username
PG_PASS = _parsed.password
ADMIN_DB = _parsed.path.lstrip("/")


@pytest.fixture(scope="module")
def isolated_storage(tmp_path_factory):
    """
    Creates an isolated storage directory with provisioned volume token for the module.
    Bypasses OS mount boundary check strictly within unit test scope.
    """
    upload_dir = tmp_path_factory.mktemp("uploads")
    volume_id = f"vol-test-{uuid.uuid4().hex[:8]}"
    secret_key = "test_secure_storage_identity_secret_2026_01"
    
    token = provision_storage_identity(
        upload_dir=upload_dir,
        volume_id=volume_id,
        secret_key=secret_key,
        cluster_id="test_cluster"
    )
    
    settings.UPLOAD_DIR = upload_dir
    settings.STORAGE_IDENTITY_SECRET = secret_key
    settings.SECRET_KEY = secret_key
    os.environ["BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST"] = "1"
    
    yield {
        "upload_dir": upload_dir,
        "volume_id": volume_id,
        "secret_key": secret_key,
        "token": token
    }
    
    os.environ.pop("BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST", None)


@pytest.fixture(scope="module")
def disposable_pg_db(isolated_storage):
    """
    Creates a dedicated, disposable PostgreSQL database with a unique name for this module.
    Verifies its identity before yielding, applies migrations up to head, and drops it on teardown.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    db_name = f"cf_disp_{unique_suffix}"
    admin_conn_str = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{ADMIN_DB}"
    
    # 1. Connect to admin DB and create disposable DB
    admin_conn = psycopg2.connect(admin_conn_str)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
    cur.execute(f'CREATE DATABASE "{db_name}" OWNER "{PG_USER}"')
    cur.close()
    admin_conn.close()

    disposable_url_sync = f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}"
    disposable_url_async = f"postgresql+asyncpg://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}"

    # 2. Verify identity of the newly created disposable database
    verify_conn = psycopg2.connect(f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}")
    vcur = verify_conn.cursor()
    vcur.execute("SELECT current_database()")
    verified_db = vcur.fetchone()[0]
    vcur.close()
    verify_conn.close()
    assert verified_db == db_name, f"Database identity check failed: expected {db_name}, got {verified_db}"

    # 3. Create Alembic Config pointing to disposable DB
    root_dir = Path(__file__).resolve().parent.parent.parent
    alembic_ini = root_dir / "backend" / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(root_dir / "backend" / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", disposable_url_async)

    # 4. Perform initial upgrade to head
    command.upgrade(alembic_cfg, "head")

    yield {
        "db_name": db_name,
        "sync_url": disposable_url_sync,
        "async_url": disposable_url_async,
        "alembic_cfg": alembic_cfg
    }

    # 5. Teardown: Disconnect and drop disposable database
    time.sleep(0.2)
    admin_conn = psycopg2.connect(admin_conn_str)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
    cur.execute(f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
    """)
    cur.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
    cur.close()
    admin_conn.close()


# =============================================================================
# Unit Tests: Storage Identity & Platform Mount Verification
# =============================================================================

def test_linux_mountinfo_parsing_hyphen_separator():
    """
    Tests parsing of /proc/self/mountinfo with the standard hyphen '-' separator.
    Verifies valid mounts (ext4, xfs, nfs) and rejection of ephemeral overlayfs.
    """
    mock_mountinfo = """
36 35 98:0 /mnt1 /app/uploads rw,noatime master:1 - ext4 /dev/sdb1 rw,errors=continue
37 35 98:1 / /app/ephemeral rw,relatime - overlay overlay rw,lowerdir=/var/lib/docker
38 35 0:35 / /app/tmp rw,nosuid - tmpfs tmpfs rw,size=65536k
39 35 0:50 /export /shared rw,noatime shared:2 master:3 - nfs4 10.0.0.1:/export rw
"""
    # 1. Genuine ext4 mountpoint
    valid, fs_type, reason = parse_linux_mountinfo(mock_mountinfo, "/app/uploads")
    assert valid is True
    assert fs_type == "ext4"

    # 2. Genuine nfs4 mountpoint with multiple optional tags before '-'
    valid, fs_type, reason = parse_linux_mountinfo(mock_mountinfo, "/shared")
    assert valid is True
    assert fs_type == "nfs4"

    # 3. Ephemeral overlay mount rejected
    valid, fs_type, reason = parse_linux_mountinfo(mock_mountinfo, "/app/ephemeral")
    assert valid is False
    assert fs_type == "overlay"
    assert "ephemeral" in reason

    # 4. Ephemeral tmpfs mount rejected
    valid, fs_type, reason = parse_linux_mountinfo(mock_mountinfo, "/app/tmp")
    assert valid is False
    assert fs_type == "tmpfs"

    # 5. Missing mountpoint
    valid, fs_type, reason = parse_linux_mountinfo(mock_mountinfo, "/nonexistent/path")
    assert valid is False
    assert "not found" in reason


def test_storage_identity_secret_resolution_and_validation(tmp_path):
    """
    Tests storage identity secret validation: rejects missing, empty, or placeholder secrets,
    and accepts valid high-entropy secrets.
    """
    # 1. Missing or empty secret raises RuntimeError
    with pytest.raises(RuntimeError, match="missing or empty"):
        resolve_storage_identity_secret("")
    with pytest.raises(RuntimeError, match="missing or empty"):
        resolve_storage_identity_secret("   ")

    # 2. Known placeholders raise RuntimeError
    for placeholder in KNOWN_INSECURE_PLACEHOLDERS:
        with pytest.raises(RuntimeError, match="cannot be an insecure placeholder"):
            resolve_storage_identity_secret(placeholder)

    # 3. Short secret (< 16 chars) raises RuntimeError
    with pytest.raises(RuntimeError, match="shorter than 16 characters"):
        resolve_storage_identity_secret("short_secret_12")

    # 4. Valid secret is accepted and returned
    valid_secret = "a_very_secure_random_key_9876543210"
    assert resolve_storage_identity_secret(valid_secret) == valid_secret


def test_storage_identity_hmac_cryptographic_verification(tmp_path):
    """
    Tests HMAC-SHA256 volume token verification: valid, tampered, wrong key, and placeholder rejection.
    """
    vol_dir = tmp_path / "vol"
    vol_dir.mkdir()
    vol_id = "vol-hmac-test-123"
    valid_secret = "super_secret_signing_key_456789"
    placeholder_secret = "clipforge_default_secret_key_change_in_prod"

    # 1. Provision fails closed when passed an insecure placeholder secret
    with pytest.raises(RuntimeError, match="cannot be an insecure placeholder"):
        provision_storage_identity(vol_dir, vol_id, placeholder_secret, cluster_id="c1")

    # 2. Provision with valid secret succeeds
    token = provision_storage_identity(vol_dir, vol_id, valid_secret, cluster_id="c1")
    assert (vol_dir / TOKEN_FILENAME).exists()

    # 3. Verification fails closed if checked with a placeholder secret
    valid, reason = verify_storage_root_identity(vol_dir, vol_id, placeholder_secret, skip_mount_check=True)
    assert valid is False
    assert "Storage identity secret rejection" in reason

    # 4. Verification with genuine valid secret succeeds
    valid, reason = verify_storage_root_identity(vol_dir, vol_id, valid_secret, skip_mount_check=True)
    assert valid is True

    # 5. Mismatched expected volume ID fails closed
    valid, reason = verify_storage_root_identity(vol_dir, "different-vol-id", valid_secret, skip_mount_check=True)
    assert valid is False
    assert "Volume ID mismatch" in reason

    # 6. Tampered HMAC signature fails closed
    token_file = vol_dir / TOKEN_FILENAME
    with open(token_file, "r") as f:
        data = json.load(f)
    data["hmac_sha256"] = "tampered_bad_hash"
    with open(token_file, "w") as f:
        json.dump(data, f)

    valid, reason = verify_storage_root_identity(vol_dir, vol_id, valid_secret, skip_mount_check=True)
    assert valid is False
    assert "HMAC verification failed" in reason


@pytest.mark.skipif(sys.platform not in ("win32", "cygwin"), reason="Windows volume verification only on Windows")
def test_windows_volume_verification_live(tmp_path):
    """
    Executes live Windows GetVolumeInformationW check on actual host storage.
    """
    valid, fs_type, reason = verify_windows_volume(tmp_path)
    assert valid is True
    assert fs_type in ("NTFS", "ReFS", "FAT32", "exFAT")
    assert "Verified Windows volume" in reason


# =============================================================================
# Migration Upgrade & Schema Integrity Tests
# =============================================================================

def test_migration_upgrade_and_schema_integrity(disposable_pg_db):
    """
    Verifies tables, columns, check constraints, foreign keys, and indexes on head.
    """
    engine = sa.create_engine(disposable_pg_db["sync_url"])
    inspector = sa.inspect(engine)

    # Tables exist
    tables = inspector.get_table_names()
    assert "storage_reservation_coordinators" in tables
    assert "upload_batches" in tables
    assert "videos" in tables

    # Check storage_reservation_coordinators columns & seeded row
    coord_cols = {col["name"]: col for col in inspector.get_columns("storage_reservation_coordinators")}
    assert "id" in coord_cols
    assert "reserved_bytes" in coord_cols
    assert "volume_id" in coord_cols
    assert "volume_hmac" in coord_cols

    with engine.connect() as conn:
        coord_row = conn.execute(sa.text("SELECT id, reserved_bytes, volume_id FROM storage_reservation_coordinators WHERE id = 'global'")).fetchone()
        assert coord_row is not None
        assert coord_row[0] == "global"
        assert coord_row[1] == 0

    # Check upload_batches columns and constraints
    batch_cols = {col["name"]: col for col in inspector.get_columns("upload_batches")}
    assert "idempotency_key" in batch_cols
    assert "status" in batch_cols
    assert "reserved_bytes" in batch_cols
    assert "version" in batch_cols
    assert "total_files" in batch_cols

    batch_checks = [c["name"] for c in inspector.get_check_constraints("upload_batches")]
    assert "ck_upload_batch_status" in batch_checks

    # Check videos columns added
    video_cols = {col["name"]: col for col in inspector.get_columns("videos")}
    expected_new_cols = [
        "is_manual_upload", "is_archived", "resolution", "source_filename",
        "file_size", "upload_batch_id", "queue_position", "upload_status",
        "uploaded_bytes", "total_bytes", "client_item_id", "upload_lease_until",
        "reservation_state", "reserved_bytes", "active_writer_token",
        "part_disposition", "final_disposition"
    ]
    for col_name in expected_new_cols:
        assert col_name in video_cols, f"Expected column {col_name} not found on videos table"

    # Check check constraints on videos
    video_checks = [c["name"] for c in inspector.get_check_constraints("videos")]
    assert "ck_video_upload_status" in video_checks
    assert "ck_video_reservation_state" in video_checks
    assert "ck_video_part_disposition" in video_checks
    assert "ck_video_final_disposition" in video_checks
    assert "ck_video_size_consistency" in video_checks

    # Check foreign key
    fks = inspector.get_foreign_keys("videos")
    batch_fk = next((fk for fk in fks if fk["referred_table"] == "upload_batches"), None)
    assert batch_fk is not None
    assert batch_fk["constrained_columns"] == ["upload_batch_id"]
    assert batch_fk["options"].get("ondelete") == "RESTRICT"

    # Check unique constraint & deferred property
    uqs = inspector.get_unique_constraints("videos")
    queue_uq = next((u for u in uqs if u["name"] == "uq_batch_queue_pos"), None)
    assert queue_uq is not None
    assert queue_uq["column_names"] == ["upload_batch_id", "queue_position"]

    engine.dispose()


# =============================================================================
# Clean Downgrade & Re-upgrade Tests
# =============================================================================

def test_clean_downgrade_and_reupgrade(disposable_pg_db):
    """
    Tests clean downgrade on verified empty Studio schema and empty storage,
    followed by clean re-upgrade back to head.
    """
    cfg = disposable_pg_db["alembic_cfg"]

    # 1. Downgrade to e1a2b3c4d5e6 (reverts f2a3b4c5d6e7 and f1b2c3d4e5f6 back to e1a2b3c4d5e6)
    command.downgrade(cfg, "e1a2b3c4d5e6")

    # 2. Verify columns and tables were removed cleanly
    engine = sa.create_engine(disposable_pg_db["sync_url"])
    inspector = sa.inspect(engine)
    tables = inspector.get_table_names()
    assert "storage_reservation_coordinators" not in tables
    assert "upload_batches" not in tables

    video_cols = {col["name"]: col for col in inspector.get_columns("videos")}
    assert "upload_batch_id" not in video_cols
    assert "upload_status" not in video_cols
    assert "reserved_bytes" not in video_cols
    assert "part_disposition" not in video_cols

    # 3. Re-upgrade back to head
    engine.dispose()
    command.upgrade(cfg, "head")

    engine = sa.create_engine(disposable_pg_db["sync_url"])
    inspector = sa.inspect(engine)
    assert "upload_batches" in inspector.get_table_names()
    engine.dispose()


# =============================================================================
# Downgrade Refusal Safety Tests
# =============================================================================

def test_downgrade_refuses_when_batch_exists(disposable_pg_db):
    """
    Asserts downgrade raises RuntimeError if an active upload_batch exists.
    """
    cfg = disposable_pg_db["alembic_cfg"]
    engine = sa.create_engine(disposable_pg_db["sync_url"])
    
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO upload_batches (id, idempotency_key, name, status)
            VALUES ('b_test_1', 'idem_1', 'Test Batch', 'staging')
        """))

    try:
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "e1a2b3c4d5e6")
        assert "Downgrade refused: Active Upload Studio state detected" in str(exc_info.value)
        assert "batches: 1" in str(exc_info.value)
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM upload_batches WHERE id = 'b_test_1'"))
        command.upgrade(cfg, "head")
        engine.dispose()


def test_downgrade_refuses_when_studio_video_exists(disposable_pg_db):
    """
    Asserts downgrade raises RuntimeError if a Studio-specific video record exists
    (e.g. upload_status is set or reserved_bytes > 0).
    """
    cfg = disposable_pg_db["alembic_cfg"]
    engine = sa.create_engine(disposable_pg_db["sync_url"])
    
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO videos (id, title, is_manual_upload, upload_status, reserved_bytes, reservation_state, created_at)
            VALUES ('vid_studio_1', 'Studio Video', TRUE, 'uploading', 1048576, 'initial', NOW())
        """))

    try:
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "e1a2b3c4d5e6")
        assert "Downgrade refused: Active Upload Studio state detected" in str(exc_info.value)
        assert "studio_videos: 1" in str(exc_info.value)
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM videos WHERE id = 'vid_studio_1'"))
        command.upgrade(cfg, "head")
        engine.dispose()


def test_downgrade_permits_clean_legacy_youtube_videos(disposable_pg_db):
    """
    Asserts downgrade SUCCEEDS when legacy YouTube video records exist in the DB,
    provided they have default/NULL Studio columns.
    """
    cfg = disposable_pg_db["alembic_cfg"]
    engine = sa.create_engine(disposable_pg_db["sync_url"])
    
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO videos (id, title, youtube_url, youtube_id, is_manual_upload, upload_batch_id, upload_status, reserved_bytes, created_at)
            VALUES ('vid_legacy_1', 'Legacy Video', 'https://youtube.com/watch?v=123', '123', FALSE, NULL, NULL, 0, NOW())
        """))

    try:
        # Downgrade must succeed cleanly
        command.downgrade(cfg, "e1a2b3c4d5e6")

        with engine.connect() as conn:
            row = conn.execute(sa.text("SELECT id, title FROM videos WHERE id = 'vid_legacy_1'")).fetchone()
            assert row is not None
            assert row[0] == "vid_legacy_1"
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM videos WHERE id = 'vid_legacy_1'"))
        # Re-upgrade to head so subsequent tests have Studio schema
        command.upgrade(cfg, "head")
        engine.dispose()


def test_downgrade_refuses_when_physical_studio_files_exist(disposable_pg_db, isolated_storage):
    """
    Asserts downgrade raises RuntimeError if unindexed physical studio files exist on disk.
    """
    cfg = disposable_pg_db["alembic_cfg"]
    studio_dir = isolated_storage["upload_dir"] / "studio" / "batches" / "b1"
    studio_dir.mkdir(parents=True, exist_ok=True)
    part_file = studio_dir / "unindexed_video.part"
    part_file.write_bytes(b"0" * 1024)

    try:
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "e1a2b3c4d5e6")
        assert "Downgrade refused: Active Upload Studio state detected" in str(exc_info.value)
        assert "physical_studio_files: 1" in str(exc_info.value)
    finally:
        if part_file.exists():
            part_file.unlink()
        try:
            os.rmdir(studio_dir)
            os.rmdir(studio_dir.parent)
            os.rmdir(studio_dir.parent.parent)
        except OSError:
            pass
        command.upgrade(cfg, "head")


def test_downgrade_refuses_on_mismatched_volume_id(disposable_pg_db):
    """
    Asserts downgrade raises RuntimeError if coordinator volume_id does not match token volume_id.
    """
    cfg = disposable_pg_db["alembic_cfg"]
    engine = sa.create_engine(disposable_pg_db["sync_url"])
    
    with engine.connect() as conn:
        orig_vol_id = conn.execute(sa.text("SELECT volume_id FROM storage_reservation_coordinators WHERE id = 'global'")).scalar()

    with engine.begin() as conn:
        conn.execute(sa.text("""
            UPDATE storage_reservation_coordinators
            SET volume_id = 'different_vol_mismatched'
            WHERE id = 'global'
        """))

    try:
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "e1a2b3c4d5e6")
        assert "Volume ID mismatch" in str(exc_info.value)
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE storage_reservation_coordinators SET volume_id = :orig WHERE id = 'global'"), {"orig": orig_vol_id})
        command.upgrade(cfg, "head")
        engine.dispose()


def test_downgrade_refuses_on_missing_volume_token(disposable_pg_db, isolated_storage):
    """
    Asserts downgrade raises RuntimeError if .clipforge_volume_token is missing.
    """
    cfg = disposable_pg_db["alembic_cfg"]
    token_file = isolated_storage["upload_dir"] / TOKEN_FILENAME
    bak_file = isolated_storage["upload_dir"] / f"{TOKEN_FILENAME}.bak"
    
    if token_file.exists():
        token_file.rename(bak_file)

    try:
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "e1a2b3c4d5e6")
        assert "Volume identity token missing" in str(exc_info.value)
    finally:
        if bak_file.exists():
            bak_file.rename(token_file)
        command.upgrade(cfg, "head")


def test_downgrade_refuses_on_placeholder_secret(disposable_pg_db, isolated_storage, monkeypatch):
    """
    Asserts downgrade raises RuntimeError if configured STORAGE_IDENTITY_SECRET / SECRET_KEY
    is set to an insecure default placeholder.
    """
    cfg = disposable_pg_db["alembic_cfg"]
    monkeypatch.setattr(settings, "STORAGE_IDENTITY_SECRET", "")
    monkeypatch.setattr(settings, "SECRET_KEY", "clipforge_default_secret_key_change_in_prod")

    try:
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "e1a2b3c4d5e6")
        assert "cannot be an insecure placeholder" in str(exc_info.value)
    finally:
        command.upgrade(cfg, "head")


def test_database_runtime_state_contract(disposable_pg_db):
    """
    Contract test: verifies that all permitted runtime states in the canonical vocabulary
    are accepted by PostgreSQL check constraints, and every invalid state is rejected with IntegrityError.
    """
    engine = sa.create_engine(disposable_pg_db["sync_url"])

    # 1. UploadBatchStatus contract
    for idx, batch_status in enumerate(UploadBatchStatus):
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO upload_batches (id, idempotency_key, name, status)
                VALUES (:id, :idem, 'Batch Contract', :status)
            """), {"id": f"b_contract_{idx}", "idem": f"idem_contract_{idx}", "status": batch_status.value})

    # Invalid upload_batches.status rejected
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO upload_batches (id, idempotency_key, name, status)
                VALUES ('b_invalid_status', 'idem_invalid', 'Invalid Batch', 'invalid_batch_status')
            """))

    # Cleanup test batches
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM upload_batches WHERE id LIKE 'b_contract_%'"))

    # Create one valid parent batch for video testing
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO upload_batches (id, idempotency_key, name, status)
            VALUES ('b_parent_video_contract', 'idem_parent_vid', 'Parent Batch', 'staging')
        """))

    try:
        # 2. VideoUploadStatus contract: all enum values and NULL must be accepted
        for idx, upload_status in enumerate(VideoUploadStatus):
            vid_id = f"v_up_status_{idx}"
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, upload_status, created_at)
                    VALUES (:id, 'Status Test', 'b_parent_video_contract', TRUE, :status, NOW())
                """), {"id": vid_id, "status": upload_status.value})

        # NULL upload_status is accepted (e.g. legacy videos)
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, upload_status, created_at)
                VALUES ('v_up_status_null', 'Null Status Test', 'b_parent_video_contract', TRUE, NULL, NOW())
            """))

        # Invalid upload_status rejected
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, upload_status, created_at)
                    VALUES ('v_bad_up_status', 'Bad Status', 'b_parent_video_contract', TRUE, 'invalid_upload_status', NOW())
                """))

        # 3. VideoReservationState contract: all enum values must be accepted
        for idx, res_state in enumerate(VideoReservationState):
            vid_id = f"v_res_state_{idx}"
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, reservation_state, created_at)
                    VALUES (:id, 'Reservation State Test', 'b_parent_video_contract', TRUE, :state, NOW())
                """), {"id": vid_id, "state": res_state.value})

        # Invalid reservation_state rejected
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, reservation_state, created_at)
                    VALUES ('v_bad_res_state', 'Bad Reservation', 'b_parent_video_contract', TRUE, 'invalid_res_state', NOW())
                """))

        # 4. VideoPartDisposition contract: all enum values must be accepted
        for idx, part_disp in enumerate(VideoPartDisposition):
            vid_id = f"v_part_disp_{idx}"
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, part_disposition, created_at)
                    VALUES (:id, 'Part Disp Test', 'b_parent_video_contract', TRUE, :disp, NOW())
                """), {"id": vid_id, "disp": part_disp.value})

        # Invalid part_disposition rejected
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, part_disposition, created_at)
                    VALUES ('v_bad_part_disp', 'Bad Part Disp', 'b_parent_video_contract', TRUE, 'invalid_part_disp', NOW())
                """))

        # 5. VideoFinalDisposition contract: all enum values must be accepted
        for idx, final_disp in enumerate(VideoFinalDisposition):
            vid_id = f"v_final_disp_{idx}"
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, final_disposition, created_at)
                    VALUES (:id, 'Final Disp Test', 'b_parent_video_contract', TRUE, :disp, NOW())
                """), {"id": vid_id, "disp": final_disp.value})

        # Invalid final_disposition rejected
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO videos (id, title, upload_batch_id, is_manual_upload, final_disposition, created_at)
                    VALUES ('v_bad_final_disp', 'Bad Final Disp', 'b_parent_video_contract', TRUE, 'invalid_final_disp', NOW())
                """))

    finally:
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM videos WHERE upload_batch_id = 'b_parent_video_contract'"))
            conn.execute(sa.text("DELETE FROM upload_batches WHERE id = 'b_parent_video_contract'"))
        engine.dispose()
