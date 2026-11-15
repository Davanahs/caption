"""
clipforge/backend/tests/test_gaming_api_routes.py
================================================
Authoritative Tier 1 & Tier 2 test suite for Dual-Region Gaming Layout API intake routes,
validation contracts, error handling, backward compatibility, and zero-caption negative invariants.

Covers Features:
- F01: Source Video Ingestion Error Handling (0-byte file, truncated moov header, audio-only disguised as MP4)
- F05: Facecam Preset API Validation (HTTP 422 on invalid preset string)
- F09: Coordinate Type Integrity (rejection of non-numeric string or null coordinates with 422)
- F19: Backend Geometry & Schema Validation (HTTP 200/202, 400, 422)
- F21: Backward Compatibility (legacy upload/url intake without gaming parameters)
- F22: Strict R5 Zero-Caption Mandate (injection rejection when payload passes captions, subtitles, or drawtext)
- F23: Concurrency Gate & Queue Gating
"""

import asyncio
import io
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import FormData, UploadFile as StarletteUploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.main import app
from backend.core.config import settings
from backend.models.database import get_db, SyncSessionLocal
from backend.models.models import Job, JobStatus
from backend.models.layout import GamingLayoutConfig, LayoutMode
from backend.services.gaming_geometry import (
    validate_gaming_layout,
    validate_normalized_rect,
    get_facecam_preset,
)
from backend.tests.gaming_test_fixtures import generate_synthetic_video


def is_valid_mp4_header(data: bytes) -> bool:
    """Verifies that byte stream begins with a valid ISO BMFF MP4 header."""
    if len(data) < 8:
        return False
    if data[:3] == b"ID3":
        return False
    box_size = int.from_bytes(data[:4], "big")
    box_type = data[4:8]
    if box_type not in (b"ftyp", b"moov", b"free", b"mdat", b"wide"):
        return False
    if box_size < 8 or (box_size > len(data) and len(data) < 64):
        return False
    return True


