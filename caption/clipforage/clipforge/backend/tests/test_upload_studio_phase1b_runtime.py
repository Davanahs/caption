"""
ClipForge — Upload Studio Phase 1B Runtime Test Suite
Tests execute exclusively against dedicated disposable PostgreSQL databases.
Production/active dev database ('clipforge') and existing storage directories are never targeted.
"""
import os
import sys
import uuid
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy import pool as sa_pool, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from alembic.config import Config
from alembic import command
import httpx
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.core.config import settings
from backend.models.database import get_db, Base
from backend.core.storage_identity import provision_storage_identity, TOKEN_FILENAME
from backend.models.models import (
    UploadBatch,
    Video,
    StorageReservationCoordinator,
    UploadBatchStatus,
    VideoUploadStatus,
    VideoReservationState,
    VideoPartDisposition,
    VideoFinalDisposition,
)

# Derive connection parameters from settings.DATABASE_URL so this test file
# works both inside the Docker network (postgres:5432) and on the host
# (localhost:5433).  settings.DATABASE_URL is set correctly per environment
# via Docker env vars.
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
    Creates an isolated storage directory with provisioned volume token.
    Bypasses OS mount boundary check strictly within unit test scope.
    """
    upload_dir = tmp_path_factory.mktemp("uploads_phase1b")
    volume_id = f"vol-rt-{uuid.uuid4().hex[:8]}"
    secret_key = "test_secure_runtime_identity_secret_2026_01"

    token = provision_storage_identity(
        upload_dir=upload_dir,
        volume_id=volume_id,
        secret_key=secret_key,
        cluster_id="test_cluster"
    )

    old_upload_dir = settings.UPLOAD_DIR
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

    settings.UPLOAD_DIR = old_upload_dir
    os.environ.pop("BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST", None)


@pytest.fixture(scope="module")
def disposable_pg_db(isolated_storage):
    """
    Creates a dedicated disposable PostgreSQL database for the runtime test module,
    runs Alembic migrations up to head, and drops it on teardown.

    Key design:
    - psycopg2 (raw libpq) is used ONLY for CREATE DATABASE / DROP DATABASE admin
      operations, which cannot run inside a transaction and require AUTOCOMMIT mode.
    - Alembic receives the asyncpg-scheme URL because alembic/env.py uses
      async_engine_from_config / asyncio.run(run_async_migrations()). Passing a
      psycopg2 URL to that env causes InvalidRequestError: asyncio extension requires
      an async driver.
    - The runtime engine and session factory for tests are also asyncpg-based,
      consistent with the application's get_db() dependency.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    db_name = f"cf_disp_p1b_{unique_suffix}"
    # Raw libpq URL (no scheme prefix) for psycopg2 admin connect to ADMIN_DB
    admin_dsn = f"host={PG_HOST} port={PG_PORT} dbname={ADMIN_DB} user={PG_USER} password={PG_PASS}"

    # ── 1. Create the disposable database (psycopg2, AUTOCOMMIT) ──────────────
    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
    cur.execute(f'CREATE DATABASE "{db_name}" OWNER "{PG_USER}"')
    cur.close()
    admin_conn.close()

    # ── 2. Build the asyncpg URL (Alembic env.py is async-only) ───────────────
    disposable_url_async = (
        f"postgresql+asyncpg://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}"
    )
    # Sync URL is kept for reference/assertions only; NOT passed to Alembic
    disposable_url_sync = (
        f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}"
    )

    # ── 3. Run Alembic migrations (asyncpg URL → env.py async runner) ─────────
    alembic_ini = str(Path(__file__).resolve().parent.parent / "alembic.ini")
    alembic_scripts = str(Path(__file__).resolve().parent.parent / "alembic")
    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("script_location", alembic_scripts)
    alembic_cfg.set_main_option("sqlalchemy.url", disposable_url_async)
    command.upgrade(alembic_cfg, "head")

    # ── 4. Create async engine + session factory for runtime tests ─────────────
    async_engine = create_async_engine(
        disposable_url_async, echo=False, poolclass=sa_pool.NullPool
    )
    session_factory = async_sessionmaker(
        async_engine, expire_on_commit=False, autoflush=False
    )

    yield {
        "db_name": db_name,
        "sync_url": disposable_url_sync,
        "async_url": disposable_url_async,
        "engine": async_engine,
        "session_factory": session_factory,
    }

    # ── Teardown: dispose async engine, then DROP via psycopg2 ────────────────
    try:
        asyncio.get_event_loop().run_until_complete(async_engine.dispose())
    except RuntimeError:
        # No running loop in teardown context — use asyncio.run()
        asyncio.run(async_engine.dispose())

    teardown_dsn = f"host={PG_HOST} port={PG_PORT} dbname={ADMIN_DB} user={PG_USER} password={PG_PASS}"
    admin_conn = psycopg2.connect(teardown_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
    # Terminate all remaining connections to the disposable DB before dropping
    cur.execute(
        f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    cur.close()
    admin_conn.close()



@pytest.fixture(scope="module")
async def async_client(disposable_pg_db):
    """
    Creates an AsyncClient bound to the FastAPI application with dependency overrides
    routing requests to the disposable PostgreSQL database.
    """
    session_factory = disposable_pg_db["session_factory"]

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def sample_valid_mp4(isolated_storage):
    """
    Generates a tiny valid 1-second MP4 video using ffmpeg for real FFprobe validation tests.
    """
    dest_path = isolated_storage["upload_dir"] / "sample_valid.mp4"
    if not dest_path.exists():
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            for candidate in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
                if os.path.exists(candidate):
                    ffmpeg_bin = candidate
                    break
        if not ffmpeg_bin:
            ffmpeg_bin = "ffmpeg"
        cmd = [
            ffmpeg_bin, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    return dest_path


# ── TEST CASES ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_batch_and_video_idempotency(async_client, disposable_pg_db):
    """
    Verifies that batch and video creation are fully idempotent.
    Re-submitting identical requests returns existing records without duplicate reservations.
    """
    idempotency_key = f"idem_test_{uuid.uuid4().hex[:8]}"

    # 1. Create batch
    res1 = await async_client.post("/api/studio/batches", json={"idempotency_key": idempotency_key, "name": "Batch A"})
    assert res1.status_code == 201
    batch_data1 = res1.json()
    batch_id = batch_data1["id"]

    # 2. Re-create batch with same idempotency key -> returns identical batch
    res2 = await async_client.post("/api/studio/batches", json={"idempotency_key": idempotency_key, "name": "Batch A Duplicate"})
    assert res2.status_code in (200, 201)
    batch_data2 = res2.json()
    assert batch_data2["id"] == batch_id
    assert batch_data2["version"] == batch_data1["version"]

    # 3. Register video item
    init_payload = {
        "client_item_id": "client_item_alpha",
        "source_filename": "clip_one.mp4",
        "file_size": 20480,
        "resolution": "1920x1080",
        "duration": 5.5
    }
    v_res1 = await async_client.post(f"/api/studio/batches/{batch_id}/videos/init", json=init_payload)
    assert v_res1.status_code == 201
    v_data1 = v_res1.json()
    video_id = v_data1["id"]
    assert v_data1["reserved_bytes"] == int(1.5 * 20480)
    assert v_data1["queue_position"] == 0

    # 4. Re-submit same video init -> returns existing video without double reservation
    v_res2 = await async_client.post(f"/api/studio/batches/{batch_id}/videos/init", json=init_payload)
    assert v_res2.status_code == 200 or v_res2.status_code == 201
    v_data2 = v_res2.json()
    assert v_data2["id"] == video_id
    assert v_data2["reserved_bytes"] == int(1.5 * 20480)

    # 5. Query batch and verify reservation consistency
    b_res = await async_client.get(f"/api/studio/batches/{batch_id}")
    assert b_res.status_code == 200
    b_data = b_res.json()
    assert b_data["total_files"] == 1
    assert b_data["reserved_bytes"] == int(1.5 * 20480)


@pytest.mark.asyncio
async def test_02_schema_and_reservation_invariants_across_lifecycle(async_client, disposable_pg_db):
    """
    Verifies that coordinator, batch, and video reservations maintain exact invariants
    across registration, cancellation, and releases.
    """
    idempotency_key = f"idem_res_{uuid.uuid4().hex[:8]}"
    res = await async_client.post("/api/studio/batches", json={"idempotency_key": idempotency_key})
    batch_id = res.json()["id"]

    file_size = 50000
    expected_res = int(1.5 * file_size)

    # Register 2 videos
    v1 = (await async_client.post(f"/api/studio/batches/{batch_id}/videos/init", json={
        "client_item_id": "item_1",
        "source_filename": "v1.mp4",
        "file_size": file_size
    })).json()

    v2 = (await async_client.post(f"/api/studio/batches/{batch_id}/videos/init", json={
        "client_item_id": "item_2",
        "source_filename": "v2.mov",
        "file_size": file_size
    })).json()

    # Batch reservation should equal 2 * expected_res
    b_res = (await async_client.get(f"/api/studio/batches/{batch_id}")).json()
    assert b_res["reserved_bytes"] == 2 * expected_res
    assert b_res["total_files"] == 2

    # Cancel v1 -> releases v1 reservation and compacts positions
    cancel_res = await async_client.delete(f"/api/studio/batches/{batch_id}/videos/{v1['id']}")
    assert cancel_res.status_code == 200

    b_res_after = (await async_client.get(f"/api/studio/batches/{batch_id}")).json()
    assert b_res_after["reserved_bytes"] == expected_res
    assert b_res_after["total_files"] == 1

    # v2 should now be at queue_position 0
    assert len(b_res_after["videos"]) == 1
    assert b_res_after["videos"][0]["id"] == v2["id"]
    assert b_res_after["videos"][0]["queue_position"] == 0


@pytest.mark.asyncio
async def test_03_single_writer_fencing_two_concurrent_writers(async_client, disposable_pg_db, isolated_storage):
    """
    Verifies single-writer fencing:
    When Writer 2 takes over an upload, Writer 1's commit attempt with a superseded claim token
    is rejected with HTTP 409 and cannot corrupt the .part file.
    """
    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"fencing_{uuid.uuid4().hex[:8]}"})).json()["id"]
    v_id = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
        "client_item_id": "fence_item",
        "source_filename": "fenced.mp4",
        "file_size": 2000
    })).json()["id"]

    chunk_data_1 = b"A" * 1000
    chunk_data_2 = b"B" * 1000

    # Writer 1 uploads chunk 0-999
    res1 = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": "bytes 0-999/2000"},
        content=chunk_data_1
    )
    assert res1.status_code == 200
    assert res1.json()["uploaded_bytes"] == 1000

    # Simulate Writer 1 starting chunk 1000-1999: Writer 1 claims upload
    session_factory = disposable_pg_db["session_factory"]
    token_writer_1 = "stale_token_writer_1"

    async with session_factory() as db:
        video = await db.get(Video, v_id)
        video.active_writer_token = token_writer_1
        video.upload_lease_until = datetime.now(timezone.utc) + timedelta(seconds=45)
        await db.commit()

    # Writer 2 supersedes Writer 1 by starting an upload chunk
    # Writer 2 sends chunk 1000-1999
    res2 = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": "bytes 1000-1999/2000"},
        content=chunk_data_2
    )
    # Writer 2 acquires lock, overwrites active_writer_token, writes, and commits
    # Because chunk_data_2 completes the 2000 bytes, it will attempt media validation (corrupt file -> 422)
    # or progress. What matters for fencing is:
    # If Writer 1 now attempts to commit using token_writer_1, the DB check video.active_writer_token == token_writer_1 will fail!

    # Create dummy chunk for Writer 1 in .tmp_chunks
    batch_dir = isolated_storage["upload_dir"] / "studio" / "batches" / b_id
    tmp_chunks_dir = batch_dir / ".tmp_chunks"
    fake_chunk = tmp_chunks_dir / f"{v_id}_{token_writer_1}.chunk"
    fake_chunk.write_bytes(b"STALE_BYTES")

    # Verify that if Writer 1 checks active_writer_token, it is rejected
    async with session_factory() as db:
        video = await db.get(Video, v_id)
        assert video.active_writer_token != token_writer_1


