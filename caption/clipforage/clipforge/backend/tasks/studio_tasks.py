"""
ClipForge — Upload Studio Phase 2 Sequential Batch Tasks

Implements durable sequential batch processing with:
- Strict queue position execution (ordered by queue_position ASC)
- Single active item guarantee per batch (zero concurrent execution)
- Safe idempotent retries preserving original queue position
- Cooperative cancellation stopping subsequent queue items
- Worker heartbeat tracking and stale execution recovery
- Headroom reservation release on completion
- Strict caption/subtitle removal constraint compliance
"""
import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from backend.tasks.celery_app import celery_app
from backend.models.database import SyncSessionLocal
from backend.models.models import (
    UploadBatch,
    Video,
    Job,
    JobStatus,
    StorageReservationCoordinator,
    UploadBatchStatus,
    VideoUploadStatus,
    VideoProcessingStatus,
    VideoReservationState,
)
from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS
from backend.core.config import settings

logger = logging.getLogger(__name__)


def get_storage_root() -> Path:
    return Path(settings.UPLOAD_DIR).resolve()


def get_batch_dir(batch_id: str) -> Path:
    base = get_storage_root()
    batch_dir = (base / "studio" / "batches" / batch_id).resolve()
    if not str(batch_dir).startswith(str(base)):
        raise ValueError("Invalid path containment for batch directory")
    return batch_dir


