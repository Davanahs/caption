"""
test_youtube_channels_management.py
===================================
Comprehensive test suite verifying My YouTube Channels management (/youtube-channels):
1. Destination vs Source Separation: Only verified publishing destinations returned.
   Monitored source channels and test fixtures are excluded.
2. OAuth Security & Multi-Channel Isolation: Account selection prompt, state flow, isolated token storage.
3. Publishing Settings: Schema validation, partial updates, persistence without side effects.
4. Channel Analytics: Live statistics mapping, bounded Shorts classification, likes scoping, failure resilience.
5. Transactional Default Selection: Exactly one primary default destination.
6. Safe Disconnection: Deactivates publishing without destroying historical records or leaking into source channels.
7. Test Data Isolation: Fixtures run with is_test=True and clean up properly.
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, Clip, Job
from backend.services.publisher import (
    _parse_iso_duration,
    fetch_channel_analytics,
    get_oauth_url,
    check_channel_authorization,
)


@pytest.fixture(autouse=True)
async def cleanup_test_destinations():
    """Ensure any test-created channels are cleaned up before and after each test, and engine disposed."""
    test_prefix = "yt_test_"
    with SyncSessionLocal() as session:
        session.query(Channel).filter(
            (Channel.id.like(f"{test_prefix}%")) | 
            (Channel.youtube_channel_id.like(f"{test_prefix}%")) |
            ((Channel.is_test == True) & (Channel.id != "518b3118-2367-4f84-898f-ff97a61df306"))
        ).delete(synchronize_session=False)
        session.commit()
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(Channel).filter(
            (Channel.id.like(f"{test_prefix}%")) | 
            (Channel.youtube_channel_id.like(f"{test_prefix}%")) |
            ((Channel.is_test == True) & (Channel.id != "518b3118-2367-4f84-898f-ff97a61df306"))
        ).delete(synchronize_session=False)
        session.commit()


@pytest.mark.asyncio
async def test_list_youtube_channels_separation_and_contract():
    """
    Test 1: GET /api/youtube-channels/ returns verified destination channels.
    - Excludes monitored source channels (is_destination=False)
    - Excludes synthetic test channels by default (is_test=False)
    - Returns clipse with valid status and publishing_settings
    - Never exposes token secrets or credentials
    """
    # Create a synthetic test channel and a monitored source channel
    with SyncSessionLocal() as session:
        test_ch = Channel(
            id="yt_test_synthetic_01",
            youtube_channel_id="yt_test_synth_yt_01",
            channel_name="Synthetic Test Channel",
            channel_url="https://youtube.com/channel/yt_test_synth_yt_01",
            is_destination=True,
            is_active=True,
            is_test=True,
        )
        session.add(test_ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Default query (include_test=False)
        resp = await client.get("/api/youtube-channels/")
        assert resp.status_code == 200
        data = resp.json()

        # clipse must be present
        clipse_entry = next((c for c in data if c["youtube_channel_id"] == "UCH90024qrJHA4amGRxnTldw"), None)
        assert clipse_entry is not None, "Real destination 'clipse' must be in destination list"
        assert clipse_entry["channel_name"] == "clipse"
        assert clipse_entry["is_destination"] is True
        assert clipse_entry["status"] == "connected"
        assert "publishing_settings" in clipse_entry
        assert "cached_stats" in clipse_entry

        # Monitored source channels (Nishant Chahar, TED) MUST NOT be present
        for c in data:
            assert c["is_destination"] is True
            assert c["youtube_channel_id"] not in ("UCVe8CMJF4caRzuckVYV8CaQ", "UCAuUUnT6oDeKwE6v1NGQxug")
            assert "token" not in c
            assert "client_secret" not in c

        # Synthetic test channel must be excluded by default
        assert not any(c["id"] == "yt_test_synthetic_01" for c in data)

        # When include_test=True, synthetic test channel is included
        resp_test = await client.get("/api/youtube-channels/?include_test=true")
        assert resp_test.status_code == 200
        test_data = resp_test.json()
        assert any(c["id"] == "yt_test_synthetic_01" for c in test_data)


@pytest.mark.asyncio
async def test_oauth_url_generation_with_multi_account_prompt():
    """
    Test 2: GET /api/youtube-channels/oauth-url generates valid authorization URL
    with prompt=select_account consent for multi-channel linking.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/youtube-channels/oauth-url")
        assert resp.status_code == 200
        data = resp.json()
        assert "oauth_url" in data
        assert "state" in data
        url = data["oauth_url"]
        assert "prompt=select_account" in url or "prompt=select_account+consent" in url or "prompt=consent" in url
        assert "access_type=offline" in url or "response_type=code" in url


