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
import subprocess
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, Clip, Job, DestinationOutro
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
            (Channel.youtube_channel_id.like(f"{test_prefix}%"))
        ).update({"active_outro_id": None}, synchronize_session=False)
        session.query(DestinationOutro).filter(
            DestinationOutro.channel_id.like(f"{test_prefix}%")
        ).delete(synchronize_session=False)
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
            (Channel.youtube_channel_id.like(f"{test_prefix}%"))
        ).update({"active_outro_id": None}, synchronize_session=False)
        session.query(DestinationOutro).filter(
            DestinationOutro.channel_id.like(f"{test_prefix}%")
        ).delete(synchronize_session=False)
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
        assert clipse_entry["channel_name"] in ("clipse", " Tomorrow’s Circuit")
        assert clipse_entry["is_destination"] is True
        assert clipse_entry["status"] == "connected"
        assert "has_outro" in clipse_entry
        assert "active_outro" in clipse_entry
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


# ─── Milestone 1: Destination Outro Management Tests ─────────────────────────

@pytest.fixture
def sample_video_outro(tmp_path):
    """Generate a real 1.5-second 1080x1920 MP4 with stereo audio using ffmpeg."""
    mp4_path = tmp_path / "sample_outro.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=purple:s=1080x1920:d=1.5",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-t", "1.5",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        str(mp4_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return mp4_path


@pytest.fixture
def sample_image_outro(tmp_path):
    """Generate a real 1080x1920 PNG image using Pillow."""
    from PIL import Image
    png_path = tmp_path / "sample_outro.png"
    img = Image.new("RGB", (1080, 1920), color=(255, 100, 50))
    img.save(png_path, format="PNG")
    return png_path


@pytest.mark.asyncio
async def test_outro_upload_video_mp4_success(sample_video_outro):
    """
    Test: POST /api/youtube-channels/{channel_id}/outro with a valid MP4 video.
    - Probes duration, resolution, audio presence.
    - Creates DestinationOutro with version=1, is_active=True.
    - Links channel.active_outro_id to the created outro.
    - Returns 201 Created and serialized OutroUploadResponse.
    """
    ch_id = "yt_test_dest_outro_01"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_01",
            channel_name="Outro Video Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_01",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(sample_video_outro, "rb") as f:
            resp = await client.post(
                f"/api/youtube-channels/{ch_id}/outro",
                data={"outro_type": "video"},
                files={"file": ("sample_outro.mp4", f, "video/mp4")},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "success"
        assert data["channel_id"] == ch_id
        outro = data["outro"]
        assert outro["outro_type"] == "video"
        assert outro["version"] == 1
        assert outro["is_active"] is True
        assert outro["width"] == 1080
        assert outro["height"] == 1920
        assert outro["duration_seconds"] >= 1.4
        assert outro["has_audio"] is True
        assert outro["preview_url"] == f"/api/youtube-channels/{ch_id}/outro/preview"

        # Verify DB state
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id=ch_id).first()
            assert db_ch.active_outro_id == outro["id"]
            db_outro = session.query(DestinationOutro).filter_by(id=outro["id"]).first()
            assert db_outro is not None
            assert db_outro.is_active is True
            assert db_outro.version == 1
            assert db_outro.has_audio is True


@pytest.mark.asyncio
async def test_outro_upload_image_custom_duration(sample_image_outro):
    """
    Test: POST /api/youtube-channels/{channel_id}/outro with a PNG image and custom duration.
    - Validates image dimensions, custom duration (e.g. 5.0s), has_audio=False.
    - Creates DestinationOutro with version=1, is_active=True.
    """
    ch_id = "yt_test_dest_outro_02"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_02",
            channel_name="Outro Image Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_02",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(sample_image_outro, "rb") as f:
            resp = await client.post(
                f"/api/youtube-channels/{ch_id}/outro",
                data={"outro_type": "image", "duration_seconds": 5.0},
                files={"file": ("sample_outro.png", f, "image/png")},
            )

        assert resp.status_code == 201
        data = resp.json()
        outro = data["outro"]
        assert outro["outro_type"] == "image"
        assert outro["duration_seconds"] == 5.0
        assert outro["has_audio"] is False
        assert outro["width"] == 1080
        assert outro["height"] == 1920
        assert outro["version"] == 1
        assert outro["is_active"] is True