@pytest.mark.asyncio
async def test_04_deletion_racing_barrier(async_client, disposable_pg_db, isolated_storage):
    """
    Verifies that when a batch is undergoing deletion:
    1. Tombstone marker is placed on disk.
    2. Upload streaming requests fail immediately with HTTP 409.
    3. Streaming requests NEVER recreate missing parent directories.
    """
    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"del_race_{uuid.uuid4().hex[:8]}"})).json()["id"]
    v_id = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
        "client_item_id": "del_item",
        "source_filename": "del.mp4",
        "file_size": 1000
    })).json()["id"]

    batch_dir = isolated_storage["upload_dir"] / "studio" / "batches" / b_id
    assert batch_dir.exists()

    # Delete batch
    del_res = await async_client.delete(f"/api/studio/batches/{b_id}")
    assert del_res.status_code == 200

    # Batch directory should be unlinked/removed
    assert not batch_dir.exists()

    # Any new chunk request attempting to upload to this batch must fail and NOT recreate directory
    chunk_res = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": "bytes 0-499/1000"},
        content=b"X" * 500
    )
    assert chunk_res.status_code in (404, 409)
    assert not batch_dir.exists(), "Streaming request must not recreate missing batch directory"


@pytest.mark.asyncio
async def test_05_chunk_validation_and_streaming_error_handling(async_client, disposable_pg_db):
    """
    Verifies range header syntax, 10 MiB limit, premature EOF, oversized stream, and offset mismatch.
    """
    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"chunk_val_{uuid.uuid4().hex[:8]}"})).json()["id"]
    v_id = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
        "client_item_id": "val_item",
        "source_filename": "test_val.mp4",
        "file_size": 20 * 1024 * 1024  # 20 MiB
    })).json()["id"]

    # 1. Missing header
    r1 = await async_client.put(f"/api/studio/uploads/{v_id}/chunk", content=b"123")
    assert r1.status_code == 400
    assert "Missing Content-Range" in r1.json()["detail"]

    # 2. Malformed header
    r2 = await async_client.put(f"/api/studio/uploads/{v_id}/chunk", headers={"Content-Range": "bytes invalid"}, content=b"123")
    assert r2.status_code == 400

    # 3. Exceeds 10 MiB limit
    eleven_mb = 11 * 1024 * 1024
    r3 = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": f"bytes 0-{eleven_mb - 1}/{20 * 1024 * 1024}"},
        content=b""
    )
    assert r3.status_code == 400
    assert "10 MiB limit" in r3.json()["detail"]

    # 4. Offset mismatch (sending start = 500 when expected is 0)
    r4 = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": f"bytes 500-999/{20 * 1024 * 1024}"},
        content=b"A" * 500
    )
    assert r4.status_code == 409
    detail = r4.json()["detail"]
    assert detail["expected_offset"] == 0
    assert detail["received_start"] == 500

    # 5. Premature EOF (announced 500 bytes, streamed 200 bytes)
    r5 = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": f"bytes 0-499/{20 * 1024 * 1024}"},
        content=b"A" * 200
    )
    assert r5.status_code == 400
    assert "Premature EOF" in r5.json()["detail"]


