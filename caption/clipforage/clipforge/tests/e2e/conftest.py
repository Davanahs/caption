"""
tests/e2e/conftest.py
=====================
Global test fixtures for ClipForge Multi-Destination Publishing & Automatic Outro E2E Suite.
Provides:
- Module-scoped event_loop for Windows asyncio compatibility.
- Disposable PostgreSQL database (cf_e2e_{uuid}) with Alembic upgrade to head.
- Isolated filesystem storage for uploads, outputs, and outros.
- AsyncClient fixture injecting disposable database session into FastAPI app.
- Google YouTube API v3 service mocks (channels, videos resumable upload, status checks).
"""
import os
import sys
import uuid
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from alembic.config import Config
from alembic import command
import httpx
from httpx import ASGITransport, AsyncClient

# Ensure clipforge root and backend are in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.main import app
from backend.core.config import settings
from backend.models.database import get_db, Base, engine as central_engine
import backend.models.database as db_mod
import backend.tasks.clip_tasks as ct_tasks


# ── Module Event Loop for Windows Proactor Loop Compatibility ─────────────────
@pytest.fixture(scope="module")
def event_loop(request):
    """
    Module-scoped event loop shared by all tests in an E2E test module.
    Prevents 'Future attached to a different loop' errors on Windows.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="module")
def _cleanup_central_engine():
    """Cleanly disposes centralized SQLAlchemy async engine connection pool at module teardown."""
    yield
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(central_engine.dispose())
        loop.close()
    except Exception:
        pass


# ── Isolated Storage Fixture ──────────────────────────────────────────────────
@pytest.fixture(scope="module")
def e2e_storage(tmp_path_factory):
    """
    Creates isolated temporary storage folders for uploads, outputs, and outros.
    Redirects settings.UPLOAD_DIR and settings.OUTPUT_DIR for the test session.
    """
    storage_root = tmp_path_factory.mktemp("clipforge_e2e_storage")
    upload_dir = storage_root / "uploads"
    output_dir = storage_root / "outputs"
    outro_dir = upload_dir / "outros"

    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    outro_dir.mkdir(parents=True, exist_ok=True)

    old_upload = settings.UPLOAD_DIR
    old_output = getattr(settings, "OUTPUT_DIR", None)
    old_publish_mode = getattr(settings, "PUBLISH_MODE", None)

    settings.UPLOAD_DIR = upload_dir
    if hasattr(settings, "OUTPUT_DIR"):
        settings.OUTPUT_DIR = output_dir
    settings.PUBLISH_MODE = "test"
    os.environ["BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST"] = "1"
    os.environ["PUBLISH_MODE"] = "test"

    yield {
        "root": storage_root,
        "upload_dir": upload_dir,
        "output_dir": output_dir,
        "outro_dir": outro_dir,
    }

    settings.UPLOAD_DIR = old_upload
    if old_output is not None:
        settings.OUTPUT_DIR = old_output
    if old_publish_mode is not None:
        settings.PUBLISH_MODE = old_publish_mode
    os.environ.pop("BYPASS_STORAGE_MOUNT_CHECK_FOR_TEST", None)
    os.environ.pop("PUBLISH_MODE", None)


# ── Disposable PostgreSQL Database Fixture ────────────────────────────────────
@pytest.fixture(scope="module")
def e2e_db(e2e_storage):
    """
    Creates a dedicated disposable PostgreSQL database for the E2E test module,
    runs Alembic migrations to head, provides async & sync session factories,
    patches SyncSessionLocal for Celery tasks, and completely drops the database on teardown.
    """
    from urllib.parse import urlparse
    parsed = urlparse(settings.DATABASE_URL)
    pg_host = parsed.hostname or "localhost"
    pg_port = parsed.port or 5433
    pg_user = parsed.username or "clipforge_user"
    pg_pass = parsed.password or "clipforge_password"
    admin_db = parsed.path.lstrip("/") or "clipforge"

    unique_db = f"cf_e2e_{uuid.uuid4().hex[:8]}"
    admin_dsn = f"host={pg_host} port={pg_port} dbname={admin_db} user={pg_user} password={pg_pass}"

    # 1. Create disposable database
    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin_conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{unique_db}" OWNER "{pg_user}"')
    admin_conn.close()

    async_url = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{unique_db}"
    sync_url = f"postgresql+psycopg2://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{unique_db}"

    # 2. Run Alembic Upgrade to Head
    alembic_ini = str(_BACKEND_DIR / "alembic.ini")
    alembic_scripts = str(_BACKEND_DIR / "alembic")
    cfg = Config(alembic_ini)
    cfg.set_main_option("script_location", alembic_scripts)
    cfg.set_main_option("sqlalchemy.url", async_url)
    command.upgrade(cfg, "head")

    # 3. Create Async & Sync Factories
    async_engine = create_async_engine(async_url, echo=False, poolclass=sa.pool.NullPool)
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)

    sync_engine = sa.create_engine(sync_url, echo=False, poolclass=sa.pool.NullPool)
    sync_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

    # 4. Patch Sync Sessions for Celery in-process tasks
    old_ct_sync = getattr(ct_tasks, "SyncSessionLocal", None)
    old_db_sync = getattr(db_mod, "SyncSessionLocal", None)
    ct_tasks.SyncSessionLocal = sync_session_factory
    db_mod.SyncSessionLocal = sync_session_factory

    db_context = {
        "db_name": unique_db,
        "async_url": async_url,
        "sync_url": sync_url,
        "async_engine": async_engine,
        "sync_engine": sync_engine,
        "session_factory": session_factory,
        "sync_session_factory": sync_session_factory,
    }

    yield db_context

    # 5. Teardown
    if old_ct_sync:
        ct_tasks.SyncSessionLocal = old_ct_sync
    if old_db_sync:
        db_mod.SyncSessionLocal = old_db_sync
    sync_engine.dispose()

    try:
        asyncio.run(async_engine.dispose())
    except Exception:
        pass

    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin_conn.cursor() as cur:
        cur.execute(f"""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
            WHERE datname = '{unique_db}' AND pid <> pg_backend_pid();
        """)
        cur.execute(f'DROP DATABASE IF EXISTS "{unique_db}"')
    admin_conn.close()


# ── FastAPI Client Fixture ────────────────────────────────────────────────────
@pytest.fixture
async def e2e_client(e2e_db):
    """
    AsyncClient fixture injecting disposable database session into FastAPI app.
    Guarantees request isolation without cross-test data pollution.
    """
    async def _get_test_db():
        async with e2e_db["session_factory"]() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


# ── Database Session Helper Fixtures ──────────────────────────────────────────
@pytest.fixture
def e2e_sync_session(e2e_db):
    """Provides a synchronous session for test data preparation or inspection."""
    with e2e_db["sync_session_factory"]() as session:
        yield session


@pytest.fixture
async def e2e_async_session(e2e_db):
    """Provides an asynchronous session for test assertions."""
    async with e2e_db["session_factory"]() as session:
        yield session


# ── Mock YouTube API v3 Service Fixture ───────────────────────────────────────
@pytest.fixture
def mock_youtube_v3():
    """
    Comprehensive mock for Google YouTube API v3:
    - channels.list (returns verified test channels)
    - videos.insert (simulates resumable chunk uploads with progress)
    - videos.list (verifies status and privacyStatus)
    - thumbnails.set (thumbnail upload)
    - upload_short service mock
    """
    mock_service = MagicMock()
    mock_channels = MagicMock()
    mock_videos = MagicMock()
    mock_thumbnails = MagicMock()

    # Default Channel List Response
    mock_channels.list.return_value.execute.return_value = {
        "items": [{
            "id": "UC_E2E_MOCK_DESTINATION_001",
            "snippet": {
                "title": "ClipForge E2E Verified Channel",
                "thumbnails": {"default": {"url": "https://example.com/mock_thumb.jpg"}},
            },
        }]
    }

    # Resumable Upload Mock: 50% chunk then completion
    mock_chunk = MagicMock()
    mock_chunk.progress.return_value = 0.5
    mock_insert_req = MagicMock()
    mock_insert_req.next_chunk.side_effect = [
        (mock_chunk, None),
        (None, {"id": "yt_mock_uploaded_e2e_999"}),
    ]
    mock_videos.insert.return_value = mock_insert_req

    # Video State Check Mock
    mock_videos.list.return_value.execute.return_value = {
        "items": [{
            "id": "yt_mock_uploaded_e2e_999",
            "status": {"uploadStatus": "processed", "privacyStatus": "private"},
        }]
    }

    mock_thumbnails.set.return_value.execute.return_value = {"status": "ok"}

    mock_service.channels.return_value = mock_channels
    mock_service.videos.return_value = mock_videos
    mock_service.thumbnails.return_value = mock_thumbnails

    # Apply patches across publisher and consuming route modules
    patches = [
        patch("backend.services.publisher.get_youtube_client", return_value=mock_service),
        patch("backend.services.publisher.check_channel_authorization", return_value=True),
        patch("backend.services.publisher.upload_short", return_value={
            "id": "yt_mock_uploaded_e2e_999",
            "url": "https://www.youtube.com/shorts/yt_mock_uploaded_e2e_999",
            "privacy": "private",
        }),
    ]

    try:
        import backend.api.routes.youtube_channels as yt_routes
        patches.append(patch.object(yt_routes, "check_channel_authorization", return_value=True))
    except Exception:
        pass

    try:
        import backend.api.routes.publish as pub_routes
        if hasattr(pub_routes, "check_channel_authorization"):
            patches.append(patch.object(pub_routes, "check_channel_authorization", return_value=True))
    except Exception:
        pass

    for p in patches:
        p.start()

    yield {
        "service": mock_service,
        "channels": mock_channels,
        "videos": mock_videos,
        "thumbnails": mock_thumbnails,
        "video_id": "yt_mock_uploaded_e2e_999",
    }

    for p in reversed(patches):
        p.stop()
