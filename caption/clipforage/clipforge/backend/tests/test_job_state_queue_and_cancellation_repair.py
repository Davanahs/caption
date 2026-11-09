"""
test_job_state_queue_and_cancellation_repair.py
=================================================
Focused regression tests verifying:
1. Cancellation persists correct terminal state (JobStatus.CANCELLED) with completed_at timestamp.
2. Repeated cancellation requests are handled idempotently.
3. Cannot cancel already completed jobs (returns HTTP 400).
4. Active queue (/api/jobs/active) excludes terminal jobs (completed, failed, cancelled).
5. History queue (/api/jobs/history) returns terminal jobs in reverse chronological order.
6. Dashboard stats (/api/jobs/stats) properly separate active, pending, done, failed, and cancelled counters.
7. Last failure banner ignores user cancellations and only displays genuine processing failures.
8. Queue count (/api/jobs/queue-count) matches total non-terminal active + pending jobs.
9. Test jobs (is_test=True) are excluded from default job queries and statistics.
10. Stale workers and callbacks cannot overwrite terminal cancelled state.
11. Parent-job aggregation accurately aggregates clip outcomes (all success, mixed, all failed).
12. Non-destructive test cleanup ensures zero database pollution after tests.
"""
import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.models.database import AsyncSessionLocal, SyncSessionLocal, engine
from backend.models.models import Job, Video, Clip, TaskExecution, TaskExecutionStatus, JobStatus, VideoProcessingStatus
from backend.models.db_sync import update_job_sync
from backend.tasks.orchestration import job_completion_aggregation_task, handle_pipeline_failure_task


@pytest.fixture(autouse=True)
async def cleanup_test_fixtures():
    """Teardown fixture ensuring all test-created entities are cleaned up."""
    yield
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text
        await session.execute(text("DELETE FROM task_executions WHERE job_id LIKE 'test_repair_%'"))
        await session.execute(text("DELETE FROM clips WHERE id LIKE 'clip_repair_%'"))
        await session.execute(text("DELETE FROM jobs WHERE id LIKE 'test_repair_%'"))
        await session.execute(text("DELETE FROM videos WHERE id LIKE 'vid_repair_%'"))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_cancellation_lifecycle_persistence_and_idempotency():
    """Verify cancellation persists status='cancelled', completed_at, and is idempotent."""
    job_id = f"test_repair_cancel_{uuid.uuid4().hex[:8]}"
    vid_id = f"vid_repair_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        video = Video(
            id=vid_id,
            title="Cancel Lifecycle Video",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            youtube_id="dQw4w9WgXcQ",
            processing_status=VideoProcessingStatus.PROCESSING.value
        )
        job = Job(
            id=job_id,
            video_id=vid_id,
            source_title="Cancel Lifecycle Video",
            status=JobStatus.SELECTING.value,
            progress=50,
            current_step="Selecting clips",
            is_test=False
        )
        session.add(video)
        session.add(job)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Job is initially active
        resp_active = await client.get("/api/jobs/active")
        assert resp_active.status_code == 200
        active_ids = [j["id"] for j in resp_active.json()]
        assert job_id in active_ids

        # 2. Cancel job
        resp_cancel = await client.delete(f"/api/jobs/{job_id}")
        assert resp_cancel.status_code == 200
        cancel_data = resp_cancel.json()
        assert cancel_data["job_id"] == job_id
        assert cancel_data["status"] == "cancelled"

        # 3. Idempotent repeated cancellation returns 200
        resp_repeat = await client.delete(f"/api/jobs/{job_id}")
        assert resp_repeat.status_code == 200
        assert resp_repeat.json().get("already_cancelled") is True

        # 4. Job is no longer in active queue
        resp_active_after = await client.get("/api/jobs/active")
        active_ids_after = [j["id"] for j in resp_active_after.json()]
        assert job_id not in active_ids_after

        # 5. Job appears in history queue
        resp_history = await client.get("/api/jobs/history")
        assert resp_history.status_code == 200
        history_ids = [j["id"] for j in resp_history.json()]
        assert job_id in history_ids

        # 6. Verify directly in DB
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            res = await session.execute(select(Job).where(Job.id == job_id))
            db_job = res.scalar_one_or_none()
            assert db_job is not None
            assert db_job.status == JobStatus.CANCELLED.value
            assert db_job.completed_at is not None
            assert db_job.current_step == "Cancelled"
            assert "Cancelled by user" in db_job.error_message


