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
import asyncio
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
    Clip,
    Channel,
    DestinationOutro,
    PublishTarget,
    PublishStatus,
    ClipStatus,
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


def _run_coro_safe(coro):
    """Safely execute an async coroutine inside a synchronous Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result(timeout=120)
    else:
        return asyncio.run(coro)


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
        batch_file = batch_dir / f"{target_video.id}.mp4"
        if batch_file.exists() and batch_file.stat().st_size > 0:
            artifact_valid = True
            local_path = str(batch_file)
            target_video.local_path = str(batch_file)
        elif local_path:
            p = Path(local_path)
            if p.exists() and p.stat().st_size > 0:
                artifact_valid = True
            elif (settings.BASE_DIR / local_path).exists() and (settings.BASE_DIR / local_path).stat().st_size > 0:
                artifact_valid = True
                local_path = str((settings.BASE_DIR / local_path).resolve())
                target_video.local_path = local_path
            else:
                try:
                    from backend.core.storage import storage_service
                    if not os.path.isabs(str(local_path)) and storage_service.exists(local_path):
                        artifact_valid = True
                except Exception:
                    pass

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

        # Create linked Job record inheriting UploadBatch configuration (including destination_ids)
        batch_cfg = batch.config if isinstance(batch.config, dict) else {}
        cfg_dest_ids = batch_cfg.get("destination_ids")
        cfg_clips_count = batch_cfg.get("clips_count") or 3
        cfg_clip_mode = batch_cfg.get("clip_mode") or "ai_highlights"
        cfg_reframe_mode = batch_cfg.get("reframe_mode")
        cfg_max_dur = batch_cfg.get("max_clip_duration")

        job_id = f"job_studio_{uuid.uuid4().hex[:12]}"
        job_config = {
            "studio_batch_id": batch_id,
            "video_id": target_video.id,
            "scoring_mode": os.environ.get("SCORING_MODE", "ai"),
            "publish_mode": os.environ.get("PUBLISH_MODE", "draft"),
            "clip_mode": cfg_clip_mode,
            "clips_count": cfg_clips_count,
            "num_clips": cfg_clips_count,
        }
        dispatch_kwargs = {
            "job_id": job_id,
            "video_id": target_video.id,
            "local_path": target_video.local_path,
            "studio_batch_id": batch_id,
            "num_clips": cfg_clips_count,
            "clips_count": cfg_clips_count,
            "clip_mode": cfg_clip_mode,
        }
        if cfg_dest_ids is not None:
            job_config["destination_ids"] = cfg_dest_ids
            dispatch_kwargs["destination_ids"] = cfg_dest_ids
            if len(cfg_dest_ids) > 0:
                job_config["publish_destination_id"] = cfg_dest_ids[0]
                dispatch_kwargs["publish_destination_id"] = cfg_dest_ids[0]
        if cfg_reframe_mode:
            job_config["reframe_mode"] = cfg_reframe_mode
            dispatch_kwargs["reframe_mode"] = cfg_reframe_mode
        if cfg_max_dur:
            job_config["max_clip_duration"] = cfg_max_dur
            dispatch_kwargs["max_clip_duration"] = cfg_max_dur
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
            job.current_step = "Starting direct studio processing..."
            session.commit()
            logger.info(f"[StudioBatch] Dispatched direct studio job {job_id} for video {target_video.id} (queue pos: {target_video.queue_position})")
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
            if not video.processing_step or video.processing_step.startswith("Queued"):
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


@celery_app.task(
    bind=True,
    name="backend.tasks.studio_tasks.process_studio_direct_video_task",
    max_retries=1,
    default_retry_delay=5,
)
def process_studio_direct_video_task(
    self,
    job_id: str,
    video_id: str,
    local_path: str,
    studio_batch_id: str,
    destination_ids: list[str] | None = None,
    **kwargs,
):
    """
    Dedicated direct processing and publishing pipeline strictly for Upload Studio.
    1. Validates media file using FFprobe (width, height, duration, audio presence).
    2. Transcribes audio content via Whisper (Groq with local fallback; handles silent video gracefully).
    3. Generates viral Short metadata (AI Title <=70 chars with emoji, rich description with hashtags, SEO tags).
    4. Creates/updates 1:1 Clip record.
    5. Checks destination channel(s) (e.g. Rhymee). If destination has an active outro, concatenates outro
       via render_clip_with_outro while strictly preserving original video and enforcing -sn subtitle exclusion.
    6. Publishes to destination YouTube channel(s) in Private mode (privacyStatus = 'private').
    7. Creates/updates PublishTarget records with youtube_video_id and marks completed.
    8. Advances sequentially to next item in the batch via on_studio_video_finished_task.
    """
    now = datetime.now(timezone.utc)
    logger.info(f"[StudioDirect] Processing job={job_id}, video={video_id}, batch={studio_batch_id}, dests={destination_ids}")

    from backend.services.transcriber import transcribe_video
    from backend.services.metadata_generator import generate_metadata
    from backend.services.outro_service import (
        render_clip_with_outro,
        probe_media_with_ffprobe,
    )
    from backend.services.publisher import upload_short

    try:
        # Step 1: Initial DB validation & state update
        with SyncSessionLocal() as session:
            batch = session.query(UploadBatch).filter_by(id=studio_batch_id).first()
            job = session.query(Job).filter_by(id=job_id).first()
            video = session.query(Video).filter_by(id=video_id).first()

            if not video or not job or not batch:
                logger.error(f"[StudioDirect] Missing video, job, or batch record for {job_id}")
                return {"status": "error", "error": "Records not found"}

            if batch.status in (UploadBatchStatus.CANCELLED.value, UploadBatchStatus.CANCELLING.value):
                logger.info(f"[StudioDirect] Batch {studio_batch_id} cancelled. Aborting.")
                job.status = JobStatus.CANCELLED.value
                video.processing_status = VideoProcessingStatus.CANCELLED.value
                session.commit()
                return {"status": "cancelled"}

            job.status = JobStatus.VALIDATING.value
            job.progress = 10
            job.current_step = "Inspecting media artifact..."
            video.processing_status = VideoProcessingStatus.PROCESSING.value
            video.processing_progress = 10
            video.processing_step = "Inspecting media artifact..."
            batch.worker_heartbeat = now
            session.commit()

            # Step 2: Resolve physical artifact path
            resolved_path = None
            candidate_paths = [
                Path(local_path) if local_path else None,
                get_batch_dir(studio_batch_id) / f"{video_id}.mp4",
                settings.BASE_DIR / local_path if local_path else None,
                Path(settings.UPLOAD_DIR) / f"{video_id}.mp4",
                Path(settings.UPLOAD_DIR) / "studio" / "batches" / studio_batch_id / f"{video_id}.mp4",
                Path(settings.UPLOAD_DIR) / video_id / "source.mp4",
            ]
            for cp in candidate_paths:
                if cp and cp.exists() and cp.stat().st_size > 0:
                    resolved_path = cp.resolve()
                    break

            if not resolved_path:
                raise ValueError(f"Media artifact missing or inaccessible on disk at {local_path}")

            video.local_path = str(resolved_path)

            # Step 3: FFprobe inspection (dimensions, duration, audio presence)
            probe_data = probe_media_with_ffprobe(resolved_path)
            streams = probe_data.get("streams", [])
            fmt = probe_data.get("format", {})
            v_streams = [s for s in streams if s.get("codec_type") == "video"]
            a_streams = [s for s in streams if s.get("codec_type") == "audio"]

            if not v_streams:
                raise ValueError(f"No video stream found in media artifact {resolved_path}")

            width = int(v_streams[0].get("width") or 1080)
            height = int(v_streams[0].get("height") or 1920)
            has_audio = len(a_streams) > 0
            raw_dur = fmt.get("duration") or v_streams[0].get("duration")
            try:
                duration = float(raw_dur) if raw_dur else 10.0
            except (ValueError, TypeError):
                duration = 10.0

            if not video.duration or video.duration == 0:
                video.duration = duration

            # Step 3B: Enforce 9:16 Vertical Aspect Ratio for YouTube Shorts
            # YouTube strictly requires a vertical (9:16 portrait) or square aspect ratio for Shorts.
            # Landscape videos (width > height, e.g. 1280x720, 1920x1080) are classified by YouTube as regular videos.
            is_vertical_short = (height > width) and ((height / width) >= 1.6)
            if not is_vertical_short:
                logger.info(f"[StudioDirect] Input video {video_id} is not 9:16 vertical ({width}x{height}). Reframing to 1080x1920 Short.")
                job.current_step = "Reframing to 9:16 vertical Short..."
                video.processing_step = "Reframing to 9:16 vertical Short..."
                session.commit()

                try:
                    from backend.services.layout_engine import LayoutEngine
                    import subprocess

                    reframed_dir = settings.OUTPUT_DIR / video_id / "reframed"
                    reframed_dir.mkdir(parents=True, exist_ok=True)
                    reframed_path = reframed_dir / "short_9_16.mp4"

                    reframe_mode_str = "blur_background"
                    if batch.config and isinstance(batch.config, dict):
                        reframe_mode_str = batch.config.get("reframe_mode") or "blur_background"

                    layout_plan = LayoutEngine.resolve_plan(
                        reframe_mode_str,
                        source_w=width,
                        source_h=height,
                        canvas_w=1080,
                        canvas_h=1920
                    )
                    filtergraph = LayoutEngine.build_render_graph(layout_plan, [resolved_path])
                    cmd = [
                        "ffmpeg", "-y", "-i", str(resolved_path),
                        "-filter_complex", filtergraph,
                        "-map", "[outv]",
                        "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "fast",
                        "-c:a", "aac",
                        "-sn",
                        "-movflags", "+faststart",
                        "-f", "mp4",
                        str(reframed_path),
                    ]
                    render_proc = subprocess.run(cmd, capture_output=True)
                    if render_proc.returncode == 0 and reframed_path.exists() and reframed_path.stat().st_size > 0:
                        resolved_path = reframed_path
                        width = 1080
                        height = 1920
                        logger.info(f"[StudioDirect] Successfully reframed video {video_id} to 1080x1920 vertical Short at {resolved_path}")
                    else:
                        err_msg = render_proc.stderr.decode("utf-8", errors="replace")[-500:] if render_proc.stderr else "unknown error"
                        logger.warning(f"[StudioDirect] Reframing to 9:16 failed ({err_msg}). Continuing with base media.")
                except Exception as reframe_err:
                    logger.warning(f"[StudioDirect] Reframing exception: {reframe_err}. Continuing with base media.")

            video.resolution = f"{width}x{height}"
            video.local_path = str(resolved_path)

            job.progress = 25
            job.current_step = "Transcribing audio content..."
            video.processing_progress = 25
            video.processing_step = "Transcribing audio content..."
            batch.worker_heartbeat = datetime.now(timezone.utc)
            session.commit()

            # Step 4: Whisper Transcription
            transcript_text = ""
            if has_audio:
                try:
                    trans_res = transcribe_video(resolved_path)
                    transcript_text = (trans_res.get("text") or "").strip()
                    logger.info(f"[StudioDirect] Transcribed video {video_id}: {len(transcript_text)} chars")
                except Exception as tr_err:
                    logger.warning(f"[StudioDirect] Transcription warning for {video_id}: {tr_err}. Using title fallback.")
                    transcript_text = ""
            else:
                logger.info(f"[StudioDirect] Video {video_id} has no audio stream. Skipping transcription.")

            job.progress = 45
            job.current_step = "Generating AI viral metadata..."
            video.processing_progress = 45
            video.processing_step = "Generating AI viral metadata..."
            batch.worker_heartbeat = datetime.now(timezone.utc)
            session.commit()

            # Step 5: AI Metadata Generation (Title, Description, SEO Tags, Pinned Comment)
            display_title = video.title or video.source_filename or "Short Video"
            if display_title.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                display_title = Path(display_title).stem

            meta = {}
            try:
                meta = _run_coro_safe(
                    generate_metadata(
                        transcript=transcript_text or f"Short video titled {display_title}",
                        clip_title=display_title,
                        clip_duration=duration,
                    )
                )
            except Exception as meta_err:
                logger.warning(f"[StudioDirect] AI metadata generation warning: {meta_err}. Using fallback.")
                meta = {
                    "title": f"{display_title[:50]} #Shorts",
                    "description": f"{transcript_text[:300]}\n\n#Shorts #viral #trending",
                    "tags": ["Shorts", "viral", "trending"],
                    "pinned_comment": "Subscribe for more amazing shorts! 👇",
                }

            ai_title = meta.get("title") or display_title
            ai_desc = meta.get("description") or ""
            ai_tags = meta.get("tags") or ["Shorts", "viral", "trending"]
            ai_pinned_comment = meta.get("pinned_comment") or ""

            video.title = ai_title

            # Create or update 1:1 Clip record
            clip = session.query(Clip).filter_by(video_id=video_id).first()
            if not clip:
                clip = Clip(
                    id=str(uuid.uuid4()),
                    video_id=video_id,
                    title=ai_title,
                    description=ai_desc,
                    start_time=0.0,
                    end_time=duration,
                    duration=duration,
                    score=1.0,
                    output_path=str(resolved_path),
                    transcript_segment=transcript_text[:1000] if transcript_text else None,
                    tags=json.dumps(ai_tags) if isinstance(ai_tags, list) else str(ai_tags),
                    pinned_comment=ai_pinned_comment,
                    metadata_status="ready",
                    privacy="private",
                    category="22",
                    license="youtube",
                    status=ClipStatus.COMPLETED.value,
                )
                session.add(clip)
            else:
                clip.title = ai_title
                clip.description = ai_desc
                clip.duration = duration
                clip.output_path = str(resolved_path)
                clip.tags = json.dumps(ai_tags) if isinstance(ai_tags, list) else str(ai_tags)
                clip.pinned_comment = ai_pinned_comment
                clip.metadata_status = "ready"
                clip.status = ClipStatus.COMPLETED.value
                clip.privacy = "private"

            session.commit()

            # Step 6: Multi-Destination Routing & Outro Concatenation & YouTube Upload
            target_destination_ids = destination_ids
            if not target_destination_ids and batch.config and isinstance(batch.config, dict):
                target_destination_ids = batch.config.get("destination_ids")

            published_count = 0
            if target_destination_ids:
                job.progress = 65
                job.current_step = "Preparing destination outros & publishing (Private)..."
                video.processing_progress = 65
                video.processing_step = "Publishing to YouTube (Private)..."
                batch.worker_heartbeat = datetime.now(timezone.utc)
                session.commit()

                dests = session.query(Channel).filter(
                    Channel.id.in_(target_destination_ids),
                    Channel.is_active == True
                ).all()

                if not dests:
                    logger.warning(f"[StudioDirect] Destinations {target_destination_ids} not found or inactive. Saving as draft.")
                    clip.publish_status = PublishStatus.DRAFT.value
                    session.commit()
                else:
                    for channel in dests:
                        upload_video_path = resolved_path
                        outro_applied_id = None

                        # Check for active outro on destination channel
                        if channel.active_outro_id:
                            active_outro = session.query(DestinationOutro).filter_by(
                                id=channel.active_outro_id,
                                is_active=True
                            ).first()
                            if active_outro:
                                dest_dir = settings.OUTPUT_DIR / video_id / "clips" / clip.id / "destinations" / str(channel.id)
                                dest_dir.mkdir(parents=True, exist_ok=True)
                                variant_path = dest_dir / "final.mp4"
                                logger.info(f"[StudioDirect] Rendering active outro {active_outro.id} for destination {channel.channel_name}")
                                try:
                                    render_clip_with_outro(
                                        base_video_path=resolved_path,
                                        output_path=variant_path,
                                        outro=active_outro,
                                        max_total_duration=180.0
                                    )
                                    upload_video_path = variant_path
                                    outro_applied_id = str(active_outro.id)
                                except Exception as outro_err:
                                    logger.error(f"[StudioDirect] Outro rendering failed: {outro_err}. Uploading base video.")
                                    upload_video_path = resolved_path

                        # Create or update PublishTarget row
                        pt = session.query(PublishTarget).filter_by(
                            clip_id=clip.id,
                            destination_id=channel.id
                        ).first()
                        if not pt:
                            pt = PublishTarget(
                                id=str(uuid.uuid4()),
                                clip_id=clip.id,
                                destination_id=channel.id,
                                status="publishing",
                                privacy="private",
                                publish_stage="publishing",
                                publish_progress=70.0,
                                publish_started_at=datetime.now(timezone.utc),
                                outro_applied_id=outro_applied_id,
                                rendered_video_path=str(upload_video_path),
                            )
                            session.add(pt)
                        else:
                            pt.status = "publishing"
                            pt.privacy = "private"
                            pt.publish_stage = "publishing"
                            pt.publish_progress = 70.0
                            pt.publish_started_at = datetime.now(timezone.utc)
                            pt.rendered_video_path = str(upload_video_path)
                            pt.outro_applied_id = outro_applied_id

                        session.commit()

                        # Upload to YouTube in Private mode
                        logger.info(f"[StudioDirect] Uploading to YouTube channel {channel.channel_name} ({channel.youtube_channel_id}) with privacy='private'")
                        upload_res = upload_short(
                            video_path=upload_video_path,
                            title=ai_title,
                            description=ai_desc,
                            tags=ai_tags,
                            privacy="private",
                            channel_id=channel.youtube_channel_id,
                            clip_id=clip.id,
                        )
                        yt_vid_id = upload_res.get("id") or upload_res.get("video_id")

                        pt.status = "completed"
                        pt.publish_stage = "published"
                        pt.publish_progress = 100.0
                        pt.youtube_video_id = yt_vid_id
                        pt.published_at = datetime.now(timezone.utc)
                        pt.publish_completed_at = datetime.now(timezone.utc)

                        clip.publish_status = PublishStatus.PUBLISHED.value
                        clip.youtube_short_id = yt_vid_id
                        clip.published_at = datetime.now(timezone.utc)
                        clip.publish_destination_id = channel.id
                        published_count += 1
                        session.commit()
                        logger.info(f"[StudioDirect] Successfully uploaded to YouTube: {yt_vid_id}")
            else:
                logger.info(f"[StudioDirect] No destinations specified. Saved as Draft.")
                clip.publish_status = PublishStatus.DRAFT.value
                session.commit()

            # Step 7: Mark completed and commit
            job.status = JobStatus.COMPLETED.value
            job.progress = 100
            final_step = "Published to YouTube (Private)" if published_count > 0 else "Completed (Draft)"
            job.current_step = final_step
            job.updated_at = datetime.now(timezone.utc)

            video.processing_status = VideoProcessingStatus.COMPLETED.value
            video.processing_progress = 100
            video.processing_step = final_step
            video.processing_completed_at = datetime.now(timezone.utc)
            video.processing_error = None
            session.commit()

        # Step 8: Trigger sequential advancement
        logger.info(f"[StudioDirect] Video {video_id} finished successfully. Advancing batch via on_studio_video_finished_task...")
        on_studio_video_finished_task.delay(batch_id=studio_batch_id, video_id=video_id, job_id=job_id)
        return {"status": "success", "video_id": video_id, "job_id": job_id}

    except Exception as e:
        logger.error(f"[StudioDirect] Error processing video {video_id}: {e}", exc_info=True)
        now_err = datetime.now(timezone.utc)
        err_msg = str(e)
        with SyncSessionLocal() as session:
            v = session.query(Video).filter_by(id=video_id).first()
            j = session.query(Job).filter_by(id=job_id).first()
            b = session.query(UploadBatch).filter_by(id=studio_batch_id).first()
            if j:
                j.status = JobStatus.FAILED.value
                j.error_message = err_msg
                j.current_step = f"Failed: {err_msg[:120]}"
                j.updated_at = now_err
            if v:
                v.processing_status = VideoProcessingStatus.FAILED.value
                v.processing_error = err_msg
                v.processing_step = f"Failed: {err_msg[:120]}"
                v.processing_completed_at = now_err
            if b:
                b.status = UploadBatchStatus.FAILED.value
                b.batch_error = f"Item {v.title if v else video_id} failed: {err_msg[:120]}"
                b.active_video_id = None
                b.worker_heartbeat = now_err
            session.commit()
        raise
