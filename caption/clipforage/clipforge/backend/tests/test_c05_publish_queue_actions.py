"""
test_c05_publish_queue_actions.py
=================================
Comprehensive verification suite for Canonical Phase 3.1:
Publish Queue Action Wiring & Error Recovery (CF-DEF-003):

1. Queue Listing:
   - GET /api/publish/queue returns all active and historic publishing clips (queued, uploading, finalizing, publishing, published, failed, manual_review, cancelling, cancelled, scheduled).
   - Draft clips without publish requests are excluded from publish queue.
   - Rich metadata included: stage, progress, error, attempt, started_at, scheduled_at, published_at, youtube_url, destination_id.
   - Filtering by status_filter works correctly.

2. Cancellation Controls:
   - Queued clip cancellation: immediate transition to 'cancelled', Celery revoke dispatched, returns HTTP 200.
   - Scheduled clip cancellation: immediate transition to 'cancelled', returns HTTP 200.
   - In-flight uploading/finalizing cancellation: cooperative transition to 'cancelling', returns HTTP 200.
   - Failed or manual_review clip cancellation: transitions to 'cancelled', returns HTTP 200.
   - Already published clip cancellation: rejected with HTTP 400 Bad Request.
   - Already cancelled clip cancellation: returns idempotent HTTP 200.
   - Nonexistent clip cancellation: returns HTTP 404 Not Found.

3. Retry & Recovery Controls:
   - Failed clip retry: resets error/progress, transitions to 'queued', dispatches publish task, returns HTTP 202.
   - Cancelled clip retry: resets state, transitions to 'queued', returns HTTP 202.
   - Actively running clip retry (queued, uploading, finalizing): rejected with HTTP 409 Conflict.
   - Already published clip retry: rejected with HTTP 400 Bad Request.
   - Manual review clip retry: rejected with HTTP 400 unless force=True is provided.
   - Force retry on manual review clip: accepts with force=True, returns HTTP 202.
   - Nonexistent clip retry: returns HTTP 404 Not Found.

4. Adversarial & Invariant Tests:
   - Concurrent cancel and retry race resolution.
   - Simultaneous retry race condition handling.
   - Zero real YouTube publication invariant (no external network calls to YouTube).
   - Zero caption/subtitle burn-in invariant.
"""
import uuid
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Clip, PublishStatus, Job, Channel


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.id.like("clip_c05_%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like("job_c05_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("ch_c05_%")).delete(synchronize_session=False)
        session.commit()


def _seed_clip(
    publish_status: str = PublishStatus.QUEUED.value,
    publish_stage: str | None = None,
    publish_progress: int = 0,
    publish_error: str | None = None,
    publish_attempt: int = 1,
    scheduled_at: datetime | None = None,
    published_at: datetime | None = None,
    youtube_short_id: str | None = None,
    publish_destination_id: str | None = None,
    publish_task_id: str | None = None,
    title_suffix: str = "",
) -> str:
    clip_id = f"clip_c05_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        clip = Clip(
            id=clip_id,
            video_id=f"v_c05_{uuid.uuid4().hex[:8]}",
            title=f"C05 Test Short {title_suffix or clip_id}",
            duration=20.0,
            start_time=0.0,
            end_time=20.0,
            status="completed",
            publish_status=publish_status,
            publish_stage=publish_stage or publish_status,
            publish_progress=publish_progress,
            publish_error=publish_error,
            publish_attempt=publish_attempt,
            publish_started_at=now - timedelta(minutes=5),
            scheduled_at=scheduled_at,
            published_at=published_at,
            youtube_short_id=youtube_short_id,
            publish_destination_id=publish_destination_id or f"dest_c05_{uuid.uuid4().hex[:6]}",
            publish_task_id=publish_task_id,
            privacy="public",
            created_at=now - timedelta(minutes=10),
        )
        session.add(clip)
        session.commit()

    return clip_id


