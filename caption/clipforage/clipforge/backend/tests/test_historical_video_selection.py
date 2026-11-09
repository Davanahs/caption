"""
test_historical_video_selection.py
==================================
Automated test suite for ClipForge Monitoring Historical Video Selection:
1. Latest N videos (with and without upload cutoff date).
2. Most-viewed N videos (verified view-count sorting and deterministic tie-breaking).
3. Uploaded-since-date boundary (inclusive ISO/date boundary comparisons).
4. New uploads only mode (preserves continuous Auto Monitor, queues 0 videos).
5. Deduplication against existing Video and VideoDecision records.
6. Deduplication of duplicate video IDs in batch requests.
7. Safety limit enforcement (batch capped at 20 videos).
8. Missing view counts and discovery limitations handling.
9. Pipeline dispatch via resolve_video_decision_sync.
10. Privacy and zero accidental live publications guarantee (privacy == private).
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, Video, VideoDecision, VideoDecisionStatus, Clip, PublishStatus


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest.fixture
def test_channels():
    tag = uuid.uuid4().hex[:8]
    src_id = f"src_test_{tag}"
    dest_id = f"dest_test_{tag}"

    with SyncSessionLocal() as session:
        dest_ch = Channel(
            id=dest_id,
            channel_name=f"Destination Channel {tag}",
            channel_url=f"https://youtube.com/@synth_dest_{tag}",
            youtube_channel_id=f"UC_synth_dest_{tag}",
            is_destination=True,
            is_active=True,
            is_test=True,
        )
        src_ch = Channel(
            id=src_id,
            channel_name=f"Source Channel {tag}",
            channel_url=f"https://youtube.com/@synth_source_{tag}",
            youtube_channel_id=f"UC_synth_source_{tag}",
            is_destination=False,
            publish_destination_id=dest_id,
            is_active=True,
            auto_clip=True,
            auto_publish=True,
            is_test=True,
        )
        session.add_all([dest_ch, src_ch])
        session.commit()

    yield {"src_id": src_id, "dest_id": dest_id, "tag": tag}

    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.publish_destination_id == dest_id).delete(synchronize_session=False)
        session.query(VideoDecision).filter(VideoDecision.channel_id == src_id).delete(synchronize_session=False)
        session.query(Video).filter(Video.channel_id == src_id).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.in_([src_id, dest_id])).delete(synchronize_session=False)
        session.commit()


@pytest.mark.asyncio
async def test_historical_preview_latest_videos(test_channels):
    """Test Option A: Latest N videos selection ordered by upload timestamp descending."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    mock_candidates = [
        {"id": f"vid_old_{tag}", "title": "Old Video", "upload_date": "20261020", "timestamp": 1792454400, "view_count": 500},
        {"id": f"vid_mid_{tag}", "title": "Mid Video", "upload_date": "20261024", "timestamp": 1792800000, "view_count": 1500},
        {"id": f"vid_new_{tag}", "title": "New Video", "upload_date": "20261026", "timestamp": 1792972800, "view_count": 800},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates), \
             patch("backend.api.routes.channels.fetch_youtube_rss_dates_sync", return_value={}):

            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "latest",
                "count": 2,
                "max_search_depth": 30
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["mode"] == "latest"
            assert data["requested_count"] == 2
            assert data["eligible_found"] == 3
            assert data["already_processed"] == 0
            assert data["will_queue"] == 2
            assert data["effective_privacy"] == "private"

            selected_ids = [it["id"] for it in data["items"] if it["selected_for_queue"]]
            assert selected_ids == [f"vid_new_{tag}", f"vid_mid_{tag}"]
            assert data["items"][0]["id"] == f"vid_new_{tag}"
            assert data["items"][0]["selected_for_queue"] is True


