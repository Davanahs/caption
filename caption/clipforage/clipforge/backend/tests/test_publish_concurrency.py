import os
import sys
import threading
import time
import uuid
import datetime

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.task_execution import check_and_claim_execution
from celery.exceptions import Ignore
from backend.models.database import SyncSessionLocal
from backend.models.models import TaskExecution, Clip, Video

def simulate_worker(worker_id, job_id, clip_id, idempotency_key, results):
    """Simulate a worker attempting to claim a publish task."""
    try:
        # Simulate check_and_claim_execution
        check_and_claim_execution(
            task_id=str(uuid.uuid4()),
            job_id=job_id,
            clip_id=clip_id,
            operation="publish",
            idempotency_key=idempotency_key,
            worker_id=worker_id
        )
        results.append(f"SUCCESS:{worker_id}")
        # Simulate upload taking time
        time.sleep(1)
        
    except Ignore:
        results.append(f"BLOCKED:{worker_id}")
    except Exception as e:
        print(f"Worker {worker_id} encountered an unexpected error: {e}")
        results.append(f"ERROR:{worker_id}")

def test_concurrency():
    clip_id = "test_concurrency_clip"
    video_id = "test_concurrency_video"
    job_id = "test_concurrency_job"
    content_version = "v1"
    idemp_key = f"task_{job_id}_{clip_id}_youtube_{content_version}"
    
    # Setup dummy data
    with SyncSessionLocal() as session:
        # Cleanup any previous runs first
        from backend.models.models import Job
        session.query(TaskExecution).filter(TaskExecution.clip_id == clip_id).delete()
        session.query(Clip).filter(Clip.id == clip_id).delete()
        session.query(Video).filter(Video.id == video_id).delete()
        session.query(Job).filter(Job.id == job_id).delete()
        session.commit()
        
        # Create Dummy Job
        from backend.models.models import Job
        job = Job(
            id=job_id,
            status="running",
            created_at=datetime.datetime.utcnow()
        )
        session.add(job)
        
        # Create Dummy Video
        video = Video(
            id=video_id,
            title="Test", 
            youtube_url="https://youtube.com/watch?v=test"
        )
        session.add(video)
        
        # Create Dummy Clip
        clip = Clip(
            id=clip_id,
            video_id=video_id,
            title="Test Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            created_at=datetime.datetime.utcnow()
        )
        session.add(clip)
        session.commit()
        
    results = []
    
    # Spawn 5 concurrent threads simulating Celery workers picking up the same task
    threads = []
    for i in range(5):
        t = threading.Thread(target=simulate_worker, args=(f"worker_{i}", job_id, clip_id, idemp_key, results))
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    # Verify the results
    successes = [r for r in results if r.startswith("SUCCESS")]
    blocked = [r for r in results if r.startswith("BLOCKED")]
    
    print("\n--- RESULTS ---")
    print(f"Total workers spawned: 5")
    print(f"Workers that claimed the task: {len(successes)}")
    print(f"Workers blocked safely: {len(blocked)}")
    
    # Cleanup
    with SyncSessionLocal() as session:
        from backend.models.models import Job
        session.query(TaskExecution).filter(TaskExecution.clip_id == clip_id).delete()
        session.query(Clip).filter(Clip.id == clip_id).delete()
        session.query(Video).filter(Video.id == video_id).delete()
        session.query(Job).filter(Job.id == job_id).delete()
        session.commit()
    
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(blocked) == 4, f"Expected exactly 4 blocked, got {len(blocked)}"
    
    print("\nTest passed! Distributed lock correctly prevents concurrent uploads.")

if __name__ == "__main__":
    test_concurrency()
