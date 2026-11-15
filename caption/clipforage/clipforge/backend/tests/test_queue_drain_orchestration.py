"""
test_queue_drain_orchestration.py
==================================
Tests for Celery Beat stale job reaper, queue drain on failure,
and queue manager safeguards for ClipForge.

Verifies:
1. stale_job_recovery_task reaps in-flight jobs older than 30 minutes:
   - Sets status='cancelled' for is_test=True
   - Sets status='failed' for is_test=False
   - Triggers trigger_queue_drain_background()
   - Ignores recently updated (<30m) or terminal jobs
2. handle_pipeline_failure_task triggers trigger_queue_drain_background on clip failure as well as job failure.
3. stale-job-recovery is registered in celery_app.conf.beat_schedule running every 120 seconds.
4. /api/videos/url auto-detects synthetic URLs and flags is_test=True.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import or_

from backend.models.database import SyncSessionLocal
from backend.models.models import Job, JobStatus, Clip
from backend.tasks.celery_app import celery_app
from backend.tasks.orchestration import (
    stale_job_recovery_task,
    handle_pipeline_failure_task,
)
from backend.services.queue_manager import (
    SYNTHETIC_URL_PREFIXES,
    is_active_manual_job_filter,
    get_active_manual_jobs_count_sync,
)


@pytest.fixture(autouse=True)
def cleanup_reaper_test_jobs():
    """Ensure clean test environment for reaper and drain tests."""
    test_ids = []

    def _cleanup():
        with SyncSessionLocal() as session:
            rows = session.query(Job.id).filter(
                or_(
                    Job.id.like("reaper-%"),
                    Job.id.like("drain-%"),
                    Job.id.like("fail-%"),
                )
            ).all()
            ids = [r[0] for r in rows] + test_ids
            if ids:
                session.query(Job).filter(Job.id.in_(ids)).delete(synchronize_session=False)
                session.commit()

    _cleanup()
    yield test_ids
    _cleanup()


def test_stale_job_recovery_reaps_stale_jobs():
    """Verify stale_job_recovery_task transitions >30m inactive jobs and triggers queue drain."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(minutes=35)
    fresh_time = now - timedelta(minutes=5)

    with SyncSessionLocal() as session:
        # 1. Stale test job (>30m, selecting) -> should become cancelled
        j_stale_test = Job(
            id=f"reaper-stale-test-{uuid.uuid4().hex[:6]}",
            status=JobStatus.SELECTING.value,
            channel_id=None,
            is_test=True,
            source_url="https://youtu.be/stale_test",
            created_at=old_time,
            updated_at=old_time,
        )
        # 2. Stale production job (>30m, transcribing) -> should become failed
        j_stale_prod = Job(
            id=f"reaper-stale-prod-{uuid.uuid4().hex[:6]}",
            status=JobStatus.TRANSCRIBING.value,
            channel_id=None,
            is_test=False,
            source_url="https://youtu.be/stale_prod",
            created_at=old_time,
            updated_at=old_time,
        )
        # 3. Fresh job (<30m, downloading) -> should stay downloading
        j_fresh = Job(
            id=f"reaper-fresh-{uuid.uuid4().hex[:6]}",
            status=JobStatus.DOWNLOADING.value,
            channel_id=None,
            is_test=False,
            source_url="https://youtu.be/fresh",
            created_at=fresh_time,
            updated_at=fresh_time,
        )
        # 4. Terminal job (already completed) -> should remain completed
        j_completed = Job(
            id=f"reaper-done-{uuid.uuid4().hex[:6]}",
            status=JobStatus.COMPLETED.value,
            channel_id=None,
            is_test=False,
            source_url="https://youtu.be/done",
            created_at=old_time,
            updated_at=old_time,
        )
        session.add_all([j_stale_test, j_stale_prod, j_fresh, j_completed])
        session.commit()

        stale_test_id = j_stale_test.id
        stale_prod_id = j_stale_prod.id
        fresh_id = j_fresh.id
        completed_id = j_completed.id

    with patch("backend.services.queue_manager.trigger_queue_drain_background") as mock_drain:
        result = stale_job_recovery_task()
        assert result["recovered"] == 2
        mock_drain.assert_called_once()

    with SyncSessionLocal() as session:
        j_test = session.query(Job).filter_by(id=stale_test_id).first()
        assert j_test.status == JobStatus.CANCELLED.value
        assert j_test.current_step == "Cancelled"
        assert "Purged stale test execution" in j_test.error_message
        assert j_test.completed_at is not None

        j_prod = session.query(Job).filter_by(id=stale_prod_id).first()
        assert j_prod.status == JobStatus.FAILED.value
        assert j_prod.current_step == "Timed out"
        assert "inactivity > 30m" in j_prod.error_message
        assert j_prod.completed_at is not None

        j_fr = session.query(Job).filter_by(id=fresh_id).first()
        assert j_fr.status == JobStatus.DOWNLOADING.value

        j_comp = session.query(Job).filter_by(id=completed_id).first()
        assert j_comp.status == JobStatus.COMPLETED.value


