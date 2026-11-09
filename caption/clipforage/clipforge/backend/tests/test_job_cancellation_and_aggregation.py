import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.models.database import AsyncSessionLocal, SyncSessionLocal
from backend.models.models import Job, Video, Clip, TaskExecution, TaskExecutionStatus, JobStatus, VideoProcessingStatus
from backend.tasks.orchestration import handle_pipeline_failure_task
import uuid
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_job_cancellation_preserves_fk_and_transitions_state():
    """
    Test that cancelling a job via DELETE /api/jobs/{id}:
    1. Returns HTTP 200.
    2. Does NOT raise ForeignKeyViolationError when task_executions exist.
    3. Transitions job.status to 'failed' with 'Cancelled by user'.
    4. Updates associated Video.processing_status if in flight.
    5. Excludes the cancelled job from /api/jobs/active.
    """
    test_id = str(uuid.uuid4())
    job_id = f"job_test_cancel_{test_id[:8]}"
    vid_id = f"vid_test_cancel_{test_id[:8]}"

    # Setup database fixture
    async with AsyncSessionLocal() as session:
        video = Video(
            id=vid_id,
            title="Cancel Test Video",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            youtube_id="dQw4w9WgXcQ",
            processing_status=VideoProcessingStatus.PROCESSING.value
        )
        session.add(video)

        job = Job(
            id=job_id,
            video_id=vid_id,
            source_title="Cancel Test Video",
            status=JobStatus.SELECTING.value,
            progress=80,
            current_step="Selecting best clips..."
        )
        session.add(job)

        # Add a referencing TaskExecution row (simulating the FK condition)
        te = TaskExecution(
            id=str(uuid.uuid4()),
            job_id=job_id,
            operation="reframe",
            status=TaskExecutionStatus.RUNNING.value,
            task_id="mock_celery_task_123"
        )
        session.add(te)
        await session.commit()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Assert job is initially in /api/jobs/active
            resp_active = await ac.get("/api/jobs/active")
            assert resp_active.status_code == 200
            active_ids = [j["id"] for j in resp_active.json()]
            assert job_id in active_ids

            # 2. Issue cancellation request
            resp_cancel = await ac.delete(f"/api/jobs/{job_id}")
            assert resp_cancel.status_code == 200
            data = resp_cancel.json()
            assert data["job_id"] == job_id
            assert data["status"] == "cancelled"

            # 3. Assert job is now excluded from /api/jobs/active
            resp_active_after = await ac.get("/api/jobs/active")
            assert resp_active_after.status_code == 200
            active_ids_after = [j["id"] for j in resp_active_after.json()]
            assert job_id not in active_ids_after

        # 4. Verify DB state directly
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            j_res = await session.execute(select(Job).where(Job.id == job_id))
            updated_job = j_res.scalar_one_or_none()
            assert updated_job is not None
            assert updated_job.status == JobStatus.CANCELLED.value
            assert updated_job.current_step == "Cancelled"
            assert "Cancelled by user" in updated_job.error_message

            # Verify TaskExecution was marked failed and still exists
            te_res = await session.execute(select(TaskExecution).where(TaskExecution.job_id == job_id))
            updated_te = te_res.scalar_one_or_none()
            assert updated_te is not None
            assert updated_te.status == TaskExecutionStatus.FAILED.value
            assert updated_te.failure_reason == "Cancelled by user"

            # Verify Video processing status updated
            v_res = await session.execute(select(Video).where(Video.id == vid_id))
            updated_video = v_res.scalar_one_or_none()
            assert updated_video.processing_status == VideoProcessingStatus.CANCELLED.value

    finally:
        # Cleanup test fixture
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(TaskExecution).where(TaskExecution.job_id == job_id))
            await session.execute(delete(Job).where(Job.id == job_id))
            await session.execute(delete(Video).where(Video.id == vid_id))
            await session.commit()
        from backend.models.database import engine
        await engine.dispose()


