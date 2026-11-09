"""
ClipForge — Phase 1 Remaining Fixes Regression Test Suite
Covers:
1. Destination disconnection and deletion API paths:
   - POST /api/youtube-channels/{channel_id}/disconnect
   - DELETE /api/channels/{channel_id}
   Ensures every dependent source profile can no longer auto-publish using the invalid destination,
   while preserving auto_clip and unrelated settings.
2. Manual Upload and Schedule:
   - POST /api/publish/publish-now
   - POST /api/publish/schedule
   Ensures missing, nonexistent, inactive, or non-destination channels are rejected (HTTP 400)
   before any publishing task is queued or status set to queued.
3. Legacy publishing endpoint:
   - POST /api/clips/{clip_id}/publish
   Ensures destination requirement, destination status validation, explicit credential use,
   prevention of fallback to global token, and non-blocking asyncio.to_thread execution.
4. Auto-publish API-level enforcement:
   - Rejects creating or updating channels with auto_publish=True without valid active destination.
"""
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, Clip, Video
from backend.services.publisher import (
    _resolve_token_file,
    get_youtube_client,
)


@pytest.fixture(autouse=True)
async def cleanup_test_records():
    """Clean up synthetic test records before and after each test and dispose engine."""
    prefix = "test_p1_"
    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.id.like(f"{prefix}%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like(f"{prefix}%")).delete(synchronize_session=False)
        session.query(Channel).filter(
            (Channel.id.like(f"{prefix}%")) | (Channel.youtube_channel_id.like(f"{prefix}%"))
        ).delete(synchronize_session=False)
        session.commit()
    yield
    try:
        await engine.dispose()
    except Exception:
        pass
    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.id.like(f"{prefix}%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like(f"{prefix}%")).delete(synchronize_session=False)
        session.query(Channel).filter(
            (Channel.id.like(f"{prefix}%")) | (Channel.youtube_channel_id.like(f"{prefix}%"))
        ).delete(synchronize_session=False)
        session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Destination Disconnection and Deletion (Requirement 1)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_destination_disconnect_resets_dependent_source_auto_publish():
    """
    POST /api/youtube-channels/{id}/disconnect
    - Sets destination is_active = False.
    - Sets auto_publish = False and publish_destination_id = None on dependent sources.
    - Preserves auto_clip and processing_profile on dependent sources.
    - Leaves unrelated source channels untouched.
    """
    dest_id = f"test_p1_dest_{uuid.uuid4().hex[:6]}"
    dest_yt = f"test_p1_yt_{uuid.uuid4().hex[:6]}"
    other_dest_id = f"test_p1_otherdest_{uuid.uuid4().hex[:6]}"
    src1_id = f"test_p1_src1_{uuid.uuid4().hex[:6]}"
    src2_id = f"test_p1_src2_{uuid.uuid4().hex[:6]}"
    src_other_id = f"test_p1_src_other_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        # Destination channel to disconnect
        dest = Channel(
            id=dest_id,
            youtube_channel_id=dest_yt,
            channel_name="Disconnect Target Dest",
            channel_url="https://youtube.com/@target_dest",
            is_destination=True,
            is_default_destination=True,
            is_active=True,
            is_test=False,
        )
        # Another destination channel (unrelated)
        other_dest = Channel(
            id=other_dest_id,
            youtube_channel_id=f"UC_{other_dest_id}",
            channel_name="Unrelated Dest",
            channel_url="https://youtube.com/@other_dest",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        # Dependent source channel 1 (points to dest_id)
        src1 = Channel(
            id=src1_id,
            youtube_channel_id=f"UC_{src1_id}",
            channel_name="Dependent Source 1",
            channel_url="https://youtube.com/@src1",
            is_destination=False,
            is_active=True,
            auto_clip=True,
            auto_publish=True,
            publish_destination_id=dest_id,
            processing_profile={"min_score": 0.85, "resolution": "1080p"},
            is_test=False,
        )
        # Dependent source channel 2 (also points to dest_id)
        src2 = Channel(
            id=src2_id,
            youtube_channel_id=f"UC_{src2_id}",
            channel_name="Dependent Source 2",
            channel_url="https://youtube.com/@src2",
            is_destination=False,
            is_active=True,
            auto_clip=True,
            auto_publish=True,
            publish_destination_id=dest_id,
            processing_profile={"min_score": 0.75},
            is_test=False,
        )
        # Unrelated source channel (points to other_dest_id)
        src_other = Channel(
            id=src_other_id,
            youtube_channel_id=f"UC_{src_other_id}",
            channel_name="Unrelated Source",
            channel_url="https://youtube.com/@src_other",
            is_destination=False,
            is_active=True,
            auto_clip=True,
            auto_publish=True,
            publish_destination_id=other_dest_id,
            processing_profile={"min_score": 0.90},
            is_test=False,
        )
        session.add_all([dest, other_dest, src1, src2, src_other])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/youtube-channels/{dest_id}/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["is_active"] is False

    with SyncSessionLocal() as session:
        # Verify destination state
        db_dest = session.query(Channel).filter_by(id=dest_id).first()
        assert db_dest.is_active is False
        assert db_dest.is_destination is True  # Invariant: remains a destination

        # Verify dependent source 1
        db_src1 = session.query(Channel).filter_by(id=src1_id).first()
        assert db_src1.auto_publish is False, "auto_publish must be disabled upon destination disconnect"
        assert db_src1.publish_destination_id is None, "publish_destination_id must be cleared"
        assert db_src1.auto_clip is True, "auto_clip MUST be preserved"
        assert db_src1.processing_profile == {"min_score": 0.85, "resolution": "1080p"}, "profile must be preserved"

        # Verify dependent source 2
        db_src2 = session.query(Channel).filter_by(id=src2_id).first()
        assert db_src2.auto_publish is False, "auto_publish must be disabled"
        assert db_src2.publish_destination_id is None, "publish_destination_id must be cleared"
        assert db_src2.auto_clip is True, "auto_clip MUST be preserved"

        # Verify unrelated source is untouched
        db_other = session.query(Channel).filter_by(id=src_other_id).first()
        assert db_other.auto_publish is True, "Unrelated source auto_publish must not be altered"
        assert db_other.publish_destination_id == other_dest_id


@pytest.mark.asyncio
async def test_destination_delete_resets_dependent_source_auto_publish():
    """
    DELETE /api/channels/{id}
    - Deletes destination channel record.
    - Sets auto_publish = False and publish_destination_id = None on all dependent sources.
    - Preserves auto_clip and processing settings on dependent sources.
    """
    dest_id = f"test_p1_deldest_{uuid.uuid4().hex[:6]}"
    src_id = f"test_p1_delsrc_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        dest = Channel(
            id=dest_id,
            youtube_channel_id=f"UC_{dest_id}",
            channel_name="Delete Target Dest",
            channel_url="https://youtube.com/@delete_dest",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        src = Channel(
            id=src_id,
            youtube_channel_id=f"UC_{src_id}",
            channel_name="Dependent Source on Deleted Dest",
            channel_url="https://youtube.com/@src_del",
            is_destination=False,
            is_active=True,
            auto_clip=True,
            auto_publish=True,
            publish_destination_id=dest_id,
            processing_profile={"target_duration": 45},
            is_test=False,
        )
        session.add_all([dest, src])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/channels/{dest_id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Channel removed"

    with SyncSessionLocal() as session:
        # Destination is deleted
        db_dest = session.query(Channel).filter_by(id=dest_id).first()
        assert db_dest is None

        # Source auto_publish is disabled and destination cleared, auto_clip preserved
        db_src = session.query(Channel).filter_by(id=src_id).first()
        assert db_src is not None
        assert db_src.auto_publish is False, "auto_publish must be disabled upon destination deletion"
        assert db_src.publish_destination_id is None, "publish_destination_id must be cleared"
        assert db_src.auto_clip is True, "auto_clip MUST be preserved"
        assert db_src.processing_profile == {"target_duration": 45}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Manual Upload and Schedule Destination Validation (Requirement 2)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_publish_now_destination_validation(tmp_path):
    """
    POST /api/publish/publish-now
    Rejects missing, nonexistent, inactive, or non-destination channels with HTTP 400
    BEFORE queueing any Celery task or setting status to queued.
    Accepts valid active destination and queues Celery task.
    """
    fake_video_file = tmp_path / "valid_clip.mp4"
    fake_video_file.write_bytes(b"dummy video data")

    clip_id = f"test_p1_clip_{uuid.uuid4().hex[:6]}"
    active_dest_id = f"test_p1_activedest_{uuid.uuid4().hex[:6]}"
    inactive_dest_id = f"test_p1_inactivedest_{uuid.uuid4().hex[:6]}"
    source_ch_id = f"test_p1_nondest_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        # Active destination
        active_dest = Channel(
            id=active_dest_id,
            youtube_channel_id=f"UC_{active_dest_id}",
            channel_name="Active Destination",
            channel_url="https://youtube.com/@activedest",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        # Inactive destination
        inactive_dest = Channel(
            id=inactive_dest_id,
            youtube_channel_id=f"UC_{inactive_dest_id}",
            channel_name="Inactive Destination",
            channel_url="https://youtube.com/@inactivedest",
            is_destination=True,
            is_active=False,
            is_test=False,
        )
        # Non-destination channel (monitored source)
        source_ch = Channel(
            id=source_ch_id,
            youtube_channel_id=f"UC_{source_ch_id}",
            channel_name="Monitored Source Only",
            channel_url="https://youtube.com/@nondest",
            is_destination=False,
            is_active=True,
            is_test=False,
        )
        # Clip
        clip = Clip(
            id=clip_id,
            video_id="dummy_vid",
            title="Test Publish Now Clip",
            output_path=str(fake_video_file),
            start_time=0.0,
            end_time=30.0,
            duration=30.0,
            publish_status="draft",
            publish_destination_id=None,
        )
        session.add_all([active_dest, inactive_dest, source_ch, clip])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_celery:
            # Case 1: Missing destination channel
            resp1 = await client.post("/api/publish/publish-now", json={
                "clip_id": clip_id,
                "title": "Title 1",
            })
            assert resp1.status_code == 400
            assert "Publish destination channel is required" in resp1.json()["detail"]
            assert mock_celery.call_count == 0

            # Case 2: Nonexistent destination channel
            resp2 = await client.post("/api/publish/publish-now", json={
                "clip_id": clip_id,
                "title": "Title 2",
                "destination_channel_id": "nonexistent_dest_id_12345",
            })
            assert resp2.status_code == 400
            assert "Invalid destination channel" in resp2.json()["detail"]
            assert mock_celery.call_count == 0

            # Case 3: Inactive destination channel
            resp3 = await client.post("/api/publish/publish-now", json={
                "clip_id": clip_id,
                "title": "Title 3",
                "destination_channel_id": inactive_dest_id,
            })
            assert resp3.status_code == 400
            assert "Invalid destination channel" in resp3.json()["detail"]
            assert mock_celery.call_count == 0

            # Case 4: Non-destination channel (source channel)
            resp4 = await client.post("/api/publish/publish-now", json={
                "clip_id": clip_id,
                "title": "Title 4",
                "destination_channel_id": source_ch_id,
            })
            assert resp4.status_code == 400
            assert "Invalid destination channel" in resp4.json()["detail"]
            assert mock_celery.call_count == 0

            # Case 4b: Active destination channel without valid OAuth credentials
            with patch("backend.services.publisher.check_channel_authorization", return_value=False):
                resp4b = await client.post("/api/publish/publish-now", json={
                    "clip_id": clip_id,
                    "title": "Title 4b Unauth",
                    "destination_channel_id": active_dest_id,
                    "privacy": "private",
                })
                assert resp4b.status_code == 400
                assert "not authorized or OAuth credentials are invalid" in resp4b.json()["detail"]
                assert mock_celery.call_count == 0

            # Verify clip is still in draft state after all invalid attempts
            with SyncSessionLocal() as session:
                refreshed_clip = session.query(Clip).filter_by(id=clip_id).first()
                assert refreshed_clip.publish_status == "draft"

            # Case 5: Valid active destination channel with verified credentials
            mock_task = MagicMock()
            mock_task.id = "mock-celery-task-id-123"
            mock_celery.return_value = mock_task

            with patch("backend.services.publisher.check_channel_authorization", return_value=True):
                resp5 = await client.post("/api/publish/publish-now", json={
                    "clip_id": clip_id,
                    "title": "Title 5 Valid",
                    "destination_channel_id": active_dest_id,
                    "privacy": "private",
                })
                assert resp5.status_code == 202
                data5 = resp5.json()
                assert data5["status"] == "queued"
                assert mock_celery.call_count == 1
                # Verify Celery kwargs received verified destination ID
                _, kwargs = mock_celery.call_args
                assert kwargs["kwargs"]["channel_id"] == active_dest_id


@pytest.mark.asyncio
async def test_schedule_publish_destination_validation(tmp_path):
    """
    POST /api/publish/schedule
    Rejects missing, nonexistent, inactive, or non-destination channels with HTTP 400
    BEFORE setting clip status to queued or scheduling the clip.
    Accepts valid active destination and sets status='queued'.
    """
    dummy_file = tmp_path / "scheduled_clip.mp4"
    dummy_file.write_bytes(b"dummy_content_bytes")

    clip_id = f"test_p1_sched_clip_{uuid.uuid4().hex[:6]}"
    active_dest_id = f"test_p1_sched_act_{uuid.uuid4().hex[:6]}"
    inactive_dest_id = f"test_p1_sched_inact_{uuid.uuid4().hex[:6]}"
    source_ch_id = f"test_p1_sched_nondest_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        active_dest = Channel(
            id=active_dest_id,
            youtube_channel_id=f"UC_{active_dest_id}",
            channel_name="Active Sched Dest",
            channel_url="https://youtube.com/@schedact",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        inactive_dest = Channel(
            id=inactive_dest_id,
            youtube_channel_id=f"UC_{inactive_dest_id}",
            channel_name="Inactive Sched Dest",
            channel_url="https://youtube.com/@schedinact",
            is_destination=True,
            is_active=False,
            is_test=False,
        )
        source_ch = Channel(
            id=source_ch_id,
            youtube_channel_id=f"UC_{source_ch_id}",
            channel_name="Source Channel Only",
            channel_url="https://youtube.com/@schednondest",
            is_destination=False,
            is_active=True,
            is_test=False,
        )
        clip = Clip(
            id=clip_id,
            video_id="dummy_vid",
            title="Clip for Scheduling",
            output_path=str(dummy_file),
            status="completed",
            start_time=0.0,
            end_time=25.0,
            duration=25.0,
            publish_status="draft",
            publish_destination_id=None,
        )
        session.add_all([active_dest, inactive_dest, source_ch, clip])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: Missing destination
        r1 = await client.post("/api/publish/schedule", json={
            "clip_id": clip_id,
            "scheduled_at": "2026-11-01T12:00:00Z",
        })
        assert r1.status_code == 400
        assert "Publish destination channel is required" in r1.json()["detail"]

        # Case 2: Nonexistent destination
        r2 = await client.post("/api/publish/schedule", json={
            "clip_id": clip_id,
            "destination_channel_id": "nonexistent_dest_id",
            "scheduled_at": "2026-11-01T12:00:00Z",
        })
        assert r2.status_code == 400
        assert "Invalid destination channel" in r2.json()["detail"]

        # Case 3: Inactive destination
        r3 = await client.post("/api/publish/schedule", json={
            "clip_id": clip_id,
            "destination_channel_id": inactive_dest_id,
            "scheduled_at": "2026-11-01T12:00:00Z",
        })
        assert r3.status_code == 400
        assert "Invalid destination channel" in r3.json()["detail"]

        # Case 4: Non-destination channel
        r4 = await client.post("/api/publish/schedule", json={
            "clip_id": clip_id,
            "destination_channel_id": source_ch_id,
            "scheduled_at": "2026-11-01T12:00:00Z",
        })
        assert r4.status_code == 400
        assert "Invalid destination channel" in r4.json()["detail"]

        # Case 4b: Active destination channel without valid OAuth credentials
        with patch("backend.services.publisher.check_channel_authorization", return_value=False):
            r4b = await client.post("/api/publish/schedule", json={
                "clip_id": clip_id,
                "destination_channel_id": active_dest_id,
                "scheduled_at": "2026-11-01T12:00:00Z",
            })
            assert r4b.status_code == 400
            assert "not authorized or OAuth credentials are invalid" in r4b.json()["detail"]

        # Verify status did not change to queued
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            assert c.publish_status == "draft"

        # Case 5: Valid active destination with verified credentials
        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            r5 = await client.post("/api/publish/schedule", json={
                "clip_id": clip_id,
                "destination_channel_id": active_dest_id,
                "scheduled_at": "2026-11-01T12:00:00Z",
            })
            assert r5.status_code == 200
            assert r5.json()["message"] == "Clip scheduled"

        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            assert c.publish_status == "queued"
            assert c.publish_destination_id == active_dest_id


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Legacy Publishing Endpoint Validation & Credential Safety (Requirement 3)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_legacy_publish_clip_destination_validation(tmp_path):
    """
    POST /api/clips/{clip_id}/publish
    - Rejects missing publish_destination_id with HTTP 400.
    - Rejects nonexistent, inactive, or non-destination channels with HTTP 400.
    - For valid destinations: passes resolved channel_id to upload_short via asyncio.to_thread.
    """
    fake_video_file = tmp_path / "legacy_clip.mp4"
    fake_video_file.write_bytes(b"dummy video data")

    clip_id = f"test_p1_leg_clip_{uuid.uuid4().hex[:6]}"
    active_dest_id = f"test_p1_leg_act_{uuid.uuid4().hex[:6]}"
    active_yt_id = f"UC_{active_dest_id}"
    inactive_dest_id = f"test_p1_leg_inact_{uuid.uuid4().hex[:6]}"
    source_ch_id = f"test_p1_leg_nondest_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        active_dest = Channel(
            id=active_dest_id,
            youtube_channel_id=active_yt_id,
            channel_name="Legacy Active Dest",
            channel_url="https://youtube.com/@legact",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        inactive_dest = Channel(
            id=inactive_dest_id,
            youtube_channel_id=f"UC_{inactive_dest_id}",
            channel_name="Legacy Inactive Dest",
            channel_url="https://youtube.com/@leginact",
            is_destination=True,
            is_active=False,
            is_test=False,
        )
        source_ch = Channel(
            id=source_ch_id,
            youtube_channel_id=f"UC_{source_ch_id}",
            channel_name="Legacy Source Only",
            channel_url="https://youtube.com/@legnondest",
            is_destination=False,
            is_active=True,
            is_test=False,
        )
        clip = Clip(
            id=clip_id,
            video_id="dummy_vid",
            title="Legacy Publish Clip",
            output_path=str(fake_video_file),
            start_time=0.0,
            end_time=20.0,
            duration=20.0,
            publish_status="draft",
            publish_destination_id=None,
        )
        session.add_all([active_dest, inactive_dest, source_ch, clip])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: Clip has no publish_destination_id
        r1 = await client.post(f"/api/clips/{clip_id}/publish")
        assert r1.status_code == 400
        assert "Publish destination channel is required" in r1.json()["detail"]

        # Case 2: Inactive destination assigned
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            c.publish_destination_id = inactive_dest_id
            session.commit()

        r2 = await client.post(f"/api/clips/{clip_id}/publish")
        assert r2.status_code == 400
        assert "Invalid destination channel" in r2.json()["detail"]

        # Case 3: Non-destination assigned
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            c.publish_destination_id = source_ch_id
            session.commit()

        r3 = await client.post(f"/api/clips/{clip_id}/publish")
        assert r3.status_code == 400
        assert "Invalid destination channel" in r3.json()["detail"]

        # Case 3b: Active destination assigned but lacks OAuth credentials
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            c.publish_destination_id = active_dest_id
            session.commit()

        with patch("backend.services.publisher.check_channel_authorization", return_value=False):
            r3b = await client.post(f"/api/clips/{clip_id}/publish")
            assert r3b.status_code == 400
            assert "not authorized or OAuth credentials are invalid" in r3b.json()["detail"]

        # Case 4: Valid active destination assigned with verified credentials
        mock_upload_res = {
            "id": "mock_yt_vid_999",
            "url": "https://www.youtube.com/shorts/mock_yt_vid_999",
            "title": "Legacy Publish Clip #Shorts",
            "privacy": "private",
            "privacy_confirmed": True,
            "remediation": None,
        }

        with patch("backend.services.publisher.check_channel_authorization", return_value=True), \
             patch("backend.services.publisher.upload_short", return_value=mock_upload_res) as mock_upload:
            r4 = await client.post(f"/api/clips/{clip_id}/publish")
            assert r4.status_code == 200
            data4 = r4.json()
            assert data4["status"] == "published"
            assert data4["youtube_short_id"] == "mock_yt_vid_999"

            # Verify upload_short was invoked with resolved destination channel_id
            assert mock_upload.call_count == 1
            _, kwargs = mock_upload.call_args
            assert kwargs["channel_id"] == active_yt_id, "Must pass the destination's credentials identifier"
            assert kwargs["privacy"] == "private"


def test_token_resolution_does_not_fall_back_to_global_token():
    """
    _resolve_token_file(channel_id):
    - When channel_id is provided, returns youtube_token_{channel_id}.json.
    - NEVER falls back to global youtube_token.json when channel_id is provided,
      even if the destination token file does not exist on disk.
    - When channel_id is None, returns global youtube_token.json.
    """
    dest_chan_id = "UC_unique_dest_no_token_123"
    chan_token_path = _resolve_token_file(dest_chan_id)
    assert chan_token_path.name == f"youtube_token_{dest_chan_id}.json"
    assert chan_token_path.name != "youtube_token.json"

    # Default fallback ONLY when channel_id is None
    global_token_path = _resolve_token_file(None)
    assert global_token_path.name == "youtube_token.json"


def test_get_youtube_client_rejects_missing_destination_credentials():
    """
    get_youtube_client(channel_id):
    When a destination channel ID is specified without valid credentials on disk,
    it raises ValueError requiring destination-specific authorization and does
    NOT fall back to the global token file.
    """
    nonexistent_dest_chan = "UC_no_creds_fixture_999"
    with pytest.raises(ValueError) as excinfo:
        get_youtube_client(channel_id=nonexistent_dest_chan)
    err_msg = str(excinfo.value)
    assert "YouTube authorization required for destination channel" in err_msg
    assert nonexistent_dest_chan in err_msg


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Auto-publish API Enforcement (Check existing fix)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_channel_auto_publish_requires_valid_destination():
    """
    POST /api/channels/
    - auto_publish=True without publish_destination_id -> HTTP 422
    - auto_publish=True with nonexistent destination -> HTTP 400
    - auto_publish=True with inactive destination -> HTTP 400
    - auto_publish=True with non-destination channel -> HTTP 400
    - auto_publish=True with valid active destination -> HTTP 200
    """
    active_dest_id = f"test_p1_add_dest_{uuid.uuid4().hex[:6]}"
    inactive_dest_id = f"test_p1_add_inact_{uuid.uuid4().hex[:6]}"
    source_ch_id = f"test_p1_add_src_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        active_dest = Channel(
            id=active_dest_id,
            youtube_channel_id=f"UC_{active_dest_id}",
            channel_name="Add Dest Active",
            channel_url="https://youtube.com/@addact",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        inactive_dest = Channel(
            id=inactive_dest_id,
            youtube_channel_id=f"UC_{inactive_dest_id}",
            channel_name="Add Dest Inactive",
            channel_url="https://youtube.com/@addinact",
            is_destination=True,
            is_active=False,
            is_test=False,
        )
        source_ch = Channel(
            id=source_ch_id,
            youtube_channel_id=f"UC_{source_ch_id}",
            channel_name="Add Source Channel",
            channel_url="https://youtube.com/@addsrc",
            is_destination=False,
            is_active=True,
            is_test=False,
        )
        session.add_all([active_dest, inactive_dest, source_ch])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=[{"id": "v1", "channel_id": f"UC_{uuid.uuid4().hex[:8]}", "channel": "Mock Channel"}]):
            # Case 1: auto_publish=True without destination
            r1 = await client.post("/api/channels/", json={
                "channel_url": "https://www.youtube.com/@channel_test_auto_1",
                "auto_clip": True,
                "auto_publish": True,
                "publish_destination_id": None,
            })
            assert r1.status_code == 422
            assert "Cannot enable auto-publish without selecting a valid publish destination" in r1.json()["detail"]

            # Case 2: auto_publish=True with nonexistent destination
            r2 = await client.post("/api/channels/", json={
                "channel_url": "https://www.youtube.com/@channel_test_auto_2",
                "auto_clip": True,
                "auto_publish": True,
                "publish_destination_id": "nonexistent_dest_id",
            })
            assert r2.status_code == 400
            assert "Invalid publish destination" in r2.json()["detail"]

            # Case 3: auto_publish=True with inactive destination
            r3 = await client.post("/api/channels/", json={
                "channel_url": "https://www.youtube.com/@channel_test_auto_3",
                "auto_clip": True,
                "auto_publish": True,
                "publish_destination_id": inactive_dest_id,
            })
            assert r3.status_code == 400
            assert "Publish destination channel is not active" in r3.json()["detail"]

            # Case 4: auto_publish=True with non-destination channel
            r4 = await client.post("/api/channels/", json={
                "channel_url": "https://www.youtube.com/@channel_test_auto_4",
                "auto_clip": True,
                "auto_publish": True,
                "publish_destination_id": source_ch_id,
            })
            assert r4.status_code == 400
            assert "Invalid publish destination" in r4.json()["detail"]

            # Case 4b: auto_publish=True with destination lacking OAuth credentials
            with patch("backend.services.publisher.check_channel_authorization", return_value=False):
                r4b = await client.post("/api/channels/", json={
                    "channel_url": "https://www.youtube.com/@channel_test_auto_4b",
                    "auto_clip": True,
                    "auto_publish": True,
                    "publish_destination_id": active_dest_id,
                })
                assert r4b.status_code == 400
                assert "not authorized or OAuth credentials are invalid" in r4b.json()["detail"]

            # Case 5: auto_publish=True with valid active destination and verified credentials
            with patch("backend.services.publisher.check_channel_authorization", return_value=True):
                r5 = await client.post("/api/channels/", json={
                    "channel_url": "https://www.youtube.com/@channel_test_auto_5",
                    "auto_clip": True,
                    "auto_publish": True,
                    "publish_destination_id": active_dest_id,
                })
                assert r5.status_code == 200
                assert r5.json()["message"] == "Channel added"
                assert r5.json()["publish_destination_id"] == active_dest_id


@pytest.mark.asyncio
async def test_update_channel_auto_publish_requires_valid_destination():
    """
    PATCH /api/channels/{channel_id}
    - Rejects auto_publish=True if destination is missing (HTTP 422).
    - Rejects auto_publish=True if destination is inactive or not destination (HTTP 400).
    - Rejects auto_publish=True if destination lacks OAuth credentials (HTTP 400).
    - Enables auto_publish=True if destination is active and has valid credentials (HTTP 200).
    """
    src_id = f"test_p1_upd_src_{uuid.uuid4().hex[:6]}"
    active_dest_id = f"test_p1_upd_act_{uuid.uuid4().hex[:6]}"
    inactive_dest_id = f"test_p1_upd_inact_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        src = Channel(
            id=src_id,
            youtube_channel_id=f"UC_{src_id}",
            channel_name="Update Src Channel",
            channel_url="https://youtube.com/@updsrc",
            is_destination=False,
            is_active=True,
            auto_clip=True,
            auto_publish=False,
            publish_destination_id=None,
            is_test=False,
        )
        active_dest = Channel(
            id=active_dest_id,
            youtube_channel_id=f"UC_{active_dest_id}",
            channel_name="Update Dest Active",
            channel_url="https://youtube.com/@updact",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        inactive_dest = Channel(
            id=inactive_dest_id,
            youtube_channel_id=f"UC_{inactive_dest_id}",
            channel_name="Update Dest Inactive",
            channel_url="https://youtube.com/@updinact",
            is_destination=True,
            is_active=False,
            is_test=False,
        )
        session.add_all([src, active_dest, inactive_dest])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: auto_publish=True without destination
        r1 = await client.patch(f"/api/channels/{src_id}", json={
            "auto_publish": True,
        })
        assert r1.status_code == 422
        assert "Cannot enable auto-publish without a valid publish destination" in r1.json()["detail"]

        # Case 2: auto_publish=True with inactive destination
        r2 = await client.patch(f"/api/channels/{src_id}", json={
            "auto_publish": True,
            "publish_destination_id": inactive_dest_id,
        })
        assert r2.status_code == 400
        assert "Publish destination channel is not active" in r2.json()["detail"]

        # Case 3: auto_publish=True with destination lacking OAuth credentials
        with patch("backend.services.publisher.check_channel_authorization", return_value=False):
            r3 = await client.patch(f"/api/channels/{src_id}", json={
                "auto_publish": True,
                "publish_destination_id": active_dest_id,
            })
            assert r3.status_code == 400
            assert "not authorized or OAuth credentials are invalid" in r3.json()["detail"]

        # Case 4: auto_publish=True with destination having verified OAuth credentials
        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            r4 = await client.patch(f"/api/channels/{src_id}", json={
                "auto_publish": True,
                "publish_destination_id": active_dest_id,
            })
            assert r4.status_code == 200
            assert r4.json()["auto_publish"] is True


def test_upload_short_rejects_missing_channel_id(tmp_path):
    """
    upload_short:
    Enforces that publishing requires an explicit destination channel_id.
    Publishing without an explicit channel_id raises ValueError.
    """
    from backend.services.publisher import upload_short
    dummy_file = tmp_path / "dummy.mp4"
    dummy_file.write_bytes(b"dummy")

    with pytest.raises(ValueError) as exc_info:
        upload_short(
            video_path=dummy_file,
            title="No Channel ID Video",
            channel_id=None,
        )
    assert "Destination channel_id is required for publishing" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info2:
        upload_short(
            video_path=dummy_file,
            title="Empty Channel ID Video",
            channel_id="",
        )
    assert "Destination channel_id is required for publishing" in str(exc_info2.value)


def test_publish_clip_task_destination_validation(tmp_path):
    """
    publish_clip_task:
    Worker task validates destination before attempting upload or reconciliation:
    - Fails if destination is missing.
    - Fails if destination is inactive or not destination.
    - Fails if destination lacks OAuth credentials.
    """
    from backend.tasks.clip_tasks import publish_clip_task
    dummy_file = tmp_path / "task_clip.mp4"
    dummy_file.write_bytes(b"dummy")

    clip_id = f"test_p1_task_{uuid.uuid4().hex[:6]}"
    active_dest_id = f"test_p1_task_act_{uuid.uuid4().hex[:6]}"
    active_yt_id = f"UC_{active_dest_id}"

    with SyncSessionLocal() as session:
        dest = Channel(
            id=active_dest_id,
            youtube_channel_id=active_yt_id,
            channel_name="Task Dest Active",
            channel_url="https://youtube.com/@taskact",
            is_destination=True,
            is_active=True,
            is_test=False,
        )
        clip = Clip(
            id=clip_id,
            video_id="dummy_vid",
            title="Task Validation Clip",
            output_path=str(dummy_file),
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            publish_status="draft",
            publish_destination_id=None,
        )
        session.add_all([dest, clip])
        session.commit()

    # Case 1: No destination provided and none on clip
    res1 = publish_clip_task(clip_id=clip_id, channel_id=None)
    assert res1["status"] == "failed"
    assert "No destination channel specified" in res1["error"]

    # Case 2: Destination lacks OAuth credentials
    with patch("backend.services.publisher.check_channel_authorization", return_value=False):
        res2 = publish_clip_task(clip_id=clip_id, channel_id=active_dest_id)
        assert res2["status"] == "failed"
        assert "lacks valid OAuth credentials" in res2["error"]

    # Case 3: Inactive or non-destination channel ID
    res3 = publish_clip_task(clip_id=clip_id, channel_id="nonexistent_dest_id_xyz")
    assert res3["status"] == "failed"
    assert "not found, inactive, or not registered" in res3["error"]