def test_handle_pipeline_failure_triggers_queue_drain_on_clip_failure():
    """Verify that handle_pipeline_failure_task triggers queue drain when a clip fails."""
    mock_request = MagicMock()
    mock_request.id = "req-fail-clip-123"
    exc = RuntimeError("FFmpeg encode error")

    with patch("backend.services.queue_manager.trigger_queue_drain_background") as mock_drain, \
         patch("backend.tasks.orchestration.update_clip_status_sync") as mock_update_clip:
        handle_pipeline_failure_task(mock_request, exc, None, job_id=None, clip_id="clip-test-1", stage="render")
        mock_update_clip.assert_called_once_with("clip-test-1", "failed", error_msg="RuntimeError: FFmpeg encode error")
        mock_drain.assert_called_once()


def test_handle_pipeline_failure_triggers_queue_drain_on_job_failure():
    """Verify that handle_pipeline_failure_task triggers queue drain when a job fails."""
    mock_request = MagicMock()
    mock_request.id = "req-fail-job-456"
    exc = ValueError("Invalid media format")

    with patch("backend.services.queue_manager.trigger_queue_drain_background") as mock_drain, \
         patch("backend.tasks.orchestration.update_job_sync") as mock_update_job:
        handle_pipeline_failure_task(mock_request, exc, None, job_id="job-test-2", clip_id=None, stage="validate_media")
        mock_update_job.assert_called_once()
        mock_drain.assert_called_once()


def test_celery_beat_schedule_registered():
    """Verify that stale-job-recovery periodic task is registered in Celery Beat schedule."""
    schedule = celery_app.conf.beat_schedule
    assert "stale-job-recovery" in schedule, "stale-job-recovery missing from beat_schedule"
    entry = schedule["stale-job-recovery"]
    assert entry["task"] == "backend.tasks.orchestration.stale_job_recovery_task"
    assert entry["schedule"] == 120, f"Expected 120s schedule, got {entry['schedule']}"


def test_synthetic_url_prefixes_constants():
    """Verify synthetic URL prefixes match specification."""
    expected = (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "test_upload.mp4",
        "legacy.mp4",
        "valid.mp4",
    )
    for prefix in expected:
        assert prefix in SYNTHETIC_URL_PREFIXES


@pytest.mark.asyncio
async def test_videos_route_synthetic_url_auto_detects_test_flag(cleanup_reaper_test_jobs):
    """Verify POST /api/videos/url auto-detects synthetic test URLs and sets is_test=True."""
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.services.queue_manager.dispatch_celery_job", return_value="mock-task-id"), \
             patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            # Rickroll URL: known synthetic fixture
            resp = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
            assert resp.status_code == 200
            data = resp.json()
            job_id = data["job_id"]
            cleanup_reaper_test_jobs.append(job_id)

            with SyncSessionLocal() as session:
                job = session.query(Job).filter_by(id=job_id).first()
                assert job is not None
                assert job.is_test is True, f"Expected is_test=True for synthetic URL, got {job.is_test}"
