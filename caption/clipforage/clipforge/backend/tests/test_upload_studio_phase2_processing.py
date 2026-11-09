"""
ClipForge — Upload Studio Phase 2 Sequential Batch Processing Test Suite
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
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy import create_engine, pool as sa_pool, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from alembic.config import Config
from alembic import command
import httpx
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.core.config import settings
from backend.models.database import get_db, Base
from backend.core.storage_identity import provision_storage_identity
from backend.models.models import (
    UploadBatch,
    Video,
    Job,
    JobStatus,
    StorageReservationCoordinator,
    UploadBatchStatus,
    VideoUploadStatus,
    VideoProcessingStatus,
    VideoReservationState,
)
from backend.tasks.studio_tasks import (
    process_studio_batch_sequential_task,
    on_studio_video_finished_task,
    recover_stale_studio_batches_task,
)

from urllib.parse import urlparse as _urlparse
_parsed = _urlparse(settings.DATABASE_URL)
PG_HOST = _parsed.hostname
PG_PORT = _parsed.port or 5432
PG_USER = _parsed.username
PG_PASS = _parsed.password
ADMIN_DB = _parsed.path.lstrip("/")


@pytest.fixture(scope="module")
def isolated_storage(tmp_path_factory):
    upload_dir = tmp_path_factory.mktemp("uploads_phase2")
    volume_id = f"vol-p2-{uuid.uuid4().hex[:8]}"
    secret_key = "test_secure_runtime_identity_secret_2026_02"

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
    unique_suffix = uuid.uuid4().hex[:8]
    db_name = f"cf_disp_p2_{unique_suffix}"
    admin_dsn = f"host={PG_HOST} port={PG_PORT} dbname={ADMIN_DB} user={PG_USER} password={PG_PASS}"

    # 1. Create disposable database
    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
    cur.execute(f'CREATE DATABASE "{db_name}" OWNER "{PG_USER}"')
    cur.close()
    admin_conn.close()

    # 2. URLs
    disposable_url_async = f"postgresql+asyncpg://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}"
    disposable_url_sync = f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{db_name}"

    # 3. Alembic migrations up to head (f2a3b4c5d6e7)
    alembic_ini = str(Path(__file__).resolve().parent.parent / "alembic.ini")
    alembic_scripts = str(Path(__file__).resolve().parent.parent / "alembic")
    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("script_location", alembic_scripts)
    alembic_cfg.set_main_option("sqlalchemy.url", disposable_url_async)
    command.upgrade(alembic_cfg, "head")

    # 4. Async engine + sessionmaker for FastAPI
    async_engine = create_async_engine(disposable_url_async, echo=False, poolclass=sa_pool.NullPool)
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)

    # 5. Sync engine + sessionmaker for Celery tasks
    sync_engine = create_engine(disposable_url_sync, echo=False, poolclass=sa_pool.NullPool)
    sync_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

    # Patch sync session factory globally for Celery tasks in this module
    import backend.tasks.studio_tasks as st_tasks
    import backend.models.database as db_mod
    old_st_sync = st_tasks.SyncSessionLocal
    old_db_sync = db_mod.SyncSessionLocal
    st_tasks.SyncSessionLocal = sync_session_factory
    db_mod.SyncSessionLocal = sync_session_factory

    yield {
        "db_name": db_name,
        "sync_url": disposable_url_sync,
        "async_url": disposable_url_async,
        "engine": async_engine,
        "session_factory": session_factory,
        "sync_session_factory": sync_session_factory,
    }

    # Restore sessionmakers
    st_tasks.SyncSessionLocal = old_st_sync
    db_mod.SyncSessionLocal = old_db_sync

    # Teardown
    try:
        asyncio.get_event_loop().run_until_complete(async_engine.dispose())
    except RuntimeError:
        asyncio.run(async_engine.dispose())

    sync_engine.dispose()

    teardown_dsn = f"host={PG_HOST} port={PG_PORT} dbname={ADMIN_DB} user={PG_USER} password={PG_PASS}"
    admin_conn = psycopg2.connect(teardown_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
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


@pytest.fixture(scope="module")
def valid_mp4_file(isolated_storage):
    dest_path = isolated_storage["upload_dir"] / "test_p2_sample.mp4"
    if not dest_path.exists():
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        cmd = [
            ffmpeg_bin, "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    return dest_path


async def upload_full_video(async_client, batch_id: str, client_item_id: str, filename: str, mp4_file: Path, duration: float = 2.0):
    size = mp4_file.stat().st_size
    # 1. Init
    init_res = await async_client.post(f"/api/studio/batches/{batch_id}/videos/init", json={
        "client_item_id": client_item_id,
        "source_filename": filename,
        "file_size": size,
        "resolution": "320x240",
        "duration": duration,
    })
    assert init_res.status_code == 201
    video_id = init_res.json()["id"]

    # 2. Upload chunk
    content = mp4_file.read_bytes()
    chunk_res = await async_client.put(
        f"/api/studio/uploads/{video_id}/chunk",
        headers={
            "Content-Range": f"bytes 0-{size - 1}/{size}",
            "Content-Type": "application/octet-stream",
        },
        content=content,
    )
    assert chunk_res.status_code == 200
    assert chunk_res.json()["status"] == "uploaded"
    return video_id, size


# ── PHASE 2 TEST CASES ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_01_batch_processing_initiation_and_queue_order(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that calling POST /api/studio/batches/{id}/process starts processing
    in strict queue_position ASC order and enforces single active item invariant.
    """
    idem_key = f"idem_p2_01_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key, "name": "Sequential Batch"})
    assert b_res.status_code == 201
    batch_id = b_res.json()["id"]

    # Upload 3 videos
    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "alpha.mp4", valid_mp4_file)
    v1_id, _ = await upload_full_video(async_client, batch_id, "item_1", "beta.mp4", valid_mp4_file)
    v2_id, _ = await upload_full_video(async_client, batch_id, "item_2", "gamma.mp4", valid_mp4_file)

    # Mock the Celery pipeline dispatch so worker doesn't need to run full ffmpeg background pipeline
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_dispatch:
        mock_dispatch.return_value = MagicMock(id="task_pipeline_001")

        # Start batch processing via API
        proc_res = await async_client.post(f"/api/studio/batches/{batch_id}/process")
        assert proc_res.status_code == 200
        data = proc_res.json()
        assert data["status"] in ("queued", "processing")

        # Verify Celery task was called synchronously or queued
        # Also run task directly to inspect database state
        task_res = process_studio_batch_sequential_task(batch_id)
        assert task_res["status"] in ("already_processing", "dispatched", "processing_started")

    # Inspect database directly
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        batch = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        assert batch.status == UploadBatchStatus.PROCESSING.value
        assert batch.active_video_id == v0_id

        videos = sync_session.query(Video).filter(Video.upload_batch_id == batch_id).order_by(Video.queue_position.asc()).all()
        assert len(videos) == 3
        # Single active item invariant: v0 is processing, v1 and v2 are queued
        assert videos[0].id == v0_id
        assert videos[0].processing_status == VideoProcessingStatus.PROCESSING.value
        assert videos[0].processing_job_id is not None

        assert videos[1].id == v1_id
        assert videos[1].processing_status == VideoProcessingStatus.QUEUED.value

        assert videos[2].id == v2_id
        assert videos[2].processing_status == VideoProcessingStatus.QUEUED.value
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_02_idempotent_start_and_duplicate_task_protection(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that calling POST /api/studio/batches/{id}/process repeatedly
    does not create duplicate jobs or spawn parallel processing.
    """
    idem_key = f"idem_p2_02_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key, "name": "Idempotent Batch"})
    batch_id = b_res.json()["id"]

    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "clip_a.mp4", valid_mp4_file)
    v1_id, _ = await upload_full_video(async_client, batch_id, "item_1", "clip_b.mp4", valid_mp4_file)

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_dispatch:
        mock_dispatch.return_value = MagicMock(id="task_mock_002")

        # 1st call
        res1 = await async_client.post(f"/api/studio/batches/{batch_id}/process")
        assert res1.status_code == 200

        # Execute task once to establish active job
        process_studio_batch_sequential_task(batch_id)

        # 2nd call (repeated API call)
        res2 = await async_client.post(f"/api/studio/batches/{batch_id}/process")
        assert res2.status_code == 200
        assert res2.json()["active_video_id"] == v0_id

        # Direct task invocation during active job
        dup_res = process_studio_batch_sequential_task(batch_id)
        assert dup_res["status"] == "already_processing"
        assert dup_res["active_video_id"] == v0_id

    # Verify only 1 Job exists in database
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        jobs = sync_session.query(Job).filter(Job.video_id == v0_id).all()
        assert len(jobs) == 1
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_03_progress_reporting_reflection(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that live job progress and step updates are reflected on the batch API.
    """
    idem_key = f"idem_p2_03_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]
    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "video.mp4", valid_mp4_file)

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        process_studio_batch_sequential_task(batch_id)

    # Update Job progress in database
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        video = sync_session.query(Video).filter(Video.id == v0_id).first()
        job = sync_session.query(Job).filter(Job.id == video.processing_job_id).first()
        assert job is not None
        job.progress = 75
        job.current_step = "Analyzing viral hooks"
        sync_session.commit()
    finally:
        sync_session.close()

    # Query batch API
    res = await async_client.get(f"/api/studio/batches/{batch_id}")
    assert res.status_code == 200
    b_data = res.json()
    assert b_data["active_video_id"] == v0_id
    v0_resp = next(v for v in b_data["videos"] if v["id"] == v0_id)
    assert v0_resp["processing_progress"] == 75
    assert v0_resp["processing_step"] == "Analyzing viral hooks"