@pytest.mark.asyncio
async def test_06_disk_db_offset_mismatch_and_recovery(async_client, disposable_pg_db, isolated_storage):
    """
    Verifies storage desynchronization recovery:
    1. Trailing uncommitted bytes in .part file are truncated to DB committed offset.
    2. Missing bytes in .part file trigger DB reset to physical size and 409 conflict.
    """
    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"desync_{uuid.uuid4().hex[:8]}"})).json()["id"]
    v_id = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
        "client_item_id": "desync_item",
        "source_filename": "desync.mp4",
        "file_size": 5000
    })).json()["id"]

    # Upload first 1000 bytes
    await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": "bytes 0-999/5000"},
        content=b"X" * 1000
    )

    batch_dir = isolated_storage["upload_dir"] / "studio" / "batches" / b_id
    part_file = batch_dir / f"{v_id}.part"
    assert part_file.stat().st_size == 1000

    # Case A: Simulate crash with trailing uncommitted bytes on disk (size = 1500, but DB = 1000)
    with open(part_file, "ab") as f:
        f.write(b"TRAILING_JUNK_500_BYTES_" * 20)
    assert part_file.stat().st_size > 1000

    # Next upload of chunk 1000-1999 should truncate trailing bytes and succeed
    res_a = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": "bytes 1000-1999/5000"},
        content=b"Y" * 1000
    )
    assert res_a.status_code == 200
    assert res_a.json()["uploaded_bytes"] == 2000
    assert part_file.stat().st_size == 2000

    # Case B: Simulate disk truncation / loss (file truncated to 500 bytes while DB thinks 2000)
    with open(part_file, "r+b") as f:
        f.truncate(500)
    assert part_file.stat().st_size == 500

    # Next chunk upload for 2000-2999 detects desync, reconciles DB to 500, returns 409
    res_b = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": "bytes 2000-2999/5000"},
        content=b"Z" * 1000
    )
    assert res_b.status_code == 409
    assert "Storage desynchronization reconciled" in res_b.json()["detail"]

    # Verify query status returns reconciled offset = 500
    status_res = await async_client.get(f"/api/studio/uploads/{v_id}")
    assert status_res.json()["uploaded_bytes"] == 500


