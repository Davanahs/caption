import asyncio
import subprocess
from pathlib import Path
from backend.models.database import AsyncSessionLocal
from backend.models.models import Clip
from backend.services.advanced_podcast_engine import (
    build_visibility_driven_schedule,
    render_visibility_driven_video,
)
from sqlalchemy import select

async def recover_clips():
    clip_ids = [
        "525f1165-8046-4ae8-9d37-b416c04ee2d4",
        "f6e2b0af-0a3a-41d7-8ad9-4430916adeeb",
        "7cf900ac-3e3f-410d-955a-4c0d5a251a98",
    ]
    src_video = Path("uploads/0GjbIOS9Q90.mp4")
    if not src_video.exists():
        src_video = Path("uploads/82b8060b-82eb-4934-a75f-46ca7b3910ea/source.mp4")

    print(f"Using source video: {src_video} (exists: {src_video.exists()})")

    reg_a = {"id": "area-1", "x": 0.08, "y": 0.1, "width": 0.4, "height": 0.8}
    reg_b = {"id": "area-2", "x": 0.52, "y": 0.1, "width": 0.4, "height": 0.8}

    print("Building full visibility-driven schedule once...")
    schedule = build_visibility_driven_schedule(
        video_path=src_video,
        region_a=reg_a,
        region_b=reg_b,
        ref_timestamp=3.0,
    )
    print(f"Schedule built with {len(schedule)} cuts.")

    async with AsyncSessionLocal() as db:
        for cid in clip_ids:
            res = await db.execute(select(Clip).where(Clip.id == cid))
            clip = res.scalar_one_or_none()
            if not clip:
                print(f"Clip {cid} not found, skipping.")
                continue

            print(f"\n--- Recovering Clip: {clip.title} ({cid}) ---")
            print(f"Time: {clip.start_time:.1f}s - {clip.end_time:.1f}s ({clip.duration:.1f}s)")

            out_dir = Path("outputs") / clip.video_id / "clips" / clip.id
            out_dir.mkdir(parents=True, exist_ok=True)
            final_mp4 = out_dir / "final.mp4"
            thumb_jpg = out_dir / "thumb_a.jpg"

            # Render 9:16 vertical video with new enhanced quality pipeline
            force_rerender = False
            if force_rerender or not final_mp4.exists() or final_mp4.stat().st_size == 0:
                print(f"Rendering 9:16 vertical video with enhanced quality to {final_mp4}...")
                await render_visibility_driven_video(
                    video_path=src_video,
                    output_path=final_mp4,
                    schedule=schedule,
                    clip_start=float(clip.start_time),
                    clip_end=float(clip.end_time),
                )
                print(f"Rendered: {final_mp4.stat().st_size} bytes")
            else:
                print(f"Video already rendered ({final_mp4.stat().st_size} bytes)")

            # Extract thumbnail frame
            if not thumb_jpg.exists():
                thumb_time = min(5.0, float(clip.duration) / 2.0)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{thumb_time:.2f}",
                    "-i", str(final_mp4),
                    "-vframes", "1",
                    "-q:v", "2",
                    str(thumb_jpg)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Thumbnail extracted: {thumb_jpg.exists()}")

            # Clean error prefixes from description
            cleaned_desc = clip.description or ""
            while "Error: " in cleaned_desc:
                cleaned_desc = cleaned_desc.split("Error: ", 1)[-1]
                # Strip traceback lines
                lines = cleaned_desc.split("\n")
                if lines and ("AttributeError" in lines[0] or "object has no attribute" in lines[0]):
                    cleaned_desc = "\n".join(lines[1:]).strip()

            # Update DB record
            clip.output_path = str(final_mp4)
            clip.thumbnail_path = str(thumb_jpg)
            clip.status = "completed"
            clip.publish_status = "draft"
            clip.description = cleaned_desc
            await db.commit()
            print(f"Clip {cid} successfully recovered and marked as COMPLETED in DB!")

    print("\nAll 3 clips fully recovered!")

if __name__ == "__main__":
    asyncio.run(recover_clips())