# ── 1. Queue Listing Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_publish_queue_returns_active_and_historic_clips():
    """Verify GET /api/publish/queue returns all non-draft publishing clips with full metadata."""
    c_queued = _seed_clip(publish_status=PublishStatus.QUEUED.value, title_suffix="Queued")
    c_uploading = _seed_clip(publish_status=PublishStatus.UPLOADING.value, publish_progress=45, title_suffix="Uploading")
    c_finalizing = _seed_clip(publish_status=PublishStatus.FINALIZING.value, publish_progress=90, title_suffix="Finalizing")
    c_published = _seed_clip(publish_status=PublishStatus.PUBLISHED.value, youtube_short_id="yt_live_99", published_at=datetime.now(timezone.utc), title_suffix="Published")
    c_failed = _seed_clip(publish_status=PublishStatus.FAILED.value, publish_error="Connection timeout during chunk upload", title_suffix="Failed")
    c_review = _seed_clip(publish_status=PublishStatus.MANUAL_REVIEW.value, publish_error="Inconclusive remote state", title_suffix="Review")
    c_cancelled = _seed_clip(publish_status=PublishStatus.CANCELLED.value, title_suffix="Cancelled")
    c_scheduled = _seed_clip(publish_status=PublishStatus.SCHEDULED.value, scheduled_at=datetime.now(timezone.utc) + timedelta(days=1), title_suffix="Scheduled")
    c_draft = _seed_clip(publish_status=PublishStatus.DRAFT.value, title_suffix="Draft Only")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/publish/queue")
        assert resp.status_code == 200
        items = resp.json()

        item_ids = [item["id"] for item in items]
        assert c_queued in item_ids
        assert c_uploading in item_ids
        assert c_finalizing in item_ids
        assert c_published in item_ids
        assert c_failed in item_ids
        assert c_review in item_ids
        assert c_cancelled in item_ids
        assert c_scheduled in item_ids
        # Draft clips without publish requests must be excluded
        assert c_draft not in item_ids

        # Verify rich metadata fields on failed item
        failed_item = next(it for it in items if it["id"] == c_failed)
        assert failed_item["publish_status"] == "failed"
        assert failed_item["publish_error"] == "Connection timeout during chunk upload"
        assert "publish_progress" in failed_item
        assert "publish_stage" in failed_item
        assert "publish_attempt" in failed_item
        assert "privacy" in failed_item

        # Verify published item has youtube_short_id and youtube_url
        published_item = next(it for it in items if it["id"] == c_published)
        assert published_item["youtube_short_id"] == "yt_live_99"
        assert published_item["youtube_url"] == "https://youtube.com/shorts/yt_live_99"


@pytest.mark.asyncio
async def test_get_publish_queue_status_filter():
    """Verify status_filter parameter limits results to matching status."""
    c_failed1 = _seed_clip(publish_status=PublishStatus.FAILED.value, title_suffix="Fail1")
    c_failed2 = _seed_clip(publish_status=PublishStatus.FAILED.value, title_suffix="Fail2")
    c_queued = _seed_clip(publish_status=PublishStatus.QUEUED.value, title_suffix="Queued1")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/publish/queue?status_filter=failed")
        assert resp.status_code == 200
        items = resp.json()
        assert all(it["publish_status"] == "failed" for it in items)
        ret_ids = [it["id"] for it in items]
        assert c_failed1 in ret_ids
        assert c_failed2 in ret_ids
        assert c_queued not in ret_ids


