"""
Focused unit tests for DEF-API-01 — YouTube URL validation parity.
Tests extract_youtube_id and FastAPI endpoint integration across all supported and rejected formats.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.services.downloader import extract_youtube_id
from backend.main import app


EXPECTED_ID = "dQw4w9WgXcQ"


# ── 1. Supported YouTube Watch URLs ──────────────────────────────────────────

def test_extract_youtube_id_supported_watch_formats():
    watch_cases = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ",
        "www.youtube.com/watch?v=dQw4w9WgXcQ",
        "youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch/?v=dQw4w9WgXcQ",
    ]
    for url in watch_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for watch URL: {url}"


def test_extract_youtube_id_query_parameter_ordering():
    ordering_cases = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?t=42s&v=dQw4w9WgXcQ&ab_channel=RickAstley",
        "https://www.youtube.com/watch?list=PLxyz&v=dQw4w9WgXcQ&index=1",
        "https://www.youtube.com/watch?themeRefresh=1&feature=youtu.be&v=dQw4w9WgXcQ&si=123",
    ]
    for url in ordering_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for query ordering: {url}"


# ── 2. Supported YouTube Shorts URLs ─────────────────────────────────────────

def test_extract_youtube_id_supported_shorts_formats():
    shorts_cases = [
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
        "https://m.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ/",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        "www.youtube.com/shorts/dQw4w9WgXcQ",
    ]
    for url in shorts_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for Shorts URL: {url}"


# ── 3. Supported YouTube Embed URLs (DEF-API-01 Core Fix) ───────────────────

def test_extract_youtube_id_supported_embed_formats():
    embed_cases = [
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ/",
        "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1",
        "https://www.youtube.com/embed/dQw4w9WgXcQ?start=10&feature=oembed",
        "www.youtube.com/embed/dQw4w9WgXcQ",
    ]
    for url in embed_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for embed URL: {url}"


# ── 4. Supported YouTube /v/ URLs ────────────────────────────────────────────

def test_extract_youtube_id_supported_v_formats():
    v_cases = [
        "https://www.youtube.com/v/dQw4w9WgXcQ",
        "https://youtube.com/v/dQw4w9WgXcQ",
        "https://www.youtube.com/v/dQw4w9WgXcQ/",
        "https://www.youtube.com/v/dQw4w9WgXcQ?version=3&autohide=1",
        "www.youtube.com/v/dQw4w9WgXcQ",
    ]
    for url in v_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for /v/ URL: {url}"


# ── 5. Supported YouTube Live URLs ───────────────────────────────────────────

def test_extract_youtube_id_supported_live_formats():
    live_cases = [
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ/",
        "https://www.youtube.com/live/dQw4w9WgXcQ?feature=share",
        "www.youtube.com/live/dQw4w9WgXcQ",
    ]
    for url in live_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for live URL: {url}"


# ── 6. Supported youtu.be Short URLs ────────────────────────────────────────

def test_extract_youtube_id_supported_youtu_be_formats():
    short_cases = [
        "https://youtu.be/dQw4w9WgXcQ",
        "http://youtu.be/dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
        "https://www.youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ/",
        "https://youtu.be/dQw4w9WgXcQ?t=42s",
        "https://youtu.be/dQw4w9WgXcQ?si=abcdef12345",
    ]
    for url in short_cases:
        assert extract_youtube_id(url) == EXPECTED_ID, f"Failed for youtu.be URL: {url}"


# ── 7. Rejection of Lookalike Domains ───────────────────────────────────────

def test_extract_youtube_id_rejects_lookalike_domains():
    lookalike_cases = [
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
        "https://evil-youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com.attacker.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be.attacker.org/dQw4w9WgXcQ",
        "https://attacker.com/youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com@attacker.com/watch?v=dQw4w9WgXcQ",
        "https://fakeyoutube.com/shorts/dQw4w9WgXcQ",
        "https://myoutu.be/dQw4w9WgXcQ",
        "https://youtube.co/watch?v=dQw4w9WgXcQ",
    ]
    for url in lookalike_cases:
        assert extract_youtube_id(url) is None, f"Should reject lookalike domain: {url}"


# ── 8. Rejection of Unrecognized Hostnames ──────────────────────────────────

def test_extract_youtube_id_rejects_unrecognized_hostnames():
    unrecognized_cases = [
        "https://vimeo.com/123456789",
        "https://tiktok.com/@user/video/123",
        "https://google.com",
        "https://facebook.com/watch?v=dQw4w9WgXcQ",
        "https://instagram.com/p/dQw4w9WgXcQ",
        "https://twitch.tv/dQw4w9WgXcQ",
        "https://dailymotion.com/video/x7tgad0",
    ]
    for url in unrecognized_cases:
        assert extract_youtube_id(url) is None, f"Should reject unrecognized host: {url}"


# ── 9. Rejection of Malformed IDs ───────────────────────────────────────────

def test_extract_youtube_id_rejects_malformed_ids():
    malformed_cases = [
        "https://www.youtube.com/watch?v=dQw4w9WgXc",     # 10 chars (too short)
        "https://www.youtube.com/watch?v=dQw4w9WgXcQQ",   # 12 chars (too long)
        "https://www.youtube.com/watch?v=dQw4w9WgXc!",    # illegal character '!'
        "https://www.youtube.com/watch?v=dQw4w9Wg Xc",    # space
        "https://www.youtube.com/watch?v=",               # empty query param
        "https://youtu.be/dQw4w9WgXc",                    # 10 chars
        "https://youtu.be/dQw4w9WgXcQQ",                  # 12 chars
        "https://youtu.be/",                              # empty youtu.be path
        "https://www.youtube.com/shorts/",                # empty shorts path
        "https://www.youtube.com/embed/",                 # empty embed path
        "https://www.youtube.com/v/",                     # empty /v/ path
        "https://www.youtube.com/live/",                  # empty /live/ path
    ]
    for url in malformed_cases:
        assert extract_youtube_id(url) is None, f"Should reject malformed ID: {url}"


# ── 10. Rejection of Unsupported URL Structures ──────────────────────────────

def test_extract_youtube_id_rejects_unsupported_structures():
    unsupported_structures = [
        "https://www.youtube.com/",
        "https://www.youtube.com/feed/subscriptions",
        "https://www.youtube.com/channel/UC12345678901",
        "https://www.youtube.com/user/RickAstley",
        "https://www.youtube.com/playlist?list=PL12345678901",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch/extra?v=dQw4w9WgXcQ",
        "https://youtu.be/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/embed/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/v/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/live/dQw4w9WgXcQ/extra",
    ]
    for url in unsupported_structures:
        assert extract_youtube_id(url) is None, f"Should reject unsupported structure: {url}"


# ── 11. Rejection of Invalid / Garbage Inputs ───────────────────────────────

def test_extract_youtube_id_rejects_invalid_inputs():
    invalid_inputs = [
        "",
        "   ",
        None,
        12345,
        {"url": "https://youtube.com"},
        "not-a-valid-url",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "ftp://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]
    for inp in invalid_inputs:
        assert extract_youtube_id(inp) is None, f"Should reject invalid input: {inp}"


# ── 12. Synthetic Fixture Preservation ──────────────────────────────────────

def test_extract_youtube_id_preserves_synthetic_fixtures():
    # Downloader uses synthetic fixture IDs like synth_vid01 (11 chars) in watch URLs
    synth_url = "https://www.youtube.com/watch?v=synth_vid01"
    assert extract_youtube_id(synth_url) == "synth_vid01"


# ── 13. API Route Contract Parity Verification ──────────────────────────────

@pytest.mark.asyncio
async def test_api_videos_url_endpoint_parity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.services.queue_manager.dispatch_celery_job", return_value="test-task-parity-01"), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply, \
             patch("backend.tasks.orchestration.start_video_processing_task.delay") as mock_delay, \
             patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            mock_apply.return_value = MagicMock(id="test-task-parity-01")
            mock_delay.return_value = MagicMock(id="test-task-parity-01")

            # DEF-API-01 Fix: Embed URL must now return HTTP 200
            embed_resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/embed/dQw4w9WgXcQ", "is_test": "true"})
            assert embed_resp.status_code == 200, f"Embed URL failed: {embed_resp.text}"
            assert embed_resp.json()["url"] == "https://www.youtube.com/embed/dQw4w9WgXcQ"

            # Shorts URL
            shorts_resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/shorts/dQw4w9WgXcQ", "is_test": "true"})
            assert shorts_resp.status_code == 200, f"Shorts URL failed: {shorts_resp.text}"

            # /v/ URL
            v_resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/v/dQw4w9WgXcQ", "is_test": "true"})
            assert v_resp.status_code == 200, f"/v/ URL failed: {v_resp.text}"

            # /live/ URL
            live_resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/live/dQw4w9WgXcQ", "is_test": "true"})
            assert live_resp.status_code == 200, f"Live URL failed: {live_resp.text}"

            # youtu.be URL
            ytbe_resp = await client.post("/api/videos/url", data={"url": "https://youtu.be/dQw4w9WgXcQ", "is_test": "true"})
            assert ytbe_resp.status_code == 200, f"youtu.be URL failed: {ytbe_resp.text}"

            # Standard watch URL with complex query parameter ordering
            watch_resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ&t=10s", "is_test": "true"})
            assert watch_resp.status_code == 200, f"Watch URL failed: {watch_resp.text}"

            # Rejection of lookalike domain
            bad_domain_resp = await client.post("/api/videos/url", data={"url": "https://notyoutube.com/watch?v=dQw4w9WgXcQ", "is_test": "true"})
            assert bad_domain_resp.status_code == 400
            assert bad_domain_resp.json() == {"detail": "Invalid YouTube URL"}

            # Rejection of Vimeo URL
            vimeo_resp = await client.post("/api/videos/url", data={"url": "https://vimeo.com/123456789", "is_test": "true"})
            assert vimeo_resp.status_code == 400
            assert vimeo_resp.json() == {"detail": "Invalid YouTube URL"}

            # Rejection of malformed video ID
            malformed_resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/watch?v=too_short", "is_test": "true"})
            assert malformed_resp.status_code == 400
            assert malformed_resp.json() == {"detail": "Invalid YouTube URL"}

    # Cleanup test jobs
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Job
    with SyncSessionLocal() as session:
        test_jobs = session.query(Job).filter(Job.source_url.like("%dQw4w9WgXcQ%"), Job.is_test == True).all()
        for tj in test_jobs:
            session.delete(tj)
        session.commit()


# ── 14. URL Authority Hardening Tests ────────────────────────────────────────

def test_extract_youtube_id_authority_hardening():
    # 1. Valid default ports (accepted)
    assert extract_youtube_id("https://www.youtube.com:443/watch?v=dQw4w9WgXcQ") == EXPECTED_ID
    assert extract_youtube_id("http://www.youtube.com:80/watch?v=dQw4w9WgXcQ") == EXPECTED_ID
    assert extract_youtube_id("https://youtube.com:443/shorts/dQw4w9WgXcQ") == EXPECTED_ID
    assert extract_youtube_id("https://youtu.be:443/dQw4w9WgXcQ") == EXPECTED_ID

    # 2. Uppercase hostnames and schemes (accepted)
    assert extract_youtube_id("HTTPS://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ") == EXPECTED_ID
    assert extract_youtube_id("HTTPS://YOUTU.BE/dQw4w9WgXcQ") == EXPECTED_ID
    assert extract_youtube_id("HTTPS://M.YOUTUBE.COM/SHORTS/dQw4w9WgXcQ") == EXPECTED_ID

    # 3. Userinfo in authority (must be rejected)
    assert extract_youtube_id("https://user:pass@www.youtube.com/watch?v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://admin@youtube.com/watch?v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://user:pass@youtu.be/dQw4w9WgXcQ") is None

    # 4. Invalid or non-standard ports (must be rejected)
    assert extract_youtube_id("https://www.youtube.com:8080/watch?v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://youtu.be:8080/dQw4w9WgXcQ") is None

    # 5. Out-of-range ports (must be rejected without crashing)
    assert extract_youtube_id("https://www.youtube.com:99999/watch?v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://www.youtube.com:65536/watch?v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://www.youtube.com:0/watch?v=dQw4w9WgXcQ") is None

    # 6. Duplicate 'v' query parameters (ambiguous input must be rejected)
    assert extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&v=anotherid12") is None
    assert extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&v=dQw4w9WgXcQ") is None
    assert extract_youtube_id("https://www.youtube.com/watch?v=&v=dQw4w9WgXcQ") is None
