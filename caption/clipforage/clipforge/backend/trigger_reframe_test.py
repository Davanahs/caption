from celery import Celery
import uuid
import time
from datetime import datetime

# Define Celery app connecting to redis inside docker network
app = Celery(
    "clipforge",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1"
)

def trigger_job(mode):
    job_id = str(uuid.uuid4())
    print(f"\nTriggering task with mode '{mode}' (job_id: {job_id})")

    from backend.models.database import SyncSessionLocal
    from backend.models.models import Job
    from datetime import timezone

    try:
        with SyncSessionLocal() as session:
            now_dt = datetime.now(timezone.utc)
            job = Job(
                id=job_id,
                status="PENDING",
                progress=0,
                current_step="Queued",
                source_url=f"rick_{mode}.mp4",
                source_title=f"Rick Astley Test ({mode})",
                created_at=now_dt,
                updated_at=now_dt
            )
            session.add(job)
            session.commit()
    except Exception as e:
        print(f"Failed to insert job: {e}")

    # Send the task
    res = app.send_task(
        "process_video",
        kwargs={
            "local_path": f"/app/uploads/rick_{mode}.mp4",
            "job_id": job_id,
            "num_clips": 1,
            "hook_type": "question",
            "reframe_mode": mode
        },
        task_id=job_id
    )

    print(f"Task sent! Task ID: {res.id}")

    # Poll status
    while True:
        time.sleep(5)
        try:
            with SyncSessionLocal() as session:
                job = session.query(Job).filter_by(id=job_id).first()
                if job:
                    print(f"[{mode}] Status: {job.status} | Progress: {job.progress}% | Step: {job.current_step} | Error: {job.error_message}")
                    if job.status in ["done", "failed"]:
                        return job_id, job.status
                else:
                    print("Job row not found yet...")
        except Exception as e:
            print(f"Polling error: {e}")

if __name__ == "__main__":
    # Trigger both crop and blur modes
    trigger_job("blur")
    trigger_job("crop")