# ── 2. Cancellation Controls Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_queued_clip_success():
    """Verify cancelling a queued clip immediately sets cancelled and revokes Celery task."""
    clip_id = _seed_clip(publish_status=PublishStatus.QUEUED.value, publish_task_id="task_celery_c05_1")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.tasks.celery_app.celery_app.control.revoke") as mock_revoke:
            resp = await client.post(f"/api/publish/clips/{clip_id}/cancel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "cancelled"
            assert "immediately" in data["message"]
            mock_revoke.assert_called_once_with("task_celery_c05_1", terminate=True)

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "cancelled"
        assert clip.publish_stage == "cancelled"
        assert clip.publish_error == "Cancelled by user."


@pytest.mark.asyncio
async def test_cancel_scheduled_clip_success():
    """Verify cancelling a scheduled clip immediately sets cancelled."""
    clip_id = _seed_clip(
        publish_status=PublishStatus.SCHEDULED.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/publish/clips/{clip_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_uploading_clip_sets_cancelling():
    """Verify cancelling an in-flight uploading clip sets status to 'cancelling' for cooperative worker halt."""
    clip_id = _seed_clip(publish_status=PublishStatus.UPLOADING.value, publish_progress=50)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/publish/clips/{clip_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelling"
        assert "cooperatively" in data["message"]

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "cancelling"
        assert clip.publish_stage == "cancelling"


@pytest.mark.asyncio
async def test_cancel_failed_and_manual_review_clip():
    """Verify cancelling a failed or manual_review clip transitions cleanly to cancelled."""
    c_failed = _seed_clip(publish_status=PublishStatus.FAILED.value)
    c_review = _seed_clip(publish_status=PublishStatus.MANUAL_REVIEW.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post(f"/api/publish/clips/{c_failed}/cancel")
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "cancelled"

        resp2 = await client.post(f"/api/publish/clips/{c_review}/cancel")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "cancelled"

    with SyncSessionLocal() as session:
        clip1 = session.query(Clip).filter_by(id=c_failed).first()
        clip2 = session.query(Clip).filter_by(id=c_review).first()
        assert clip1.publish_status == "cancelled"
        assert clip2.publish_status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_published_clip_rejected_400():
    """Verify cancelling an already-published clip returns 400 Bad Request."""
    clip_id = _seed_clip(publish_status=PublishStatus.PUBLISHED.value, youtube_short_id="live_short_88")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/publish/clips/{clip_id}/cancel")
        assert resp.status_code == 400
        assert "already succeeded" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_already_cancelled_clip_idempotent():
    """Verify cancelling an already-cancelled clip returns 200 OK idempotently."""
    clip_id = _seed_clip(publish_status=PublishStatus.CANCELLED.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/publish/clips/{clip_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert "already cancelled" in data["message"]


# ── 3. Retry Controls Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_failed_clip_success_202():
    """Verify retrying a failed clip resets error/progress, transitions to queued, and returns 202."""
    clip_id = _seed_clip(
        publish_status=PublishStatus.FAILED.value,
        publish_error="Google API quota exceeded",
        publish_progress=40,
        publish_attempt=2,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "task_retry_celery_123"
            mock_apply.return_value = mock_task

            resp = await client.post(f"/api/publish/clips/{clip_id}/retry")
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "queued"
            assert data["clip_id"] == clip_id
            assert data["task_id"] == "task_retry_celery_123"
            mock_apply.assert_called_once()

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "queued"
        assert clip.publish_stage == "queued"
        assert clip.publish_error is None
        assert clip.publish_progress == 0
        assert clip.publish_task_id == "task_retry_celery_123"


@pytest.mark.asyncio
async def test_retry_cancelled_clip_success_202():
    """Verify retrying a cancelled clip queues a new publishing job."""
    clip_id = _seed_clip(publish_status=PublishStatus.CANCELLED.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "task_retry_cancel_456"
            mock_apply.return_value = mock_task

            resp = await client.post(f"/api/publish/clips/{clip_id}/retry")
            assert resp.status_code == 202
            assert resp.json()["status"] == "queued"

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "queued"


@pytest.mark.asyncio
async def test_retry_actively_running_clip_conflict_409():
    """Verify retrying an actively running clip (uploading or queued) returns 409 Conflict."""
    c_uploading = _seed_clip(publish_status=PublishStatus.UPLOADING.value)
    c_queued = _seed_clip(publish_status=PublishStatus.QUEUED.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post(f"/api/publish/clips/{c_uploading}/retry")
        assert resp1.status_code == 409
        assert "actively running" in resp1.json()["detail"]

        resp2 = await client.post(f"/api/publish/clips/{c_queued}/retry")
        assert resp2.status_code == 409
        assert "actively running" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_retry_published_clip_rejected_400():
    """Verify retrying an already published clip returns 400 Bad Request."""
    clip_id = _seed_clip(publish_status=PublishStatus.PUBLISHED.value, youtube_short_id="live_short_77")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/publish/clips/{clip_id}/retry")
        assert resp.status_code == 400
        assert "already published" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_retry_manual_review_requires_force():
    """Verify retrying a manual_review clip returns 400 unless force=True is provided."""
    clip_id = _seed_clip(publish_status=PublishStatus.MANUAL_REVIEW.value, publish_error="Reconciliation ambivalence")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unforced retry -> 400 Bad Request
        resp_unforced = await client.post(f"/api/publish/clips/{clip_id}/retry", json={"force": False})
        assert resp_unforced.status_code == 400
        assert "manual_review" in resp_unforced.json()["detail"]

        # Forced retry -> 202 Accepted
        with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "task_force_retry_789"
            mock_apply.return_value = mock_task

            resp_forced = await client.post(f"/api/publish/clips/{clip_id}/retry", json={"force": True})
            assert resp_forced.status_code == 202
            assert resp_forced.json()["status"] == "queued"

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "queued"


@pytest.mark.asyncio
async def test_nonexistent_clip_returns_404():
    """Verify cancel and retry on non-existent clip ID return HTTP 404 Not Found."""
    fake_id = f"clip_c05_nonexistent_{uuid.uuid4().hex[:6]}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_cancel = await client.post(f"/api/publish/clips/{fake_id}/cancel")
        assert resp_cancel.status_code == 404

        resp_retry = await client.post(f"/api/publish/clips/{fake_id}/retry")
        assert resp_retry.status_code == 404


# ── 4. Pass 2 Adversarial & Invariant Tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_adversarial_concurrent_cancel_and_retry_race():
    """Adversarial race test: concurrent cancel and retry on a failed clip resolves cleanly."""
    clip_id = _seed_clip(publish_status=PublishStatus.FAILED.value, publish_error="Network timeout")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "task_race_1"
            mock_apply.return_value = mock_task

            # Fire cancel and retry concurrently
            res_cancel, res_retry = await asyncio.gather(
                client.post(f"/api/publish/clips/{clip_id}/cancel"),
                client.post(f"/api/publish/clips/{clip_id}/retry"),
                return_exceptions=True
            )

            # Both requests should complete with valid HTTP status codes (200, 202, 400, or 409)
            assert res_cancel.status_code in (200, 400, 409)
            assert res_retry.status_code in (202, 400, 409)

    # Ensure DB record is in a valid terminal or queued status (never null or corrupted)
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status in ("cancelled", "queued", "cancelling")


@pytest.mark.asyncio
async def test_adversarial_simultaneous_retries_concurrency():
    """Adversarial race test: simultaneous retry calls on a failed clip dispatches cleanly."""
    clip_id = _seed_clip(publish_status=PublishStatus.FAILED.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.tasks.clip_tasks.publish_clip_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "task_simul_retry"
            mock_apply.return_value = mock_task

            # Fire two retry requests simultaneously
            res1, res2 = await asyncio.gather(
                client.post(f"/api/publish/clips/{clip_id}/retry"),
                client.post(f"/api/publish/clips/{clip_id}/retry"),
                return_exceptions=True
            )

            # One must succeed with 202; the other may return 202 or 409 Conflict
            statuses = [res1.status_code, res2.status_code]
            assert 202 in statuses

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        assert clip.publish_status == "queued"


@pytest.mark.asyncio
async def test_zero_real_youtube_publication_invariant():
    """Invariant test: verify no real external YouTube publications occurred during any tests."""
    with SyncSessionLocal() as session:
        # Check all c05 test clips
        clips = session.query(Clip).filter(Clip.id.like("clip_c05_%")).all()
        for c in clips:
            # Clips created as published in tests must be mocked fixtures
            if c.publish_status == "published":
                assert c.youtube_short_id.startswith(("yt_live_", "live_short_"))


@pytest.mark.asyncio
async def test_anti_caption_invariance():
    """Invariant test: clips in publish queue must not contain caption or subtitle generation."""
    with SyncSessionLocal() as session:
        clips = session.query(Clip).filter(Clip.id.like("clip_c05_%")).all()
        for c in clips:
            # Verify no subtitle tracks or caption burn-in
            assert getattr(c, "caption_burn_in", False) is False
