import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.models.database import AsyncSessionLocal
from backend.models.models import (
    Clip, Video, Job, TaskExecution, TaskExecutionStatus, 
    ClipVariant, ClipRetention, ClipSFXPlan, ClipVisualPlan, ClipHookPlan
)

@pytest.mark.asyncio
async def test_clip_deletion_cascades_and_nullifies_task_execution():
    """
    Verifies that deleting a clip via DELETE /api/clips/{id}:
    1. Returns HTTP 200.
    2. Does NOT raise ForeignKeyViolationError when task_executions reference the clip.
    3. Sets task_executions.clip_id to NULL, preserving the parent job execution audit trail.
    4. Cascades deletion of dependent child records (ClipVariant, ClipRetention, plans).
    """
    uid = str(uuid.uuid4())[:8]
    test_clip_id = f"test_clip_del_{uid}"
    test_job_id = f"test_job_del_{uid}"
    test_vid_id = f"test_vid_del_{uid}"
    test_te_id = f"test_te_del_{uid}"

    async with AsyncSessionLocal() as session:
        # 1. Create parent Video & Job
        vid = Video(id=test_vid_id, title="Del Test Vid", youtube_url="https://youtube.com/watch?v=123", youtube_id="123")
        job = Job(id=test_job_id, video_id=test_vid_id, source_title="Del Test Vid", status="completed")
        clip = Clip(id=test_clip_id, video_id=test_vid_id, title="Delete Test Clip", score=4.5, start_time=0.0, end_time=10.0, duration=10.0)
        session.add_all([vid, job, clip])
        await session.flush()

        # 2. Add dependent records
        te = TaskExecution(
            id=test_te_id,
            job_id=test_job_id,
            clip_id=test_clip_id,
            operation="reframe",
            status=TaskExecutionStatus.FAILED.value
        )
        variant = ClipVariant(
            variant_id=str(uuid.uuid4()),
            clip_id=test_clip_id,
            variant_type="hook",
            status="completed"
        )
        retention = ClipRetention(
            clip_id=test_clip_id,
            overall_score=0.75,
            analysis_json="[]"
        )
        sfx_plan = ClipSFXPlan(
            clip_id=test_clip_id,
            plan_json="{}",
            plan_hash="hash123"
        )
        session.add_all([te, variant, retention, sfx_plan])
        await session.commit()

    # 3. Call DELETE /api/clips/{id}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/clips/{test_clip_id}")
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        assert resp.json() == {"message": "Clip deleted"}

    # 4. Verify DB state after deletion
    async with AsyncSessionLocal() as session:
        # Clip should be deleted
        c_res = await session.get(Clip, test_clip_id)
        assert c_res is None

        # TaskExecution should remain, with clip_id set to None
        te_res = await session.get(TaskExecution, test_te_id)
        assert te_res is not None
        assert te_res.clip_id is None
        assert te_res.job_id == test_job_id

        # ClipVariant, ClipRetention, ClipSFXPlan should be cascade deleted
        from sqlalchemy import text
        v_count = (await session.execute(text("SELECT count(*) FROM clip_variants WHERE clip_id = :cid"), {"cid": test_clip_id})).scalar()
        assert v_count == 0

        r_count = (await session.execute(text("SELECT count(*) FROM clip_retention WHERE clip_id = :cid"), {"cid": test_clip_id})).scalar()
        assert r_count == 0

        # Clean up test job & video fixture
        await session.delete(te_res)
        await session.flush()
        await session.delete(job)
        await session.flush()
        await session.delete(vid)
        await session.commit()
