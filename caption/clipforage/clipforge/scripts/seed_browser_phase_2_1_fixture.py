import os
import shutil
import json
from pathlib import Path
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import Video, Clip, ClipRetention

video_id = "p21_browser_vid_1"
clip_id = "p21_browser_clip_1"

clip_dir = settings.OUTPUT_DIR / video_id / "clips" / clip_id
clip_dir.mkdir(parents=True, exist_ok=True)
final_file = clip_dir / "final.mp4"
if not final_file.exists():
    final_file.write_bytes(b"X" * (512 * 1024))  # 512 KB

with SyncSessionLocal() as session:
    # Cleanup previous if any
    session.query(ClipRetention).filter(ClipRetention.clip_id == clip_id).delete()
    session.query(Clip).filter(Clip.id == clip_id).delete()
    session.query(Video).filter(Video.id == video_id).delete()
    session.commit()

    v = Video(
        id=video_id,
        title="AI Creative Enhancements Master Video",
        duration=45.0,
        channel_id="ch_p21_demo"
    )
    c = Clip(
        id=clip_id,
        video_id=video_id,
        title="Unbelievable AI Breakthrough in 2026",
        score=9.2,
        start_time=0.0,
        end_time=18.0,
        duration=18.0,
        output_path=f"{video_id}/clips/{clip_id}/final.mp4",
        transcript_segment="Wait until you see how this insane technology changes everything you knew.",
        description="High-velocity curiosity hook explaining transformative AI systems.",
        publish_status="draft"
    )
    r = ClipRetention(
        clip_id=clip_id,
        overall_score=8.4,
        analysis_json=json.dumps([{
            "start_time": 0.0,
            "end_time": 2.5,
            "severity": "high",
            "primary_reason": "low_audio_energy",
            "contributing_reasons": ["silence"],
            "confidence": 0.91,
            "suggested_intervention_types": ["sfx_opportunity", "zoom_push"]
        }])
    )
    session.add_all([v, c, r])
    session.commit()

print(f"Seeded Phase 2.1 browser fixture: {clip_id} with file {final_file}")
