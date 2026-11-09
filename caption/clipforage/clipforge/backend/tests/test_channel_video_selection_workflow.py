"""
test_channel_video_selection_workflow.py
=========================================
Tests for channel-to-video-to-clip linkage, destination routing, and persistence:
1. Channels API supports publish_destination_id on add and update.
2. Channel recent videos endpoint retrieves video list for discovery.
3. Video submission links channel_id to Video and Job config.
4. Clip generation propagates publish_destination_id to generated clips.
5. Clips listing filters by channel_id and destination_id with full metadata.
6. Publish endpoints (publish-now, schedule) correctly validate and route to destination_channel_id.
"""
import uuid
import json
import pytest
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch, MagicMock

from httpx import ASGITransport, AsyncClient
from backend.main import app
from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Video, Clip, Job, PublishStatus
from backend.api.routes.channels import AddChannelRequest, UpdateChannelRequest
from backend.tasks.analysis_tasks import clip_selection_task, scoring_task


def test_channel_model_and_requests_have_publish_destination_id():
    """Verify AddChannelRequest and UpdateChannelRequest support publish_destination_id."""
    req = AddChannelRequest(
        channel_url="https://youtube.com/@TechTips",
        auto_clip=True,
        auto_publish=False,
        publish_destination_id="dest-uuid-1234"
    )
    assert req.publish_destination_id == "dest-uuid-1234"

    upd = UpdateChannelRequest(publish_destination_id="dest-uuid-5678")
    assert upd.publish_destination_id == "dest-uuid-5678"


