"""
backend/tests/test_challenger_m2_adversarial.py
===============================================
Empirical Challenger 2 Adversarial Stress Test Suite for Milestone M2:
1. Ingestion Fuzzing against bare FastAPI app (POST /api/videos/url & POST /api/videos/upload):
   - Negative coordinates
   - Overflow coordinates (x+w > 1.0, y+h > 1.0)
   - Sub-0.05 dimensions
   - Non-finite coordinates (NaN, Infinity, -Infinity)
   - Inverted boxes (negative width/height)
   - Malformed JSON strings, empty JSON {}, missing required fields, invalid presets
   - Verification that NO invalid payload silently defaults to center_crop
2. Temporary File Disk Leak Verification on upload failure:
   - Verification that files in settings.UPLOAD_DIR are unlinked on HTTP 422
3. Lossless Persistence & DB Schema Invariant:
   - High-precision float coordinates in Job.config
   - Zero Alembic migration files
"""

import asyncio
import io
import json
import math
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.main import app
from backend.core.config import settings
from backend.models.database import get_db, SyncSessionLocal
from backend.models.models import Job, JobStatus
from backend.tests.gaming_test_fixtures import generate_synthetic_video


# NullPool engine and sessionmaker to prevent Windows cross-loop leaks
nullpool_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
nullpool_session_factory = async_sessionmaker(nullpool_engine, expire_on_commit=False, autoflush=False)


async def override_get_db():
    async with nullpool_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest.fixture(autouse=True)
def setup_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="module", autouse=True)
def cleanup_nullpool():
    yield
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(nullpool_engine.dispose())
        loop.close()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_test_jobs():
    def _do_clean():
        try:
            with SyncSessionLocal() as session:
                jobs = session.query(Job).filter(Job.is_test == True).all()
                for j in jobs:
                    session.delete(j)
                session.commit()
        except Exception:
            pass

    _do_clean()
    yield
    _do_clean()


@pytest.fixture(scope="module")
def mock_external():
    with patch("backend.services.queue_manager.dispatch_celery_job", return_value="mock-celery-challenger"), \
         patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)):
        yield