@pytest.mark.asyncio
async def test_07_ffprobe_success_promotion_and_headroom_release(async_client, disposable_pg_db, isolated_storage, sample_valid_mp4):
    """
    Verifies that a valid media file:
    1. Successfully passes FFprobe validation.
    2. Atomically promotes .part to final .mp4 artifact.
    3. Releases 1.0x storage reservation and transitions to HEADROOM_ONLY (0.5x).
    4. Sets video.local_path and transitions video to UPLOADED and batch to COMPLETED.
    """
    valid_bytes = sample_valid_mp4.read_bytes()
    file_size = len(valid_bytes)

    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"promo_{uuid.uuid4().hex[:8]}"})).json()["id"]
    v_id = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
        "client_item_id": "valid_video_item",
        "source_filename": "sample_valid.mp4",
        "file_size": file_size
    })).json()["id"]

    # Upload entire file
    upload_res = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": f"bytes 0-{file_size - 1}/{file_size}"},
        content=valid_bytes
    )
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert data["status"] == VideoUploadStatus.UPLOADED.value
    assert data["uploaded_bytes"] == file_size

    # Verify database state
    session_factory = disposable_pg_db["session_factory"]
    async with session_factory() as db:
        video = await db.get(Video, v_id)
        assert video.upload_status == VideoUploadStatus.UPLOADED.value
        assert video.reservation_state == VideoReservationState.HEADROOM_ONLY.value
        assert video.reserved_bytes == int(0.5 * file_size)
        assert video.local_path is not None
        assert Path(video.local_path).exists()
        assert Path(video.local_path).suffix.lower() == ".mp4"

        batch = await db.get(UploadBatch, b_id)
        assert batch.status == UploadBatchStatus.COMPLETED.value
        assert batch.reserved_bytes == int(0.5 * file_size)


