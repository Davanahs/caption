import sys
from pathlib import Path

sys.path.append(str(Path('.').resolve()))

from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import Job, Video, Clip, ArtifactRecord, ArtifactStatus
from backend.cleanup_storage import cleanup
import uuid
import os

def test():
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    vid = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    clip_id = str(uuid.uuid4())
    
    print(f"Test Video ID: {vid}")
    
    # Create DB records
    with SyncSessionLocal() as session:
        v = Video(id=vid, title="Test Video")
        session.add(v)
        
        j = Job(id=job_id, video_id=vid, status="done")
        session.add(j)
        
        c = Clip(id=clip_id, video_id=vid, status="done", start_time=0.0, end_time=10.0, duration=10.0)
        session.add(c)
        session.commit()
    
    # Create files
    upload_dir = settings.UPLOAD_DIR / vid
    upload_dir.mkdir(parents=True, exist_ok=True)
    raw_file = upload_dir / "raw.mp4"
    raw_file.write_text("dummy raw data")
    
    output_dir = settings.OUTPUT_DIR / vid / "clips" / clip_id
    output_dir.mkdir(parents=True, exist_ok=True)
    final_file = output_dir / "final.mp4"
    final_file.write_text("dummy final data")
    
    # Run cleanup
    print("Running cleanup...")
    cleanup()
    
    # Assertions
    if raw_file.exists():
        print(f"ERROR: {raw_file} still exists! It should have been cleaned up.")
        sys.exit(1)
        
    if not final_file.exists():
        print(f"ERROR: {final_file} was deleted! Canonical storage was touched.")
        sys.exit(1)
        
    print("SUCCESS: Transient file deleted, Canonical file preserved.")
    
    # Cleanup DB
    with SyncSessionLocal() as session:
        c = session.query(Clip).filter_by(id=clip_id).first()
        j = session.query(Job).filter_by(id=job_id).first()
        v = session.query(Video).filter_by(id=vid).first()
        session.delete(c)
        session.delete(j)
        session.delete(v)
        session.commit()
        
    # Cleanup files
    import shutil
    shutil.rmtree(settings.OUTPUT_DIR / vid, ignore_errors=True)

if __name__ == "__main__":
    test()
