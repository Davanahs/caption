import os
import shutil
from pathlib import Path
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import Video, Clip

video_id = "p13_browser_vid_1"
clip_id = "p13_browser_clip_1"

clip_dir = settings.OUTPUT_DIR / video_id / "clips" / clip_id
clip_dir.mkdir(parents=True, exist_ok=True)
final_file = clip_dir / "final.mp4"
final_file.write_bytes(b"X" * (1024 * 1024))  # 1 MB

with SyncSessionLocal() as session:
    # Cleanup previous if any
    session.query(Clip).filter(Clip.id == clip_id).delete()
    session.query(Video).filter(Video.id == video_id).delete()
    session.commit()

    v = Video(id=video_id, title="Browser Test Source Video", duration=30.0)
    c = Clip(
        id=clip_id,
        video_id=video_id,
        title="Browser Test Low Score Clip",
        score=3.1,
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        output_path=f"{video_id}/clips/{clip_id}/final.mp4",
        publish_status="draft"
    )
    session.add_all([v, c])
    session.commit()

print(f"Seeded browser fixture: {clip_id} with file {final_file} (1 MB)")
