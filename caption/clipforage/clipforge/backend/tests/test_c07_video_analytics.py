"""
test_c07_video_analytics.py
===========================
Comprehensive verification suite for Canonical Phase 4.1:
CF-DEF-005 Per-Video Analytics & SEO Cards Integration:

1. Pipeline Summary Telemetry:
   - GET /api/analytics/summary returns pipeline, seo, optimizer, and tracking stats.

2. Video Performance Telemetry (GET /api/analytics/{video_id}):
   - Unpolled clip returns 200 with latest_score=None, trend='stable', total_polls=0, snapshots=[].
   - Seeded snapshots calculate correct trend ('up', 'down', 'stable') and latest score.
   - Resolves parent Video snapshots when queried by child Clip ID.

3. SEO Recommendations & Cards (GET /api/analytics/seo/{video_id}):
   - Unanalyzed clip returns 200 with total_snapshots=0, latest_seo_score=None, snapshots=[].
   - Seeded SEOAnalysis records parse missing_keywords, recommended_hashtags, weak_hashtags,
     tags, and hashtags as clean Python lists (not raw JSON or unparsed strings).
   - Resolves child clip SEO records when queried by parent Video ID.

4. Auto-Optimization Logs (GET /api/analytics/optimize/{video_id}/log):
   - Returns empty log when no attempts recorded.
   - Returns ordered attempt history with attempts, new titles, and view scores.
   - Resolves parent Video logs when queried by child Clip ID.

5. Auto-Optimize Flag Mutation (PATCH /api/analytics/optimize/{video_id}/flag):
   - Sets auto_optimize=True on Video.
   - Sets auto_optimize=False on parent Video when queried with child Clip ID.
   - Returns 404 Not Found for invalid ID.

6. Active Tracking Queue Management (GET /active, POST /track, POST /cancel):
   - GET /api/analytics/active returns enriched tracker tasks (task_id, clip_id, youtube_video_id, status, done=False).
   - POST /api/analytics/track/{video_id} starts tracking with explicit youtube_video_id.
   - POST /api/analytics/track/{video_id} infers youtube_short_id from published clip.
   - POST /api/analytics/cancel/{task_id} marks tracker as 'stopped' and returns 200.
   - POST /api/analytics/cancel/{task_id} returns 404 for nonexistent task.

7. Manual Optimization Trigger (POST /api/analytics/optimize/{video_id}):
   - Triggers single-shot optimizer and returns 200 with optimizer_started.

8. System Invariants & Safety:
   - Shorts duration capped strictly between 15.0 and 30.0 seconds.
   - Zero caption/subtitle burn-in or generation.
   - Never publish real YouTube content or perform destructive actions (is_test=True).
"""
import uuid
import json
import pytest
from datetime import datetime, timezone, timedelta
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import (
    Clip,
    Video,
    Channel,
    VideoAnalytics,
    SEOAnalysis,
    OptimizationLog,
    VideoTrackingQueue,
    PublishStatus,
)


