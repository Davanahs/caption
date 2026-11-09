import os
import sys
import requests

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.models.database import SyncSessionLocal
from backend.models.models import Job

try:
    with SyncSessionLocal() as session:
        # Reset the stuck 'transcribing' job back to pending so it can be re-queued
        job1 = session.query(Job).filter(Job.id == "f6a27fbf-9e1b-46e2-adba-251700df998b", Job.status.in_(['transcribing', 'failed'])).first()
        if job1:
            job1.status = 'pending'
            job1.celery_task_id = None
        
        # Also reset the one stuck in 'failed' state
        job2 = session.query(Job).filter_by(id="3d4a3217-e950-42a8-91f8-227e1ba8e0e1").first()
        if job2:
            job2.status = 'pending'
            job2.celery_task_id = None
            
        session.commit()

        # Find all jobs that are pending and have no celery task dispatched
        pending_jobs = session.query(Job).filter(Job.status == 'pending', Job.celery_task_id == None).all()
        jobs = [(j.id, j.source_url) for j in pending_jobs if j.source_url]
except Exception as e:
    print(f"DB Error: {e}")
    jobs = []

print(f"Jobs to re-dispatch: {len(jobs)}")
for job_id, source_url in jobs:
    print(f"  Re-dispatching job {job_id[:8]}... url={source_url[:60]}")
    try:
        resp = requests.post(
            "http://localhost:8000/api/youtube/process",
            json={"url": source_url},
            timeout=15,
        )
        print(f"  -> {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  -> ERROR: {e}")