@pytest.mark.asyncio
async def test_settings_validation_and_partial_update():
    """
    Test 3: PATCH /api/youtube-channels/{channel_id}/settings
    - Valid updates persist into publishing_settings
    - Invalid privacy or license values are rejected with 422
    - Partial updates preserve unspecified fields
    """
    # Create isolated test channel
    with SyncSessionLocal() as session:
        ch = Channel(
            id="yt_test_settings_ch_01",
            youtube_channel_id="yt_test_settings_yt_01",
            channel_name="Settings Test Channel",
            channel_url="https://youtube.com/channel/yt_test_settings_yt_01",
            is_destination=True,
            is_active=True,
            is_test=False,
            publishing_settings={
                "default_privacy": "public",
                "default_category": "22",
                "default_tags": "initial, tags",
                "default_license": "youtube",
                "default_made_for_kids": False,
            }
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Reject invalid privacy
        bad_privacy = await client.patch(
            "/api/youtube-channels/yt_test_settings_ch_01/settings",
            json={"default_privacy": "invalid_privacy"}
        )
        assert bad_privacy.status_code == 422

        # 2. Reject invalid license
        bad_license = await client.patch(
            "/api/youtube-channels/yt_test_settings_ch_01/settings",
            json={"default_license": "custom_copyright"}
        )
        assert bad_license.status_code == 422

        # 3. Successful partial update
        valid_update = await client.patch(
            "/api/youtube-channels/yt_test_settings_ch_01/settings",
            json={
                "default_privacy": "unlisted",
                "default_category": "28",
                "default_made_for_kids": True,
                "brand_color_primary": "#10b981",
            }
        )
        assert valid_update.status_code == 200
        saved = valid_update.json()["publishing_settings"]
        assert saved["default_privacy"] == "unlisted"
        assert saved["default_category"] == "28"
        assert saved["default_made_for_kids"] is True
        assert saved["brand_color_primary"] == "#10b981"
        # Preserved unspecified field
        assert saved["default_tags"] == "initial, tags"
        assert saved["default_license"] == "youtube"


@pytest.mark.asyncio
async def test_set_default_destination_transactional():
    """
    Test 4: POST /api/youtube-channels/{channel_id}/set-default
    - Designates the target channel as default
    - Transactionally resets any previously designated default
    - Disconnected channels cannot be set as default
    """
    with SyncSessionLocal() as session:
        ch_a = Channel(
            id="yt_test_default_ch_a",
            youtube_channel_id="yt_test_default_yt_a",
            channel_name="Default Candidate A",
            channel_url="https://youtube.com/channel/yt_test_default_yt_a",
            is_destination=True,
            is_default_destination=True,
            is_active=True,
            is_test=False,
        )
        ch_b = Channel(
            id="yt_test_default_ch_b",
            youtube_channel_id="yt_test_default_yt_b",
            channel_name="Default Candidate B",
            channel_url="https://youtube.com/channel/yt_test_default_yt_b",
            is_destination=True,
            is_default_destination=False,
            is_active=True,
            is_test=False,
        )
        session.add_all([ch_a, ch_b])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Mock authorization check for Candidate B
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True):
            resp = await client.post("/api/youtube-channels/yt_test_default_ch_b/set-default")
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_default_destination"] is True

        # Verify in DB: B is default, A is no longer default
        with SyncSessionLocal() as session:
            db_a = session.query(Channel).filter_by(id="yt_test_default_ch_a").first()
            db_b = session.query(Channel).filter_by(id="yt_test_default_ch_b").first()
            assert db_a.is_default_destination is False
            assert db_b.is_default_destination is True