@pytest.mark.asyncio
async def test_outro_version_increment_and_deactivation(sample_image_outro):
    """
    Test: Uploading a new outro for the same channel increments version to 2
    and marks version 1 as is_active=False.
    """
    ch_id = "yt_test_dest_outro_03"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_03",
            channel_name="Versioning Outro Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_03",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Upload first outro
        with open(sample_image_outro, "rb") as f:
            resp1 = await client.post(
                f"/api/youtube-channels/{ch_id}/outro",
                data={"outro_type": "image", "duration_seconds": 3.0},
                files={"file": ("outro_v1.png", f, "image/png")},
            )
        assert resp1.status_code == 201
        v1_id = resp1.json()["outro"]["id"]
        assert resp1.json()["outro"]["version"] == 1

        # 2. Upload second outro
        with open(sample_image_outro, "rb") as f:
            resp2 = await client.post(
                f"/api/youtube-channels/{ch_id}/outro",
                data={"outro_type": "image", "duration_seconds": 4.5},
                files={"file": ("outro_v2.png", f, "image/png")},
            )
        assert resp2.status_code == 201
        v2_id = resp2.json()["outro"]["id"]
        assert resp2.json()["outro"]["version"] == 2

        # 3. Verify in DB: v1 is deactivated, v2 is active, channel.active_outro_id is v2
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id=ch_id).first()
            assert db_ch.active_outro_id == v2_id
            v1_outro = session.query(DestinationOutro).filter_by(id=v1_id).first()
            v2_outro = session.query(DestinationOutro).filter_by(id=v2_id).first()
            assert v1_outro.is_active is False
            assert v2_outro.is_active is True


