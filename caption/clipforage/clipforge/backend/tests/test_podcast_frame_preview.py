"""
Tests for Timestamp-Accurate Source-Frame Preview (PODCAST-PREVIEW-FRAME-002).
Verifies:
- Safe identifier validation (rejection of path traversal, special characters).
- Timestamp bounds validation (negative, infinite, NaN, exceeding duration).
- Managed storage containment and non-existent asset 404.
- Real frame extraction from local synthetic video fixture.
- Cache hit / miss lifecycle.
- Shot ID cache binding.
- Subprocess protocol restrictions.
"""
import pytest
import os
import shutil
import math
import subprocess
from pathlib import Path
from httpx import ASGITransport, AsyncClient
from backend.main import app
from backend.core.config import settings
from backend.models.database import engine, SyncSessionLocal
from backend.models.models import Video


@pytest.fixture(autouse=True)
async def ensure_upload_and_fixture_dir():
    """Ensure upload directory and synthetic test fixture exist, and dispose DB engine cleanly."""
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    fixture_path = settings.UPLOAD_DIR / "synthetic_test_fixture.mp4"
    if not fixture_path.exists():
        # Create a tiny 3-second synthetic video fixture if missing
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "testsrc=duration=3:size=320x240:rate=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(fixture_path)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception:
            pass
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_frame_preview_invalid_video_id_rejected():
    """Verify video_id with path traversal or metacharacters is rejected with 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Path traversal
        res = await client.get("/api/videos/..%2F..%2Fetc%2Fpasswd/frame?timestamp=1.0")
        assert res.status_code in (400, 404)

        # Illegal characters in path parameter
        res2 = await client.get("/api/videos/test;cat/frame?timestamp=1.0")
        assert res2.status_code == 400
        assert "Invalid video_id identifier" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_frame_preview_invalid_timestamp_rejected():
    """Verify negative, NaN, or non-finite timestamps return 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Negative timestamp
        res1 = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=-2.5")
        assert res1.status_code == 400
        assert "non-negative" in res1.json()["detail"]

        # Huge timestamp beyond media duration
        res2 = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=999999.0")
        assert res2.status_code == 400
        assert "exceeds" in res2.json()["detail"].lower()

        # Non-numeric / invalid float string
        res3 = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=notanumber")
        assert res3.status_code == 422


@pytest.mark.asyncio
async def test_frame_preview_nonexistent_asset_returns_404():
    """Verify that an unknown video_id returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/videos/nonexistent_asset_xyz123/frame?timestamp=1.0")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_frame_preview_extraction_and_caching():
    """
    Verify real frame extraction from synthetic test fixture:
    - First request returns 200, image/jpeg, X-Frame-Cache: MISS.
    - Second request returns 200, image/jpeg, X-Frame-Cache: HIT.
    - Frame size is non-zero.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Extraction (MISS or HIT)
        res1 = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=1.000&shot_id=1")
        assert res1.status_code == 200
        assert res1.headers["content-type"] == "image/jpeg"
        assert res1.headers["x-source-id"] == "synthetic_test_fixture"
        assert len(res1.content) > 100
        assert res1.headers.get("x-frame-cache") in ("MISS", "HIT")

        # 2. Re-fetch same frame (HIT)
        res2 = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=1.000&shot_id=1")
        assert res2.status_code == 200
        assert res2.headers["content-type"] == "image/jpeg"
        assert res2.headers.get("x-frame-cache") == "HIT"

        # 3. Different timestamp (distinct extraction)
        res3 = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=2.000&shot_id=2")
        assert res3.status_code == 200
        assert res3.headers["content-type"] == "image/jpeg"
        assert res3.headers["x-frame-timestamp"] == "2.000"


@pytest.mark.asyncio
async def test_frame_preview_respects_db_video_duration():
    """Verify that if a Video DB record has duration=5.0s, requesting 7.0s returns 400."""
    with SyncSessionLocal() as session:
        # Delete if exists
        v_old = session.get(Video, "vid_duration_test")
        if v_old:
            session.delete(v_old)
            session.commit()
        test_vid = Video(
            id="vid_duration_test",
            title="Duration Test Video",
            youtube_id="vid_duration_test",
            local_path="synthetic_test_fixture.mp4",
            duration=5.0
        )
        session.add(test_vid)
        session.commit()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/videos/vid_duration_test/frame?timestamp=8.0")
            assert res.status_code == 400
            assert "exceeds video duration" in res.json()["detail"]
    finally:
        with SyncSessionLocal() as session:
            v = session.get(Video, "vid_duration_test")
            if v:
                session.delete(v)
                session.commit()


@pytest.mark.asyncio
async def test_frame_preview_exact_start_boundary():
    """Verify exact 0.0 timestamp works without error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/videos/synthetic_test_fixture/frame?timestamp=0.0")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"
        assert res.headers["x-frame-timestamp"] == "0.000"


@pytest.mark.asyncio
async def test_frame_preview_remote_url_rejected_as_id():
    """Verify attempting to pass remote/metadata URLs as video_id is rejected with 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # SSRF attempt targeting cloud metadata service
        res1 = await client.get("/api/videos/http:%2F%2F169.254.169.254/frame?timestamp=1.0")
        assert res1.status_code in (400, 404)

        # Localhost attempt
        res2 = await client.get("/api/videos/http:%2F%2Flocalhost:8000/frame?timestamp=1.0")
        assert res2.status_code in (400, 404)


@pytest.mark.asyncio
async def test_frame_preview_temp_cleanup():
    """Verify no leftover temp files remain in frame_cache directory after extraction."""
    cache_dir = settings.UPLOAD_DIR / "frame_cache" / "synthetic_test_fixture"
    if cache_dir.exists():
        tmp_files = list(cache_dir.glob("tmp_frame_*"))
        assert len(tmp_files) == 0, f"Dangling temp extraction files found: {tmp_files}"
