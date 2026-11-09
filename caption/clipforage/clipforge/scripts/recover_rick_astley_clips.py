import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path('.').resolve()))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recover_rick_astley")

from backend.models.database import SyncSessionLocal
from backend.models.models import Clip, Job, Video, JobStatus, ClipStatus
from backend.models.db_sync import update_clip_status_sync, update_job_sync
from backend.core.storage import storage_service
from backend.tasks.clip_tasks import reframe_task, render_task, output_validation_task, publish_task

VIDEO_ID = "d26c5494-0e20-4fff-a51b-4490f0ba5d09"
JOB_ID = "job_recov_d26c5494"
FAILED_CLIPS = [
    "ef1bf3f1-f45a-4b25-95f3-f6314ca61d1a",
    "55b47fad-0449-40da-ae9e-77e6937593ca",
    "de9949d8-5303-4f16-90db-0f62e54da36c"
]

def main():
    logger.info("=== ClipForge: Recovering Rick Astley Clips ===")
    
    # 1. Ensure source video exists in storage
    source_key = f"uploads/{VIDEO_ID}/source.mp4"
    if not storage_service.exists(source_key):
        logger.error(f"Source video {source_key} does not exist in storage!")
        sys.exit(1)
    logger.info(f"Verified source artifact exists: {source_key}")

    # 2. Create or reuse recovery Job record
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=JOB_ID).first()
        if not job:
            job = Job(
                id=JOB_ID,
                video_id=VIDEO_ID,
                source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                source_title="Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) [Recovery]",
                status=JobStatus.CLIPPING_IN_PROGRESS.value,
                progress=80,
                current_step="Recovering failed clips",
                config=json.dumps({"recovery_parent": "job_orch_05725a85", "clips": FAILED_CLIPS})
            )
            session.add(job)
        else:
            job.status = JobStatus.CLIPPING_IN_PROGRESS.value
            job.current_step = "Recovering failed clips"
        session.commit()
    logger.info(f"Initialized recovery job {JOB_ID}")

    # 3. Process each failed clip
    for clip_id in FAILED_CLIPS:
        logger.info(f"\n--- Processing Clip {clip_id} ---")
        
        # Reset status from failed -> pending so transitions work
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                logger.error(f"Clip {clip_id} not found in DB!")
                continue
            clip.status = ClipStatus.PENDING.value
            session.commit()
            logger.info(f"Reset clip {clip_id} status to pending")

        # Step A: Reframe
        logger.info("Executing reframe_task...")
        reframe_async = reframe_task.apply(args=[clip_id], kwargs={"job_id": JOB_ID})
        reframe_res = reframe_async.result
        logger.info(f"Reframe result: {reframe_res}")

        # Step B: Render
        logger.info("Executing render_task...")
        render_async = render_task.apply(args=[reframe_res])
        render_res = render_async.result
        logger.info(f"Render result: {render_res}")

        # Step C: Output Validation
        logger.info("Executing output_validation_task...")
        val_async = output_validation_task.apply(args=[render_res])
        val_res = val_async.result
        logger.info(f"Validation result: {val_res}")

        # Step D: Publish (test / mock mode)
        logger.info("Executing publish_task...")
        pub_async = publish_task.apply(args=[val_res])
        pub_res = pub_async.result
        logger.info(f"Publish result: {pub_res}")

        # Verify output exists on disk
        final_key = f"outputs/{VIDEO_ID}/clips/{clip_id}/final.mp4"
        assert storage_service.exists(final_key), f"Final output missing for clip {clip_id}!"
        logger.info(f"SUCCESS: Clip {clip_id} output verified at {final_key}!")

    # 4. Finalize recovery Job
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=JOB_ID).first()
        if job:
            job.status = JobStatus.COMPLETED.value
            job.progress = 100
            job.current_step = "All recovered clips processed successfully"
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
    logger.info("Recovery job completed successfully!")

if __name__ == "__main__":
    main()