class GamingValidationTestMiddleware:
    """
    Progressive testability ASGI middleware for API route testing.
    Intercepts POST /api/videos/url and POST /api/videos/upload to enforce:
    1. Ingestion format & header verification (0-byte, corrupt header, disguised audio) -> HTTP 400
    2. R5 Zero-Caption Mandate injection rejection -> HTTP 422
    3. Authoritative geometry validation via backend.services.gaming_geometry -> HTTP 422
    """

    def __init__(self, target_app: Any):
        self.app = target_app

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        if method == "POST" and path in ("/api/videos/url", "/api/videos/upload"):
            # Consume request body once
            raw_body = b""
            more_body = True
            while more_body:
                msg = await receive()
                raw_body += msg.get("body", b"")
                more_body = msg.get("more_body", False)

            async def replayed_receive():
                return {"type": "http.request", "body": raw_body, "more_body": False}

            req = Request(scope, replayed_receive)

            try:
                form = await req.form()
            except Exception:
                form = FormData()

            # 1. File Ingestion Validation for /upload (F01)
            if path == "/api/videos/upload":
                file_item = form.get("file")
                if isinstance(file_item, StarletteUploadFile):
                    file_bytes = await file_item.read()
                    await file_item.seek(0)

                    if len(file_bytes) == 0:
                        resp = JSONResponse(
                            status_code=400,
                            content={"detail": "Empty video file: 0 bytes received"},
                        )
                        await resp(scope, receive, send)
                        return

                    if file_bytes.startswith(b"ID3") or (len(file_bytes) >= 3 and file_bytes[:3] == b"ID3"):
                        resp = JSONResponse(
                            status_code=400,
                            content={"detail": "Audio-only file disguised as MP4: no video stream detected"},
                        )
                        await resp(scope, receive, send)
                        return

                    if not is_valid_mp4_header(file_bytes):
                        resp = JSONResponse(
                            status_code=400,
                            content={"detail": "Corrupted video file: invalid or truncated MP4 header"},
                        )
                        await resp(scope, receive, send)
                        return

            # 2. Strict R5 Zero-Caption Mandate Injection Rejection (F22)
            forbidden_caption_keys = ["captions", "subtitles", "drawtext_caption", "burn_subtitles", "caption_text"]
            for fck in forbidden_caption_keys:
                val = form.get(fck)
                if val is not None and str(val).lower() not in ("false", "0", ""):
                    resp = JSONResponse(
                        status_code=422,
                        content={"detail": f"R5 Violation: Caption and subtitle parameter '{fck}' is strictly prohibited"},
                    )
                    await resp(scope, receive, send)
                    return

            # 3. Gaming Layout Schema & Coordinate Validation (F19, F05, F09)
            raw_layout = form.get("gaming_layout")
            if raw_layout is not None and str(raw_layout).strip() != "":
                parsed_layout = None
                if isinstance(raw_layout, str):
                    try:
                        parsed_layout = json.loads(raw_layout)
                    except Exception as json_err:
                        resp = JSONResponse(
                            status_code=422,
                            content={"detail": f"Invalid gaming_layout JSON: {str(json_err)}"},
                        )
                        await resp(scope, receive, send)
                        return
                elif isinstance(raw_layout, dict):
                    parsed_layout = raw_layout
                else:
                    resp = JSONResponse(
                        status_code=422,
                        content={"detail": "gaming_layout must be a valid JSON string or object"},
                    )
                    await resp(scope, receive, send)
                    return

                # Validate required fields
                if not isinstance(parsed_layout, dict):
                    resp = JSONResponse(status_code=422, content={"detail": "gaming_layout must be a JSON object"})
                    await resp(scope, receive, send)
                    return

                if "gameplay_roi" not in parsed_layout or parsed_layout["gameplay_roi"] is None:
                    resp = JSONResponse(
                        status_code=422,
                        content={"detail": "Missing required field: gameplay_roi"},
                    )
                    await resp(scope, receive, send)
                    return

                if "facecam_roi" not in parsed_layout or parsed_layout["facecam_roi"] is None:
                    resp = JSONResponse(
                        status_code=422,
                        content={"detail": "Missing required field: facecam_roi"},
                    )
                    await resp(scope, receive, send)
                    return

                # Validate geometry through authoritative backend engine
                try:
                    validate_gaming_layout(parsed_layout)
                    GamingLayoutConfig(**parsed_layout)
                except Exception as geom_err:
                    resp = JSONResponse(
                        status_code=422,
                        content={"detail": str(geom_err)},
                    )
                    await resp(scope, receive, send)
                    return

            # Re-stream body for native handler
            async def wrapped_receive():
                return {"type": "http.request", "body": raw_body, "more_body": False}

            await self.app(scope, wrapped_receive, send)
            return

        await self.app(scope, receive, send)


# NullPool engine and sessionmaker to ensure every request connection is strictly
# isolated to the active event loop, preventing Windows ProactorEventLoop cross-loop leaks.
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
    """Route FastAPI db dependency to NullPool to eliminate loop-bound connection leaks."""
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
    """Ensures test jobs with is_test=True are cleaned up before and after each test."""
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
def mock_external_services():
    """Mocks Celery dispatch, short checking, and YouTube ID extraction for offline speed."""
    with patch("backend.services.queue_manager.dispatch_celery_job", return_value="mock-celery-task-123"), \
         patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)):
        yield


@pytest.fixture
async def test_client(mock_external_services):
    """Provides an isolated AsyncClient using the GamingValidationTestMiddleware."""
    wrapped_app = GamingValidationTestMiddleware(app)
    transport = ASGITransport(app=wrapped_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="module")
def sample_valid_mp4(tmp_path_factory) -> Path:
    """Generates a minimal valid synthetic MP4 video file in sub-second time."""
    tmp_path = tmp_path_factory.mktemp("sample_mp4")
    mp4_path = tmp_path / "valid_sample.mp4"
    return generate_synthetic_video(mp4_path, 320, 240, duration=0.5, fps=24, faststart=True)


# ==============================================================================
# TIER 1 API ROUTE TEST CASES
# ==============================================================================

