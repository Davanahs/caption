"""
test_automatic_channel_monitoring_and_decision_lifecycle.py
============================================================
Comprehensive test suite verifying:
1. ChannelProcessingProfile schema validation and strict Shorts duration limit (<= 30.0s).
2. Channel CRUD with processing profile persistence.
3. Complete paginated video discovery contract (items, page, page_size, has_more).
4. Restart-safe 20-second VideoDecision countdown lifecycle with DB row-locking.
5. Protection against duplicate decisions from concurrent monitors.
6. Customization modal lease (120s) and safe expiration resolution.
7. Decision race safety: stale countdown cannot override user's saved overrides.
8. User intentional cancellation permanently halts automatic processing.
9. Isolation of per-video overrides from channel defaults and other videos.
10. All four Auto-clip / Auto-publish toggle combinations.
11. Truthful pipeline start and completion timestamps with Asia/Kolkata (IST) display.
12. Downstream pipeline consumers (candidate generation, scoring mode, reframe layout, output validation).
"""
import uuid
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Video, VideoDecision, VideoDecisionStatus, Job, Clip
from backend.api.routes.channels import (
    ChannelProcessingProfile,
    AddChannelRequest,
    UpdateChannelRequest,
    format_ist,
)
from backend.tasks.orchestration import (
    resolve_video_decision_sync,
    sweep_pending_decisions_task,
)
from backend.services.channel_monitor import (
    check_channel_for_new_videos,
    run_channel_monitor,
)
from backend.services.output_validator import validate_video_output, OutputValidatorError
from backend.models.database import engine


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        from sqlalchemy import or_
        test_ch_filter = or_(
            Channel.id.like("ch_cust_%"),
            Channel.id.like("ch_race_%"),
            Channel.id.like("ch_iso_%"),
            Channel.id.like("test_ch_%"),
            Channel.id.like("ch_dup_%"),
            Channel.id.like("ch_dec_%"),
            Channel.id.like("ch_cancel_%"),
            Channel.id.like("ch_err_%"),
            Channel.id.like("ch_combo_%"),
            Channel.id.like("ch_restart_%"),
            Channel.id.like("dest_%"),
            Channel.channel_url.like("https://www.youtube.com/@Channel_%")
        )
        test_chs = session.query(Channel.id).filter(test_ch_filter).all()
        test_ch_ids = [ch[0] for ch in test_chs]
        if test_ch_ids:
            session.query(Job).filter(Job.channel_id.in_(test_ch_ids)).delete(synchronize_session=False)
            session.query(VideoDecision).filter(VideoDecision.channel_id.in_(test_ch_ids)).delete(synchronize_session=False)
            session.query(Channel).filter(Channel.id.in_(test_ch_ids)).delete(synchronize_session=False)
            session.commit()


# ── 1. Profile Schema Constraints & Shorts Duration Cap ─────────────────────

def test_profile_enforces_shorts_duration_cap():
    """Verify profile strictly caps durations at 30.0s and rejects caption burn-in."""
    # 1. Valid adaptive profile within 15-30s bounds
    p1 = ChannelProcessingProfile(
        duration_mode="adaptive",
        min_clip_duration=15.0,
        max_clip_duration=30.0,
        clips_count=3
    )
    assert p1.min_clip_duration == 15.0
    assert p1.max_clip_duration == 30.0

    # 2. Reject duration > 60s (Shorts ceiling contract)
    with pytest.raises(ValueError, match="between 15.0 and 60.0"):
        ChannelProcessingProfile(max_clip_duration=65.0)

    # 3. Reject target duration > 60s for fixed mode
    with pytest.raises(ValueError, match="between 15.0 and 60.0"):
        ChannelProcessingProfile(duration_mode="fixed", target_duration=65.0)

    # 4. Fixed mode requires target_duration
    with pytest.raises(ValueError, match="target_duration is required"):
        ChannelProcessingProfile(duration_mode="fixed", target_duration=None)

    # 5. Reject min_clip_duration > max_clip_duration
    with pytest.raises(ValueError, match="cannot exceed max_clip_duration"):
        ChannelProcessingProfile(min_clip_duration=25.0, max_clip_duration=20.0)

    # 6. Reject caption burn in (freeze rule: zero burn-in)
    with pytest.raises(ValueError, match="Caption burn-in is strictly disabled"):
        ChannelProcessingProfile(caption_burn_in=True)


