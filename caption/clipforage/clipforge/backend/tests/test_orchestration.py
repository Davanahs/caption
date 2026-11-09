import os
import sys
import uuid
import time
from pathlib import Path
import pytest

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.models.database import SyncSessionLocal
from backend.models.models import Job, Clip, Video
from backend.tasks.orchestration import start_video_processing_task

def test_orchestration_pipeline():
    """
    Integration test for the full video processing pipeline.
    Requires Celery worker to be running in TEST mode.
    """
    job_id = f"job_orch_{uuid.uuid4().hex[:8]}"
    
    os.environ["SCORING_MODE"] = "test"
    os.environ["PUBLISH_MODE"] = "test"
    
    import json
    # Pre-create Job record in DB to match production API behavior
    with SyncSessionLocal() as session:
        job = Job(
            id=job_id,
            status="pending",
            progress=0,
            current_step="Queued",
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            source_title="Test Video",
            config=json.dumps({"scoring_mode": "test", "publish_mode": "test"})
        )
        session.add(job)
        session.commit()

    # Trigger the task
    print(f"Triggering job {job_id}")
    result = start_video_processing_task.delay(
        job_id, 
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", title="Test Video"
    )
    
    print(f"Task submitted with ID {result.id}. Waiting for completion...")
    
    # Poll database for completion
    max_retries = 150
    retry_delay = 2  # seconds
    
    completed = False
    for _ in range(max_retries):
        with SyncSessionLocal() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                # print(f"Job status: {job.status}, step: {job.current_step}")
                if job.status == "completed":
                    completed = True
                    break
                elif job.status == "failed":
                    print(f"Job failed: {job.error_message}")
                    break
        time.sleep(retry_delay)
        
    assert completed, f"Job {job_id} did not complete within the timeout"
        
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        # Verify clips were generated and published
        clips = session.query(Clip).filter_by(video_id=job.video_id).all()
        assert len(clips) > 0, "No clips were generated"
        
        for clip in clips:
            assert clip.status == "completed", f"Clip {clip.id} is not completed"
            assert clip.publish_status == "published", f"Clip {clip.id} is not published"
            assert clip.youtube_short_id is not None, f"Clip {clip.id} has no youtube_short_id"
            
        print("SUCCESS: Orchestration pipeline verified.")

if __name__ == "__main__":
    test_orchestration_pipeline()