import asyncio
from sqlalchemy import select
from backend.models.database import AsyncSessionLocal
from backend.models.models import Clip
from backend.services.broll_planner import BrollPlanner
from backend.tasks.clip_tasks import apply_broll_task
import time

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Clip).order_by(Clip.created_at.desc()).limit(1))
        clip = res.scalar_one_or_none()
        
    if not clip:
        print("No clips in DB. Cannot test B-roll.")
        return
        
    print(f"Testing Phase 12 B-roll on clip: {clip.id}")
    
    # 1. Generate B-roll Plan
    planner = BrollPlanner()
    transcript = clip.transcript_segment or clip.description or "This is a test of a shocking revelation that will blow your mind!"
    
    async with AsyncSessionLocal() as db:
        try:
            plan = await planner.create_plan(
                db=db,
                clip_id=clip.id,
                transcript=[{"word": word, "start": i*1.5, "end": (i+1)*1.5} for i, word in enumerate(transcript.split())],
                clip_start_time=0.0,
                clip_end_time=float(clip.duration) if clip.duration else 10.0
            )
            print("Successfully generated B-roll Plan:")
            print(plan.model_dump_json(indent=2))
        except Exception as e:
            print(f"Error generating B-roll plan: {e}")
            return
            
    # 2. Execute B-roll apply task
    # Insert a dummy job for the task execution
    from backend.models.models import Job
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Job).filter_by(id='unknown'))
        job = res.scalar_one_or_none()
        if not job:
            job = Job(id='unknown', status='completed')
            db.add(job)
            await db.commit()

    # To avoid asyncio.run() nested error, we will return the args and run it outside
    return clip.id, plan.model_dump(), 'unknown'

if __name__ == "__main__":
    clip_id, plan_dump, job_id = asyncio.run(main())
    
    # Normally this is an async Celery task, but we call the function directly
    # Note: apply_broll_task is bound, so we call it via apply
    result = apply_broll_task.apply(kwargs={"clip_id": clip_id, "broll_plan_dict": plan_dump})
    
    print(f"Task result: {result.result}")
    
    if result.successful():
        print("SUCCESS: B-roll applied.")
        from backend.models.database import SyncSessionLocal
        from backend.models.models import ClipVariant
        with SyncSessionLocal() as session:
            variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="broll").order_by(ClipVariant.created_at.desc()).first()
            if variant:
                print(f"Created ClipVariant in DB: {variant.id} with status {variant.status}")
                print(f"Configuration Hash: {variant.configuration_hash}")
    else:
        print(f"FAILED: {result.result}")
        if result.traceback:
            print(result.traceback)