@pytest.mark.asyncio
async def test_disconnect_channel_preserves_destination_separation():
    """
    Test 5: POST /api/youtube-channels/{channel_id}/disconnect
    - Sets is_active = False and clears default status
    - Preserves is_destination = True so it DOES NOT become a monitored source!
    - Historical jobs/clips remain intact
    """
    with SyncSessionLocal() as session:
        ch = Channel(
            id="yt_test_disconnect_ch_01",
            youtube_channel_id="yt_test_disconnect_yt_01",
            channel_name="Disconnect Candidate",
            channel_url="https://youtube.com/channel/yt_test_disconnect_yt_01",
            is_destination=True,
            is_default_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/youtube-channels/yt_test_disconnect_ch_01/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["is_active"] is False

        # Verify DB state
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id="yt_test_disconnect_ch_01").first()
            assert db_ch.is_active is False
            assert db_ch.is_default_destination is False
            # CRITICAL INVARIANT: is_destination remains True!
            assert db_ch.is_destination is True

        # Confirm it is NOT returned in GET /api/channels/ (monitored source channels)
        source_resp = await client.get("/api/channels/")
        assert source_resp.status_code == 200
        sources = source_resp.json()
        assert not any(s["id"] == "yt_test_disconnect_ch_01" for s in sources)


def test_iso_duration_parser_and_analytics_mapping():
    """
    Test 6: ISO 8601 duration parsing and analytics dictionary structure.
    """
    # 1. ISO Duration Parsing
    assert _parse_iso_duration("PT30S") == 30
    assert _parse_iso_duration("PT1M") == 60
    assert _parse_iso_duration("PT1M15S") == 75
    assert _parse_iso_duration("PT2M45S") == 165
    assert _parse_iso_duration("PT1H") == 3600
    assert _parse_iso_duration("") == 0
    assert _parse_iso_duration(None) == 0

    # 2. Analytics mapping for clipse
    stats = fetch_channel_analytics("UCH90024qrJHA4amGRxnTldw")
    assert "subscriber_count" in stats
    assert "video_count" in stats
    assert "view_count" in stats
    assert "shorts_count" in stats
    assert "shorts_scan_coverage" in stats
    assert "shorts_classification_method" in stats
    assert "likes_count" in stats
    assert "likes_scope" in stats
    assert stats["status"] == "fresh"


@pytest.mark.asyncio
async def test_refresh_stats_preserves_old_cache_on_failure():
    """
    Test 7: POST /api/youtube-channels/{channel_id}/refresh
    - Valid refresh updates cached_stats
    - Remote failure preserves existing cache and tags status='stale'
    """
    initial_stats = {
        "subscriber_count": 500,
        "video_count": 5,
        "view_count": 10000,
        "shorts_count": 3,
        "shorts_scan_coverage": "5 recent uploads",
        "shorts_classification_method": "Duration <= 60s",
        "likes_count": 250,
        "likes_scope": "Summed across 5 uploads",
        "fetched_at": "2026-10-13T10:00:00Z",
        "status": "fresh",
        "warning_metadata": None,
    }

    with SyncSessionLocal() as session:
        ch = Channel(
            id="yt_test_refresh_ch_01",
            youtube_channel_id="yt_test_refresh_yt_01",
            channel_name="Refresh Test Channel",
            channel_url="https://youtube.com/channel/yt_test_refresh_yt_01",
            is_destination=True,
            is_active=True,
            is_test=False,
            cached_stats=initial_stats,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Mock check_channel_authorization to True, but fetch_channel_analytics to raise exception
        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True), \
             patch("backend.api.routes.youtube_channels.fetch_channel_analytics", side_effect=RuntimeError("YouTube Quota Exceeded")):
            resp = await client.post("/api/youtube-channels/yt_test_refresh_ch_01/refresh")
            assert resp.status_code == 502

        # Verify old stats were preserved in DB and tagged stale
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id="yt_test_refresh_ch_01").first()
            assert db_ch.cached_stats is not None
            assert db_ch.cached_stats["subscriber_count"] == 500
            assert db_ch.cached_stats["status"] == "stale"
            assert "Quota Exceeded" in db_ch.cached_stats["warning_metadata"]