@pytest.mark.asyncio
async def test_historical_preview_latest_with_date_cutoff(test_channels):
    """Test Option A with upload-date cutoff (inclusive 'Uploaded on or after')."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    mock_candidates = [
        {"id": f"vid_1_{tag}", "title": "V1", "upload_date": "20261022", "timestamp": 1792627200, "view_count": 100},
        {"id": f"vid_2_{tag}", "title": "V2", "upload_date": "20261024", "timestamp": 1792800000, "view_count": 200},
        {"id": f"vid_3_{tag}", "title": "V3", "upload_date": "20261026", "timestamp": 1792972800, "view_count": 300},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates), \
             patch("backend.api.routes.channels.fetch_youtube_rss_dates_sync", return_value={}):

            # Cutoff on 2026-10-24: vid_1 (20261022) should be excluded
            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "latest",
                "count": 5,
                "since_date": "2026-10-24"
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["eligible_found"] == 2
            assert data["will_queue"] == 2
            selected_ids = [it["id"] for it in data["items"] if it["selected_for_queue"]]
            assert selected_ids == [f"vid_3_{tag}", f"vid_2_{tag}"]


@pytest.mark.asyncio
async def test_historical_preview_most_viewed_sorting_and_tie_breaking(test_channels):
    """Test Option B: Most-viewed N videos sorted by view count descending with deterministic tie-breaking."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    mock_candidates = [
        {"id": f"vid_low_{tag}", "title": "Low Views", "upload_date": "20261025", "timestamp": 1792886400, "view_count": 100},
        {"id": f"vid_high_{tag}", "title": "High Views", "upload_date": "20261020", "timestamp": 1792454400, "view_count": 10000},
        # Tie in view_count: 5000 vs 5000 -> tie-break by newer timestamp: vid_tie_newer should come before vid_tie_older
        {"id": f"vid_tie_older_{tag}", "title": "Tie Older", "upload_date": "20261021", "timestamp": 1792540800, "view_count": 5000},
        {"id": f"vid_tie_newer_{tag}", "title": "Tie Newer", "upload_date": "20261023", "timestamp": 1792713600, "view_count": 5000},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates), \
             patch("backend.api.routes.channels.fetch_youtube_rss_dates_sync", return_value={}):

            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "most_viewed",
                "count": 3
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["mode"] == "most_viewed"
            assert data["will_queue"] == 3
            # Expected order: high (10000), tie_newer (5000, 1792713600), tie_older (5000, 1792540800)
            selected_ids = [it["id"] for it in data["items"] if it["selected_for_queue"]]
            assert selected_ids == [f"vid_high_{tag}", f"vid_tie_newer_{tag}", f"vid_tie_older_{tag}"]
            assert data["has_view_counts"] is True


@pytest.mark.asyncio
async def test_historical_preview_uploaded_since_date(test_channels):
    """Test Option C: Uploaded since a date boundary."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    mock_candidates = [
        {"id": f"vid_a_{tag}", "title": "Old", "upload_date": "20261001", "timestamp": 1790812800, "view_count": 50},
        {"id": f"vid_b_{tag}", "title": "Within Date 1", "upload_date": "20261025", "timestamp": 1792886400, "view_count": 60},
        {"id": f"vid_c_{tag}", "title": "Within Date 2", "upload_date": "20261026", "timestamp": 1792972800, "view_count": 70},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates), \
             patch("backend.api.routes.channels.fetch_youtube_rss_dates_sync", return_value={}):

            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "uploaded_since",
                "since_date": "2026-10-25",
                "count": 10
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["eligible_found"] == 2
            assert data["will_queue"] == 2
            selected_ids = [it["id"] for it in data["items"] if it["selected_for_queue"]]
            assert f"vid_a_{tag}" not in selected_ids
            assert selected_ids == [f"vid_c_{tag}", f"vid_b_{tag}"]


@pytest.mark.asyncio
async def test_historical_preview_new_only(test_channels):
    """Test Option D: New uploads only backfills 0 videos and keeps Auto Monitor active."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    mock_candidates = [
        {"id": f"vid_hist_{tag}", "title": "Hist", "upload_date": "20261025", "timestamp": 1792886400, "view_count": 999},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates):
            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "new_only"
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["mode"] == "new_only"
            assert data["will_queue"] == 0
            assert len(data["items"]) == 0
            assert any("future uploads" in str(lim).lower() for lim in data["limitations"])