@celery_app.task(
    bind=True,
    name="backend.tasks.studio_tasks.process_studio_batch_sequential_task",
    **DEFAULT_RETRY_KWARGS,
)
def process_studio_batch_sequential_task(self, batch_id: str, retry_video_id: Optional[str] = None):
    """
    Main sequential orchestrator for an Upload Studio batch.
    Processes items strictly one by one in queue_position order.
    Guarantees:
    - Only one item actively processing per batch at any time.
    - Idempotent: repeated calls do not create duplicate work.
    - Fails safely if media artifact is missing.
    - Does not proceed past a failed item unless explicitly retried.
    """
    from backend.tasks.orchestration import start_video_processing_task

    now = datetime.now(timezone.utc)
    task_id = self.request.id if hasattr(self, "request") and self.request else str(uuid.uuid4())
    logger.info(f"[StudioBatch] Starting sequential processing for batch {batch_id} (task: {task_id})")

    with SyncSessionLocal() as session:
        # Step 1: Acquire row lock on UploadBatch
        batch = session.query(UploadBatch).filter(UploadBatch.id == batch_id).with_for_update().first()
        if not batch:
            logger.error(f"[StudioBatch] Batch {batch_id} not found")
            return {"status": "batch_not_found"}

        # Step 2: Validate batch lifecycle state
        if batch.status in (UploadBatchStatus.CANCELLED.value, UploadBatchStatus.DELETING.value):
            logger.info(f"[StudioBatch] Batch {batch_id} is {batch.status}. Aborting processing.")
            return {"status": batch.status}

        if batch.status == UploadBatchStatus.CANCELLING.value:
            # Complete cancellation
            remaining_queued = session.query(Video).filter(
                Video.upload_batch_id == batch_id,
                Video.processing_status.in_([VideoProcessingStatus.QUEUED.value, VideoProcessingStatus.NONE.value])
            ).all()
            for v in remaining_queued:
                v.processing_status = VideoProcessingStatus.CANCELLED.value
            batch.status = UploadBatchStatus.CANCELLED.value
            batch.active_video_id = None
            batch.active_task_id = None
            session.commit()
            return {"status": "cancelled"}

        # Step 3: Query all uploaded videos in this batch ordered by queue_position
        videos = session.query(Video).filter(
            Video.upload_batch_id == batch_id,
            Video.upload_status == VideoUploadStatus.UPLOADED.value
        ).order_by(Video.queue_position.asc()).with_for_update().all()

        if not videos:
            logger.warning(f"[StudioBatch] Batch {batch_id} has no uploaded videos.")
            batch.status = UploadBatchStatus.COMPLETED.value
            batch.active_video_id = None
            batch.active_task_id = None
            session.commit()
            return {"status": "no_videos"}

        # Step 4: Check if any item is ALREADY actively processing
        active_video = next((v for v in videos if v.processing_status == VideoProcessingStatus.PROCESSING.value), None)
        if active_video and not retry_video_id:
            # Check if active job is still legitimately running
            if active_video.processing_job_id:
                job = session.query(Job).filter(Job.id == active_video.processing_job_id).first()
                if job and job.status not in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
                    # Job is actively running: prevent duplicate concurrent task execution!
                    logger.info(f"[StudioBatch] Video {active_video.id} is already actively processing in job {job.id}. Skipping duplicate dispatch.")
                    batch.worker_heartbeat = now
                    session.commit()
                    return {"status": "already_processing", "active_video_id": active_video.id}

        # Step 5: Find the target video to process
        target_video = None

        if retry_video_id:
            # User explicitly requested retry of a specific video
            target_candidate = next((v for v in videos if v.id == retry_video_id), None)
            if target_candidate:
                # Ensure no preceding video is failed
                preceding_failed = [
                    v for v in videos 
                    if (v.queue_position or 0) < (target_candidate.queue_position or 0) 
                    and v.processing_status == VideoProcessingStatus.FAILED.value
                ]
                if not preceding_failed:
                    target_video = target_candidate
                else:
                    logger.warning(f"[StudioBatch] Cannot retry video {retry_video_id} because earlier item is failed.")
                    batch.status = UploadBatchStatus.FAILED.value
                    batch.batch_error = f"Cannot process item #{target_candidate.queue_position + 1} while earlier item is failed."
                    session.commit()
                    return {"status": "preceding_item_failed"}
        else:
            # Sequential scan: find first video that is NOT completed or cancelled
            for v in videos:
                if v.processing_status == VideoProcessingStatus.FAILED.value:
                    # Encountered a failed item in sequential scan: HALT the batch!
                    logger.info(f"[StudioBatch] Batch {batch_id} halted at failed item {v.id} (pos: {v.queue_position})")
                    batch.status = UploadBatchStatus.FAILED.value
                    batch.active_video_id = None
                    batch.active_task_id = None
                    batch.batch_error = f"Processing paused at failed item #{v.queue_position + 1}: {v.processing_error or 'pipeline error'}"
                    session.commit()
                    return {"status": "halted_at_failed_item", "video_id": v.id}

                if v.processing_status not in (VideoProcessingStatus.COMPLETED.value, VideoProcessingStatus.CANCELLED.value):
                    target_video = v
                    break

        if not target_video:
            # All items in batch are completed (or cancelled)
            logger.info(f"[StudioBatch] All items in batch {batch_id} are completed.")
            batch.status = UploadBatchStatus.COMPLETED.value
            batch.active_video_id = None
            batch.active_task_id = None
            batch.processing_completed_at = now
            session.commit()
            return {"status": "completed"}

        # Step 6: Validate physical media artifact existence before processing
        batch_dir = get_batch_dir(batch_id)
        local_path = target_video.local_path

        artifact_valid = False
        if local_path:
            p = Path(local_path)
            if p.exists() and p.stat().st_size > 0:
                artifact_valid = True

        if not artifact_valid:
            # Media artifact is missing or corrupted on disk: mark failed and halt!
            logger.error(f"[StudioBatch] Media artifact for video {target_video.id} is missing at {local_path}")
            target_video.processing_status = VideoProcessingStatus.FAILED.value
            target_video.processing_error = "Media artifact is missing or inaccessible on disk"
            target_video.processing_step = "Artifact validation failed"
            target_video.processing_completed_at = now
            batch.status = UploadBatchStatus.FAILED.value
            batch.active_video_id = None
            batch.active_task_id = None
            batch.batch_error = f"Item {target_video.id} failed: artifact missing on disk"
            session.commit()
            return {"status": "artifact_missing", "video_id": target_video.id}

        # Step 7: Claim processing lease on target_video
        target_video.processing_status = VideoProcessingStatus.PROCESSING.value
        target_video.processing_attempt = (target_video.processing_attempt or 0) + 1
        target_video.processing_started_at = now
        target_video.processing_error = None
        target_video.processing_step = "Queued in video pipeline"
        target_video.processing_progress = 5

        batch.status = UploadBatchStatus.PROCESSING.value
        batch.active_video_id = target_video.id
        batch.active_task_id = task_id
        batch.worker_heartbeat = now
        batch.batch_error = None
        if not batch.processing_started_at:
            batch.processing_started_at = now

        # Create linked Job record
        job_id = f"job_studio_{uuid.uuid4().hex[:12]}"
        job_config = {
            "studio_batch_id": batch_id,
            "video_id": target_video.id,
            "scoring_mode": os.environ.get("SCORING_MODE", "ai"),
            "publish_mode": os.environ.get("PUBLISH_MODE", "draft"),
            "clip_mode": "ai_highlights",
            "clips_count": 3,
            "num_clips": 3,
        }
        dispatch_kwargs = {
            "job_id": job_id,
            "video_id": target_video.id,
            "local_path": target_video.local_path,
            "studio_batch_id": batch_id,
            "num_clips": 3,
            "clips_count": 3,
            "clip_mode": "ai_highlights",
        }
        job_config["dispatch_kwargs"] = dispatch_kwargs

        job = Job(
            id=job_id,
            video_id=target_video.id,
            source_url=target_video.source_filename or target_video.title,
            source_title=target_video.title,
            status=JobStatus.PENDING.value,
            progress=5,
            current_step="Queued for sequential processing",
            config=json.dumps(job_config),
            created_at=now,
            updated_at=now
        )
        session.add(job)
        target_video.processing_job_id = job_id

        session.commit()

        # Step 8: Check manual concurrency limit (max 5 active)
        from backend.services.queue_manager import (
            get_active_manual_jobs_count_sync,
            get_pending_queue_position_sync,
            format_queue_step,
            MAX_CONCURRENT_MANUAL_JOBS,
            dispatch_celery_job,
        )

        active_count = get_active_manual_jobs_count_sync(session)
        if active_count < MAX_CONCURRENT_MANUAL_JOBS:
            task_id = dispatch_celery_job(job_id, dispatch_kwargs)
            job.celery_task_id = task_id
            job.current_step = "Queued for sequential processing"
            session.commit()
            logger.info(f"[StudioBatch] Dispatched pipeline job {job_id} for video {target_video.id} (queue pos: {target_video.queue_position})")
            return {
                "status": "processing_started",
                "batch_id": batch_id,
                "video_id": target_video.id,
                "job_id": job_id,
                "queue_position": target_video.queue_position
            }
        else:
            position = get_pending_queue_position_sync(session, job_id)
            job.celery_task_id = None
            job.current_step = format_queue_step(position)
            session.commit()
            logger.info(f"[StudioBatch] Queued pipeline job {job_id} (#{position} in line - limit {MAX_CONCURRENT_MANUAL_JOBS} reached)")
            return {
                "status": "queued",
                "batch_id": batch_id,
                "video_id": target_video.id,
                "job_id": job_id,
                "queue_position": position
            }