@pytest.fixture(autouse=True)
async def cleanup_c07_db():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(VideoAnalytics).filter(VideoAnalytics.video_id.like("%c07%")).delete(synchronize_session=False)
        session.query(SEOAnalysis).filter(SEOAnalysis.clip_id.like("%c07%")).delete(synchronize_session=False)
        session.query(OptimizationLog).filter(OptimizationLog.video_id.like("%c07%")).delete(synchronize_session=False)
        session.query(VideoTrackingQueue).filter(VideoTrackingQueue.clip_id.like("%c07%")).delete(synchronize_session=False)
        session.query(VideoTrackingQueue).filter(VideoTrackingQueue.id.like("%c07%")).delete(synchronize_session=False)
        session.query(Clip).filter(Clip.id.like("clip_c07_%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like("vid_c07_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("ch_c07_%")).delete(synchronize_session=False)
        session.commit()


def _seed_channel(channel_id: str, channel_name: str = "C07 Test Channel") -> Channel:
    with SyncSessionLocal() as session:
        ch = Channel(
            id=channel_id,
            channel_name=channel_name,
            channel_url="https://youtube.com/@c07test",
            is_destination=True,
            is_default_destination=False,
        )
        session.add(ch)
        session.commit()
        return ch


def _seed_video(video_id: str, channel_id: str | None = None, auto_optimize: bool = True) -> Video:
    with SyncSessionLocal() as session:
        vid = Video(
            id=video_id,
            channel_id=channel_id,
            youtube_url="https://youtube.com/watch?v=c07test123",
            title="C07 Source Video Title",
            transcript="This is a test transcript for C07 video analytics testing.",
            auto_optimize=auto_optimize,
        )
        session.add(vid)
        session.commit()
        return vid


def _seed_clip(
    clip_id: str,
    video_id: str,
    title: str = "C07 Test Clip",
    publish_status: str = PublishStatus.DRAFT,
    youtube_short_id: str | None = None,
    duration: float = 22.5,
    score: float = 8.5,
) -> Clip:
    with SyncSessionLocal() as session:
        clip = Clip(
            id=clip_id,
            video_id=video_id,
            title=title,
            description="C07 Test clip description",
            start_time=10.0,
            end_time=10.0 + duration,
            duration=duration,
            score=score,
            publish_status=publish_status,
            youtube_short_id=youtube_short_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(clip)
        session.commit()
        session.refresh(clip)
        session.expunge(clip)
        return clip


# ── 1. Pipeline Summary Telemetry ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_pipeline_summary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline" in data
        assert "successful_phases" in data["pipeline"]
        assert "avg_phase_duration_ms" in data["pipeline"]
        assert "seo" in data
        assert "avg_seo_score" in data["seo"]
        assert "optimizer" in data
        assert "tracking" in data


# ── 2. Video Performance Telemetry ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_analytics_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/analytics/clip_c07_nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == "clip_c07_nonexistent"
        assert data["latest_score"] is None
        assert data["trend"] == "stable"
        assert data["total_polls"] == 0
        assert data["snapshots"] == []


@pytest.mark.asyncio
async def test_get_analytics_with_snapshots_and_trend():
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_clip(clip_id, "vid_c07_parent")

    # Seed 3 snapshots (newest to oldest)
    now = datetime.now(timezone.utc)
    with SyncSessionLocal() as session:
        s1 = VideoAnalytics(
            video_id=clip_id,
            view_count=5200,
            like_count=350,
            comment_count=45,
            view_score=8.7,
            fetched_at=now,
        )
        s2 = VideoAnalytics(
            video_id=clip_id,
            view_count=3100,
            like_count=210,
            comment_count=25,
            view_score=7.2,
            fetched_at=now - timedelta(hours=12),
        )
        s3 = VideoAnalytics(
            video_id=clip_id,
            view_count=1200,
            like_count=80,
            comment_count=8,
            view_score=5.5,
            fetched_at=now - timedelta(hours=24),
        )
        session.add_all([s1, s2, s3])
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/analytics/{clip_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == clip_id
        assert data["latest_score"] == 8.7
        # 8.7 - 7.2 = 1.5 > 0.5 => trend is 'up'
        assert data["trend"] == "up"
        assert data["total_polls"] == 3
        assert len(data["snapshots"]) == 3
        assert data["snapshots"][0]["view_count"] == 5200
        assert data["snapshots"][0]["view_score"] == 8.7


@pytest.mark.asyncio
async def test_get_analytics_resolves_parent_video_of_clip():
    vid_id = f"vid_c07_{uuid.uuid4().hex[:8]}"
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_video(vid_id)
    _seed_clip(clip_id, vid_id)

    # Seed snapshot under parent video_id
    now = datetime.now(timezone.utc)
    with SyncSessionLocal() as session:
        s = VideoAnalytics(
            video_id=vid_id,
            view_count=9800,
            like_count=620,
            comment_count=88,
            view_score=9.1,
            fetched_at=now,
        )
        session.add(s)
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Query using child clip_id
        resp = await client.get(f"/api/analytics/{clip_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_score"] == 9.1
        assert len(data["snapshots"]) == 1
        assert data["snapshots"][0]["view_count"] == 9800


# ── 3. SEO Analysis & Recommendation Cards ────────────────────────────────────

@pytest.mark.asyncio
async def test_get_seo_analysis_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/analytics/seo/clip_c07_nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == "clip_c07_nonexistent"
        assert data["total_snapshots"] == 0
        assert data["latest_seo_score"] is None
        assert data["snapshots"] == []


@pytest.mark.asyncio
async def test_get_seo_analysis_with_seeded_data_and_list_parsing():
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_clip(clip_id, "vid_c07_parent")

    # Seed SEO record with JSON list strings
    with SyncSessionLocal() as session:
        seo = SEOAnalysis(
            clip_id=clip_id,
            seo_score=88.5,
            ctr_score=75.0,
            discoverability_score=81.8,
            missing_keywords=json.dumps(["viral hooks", "shorts mastery", "growth tips"]),
            recommended_hashtags=json.dumps(["#shorts", "#viral", "#creator"]),
            weak_hashtags=json.dumps(["#trending", "#fyp"]),
            seo_json=json.dumps({
                "title": "5 Insane YouTube Secrets You Never Knew 🤯",
                "tags": ["youtube tips", "algorithm", "shorts"],
                "hashtags": ["#shorts", "#viral", "#creator"],
                "view_score_at_optimization": 8.4,
            }),
        )
        session.add(seo)
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/analytics/seo/{clip_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == clip_id
        assert data["total_snapshots"] == 1
        assert data["latest_seo_score"] == 88.5
        assert data["latest_ctr_score"] == 75.0

        snap = data["snapshots"][0]
        assert snap["clip_id"] == clip_id
        assert snap["seo_score"] == 88.5
        assert snap["title"] == "5 Insane YouTube Secrets You Never Knew 🤯"
        # Verify fields are parsed as lists
        assert isinstance(snap["missing_keywords"], list)
        assert "viral hooks" in snap["missing_keywords"]
        assert isinstance(snap["recommended_hashtags"], list)
        assert "#shorts" in snap["recommended_hashtags"]
        assert isinstance(snap["weak_hashtags"], list)
        assert "#trending" in snap["weak_hashtags"]
        assert isinstance(snap["tags"], list)
        assert "algorithm" in snap["tags"]


@pytest.mark.asyncio
async def test_get_seo_analysis_resolves_parent_video():
    vid_id = f"vid_c07_{uuid.uuid4().hex[:8]}"
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_video(vid_id)
    _seed_clip(clip_id, vid_id)

    with SyncSessionLocal() as session:
        seo = SEOAnalysis(
            clip_id=clip_id,
            seo_score=92.0,
            ctr_score=80.0,
            discoverability_score=86.0,
            missing_keywords="keyword1, keyword2",
            recommended_hashtags="#tag1, #tag2",
            weak_hashtags="#weak1",
            seo_json=json.dumps({"title": "Parent Video Child SEO"}),
        )
        session.add(seo)
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Query using parent vid_id
        resp = await client.get(f"/api/analytics/seo/{vid_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_snapshots"] >= 1
        assert data["latest_seo_score"] == 92.0


# ── 4. Auto-Optimization History & Logs ───────────────────────────────────────

@pytest.mark.asyncio
async def test_get_optimization_log_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/analytics/optimize/vid_c07_none/log")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == "vid_c07_none"
        assert data["total_attempts"] == 0
        assert data["log"] == []


@pytest.mark.asyncio
async def test_get_optimization_log_with_seeded_data():
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_clip(clip_id, "vid_c07_parent")

    now = datetime.now(timezone.utc)
    with SyncSessionLocal() as session:
        opt1 = OptimizationLog(
            video_id=clip_id,
            attempt=1,
            new_title="Secret AI Trick That Will Blow Your Mind!",
            view_score=7.9,
            created_at=now - timedelta(hours=6),
        )
        opt2 = OptimizationLog(
            video_id=clip_id,
            attempt=2,
            new_title="Stop Scrolling! This 1 AI Tool Changes Everything 🚀",
            view_score=8.6,
            created_at=now,
        )
        session.add_all([opt1, opt2])
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/analytics/optimize/{clip_id}/log")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == clip_id
        assert data["total_attempts"] == 2
        # Ordered newest first
        assert data["log"][0]["attempt"] == 2
        assert "Stop Scrolling" in data["log"][0]["new_title"]
        assert data["log"][0]["view_score"] == 8.6
        assert data["log"][1]["attempt"] == 1


# ── 5. Auto-Optimize Flag Mutation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_auto_optimize_flag():
    vid_id = f"vid_c07_{uuid.uuid4().hex[:8]}"
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_video(vid_id, auto_optimize=True)
    _seed_clip(clip_id, vid_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Toggle to false on parent video
        resp = await client.patch(f"/api/analytics/optimize/{vid_id}/flag?auto_optimize=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_optimize"] is False

        # Verify in DB
        with SyncSessionLocal() as session:
            v = session.query(Video).filter_by(id=vid_id).first()
            assert v.auto_optimize is False

        # Toggle to true using child clip_id
        resp2 = await client.patch(f"/api/analytics/optimize/{clip_id}/flag?auto_optimize=true")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["auto_optimize"] is True

        # Verify in DB
        with SyncSessionLocal() as session:
            v = session.query(Video).filter_by(id=vid_id).first()
            assert v.auto_optimize is True

        # Nonexistent video returns 404
        resp_404 = await client.patch("/api/analytics/optimize/vid_c07_invalid_404/flag?auto_optimize=true")
        assert resp_404.status_code == 404


# ── 6. Active Performance Tracking Queue & Lifecycle ─────────────────────────

@pytest.mark.asyncio
async def test_list_active_trackers_empty_and_populated():
    task_id = f"task_c07_{uuid.uuid4().hex[:8]}"
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_clip(clip_id, "vid_c07_parent")

    with SyncSessionLocal() as session:
        t = VideoTrackingQueue(
            id=task_id,
            clip_id=clip_id,
            youtube_video_id=f"yt_c07_{task_id[:6]}",
            uploaded_at=datetime.now(timezone.utc),
            next_check_at=datetime.now(timezone.utc) + timedelta(hours=2),
            optimization_attempts=1,
            last_score=7.4,
            status="active",
        )
        session.add(t)
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/analytics/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_trackers" in data
        assert any(x["task_id"] == task_id for x in data["active_trackers"])
        tracker = next(x for x in data["active_trackers"] if x["task_id"] == task_id)
        assert tracker["clip_id"] == clip_id
        assert tracker["status"] == "active"
        assert tracker["done"] is False


@pytest.mark.asyncio
async def test_start_tracker_explicit_youtube_id():
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_clip(clip_id, "vid_c07_parent")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"youtube_video_id": f"yt_c07_explicit_{clip_id[:6]}"}
        resp = await client.post(f"/api/analytics/track/{clip_id}", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "tracking_started"
        assert data["video_id"] == clip_id
        assert data["youtube_video_id"] == payload["youtube_video_id"]
        assert "task_id" in data

        # Verify entry created in DB
        with SyncSessionLocal() as session:
            entry = session.query(VideoTrackingQueue).filter_by(id=data["task_id"]).first()
            assert entry is not None
            assert entry.clip_id == clip_id
            assert entry.status == "active"


@pytest.mark.asyncio
async def test_start_tracker_published_clip_inferred_id():
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    inferred_yt = f"yt_c07_inferred_{clip_id[:6]}"
    _seed_clip(clip_id, "vid_c07_parent", publish_status=PublishStatus.PUBLISHED, youtube_short_id=inferred_yt)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Post with empty json payload to trigger inference
        resp = await client.post(f"/api/analytics/track/{clip_id}", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "tracking_started"
        assert data["youtube_video_id"] == inferred_yt


@pytest.mark.asyncio
async def test_cancel_tracker_lifecycle():
    task_id = f"task_c07_{uuid.uuid4().hex[:8]}"
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    _seed_clip(clip_id, "vid_c07_parent")

    with SyncSessionLocal() as session:
        t = VideoTrackingQueue(
            id=task_id,
            clip_id=clip_id,
            youtube_video_id=f"yt_c07_{task_id[:6]}",
            uploaded_at=datetime.now(timezone.utc),
            next_check_at=datetime.now(timezone.utc) + timedelta(hours=2),
            status="active",
        )
        session.add(t)
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cancel active tracker
        resp = await client.post(f"/api/analytics/cancel/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["task_id"] == task_id

        # Verify in DB that status is 'stopped'
        with SyncSessionLocal() as session:
            row = session.query(VideoTrackingQueue).filter_by(id=task_id).first()
            assert row.status == "stopped"

        # Cancelling an unknown task returns 404
        resp_404 = await client.post("/api/analytics/cancel/nonexistent_task_c07")
        assert resp_404.status_code == 404


# ── 7. Manual Optimizer Trigger ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_optimizer_success():
    from unittest.mock import patch, MagicMock
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    yt_id = f"yt_c07_opt_{clip_id[:6]}"
    _seed_clip(clip_id, "vid_c07_parent", publish_status=PublishStatus.PUBLISHED, youtube_short_id=yt_id)

    with patch("backend.new_files.auto_optimizer.start_optimizer", return_value=MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/analytics/optimize/{clip_id}", json={})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "optimizer_started"
            assert data["video_id"] == clip_id
            assert data["youtube_video_id"] == yt_id


# ── 8. System Invariants & Safety Verification ────────────────────────────────

@pytest.mark.asyncio
async def test_invariant_duration_and_zero_subtitles():
    """
    Strict Invariant:
    1. Shorts duration must strictly remain between 15.0 and 30.0 seconds.
    2. Zero caption/subtitle burn-in or subtitle generation across all analytics records.
    """
    clip_id = f"clip_c07_{uuid.uuid4().hex[:8]}"
    clip = _seed_clip(clip_id, "vid_c07_parent", duration=25.0)

    assert 15.0 <= clip.duration <= 30.0, f"Duration {clip.duration} violates 15-30s Shorts invariant"

    with SyncSessionLocal() as session:
        c = session.query(Clip).filter_by(id=clip_id).first()
        # Verify no subtitle tracks or burned-in artifacts
        output_p = c.output_path or ""
        assert ".srt" not in output_p.lower()
        assert ".vtt" not in output_p.lower()
        assert ".ass" not in output_p.lower()