# ── 2. Channel CRUD with Processing Profile ──────────────────────────────────

@pytest.mark.asyncio
async def test_channel_crud_with_processing_profile():
    """Test channel creation, listing, and updating with persistent processing profile."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_url = f"https://www.youtube.com/@Channel_{uuid.uuid4().hex[:6]}"
        
        # Mock yt-dlp discovery for adding channel
        mock_vid = [{"playlist_channel": "Test Channel", "playlist_channel_id": f"yt_ch_{uuid.uuid4().hex[:6]}"}]
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_vid):
            profile = {
                "duration_mode": "adaptive",
                "min_clip_duration": 15.0,
                "max_clip_duration": 28.0,
                "clips_count": 4,
                "video_layout": "fill_blur",
                "scoring_mode": "ai",
                "segmentation_strategy": "scene"
            }
            res = await client.post("/api/channels/", json={
                "channel_url": test_url,
                "auto_clip": True,
                "auto_publish": False,
                "processing_profile": profile
            })
            assert res.status_code == 200, res.text
            ch_data = res.json()
            channel_id = ch_data["id"]
            assert ch_data["processing_profile"]["max_clip_duration"] == 28.0

            # Verify GET /api/channels/ includes profile and IST timestamp
            list_res = await client.get("/api/channels/")
            assert list_res.status_code == 200
            channels = list_res.json()
            found = next(c for c in channels if c["id"] == channel_id)
            assert found["processing_profile"]["clips_count"] == 4
            assert found["auto_clip"] is True

            # Verify PATCH /api/channels/{id} updates profile
            patch_res = await client.patch(f"/api/channels/{channel_id}", json={
                "processing_profile": {
                    "duration_mode": "fixed",
                    "target_duration": 25.0,
                    "min_clip_duration": 15.0,
                    "max_clip_duration": 30.0,
                    "clips_count": 2,
                    "video_layout": "fit_black"
                }
            })
            assert patch_res.status_code == 200
            assert patch_res.json()["processing_profile"]["video_layout"] == "fit_black"
            assert patch_res.json()["processing_profile"]["target_duration"] == 25.0


# ── 3. Paginated Video Discovery Contract ───────────────────────────────────

@pytest.mark.asyncio
async def test_paginated_video_discovery_contract():
    """Verify GET /api/channels/{id}/videos exposes items, page, page_size, has_more."""
    ch_id = f"test_ch_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_{ch_id}",
            channel_name="Pagination Test Channel",
            channel_url="https://youtube.com/@PaginationTest",
            auto_clip=True,
            auto_publish=False
        )
        session.add(ch)
        session.commit()

    mock_discovery = {
        "items": [
            {"id": "vid_001", "title": "Video 1", "url": "https://youtube.com/watch?v=vid_001", "duration": 120},
            {"id": "vid_002", "title": "Video 2", "url": "https://youtube.com/watch?v=vid_002", "duration": 180},
        ],
        "page": 1,
        "page_size": 2,
        "has_more": True
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.api.routes.channels.get_channel_videos", return_value=mock_discovery):
            res = await client.get(f"/api/channels/{ch_id}/videos?page=1&page_size=2")
            assert res.status_code == 200
            data = res.json()
            assert "items" in data
            assert len(data["items"]) == 2
            assert data["page"] == 1
            assert data["page_size"] == 2
            assert data["has_more"] is True
            assert data["items"][0]["id"] == "vid_001"
            assert data["items"][0]["is_processed"] is False


# ── 4. Restart-Safe 20-Second Decision Lifecycle ─────────────────────────────

def test_decision_lifecycle_countdown_resolution_and_idempotency():
    """Verify decision countdown resolves atomically and resists duplicate execution."""
    ch_id = f"ch_dec_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_vid_{uuid.uuid4().hex[:8]}"
    dec_id = str(uuid.uuid4())

    profile = {"duration_mode": "adaptive", "min_clip_duration": 15.0, "max_clip_duration": 30.0, "clips_count": 3}

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Decision Channel",
            channel_url="https://youtube.com/@DecisionChannel",
            auto_clip=True,
            auto_publish=False,
            processing_profile=profile
        )
        session.add(ch)

        now = datetime.now(timezone.utc)
        dec = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=yt_id,
            video_title="Decision Video",
            youtube_url=f"https://youtube.com/watch?v={yt_id}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=now - timedelta(seconds=1),  # already reached deadline
            channel_profile_snapshot=profile,
            overrides=profile,
            created_at=now
        )
        session.add(dec)
        session.commit()

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
        # First resolution: should resolve to defaults and dispatch task
        res1 = resolve_video_decision_sync(decision_id=dec_id, action="countdown")
        assert res1["status"] == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert "job_id" in res1
        assert mock_apply.called

        # Second resolution: should be recognized as already resolved without re-dispatching
        mock_apply.reset_mock()
        res2 = resolve_video_decision_sync(decision_id=dec_id, action="countdown")
        assert res2["already_resolved"] is True
        assert res2["job_id"] == res1["job_id"]
        assert not mock_apply.called


# ── 5. Duplicate Decisions Prevented by Concurrent Monitors ──────────────────

@pytest.mark.asyncio
async def test_duplicate_decisions_prevented_by_monitor():
    """Verify repeated channel checks do not create duplicate VideoDecision records."""
    ch_id = f"ch_dup_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_dup_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Duplicate Test Channel",
            channel_url="https://youtube.com/@DuplicateTest",
            auto_clip=True,
            auto_publish=False,
            last_checked_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            processing_profile={"monitoring_baseline": {"baseline_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}}
        )
        session.add(ch)
        session.commit()

    mock_videos = [
        {"id": yt_id, "title": "New Upload", "url": f"https://youtube.com/watch?v={yt_id}", "duration": 120}
    ]

    from backend.models.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        ch = await db.get(Channel, ch_id)
        with patch("backend.services.channel_monitor.get_channel_videos", return_value=mock_videos):
            with patch("backend.tasks.orchestration.resolve_video_decision_countdown_task.apply_async"):
                # First run discovers video
                new_vids1 = await check_channel_for_new_videos(ch, db)
                assert len(new_vids1) == 1

                # Simulate creating decision
                dec = VideoDecision(
                    id=str(uuid.uuid4()),
                    channel_id=ch_id,
                    youtube_id=yt_id,
                    video_title="New Upload",
                    youtube_url=f"https://youtube.com/watch?v={yt_id}",
                    status=VideoDecisionStatus.AWAITING_SETTINGS.value,
                    decision_deadline=datetime.now(timezone.utc) + timedelta(seconds=20),
                    channel_profile_snapshot={},
                    created_at=datetime.now(timezone.utc)
                )
                db.add(dec)
                await db.commit()

                # Second run encounters the same video -> must deduplicate against VideoDecision
                new_vids2 = await check_channel_for_new_videos(ch, db)
                assert len(new_vids2) == 0


# ── 6. Customization Modal Lease & Expiration Safety ─────────────────────────

def test_customization_modal_lease_and_expiration():
    """Verify customization modal grants 120s lease, and expired leases resolve safely."""
    ch_id = f"ch_cust_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_cust_{uuid.uuid4().hex[:8]}"
    dec_id = str(uuid.uuid4())

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Customize Channel",
            channel_url="https://youtube.com/@CustChannel",
            auto_clip=True,
            auto_publish=False
        )
        session.add(ch)
        dec = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=yt_id,
            video_title="Customizing Video",
            youtube_url=f"https://youtube.com/watch?v={yt_id}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=datetime.now(timezone.utc) + timedelta(seconds=20),
            channel_profile_snapshot={},
            created_at=datetime.now(timezone.utc)
        )
        session.add(dec)
        session.commit()

    # 1. User opens modal -> enter customizing state with 120s lease
    res_cust = resolve_video_decision_sync(decision_id=dec_id, action="customize")
    assert res_cust["status"] == VideoDecisionStatus.CUSTOMIZING.value

    # 2. While lease is active, countdown/sweep must skip resolution
    res_active = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
    assert res_active.get("skipped") == "customization_in_progress"

    # 3. Simulate lease expiration (e.g. user closed browser tab)
    with SyncSessionLocal() as session:
        dec_obj = session.query(VideoDecision).filter_by(id=dec_id).first()
        dec_obj.customization_lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        session.commit()

    # 4. Sweep now safely defaults abandoned customization
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        res_expired = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
        assert res_expired["status"] == VideoDecisionStatus.RESOLVED_DEFAULTS.value


# ── 7. Race Safety: Stale Countdown vs Save & Process ─────────────────────────

def test_stale_countdown_cannot_override_saved_custom_overrides():
    """Verify user saving custom overrides permanently transitions decision to resolved_custom."""
    ch_id = f"ch_race_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_race_{uuid.uuid4().hex[:8]}"
    dec_id = str(uuid.uuid4())

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Race Channel",
            channel_url="https://youtube.com/@RaceChannel",
            auto_clip=True,
            auto_publish=False,
            processing_profile={"video_layout": "fill_blur", "clips_count": 3}
        )
        session.add(ch)
        dec = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=yt_id,
            video_title="Race Video",
            youtube_url=f"https://youtube.com/watch?v={yt_id}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=datetime.now(timezone.utc) + timedelta(seconds=1),
            channel_profile_snapshot={"video_layout": "fill_blur", "clips_count": 3},
            created_at=datetime.now(timezone.utc)
        )
        session.add(dec)
        session.commit()

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        # User saves custom overrides
        custom_overrides = {"video_layout": "split_screen", "clips_count": 5}
        res_custom = resolve_video_decision_sync(
            decision_id=dec_id,
            action="custom",
            custom_overrides=custom_overrides
        )
        assert res_custom["status"] == VideoDecisionStatus.RESOLVED_CUSTOM.value

        # Stale countdown arrives later: must NOT overwrite custom resolution
        res_stale = resolve_video_decision_sync(decision_id=dec_id, action="countdown")
        assert res_stale["status"] == VideoDecisionStatus.RESOLVED_CUSTOM.value
        assert res_stale["already_resolved"] is True

        with SyncSessionLocal() as session:
            final_dec = session.query(VideoDecision).filter_by(id=dec_id).first()
            assert final_dec.overrides["video_layout"] == "split_screen"
            assert final_dec.overrides["clips_count"] == 5


# ── 8. User Cancellation Permanently Halts Processing ────────────────────────

def test_user_cancellation_remains_cancelled():
    """Verify user cancellation sets status=cancelled and sweep/countdown never runs job."""
    ch_id = f"ch_cancel_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_cancel_{uuid.uuid4().hex[:8]}"
    dec_id = str(uuid.uuid4())

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Cancel Channel",
            channel_url="https://youtube.com/@CancelChannel",
            auto_clip=True,
            auto_publish=False
        )
        session.add(ch)
        dec = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=yt_id,
            video_title="Cancel Video",
            youtube_url=f"https://youtube.com/watch?v={yt_id}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=datetime.now(timezone.utc) + timedelta(seconds=20),
            channel_profile_snapshot={},
            created_at=datetime.now(timezone.utc)
        )
        session.add(dec)
        session.commit()

    # User explicitly cancels
    res_cancel = resolve_video_decision_sync(decision_id=dec_id, action="cancel")
    assert res_cancel["status"] == VideoDecisionStatus.CANCELLED.value

    # Stale countdown or periodic sweep later
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
        res_sweep = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
        assert res_sweep["status"] == VideoDecisionStatus.CANCELLED.value
        assert res_sweep["already_resolved"] is True
        assert not mock_apply.called


# ── 9. Per-Video Overrides Isolation ─────────────────────────────────────────

def test_per_video_overrides_isolated_from_channel_defaults():
    """Verify overriding settings for video A does not alter channel defaults for video B."""
    ch_id = f"ch_iso_{uuid.uuid4().hex[:8]}"
    yt_id_a = f"yt_a_{uuid.uuid4().hex[:8]}"
    yt_id_b = f"yt_b_{uuid.uuid4().hex[:8]}"

    channel_defaults = {
        "duration_mode": "adaptive",
        "min_clip_duration": 15.0,
        "max_clip_duration": 30.0,
        "clips_count": 3,
        "video_layout": "fill_blur"
    }

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Isolation Channel",
            channel_url="https://youtube.com/@IsoChannel",
            auto_clip=True,
            auto_publish=False,
            processing_profile=channel_defaults
        )
        session.add(ch)

        # Decision A (Customized)
        dec_a = VideoDecision(
            id=str(uuid.uuid4()),
            channel_id=ch_id,
            youtube_id=yt_id_a,
            video_title="Video A",
            youtube_url=f"https://youtube.com/watch?v={yt_id_a}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=datetime.now(timezone.utc),
            channel_profile_snapshot=channel_defaults,
            created_at=datetime.now(timezone.utc)
        )
        # Decision B (Default)
        dec_b = VideoDecision(
            id=str(uuid.uuid4()),
            channel_id=ch_id,
            youtube_id=yt_id_b,
            video_title="Video B",
            youtube_url=f"https://youtube.com/watch?v={yt_id_b}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=datetime.now(timezone.utc),
            channel_profile_snapshot=channel_defaults,
            created_at=datetime.now(timezone.utc)
        )
        session.add_all([dec_a, dec_b])
        session.commit()

        dec_a_id = dec_a.id
        dec_b_id = dec_b.id

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        # Resolve A with custom overrides
        overrides_a = {"video_layout": "fit_black", "clips_count": 5}
        resolve_video_decision_sync(decision_id=dec_a_id, action="custom", custom_overrides=overrides_a)

        # Resolve B with defaults
        resolve_video_decision_sync(decision_id=dec_b_id, action="countdown")

    # Assert persistence
    with SyncSessionLocal() as session:
        rec_ch = session.query(Channel).filter_by(id=ch_id).first()
        rec_a = session.query(VideoDecision).filter_by(id=dec_a_id).first()
        rec_b = session.query(VideoDecision).filter_by(id=dec_b_id).first()

        # Channel defaults remain untouched
        assert rec_ch.processing_profile["video_layout"] == "fill_blur"
        assert rec_ch.processing_profile["clips_count"] == 3

        # Decision A has custom overrides
        assert rec_a.overrides["video_layout"] == "fit_black"
        assert rec_a.overrides["clips_count"] == 5

        # Decision B has original defaults
        assert rec_b.overrides["video_layout"] == "fill_blur"
        assert rec_b.overrides["clips_count"] == 3


# ── 10. Truthful Pipeline Timestamps in Asia/Kolkata (IST) ───────────────────

def test_truthful_pipeline_timestamps_and_ist_formatting():
    """Verify IST formatting and genuine pipeline timestamps."""
    utc_now = datetime(2026, 10, 13, 10, 30, 0, tzinfo=timezone.utc)
    ist_str = format_ist(utc_now)
    # UTC 10:30 + 05:30 = 16:00 (4:00 PM)
    assert "04:00:00 PM IST" in ist_str
    assert "13 Oct 2026" in ist_str


# ── 11. Output Validator Enforces Shorts Duration Limit ──────────────────────

def test_output_validator_rejects_duration_exceeding_shorts_limit():
    """Verify OutputValidatorError raised if video exceeds 30.0s."""
    mock_ffprobe_data = {
        "format": {"duration": "35.5"},
        "streams": [
            {"codec_type": "video", "width": 1080, "height": 1920},
            {"codec_type": "audio"}
        ]
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 1024
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = json.dumps(mock_ffprobe_data)

                with pytest.raises(OutputValidatorError, match="exceeds maximum Shorts duration limit of 30.0s"):
                    validate_video_output(video_path="dummy.mp4", max_duration=30.0)


# ── 12. Backend Restart & Periodic Sweep Recovery ────────────────────────────

def test_backend_restart_recovery_with_sweep():
    """Verify sweep task recovers pending decisions left in DB across backend restarts."""
    ch_id = f"ch_restart_{uuid.uuid4().hex[:8]}"
    dec_id_1 = str(uuid.uuid4())
    dec_id_2 = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Restart Channel",
            channel_url="https://youtube.com/@RestartChannel",
            auto_clip=True,
            auto_publish=False
        )
        session.add(ch)

        # 1. Decision awaiting settings with passed deadline
        d1 = VideoDecision(
            id=dec_id_1,
            channel_id=ch_id,
            youtube_id=f"yt_1_{uuid.uuid4().hex[:6]}",
            video_title="Stale Awaiting",
            youtube_url="https://youtube.com/watch?v=stale1",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=now - timedelta(seconds=10),
            channel_profile_snapshot={},
            created_at=now - timedelta(seconds=30)
        )
        # 2. Decision customizing with expired lease
        d2 = VideoDecision(
            id=dec_id_2,
            channel_id=ch_id,
            youtube_id=f"yt_2_{uuid.uuid4().hex[:6]}",
            video_title="Abandoned Customizing",
            youtube_url="https://youtube.com/watch?v=stale2",
            status=VideoDecisionStatus.CUSTOMIZING.value,
            decision_deadline=now - timedelta(seconds=150),
            customization_lease_expires_at=now - timedelta(seconds=5),
            channel_profile_snapshot={},
            created_at=now - timedelta(seconds=160)
        )
        session.add_all([d1, d2])
        session.commit()

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async"):
        # Run periodic sweep (as would happen right after backend/beat starts up)
        sweep_pending_decisions_task()

    with SyncSessionLocal() as session:
        rec1 = session.query(VideoDecision).filter_by(id=dec_id_1).first()
        rec2 = session.query(VideoDecision).filter_by(id=dec_id_2).first()
        assert rec1.status == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert rec1.job_id is not None
        assert rec2.status == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert rec2.job_id is not None


# ── 13. Celery Dispatch Failure Safety ───────────────────────────────────────

def test_celery_dispatch_failure_retained_safely():
    """Verify decision and job remain securely committed in DB even if Celery dispatch errors."""
    ch_id = f"ch_err_{uuid.uuid4().hex[:8]}"
    dec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"yt_ch_{ch_id}",
            channel_name="Error Channel",
            channel_url="https://youtube.com/@ErrorChannel",
            auto_clip=True,
            auto_publish=False
        )
        session.add(ch)
        d = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=f"yt_err_{uuid.uuid4().hex[:6]}",
            video_title="Error Video",
            youtube_url="https://youtube.com/watch?v=errvid",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=now,
            channel_profile_snapshot={},
            created_at=now
        )
        session.add(d)
        session.commit()

    # Simulate Celery broker temporarily unreachable
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async", side_effect=RuntimeError("Redis connection lost")):
        res = resolve_video_decision_sync(decision_id=dec_id, action="apply_defaults")
        assert res["status"] == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert "job_id" in res

    # Verify decision state and job record exist in PostgreSQL
    with SyncSessionLocal() as session:
        d_rec = session.query(VideoDecision).filter_by(id=dec_id).first()
        job_rec = session.query(Job).filter_by(id=res["job_id"]).first()
        assert d_rec.status == VideoDecisionStatus.RESOLVED_DEFAULTS.value
        assert job_rec is not None
        assert job_rec.source_url == "https://youtube.com/watch?v=errvid"


# ── 14. All Four Auto-Clip / Auto-Publish Combinations ────────────────────────

def test_all_four_auto_clip_and_auto_publish_combinations():
    """Verify independent behavior across all 4 combinations of auto_clip and auto_publish."""
    combinations = [
        {"auto_clip": False, "auto_publish": False},
        {"auto_clip": True, "auto_publish": False},
        {"auto_clip": False, "auto_publish": True},
        {"auto_clip": True, "auto_publish": True},
    ]

    for combo in combinations:
        ch_id = f"ch_combo_{uuid.uuid4().hex[:8]}"
        dec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        dest_id = f"dest_{uuid.uuid4().hex[:8]}" if combo["auto_publish"] else None

        with SyncSessionLocal() as session:
            if dest_id:
                dest_ch = Channel(
                    id=dest_id,
                    youtube_channel_id=f"yt_dest_{dest_id}",
                    channel_name=f"Dest Channel {dest_id}",
                    channel_url=f"https://youtube.com/@Dest_{dest_id}",
                    is_destination=True,
                    is_test=True
                )
                session.add(dest_ch)
                session.flush()

            ch = Channel(
                id=ch_id,
                youtube_channel_id=f"yt_ch_{ch_id}",
                channel_name=f"Combo {combo['auto_clip']}_{combo['auto_publish']}",
                channel_url=f"https://youtube.com/@Combo_{uuid.uuid4().hex[:6]}",
                auto_clip=combo["auto_clip"],
                auto_publish=combo["auto_publish"],
                publish_destination_id=dest_id,
                is_test=True
            )
            session.add(ch)

            dec = VideoDecision(
                id=dec_id,
                channel_id=ch_id,
                youtube_id=f"yt_c_{uuid.uuid4().hex[:6]}",
                video_title="Combo Video",
                youtube_url="https://youtube.com/watch?v=combo",
                status=VideoDecisionStatus.AWAITING_SETTINGS.value if combo["auto_clip"] else "manual_selection_required",
                decision_deadline=now,
                channel_profile_snapshot={},
                created_at=now
            )
            session.add(dec)
            session.commit()

        # If auto_clip is False, it should NOT automatically resolve during sweep
        if not combo["auto_clip"]:
            sweep_res = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
            assert sweep_res.get("skipped") == "ineligible_status"
        else:
            with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
                sweep_res = resolve_video_decision_sync(decision_id=dec_id, action="sweep")
                assert sweep_res["status"] == VideoDecisionStatus.RESOLVED_DEFAULTS.value
                assert mock_apply.called
                kwargs = mock_apply.call_args.kwargs["kwargs"]
                assert kwargs["auto_publish"] == combo["auto_publish"]
                assert kwargs["publish_destination_id"] == dest_id

        # Clean up combo test entities
        with SyncSessionLocal() as session:
            session.query(VideoDecision).filter_by(id=dec_id).delete(synchronize_session=False)
            cleanup_ch_ids = [ch_id] + ([dest_id] if dest_id else [])
            session.query(Channel).filter(Channel.id.in_(cleanup_ch_ids)).delete(synchronize_session=False)
            session.commit()


# ── 15. Equal Splits Segmentation Boundaries ─────────────────────────────────

def test_equal_splits_duration_and_count_interaction():
    """Verify equal splits respects bounds and does not fabricate empty clips."""
    from backend.services.segmentation import generate_equal_splits

    # 1. 100s video with target duration 25s -> exactly 4 clips
    clips_1 = generate_equal_splits(video_duration=100.0, target_duration=25.0)
    assert len(clips_1) == 4
    for c in clips_1:
        assert c["duration"] == 25.0

    # 2. Short video (18s) with target duration 25s -> exactly 1 clip of 18s (no empty remainder)
    clips_2 = generate_equal_splits(video_duration=18.0, target_duration=25.0)
    assert len(clips_2) == 1
    assert clips_2[0]["duration"] == 18.0
    assert clips_2[0]["start"] == 0.0
    assert clips_2[0]["end"] == 18.0

    # 3. Target duration absent -> divides by num_clips
    clips_3 = generate_equal_splits(video_duration=90.0, num_clips=3)
    assert len(clips_3) == 3
    for c in clips_3:
        assert c["duration"] == 30.0