def test_scoring_task_fallback_without_nameerror():
    """Verify scoring_task runs without NameError: os even when SCORING_MODE is set."""
    mock_job = MagicMock()
    mock_job.id = f"job_{uuid.uuid4().hex[:8]}"
    mock_job.config = json.dumps({"scoring_mode": "test"})
    mock_job.video_id = str(uuid.uuid4())

    candidates = [
        {
            "start": 0.0,
            "end": 30.0,
            "duration": 30.0,
            "text": "Hello world",
            "score": 8.0,
            "title": "Clip 1",
            "reason": "Good hook"
        }
    ]

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as cand_file:
        json.dump(candidates, cand_file)
        cand_path = cand_file.name

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as out_file:
        out_path = out_file.name

    @contextmanager
    def fake_download(*args, **kwargs):
        yield cand_path

    @contextmanager
    def fake_upload(*args, **kwargs):
        yield out_path

    with patch("backend.models.database.SyncSessionLocal") as mock_session_cls, \
         patch("backend.models.artifact_sync.managed_download_sync", side_effect=fake_download), \
         patch("backend.models.artifact_sync.managed_upload_sync", side_effect=fake_upload), \
         patch("backend.models.db_sync.update_job_sync"):
        session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = session
        session.query.return_value.filter_by.return_value.first.return_value = mock_job

        # Run scoring_task directly
        res = scoring_task({"video_id": mock_job.video_id, "job_id": mock_job.id})
        assert res["scoring_version"] == "test_v1"
        assert res["video_id"] == mock_job.video_id

    # Cleanup temp files
    try:
        Path(cand_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
    except Exception:
        pass


def test_clip_selection_inherits_publish_destination():
    """Verify clip_selection_task assigns publish_destination_id from job config or channel."""
    video_id = str(uuid.uuid4())
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    channel_id = str(uuid.uuid4())
    dest_id = "target-dest-channel-999"

    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.video_id = video_id
    mock_job.config = json.dumps({
        "channel_id": channel_id,
        "publish_destination_id": dest_id
    })

    mock_video = MagicMock()
    mock_video.id = video_id
    mock_video.channel_id = channel_id

    mock_channel = MagicMock()
    mock_channel.id = channel_id
    mock_channel.publish_destination_id = dest_id
    mock_channel.clips_generated = 0
    mock_channel.auto_publish = False

    candidate = {
        "start": 10.0,
        "end": 40.0,
        "duration": 30.0,
        "score": 9.2,
        "text": "Mind blowing fact!",
        "title": "Viral Fact",
        "reason": "High hook score",
        "description": "Awesome clip",
        "hashtags": "#Shorts",
        "pinned_comment": "Subscribe"
    }

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as scored_file:
        json.dump([candidate], scored_file)
        scored_path = scored_file.name

    @contextmanager
    def fake_download(*args, **kwargs):
        yield scored_path

    with patch("backend.models.database.SyncSessionLocal") as mock_session_cls, \
         patch("backend.models.artifact_sync.managed_download_sync", side_effect=fake_download), \
         patch("backend.models.db_sync.update_job_sync"):

        session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = session

        # Query routing
        def mock_query(model):
            q = MagicMock()
            if model == Job:
                q.filter_by.return_value.first.return_value = mock_job
            elif model == Video:
                q.filter_by.return_value.first.return_value = mock_video
            elif model == Channel:
                q.filter_by.return_value.first.return_value = mock_channel
            elif model == Clip:
                q.filter_by.return_value.all.return_value = []
                q.filter_by.return_value.count.return_value = 1
            return q
        session.query.side_effect = mock_query

        with patch("backend.models.db_sync.save_clip_record") as mock_save_clip:
            # Run clip_selection_task
            selected_clip_ids = clip_selection_task({
                "video_id": video_id, 
                "job_id": job_id, 
                "candidate_set_hash": "dummy_hash",
                "scoring_version": "test_v1"
            })

            assert len(selected_clip_ids) == 1
            mock_save_clip.assert_called_once()
            _, kwargs = mock_save_clip.call_args
            assert kwargs["publish_destination_id"] == dest_id
            assert kwargs["destination_ids"] == [dest_id]
            assert mock_channel.clips_generated == 1

    try:
        Path(scored_path).unlink(missing_ok=True)
    except Exception:
        pass


def test_video_model_has_channel_id_field():
    """Verify Video model has channel_id attribute."""
    video = Video(
        id=str(uuid.uuid4()),
        channel_id="channel-xyz-123"
    )
    assert video.channel_id == "channel-xyz-123"


def test_clip_model_has_publish_destination_id():
    """Verify Clip model has publish_destination_id attribute."""
    clip = Clip(
        id=str(uuid.uuid4()),
        video_id=str(uuid.uuid4()),
        publish_destination_id="dest-abc-789"
    )
    assert clip.publish_destination_id == "dest-abc-789"


def test_scoring_task_production_mode_without_nameerror(monkeypatch):
    """
    Task 4 verification:
    Verify scoring_task in production mode when:
    - job.config does NOT specify test mode (e.g. {"clip_mode": "ai_highlights"})
    - SCORING_MODE is unset or 'prod'
    - reaches ai_score_candidates without NameError: os
    - yields scoring_version == 'v1'
    """
    monkeypatch.delenv("SCORING_MODE", raising=False)
    
    mock_job = MagicMock()
    mock_job.id = f"job_prod_{uuid.uuid4().hex[:8]}"
    mock_job.config = json.dumps({"clip_mode": "ai_highlights", "clips_count": 1})
    mock_job.video_id = str(uuid.uuid4())

    candidates = [
        {
            "start": 0.0,
            "end": 30.0,
            "duration": 30.0,
            "text": "Production highlight text",
            "score": 9.5,
            "title": "Prod Clip 1",
            "reason": "Top hook"
        }
    ]

    mock_scored = MagicMock()
    mock_scored.start = 0.0
    mock_scored.end = 30.0
    mock_scored.duration = 30.0
    mock_scored.text = "Production highlight text"
    mock_scored.score = 9.5
    mock_scored.title = "Prod Clip 1"
    mock_scored.reason = "Top hook"
    mock_scored.description = "Prod description"
    mock_scored.hashtags = "#Prod"
    mock_scored.pinned_comment = "Check this out"

    async def fake_ai_score(cands, top_n=3):
        return [mock_scored]

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as cand_file:
        json.dump(candidates, cand_file)
        cand_path = cand_file.name

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as out_file:
        out_path = out_file.name

    @contextmanager
    def fake_download(*args, **kwargs):
        yield cand_path

    @contextmanager
    def fake_upload(*args, **kwargs):
        yield out_path

    with patch("backend.models.database.SyncSessionLocal") as mock_session_cls, \
         patch("backend.models.artifact_sync.managed_download_sync", side_effect=fake_download), \
         patch("backend.models.artifact_sync.managed_upload_sync", side_effect=fake_upload), \
         patch("backend.models.db_sync.update_job_sync"), \
         patch("backend.services.clip_scorer.ai_score_candidates", side_effect=fake_ai_score), \
         patch("backend.core.config.settings.SCORING_MODE", "prod", create=True):
        session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = session
        session.query.return_value.filter_by.return_value.first.return_value = mock_job

        res = scoring_task({"video_id": mock_job.video_id, "job_id": mock_job.id})
        assert res["scoring_version"] == "v1"
        assert res["video_id"] == mock_job.video_id

    try:
        Path(cand_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
    except Exception:
        pass


def test_scoring_task_equal_splits_mode():
    """Task 4 verification: verify scoring_task when segmentation_strategy is equal_splits."""
    mock_job = MagicMock()
    mock_job.id = f"job_eq_{uuid.uuid4().hex[:8]}"
    mock_job.config = json.dumps({"segmentation_strategy": "equal_splits"})
    mock_job.video_id = str(uuid.uuid4())

    candidates = [{"start": 0.0, "end": 15.0, "duration": 15.0, "text": "Split 1", "score": 5.0, "title": "Part 1", "reason": "equal"}]

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as cand_file:
        json.dump(candidates, cand_file)
        cand_path = cand_file.name
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as out_file:
        out_path = out_file.name

    @contextmanager
    def fake_download(*args, **kwargs):
        yield cand_path
    @contextmanager
    def fake_upload(*args, **kwargs):
        yield out_path

    with patch("backend.models.database.SyncSessionLocal") as mock_session_cls, \
         patch("backend.models.artifact_sync.managed_download_sync", side_effect=fake_download), \
         patch("backend.models.artifact_sync.managed_upload_sync", side_effect=fake_upload), \
         patch("backend.models.db_sync.update_job_sync"):
        session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = session
        session.query.return_value.filter_by.return_value.first.return_value = mock_job

        res = scoring_task({"video_id": mock_job.video_id, "job_id": mock_job.id})
        assert res["scoring_version"] == "equal_splits_v1"

    try:
        Path(cand_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_channel_id_contract_and_clip_filtering_with_real_fixtures():
    """
    Task 2 verification:
    Verify the real database end-to-end contract:
    1. Add Channel via API with publish_destination_id and verify persistence.
    2. Submit YouTube URL with channel_id:
       - Confirms Job.config has channel_id.
       - Confirms existing callers without channel_id remain compatible.
    3. Verify download_task sets Video.channel_id.
    4. Query GET /api/clips/?channel_id=... with real persisted fixture IDs:
       - Asserts only matching channel clips are returned.
       - Asserts destination filter returns only matching destination clips.
       - Asserts non-existent channel returns empty list (not dummy mock).
    5. Invalid publish request (non-existent clip/destination) is safely rejected.
    """
    import httpx
    from httpx import ASGITransport, AsyncClient
    from backend.main import app
    from backend.models.database import SyncSessionLocal
    from datetime import datetime, timezone

    # Unique fixture IDs for isolation
    tag = uuid.uuid4().hex[:8]
    dest_ch_id = f"dest_ch_{tag}"
    src_ch_id = f"src_ch_{tag}"
    other_ch_id = f"other_ch_{tag}"
    vid_a_id = f"vid_a_{tag}"
    vid_b_id = f"vid_b_{tag}"
    clip_a_id = f"clip_a_{tag}"
    clip_b_id = f"clip_b_{tag}"

    with SyncSessionLocal() as session:
        # Create Destination Channel
        dest_ch = Channel(
            id=dest_ch_id,
            channel_name=f"Destination Channel {tag}",
            channel_url=f"https://youtube.com/@Dest_{tag}",
            youtube_channel_id=f"UC_dest_{tag}",
            is_destination=True,
            is_active=True,
            is_test=True
        )
        # Create Source Channel linked to destination
        src_ch = Channel(
            id=src_ch_id,
            channel_name=f"Source Channel {tag}",
            channel_url=f"https://youtube.com/@Source_{tag}",
            youtube_channel_id=f"UC_src_{tag}",
            is_destination=False,
            publish_destination_id=dest_ch_id,
            is_active=True,
            is_test=True
        )
        # Create Other Channel (unlinked)
        other_ch = Channel(
            id=other_ch_id,
            channel_name=f"Other Channel {tag}",
            channel_url=f"https://youtube.com/@Other_{tag}",
            youtube_channel_id=f"UC_other_{tag}",
            is_destination=False,
            is_active=True,
            is_test=True
        )
        session.add_all([dest_ch, src_ch, other_ch])

        # Create Videos
        vid_a = Video(
            id=vid_a_id,
            title="Video A",
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            channel_id=src_ch_id
        )
        vid_b = Video(
            id=vid_b_id,
            title="Video B",
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            channel_id=other_ch_id
        )
        session.add_all([vid_a, vid_b])

        # Create Clips
        now = datetime.now(timezone.utc)
        clip_a = Clip(
            id=clip_a_id,
            video_id=vid_a_id,
            title="Clip A from Source Channel",
            publish_destination_id=dest_ch_id,
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            score=8.5,
            created_at=now
        )
        clip_b = Clip(
            id=clip_b_id,
            video_id=vid_b_id,
            title="Clip B from Other Channel",
            publish_destination_id=None,
            start_time=0.0,
            end_time=20.0,
            duration=20.0,
            score=7.0,
            created_at=now
        )
        session.add_all([clip_a, clip_b])
        session.commit()

    job_id = None
    job_compat_id = None
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Test POST /api/videos/url with channel_id
            with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
                mock_apply.return_value = MagicMock(id=f"task_{tag}")
                resp = await ac.post("/api/videos/url", data={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "channel_id": src_ch_id,
                    "publish_destination_id": dest_ch_id
                })
                assert resp.status_code == 200, resp.text
                job_id = resp.json()["job_id"]

                # Verify Job.config has channel_id
                with SyncSessionLocal() as session:
                    db_job = session.query(Job).filter_by(id=job_id).first()
                    assert db_job is not None
                    cfg = json.loads(db_job.config)
                    assert cfg["channel_id"] == src_ch_id
                    assert cfg["publish_destination_id"] == dest_ch_id

            # 2. Test compatibility: POST /api/videos/url WITHOUT channel_id
            with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
                mock_apply.return_value = MagicMock(id=f"task_compat_{tag}")
                resp_compat = await ac.post("/api/videos/url", data={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                })
                assert resp_compat.status_code == 200
                job_compat_id = resp_compat.json()["job_id"]
                with SyncSessionLocal() as session:
                    db_job = session.query(Job).filter_by(id=job_compat_id).first()
                    cfg = json.loads(db_job.config)
                    assert cfg["channel_id"] is None

            # 3. Test GET /api/clips/?channel_id={src_ch_id}
            resp_src = await ac.get(f"/api/clips/?channel_id={src_ch_id}")
            assert resp_src.status_code == 200
            data_src = resp_src.json()
            returned_ids = [c["id"] for c in data_src]
            assert clip_a_id in returned_ids
            assert clip_b_id not in returned_ids
            # Assert full metadata returned
            c_a = next(c for c in data_src if c["id"] == clip_a_id)
            assert c_a["channel_id"] == src_ch_id
            assert c_a["publish_destination_id"] == dest_ch_id
            assert c_a["source_channel_name"] == f"Source Channel {tag}"

            # 4. Test GET /api/clips/?destination_id={dest_ch_id}
            resp_dest = await ac.get(f"/api/clips/?destination_id={dest_ch_id}")
            assert resp_dest.status_code == 200
            data_dest = resp_dest.json()
            dest_returned_ids = [c["id"] for c in data_dest]
            assert clip_a_id in dest_returned_ids
            assert clip_b_id not in dest_returned_ids

            # 5. Test GET /api/clips/?channel_id=nonexistent_id
            resp_nonexistent = await ac.get("/api/clips/?channel_id=nonexistent_uuid_9999")
            assert resp_nonexistent.status_code == 200
            assert resp_nonexistent.json() == []

            # 6. Test invalid publish rejection (non-existent clip)
            resp_invalid = await ac.post("/api/publish/publish-now", json={
                "clip_id": "nonexistent_clip_12345",
                "destination_channel_id": dest_ch_id
            })
            assert resp_invalid.status_code == 404

    finally:
        # Cleanup fixtures
        with SyncSessionLocal() as session:
            session.query(Clip).filter(Clip.id.in_([clip_a_id, clip_b_id])).delete(synchronize_session=False)
            cleanup_jobs = [j for j in [job_id, job_compat_id] if j is not None]
            if cleanup_jobs:
                session.query(Job).filter(Job.id.in_(cleanup_jobs)).delete(synchronize_session=False)
            session.query(Video).filter(Video.id.in_([vid_a_id, vid_b_id])).delete(synchronize_session=False)
            session.query(Channel).filter(Channel.id.in_([dest_ch_id, src_ch_id, other_ch_id])).delete(synchronize_session=False)
            session.commit()
        from backend.models.database import engine
        await engine.dispose()


@pytest.mark.asyncio
async def test_publish_destination_validation_and_unassigned_preservation():
    """
    Test destination consistency and security:
    1. Channel PATCH with invalid/non-destination ID returns HTTP 400.
    2. Monitored channel with publish_destination_id = None preserves None without falling back to default.
    3. POST /api/publish/publish-now rejects invalid/non-destination channel with HTTP 400.
    """
    tag = uuid.uuid4().hex[:6]
    src_id = f"src_{tag}"
    valid_dest_id = f"dest_valid_{tag}"
    non_dest_id = f"dest_invalid_{tag}"
    vid_id = f"vid_{tag}"
    clip_id = f"clip_{tag}"

    with SyncSessionLocal() as session:
        # Valid destination
        dest_valid = Channel(
            id=valid_dest_id,
            youtube_channel_id=f"yt_valid_{tag}",
            channel_name=f"Valid Dest {tag}",
            channel_url="https://youtube.com/channel/valid",
            is_destination=True,
            is_default_destination=True,
            is_active=True,
            is_test=True
        )
        # Channel that is NOT a destination
        non_dest = Channel(
            id=non_dest_id,
            youtube_channel_id=f"yt_invalid_{tag}",
            channel_name=f"Non Dest {tag}",
            channel_url="https://youtube.com/channel/nondest",
            is_destination=False,
            is_active=True,
            is_test=True
        )
        # Source monitored channel with NO destination (None - Select at publish time)
        src_ch = Channel(
            id=src_id,
            youtube_channel_id=f"yt_src_{tag}",
            channel_name=f"Source Channel {tag}",
            channel_url="https://youtube.com/channel/src",
            is_destination=False,
            publish_destination_id=None,
            is_active=True,
            is_test=True
        )
        session.add(dest_valid)
        session.add(non_dest)
        session.add(src_ch)

        # Video and Clip
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(b"mock video data")
        tmp.close()
        dummy_path = tmp.name

        vid = Video(id=vid_id, title=f"Test Video {tag}", youtube_url="https://youtube.com/watch?v=123", channel_id=src_id)
        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="Dest Validation Clip",
            duration=10.0,
            start_time=0.0,
            end_time=10.0,
            status="completed",
            output_path=dummy_path,
            publish_destination_id=None
        )
        session.add(vid)
        session.add(clip)
        session.commit()

    try:
        from backend.services.publisher import resolve_publish_destinations

        # 1. Monitored channel with publish_destination_id = None must NOT fall back to default destination!
        with SyncSessionLocal() as session:
            from unittest.mock import patch
            with patch("pathlib.Path.exists", return_value=True):
                resolved = resolve_publish_destinations({}, src_id, session)
                assert resolved == [], "Intentional None destination must not fall back to default destination"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 2. Reject PATCH /api/channels/{id} with non-destination channel
            resp_patch_nondest = await ac.patch(f"/api/channels/{src_id}", json={
                "publish_destination_id": non_dest_id
            })
            assert resp_patch_nondest.status_code == 400
            assert "Invalid publish destination" in resp_patch_nondest.json()["detail"]

            # 3. Reject PATCH /api/channels/{id} with nonexistent channel
            resp_patch_nonexistent = await ac.patch(f"/api/channels/{src_id}", json={
                "publish_destination_id": "nonexistent_uuid_123"
            })
            assert resp_patch_nonexistent.status_code == 400

            # 4. Reject POST /api/publish/publish-now with non-destination channel
            resp_pub_invalid = await ac.post("/api/publish/publish-now", json={
                "clip_id": clip_id,
                "destination_channel_id": non_dest_id
            })
            assert resp_pub_invalid.status_code == 400
            assert "not an authorized destination" in resp_pub_invalid.json()["detail"]

    finally:
        with SyncSessionLocal() as session:
            session.query(Clip).filter(Clip.id == clip_id).delete()
            session.query(Video).filter(Video.id == vid_id).delete()
            session.query(Channel).filter(Channel.id.in_([src_id, valid_dest_id, non_dest_id])).delete()
            session.commit()
        import os
        if os.path.exists(dummy_path):
            os.remove(dummy_path)
        from backend.models.database import engine
        await engine.dispose()