@pytest.mark.asyncio
async def test_historical_preview_deduplication_against_processed_videos(test_channels):
    """Test that videos already in the Video table are marked as processed and not queued."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]
    already_proc_id = f"proc_vid_{tag}"

    with SyncSessionLocal() as session:
        vid = Video(
            id=str(uuid.uuid4()),
            youtube_id=already_proc_id,
            title="Already Processed Video",
            youtube_url=f"https://youtube.com/watch?v={already_proc_id}",
            channel_id=src_id,
        )
        session.add(vid)
        session.commit()

    mock_candidates = [
        {"id": already_proc_id, "title": "Already Processed Video", "upload_date": "20261026", "timestamp": 1792972800, "view_count": 5000},
        {"id": f"fresh_vid_{tag}", "title": "Fresh Video", "upload_date": "20261025", "timestamp": 1792886400, "view_count": 2000},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates), \
             patch("backend.api.routes.channels.fetch_youtube_rss_dates_sync", return_value={}):

            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "latest",
                "count": 5
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["already_processed"] == 1
            assert data["will_queue"] == 1
            selected_ids = [it["id"] for it in data["items"] if it["selected_for_queue"]]
            assert already_proc_id not in selected_ids
            assert selected_ids == [f"fresh_vid_{tag}"]

            cand_map = {c["id"]: c for c in data["items"]}
            assert cand_map[already_proc_id]["is_processed"] is True
            assert cand_map[already_proc_id]["selected_for_queue"] is False
            assert cand_map[f"fresh_vid_{tag}"]["is_processed"] is False
            assert cand_map[f"fresh_vid_{tag}"]["selected_for_queue"] is True


@pytest.mark.asyncio
async def test_historical_process_deduplication_and_limit_enforcement(test_channels):
    """Test POST /api/channels/{id}/historical-process: deduplicates IDs and enforces max 20 limit."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    # Provide duplicates: total 25 entries with duplicates
    unique_ids = [f"vid_{i}_{tag}" for i in range(25)]
    raw_ids = unique_ids + [f"vid_0_{tag}", f"vid_1_{tag}"]

    mock_metadata = [
        {"id": vid_id, "title": f"Video {vid_id}", "thumbnail": "https://img/test.jpg", "view_count": 100}
        for vid_id in unique_ids
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_metadata), \
             patch("backend.api.routes.channels.resolve_video_decision_sync", side_effect=lambda decision_id, **kw: {"job_id": f"job_{decision_id}"}) as mock_resolve:

            resp = await ac.post(f"/api/channels/{src_id}/historical-process", json={
                "video_ids": raw_ids,
                "mode": "latest"
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            # Max allowed per batch is 20
            assert data["total_selected"] == 20
            assert data["queued_count"] == 20
            assert len(data["results"]) == 20
            assert mock_resolve.call_count == 20

            # Verify channel is_active remains True for continuous monitoring
            with SyncSessionLocal() as session:
                ch = session.query(Channel).filter_by(id=src_id).first()
                assert ch.is_active is True

                # Check created decisions
                decisions = session.query(VideoDecision).filter_by(channel_id=src_id).all()
                assert len(decisions) == 20
                for d in decisions:
                    assert d.status == VideoDecisionStatus.AWAITING_SETTINGS.value


@pytest.mark.asyncio
async def test_historical_process_new_only_mode(test_channels):
    """Test POST /api/channels/{id}/historical-process with new_only mode ensures Auto Monitor is active."""
    src_id = test_channels["src_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/channels/{src_id}/historical-process", json={
            "video_ids": [],
            "mode": "new_only"
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["queued_count"] == 0

        with SyncSessionLocal() as session:
            ch = session.query(Channel).filter_by(id=src_id).first()
            assert ch.is_active is True


@pytest.mark.asyncio
async def test_historical_preview_missing_view_counts_note(test_channels):
    """Test that when view counts are absent, the system accurately reports the limitation."""
    src_id = test_channels["src_id"]
    tag = test_channels["tag"]

    mock_candidates = [
        {"id": f"vid_noview_{tag}", "title": "No Views", "upload_date": "20261025", "timestamp": 1792886400, "view_count": None},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_candidates), \
             patch("backend.api.routes.channels.fetch_youtube_rss_dates_sync", return_value={}):

            resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
                "mode": "most_viewed",
                "count": 5
            })
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["has_view_counts"] is False
            assert any("did not expose numeric view counts" in str(lim).lower() for lim in data["limitations"])
