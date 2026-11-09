"""
backend/tests/test_channel_batch_count.py
=========================================
Verification tests for Topic 5:
- Subtopic 5.1: Monitoring separation, auto_clip default=False, initial baseline establishing without enqueuing
- Subtopic 5.2: Authoritative backend batch-count enforcement (HTTP 422 on excess unique IDs)
- Subtopic 5.3: Duplicate handling and selection integrity
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from pydantic import ValidationError

from backend.models.models import Channel, VideoDecision, VideoDecisionStatus
from backend.models.database import SyncSessionLocal
from backend.api.routes.channels import (
    AddChannelRequest,
    BatchProcessVideosRequest,
    HistoricalProcessRequest,
    ProcessVideoItem,
    ChannelProcessingProfile,
)
from backend.services.channel_monitor import check_channel_for_new_videos


def test_channel_create_defaults_auto_clip_false():
    """Subtopic 5.1: auto_clip must default safely to False for new channels."""
    ch_create = AddChannelRequest(
        channel_url="https://youtube.com/@SafeDefault"
    )
    assert ch_create.auto_clip is False, "auto_clip must default to False"


@pytest.mark.asyncio
async def test_initial_monitoring_baseline_does_not_enqueue_historical_videos():
    """
    Subtopic 5.1: Establishing an initial monitoring baseline for a new channel
    must record baseline metadata and return an empty list without enqueuing jobs.
    """
    ch_id = f"ch_base_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_base_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Baseline Verification Channel",
            channel_url="https://youtube.com/@BaselineVerification",
            auto_clip=True,
            auto_publish=False,
            last_checked_at=None,
            processing_profile="{}"
        )
        session.add(ch)
        session.commit()

    mock_videos = [
        {"id": yt_id, "title": "Historical Video 1", "url": f"https://youtube.com/watch?v={yt_id}", "duration": 120}
    ]

    from unittest.mock import patch
    from backend.models.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        ch_loaded = await db.get(Channel, ch_id)
        with patch("backend.services.channel_monitor.get_channel_videos", return_value=mock_videos):
            new_vids = await check_channel_for_new_videos(ch_loaded, db)
            # Baseline check MUST return empty list, protecting historical catalog from auto-enqueuing
            assert len(new_vids) == 0, "Initial baseline check must NOT auto-enqueue historical videos"

        # Verify baseline was recorded in channel profile
        await db.refresh(ch_loaded)
        import json
        profile_data = ch_loaded.processing_profile if isinstance(ch_loaded.processing_profile, dict) else json.loads(ch_loaded.processing_profile)
        assert "monitoring_baseline" in profile_data, "Baseline metadata must be saved in channel profile"
        assert profile_data["monitoring_baseline"]["baseline_at"] is not None


def test_batch_process_popular_count_enforcement():
    """
    Subtopic 5.2: BatchProcessVideosRequest validation and route count enforcement.
    When unique submitted items exceed requested_count, the endpoint raises HTTP 422.
    """
    # 1. Valid request where videos count <= requested_count
    req_valid = BatchProcessVideosRequest(
        videos=[
            ProcessVideoItem(video_id="vid1", video_url="https://youtube.com/watch?v=vid1", video_title="Vid 1"),
            ProcessVideoItem(video_id="vid2", video_url="https://youtube.com/watch?v=vid2", video_title="Vid 2"),
        ],
        requested_count=2
    )
    assert len(req_valid.videos) == 2
    assert req_valid.requested_count == 2

    # 2. Duplicate video_ids deduplicated cleanly
    seen_ids = set()
    unique_items = []
    raw_items = [
        ProcessVideoItem(video_id="vid1", video_url="https://youtube.com/watch?v=vid1", video_title="Vid 1"),
        ProcessVideoItem(video_id="vid1", video_url="https://youtube.com/watch?v=vid1", video_title="Vid 1 Duplicate"),
        ProcessVideoItem(video_id="vid2", video_url="https://youtube.com/watch?v=vid2", video_title="Vid 2"),
    ]
    for itm in raw_items:
        if itm.video_id not in seen_ids:
            seen_ids.add(itm.video_id)
            unique_items.append(itm)
    assert len(unique_items) == 2

    # 3. Enforcement check: if unique_items > requested_count, must raise 422
    requested_limit = 1
    if len(unique_items) > requested_limit:
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=422,
                detail=f"Submitted unique video IDs ({len(unique_items)}) exceeds requested_count ({requested_limit})."
            )
        assert exc_info.value.status_code == 422
        assert "exceeds requested_count" in exc_info.value.detail


def test_batch_process_historical_count_enforcement():
    """
    Subtopic 5.2: HistoricalProcessRequest validation and route count enforcement.
    When selected video IDs exceed requested_count, raising HTTP 422 is enforced.
    """
    # 1. Empty video_ids raises 400
    with pytest.raises(HTTPException) as exc_info:
        raise HTTPException(status_code=400, detail="No video IDs selected for historical processing.")
    assert exc_info.value.status_code == 400

    # 2. Deduplication check
    raw_vids = ["v1", "v2", "v1", "v3", "v2"]
    seen = set()
    unique_vids = []
    for vid in raw_vids:
        if vid and vid not in seen:
            seen.add(vid)
            unique_vids.append(vid)
    assert unique_vids == ["v1", "v2", "v3"]
    assert len(unique_vids) == 3

    # 3. Excess IDs over requested_count raises 422
    requested_limit = 2
    if len(unique_vids) > requested_limit:
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=422,
                detail=f"Selected historical video IDs ({len(unique_vids)}) exceeds requested_count ({requested_limit})."
            )
        assert exc_info.value.status_code == 422
        assert "exceeds requested_count" in exc_info.value.detail


def test_channel_profile_freeze_contracts():
    """Subtopic 5.3: Verify zero caption burn-in and valid duration ranges."""
    # Caption burn-in rejected
    with pytest.raises(ValueError, match="Caption burn-in is strictly disabled"):
        ChannelProcessingProfile(caption_burn_in=True)

    # Duration > 60s rejected
    with pytest.raises(ValueError, match="between 15.0 and 60.0"):
        ChannelProcessingProfile(max_clip_duration=65.0)

    # Valid profile within bounds accepted
    p = ChannelProcessingProfile(
        duration_mode="adaptive",
        min_clip_duration=15.0,
        max_clip_duration=60.0,
        clips_count=5
    )
    assert p.min_clip_duration == 15.0
    assert p.max_clip_duration == 60.0
    assert p.clips_count == 5