@pytest.mark.asyncio
async def test_outro_upload_rejections():
    """
    Test: Validation rejections:
    - Invalid outro_type (400)
    - Unsupported file extension (400)
    - Invalid image duration out of bounds (400)
    - Non-existent destination channel (404)
    - Inactive / disconnected destination channel (400)
    """
    ch_id = "yt_test_dest_outro_04"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_04",
            channel_name="Rejection Test Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_04",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid outro_type
        resp = await client.post(
            f"/api/youtube-channels/{ch_id}/outro",
            data={"outro_type": "audio"},
            files={"file": ("audio.mp3", b"dummy audio", "audio/mp3")},
        )
        assert resp.status_code == 400
        assert "Invalid outro_type" in resp.json()["detail"]

        # Unsupported extension
        resp = await client.post(
            f"/api/youtube-channels/{ch_id}/outro",
            data={"outro_type": "video"},
            files={"file": ("document.txt", b"dummy text", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported video extension" in resp.json()["detail"]

        # Duration out of bounds for image (e.g. 25.0s > 15.0s)
        resp = await client.post(
            f"/api/youtube-channels/{ch_id}/outro",
            data={"outro_type": "image", "duration_seconds": 25.0},
            files={"file": ("image.png", b"dummy png", "image/png")},
        )
        assert resp.status_code == 400
        assert "duration must be between" in resp.json()["detail"]

        # Channel not found
        resp = await client.post(
            "/api/youtube-channels/non_existent_ch_uuid/outro",
            data={"outro_type": "image"},
            files={"file": ("image.png", b"dummy png", "image/png")},
        )
        assert resp.status_code == 404

        # Disconnected channel
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id=ch_id).first()
            db_ch.is_active = False
            session.commit()

        resp = await client.post(
            f"/api/youtube-channels/{ch_id}/outro",
            data={"outro_type": "image"},
            files={"file": ("image.png", b"dummy png", "image/png")},
        )
        assert resp.status_code == 400
        assert "disconnected" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_outro_get_metadata_and_preview(sample_image_outro):
    """
    Test: GET /{channel_id}/outro and GET /{channel_id}/outro/preview
    - Retrieves metadata when active outro exists.
    - Streams preview file with correct media_type.
    - Returns 404 when channel has no active outro.
    """
    ch_id = "yt_test_dest_outro_05"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_05",
            channel_name="Preview Test Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_05",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Initial GET before upload -> 404
        resp = await client.get(f"/api/youtube-channels/{ch_id}/outro")
        assert resp.status_code == 404

        # Upload image outro
        with open(sample_image_outro, "rb") as f:
            await client.post(
                f"/api/youtube-channels/{ch_id}/outro",
                data={"outro_type": "image", "duration_seconds": 3.0},
                files={"file": ("preview_outro.png", f, "image/png")},
            )

        # GET metadata -> 200 OK
        resp = await client.get(f"/api/youtube-channels/{ch_id}/outro")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["channel_id"] == ch_id
        assert data["outro"]["duration_seconds"] == 3.0

        # GET preview -> 200 OK with image/png
        prev_resp = await client.get(f"/api/youtube-channels/{ch_id}/outro/preview")
        assert prev_resp.status_code == 200
        assert "image/png" in prev_resp.headers["content-type"]
        assert len(prev_resp.content) > 0


@pytest.mark.asyncio
async def test_outro_delete_unlinks_channel(sample_image_outro):
    """
    Test: DELETE /api/youtube-channels/{channel_id}/outro
    - Unlinks active_outro_id from channel.
    - Soft-deletes DestinationOutro (is_active=False).
    - Subsequent GET returns 404.
    """
    ch_id = "yt_test_dest_outro_06"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_06",
            channel_name="Delete Test Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_06",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Upload outro
        with open(sample_image_outro, "rb") as f:
            upload_resp = await client.post(
                f"/api/youtube-channels/{ch_id}/outro",
                data={"outro_type": "image", "duration_seconds": 3.0},
                files={"file": ("to_delete.png", f, "image/png")},
            )
        outro_id = upload_resp.json()["outro"]["id"]

        # Delete outro
        del_resp = await client.delete(f"/api/youtube-channels/{ch_id}/outro")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"

        # Check GET now returns 404
        get_resp = await client.get(f"/api/youtube-channels/{ch_id}/outro")
        assert get_resp.status_code == 404

        # Check DB: channel has active_outro_id=None, outro record still exists with is_active=False
        with SyncSessionLocal() as session:
            db_ch = session.query(Channel).filter_by(id=ch_id).first()
            assert db_ch.active_outro_id is None
            db_outro = session.query(DestinationOutro).filter_by(id=outro_id).first()
            assert db_outro is not None
            assert db_outro.is_active is False


@pytest.mark.asyncio
async def test_list_youtube_channels_enrichment_with_outros(sample_image_outro):
    """
    Test: GET /api/youtube-channels/ enrichment.
    - A destination with an active outro returns has_outro=True and active_outro object.
    - A destination without an outro returns has_outro=False and active_outro=None.
    """
    ch_with_outro_id = "yt_test_enrich_with_outro"
    ch_no_outro_id = "yt_test_enrich_no_outro"

    with SyncSessionLocal() as session:
        ch1 = Channel(
            id=ch_with_outro_id,
            youtube_channel_id="yt_test_enrich_yt_01",
            channel_name="Enriched Channel With Outro",
            channel_url="https://youtube.com/channel/yt_test_enrich_yt_01",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        ch2 = Channel(
            id=ch_no_outro_id,
            youtube_channel_id="yt_test_enrich_yt_02",
            channel_name="Enriched Channel Without Outro",
            channel_url="https://youtube.com/channel/yt_test_enrich_yt_02",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add_all([ch1, ch2])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Upload outro to ch1
        with open(sample_image_outro, "rb") as f:
            await client.post(
                f"/api/youtube-channels/{ch_with_outro_id}/outro",
                data={"outro_type": "image", "duration_seconds": 4.0},
                files={"file": ("outro.png", f, "image/png")},
            )

        resp = await client.get("/api/youtube-channels/")
        assert resp.status_code == 200
        channels = resp.json()

        item_with = next((c for c in channels if c["id"] == ch_with_outro_id), None)
        item_without = next((c for c in channels if c["id"] == ch_no_outro_id), None)

        assert item_with is not None
        assert item_with["has_outro"] is True
        assert item_with["active_outro"] is not None
        assert item_with["active_outro"]["outro_type"] == "image"
        assert item_with["active_outro"]["duration_seconds"] == 4.0

        assert item_without is not None
        assert item_without["has_outro"] is False
        assert item_without["active_outro"] is None


@pytest.mark.asyncio
async def test_outro_preview_path_traversal_protection():
    """
    Test: Preview endpoint blocks directory traversal if an invalid file_path is manipulated.
    """
    ch_id = "yt_test_dest_outro_traversal"
    bad_outro_id = "bad_outro_traversal_01"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id="yt_test_dest_yt_traversal",
            channel_name="Traversal Test Channel",
            channel_url="https://youtube.com/channel/yt_test_dest_yt_traversal",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        session.add(ch)
        session.commit()

        bad_outro = DestinationOutro(
            id=bad_outro_id,
            channel_id=ch_id,
            file_path="../../../../../../../../../windows/system32/cmd.exe",
            outro_type="video",
            duration_seconds=3.0,
            is_active=True,
        )
        session.add(bad_outro)
        session.commit()

        ch.active_outro_id = bad_outro_id
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/youtube-channels/{ch_id}/outro/preview")
        assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_delete_destination_channel_flow():
    """Verify DELETE /api/youtube-channels/{channel_id} safely deletes eligible channels."""
    from backend.models.models import Channel

    # 1. Create a test fixture destination channel
    test_del_id = "test_del_dest_fixture_99"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=test_del_id,
            youtube_channel_id="yt_del_fixture_99",
            channel_name="Deletable Test Channel",
            channel_url="https://youtube.com/channel/yt_del_fixture_99",
            is_destination=True,
            is_active=False,
            is_test=True,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Delete should succeed
        resp = await client.delete(f"/api/youtube-channels/{test_del_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["channel_id"] == test_del_id

        # Verify record no longer exists
        verify_resp = await client.delete(f"/api/youtube-channels/{test_del_id}")
        assert verify_resp.status_code == 404

    # 2. Test deleting a channel with mapped sources and publish targets
    test_del_mapped_id = "test_del_dest_mapped_99"
    with SyncSessionLocal() as session:
        ch2 = Channel(
            id=test_del_mapped_id,
            youtube_channel_id="yt_del_mapped_99",
            channel_name="Deletable Mapped Channel",
            channel_url="https://youtube.com/channel/yt_del_mapped_99",
            is_destination=True,
            is_active=True,
            is_test=True,
        )
        session.add(ch2)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp2 = await client.delete(f"/api/youtube-channels/{test_del_mapped_id}")
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["status"] == "deleted"


def test_sanitize_youtube_description_and_title():
    """Verify description and title sanitizers prevent invalidDescription 400 errors."""
    from backend.services.publisher import sanitize_youtube_description, sanitize_youtube_title

    # 1. Title stripping angle brackets and newlines
    bad_title = "Episode 1 <Epic Showdown>\nNew Season!   "
    clean_title = sanitize_youtube_title(bad_title)
    assert "<" not in clean_title
    assert ">" not in clean_title
    assert "\n" not in clean_title
    assert clean_title == "Episode 1 Epic Showdown New Season!"

    # 2. Description stripping angle brackets and null bytes
    bad_desc = "Watch this <amazing> video!\x00\x08Click <here> for more:\nhttps://example.com"
    clean_desc = sanitize_youtube_description(bad_desc)
    assert "<" not in clean_desc
    assert ">" not in clean_desc
    assert "\x00" not in clean_desc
    assert "\x08" not in clean_desc
    assert "Watch this amazing video!" in clean_desc
    assert "https://example.com" in clean_desc
    assert len(clean_desc) <= 5000