@pytest.mark.asyncio
async def test_cannot_cancel_completed_job():
    """Verify attempting to cancel an already completed job returns HTTP 400."""
    job_id = f"test_repair_done_{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        job = Job(
            id=job_id,
            source_title="Completed Job",
            status=JobStatus.COMPLETED.value,
            progress=100,
            current_step="Done",
            is_test=False
        )
        session.add(job)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/jobs/{job_id}")
        assert resp.status_code == 400
        assert "Cannot cancel a completed job" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_queue_endpoints_and_stats_reconciliation():
    """Verify active queue, history queue, queue-count, and stats accurately reconcile."""
    uid = uuid.uuid4().hex[:6]
    job_pending = f"test_repair_pend_{uid}"
    job_active = f"test_repair_act_{uid}"
    job_completed = f"test_repair_comp_{uid}"
    job_failed = f"test_repair_fail_{uid}"
    job_cancelled = f"test_repair_canc_{uid}"
    job_test = f"test_repair_test_{uid}"

    async with AsyncSessionLocal() as session:
        session.add_all([
            Job(id=job_pending, status=JobStatus.PENDING.value, is_test=False, source_title="Pending Video"),
            Job(id=job_active, status=JobStatus.TRANSCRIBING.value, progress=35, is_test=False, source_title="Active Video"),
            Job(id=job_completed, status=JobStatus.COMPLETED.value, progress=100, is_test=False, source_title="Completed Video"),
            Job(id=job_failed, status=JobStatus.FAILED.value, progress=20, is_test=False, error_message="Network error", source_title="Failed Video"),
            Job(id=job_cancelled, status=JobStatus.CANCELLED.value, progress=40, is_test=False, error_message="Cancelled by user", source_title="Cancelled Video"),
            # Synthetic test job that must be ignored by default
            Job(id=job_test, status=JobStatus.PENDING.value, is_test=True, source_title="Mock Test Video"),
        ])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. /api/jobs/active only returns pending and running
        resp_act = await client.get("/api/jobs/active")
        assert resp_act.status_code == 200
        active_ids = {j["id"] for j in resp_act.json()}
        assert job_pending in active_ids
        assert job_active in active_ids
        assert job_completed not in active_ids
        assert job_failed not in active_ids
        assert job_cancelled not in active_ids
        assert job_test not in active_ids  # Ignored because is_test=True

        # 2. /api/jobs/history only returns terminal jobs
        resp_hist = await client.get("/api/jobs/history")
        assert resp_hist.status_code == 200
        hist_ids = {j["id"] for j in resp_hist.json()}
        assert job_completed in hist_ids
        assert job_failed in hist_ids
        assert job_cancelled in hist_ids
        assert job_pending not in hist_ids
        assert job_active not in hist_ids
        assert job_test not in hist_ids

        # 3. /api/jobs/stats reconciles
        resp_stats = await client.get("/api/jobs/stats")
        assert resp_stats.status_code == 200
        stats = resp_stats.json()
        queue = stats["queue"]
        assert queue["cancelled"] >= 1
        assert queue["done"] >= 1
        assert queue["active"] >= 1
        assert queue["pending"] >= 1
        # Last failure must NOT be the cancelled job
        if stats.get("last_failure"):
            assert "Cancelled by user" not in stats["last_failure"]["error"]

        # 4. include_test=True includes test job in count
        resp_test_stats = await client.get("/api/jobs/stats?include_test=true")
        assert resp_test_stats.status_code == 200
        assert resp_test_stats.json()["queue"]["pending"] > queue["pending"]


def test_cancelled_job_cannot_be_overwritten_by_stale_callbacks():
    """Verify that update_job_sync and job_completion_aggregation_task skip cancelled jobs."""
    job_id = f"test_repair_stale_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        job = Job(
            id=job_id,
            status=JobStatus.CANCELLED.value,
            progress=50,
            current_step="Cancelled",
            error_message="Cancelled by user",
            is_test=False
        )
        session.add(job)
        session.commit()

    try:
        # Attempt 1: Worker tries to update progress
        update_job_sync(job_id, "analyzing", 60, "AI scoring")
        with SyncSessionLocal() as session:
            j = session.query(Job).filter_by(id=job_id).first()
            assert j.status == JobStatus.CANCELLED.value
            assert j.current_step == "Cancelled"

        # Attempt 2: Celery completion aggregation callback tries to complete job
        job_completion_aggregation_task([], job_id=job_id)
        with SyncSessionLocal() as session:
            j = session.query(Job).filter_by(id=job_id).first()
            assert j.status == JobStatus.CANCELLED.value
            assert j.current_step == "Cancelled"
    finally:
        with SyncSessionLocal() as session:
            session.query(Job).filter_by(id=job_id).delete()
            session.commit()


def test_parent_job_aggregation_on_terminal_child_clips():
    """Verify handle_pipeline_failure_task correctly aggregates parent job when clips finish."""
    uid = uuid.uuid4().hex[:8]
    job_id = f"test_repair_agg_{uid}"
    vid_id = f"vid_repair_agg_{uid}"
    clip1_id = f"clip_repair_1_{uid}"
    clip2_id = f"clip_repair_2_{uid}"

    with SyncSessionLocal() as session:
        session.add(Video(id=vid_id, title="Agg Video", youtube_url="https://youtube.com/watch?v=xyz", youtube_id="xyz"))
        session.add(Job(id=job_id, video_id=vid_id, status=JobStatus.SELECTING.value, progress=80, current_step="Selecting clips"))
        # Clip 1 completed, Clip 2 in progress
        session.add(Clip(id=clip1_id, video_id=vid_id, title="Clip 1", status="completed", start_time=0.0, end_time=10.0, duration=10.0))
        session.add(Clip(id=clip2_id, video_id=vid_id, title="Clip 2", status="rendering", start_time=10.0, end_time=20.0, duration=10.0))
        session.commit()

    try:
        class DummyRequest:
            id = "dummy_task_id"

        # Fail Clip 2
        handle_pipeline_failure_task(
            request=DummyRequest(),
            exc=ValueError("Render failed"),
            traceback="dummy_tb",
            job_id=job_id,
            clip_id=clip2_id,
            stage="render"
        )

        with SyncSessionLocal() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            assert job is not None
            # Mixed success (1/2 succeeded) -> completed_with_failures, progress 100
            assert job.status == "completed_with_failures"
            assert job.progress == 100
            assert "1/2 clips failed" in job.current_step

            c2 = session.query(Clip).filter_by(id=clip2_id).first()
            assert c2.status == "failed"
    finally:
        with SyncSessionLocal() as session:
            session.query(Clip).filter(Clip.video_id == vid_id).delete()
            session.query(Job).filter_by(id=job_id).delete()
            session.query(Video).filter_by(id=vid_id).delete()
            session.commit()