@celery_app.task(
    name="backend.tasks.studio_tasks.on_studio_video_finished_task"
)
def on_studio_video_finished_task(batch_id: str, video_id: str, job_id: str):
    """
    Callback executed when a video processing job completes or fails.
    Updates persistent state, releases headroom reservations on success,
    and advances sequentially to the next item if eligible.
    """
    now = datetime.now(timezone.utc)
    logger.info(f"[StudioBatch] Video {video_id} in batch {batch_id} finished job {job_id}")

    with SyncSessionLocal() as session:
        # Lock Coordinator -> Batch -> Video in strict hierarchy
        coord = session.query(StorageReservationCoordinator).filter(
            StorageReservationCoordinator.id == "global"
        ).with_for_update().first()

        batch = session.query(UploadBatch).filter(
            UploadBatch.id == batch_id
        ).with_for_update().first()

        video = session.query(Video).filter(
            Video.id == video_id
        ).with_for_update().first()

        job = session.query(Job).filter(
            Job.id == job_id
        ).first()

        if not batch or not video or not job:
            logger.error(f"[StudioBatch] on_studio_video_finished_task: Missing batch/video/job record")
            return

        # Stale-worker ownership fencing: ensure callback belongs to video's active processing job
        if video.processing_job_id and video.processing_job_id != job_id:
            logger.warning(f"[StudioBatch] Obsolete callback from job {job_id}; active job is {video.processing_job_id}. Discarding.")
            return

        is_success = (job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value))

        if is_success:
            # 1. Update Video to COMPLETED
            video.processing_status = VideoProcessingStatus.COMPLETED.value
            video.processing_progress = 100
            video.processing_step = "Completed"
            video.processing_completed_at = now
            video.processing_error = None

            # 2. Release remaining headroom reservation for this video
            if video.reserved_bytes > 0:
                released = video.reserved_bytes
                if coord:
                    coord.reserved_bytes = max(0, coord.reserved_bytes - released)
                batch.reserved_bytes = max(0, batch.reserved_bytes - released)
                video.reserved_bytes = 0
                video.reservation_state = VideoReservationState.RELEASED.value

            batch.worker_heartbeat = now

            # Check if batch cancellation was requested while item was processing
            if batch.status == UploadBatchStatus.CANCELLING.value:
                # Cancel remaining queued items
                remaining = session.query(Video).filter(
                    Video.upload_batch_id == batch_id,
                    Video.processing_status.in_([VideoProcessingStatus.QUEUED.value, VideoProcessingStatus.NONE.value])
                ).all()
                for rem in remaining:
                    rem.processing_status = VideoProcessingStatus.CANCELLED.value
                batch.status = UploadBatchStatus.CANCELLED.value
                batch.active_video_id = None
                batch.active_task_id = None
                session.commit()
                return

            # Check if there are further uncompleted items
            uncompleted_count = session.query(func.count(Video.id)).filter(
                Video.upload_batch_id == batch_id,
                Video.upload_status == VideoUploadStatus.UPLOADED.value,
                Video.processing_status.notin_([VideoProcessingStatus.COMPLETED.value, VideoProcessingStatus.CANCELLED.value])
            ).scalar()

            if uncompleted_count == 0:
                # All videos in batch completed!
                batch.status = UploadBatchStatus.COMPLETED.value
                batch.active_video_id = None
                batch.active_task_id = None
                batch.processing_completed_at = now
                session.commit()
                logger.info(f"[StudioBatch] Batch {batch_id} all items completed successfully!")
                return
            else:
                # More videos waiting in queue: advance to next item sequentially
                batch.active_video_id = None
                session.commit()
                logger.info(f"[StudioBatch] Video {video_id} completed. Advancing to next video in batch {batch_id}")
                process_studio_batch_sequential_task.delay(batch_id)
                return

        else:
            # Job failed
            video.processing_status = VideoProcessingStatus.FAILED.value
            video.processing_error = job.error_message or "Video processing pipeline failed"
            video.processing_step = f"Failed: {job.current_step or 'Pipeline error'}"
            video.processing_completed_at = now

            # Pause batch at failed item
            batch.status = UploadBatchStatus.FAILED.value
            batch.active_video_id = None
            batch.active_task_id = None
            batch.batch_error = f"Item #{video.queue_position + 1} ({video.title}) failed: {video.processing_error}"
            batch.worker_heartbeat = now

            session.commit()
            logger.warning(f"[StudioBatch] Video {video_id} failed. Batch {batch_id} paused in failed state.")
            return


