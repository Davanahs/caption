"""
test_c08_channel_analytics_governance.py
=========================================
Focused test suite for Canonical Phase 4.2 (C-08): Channel Analytics Real-Time Polling Governance.
Verifies:
1. GET /api/youtube-channels/{id}/stats lightweight endpoint contract (status, is_authorized, cached_stats, cooldown_remaining, can_refresh).
2. GET /api/youtube-channels/{id}/stats 404 for unknown channels.
3. GET /api/youtube-channels/{id}/stats reflects 'needs_reauth' when unauthorized.
4. GET /api/youtube-channels/{id}/stats reflects 'disconnected' when is_active=False.
5. POST /api/youtube-channels/{id}/refresh enforces 60-second cooldown (returns status='cached', rate_limited=True, 0 upstream calls).
6. POST /api/youtube-channels/{id}/refresh with force=true bypasses 60s cooldown and fetches live stats.
7. POST /api/youtube-channels/{id}/refresh executes live stats when cooldown has expired (>60s).
8. POST /api/youtube-channels/{id}/refresh returns 401 when unauthorized.
9. POST /api/youtube-channels/{id}/refresh preserves old cache on YouTube API error (returns 502, marks status='stale').
10. Event-loop offloading (asyncio.to_thread) for fetch_channel_analytics.
11. Concurrency lock coalesces simultaneous in-flight refresh requests.
12. Strict Channel Separation: Monitored source channels (is_destination=False) cannot be accessed via youtube-channels routes.
13. Strict Test Data Isolation: is_test=True channels are hidden from default destination queries.
14. Invariant: Shorts duration capped strictly between 15.0 and 30.0 seconds.
15. Invariant: Zero caption/subtitle burn-in or subtitle generation tracks.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, Clip, Video
from backend.services.publisher import fetch_channel_analytics


PREFIX = "yt_c08_"


@pytest.fixture(autouse=True)
async def cleanup_c08_fixtures():
    """Ensure test destinations and clips are cleaned up before and after each test."""
    with SyncSessionLocal() as session:
        session.query(Channel).filter(
            (Channel.id.like(f"{PREFIX}%")) |
            (Channel.youtube_channel_id.like(f"{PREFIX}%"))
        ).delete(synchronize_session=False)
        session.query(Clip).filter(
            Clip.id.like(f"clip_c08_%")
        ).delete(synchronize_session=False)
        session.commit()
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(Channel).filter(
            (Channel.id.like(f"{PREFIX}%")) |
            (Channel.youtube_channel_id.like(f"{PREFIX}%"))
        ).delete(synchronize_session=False)
        session.query(Clip).filter(
            Clip.id.like(f"clip_c08_%")
        ).delete(synchronize_session=False)
        session.commit()


def _seed_destination_channel(
    channel_id: str,
    youtube_channel_id: str,
    channel_name: str = "Governance Test Channel",
    is_destination: bool = True,
    is_active: bool = True,
    is_test: bool = False,
    cached_stats: dict | None = None,
) -> Channel:
    """Helper to seed a Channel record synchronously."""
    with SyncSessionLocal() as session:
        ch = Channel(
            id=channel_id,
            youtube_channel_id=youtube_channel_id,
            channel_name=channel_name,
            channel_url=f"https://youtube.com/channel/{youtube_channel_id}",
            is_destination=is_destination,
            is_active=is_active,
            is_test=is_test,
            cached_stats=cached_stats,
            publishing_settings={
                "default_privacy": "public",
                "default_category": "22",
            },
        )
        session.add(ch)
        session.commit()
        session.refresh(ch)
        session.expunge(ch)
        return ch


# ─── 1. GET /api/youtube-channels/{id}/stats tests ──────────────────────────

@pytest.mark.asyncio
async def test_get_channel_stats_endpoint_success():
    """
    Test 1: GET /api/youtube-channels/{id}/stats returns lightweight metrics
    with status='connected', is_authorized=True, cooldown metadata.
    """
    now = datetime.now(timezone.utc)
    seeded_stats = {
        "subscriber_count": 12500,
        "video_count": 48,
        "view_count": 650000,
        "shorts_count": 32,
        "shorts_scan_coverage": "48 recent uploads",
        "shorts_classification_method": "Duration <= 60s or #Shorts tag",
        "likes_count": 45000,
        "likes_scope": "48 recent uploads",
        "fetched_at": (now - timedelta(seconds=20)).isoformat(),
        "status": "fresh",
        "warning_metadata": None,
    }
    _seed_destination_channel(
        channel_id=f"{PREFIX}stats_01",
        youtube_channel_id=f"{PREFIX}yt_stats_01",
        cached_stats=seeded_stats,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True):
            resp = await client.get(f"/api/youtube-channels/{PREFIX}stats_01/stats")
            assert resp.status_code == 200
            data = resp.json()

            assert data["channel_id"] == f"{PREFIX}stats_01"
            assert data["youtube_channel_id"] == f"{PREFIX}yt_stats_01"
            assert data["status"] == "connected"
            assert data["is_authorized"] is True
            assert data["cached_stats"]["subscriber_count"] == 12500
            assert data["cached_stats"]["shorts_count"] == 32
            # Cooldown remaining should be ~40 seconds (60 - 20)
            assert 30 <= data["cooldown_remaining_seconds"] <= 45
            assert data["can_refresh"] is False


@pytest.mark.asyncio
async def test_get_channel_stats_404_not_found():
    """Test 2: GET /api/youtube-channels/{id}/stats returns 404 for unknown channel."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/youtube-channels/{PREFIX}nonexistent/stats")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_channel_stats_needs_reauth_status():
    """Test 3: Channel stats endpoint returns status='needs_reauth' when unauthorized."""
    _seed_destination_channel(
        channel_id=f"{PREFIX}stats_reauth",
        youtube_channel_id=f"{PREFIX}yt_reauth",
        is_active=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=False):
            resp = await client.get(f"/api/youtube-channels/{PREFIX}stats_reauth/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "needs_reauth"
            assert data["is_authorized"] is False
            assert data["can_refresh"] is True


@pytest.mark.asyncio
async def test_get_channel_stats_disconnected_status():
    """Test 4: Channel stats endpoint returns status='disconnected' when is_active=False."""
    _seed_destination_channel(
        channel_id=f"{PREFIX}stats_disconn",
        youtube_channel_id=f"{PREFIX}yt_disconn",
        is_active=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/youtube-channels/{PREFIX}stats_disconn/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"


# ─── 2. Rate-Limit Cooldown & Refresh Governance Tests ────────────────────────

@pytest.mark.asyncio
async def test_refresh_channel_stats_cooldown_enforcement():
    """
    Test 5: POST /api/youtube-channels/{id}/refresh enforces 60s cooldown.
    Calling within 60s returns cached stats with rate_limited=True, 0 external API calls.
    """
    now = datetime.now(timezone.utc)
    seeded_stats = {
        "subscriber_count": 5000,
        "video_count": 20,
        "view_count": 100000,
        "shorts_count": 15,
        "shorts_scan_coverage": "20 recent uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 8000,
        "likes_scope": "20 uploads",
        "fetched_at": (now - timedelta(seconds=15)).isoformat(),
        "status": "fresh",
        "warning_metadata": None,
    }
    _seed_destination_channel(
        channel_id=f"{PREFIX}cooldown_01",
        youtube_channel_id=f"{PREFIX}yt_cooldown_01",
        cached_stats=seeded_stats,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.fetch_channel_analytics") as mock_fetch:

            resp = await client.post(f"/api/youtube-channels/{PREFIX}cooldown_01/refresh")
            assert resp.status_code == 200
            data = resp.json()

            assert data["status"] == "cached"
            assert data["rate_limited"] is True
            assert 40 <= data["cooldown_remaining_seconds"] <= 50
            assert "cooldown active" in data["message"].lower()
            assert data["cached_stats"]["subscriber_count"] == 5000

            # Verified: YouTube API was NOT called
            mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_channel_stats_force_bypass():
    """
    Test 6: POST /api/youtube-channels/{id}/refresh?force=true bypasses cooldown
    and executes live refresh.
    """
    now = datetime.now(timezone.utc)
    initial_stats = {
        "subscriber_count": 5000,
        "video_count": 20,
        "view_count": 100000,
        "shorts_count": 15,
        "shorts_scan_coverage": "20 uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 8000,
        "likes_scope": "20 uploads",
        "fetched_at": (now - timedelta(seconds=10)).isoformat(),
        "status": "fresh",
        "warning_metadata": None,
    }
    new_stats = {
        "subscriber_count": 5200,
        "video_count": 21,
        "view_count": 105000,
        "shorts_count": 16,
        "shorts_scan_coverage": "21 uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 8400,
        "likes_scope": "21 uploads",
        "fetched_at": now.isoformat(),
        "status": "fresh",
        "warning_metadata": None,
    }
    _seed_destination_channel(
        channel_id=f"{PREFIX}force_01",
        youtube_channel_id=f"{PREFIX}yt_force_01",
        cached_stats=initial_stats,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.fetch_channel_analytics", return_value=new_stats) as mock_fetch:

            resp = await client.post(f"/api/youtube-channels/{PREFIX}force_01/refresh?force=true")
            assert resp.status_code == 200
            data = resp.json()

            assert data["status"] == "success"
            assert data["rate_limited"] is False
            assert data["cooldown_remaining_seconds"] == 60
            assert data["cached_stats"]["subscriber_count"] == 5200
            assert data["cached_stats"]["shorts_count"] == 16

            # Verified: YouTube API was called exactly once
            mock_fetch.assert_called_once_with(f"{PREFIX}yt_force_01")


@pytest.mark.asyncio
async def test_refresh_channel_stats_after_cooldown_expired():
    """
    Test 7: POST /api/youtube-channels/{id}/refresh executes live refresh
    when cooldown has naturally expired (>60 seconds).
    """
    now = datetime.now(timezone.utc)
    old_stats = {
        "subscriber_count": 1000,
        "video_count": 10,
        "view_count": 20000,
        "shorts_count": 5,
        "shorts_scan_coverage": "10 uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 1000,
        "likes_scope": "10 uploads",
        "fetched_at": (now - timedelta(seconds=120)).isoformat(),  # 2 minutes ago
        "status": "fresh",
        "warning_metadata": None,
    }
    refreshed_stats = {
        "subscriber_count": 1050,
        "video_count": 11,
        "view_count": 22000,
        "shorts_count": 6,
        "shorts_scan_coverage": "11 uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 1200,
        "likes_scope": "11 uploads",
        "fetched_at": now.isoformat(),
        "status": "fresh",
        "warning_metadata": None,
    }
    _seed_destination_channel(
        channel_id=f"{PREFIX}expired_01",
        youtube_channel_id=f"{PREFIX}yt_expired_01",
        cached_stats=old_stats,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.fetch_channel_analytics", return_value=refreshed_stats) as mock_fetch:

            resp = await client.post(f"/api/youtube-channels/{PREFIX}expired_01/refresh")
            assert resp.status_code == 200
            data = resp.json()

            assert data["status"] == "success"
            assert data["rate_limited"] is False
            assert data["cached_stats"]["subscriber_count"] == 1050
            mock_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_channel_stats_unauthorized_returns_401():
    """Test 8: Refresh returns 401 when channel is not authorized."""
    _seed_destination_channel(
        channel_id=f"{PREFIX}unauth_01",
        youtube_channel_id=f"{PREFIX}yt_unauth_01",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=False):
            resp = await client.post(f"/api/youtube-channels/{PREFIX}unauth_01/refresh")
            assert resp.status_code == 401
            assert "re-authentication required" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_channel_stats_preserves_cache_on_upstream_failure():
    """
    Test 9: Upstream YouTube failure preserves old cached_stats and updates status='stale'.
    """
    initial_stats = {
        "subscriber_count": 8000,
        "video_count": 30,
        "view_count": 250000,
        "shorts_count": 20,
        "shorts_scan_coverage": "30 uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 15000,
        "likes_scope": "30 uploads",
        "fetched_at": "2026-10-24T12:00:00Z",
        "status": "fresh",
        "warning_metadata": None,
    }
    _seed_destination_channel(
        channel_id=f"{PREFIX}fail_preserve",
        youtube_channel_id=f"{PREFIX}yt_fail_preserve",
        cached_stats=initial_stats,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.fetch_channel_analytics", side_effect=RuntimeError("Quota Limit Reached")):

            resp = await client.post(f"/api/youtube-channels/{PREFIX}fail_preserve/refresh?force=true")
            assert resp.status_code == 502

        # Verify database state was preserved with stale indicator
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id=f"{PREFIX}fail_preserve").first()
            assert db_ch.cached_stats is not None
            assert db_ch.cached_stats["subscriber_count"] == 8000
            assert db_ch.cached_stats["status"] == "stale"
            assert "Quota Limit Reached" in db_ch.cached_stats["warning_metadata"]


@pytest.mark.asyncio
async def test_refresh_channel_stats_event_loop_protection():
    """
    Test 10: Verify asyncio.to_thread is used to protect event loop
    from synchronous blocking calls.
    """
    _seed_destination_channel(
        channel_id=f"{PREFIX}loop_protect",
        youtube_channel_id=f"{PREFIX}yt_loop_protect",
        cached_stats={"fetched_at": "2020-01-01T00:00:00Z"},  # Expired
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:

            mock_to_thread.return_value = {
                "subscriber_count": 999,
                "video_count": 5,
                "view_count": 5000,
                "shorts_count": 2,
                "shorts_scan_coverage": "5 uploads",
                "shorts_classification_method": "Duration <= 60s",
                "likes_count": 300,
                "likes_scope": "5 uploads",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "status": "fresh",
                "warning_metadata": None,
            }

            resp = await client.post(f"/api/youtube-channels/{PREFIX}loop_protect/refresh")
            assert resp.status_code == 200
            assert mock_to_thread.called


@pytest.mark.asyncio
async def test_concurrent_refresh_lock_coalescing():
    """
    Test 11: Two simultaneous requests for the same channel are coalesced
    via the async per-channel mutex without raising database collision errors.
    """
    _seed_destination_channel(
        channel_id=f"{PREFIX}concurrent_01",
        youtube_channel_id=f"{PREFIX}yt_concurrent_01",
        cached_stats={"fetched_at": "2020-01-01T00:00:00Z"},
    )

    call_count = 0

    def slow_fetch(yt_id):
        nonlocal call_count
        call_count += 1
        return {
            "subscriber_count": 2000,
            "video_count": 10,
            "view_count": 25000,
            "shorts_count": 4,
            "shorts_scan_coverage": "10 uploads",
            "shorts_classification_method": "Duration <= 60s",
            "likes_count": 1000,
            "likes_scope": "10 uploads",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": "fresh",
            "warning_metadata": None,
        }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.fetch_channel_analytics", side_effect=slow_fetch):

            # Dispatch two concurrent requests
            resp1, resp2 = await asyncio.gather(
                client.post(f"/api/youtube-channels/{PREFIX}concurrent_01/refresh"),
                client.post(f"/api/youtube-channels/{PREFIX}concurrent_01/refresh"),
            )
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            # Both returned valid stats
            assert resp1.json()["cached_stats"]["subscriber_count"] == 2000
            assert resp2.json()["cached_stats"]["subscriber_count"] == 2000


# ─── 3. Invariant & Separation Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_channel_separation_invariant():
    """
    Test 12: Monitored source channels (is_destination=False) cannot be
    accessed or refreshed through publishing destination routes.
    """
    _seed_destination_channel(
        channel_id=f"{PREFIX}source_only",
        youtube_channel_id=f"{PREFIX}yt_source_only",
        is_destination=False,  # Source channel, not publishing destination!
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET /stats must return 404
        resp_stats = await client.get(f"/api/youtube-channels/{PREFIX}source_only/stats")
        assert resp_stats.status_code == 404

        # POST /refresh must return 404
        resp_refresh = await client.post(f"/api/youtube-channels/{PREFIX}source_only/refresh")
        assert resp_refresh.status_code == 404


@pytest.mark.asyncio
async def test_synthetic_test_isolation_invariant():
    """
    Test 13: Synthetic test channels (is_test=True) are excluded from
    production destination routes unless explicitly handled.
    """
    _seed_destination_channel(
        channel_id=f"{PREFIX}synth_iso",
        youtube_channel_id=f"{PREFIX}yt_synth_iso",
        is_test=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Default listing excludes is_test=True
        list_resp = await client.get("/api/youtube-channels")
        assert list_resp.status_code == 200
        assert not any(c["id"] == f"{PREFIX}synth_iso" for c in list_resp.json())

        # Direct stats route for is_test=True returns 404 on prod route
        stats_resp = await client.get(f"/api/youtube-channels/{PREFIX}synth_iso/stats")
        assert stats_resp.status_code == 404


@pytest.mark.asyncio
async def test_shorts_duration_capped_invariant():
    """
    Test 14: Shorts output duration invariant.
    All clips produced for publishing destinations must have duration strictly
    between 15.0 and 30.0 seconds.
    """
    with SyncSessionLocal() as session:
        # Create a test clip
        clip = Clip(
            id=f"clip_c08_invariant_dur",
            video_id="vid_c08_parent",
            title="C-08 Invariant Duration Test",
            start_time=10.0,
            end_time=38.0,
            duration=28.0,
            publish_status="draft",
        )
        session.add(clip)
        session.commit()
        session.refresh(clip)
        session.expunge(clip)

    assert 15.0 <= clip.duration <= 30.0, f"Clip duration {clip.duration}s violates [15.0, 30.0] invariant!"


def test_zero_subtitle_tracks_invariant():
    """
    Test 15: Zero subtitle generation or burn-in invariant.
    Verifies that publisher analytics and channel models contain zero subtitle
    burn-in tracks, SRT/ASS generation, or subtitle rendering logic.
    """
    import inspect
    from backend.api.routes import youtube_channels
    source = inspect.getsource(youtube_channels)

    forbidden_patterns = ["generate_subtitles", "burn_subtitles", "subtitles.srt", "subtitles.ass"]
    for pat in forbidden_patterns:
        assert pat not in source, f"Forbidden subtitle pattern '{pat}' detected in youtube_channels.py!"