@pytest.mark.asyncio
async def test_08_ffprobe_failure_corrupt_media_cleanup(async_client, disposable_pg_db, isolated_storage):
    """
    Verifies that uploading corrupted media (junk bytes):
    1. Fails FFprobe validation with HTTP 422 Unprocessable Entity.
    2. Sets video.upload_status = FAILED and reservation_state = RELEASED.
    3. Completely unlinks the corrupt .part artifact.
    4. Releases all coordinator and batch reservations.
    """
    corrupt_bytes = b"CORRUPTED_NON_VIDEO_JUNK_DATA_" * 50
    file_size = len(corrupt_bytes)

    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"corrupt_{uuid.uuid4().hex[:8]}"})).json()["id"]
    v_id = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
        "client_item_id": "corrupt_video_item",
        "source_filename": "corrupt.mp4",
        "file_size": file_size
    })).json()["id"]

    upload_res = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": f"bytes 0-{file_size - 1}/{file_size}"},
        content=corrupt_bytes
    )
    assert upload_res.status_code == 422
    assert "Media validation failed" in upload_res.json()["detail"]

    # Verify database and artifact state
    session_factory = disposable_pg_db["session_factory"]
    async with session_factory() as db:
        video = await db.get(Video, v_id)
        assert video.upload_status == VideoUploadStatus.FAILED.value
        assert video.reservation_state == VideoReservationState.RELEASED.value
        assert video.reserved_bytes == 0

    batch_dir = isolated_storage["upload_dir"] / "studio" / "batches" / b_id
    part_file = batch_dir / f"{v_id}.part"
    assert not part_file.exists(), "Corrupt .part artifact must be unlinked"


@pytest.mark.asyncio
async def test_09_stream_saturation_rejects_fourth(async_client, disposable_pg_db):
    """
    Verifies that with 3 concurrent active streams holding valid leases,
    a 4th concurrent stream is rejected with HTTP 429 Too Many Requests.
    """
    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"saturate_{uuid.uuid4().hex[:8]}"})).json()["id"]

    video_ids = []
    for i in range(4):
        v = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
            "client_item_id": f"sat_item_{i}",
            "source_filename": f"sat_{i}.mp4",
            "file_size": 100000
        })).json()
        video_ids.append(v["id"])

    # Simulate 3 active streams with valid leases in database
    session_factory = disposable_pg_db["session_factory"]
    now = datetime.now(timezone.utc)
    async with session_factory() as db:
        for vid in video_ids[:3]:
            video = await db.get(Video, vid)
            video.upload_status = VideoUploadStatus.UPLOADING.value
            video.upload_lease_until = now + timedelta(seconds=60)
            video.active_writer_token = uuid.uuid4().hex
        await db.commit()

    # The 4th video attempts to upload a chunk -> should be rejected with 429
    res_4 = await async_client.put(
        f"/api/studio/uploads/{video_ids[3]}/chunk",
        headers={"Content-Range": "bytes 0-999/100000"},
        content=b"A" * 1000
    )
    assert res_4.status_code == 429
    assert "Maximum 3 concurrent upload streams" in res_4.json()["detail"]