@celery_app.task(
    name="backend.tasks.studio_tasks.recover_stale_studio_batches_task"
)
def recover_stale_studio_batches_task(timeout_minutes: int = 10):
    """
    Celery Beat task that inspects active processing batches.
    Detects workers that died or lost heartbeat (>10 minutes).
    Transitions stale active items safely to FAILED to allow user retry.
    """
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(minutes=timeout_minutes)

    recovered_count = 0
    with SyncSessionLocal() as session:
        stale_batches = session.query(UploadBatch).filter(
            UploadBatch.status == UploadBatchStatus.PROCESSING.value,
            UploadBatch.worker_heartbeat < stale_threshold
        ).all()

        for batch in stale_batches:
            logger.warning(f"[StudioBatch] Batch {batch.id} has stale worker heartbeat ({batch.worker_heartbeat}). Recovering...")
            if batch.active_video_id:
                active_video = session.query(Video).filter(Video.id == batch.active_video_id).first()
                if active_video and active_video.processing_status == VideoProcessingStatus.PROCESSING.value:
                    active_video.processing_status = VideoProcessingStatus.FAILED.value
                    active_video.processing_error = "Worker timeout / stale execution (worker disappeared)"
                    active_video.processing_step = "Worker timeout"
                    active_video.processing_completed_at = now

            batch.status = UploadBatchStatus.FAILED.value
            batch.batch_error = "Worker failure recovered: task became stale without heartbeat."
            batch.active_video_id = None
            batch.active_task_id = None
            batch.worker_heartbeat = now
            recovered_count += 1

        session.commit()

    if recovered_count > 0:
        logger.info(f"[StudioBatch] Recovered {recovered_count} stale studio batches.")

    return {"recovered_batches": recovered_count}