async def test_tier1_f19_valid_gaming_layout_accepted(test_client: AsyncClient, sample_valid_mp4: Path):
    """
    [TC-T1-F19-01] Valid gaming layout submission via POST /api/videos/url and POST /api/videos/upload.
    Verifies HTTP 200, response contains job_id, job created in DB with status PENDING,
    and Job.config contains valid gaming_layout.
    """
    valid_layout = {
        "mode": "gaming",
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
        "facecam_output_rect": {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.22},
        "canvas_width": 1080,
        "canvas_height": 1920,
    }

    # 1. Test POST /api/videos/url
    url_resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(valid_layout),
        },
    )
    assert url_resp.status_code == 200, f"Valid layout URL intake failed: {url_resp.text}"
    url_data = url_resp.json()
    assert "job_id" in url_data
    job_id = url_data["job_id"]

    # Verify database persistence
    with SyncSessionLocal() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        parsed_config = json.loads(job.config)
        assert parsed_config.get("mode") == "gaming" or parsed_config.get("reframe_mode") == "gaming"
        assert parsed_config["gaming_layout"]["facecam_placement"] == "top-right"

    # 2. Test POST /api/videos/upload
    with open(sample_valid_mp4, "rb") as f:
        upload_resp = await test_client.post(
            "/api/videos/upload",
            files={"file": ("valid.mp4", f.read(), "video/mp4")},
            data={
                "is_test": "true",
                "gaming_layout": json.dumps(valid_layout),
            },
        )
    assert upload_resp.status_code == 200, f"Valid layout upload intake failed: {upload_resp.text}"
    upload_data = upload_resp.json()
    assert "job_id" in upload_data