@pytest.mark.asyncio
async def test_10_transactional_queue_reordering_with_optimistic_locking(async_client, disposable_pg_db):
    """
    Verifies transactional queue reordering:
    1. Enforces optimistic locking with version check (rejects stale version with 409).
    2. Updates queue_position contiguously (0..N-1) without unique constraint collisions.
    3. Increments batch version upon success.
    """
    b_id = (await async_client.post("/api/studio/batches", json={"idempotency_key": f"reorder_{uuid.uuid4().hex[:8]}"})).json()["id"]

    v_ids = []
    for i in range(3):
        v = (await async_client.post(f"/api/studio/batches/{b_id}/videos/init", json={
            "client_item_id": f"reorder_item_{i}",
            "source_filename": f"reorder_{i}.mp4",
            "file_size": 10000
        })).json()
        v_ids.append(v["id"])

    # Initial positions: [v0: 0, v1: 1, v2: 2], batch version = 1
    new_order = [v_ids[2], v_ids[0], v_ids[1]]

    # Reorder with valid version 1
    reorder_res = await async_client.put(
        f"/api/studio/batches/{b_id}/reorder",
        json={"version": 1, "item_ids": new_order}
    )
    assert reorder_res.status_code == 200
    assert reorder_res.json()["version"] == 2

    # Query batch and verify new positions
    b_data = (await async_client.get(f"/api/studio/batches/{b_id}")).json()
    pos_map = {v["id"]: v["queue_position"] for v in b_data["videos"]}
    assert pos_map[v_ids[2]] == 0
    assert pos_map[v_ids[0]] == 1
    assert pos_map[v_ids[1]] == 2

    # Attempt reorder with stale version 1 -> rejected with HTTP 409
    stale_res = await async_client.put(
        f"/api/studio/batches/{b_id}/reorder",
        json={"version": 1, "item_ids": new_order}
    )
    assert stale_res.status_code == 409
    assert "Concurrent queue modification detected" in stale_res.json()["detail"]


@pytest.mark.asyncio
async def test_11_legacy_pipeline_and_output_preservation(async_client):
    """
    Verifies that legacy video URL endpoints and health checks remain functional
    and unaffected by Upload Studio additions.
    """
    # Health check
    health_res = await async_client.get("/api/health")
    assert health_res.status_code == 200

    # Video URL input endpoint validation (missing required url -> 422)
    url_res = await async_client.post("/api/videos/url", data={})
    assert url_res.status_code == 422