def test_cancelled_job_blocks_stale_callbacks_and_workers():
    """
    Test that once a Job is cancelled:
    1. update_job_sync refuses to overwrite 'cancelled' status.
    2. job_completion_aggregation_task skips overwriting 'cancelled'.
    3. reframe_task and render_task abort immediately without producing artifacts.
    """
    from backend.models.db_sync import update_job_sync
    from backend.tasks.orchestration import job_completion_aggregation_task
    from backend.tasks.clip_tasks import reframe_task, render_task
    
    test_id = str(uuid.uuid4())
    job_id = f"job_cancel_prot_{test_id[:8]}"
    vid_id = f"vid_cancel_prot_{test_id[:8]}"
    clip_id = f"clip_cancel_prot_{test_id[:8]}"

    with SyncSessionLocal() as session:
        video = Video(
            id=vid_id,
            title="Cancel Protection Video",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            youtube_id="dQw4w9WgXcQ"
        )
        session.add(video)
        job = Job(
            id=job_id,
            video_id=vid_id,
            source_title="Cancel Protection Video",
            status=JobStatus.CANCELLED.value,
            progress=50,
            current_step="Cancelled",
            error_message="Cancelled by user"
        )
        session.add(job)
        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="Cancel Protection Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            status="pending"
        )
        session.add(clip)
        session.commit()

    try:
        # 1. Stale update_job_sync attempt
        update_job_sync(job_id, "clipping_in_progress", 80, "Selecting best clips...")
        with SyncSessionLocal() as session:
            j = session.query(Job).filter_by(id=job_id).first()
            assert j.status == JobStatus.CANCELLED.value
            assert j.current_step == "Cancelled"

        # 2. Stale aggregation callback attempt
        job_completion_aggregation_task([], job_id=job_id)
        with SyncSessionLocal() as session:
            j = session.query(Job).filter_by(id=job_id).first()
            assert j.status == JobStatus.CANCELLED.value
            assert j.current_step == "Cancelled"

        # 3. reframe_task execution aborts cooperatively
        res_reframe = reframe_task.apply(args=[clip_id], kwargs={"job_id": job_id}).result
        assert res_reframe.get("status") == "cancelled"

        # 4. render_task execution aborts cooperatively
        res_render = render_task.apply(args=[{"clip_id": clip_id, "job_id": job_id, "video_id": vid_id}]).result
        assert res_render.get("status") == "cancelled"

    finally:
        with SyncSessionLocal() as session:
            session.query(Clip).filter(Clip.id == clip_id).delete()
            session.query(Job).filter(Job.id == job_id).delete()
            session.query(Video).filter(Video.id == vid_id).delete()
            session.commit()


def test_handle_pipeline_failure_aggregates_terminal_job():
    """
    Test that handle_pipeline_failure_task aggregates the overall job status
    when all clips for the job reach terminal state (preventing stuck selecting/80%).
    """
    test_id = str(uuid.uuid4())
    job_id = f"job_test_agg_{test_id[:8]}"
    vid_id = f"vid_test_agg_{test_id[:8]}"
    clip1_id = f"clip1_{test_id[:8]}"
    clip2_id = f"clip2_{test_id[:8]}"

    with SyncSessionLocal() as session:
        video = Video(
            id=vid_id,
            title="Aggregation Test Video",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            youtube_id="dQw4w9WgXcQ"
        )
        session.add(video)

        job = Job(
            id=job_id,
            video_id=vid_id,
            source_title="Aggregation Test Video",
            status=JobStatus.SELECTING.value,
            progress=80,
            current_step="Selecting best clips..."
        )
        session.add(job)

        # Clip 1 already completed
        c1 = Clip(
            id=clip1_id,
            video_id=vid_id,
            title="Clip 1",
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            status="completed"
        )
        # Clip 2 currently reframing
        c2 = Clip(
            id=clip2_id,
            video_id=vid_id,
            title="Clip 2",
            start_time=15.0,
            end_time=30.0,
            duration=15.0,
            status="reframing"
        )
        session.add(c1)
        session.add(c2)
        session.commit()

    try:
        # Mock request object for Celery task callback
        class MockRequest:
            id = "mock_task_id_456"

        exc = RuntimeError("Storage key missing from physical backend")
        handle_pipeline_failure_task(
            request=MockRequest(),
            exc=exc,
            traceback="mock_traceback",
            job_id=job_id,
            clip_id=clip2_id,
            stage="clip_workflow"
        )

        # Verify job and clip statuses in DB
        with SyncSessionLocal() as session:
            j = session.query(Job).filter_by(id=job_id).first()
            assert j is not None
            # Clip 1 succeeded, Clip 2 failed -> job must be completed_with_failures, progress 100
            assert j.status == "completed_with_failures"
            assert j.progress == 100
            assert "1/2 clips failed" in j.current_step

            c2_db = session.query(Clip).filter_by(id=clip2_id).first()
            assert c2_db.status == "failed"

    finally:
        with SyncSessionLocal() as session:
            session.query(Clip).filter(Clip.video_id == vid_id).delete()
            session.query(Job).filter(Job.id == job_id).delete()
            session.query(Video).filter(Video.id == vid_id).delete()
            session.commit()
