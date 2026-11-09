"""
test_phase_1_2_execution_and_failure_handling.py
==================================================
Regression tests for Phase 1.2:
1. Controlled worker failure handling via handle_pipeline_failure_task.
2. Celery dispatch failure handling in resolve_video_decision_sync (prevents stuck pending jobs).
3. Parent/child clip aggregation (completed, completed_with_failures, failed).
4. Stale TaskExecution recovery via stale_recovery_task.
5. Isolated test record cleanup.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from backend.models.database import SyncSessionLocal, AsyncSessionLocal
from backend.models.models import (
    Job, Video, Clip, TaskExecution, TaskExecutionStatus, JobStatus,
    Channel, VideoDecision, VideoDecisionStatus
)
from backend.models.db_sync import update_job_sync
from backend.tasks.orchestration import (
    handle_pipeline_failure_task,
    job_completion_aggregation_task,
    stale_recovery_task,
    resolve_video_decision_sync
)

@pytest.fixture(autouse=True)
def cleanup_phase12_test_records():
    """Teardown fixture ensuring all test records are wiped after every test."""
    yield
    with SyncSessionLocal() as session:
        session.query(TaskExecution).filter(TaskExecution.job_id.like("test_p12_%")).delete(synchronize_session=False)
        session.query(Clip).filter(Clip.id.like("clip_p12_%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like("test_p12_%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like("vid_p12_%")).delete(synchronize_session=False)
        session.query(VideoDecision).filter(VideoDecision.id.like("dec_p12_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("ch_p12_%")).delete(synchronize_session=False)
        session.commit()


def test_controlled_worker_failure_handling():
    """Verify handle_pipeline_failure_task transitions job to failed with error message and completed_at."""
    job_id = f"test_p12_fail_{uuid.uuid4().hex[:8]}"
    
    with SyncSessionLocal() as session:
        job = Job(
            id=job_id,
            status=JobStatus.DOWNLOADING.value,
            progress=10,
            current_step="Downloading video...",
            is_test=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(job)
        session.commit()

    class MockRequest:
        id = f"task_{uuid.uuid4().hex[:8]}"

    # Invoke failure callback directly as Celery does on error
    exc = RuntimeError("Simulated worker transcoding failure")
    handle_pipeline_failure_task(MockRequest(), exc, None, job_id=job_id, stage="transcoding")

    with SyncSessionLocal() as session:
        updated_job = session.query(Job).filter_by(id=job_id).first()
        assert updated_job.status == JobStatus.FAILED.value
        assert updated_job.current_step == "Failed at transcoding"
        assert "RuntimeError" in updated_job.error_message
        assert "Simulated worker transcoding failure" in updated_job.error_message
        assert updated_job.completed_at is not None


def test_dispatch_failure_marks_job_as_failed():
    """Verify that if apply_async raises an exception, the committed Job is marked failed instead of stuck pending."""
    ch_id = f"ch_p12_disp_{uuid.uuid4().hex[:6]}"
    dec_id = f"dec_p12_disp_{uuid.uuid4().hex[:6]}"
    yt_id = f"yt_p12_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        channel = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_name="Phase 1.2 Dispatch Channel",
            channel_url="https://youtube.com/@phase12_disp",
            is_active=True,
            is_test=True,
            processing_profile={"clips_count": 1, "reframe_mode": "blur"}
        )
        session.add(channel)

        now = datetime.now(timezone.utc)
        decision = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id=yt_id,
            video_title="Dispatch Failure Test Video",
            youtube_url=f"https://www.youtube.com/watch?v={yt_id}",
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=now,
            channel_profile_snapshot={"clips_count": 1, "reframe_mode": "blur"}
        )
        session.add(decision)
        session.commit()

    # Simulate Celery broker connection error on apply_async
    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
        mock_apply.side_effect = ConnectionError("Redis broker connection refused")

        res = resolve_video_decision_sync(decision_id=dec_id, action="apply_defaults")
        job_id = res.get("job_id")
        assert job_id is not None

    # Verify that the job was immediately marked failed in the database
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        assert job is not None
        assert job.status == JobStatus.FAILED.value
        assert job.current_step == "Dispatch Error"
        assert "Redis broker connection refused" in (job.error_message or "")


def test_parent_child_clip_aggregation_partial_failure():
    """Verify that when 1 clip succeeds and 1 clip fails, the job aggregates to completed_with_failures."""
    job_id = f"test_p12_agg_{uuid.uuid4().hex[:8]}"
    vid_id = f"vid_p12_agg_{uuid.uuid4().hex[:8]}"
    clip1_id = f"clip_p12_c1_{uuid.uuid4().hex[:6]}"
    clip2_id = f"clip_p12_c2_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        vid = Video(id=vid_id, title="Agg Test Video", duration=40.0)
        session.add(vid)

        job = Job(
            id=job_id,
            video_id=vid_id,
            status=JobStatus.SELECTING.value,
            progress=80,
            current_step="Selecting best clips...",
            is_test=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(job)

        c1 = Clip(id=clip1_id, video_id=vid_id, start_time=0.0, end_time=15.0, duration=15.0, status="completed")
        c2 = Clip(id=clip2_id, video_id=vid_id, start_time=15.0, end_time=30.0, duration=15.0, status="failed")
        session.add_all([c1, c2])
        session.commit()

    # Run completion aggregation task
    job_completion_aggregation_task(results=[], job_id=job_id)

    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        assert job.status == JobStatus.COMPLETED_WITH_FAILURES.value
        assert job.progress == 100
        assert "1/2 clips failed" in job.current_step
        assert job.completed_at is not None


def test_parent_child_clip_aggregation_all_failed():
    """Verify that when all clips fail, the job aggregates to failed."""
    job_id = f"test_p12_allfail_{uuid.uuid4().hex[:8]}"
    vid_id = f"vid_p12_allfail_{uuid.uuid4().hex[:8]}"
    clip1_id = f"clip_p12_af1_{uuid.uuid4().hex[:6]}"
    clip2_id = f"clip_p12_af2_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        vid = Video(id=vid_id, title="All Fail Test Video", duration=40.0)
        session.add(vid)

        job = Job(
            id=job_id,
            video_id=vid_id,
            status=JobStatus.SELECTING.value,
            progress=80,
            current_step="Selecting best clips...",
            is_test=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(job)

        c1 = Clip(id=clip1_id, video_id=vid_id, start_time=0.0, end_time=15.0, duration=15.0, status="failed")
        c2 = Clip(id=clip2_id, video_id=vid_id, start_time=15.0, end_time=30.0, duration=15.0, status="failed")
        session.add_all([c1, c2])
        session.commit()

    # Run completion aggregation task
    job_completion_aggregation_task(results=[], job_id=job_id)

    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        assert job.status == JobStatus.FAILED.value
        assert job.progress == 100
        assert "All 2 clips failed" in job.current_step
        assert job.completed_at is not None


def test_stale_recovery_task_transitions_dead_tasks():
    """Verify that stale_recovery_task marks RUNNING executions without recent heartbeat as FAILED."""
    job_id = f"test_p12_stale_{uuid.uuid4().hex[:8]}"
    exec_id = f"test_p12_exec_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        job = Job(id=job_id, status=JobStatus.ANALYZING.value, progress=40, is_test=True)
        session.add(job)

        # Heartbeat 15 minutes ago (> 10 minute threshold)
        fifteen_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
        stale_exec = TaskExecution(
            id=exec_id,
            job_id=job_id,
            task_id="celery_task_12345",
            operation="render",
            status=TaskExecutionStatus.RUNNING.value,
            last_heartbeat=fifteen_mins_ago
        )
        session.add(stale_exec)
        session.commit()

    # Run stale execution recovery task
    stale_recovery_task()

    with SyncSessionLocal() as session:
        rec = session.query(TaskExecution).filter_by(id=exec_id).first()
        assert rec is not None
        assert rec.status == TaskExecutionStatus.FAILED.value
        assert "Stale execution timeout (no heartbeat)" in rec.failure_reason