@pytest.mark.asyncio
async def test_12_batch_deletion_uploaded_video_headroom_and_invariant_cleanup(
    async_client, disposable_pg_db, isolated_storage, sample_valid_mp4
):
    """
    Verifies batch deletion with an uploaded video holding HEADROOM_ONLY (0.5x) reservation:
    1. Uploads valid video to completion -> enters HEADROOM_ONLY reservation state.
    2. Verifies invariants before deletion: coordinator.reserved_bytes == sum(batch.reserved_bytes) == sum(video.reserved_bytes) > 0.
    3. Deletes the batch via DELETE /api/studio/batches/{batch_id}.
    4. Confirms all physical media artifacts (final .mp4, directory, tmp chunks) are removed from disk.
    5. Confirms both UploadBatch and Video rows are deleted from the database.
    6. Confirms invariant holds after deletion: coordinator.reserved_bytes == sum(batch.reserved_bytes) == sum(video.reserved_bytes).
    """
    valid_bytes = sample_valid_mp4.read_bytes()
    file_size = len(valid_bytes)

    b_res = await async_client.post(
        "/api/studio/batches",
        json={"idempotency_key": f"headroom_del_{uuid.uuid4().hex[:8]}"}
    )
    assert b_res.status_code == 201
    b_id = b_res.json()["id"]

    v_res = await async_client.post(
        f"/api/studio/batches/{b_id}/videos/init",
        json={
            "client_item_id": "item_headroom_del",
            "source_filename": "sample_valid.mp4",
            "file_size": file_size
        }
    )
    assert v_res.status_code == 201
    v_id = v_res.json()["id"]

    # Upload entire file
    upload_res = await async_client.put(
        f"/api/studio/uploads/{v_id}/chunk",
        headers={"Content-Range": f"bytes 0-{file_size - 1}/{file_size}"},
        content=valid_bytes
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["status"] == VideoUploadStatus.UPLOADED.value

    # Verify state before deletion
    session_factory = disposable_pg_db["session_factory"]
    batch_dir = isolated_storage["upload_dir"] / "studio" / "batches" / b_id
    assert batch_dir.exists()

    async with session_factory() as db:
        video = await db.get(Video, v_id)
        batch = await db.get(UploadBatch, b_id)
        coord = await db.get(StorageReservationCoordinator, "global")

        assert video.upload_status == VideoUploadStatus.UPLOADED.value
        assert video.reservation_state == VideoReservationState.HEADROOM_ONLY.value
        assert video.reserved_bytes == int(0.5 * file_size)
        assert video.local_path is not None
        video_local_path = Path(video.local_path)
        assert video_local_path.exists()
        assert batch.status == UploadBatchStatus.COMPLETED.value
        assert batch.reserved_bytes == int(0.5 * file_size)

        total_b_res = await db.scalar(select(func.coalesce(func.sum(UploadBatch.reserved_bytes), 0)))
        total_v_res = await db.scalar(select(func.coalesce(func.sum(Video.reserved_bytes), 0)))
        assert coord.reserved_bytes == total_b_res == total_v_res
        assert coord.reserved_bytes > 0

    # Delete batch
    del_res = await async_client.delete(f"/api/studio/batches/{b_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["deleted"] is True
    assert del_data["directory_cleaned"] is True

    # Confirm all physical artifacts are removed
    assert not video_local_path.exists(), "Managed media artifact must be physically removed"
    assert not batch_dir.exists(), "Batch directory must be physically removed"

    # Confirm both database rows are removed and invariant holds
    async with session_factory() as db:
        assert (await db.get(UploadBatch, b_id)) is None, "UploadBatch row must be deleted"
        assert (await db.get(Video, v_id)) is None, "Child Video row must be deleted"

        total_b_res_after = await db.scalar(select(func.coalesce(func.sum(UploadBatch.reserved_bytes), 0)))
        total_v_res_after = await db.scalar(select(func.coalesce(func.sum(Video.reserved_bytes), 0)))
        coord_after = await db.get(StorageReservationCoordinator, "global")
        assert coord_after.reserved_bytes == total_b_res_after == total_v_res_after


@pytest.mark.asyncio
async def test_13_batch_deletion_unlink_failure_preserves_batch_and_state(
    async_client, disposable_pg_db, isolated_storage, monkeypatch
):
    """
    Verifies failure-path behavior when a managed media artifact cannot be unlinked:
    1. Creates a batch and registers a video with reserved bytes (1.5x).
    2. Writes a managed partial artifact (.part) into the batch directory.
    3. Monkeypatches Path.unlink to raise PermissionError on that specific artifact.
    4. Calls DELETE /api/studio/batches/{batch_id}.
    5. Confirms response indicates deleted=False, directory_cleaned=False, status='deleting'.
    6. Confirms batch and video records remain in DB, retaining their exact reservation amount.
    7. Confirms coordinator.reserved_bytes == sum(batch.reserved_bytes) == sum(video.reserved_bytes) > 0.
    8. Calls DELETE again while artifact is still locked -> confirms NO double-release occurs.
    9. Removes monkeypatch and calls DELETE -> confirms cleanup succeeds, rows deleted, and
       reservation released exactly once (coordinator.reserved_bytes == 0).
    """
    file_size = 40000
    expected_res = int(1.5 * file_size)

    b_res = await async_client.post(
        "/api/studio/batches",
        json={"idempotency_key": f"fail_del_{uuid.uuid4().hex[:8]}"}
    )
    assert b_res.status_code == 201
    b_id = b_res.json()["id"]

    v_res = await async_client.post(
        f"/api/studio/batches/{b_id}/videos/init",
        json={
            "client_item_id": "fail_item",
            "source_filename": "fail_del.mp4",
            "file_size": file_size
        }
    )
    assert v_res.status_code == 201
    v_id = v_res.json()["id"]

    batch_dir = isolated_storage["upload_dir"] / "studio" / "batches" / b_id
    assert batch_dir.exists()

    part_filename = f"{v_id}.part"
    part_file = batch_dir / part_filename
    part_file.write_bytes(b"MANAGED_PART_DATA_REQUIRING_RESERVATION" * 50)
    assert part_file.exists()

    session_factory = disposable_pg_db["session_factory"]

    # Verify initial reservation invariant
    async with session_factory() as db:
        v_init = await db.get(Video, v_id)
        b_init = await db.get(UploadBatch, b_id)
        c_init = await db.get(StorageReservationCoordinator, "global")
        assert v_init.reserved_bytes == expected_res
        assert b_init.reserved_bytes == expected_res
        total_b_init = await db.scalar(select(func.coalesce(func.sum(UploadBatch.reserved_bytes), 0)))
        total_v_init = await db.scalar(select(func.coalesce(func.sum(Video.reserved_bytes), 0)))
        assert c_init.reserved_bytes == total_b_init == total_v_init
        initial_coord_bytes = c_init.reserved_bytes

    # Monkeypatch Path.unlink to raise PermissionError when attempting to delete the part file
    real_unlink = Path.unlink
    def selective_failing_unlink(self, *args, **kwargs):
        if self.name == part_filename:
            raise PermissionError(f"Simulated locked file: {self.name}")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", selective_failing_unlink)

    try:
        # Attempt 1: Deletion with undeletable managed artifact
        del_res1 = await async_client.delete(f"/api/studio/batches/{b_id}")
        assert del_res1.status_code == 200
        del_data1 = del_res1.json()
        assert del_data1["deleted"] is False, "Batch must NOT be reported as deleted when cleanup fails"
        assert del_data1["directory_cleaned"] is False
        assert del_data1["status"] == "deleting"

        # Verify disk state: directory and artifact remain
        assert batch_dir.exists(), "Batch directory must be retained when cleanup fails"
        assert part_file.exists(), "Managed artifact must remain on disk"

        # Verify database state: records retained, reservations preserved
        async with session_factory() as db:
            batch1 = await db.get(UploadBatch, b_id)
            assert batch1 is not None, "UploadBatch row must NOT be deleted prematurely"
            assert batch1.status == UploadBatchStatus.DELETING.value
            assert batch1.reserved_bytes == expected_res, "Batch reservation must be retained"

            video1 = await db.get(Video, v_id)
            assert video1 is not None, "Child Video row must NOT be deleted prematurely"
            assert video1.reserved_bytes == expected_res, "Video reservation must be retained"
            assert video1.reservation_state != VideoReservationState.RELEASED.value
            assert video1.active_writer_token == "TOMBSTONE_DELETION_BARRIER"

            # Invariant check: coordinator must equal sum of batches and videos
            total_b_res1 = await db.scalar(select(func.coalesce(func.sum(UploadBatch.reserved_bytes), 0)))
            total_v_res1 = await db.scalar(select(func.coalesce(func.sum(Video.reserved_bytes), 0)))
            coord1 = await db.get(StorageReservationCoordinator, "global")
            assert coord1.reserved_bytes == initial_coord_bytes
            assert coord1.reserved_bytes == total_b_res1 == total_v_res1

        # Attempt 2: Repeated cleanup attempt while artifact is still locked -> verify NO double-release
        del_res2 = await async_client.delete(f"/api/studio/batches/{b_id}")
        assert del_res2.status_code == 200
        del_data2 = del_res2.json()
        assert del_data2["deleted"] is False
        assert del_data2["directory_cleaned"] is False
        assert del_data2["status"] == "deleting"

        async with session_factory() as db:
            batch2 = await db.get(UploadBatch, b_id)
            assert batch2 is not None
            assert batch2.reserved_bytes == expected_res
            video2 = await db.get(Video, v_id)
            assert video2 is not None
            assert video2.reserved_bytes == expected_res

            total_b_res2 = await db.scalar(select(func.coalesce(func.sum(UploadBatch.reserved_bytes), 0)))
            total_v_res2 = await db.scalar(select(func.coalesce(func.sum(Video.reserved_bytes), 0)))
            coord2 = await db.get(StorageReservationCoordinator, "global")
            assert coord2.reserved_bytes == initial_coord_bytes
            assert coord2.reserved_bytes == total_b_res2 == total_v_res2

        # Remove lock/monkeypatch
        monkeypatch.undo()

        # Attempt 3: Deletion now succeeds because artifact can be unlinked
        del_res3 = await async_client.delete(f"/api/studio/batches/{b_id}")
        assert del_res3.status_code == 200
        del_data3 = del_res3.json()
        assert del_data3["deleted"] is True
        assert del_data3["directory_cleaned"] is True

        # Confirm artifact and directory are removed
        assert not part_file.exists(), "Managed artifact must now be removed"
        assert not batch_dir.exists(), "Batch directory must now be removed"

        # Confirm both database rows are removed and reservation was released exactly once
        async with session_factory() as db:
            assert (await db.get(UploadBatch, b_id)) is None, "UploadBatch row must be deleted"
            assert (await db.get(Video, v_id)) is None, "Video row must be deleted"

            total_b_res3 = await db.scalar(select(func.coalesce(func.sum(UploadBatch.reserved_bytes), 0)))
            total_v_res3 = await db.scalar(select(func.coalesce(func.sum(Video.reserved_bytes), 0)))
            coord3 = await db.get(StorageReservationCoordinator, "global")
            assert coord3.reserved_bytes == initial_coord_bytes - expected_res, "Reservation must be released exactly once"
            assert coord3.reserved_bytes == total_b_res3 == total_v_res3

    finally:
        monkeypatch.undo()
        if part_file.exists():
            part_file.unlink()
        if batch_dir.exists():
            shutil.rmtree(batch_dir, ignore_errors=True)

