import sys
import os
import time

# Ensure we can import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models.database import SyncSessionLocal
from backend.models.models import Job, Video, Clip
from backend.tasks.orchestration import start_video_processing_task

def main():
    with SyncSessionLocal() as session:
        # Create dummy job
        job = Job(source_url="https://www.youtube.com/watch?v=TEST_CRASH", status="pending")
        session.add(job)
        session.commit()
        session.refresh(job)
        print(f"Created Job {job.id}")
        
    print("Triggering video processing...")
    # Trigger processing. For a worker crash test, you'd usually run docker compose up -d with
    # environment variables set to simulate a crash (e.g. CRASH_AFTER_UPLOAD=1 in clip_tasks.py).
    # Since we have task_acks_late=True, if the worker dies, celery will redeliver the task
    # to a new worker. The new worker will retry, and thanks to idempotency (TaskExecution and PublishRecord),
    # it will safely resume or skip already completed steps.
    start_video_processing_task.delay(job_id=job.id, youtube_url="https://www.youtube.com/watch?v=TEST_CRASH")
    
    print(f"Job {job.id} dispatched. Monitor worker logs to observe recovery.")
    
if __name__ == "__main__":
    main()