@pytest.mark.asyncio
async def test_p2_04_missing_media_artifact_fails_safely_and_halts(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that if an artifact is missing from disk, processing fails safely
    without crashing or corrupting subsequent queue items.
    """
    idem_key = f"idem_p2_04_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "corrupt_artifact.mp4", valid_mp4_file)
    v1_id, _ = await upload_full_video(async_client, batch_id, "item_1", "next_item.mp4", valid_mp4_file)

    # Intentionally unlink the media artifact
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        video0 = sync_session.query(Video).filter(Video.id == v0_id).first()
        assert video0.local_path is not None
        artifact_path = Path(video0.local_path)
        if artifact_path.exists():
            artifact_path.unlink()
    finally:
        sync_session.close()

    # Run processing
    task_res = process_studio_batch_sequential_task(batch_id)
    assert task_res["status"] == "artifact_missing"

    # Verify database state
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        batch = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        assert batch.status == UploadBatchStatus.FAILED.value
        assert "artifact missing" in batch.batch_error.lower()

        v0 = sync_session.query(Video).filter(Video.id == v0_id).first()
        assert v0.processing_status == VideoProcessingStatus.FAILED.value
        assert "missing" in v0.processing_error.lower()

        # Item 1 must NOT have executed
        v1 = sync_session.query(Video).filter(Video.id == v1_id).first()
        assert v1.processing_status in (VideoProcessingStatus.QUEUED.value, VideoProcessingStatus.NONE.value)
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_05_safe_retry_preserving_queue_position(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that retrying a failed video resets status and preserves original queue_position.
    """
    idem_key = f"idem_p2_05_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "first.mp4", valid_mp4_file)
    v1_id, _ = await upload_full_video(async_client, batch_id, "item_1", "second.mp4", valid_mp4_file)

    # Set v0 to failed manually
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        b = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        b.status = UploadBatchStatus.FAILED.value
        v0 = sync_session.query(Video).filter(Video.id == v0_id).first()
        v0.processing_status = VideoProcessingStatus.FAILED.value
        v0.processing_error = "Transient error"
        sync_session.commit()
    finally:
        sync_session.close()

    # Retry specific video via API
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        retry_res = await async_client.post(f"/api/studio/batches/{batch_id}/videos/{v0_id}/retry")
        assert retry_res.status_code == 200
        ret_data = retry_res.json()
        assert ret_data["retried"] is True
        assert ret_data["queue_position"] == 0

        # Execute task with retry
        task_res = process_studio_batch_sequential_task(batch_id, retry_video_id=v0_id)

    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        v0 = sync_session.query(Video).filter(Video.id == v0_id).first()
        assert v0.queue_position == 0  # Queue position preserved!
        assert v0.processing_status == VideoProcessingStatus.PROCESSING.value
        assert v0.processing_attempt == 1
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_06_sequential_advancement_and_headroom_release(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that when item 0 finishes, its 1.5x reservation headroom is released,
    and item 1 is sequentially dispatched.
    """
    idem_key = f"idem_p2_06_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    v0_id, s0 = await upload_full_video(async_client, batch_id, "item_0", "clip0.mp4", valid_mp4_file)
    v1_id, s1 = await upload_full_video(async_client, batch_id, "item_1", "clip1.mp4", valid_mp4_file)

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        process_studio_batch_sequential_task(batch_id)

    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        v0 = sync_session.query(Video).filter(Video.id == v0_id).first()
        job0_id = v0.processing_job_id
        assert job0_id is not None
        # Headroom was reserved (0.5 * size)
        assert v0.reservation_state == VideoReservationState.HEADROOM_ONLY.value
        assert v0.reserved_bytes > 0
    finally:
        sync_session.close()

    # Simulate pipeline completion of item 0
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        j0 = sync_session.query(Job).filter(Job.id == job0_id).first()
        j0.status = JobStatus.COMPLETED.value
        sync_session.commit()
    finally:
        sync_session.close()

    with patch("backend.tasks.studio_tasks.process_studio_batch_sequential_task.delay") as mock_next:
        on_studio_video_finished_task(batch_id, v0_id, job0_id)
        assert mock_next.called

    # Verify v0 headroom released
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        v0 = sync_session.query(Video).filter(Video.id == v0_id).first()
        assert v0.processing_status == VideoProcessingStatus.COMPLETED.value
        assert v0.reservation_state == VideoReservationState.RELEASED.value
        assert v0.reserved_bytes == 0
    finally:
        sync_session.close()

    # Process next item in sequence
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        task_res = process_studio_batch_sequential_task(batch_id)

    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        batch = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        assert batch.active_video_id == v1_id
        v1 = sync_session.query(Video).filter(Video.id == v1_id).first()
        assert v1.processing_status == VideoProcessingStatus.PROCESSING.value
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_07_cooperative_cancellation_stops_remaining_items(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that calling cancel transitions batch to cancelled and prevents subsequent items from running.
    """
    idem_key = f"idem_p2_07_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "cancel_a.mp4", valid_mp4_file)
    v1_id, _ = await upload_full_video(async_client, batch_id, "item_1", "cancel_b.mp4", valid_mp4_file)

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        process_studio_batch_sequential_task(batch_id)

    # Cancel batch via API
    cancel_res = await async_client.post(f"/api/studio/batches/{batch_id}/cancel")
    assert cancel_res.status_code == 200

    # Execute cancellation in sequential task
    task_res = process_studio_batch_sequential_task(batch_id)
    assert task_res["status"] == "cancelled"

    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        batch = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        assert batch.status == UploadBatchStatus.CANCELLED.value

        v1 = sync_session.query(Video).filter(Video.id == v1_id).first()
        assert v1.processing_status == VideoProcessingStatus.CANCELLED.value
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_08_deletion_rejection_during_active_processing(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that DELETE /api/studio/batches/{id} returns HTTP 409 Conflict if processing is active.
    """
    idem_key = f"idem_p2_08_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    await upload_full_video(async_client, batch_id, "item_0", "del_test.mp4", valid_mp4_file)

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        process_studio_batch_sequential_task(batch_id)

    # Attempt delete while processing
    del_res = await async_client.delete(f"/api/studio/batches/{batch_id}")
    assert del_res.status_code == 409
    assert "Cannot delete batch while video processing is active" in del_res.json()["detail"]


@pytest.mark.asyncio
async def test_p2_09_stale_worker_heartbeat_recovery(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies that batches with stale worker heartbeats (> 10 minutes) are recovered safely.
    """
    idem_key = f"idem_p2_09_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "stale.mp4", valid_mp4_file)

    # Manually simulate stale heartbeat (15 minutes ago)
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(minutes=15)

    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        b = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        b.status = UploadBatchStatus.PROCESSING.value
        b.active_video_id = v0_id
        b.worker_heartbeat = stale_time

        v = sync_session.query(Video).filter(Video.id == v0_id).first()
        v.processing_status = VideoProcessingStatus.PROCESSING.value
        v.processing_started_at = stale_time
        sync_session.commit()
    finally:
        sync_session.close()

    # Run recovery task
    rec_res = recover_stale_studio_batches_task(timeout_minutes=10)
    assert rec_res["recovered_batches"] >= 1

    # Verify batch was transitioned to failed
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        batch = sync_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        assert batch.status == UploadBatchStatus.FAILED.value
        assert "heartbeat" in batch.batch_error.lower()

        v = sync_session.query(Video).filter(Video.id == v0_id).first()
        assert v.processing_status == VideoProcessingStatus.FAILED.value
        assert "timeout" in v.processing_error.lower()
    finally:
        sync_session.close()


@pytest.mark.asyncio
async def test_p2_10_zero_captions_subtitles_invariant(async_client, disposable_pg_db, valid_mp4_file):
    """
    Verifies strict compliance with the project rule:
    ZERO caption/subtitle functionality (no ASS/SRT, font styling, or subtitle burning filters).
    """
    idem_key = f"idem_p2_10_{uuid.uuid4().hex[:8]}"
    b_res = await async_client.post("/api/studio/batches", json={"idempotency_key": idem_key})
    batch_id = b_res.json()["id"]

    v0_id, _ = await upload_full_video(async_client, batch_id, "item_0", "caption_check.mp4", valid_mp4_file)

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        process_studio_batch_sequential_task(batch_id)

    # Inspect Job config and DB records
    sync_session = disposable_pg_db["sync_session_factory"]()
    try:
        video = sync_session.query(Video).filter(Video.id == v0_id).first()
        job = sync_session.query(Job).filter(Job.id == video.processing_job_id).first()
        assert job is not None

        cfg_str = job.config or "{}"
        cfg = json.loads(cfg_str) if isinstance(cfg_str, str) else cfg_str

        # Forbidden tokens according to Section 1 & Section 10
        forbidden_keys = ["captions", "subtitles", "burn_subtitles", "ass", "srt", "font", "font_name"]
        for key in forbidden_keys:
            assert key not in cfg, f"Forbidden caption key '{key}' found in Job config: {cfg}"

        # Ensure no subtitle filters in video processing
        raw_text = str(cfg).lower()
        assert "subtitles=" not in raw_text
        assert "ass=" not in raw_text
    finally:
        sync_session.close()
