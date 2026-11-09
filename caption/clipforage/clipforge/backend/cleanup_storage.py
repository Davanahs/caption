import os
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR = BASE_DIR / "uploads"

def cleanup():
    print("=== ClipForge Storage Cleanup ===")
    
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Job

    try:
        with SyncSessionLocal() as session:
            active_jobs = session.query(Job).filter(Job.status.notin_(['done', 'failed'])).all()
            active_video_ids = {job.video_id for job in active_jobs if job.video_id}
            
            done_jobs = session.query(Job).filter(Job.status == 'done').all()
            done_video_ids = {job.video_id for job in done_jobs if job.video_id}
    except Exception as e:
        print(f"Database error: {e}")
        return
    
    print(f"Found {len(active_video_ids)} active jobs and {len(done_video_ids)} completed jobs.")
    
    reclaimed_bytes = 0
    
    # 1. Clean outputs/ folder (REMOVED)
    # The outputs/ directory contains canonical final artifacts.
    # It must NEVER be touched by generic transient cleanup.
                        
    # 2. Clean uploads/ folder
    # We delete downloaded source videos for jobs that are 'done' or 'failed' (completed)
    if UPLOADS_DIR.exists():
        for upload_dir in UPLOADS_DIR.iterdir():
            if not upload_dir.is_dir():
                continue
                
            import uuid
            try:
                uuid_obj = uuid.UUID(upload_dir.name)
            except ValueError:
                # Not a valid UUID, might be legacy folder or other file
                print(f"Skipping non-UUID directory: {upload_dir.name}")
                continue
                
            if upload_dir.name in active_video_ids:
                print(f"Skipping active upload directory: {upload_dir.name}")
                continue
                
            # If the job is done or failed (completed), we can delete the whole upload folder
            # as it contains the original full-length video which is no longer needed
            print(f"Removing completed upload folder: {upload_dir.relative_to(BASE_DIR)}")
            
            # Calculate size
            folder_size = 0
            for root, dirs, files in os.walk(upload_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.exists(fp):
                        folder_size += os.path.getsize(fp)
            
            try:
                shutil.rmtree(upload_dir)
                reclaimed_bytes += folder_size
                print(f"Deleted source video folder: {upload_dir.name} ({folder_size / (1024*1024):.2f} MB)")
            except Exception as e:
                print(f"Failed to delete {upload_dir.name}: {e}")
                
    print(f"\nStorage cleanup complete! Reclaimed: {reclaimed_bytes / (1024*1024*1024):.2f} GB of disk space.")

if __name__ == "__main__":
    cleanup()
