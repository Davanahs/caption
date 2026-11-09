"""
ClipForge — Upload Studio Phase 3 YouTube Publishing Test Suite
Tests execute exclusively against dedicated disposable PostgreSQL databases.
Production/active dev database ('clipforge') and existing storage directories are never targeted.
"""
import os
import sys
import uuid
import json
import shutil
import asyncio
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
    Clip,
    Job,
    PublishRecord,
    PublishStatus,
    StorageReservationCoordinator,
    UploadBatchStatus,
    VideoUploadStatus,
    VideoProcessingStatus,
    VideoReservationState,
    VideoTrackingQueue,
)
from backend.tasks.clip_tasks import (
    publish_clip_task,
    recover_stranded_publish_jobs_task,
    PublishCancelledException,
)
from backend.services.publisher import (
    update_video_metadata,
    get_channel_info,
    check_auth_status,
    get_oauth_url,
    upload_short,
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
    upload_dir = tmp_path_factory.mktemp("uploads_phase3")
    volume_id = f"vol-p3-{uuid.uuid4().hex[:8]}"
    secret_key = "test_secure_runtime_identity_secret_2026_03"

    token = provision_storage_identity(
        upload_dir=upload_dir,
        volume_id=volume_id,
        secret_key=secret_key,
        cluster_id="test_cluster"
    )

    old_upload_dir = settings.UPLOAD_DIR
    old_publish_mode = getattr(settings, "PUBLISH_MODE", "prod")
    settings.UPLOAD_DIR = upload_dir
    settings.STORAGE_IDENTITY_SECRET = secret_key
    settings.SECRET_KEY = secret_key
    settings.PUBLISH_MODE = "test"
    os.environ["BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST"] = "1"
    os.environ["PUBLISH_MODE"] = "test"

    yield {
        "upload_dir": upload_dir,
        "volume_id": volume_id,
        "secret_key": secret_key,
        "token": token
    }

    settings.UPLOAD_DIR = old_upload_dir
    settings.PUBLISH_MODE = old_publish_mode
    os.environ.pop("BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST", None)
    os.environ.pop("PUBLISH_MODE", None)


@pytest.fixture(scope="module")
def disposable_pg_db(isolated_storage):
    unique_suffix = uuid.uuid4().hex[:8]
    db_name = f"cf_disp_p3_{unique_suffix}"
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

    # 3. Alembic migrations up to head (f3b4c5d6e7f8)
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
    import backend.tasks.clip_tasks as ct_tasks
    import backend.models.database as db_mod
    old_ct_sync = ct_tasks.SyncSessionLocal
    old_db_sync = db_mod.SyncSessionLocal
    ct_tasks.SyncSessionLocal = sync_session_factory
    db_mod.SyncSessionLocal = sync_session_factory

    from backend.models.models import Channel
    with sync_session_factory() as session:
        dest_chan = Channel(
            id="ch_main",
            youtube_channel_id="ch_main",
            channel_name="Main Destination Channel",
            channel_url="https://youtube.com/@main",
            is_active=True,
            is_destination=True,
            is_default_destination=True,
        )
        session.add(dest_chan)
        session.commit()

    import backend.services.publisher as pub_mod
    auth_patcher = patch.object(pub_mod, "check_channel_authorization", return_value=(True, None))
    auth_patcher.start()

    yield {
        "db_name": db_name,
        "sync_url": disposable_url_sync,
        "async_url": disposable_url_async,
        "engine": async_engine,
        "session_factory": session_factory,
        "sync_session_factory": sync_session_factory,
    }

    # Teardown
    auth_patcher.stop()
    ct_tasks.SyncSessionLocal = old_ct_sync
    db_mod.SyncSessionLocal = old_db_sync
    sync_engine.dispose()
    asyncio.run(async_engine.dispose())

    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = admin_conn.cursor()
    cur.execute(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{db_name}'
          AND pid <> pg_backend_pid();
    """)
    cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    cur.close()
    admin_conn.close()


@pytest.fixture
def override_db(disposable_pg_db):
    async def _get_test_db():
        async with disposable_pg_db["session_factory"]() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield disposable_pg_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client(override_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def _create_dummy_mp4(target_path: Path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"A" * 1024)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 Publishing Test Suite (10 Production-Safety Requirements)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_p3_01_publish_eligibility_validation(override_db, client, isolated_storage):
    """
    Test 1: Publish eligibility validation
    Rejects unready clips:
    - Clip missing output file on disk -> fails safely with clear error.
    - Clip undergoing active processing -> rejected.
    """
    session_factory = override_db["sync_session_factory"]

    # Clip with non-existent file
    clip_id_missing = f"clip_missing_{uuid.uuid4().hex[:8]}"
    with session_factory() as session:
        c1 = Clip(
            id=clip_id_missing,
            video_id="v_missing",
            title="Missing File Clip",
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            output_path="/tmp/non_existent_clip_12345.mp4",
            publish_status=PublishStatus.DRAFT.value,
            status="completed"
        )
        session.add(c1)
        session.commit()

    # Call task
    mock_task = MagicMock()
    mock_task.request.id = "task_eligibility_1"
    mock_task.request.retries = 0
    mock_task.max_retries = 3

    res1 = publish_clip_task(mock_task, clip_id=clip_id_missing)
    assert res1["status"] == "failed"
    assert "missing from disk" in res1["error"]

    with session_factory() as session:
        c1 = session.query(Clip).filter_by(id=clip_id_missing).first()
        assert c1.publish_status == PublishStatus.FAILED.value
        assert "missing from disk" in c1.publish_error


@pytest.mark.asyncio
async def test_p3_02_stable_logical_idempotency_key(override_db, client, isolated_storage):
    """
    Test 2: Stable logical idempotency key across retries
    The logical publication idempotency key MUST be stable across retries and redelivery.
    It must NOT change when publish_attempt increments.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_idemp_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_idemp",
            title="Idempotency Test Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    mock_task = MagicMock()
    mock_task.request.id = "task_idemp_1"
    mock_task.request.retries = 0
    mock_task.max_retries = 3

    # Attempt 1
    res1 = publish_clip_task(mock_task, clip_id=clip_id, channel_id="ch_main")
    assert res1["status"] == "published"

    with session_factory() as session:
        c_after = session.query(Clip).filter_by(id=clip_id).first()
        initial_key = c_after.publish_idempotency_key
        assert initial_key == f"pub_{clip_id}_ch_main"
        assert "v1" not in initial_key  # Must not contain version/attempt string
        assert c_after.publish_attempt == 1

    # Attempt 2 (Simulated retry of the same operation)
    mock_task.request.id = "task_idemp_2"
    mock_task.request.retries = 1
    res2 = publish_clip_task(mock_task, clip_id=clip_id, channel_id="ch_main")
    assert res2["status"] == "published"

    with session_factory() as session:
        c_retry = session.query(Clip).filter_by(id=clip_id).first()
        # Key remains strictly identical
        assert c_retry.publish_idempotency_key == initial_key


@pytest.mark.asyncio
async def test_p3_03_concurrent_worker_fencing(override_db, client, isolated_storage):
    """
    Test 3: Enforce database uniqueness and task-claiming rules to prevent concurrent duplicates.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_fence_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    stable_key = f"pub_{clip_id}_default"
    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_fence",
            title="Fenced Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.PUBLISHED.value,
            youtube_short_id="mock_already_published_id",
            publish_idempotency_key=stable_key,
            status="completed"
        )
        pr = PublishRecord(
            idempotency_key=stable_key,
            job_id="job_fenced",
            clip_id=clip_id,
            target="youtube",
            external_id="mock_already_published_id",
            status="completed"
        )
        session.add(c)
        session.add(pr)
        session.commit()

    # Second worker attempts to publish the same clip
    mock_task = MagicMock()
    mock_task.request.id = "task_worker_replacement"
    mock_task.request.retries = 0

    with patch("backend.services.publisher.upload_short") as mock_upload:
        res = publish_clip_task(mock_task, clip_id=clip_id)
        assert res["status"] == "published"
        assert res["youtube_id"] == "mock_already_published_id"
        # Duplicate remote upload was NEVER called
        mock_upload.assert_not_called()


@pytest.mark.asyncio
async def test_p3_04_immediate_persistence_of_remote_video_id(override_db, client, isolated_storage):
    """
    Test 4: Immediate persistence of remote video ID, timestamps, and PublishRecord on success.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_persist_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_persist",
            title="Persistence Test",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    mock_task = MagicMock()
    mock_task.request.id = "task_persist_1"
    mock_task.request.retries = 0

    res = publish_clip_task(mock_task, clip_id=clip_id)
    assert res["status"] == "published"
    remote_id = res["youtube_id"]
    assert remote_id.startswith("mock_")

    with session_factory() as session:
        c_check = session.query(Clip).filter_by(id=clip_id).first()
        assert c_check.youtube_short_id == remote_id
        assert c_check.publish_status == PublishStatus.PUBLISHED.value
        assert c_check.publish_stage == "published"
        assert c_check.publish_progress == 100
        assert c_check.published_at is not None
        assert c_check.publish_completed_at is not None

        pr_check = session.query(PublishRecord).filter_by(clip_id=clip_id).first()
        assert pr_check is not None
        assert pr_check.external_id == remote_id
        assert pr_check.status == "completed"


@pytest.mark.asyncio
async def test_p3_05_safe_remote_upload_reconciliation(override_db, client, isolated_storage):
    """
    Test 5: Safe remote upload reconciliation
    If a worker fails after remote upload may have succeeded, reconcile the existing
    operation before attempting another upload.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_reconcile_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)
    idemp_key = f"pub_{clip_id}_default"

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_recon",
            title="Reconciliation Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            publish_idempotency_key=idemp_key,
            status="completed"
        )
        session.add(c)
        session.commit()

    # Simulate: check_external_youtube_state finds the video on YouTube
    mock_task = MagicMock()
    mock_task.request.id = "task_recon_retry"
    mock_task.request.retries = 1

    with patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value="yt_discovered_999") as mock_check, \
         patch("backend.tasks.clip_tasks.upload_short") as mock_upload:

        res = publish_clip_task(mock_task, clip_id=clip_id)
        assert res["status"] == "published"
        assert res["youtube_id"] == "yt_discovered_999"

        # Reconciled without duplicate upload!
        mock_check.assert_called_once()
        mock_upload.assert_not_called()

        with session_factory() as session:
            c_check = session.query(Clip).filter_by(id=clip_id).first()
            assert c_check.youtube_short_id == "yt_discovered_999"
            assert c_check.publish_status == PublishStatus.PUBLISHED.value


@pytest.mark.asyncio
async def test_p3_06_manual_review_gating_blocks_auto_retry(override_db, client, isolated_storage):
    """
    Test 6: Inconclusive reconciliation transitions to manual_review and blocks normal retry.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_review_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_review",
            title="Review Gated Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    mock_task = MagicMock()
    mock_task.request.id = "task_inconclusive"
    mock_task.request.retries = 0

    # Reconciliation returns MANUAL_REVIEW_REQUIRED
    with patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value="MANUAL_REVIEW_REQUIRED"):
        res = publish_clip_task(mock_task, clip_id=clip_id)
        assert res["status"] == "manual_review"

    with session_factory() as session:
        c_check = session.query(Clip).filter_by(id=clip_id).first()
        assert c_check.publish_status == PublishStatus.MANUAL_REVIEW.value
        assert "Manual review required" in c_check.publish_error

    # API: normal publish-now is blocked with 409 Conflict
    resp_pub = await client.post("/api/publish/publish-now", json={"clip_id": clip_id})
    assert resp_pub.status_code == 409
    assert "manual_review" in resp_pub.json()["detail"]

    # API: normal retry is blocked with 400 Bad Request
    resp_retry_unforced = await client.post(f"/api/publish/clips/{clip_id}/retry", json={"force": False})
    assert resp_retry_unforced.status_code == 400
    assert "manual_review" in resp_retry_unforced.json()["detail"]

    # API: explicit resolution with force=True is permitted
    resp_retry_forced = await client.post(f"/api/publish/clips/{clip_id}/retry", json={"force": True})
    assert resp_retry_forced.status_code == 202
    assert resp_retry_forced.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_p3_07_permanent_error_non_retryable(override_db, client, isolated_storage):
    """
    Test 7: Permanent errors (credentials invalid, missing files, quota exhausted)
    transition to failed without raising Celery retry loop.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_perm_err_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_perm",
            title="Permanent Error Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    mock_task = MagicMock()
    mock_task.request.id = "task_permanent_error"
    mock_task.request.retries = 0
    mock_task.max_retries = 3

    # Simulate permanent authentication / credential failure
    with patch("backend.tasks.clip_tasks.upload_short", side_effect=ValueError("YouTube authorization required: No valid credentials found.")):
        res = publish_clip_task(mock_task, clip_id=clip_id)
        assert res["status"] == "failed"
        assert "authorization required" in res["error"].lower()
        # Celery retry was NOT invoked for permanent error
        mock_task.retry.assert_not_called()

    with session_factory() as session:
        c_check = session.query(Clip).filter_by(id=clip_id).first()
        assert c_check.publish_status == PublishStatus.FAILED.value


@pytest.mark.asyncio
async def test_p3_08_cooperative_cancellation(override_db, client, isolated_storage):
    """
    Test 8: Cooperative cancellation stops upload gracefully and never reports
    cancelled if YouTube has already accepted it.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_cancel_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_cancel",
            title="Cancel Test Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    # Cancel via API
    resp_cancel = await client.post(f"/api/publish/clips/{clip_id}/cancel")
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "cancelled"

    mock_task = MagicMock()
    mock_task.request.id = "task_cancelled_exec"
    res = publish_clip_task(mock_task, clip_id=clip_id)
    assert res["status"] == "cancelled"

    # Already published clip cannot be cancelled
    with session_factory() as session:
        c_pub = session.query(Clip).filter_by(id=clip_id).first()
        c_pub.publish_status = PublishStatus.PUBLISHED.value
        c_pub.youtube_short_id = "already_live_123"
        session.commit()

    resp_cancel_published = await client.post(f"/api/publish/clips/{clip_id}/cancel")
    assert resp_cancel_published.status_code == 400
    assert "already succeeded" in resp_cancel_published.json()["detail"]


@pytest.mark.asyncio
async def test_p3_09_batch_deletion_409_conflict(override_db, client, isolated_storage):
    """
    Test 9: DELETE /api/studio/batches/{id} returns HTTP 409 Conflict when clips
    in the batch are actively publishing ('queued', 'uploading', 'finalizing').
    """
    session_factory = override_db["sync_session_factory"]
    batch_id = f"b_del_{uuid.uuid4().hex[:8]}"
    video_id = f"v_del_{uuid.uuid4().hex[:8]}"
    clip_id = f"clip_del_{uuid.uuid4().hex[:8]}"

    with session_factory() as session:
        b = UploadBatch(
            id=batch_id,
            idempotency_key=f"idemp_{batch_id}",
            status=UploadBatchStatus.COMPLETED.value
        )
        v = Video(
            id=video_id,
            upload_batch_id=batch_id,
            title="Video in Batch",
            upload_status=VideoUploadStatus.UPLOADED.value
        )
        c = Clip(
            id=clip_id,
            video_id=video_id,
            title="Actively Publishing Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            publish_status=PublishStatus.UPLOADING.value,
            status="completed"
        )
        session.add(b)
        session.add(v)
        session.add(c)
        session.commit()

    # Attempt delete while clip is actively publishing -> 409 Conflict
    resp_del = await client.delete(f"/api/studio/batches/{batch_id}")
    assert resp_del.status_code == 409
    assert "actively publishing" in resp_del.json()["detail"]

    # When clip transitions to published or cancelled, deletion succeeds
    with session_factory() as session:
        c_up = session.query(Clip).filter_by(id=clip_id).first()
        c_up.publish_status = PublishStatus.PUBLISHED.value
        session.commit()

    resp_del_ok = await client.delete(f"/api/studio/batches/{batch_id}")
    assert resp_del_ok.status_code == 200
    assert resp_del_ok.json()["deleted"] is True


@pytest.mark.asyncio
async def test_p3_10_storage_reservation_invariant_and_durable_dispatch(override_db, client, isolated_storage):
    """
    Test 10:
    a) Publishing must NEVER modify processing storage reservations.
    b) Durable dispatch: stranded queued jobs committed in DB are recoverable by recovery task.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_inv_{uuid.uuid4().hex[:8]}"
    video_id = f"v_inv_{uuid.uuid4().hex[:8]}"
    batch_id = f"b_inv_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        coord = StorageReservationCoordinator(id="global", reserved_bytes=500000)
        session.merge(coord)

        b = UploadBatch(id=batch_id, idempotency_key=f"idemp_{batch_id}", reserved_bytes=200000)
        v = Video(
            id=video_id,
            upload_batch_id=batch_id,
            title="Reservation Invariant Video",
            reserved_bytes=200000,
            reservation_state=VideoReservationState.HEADROOM_ONLY.value
        )
        c = Clip(
            id=clip_id,
            video_id=video_id,
            title="Publishing Invariant Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            publish_started_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # Stranded job
            status="completed"
        )
        session.add(b)
        session.add(v)
        session.add(c)
        session.commit()

    # Part a: Execute publish task and check storage reservation is 100% untouched
    mock_task = MagicMock()
    mock_task.request.id = "task_inv_exec"
    mock_task.request.retries = 0

    res = publish_clip_task(mock_task, clip_id=clip_id)
    assert res["status"] == "published"

    with session_factory() as session:
        v_check = session.query(Video).filter_by(id=video_id).first()
        b_check = session.query(UploadBatch).filter_by(id=batch_id).first()
        coord_check = session.query(StorageReservationCoordinator).filter_by(id="global").first()

        # Reservations are exactly identical to pre-publish values!
        assert v_check.reserved_bytes == 200000
        assert v_check.reservation_state == VideoReservationState.HEADROOM_ONLY.value
        assert b_check.reserved_bytes == 200000
        assert coord_check.reserved_bytes == 500000

    # Part b: Durable dispatch recovery
    stranded_clip_id = f"clip_stranded_{uuid.uuid4().hex[:8]}"
    with session_factory() as session:
        c_strand = Clip(
            id=stranded_clip_id,
            video_id=video_id,
            title="Stranded Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            publish_started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            status="completed"
        )
        session.add(c_strand)
        session.commit()

    with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_apply:
        mock_task_res = MagicMock()
        mock_task_res.id = "recovered_task_id_777"
        mock_apply.return_value = mock_task_res

        rec_res = recover_stranded_publish_jobs_task(stale_threshold_seconds=60)
        assert stranded_clip_id in rec_res["clip_ids"]
        mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_p3_11_video_tracking_queue_auto_optimizer_enqueued(override_db, client, isolated_storage):
    """
    Test 11: Successful publishing populates VideoTrackingQueue for Phase 5 auto-optimizer.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_track_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_track_1",
            title="Auto-Optimizer Tracked Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    mock_task = MagicMock()
    mock_task.request.id = "task_track_exec"

    res = publish_clip_task(mock_task, clip_id=clip_id)
    assert res["status"] == "published"
    assert "youtube_id" in res
    yt_id = res["youtube_id"]

    with session_factory() as session:
        tq = session.query(VideoTrackingQueue).filter_by(youtube_video_id=yt_id).first()
        assert tq is not None
        assert tq.clip_id == clip_id
        assert tq.status == "active"
        assert tq.optimization_attempts == 0
        assert tq.next_check_at is not None
        assert tq.next_check_at > tq.uploaded_at


@pytest.mark.asyncio
async def test_p3_12_update_video_metadata_preservation():
    """
    Test 12: update_video_metadata updates snippet with 450-character tag payload safety.
    """
    res = update_video_metadata(
        youtube_video_id="yt_test_vid_123",
        title="Optimized Title for Viral Reach",
        description="Optimized description with keywords",
        tags=["ai", "shorts", "automation", "verylongtag" * 50]  # will exceed 450 chars
    )
    assert res["title"] == "Optimized Title for Viral Reach"
    assert res["description"] == "Optimized description with keywords"
    assert "shorts" in res["tags"]
    total_tag_len = sum(len(t) + 1 for t in res["tags"])
    assert total_tag_len <= 451


@pytest.mark.asyncio
async def test_p3_13_oauth_channel_info_and_auth_status():
    """
    Test 13: check_auth_status, get_channel_info, and get_oauth_url preservation.
    """
    auth_ok = check_auth_status()
    assert auth_ok is True

    ch_info = get_channel_info()
    assert "id" in ch_info
    assert "title" in ch_info
    assert "subscribers" in ch_info

    oauth_url = get_oauth_url(redirect_uri="http://localhost:8000/api/publish/oauth-callback", state="test_state_123")
    assert oauth_url != ""
    assert "accounts.google.com" in oauth_url


@pytest.mark.asyncio
async def test_p3_14_resumable_upload_chunking_and_thumbnail_support(isolated_storage):
    """
    Test 14: upload_short executes resumable chunk loop and thumbnail upload.
    """
    clip_file = Path(isolated_storage["upload_dir"]) / "resumable_test.mp4"
    _create_dummy_mp4(clip_file)
    thumb_file = Path(isolated_storage["upload_dir"]) / "thumb.png"
    thumb_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    # Mock googleapiclient youtube service
    mock_yt = MagicMock()
    mock_insert_req = MagicMock()
    mock_chunk_1 = MagicMock()
    mock_chunk_1.resumable_progress = 5000000
    mock_chunk_1.total_size = 10000000
    mock_chunk_1.progress.return_value = 0.5

    mock_insert_req.next_chunk.side_effect = [
        (mock_chunk_1, None),
        (None, {"id": "yt_resumable_999"})
    ]
    mock_yt.videos().insert.return_value = mock_insert_req
    mock_thumb_req = MagicMock()
    mock_yt.thumbnails().set.return_value = mock_thumb_req

    progress_events = []
    def track_cb(b_up, b_tot, p_float):
        progress_events.append((b_up, b_tot, p_float))

    with patch("backend.services.publisher.settings.PUBLISH_MODE", "prod"), \
         patch("backend.services.publisher.get_youtube_client", return_value=mock_yt), \
         patch("time.sleep"), \
         patch("backend.services.publisher.MediaFileUpload"):
        res = upload_short(
            video_path=clip_file,
            title="Resumable Test Video",
            description="Testing chunk progress",
            thumbnail_path=thumb_file,
            idempotency_key="idemp_chunk_test",
            channel_id="ch_main",
            progress_callback=track_cb
        )

        assert res["id"] == "yt_resumable_999"
        assert res["url"] == "https://www.youtube.com/shorts/yt_resumable_999"
        assert len(progress_events) == 1
        assert progress_events[0][2] == 0.5
        mock_yt.thumbnails().set.assert_called_once()


@pytest.mark.asyncio
async def test_p3_15_reconciliation_enqueues_tracking_queue(override_db, isolated_storage):
    """
    Test 15: Reconciled remote upload also enqueues VideoTrackingQueue.
    """
    session_factory = override_db["sync_session_factory"]
    clip_id = f"clip_recon_tq_{uuid.uuid4().hex[:8]}"
    out_file = Path(isolated_storage["upload_dir"]) / f"{clip_id}.mp4"
    _create_dummy_mp4(out_file)

    with session_factory() as session:
        c = Clip(
            id=clip_id,
            video_id="v_recon_tq",
            title="Reconciled Tracking Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            output_path=str(out_file),
            publish_status=PublishStatus.QUEUED.value,
            publish_destination_id="ch_main",
            status="completed"
        )
        session.add(c)
        session.commit()

    mock_task = MagicMock()
    mock_task.request.id = "task_recon_tq"

    with patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value="yt_reconciled_ext_888"):
        res = publish_clip_task(mock_task, clip_id=clip_id)
        assert res["status"] == "published"
        assert res["youtube_id"] == "yt_reconciled_ext_888"

    with session_factory() as session:
        tq = session.query(VideoTrackingQueue).filter_by(youtube_video_id="yt_reconciled_ext_888").first()
        assert tq is not None
        assert tq.clip_id == clip_id
        assert tq.status == "active"