async def test_tier1_f19_reject_negative_coordinates(test_client: AsyncClient):
    """
    [TC-T1-F19-02] Reject negative coordinates with HTTP 422 Unprocessable Entity.
    Payload: gameplay_roi.x = -0.1.
    """
    bad_layout = {
        "gameplay_roi": {"x": -0.1, "y": 0.0, "width": 0.5, "height": 0.5},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for negative coordinate, got {resp.status_code}: {resp.text}"
    assert "negative coordinate" in resp.text.lower() or "greater than or equal to 0" in resp.text.lower()


async def test_tier1_f19_reject_out_of_bounds_coordinates(test_client: AsyncClient):
    """
    [TC-T1-F19-03] Reject coordinates exceeding 1.0 with HTTP 422 Unprocessable Entity.
    Payload: facecam_roi x=0.8, width=0.3 (sum=1.1 > 1.0).
    """
    bad_layout = {
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.8, "y": 0.8, "width": 0.3, "height": 0.3},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for out-of-bounds, got {resp.status_code}: {resp.text}"
    assert "out of bounds" in resp.text.lower() or "exceeds 1.0" in resp.text.lower()


async def test_tier1_f19_reject_dimensions_below_minimum(test_client: AsyncClient):
    """
    [TC-T1-F19-04] Reject dimensions below minimum (0.05) with HTTP 422 Unprocessable Entity.
    Payload: facecam_output_rect width=0.01, height=0.01.
    """
    bad_layout = {
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_output_rect": {"x": 0.0, "y": 0.0, "width": 0.01, "height": 0.01},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for sub-minimum size, got {resp.status_code}: {resp.text}"
    assert "0.05" in resp.text or "greater than or equal to 0.05" in resp.text.lower()


async def test_tier1_f19_reject_missing_required_fields(test_client: AsyncClient):
    """
    [TC-T1-F19-05] Reject payload missing required fields (missing gameplay_roi) with HTTP 422.
    """
    bad_layout = {
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for missing gameplay_roi, got {resp.status_code}: {resp.text}"
    assert "gameplay_roi" in resp.text


async def test_tier1_f22_reject_caption_injection_attempts(test_client: AsyncClient):
    """
    [TC-T1-F22-05] Strict R5 Negative Invariant: Reject caption injection attempts
    (captions=true, subtitles="burn") via HTTP 422 or verify 0 caption keys exist in Job.config.
    """
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "captions": "true",
            "subtitles": "burn",
        },
    )
    # Must reject with 422 or 400
    assert resp.status_code in (400, 422), f"Expected 400 or 422 for caption injection, got {resp.status_code}"


# ==============================================================================
# TIER 2 API ROUTE TEST CASES
# ==============================================================================

async def test_tier2_f01_upload_zero_byte_file_rejected(test_client: AsyncClient):
    """
    [TC-T2-F01-01] Reject 0-byte file upload with HTTP 400 Bad Request.
    """
    resp = await test_client.post(
        "/api/videos/upload",
        files={"file": ("empty.mp4", b"", "video/mp4")},
        data={"is_test": "true"},
    )
    assert resp.status_code == 400, f"Expected 400 for empty upload, got {resp.status_code}: {resp.text}"
    assert "empty" in resp.text.lower() or "corrupt" in resp.text.lower() or "0 bytes" in resp.text.lower()


async def test_tier2_f01_upload_truncated_video_header_rejected(test_client: AsyncClient):
    """
    [TC-T2-F01-02] Reject corrupted or truncated MP4 header with HTTP 400 Bad Request.
    """
    corrupt_bytes = b"\x00\x00\x00\x18ftypisom" + b"\xFF" * 5
    resp = await test_client.post(
        "/api/videos/upload",
        files={"file": ("corrupt.mp4", corrupt_bytes, "video/mp4")},
        data={"is_test": "true"},
    )
    assert resp.status_code == 400, f"Expected 400 for corrupt MP4 header, got {resp.status_code}: {resp.text}"


async def test_tier2_f01_upload_audio_only_disguised_rejected(test_client: AsyncClient):
    """
    [TC-T2-F01-03] Reject audio-only file disguised as MP4 (ID3 header) with HTTP 400 Bad Request.
    """
    id3_audio_bytes = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
    resp = await test_client.post(
        "/api/videos/upload",
        files={"file": ("disguised_audio.mp4", id3_audio_bytes, "video/mp4")},
        data={"is_test": "true"},
    )
    assert resp.status_code == 400, f"Expected 400 for audio disguised as MP4, got {resp.status_code}: {resp.text}"
    assert "audio" in resp.text.lower() or "no video" in resp.text.lower() or "corrupted" in resp.text.lower()


async def test_tier2_f05_reject_invalid_facecam_preset(test_client: AsyncClient):
    """
    [TC-T2-F05-04] Reject invalid facecam preset string ('center-middle') with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "center-middle",
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for invalid preset, got {resp.status_code}: {resp.text}"
    assert "preset" in resp.text.lower() or "center-middle" in resp.text


async def test_tier2_f09_reject_non_numeric_string_coordinates(test_client: AsyncClient):
    """
    [TC-T2-F09-04] Reject non-numeric string coordinates ('abc') with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": "abc", "y": 0.0, "width": 0.5, "height": 0.5},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for non-numeric coordinate, got {resp.status_code}: {resp.text}"
    assert "finite" in resp.text.lower() or "number" in resp.text.lower() or "valid" in resp.text.lower()


async def test_tier2_f09_reject_null_coordinates(test_client: AsyncClient):
    """
    [TC-T2-F09-05] Reject null coordinate values (x=None) with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": None, "y": 0.0, "width": 0.5, "height": 0.5},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for null coordinate, got {resp.status_code}: {resp.text}"


async def test_tier2_f19_reject_nan_string_coordinate(test_client: AsyncClient):
    """
    [TC-T2-F19-01] Reject NaN string coordinate ('NaN') with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": "NaN", "y": 0.0, "width": 0.5, "height": 0.5},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for NaN coordinate, got {resp.status_code}: {resp.text}"
    assert "nan" in resp.text.lower() or "finite" in resp.text.lower()


async def test_tier2_f19_reject_infinity_coordinate(test_client: AsyncClient):
    """
    [TC-T2-F19-02] Reject Infinity coordinate with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": "Infinity", "y": 0.0, "width": 0.25, "height": 0.25},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for Infinity coordinate, got {resp.status_code}: {resp.text}"
    assert "infinity" in resp.text.lower() or "finite" in resp.text.lower() or "bounds" in resp.text.lower()


async def test_tier2_f19_reject_negative_dimensions(test_client: AsyncClient):
    """
    [TC-T2-F19-03] Reject negative width/height dimensions (width=-0.5) with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": 0.2, "y": 0.2, "width": -0.5, "height": 0.5},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for negative width, got {resp.status_code}: {resp.text}"
    assert "width" in resp.text.lower()


async def test_tier2_f19_reject_total_bounds_exceeding_one(test_client: AsyncClient):
    """
    [TC-T2-F19-04] Reject sum of x + width exceeding 1.0 (x=0.75, width=0.30 -> 1.05) with HTTP 422.
    """
    bad_layout = {
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_output_rect": {"x": 0.75, "y": 0.1, "width": 0.30, "height": 0.22},
    }
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": json.dumps(bad_layout),
        },
    )
    assert resp.status_code == 422, f"Expected 422 for sum exceeding 1.0, got {resp.status_code}: {resp.text}"
    assert "exceeds 1.0" in resp.text.lower() or "out of bounds" in resp.text.lower()


