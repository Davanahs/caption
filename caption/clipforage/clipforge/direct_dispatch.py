"""
Directly dispatch Celery tasks for jobs stuck with celery_task_id=NULL.
Bypasses the HTTP API — talks to Redis directly via Celery.
"""
import sys, os
sys.path.insert(0, os.path.abspath("."))

from backend.models.database import SyncSessionLocal
from backend.models.models import Job
from backend.celery_app import celery_app
from backend.tasks.process_video import process_video_task

try:
    with SyncSessionLocal() as session:
        jobs = session.query(Job).filter(
            Job.status.in_(['pending', 'failed', 'transcribing']),
            (Job.celery_task_id == None) | (Job.celery_task_id == Job.id)
        ).all()

        print(f"Jobs to dispatch: {len(jobs)}")

        for job in jobs:
            print(f"  Dispatching job {job.id[:8]}...")
            result = process_video_task.apply_async(
                kwargs={
                    "job_id": job.id,
                    "youtube_url": job.source_url,
                    "channel_id": None, # channel_id isn't guaranteed
                    "clip_mode": "auto",
                },
                task_id=job.id,
            )
            job.status = 'pending'
            job.celery_task_id = result.id
            session.commit()
            print(f"    -> Celery task id: {result.id}")

    print("Done.")
except Exception as e:
    print(f"Failed to dispatch: {e}")