@pytest.fixture
async def direct_client(mock_external):
    """Direct AsyncClient connected directly to bare FastAPI app (NO test middleware)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="module")
def sample_valid_mp4(tmp_path_factory) -> Path:
    tmp_path = tmp_path_factory.mktemp("challenger_mp4")
    mp4_path = tmp_path / "valid_test.mp4"
    return generate_synthetic_video(mp4_path, 320, 240, duration=0.5, fps=24, faststart=True)


# ==============================================================================
# SECTION 1: ADVERSARIAL INGESTION FUZZING PAYLOAD MATRIX
# ==============================================================================

ADVERSARIAL_PAYLOADS = [
    # 1. Negative coordinates
    (
        "negative_x",
        {"gameplay_roi": {"x": -0.01, "y": 0.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "negative_y",
        {"gameplay_roi": {"x": 0.0, "y": -1.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "negative_facecam_x",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, "facecam_roi": {"x": -0.5, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "negative_facecam_output_y",
        {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_output_rect": {"x": 0.1, "y": -0.1, "width": 0.3, "height": 0.3},
        },
    ),
    # 2. Overflow coordinates (x+w > 1.0 or y+h > 1.0)
    (
        "overflow_x_width",
        {"gameplay_roi": {"x": 0.9, "y": 0.0, "width": 0.2, "height": 1.0}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "overflow_y_height",
        {"gameplay_roi": {"x": 0.0, "y": 0.8, "width": 1.0, "height": 0.3}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "overflow_facecam_output",
        {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_output_rect": {"x": 0.8, "y": 0.8, "width": 0.3, "height": 0.3},
        },
    ),
    (
        "out_of_bounds_x_exceeds_1",
        {"gameplay_roi": {"x": 1.5, "y": 0.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    # 3. Sub-0.05 dimensions
    (
        "sub_min_width_gameplay",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 0.049, "height": 1.0}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "sub_min_height_gameplay",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 0.01}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "sub_min_facecam_width",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.001, "height": 0.25}},
    ),
    (
        "sub_min_output_rect_height",
        {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_output_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.049},
        },
    ),
    # 4. Non-finite coordinates
    (
        "nan_coordinate_string",
        {"gameplay_roi": {"x": "NaN", "y": 0.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "infinity_coordinate_string",
        {"gameplay_roi": {"x": "Infinity", "y": 0.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "neg_infinity_coordinate_string",
        {"gameplay_roi": {"x": "-Infinity", "y": 0.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "null_coordinate",
        {"gameplay_roi": {"x": None, "y": 0.0, "width": 0.5, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    # 5. Inverted boxes (negative width/height)
    (
        "inverted_width",
        {"gameplay_roi": {"x": 0.5, "y": 0.0, "width": -0.2, "height": 0.5}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    (
        "inverted_height",
        {"gameplay_roi": {"x": 0.0, "y": 0.5, "width": 0.5, "height": -0.1}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}},
    ),
    # 6. Malformed JSON strings and non-dict JSON
    (
        "malformed_json_syntax",
        "NOT_A_JSON_STRING {x=1}",
    ),
    (
        "json_array_instead_of_object",
        "[1, 2, 3]",
    ),
    (
        "json_primitive_number",
        "12345",
    ),
    # 7. Empty JSON and missing required fields
    (
        "empty_json_dict",
        {},
    ),
    (
        "empty_json_dict_string",
        "{}",
    ),
    (
        "missing_gameplay_roi",
        {"facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}, "facecam_placement": "top-right"},
    ),
    (
        "missing_facecam_roi",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}},
    ),
    (
        "mode_gaming_only_empty_rois",
        {"mode": "gaming"},
    ),
    # 8. Invalid presets
    (
        "invalid_preset_center",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}, "facecam_placement": "center"},
    ),
    (
        "invalid_preset_unknown",
        {"gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25}, "facecam_placement": "floating_facecam"},
    ),
]


@pytest.mark.parametrize("payload_id,payload", ADVERSARIAL_PAYLOADS)
async def test_adversarial_url_ingestion_rejected_422(
    direct_client: AsyncClient, payload_id: str, payload: Any
):
    """
    Empirical fuzzing of POST /api/videos/url directly against FastAPI app.
    EVERY malformed or boundary-violating payload MUST strictly return HTTP 422
    and NEVER silently default to center_crop or succeed with 200.
    """
    raw_payload = payload if isinstance(payload, str) else json.dumps(payload)
    resp = await direct_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": raw_payload,
        },
    )
    assert resp.status_code == 422, (
        f"[ADVERSARIAL FAULT in /api/videos/url] Payload '{payload_id}' was NOT rejected with HTTP 422. "
        f"Got status {resp.status_code}: {resp.text}"
    )


@pytest.mark.parametrize("payload_id,payload", ADVERSARIAL_PAYLOADS)
async def test_adversarial_upload_ingestion_rejected_422(
    direct_client: AsyncClient, sample_valid_mp4: Path, payload_id: str, payload: Any
):
    """
    Empirical fuzzing of POST /api/videos/upload directly against FastAPI app.
    EVERY malformed or boundary-violating payload MUST strictly return HTTP 422
    and NEVER silently default to center_crop or succeed with 200.
    """
    raw_payload = payload if isinstance(payload, str) else json.dumps(payload)
    with open(sample_valid_mp4, "rb") as f:
        file_bytes = f.read()

    resp = await direct_client.post(
        "/api/videos/upload",
        files={"file": ("test_upload.mp4", file_bytes, "video/mp4")},
        data={
            "is_test": "true",
            "gaming_layout": raw_payload,
        },
    )
    assert resp.status_code == 422, (
        f"[ADVERSARIAL FAULT in /api/videos/upload] Payload '{payload_id}' was NOT rejected with HTTP 422. "
        f"Got status {resp.status_code}: {resp.text}"
    )


# ==============================================================================
# SECTION 2: TEMPORARY FILE DISK LEAK VERIFICATION
# ==============================================================================

async def test_upload_rejection_cleans_temporary_file(
    direct_client: AsyncClient, sample_valid_mp4: Path
):
    """
    Verify that when POST /api/videos/upload rejects an invalid gaming_layout with HTTP 422,
    the uploaded temporary file in settings.UPLOAD_DIR is immediately unlinked and NOT orphaned.
    """
    upload_dir = settings.UPLOAD_DIR.resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Record files on disk before upload
    files_before = set(upload_dir.rglob("*.mp4"))

    bad_layout = {
        "gameplay_roi": {"x": -0.5, "y": 0.0, "width": 0.5, "height": 0.5},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
    }

    with open(sample_valid_mp4, "rb") as f:
        file_bytes = f.read()

    resp = await direct_client.post(
        "/api/videos/upload",
        files={"file": ("leak_test.mp4", file_bytes, "video/mp4")},
        data={
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    # Record files on disk after upload
    files_after = set(upload_dir.rglob("*.mp4"))

    # Assert no new .mp4 files were left behind
    leaked_files = files_after - files_before
    assert len(leaked_files) == 0, (
        f"[DISK LEAK DETECTED] Temporary upload file was orphaned on disk after HTTP 422: {leaked_files}"
    )


# ==============================================================================
# SECTION 3: LOSSLESS PERSISTENCE & DB SCHEMA INVARIANT
# ==============================================================================

async def test_lossless_persistence_high_precision_floats(direct_client: AsyncClient):
    """
    Verify that Job.config retains exact high-precision float coordinates without
    rounding or truncation errors across JSON serialization and database storage.
    """
    high_precision_layout = {
        "mode": "gaming",
        "gameplay_roi": {
            "x": 0.1234567,
            "y": 0.0987654,
            "width": 0.8123456,
            "height": 0.9012345,
        },
        "facecam_roi": {
            "x": 0.6543210,
            "y": 0.0432109,
            "width": 0.2876543,
            "height": 0.2345678,
        },
        "facecam_placement": "top-right",
        "facecam_output_rect": {
            "x": 0.6012345,
            "y": 0.0345678,
            "width": 0.3567890,
            "height": 0.2109876,
        },
        "canvas_width": 1080,
        "canvas_height": 1920,
    }

    resp = await direct_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(high_precision_layout),
        },
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    job_id = resp.json()["job_id"]

    # Read Job directly from database
    with SyncSessionLocal() as session:
        job = session.query(Job).filter(Job.id == job_id).first()
        assert job is not None, f"Job {job_id} not found in DB"
        assert job.config is not None, "Job.config is None"

        parsed = json.loads(job.config)
        assert parsed["reframe_mode"] == "gaming"
        assert parsed["mode"] == "gaming"
        persisted_layout = parsed["gaming_layout"]

        # Check precision across all coordinates (tolerance 1e-6)
        gp = persisted_layout["gameplay_roi"]
        assert abs(gp["x"] - 0.1234567) < 1e-6, f"gameplay.x precision lost: {gp['x']}"
        assert abs(gp["y"] - 0.0987654) < 1e-6, f"gameplay.y precision lost: {gp['y']}"
        assert abs(gp["width"] - 0.8123456) < 1e-6, f"gameplay.width precision lost: {gp['width']}"
        assert abs(gp["height"] - 0.9012345) < 1e-6, f"gameplay.height precision lost: {gp['height']}"

        fc = persisted_layout["facecam_roi"]
        assert abs(fc["x"] - 0.6543210) < 1e-6, f"facecam.x precision lost: {fc['x']}"
        assert abs(fc["y"] - 0.0432109) < 1e-6, f"facecam.y precision lost: {fc['y']}"
        assert abs(fc["width"] - 0.2876543) < 1e-6, f"facecam.width precision lost: {fc['width']}"
        assert abs(fc["height"] - 0.2345678) < 1e-6, f"facecam.height precision lost: {fc['height']}"

        fo = persisted_layout["facecam_output_rect"]
        assert abs(fo["x"] - 0.6012345) < 1e-6, f"facecam_output.x precision lost: {fo['x']}"
        assert abs(fo["y"] - 0.0345678) < 1e-6, f"facecam_output.y precision lost: {fo['y']}"
        assert abs(fo["width"] - 0.3567890) < 1e-6, f"facecam_output.width precision lost: {fo['width']}"
        assert abs(fo["height"] - 0.2109876) < 1e-6, f"facecam_output.height precision lost: {fo['height']}"


def test_zero_alembic_migrations_added():
    """
    Verify that NO new Alembic migration files were added in alembic/versions.
    """
    import subprocess
    res = subprocess.run(
        ["git", "status", "--porcelain", "alembic/versions/", "backend/alembic/versions/"],
        cwd=str(settings.BASE_DIR),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"Found untracked/modified Alembic migrations: {res.stdout}"
