import sys
import os
import time

# Ensure we can import from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models.database import SyncSessionLocal
from backend.models.models import Job, Video, Clip
from backend.tasks.clip_tasks import reframe_task

def main():
    with SyncSessionLocal() as session:
        # Create dummy job, video, and clip
        job = Job(source_url="https://www.youtube.com/watch?v=TEST_CONCURRENCY", status="pending")
        session.add(job)
        session.commit()
        session.refresh(job)
        video = Video(youtube_id="TEST_CONCURRENCY", title="Concurrency Test", local_path="dummy_local_path")
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Now we have video.id, we can set local_path to use video.id
        video.local_path = f"outputs/dummy_{video.id}.mp4"
        session.commit()
        
        job.video_id = video.id
        session.commit()
        
        clip = Clip(
            video_id=video.id, 
            title="Concurrency Clip", 
            status="pending", 
            start_time=0.0, 
            end_time=10.0, 
            duration=10.0,
            run_identity=f"{job.id}_test_1"
        )
        session.add(clip)
        session.commit()
        session.refresh(clip)
        
        # Add dummy artifact
        from backend.models.models import ArtifactRecord, ArtifactType
        artifact = ArtifactRecord(
            owner_type="video", 
            owner_id=video.id, 
            artifact_type=ArtifactType.RAW_VIDEO, 
            storage_key=f"outputs/dummy_{video.id}.mp4",
            backend="local",
            status="ready",
            retention_policy="keep"
        )
        session.add(artifact)
        session.commit()
        
        # Ensure dummy file exists
        with open(f"/app/outputs/dummy_{video.id}.mp4", "w") as f:
            f.write("dummy")
            
        
        print(f"Created Job {job.id}, Video {video.id}, Clip {clip.id}")
        
    print("Dispatching TWO identical reframe tasks concurrently...")
    
    # Send duplicate tasks to Celery to simulate a redelivered task or race condition
    t1 = reframe_task.apply_async(args=[clip.id], queue="celery")
    t2 = reframe_task.apply_async(args=[clip.id], queue="celery")
    
    print(f"Dispatched task 1: {t1.id}")
    print(f"Dispatched task 2: {t2.id}")
    
    print("Wait and observe Celery logs. The second task should report 'ignored due to idempotency'.")
    
if __name__ == "__main__":
    main()
