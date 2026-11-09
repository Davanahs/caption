"""
test_manual_video_concurrency_gate.py
======================================
Tests for the 5-Video Concurrent Processing Limit & FIFO Queue Manager.

Verifies:
1. At most 5 manual videos are dispatched concurrently.
2. The 6th+ video is accepted and placed in the FIFO queue with queue position in current_step.
3. Channel automation jobs (channel_id != None) bypass the manual limit.
4. When an active video reaches a terminal state (completed, failed, cancelled), the oldest queued video is automatically dispatched.
5. Remaining queued videos update their queue position.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import select, or_

from backend.models.database import SyncSessionLocal
from backend.models.models import Job, JobStatus
from backend.services.queue_manager import (
    MAX_CONCURRENT_MANUAL_JOBS,
    get_active_manual_jobs_count_sync,
    get_pending_queue_position_sync,
    dispatch_next_queued_manual_jobs_sync,
    format_queue_step,
    build_dispatch_kwargs_from_job,
)


@pytest.fixture(autouse=True)
def clean_test_jobs():
    """Ensure clean test environment before and after each test."""
    def _cleanup():
        with SyncSessionLocal() as session:
            test_job_ids = [
                r[0] for r in session.query(Job.id).filter(
                    or_(
                        Job.is_test == True,
                        Job.id.like("gate-%"),
                        Job.id.like("active-job-%"),
                        Job.id.like("queued-job-%"),
                        Job.id.like("test-%"),
                    )
                ).all()
            ]
            if test_job_ids:
                from backend.models.models import TaskExecution
                session.query(TaskExecution).filter(TaskExecution.job_id.in_(test_job_ids)).delete(synchronize_session=False)
                session.query(Job).filter(Job.id.in_(test_job_ids)).delete(synchronize_session=False)
                session.commit()

    _cleanup()
    yield
    _cleanup()


def test_concurrency_constant():
    """Rule verification: Maximum concurrent manual videos must be exactly 5."""
    assert MAX_CONCURRENT_MANUAL_JOBS == 5


def test_format_queue_step():
    """Verify user-facing queue position text formatting."""
    assert format_queue_step(1) == "Queued (#1 in line - waiting for an active video to finish)"
    assert format_queue_step(3) == "Queued (#3 in line - waiting for an active video to finish)"


def test_active_manual_jobs_count():
    """Verify active manual jobs count accurately includes in-flight statuses and ignores completed/cancelled."""
    with SyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        # Create 2 active manual jobs
        j1 = Job(id=str(uuid.uuid4()), status=JobStatus.DOWNLOADING.value, channel_id=None, is_test=True, created_at=now, updated_at=now)
        j2 = Job(id=str(uuid.uuid4()), status=JobStatus.ANALYZING.value, channel_id=None, is_test=True, created_at=now, updated_at=now)
        # Create 1 channel automation job (must be ignored by manual count)
        j3 = Job(id=str(uuid.uuid4()), status=JobStatus.DOWNLOADING.value, channel_id="ch_auto_99", is_test=True, created_at=now, updated_at=now)
        # Create 1 completed job (must be ignored)
        j4 = Job(id=str(uuid.uuid4()), status=JobStatus.COMPLETED.value, channel_id=None, is_test=True, created_at=now, updated_at=now)
        session.add_all([j1, j2, j3, j4])
        session.commit()

        active = get_active_manual_jobs_count_sync(session)
        assert active == 2, f"Expected 2 active manual jobs, got {active}"


def test_manual_queue_drain_fifo_order():
    """
    Verify that when 5 videos are active, 6th and 7th videos are queued,
    and when capacity opens, they are dequeued in strict FIFO order (oldest first).
    """
    with SyncSessionLocal() as session:
        now = datetime.now(timezone.utc)

        # 1. Fill 5 slots with active manual jobs
        active_jobs = []
        for i in range(5):
            aj = Job(
                id=f"active-job-{i}-{uuid.uuid4().hex[:6]}",
                status=JobStatus.TRANSCRIBING.value,
                channel_id=None,
                is_test=True,
                created_at=now - timedelta(minutes=10 - i),
                updated_at=now,
            )
            active_jobs.append(aj)
        session.add_all(active_jobs)
        session.commit()

        assert get_active_manual_jobs_count_sync(session) == 5

        # 2. Add 2 queued pending jobs (Job 6 created at t-2 min, Job 7 created at t-1 min)
        cfg6 = {"clip_mode": "ai_highlights", "dispatch_kwargs": {"youtube_url": "https://youtu.be/vid6"}}
        j6 = Job(
            id=f"queued-job-6-{uuid.uuid4().hex[:6]}",
            status=JobStatus.PENDING.value,
            celery_task_id=None,
            source_url="https://youtu.be/vid6",
            config=json.dumps(cfg6),
            channel_id=None,
            is_test=True,
            created_at=now - timedelta(minutes=2),
            updated_at=now,
            current_step=format_queue_step(1),
        )
        cfg7 = {"clip_mode": "ai_highlights", "dispatch_kwargs": {"youtube_url": "https://youtu.be/vid7"}}
        j7 = Job(
            id=f"queued-job-7-{uuid.uuid4().hex[:6]}",
            status=JobStatus.PENDING.value,
            celery_task_id=None,
            source_url="https://youtu.be/vid7",
            config=json.dumps(cfg7),
            channel_id=None,
            is_test=True,
            created_at=now - timedelta(minutes=1),
            updated_at=now,
            current_step=format_queue_step(2),
        )
        session.add_all([j6, j7])
        session.commit()

        # Check queue positions
        assert get_pending_queue_position_sync(session, j6.id) == 1
        assert get_pending_queue_position_sync(session, j7.id) == 2

        # 3. Simulate capacity full: drain attempts dispatch 0 jobs
        with patch("backend.services.queue_manager.dispatch_celery_job") as mock_dispatch:
            dispatched = dispatch_next_queued_manual_jobs_sync(session)
            assert dispatched == 0
            mock_dispatch.assert_not_called()

        # 4. Now simulate 1 active job completing (freeing 1 slot)
        active_jobs[0].status = JobStatus.COMPLETED.value
        session.commit()
        assert get_active_manual_jobs_count_sync(session) == 4

        # 5. Trigger queue drain: Job 6 (older) must be dispatched first
        with patch("backend.services.queue_manager.dispatch_celery_job", return_value="celery-task-vid6") as mock_dispatch:
            dispatched = dispatch_next_queued_manual_jobs_sync(session)
            assert dispatched == 1
            mock_dispatch.assert_called_once()
            called_job_id, called_kwargs = mock_dispatch.call_args[0]
            assert called_job_id == j6.id
            assert called_kwargs["youtube_url"] == "https://youtu.be/vid6"

        # Verify Job 6 is now dispatched and Job 7 moves up to #1 in line
        session.refresh(j6)
        session.refresh(j7)
        assert j6.celery_task_id == "celery-task-vid6"
        assert j6.current_step == "Starting pipeline..."
        assert j7.current_step == format_queue_step(1)
        assert j7.celery_task_id is None

        # 6. Now simulate a second job failing (freeing another slot)
        active_jobs[1].status = JobStatus.FAILED.value
        session.commit()

        # 7. Trigger queue drain: Job 7 must now be claimed and dispatched
        with patch("backend.services.queue_manager.dispatch_celery_job", return_value="celery-task-vid7") as mock_dispatch:
            dispatched = dispatch_next_queued_manual_jobs_sync(session)
            assert dispatched == 1
            mock_dispatch.assert_called_once()
            called_job_id, called_kwargs = mock_dispatch.call_args[0]
            assert called_job_id == j7.id

        session.refresh(j7)
        assert j7.celery_task_id == "celery-task-vid7"
        assert j7.current_step == "Starting pipeline..."


def test_build_dispatch_kwargs_from_config():
    """Verify build_dispatch_kwargs_from_job extracts all needed pipeline parameters."""
    cfg = {
        "clip_mode": "ai_highlights",
        "num_clips": 3,
        "reframe_mode": "smart",
        "hook_title": "Best Clip",
        "target_duration": 45,
        "dispatch_kwargs": {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "num_clips": 3,
            "reframe_mode": "smart",
        }
    }
    dummy_job = Job(id="test-job-build", source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", config=json.dumps(cfg), channel_id=None)
    kwargs = build_dispatch_kwargs_from_job(dummy_job)
    assert kwargs["job_id"] == "test-job-build"
    assert kwargs["youtube_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert kwargs["num_clips"] == 3
    assert kwargs["reframe_mode"] == "smart"


@pytest.mark.asyncio
async def test_api_video_url_concurrency_gate():
    """
    Test POST /api/videos/url endpoint directly:
    1. First 5 videos return queued: False and are dispatched.
    2. 6th video returns queued: True, queue_position: 1, and 'Queued (#1 in line - waiting for an active video to finish)'.
    3. 7th video returns queued: True, queue_position: 2, and 'Queued (#2 in line - waiting for an active video to finish)'.
    """
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.services.queue_manager.dispatch_celery_job", return_value="mock-celery-id"):
            # Step 1: Pre-populate 4 active jobs in DB
            now = datetime.now(timezone.utc)
            with SyncSessionLocal() as session:
                for i in range(4):
                    session.add(Job(
                        id=f"gate-active-{i}-{uuid.uuid4().hex[:6]}",
                        status=JobStatus.DOWNLOADING.value,
                        channel_id=None,
                        is_test=True,
                        created_at=now,
                        updated_at=now,
                    ))
                session.commit()

            # Video 5: should fill the 5th slot and be dispatched (queued=False)
            resp5 = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "is_test": "true"})
            assert resp5.status_code == 200
            data5 = resp5.json()
            assert data5["queued"] is False
            assert data5["message"] == "Processing started"

            # Video 6: should be placed in queue (#1 in line)
            resp6 = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "is_test": "true"})
            assert resp6.status_code == 200
            data6 = resp6.json()
            assert data6["queued"] is True
            assert data6["queue_position"] == 1
            assert "Queued (#1 in line" in data6["message"]

            # Video 7: should be placed in queue (#2 in line)
            resp7 = await client.post("/api/videos/url", data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "is_test": "true"})
            assert resp7.status_code == 200
            data7 = resp7.json()
            assert data7["queued"] is True
            assert data7["queue_position"] == 2
            assert "Queued (#2 in line" in data7["message"]