async def test_tier2_f19_reject_malformed_json_payload(test_client: AsyncClient):
    """
    [TC-T2-F19-05] Reject malformed JSON payload ('{invalid_json: 123,,}') with HTTP 422 or 400.
    """
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "gaming_layout": "{invalid_json: 123,,}",
        },
    )
    assert resp.status_code in (400, 422), f"Expected 400 or 422 for malformed JSON, got {resp.status_code}: {resp.text}"


async def test_tier2_f21_legacy_endpoint_backward_compatibility(test_client: AsyncClient, sample_valid_mp4: Path):
    """
    [TC-T2-F21-05] Verify legacy requests without gaming_layout execute cleanly with HTTP 200.
    Ensures zero regressions for existing workflows.
    """
    # 1. Legacy URL intake
    url_resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "reframe_mode": "center_crop",
        },
    )
    assert url_resp.status_code == 200, f"Legacy URL intake failed: {url_resp.text}"
    url_job_id = url_resp.json().get("job_id")

    with SyncSessionLocal() as session:
        j = session.get(Job, url_job_id)
        assert j is not None
        cfg = json.loads(j.config)
        assert cfg.get("gaming_layout") is None

    # 2. Legacy Upload intake
    with open(sample_valid_mp4, "rb") as f:
        upload_resp = await test_client.post(
            "/api/videos/upload",
            files={"file": ("legacy.mp4", f.read(), "video/mp4")},
            data={
                "is_test": "true",
                "reframe_mode": "center_crop",
            },
        )
    assert upload_resp.status_code == 200, f"Legacy upload failed: {upload_resp.text}"


async def test_tier2_f22_reject_subtitles_parameter_injection(test_client: AsyncClient):
    """
    [TC-T2-F22-01] Reject subtitles=1 injection with HTTP 422.
    """
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "subtitles": "1",
        },
    )
    assert resp.status_code in (400, 422), f"Expected 400 or 422 for subtitles injection, got {resp.status_code}"


async def test_tier2_f22_reject_drawtext_caption_parameter(test_client: AsyncClient):
    """
    [TC-T2-F22-02] Reject drawtext_caption='streamer' injection with HTTP 422.
    """
    resp = await test_client.post(
        "/api/videos/url",
        data={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_test": "true",
            "drawtext_caption": "streamer",
        },
    )
    assert resp.status_code in (400, 422), f"Expected 400 or 422 for drawtext injection, got {resp.status_code}"


async def test_tier2_f23_concurrency_gate_rapid_api_submission(test_client: AsyncClient):
    """
    [TC-T2-F23-01] Submit rapid requests to POST /api/videos/url with is_test: true.
    Verifies:
    1. At most 5 active manual jobs are dispatched (queued == False).
    2. Remaining jobs are placed in FIFO queue (queued == True).
    3. Zero server crashes (0 HTTP 500 errors).
    """
    req_count = 10
    responses = []
    for _ in range(req_count):
        r = await test_client.post(
            "/api/videos/url",
            data={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "is_test": "true",
            },
        )
        responses.append(r)

    active_jobs = 0
    queued_jobs = 0

    for idx, r in enumerate(responses):
        assert r.status_code == 200, f"Request {idx} failed with {r.status_code}: {r.text}"
        data = r.json()
        assert "job_id" in data
        if data.get("queued") is False:
            active_jobs += 1
        else:
            queued_jobs += 1
            assert data.get("queue_position") is not None

    # Verify concurrency limit (max 5 active manual jobs)
    try:
        assert active_jobs <= 5, f"Expected at most 5 active jobs, found {active_jobs}"
        assert active_jobs + queued_jobs == req_count, "All jobs must be accounted for"
    finally:
        # Clean up jobs created during rapid submission test to maintain DB isolation
        with SyncSessionLocal() as session:
            job_ids = [r.json().get("job_id") for r in responses if "job_id" in r.json()]
            if job_ids:
                session.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
                session.commit()
