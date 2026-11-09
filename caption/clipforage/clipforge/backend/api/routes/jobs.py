"""API Routes — Jobs (real-time status polling + manual cancel)"""
import asyncio
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, case
from backend.models.database import get_db, AsyncSessionLocal
from backend.models.models import Job, JobStatus, Video
from backend.services.downloader import extract_youtube_id
from backend.core.sanitizer import sanitize_user_facing_error

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
YOUTUBE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")
SYNTHETIC_PATTERNS = re.compile(
    r"^(yt_dup|yt_vid|yt_test|yt_race|yt_combo|yt_err|yt_cust|mock|stale|errvid|combo|test|phase_artifact|vid_repair)",
    re.IGNORECASE
)


def format_ist(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KOLKATA_TZ).strftime("%d %b %Y, %I:%M:%S %p IST")


def is_valid_youtube_id(yt_id: str | None) -> bool:
    """Validate genuine 11-char YouTube ID while strictly rejecting synthetic/test patterns."""
    if not yt_id or not isinstance(yt_id, str):
        return False
    yt_id = yt_id.strip()
    if not YOUTUBE_ID_REGEX.match(yt_id):
        return False
    if SYNTHETIC_PATTERNS.search(yt_id):
        return False
    return True


def resolve_thumbnail_url(job: Job, video: Video | None = None) -> str | None:
    """
    Resolve authentic video thumbnail with deterministic hierarchy:
    1. Reuse existing persisted thumbnail URL on Video record if valid HTTP URL.
    2. Extract and validate YouTube ID from Job.source_url.
    3. Validate and use Video.youtube_id if present.
    4. Validate and use Video.youtube_url if present.
    5. Return None (neutral fallback placeholder on frontend) for invalid/synthetic IDs or local uploads.
    """
    # 1. Reuse existing persisted thumbnail URL
    if video and video.thumbnail_url and video.thumbnail_url.startswith("http"):
        return video.thumbnail_url

    # 2. Extract from job source_url
    if job.source_url:
        yt_id = extract_youtube_id(job.source_url)
        if is_valid_youtube_id(yt_id):
            return f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"

    # 3. Check video.youtube_id
    if video and is_valid_youtube_id(video.youtube_id):
        return f"https://i.ytimg.com/vi/{video.youtube_id}/hqdefault.jpg"

    # 4. Check video.youtube_url
    if video and video.youtube_url:
        yt_id = extract_youtube_id(video.youtube_url)
        if is_valid_youtube_id(yt_id):
            return f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"

    return None


def _job_dict(j: Job, video: Video | None = None) -> dict:
    thumb = resolve_thumbnail_url(j, video)
    return {
        "id": j.id,
        "video_id": j.video_id,
        "source_url": j.source_url,
        "source_title": j.source_title,
        "status": j.status,
        "progress": j.progress,
        "current_step": j.current_step,
        "error_message": sanitize_user_facing_error(j.error_message),
        "celery_task_id": j.celery_task_id,
        "config": json.loads(j.config) if j.config else {},
        "pipeline_started_at": j.pipeline_started_at.isoformat() if j.pipeline_started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "is_test": j.is_test,
        "thumbnail_url": thumb,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "created_at_ist": format_ist(j.created_at),
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        "updated_at_ist": format_ist(j.updated_at),
    }


@router.get("/")
async def list_jobs(
    status: str | None = None,
    filter_type: str | None = None,
    include_test: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    query = select(Job, Video).outerjoin(Video, Job.video_id == Video.id)
    if not include_test:
        query = query.where(Job.is_test == False)
    if status:
        query = query.where(Job.status == status)

    terminal_statuses = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]
    if filter_type == "active":
        query = query.where(Job.status.not_in(terminal_statuses))
    elif filter_type == "history":
        query = query.where(Job.status.in_(terminal_statuses))

    query = query.order_by(desc(Job.created_at), desc(Job.id)).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    return [_job_dict(j, v) for j, v in rows]


@router.get("/active")
async def list_active_jobs(
    include_test: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Return all non-terminal active or pending jobs ordered newest-first."""
    terminal = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]
    query = select(Job, Video).outerjoin(Video, Job.video_id == Video.id).where(Job.status.not_in(terminal))
    if not include_test:
        query = query.where(Job.is_test == False)
    query = query.order_by(desc(Job.created_at), desc(Job.id))
    result = await db.execute(query)
    rows = result.all()
    return [_job_dict(j, v) for j, v in rows]


@router.get("/history")
async def list_job_history(
    limit: int = 50,
    include_test: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Return all terminal jobs (completed, failed, cancelled) ordered newest-first by creation time."""
    terminal = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]
    query = select(Job, Video).outerjoin(Video, Job.video_id == Video.id).where(Job.status.in_(terminal))
    if not include_test:
        query = query.where(Job.is_test == False)
    query = query.order_by(desc(Job.created_at), desc(Job.id)).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    return [_job_dict(j, v) for j, v in rows]


@router.get("/queue-count")
async def queue_count(include_test: bool = False, db: AsyncSession = Depends(get_db)):
    """Number of jobs currently pending or in-progress."""
    terminal = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]
    query = select(func.count()).select_from(Job).where(Job.status.not_in(terminal))
    if not include_test:
        query = query.where(Job.is_test == False)
    result = await db.execute(query)
    return {"count": result.scalar_one()}


@router.get("/stats")
async def get_job_stats(include_test: bool = False, db: AsyncSession = Depends(get_db)):
    """
    Return a live pipeline queue health summary.
    GET /api/jobs/stats
    """
    where_cond = [Job.is_test == False] if not include_test else []

    query = select(
        func.count().label("total"),
        func.sum(case((Job.status.in_([JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value]), 1), else_=0)).label("done"),
        func.sum(case(((Job.status == JobStatus.FAILED.value) & (Job.error_message != "Cancelled by user"), 1), else_=0)).label("failed"),
        func.sum(case(((Job.status == JobStatus.CANCELLED.value) | ((Job.status == JobStatus.FAILED.value) & (Job.error_message == "Cancelled by user")), 1), else_=0)).label("cancelled"),
        func.sum(case((Job.status.in_([
            JobStatus.DOWNLOADING.value,
            JobStatus.VALIDATING.value,
            JobStatus.TRANSCRIBING.value,
            JobStatus.ANALYZING.value,
            JobStatus.SELECTING.value,
            JobStatus.CLIPPING_IN_PROGRESS.value
        ]), 1), else_=0)).label("active"),
        func.sum(case((Job.status == JobStatus.PENDING.value, 1), else_=0)).label("pending"),
    ).select_from(Job)

    if where_cond:
        query = query.where(*where_cond)

    result = await db.execute(query)
    row = result.one()

    # Last genuine failed job info (NOT cancelled)
    last_fail_query = (
        select(Job)
        .where(
            Job.status == JobStatus.FAILED.value,
            Job.error_message != "Cancelled by user"
        )
    )
    if where_cond:
        last_fail_query = last_fail_query.where(*where_cond)
    last_fail_query = last_fail_query.order_by(desc(Job.updated_at)).limit(1)

    last_fail_result = await db.execute(last_fail_query)
    last_fail = last_fail_result.scalar_one_or_none()

    return {
        "queue": {
            "total": row.total or 0,
            "active": row.active or 0,
            "pending": row.pending or 0,
            "done": row.done or 0,
            "failed": row.failed or 0,
            "cancelled": row.cancelled or 0,
        },
        "last_failure": {
            "job_id": last_fail.id if last_fail else None,
            "source_title": last_fail.source_title if last_fail else None,
            "error": sanitize_user_facing_error(last_fail.error_message) if last_fail else None,
            "failed_at": last_fail.updated_at.isoformat() if last_fail and last_fail.updated_at else None,
        } if last_fail else None,
    }


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job, Video).outerjoin(Video, Job.video_id == Video.id).where(Job.id == job_id))
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    j, v = row
    return _job_dict(j, v)


@router.delete("/{job_id}")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Cancel a job from the queue.
    - If the job is already cancelled, returns idempotently.
    - If the job has completed, rejects cancellation.
    - If the job has a Celery task running, revokes it.
    - Revokes and fails any active subtasks in task_executions.
    - Marks the job as cancelled with a user-cancelled message in the DB.
    - Updates associated video processing status if active.
    - Preserves job and task execution audit records in the database.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.CANCELLED.value:
        return {
            "message": "Job already cancelled",
            "job_id": job_id,
            "status": "cancelled",
            "already_cancelled": True,
        }

    if job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value):
        raise HTTPException(status_code=400, detail="Cannot cancel a completed job")

    # Revoke Celery task if present on job
    if job.celery_task_id:
        try:
            from backend.tasks.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")
            print(f"[ClipForge] Revoked Celery task {job.celery_task_id} for job {job_id}")
        except Exception as e:
            print(f"[ClipForge] Could not revoke Celery task: {e}")

    # Revoke and fail any running subtasks in task_executions
    try:
        from backend.models.models import TaskExecution, TaskExecutionStatus
        from backend.tasks.celery_app import celery_app
        te_res = await db.execute(
            select(TaskExecution).where(
                TaskExecution.job_id == job_id,
                TaskExecution.status.in_([TaskExecutionStatus.PENDING.value, TaskExecutionStatus.RUNNING.value])
            )
        )
        active_tasks = te_res.scalars().all()
        for t in active_tasks:
            if t.task_id:
                try:
                    celery_app.control.revoke(t.task_id, terminate=True, signal="SIGTERM")
                except Exception:
                    pass
            t.status = TaskExecutionStatus.FAILED.value
            t.failure_reason = "Cancelled by user"
    except Exception as te_err:
        print(f"[ClipForge] Could not revoke subtasks: {te_err}")

    # Transition Job to terminal cancelled state
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    job.status = JobStatus.CANCELLED.value
    job.current_step = "Cancelled"
    job.error_message = "Cancelled by user"
    job.completed_at = now
    job.updated_at = now

    # Update associated Video processing status if in-flight
    if job.video_id:
        from backend.models.models import Video, VideoProcessingStatus
        v_res = await db.execute(select(Video).where(Video.id == job.video_id))
        video = v_res.scalar_one_or_none()
        if video and video.processing_status in (VideoProcessingStatus.QUEUED.value, VideoProcessingStatus.PROCESSING.value):
            video.processing_status = VideoProcessingStatus.CANCELLED.value
            video.processing_error = "Cancelled by user"

    await db.commit()

    # Trigger queue drain to let next queued manual job start
    try:
        from backend.services.queue_manager import trigger_queue_drain_background
        trigger_queue_drain_background()
    except Exception as q_err:
        print(f"[QueueManager] Trigger drain warning on cancel: {q_err}")

    return {"message": "Job cancelled successfully", "job_id": job_id, "status": "cancelled"}


@router.websocket("/ws/{job_id}")
async def job_status_ws(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint — streams real-time job status for a given job_id.
    Sends a JSON update every second until job reaches terminal state (done/failed).
    """
    await websocket.accept()
    terminal_statuses = {JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}
    last_payload: str = ""

    try:
        while True:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Job, Video).outerjoin(Video, Job.video_id == Video.id).where(Job.id == job_id))
                row = result.first()

            if row is None:
                await websocket.send_text(json.dumps({"error": "Job not found", "job_id": job_id}))
                break

            job, video = row
            payload = json.dumps(_job_dict(job, video))

            # Only push if something changed (avoids unnecessary re-renders)
            if payload != last_payload:
                await websocket.send_text(payload)
                last_payload = payload

            # Close gracefully once terminal
            if job.status in terminal_statuses:
                break

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        pass  # Client closed connection — clean exit
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"error": str(e), "job_id": job_id}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/{job_id}/retry")
async def retry_failed_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Manually retry a failed job by re-submitting it as a fresh Celery task.
    POST /api/jobs/{job_id}/retry
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not in 'failed' state (current: '{job.status}'). Only failed jobs can be retried."
        )

    # Determine source type and config
    config = {}
    if job.config:
        try:
            config = json.loads(job.config)
        except Exception:
            pass

    source_type = config.get("source_type")
    raw_source = job.source_url or ""
    is_youtube = False

    from backend.services.downloader import extract_youtube_id
    if source_type == "youtube":
        is_youtube = True
    elif source_type == "local":
        is_youtube = False
    else:
        # Infer from source_url
        if raw_source.startswith("http://") or raw_source.startswith("https://") or extract_youtube_id(raw_source):
            is_youtube = True
        else:
            is_youtube = False

    resolved_local_path = None
    if is_youtube:
        if not raw_source:
            raise HTTPException(status_code=400, detail="Job has no source_url — cannot retry without original YouTube URL")

        # Guard: Check ClipForge-generated Short provenance
        from backend.services.provenance import check_is_clipforge_short
        is_short, cf_clip, parent_v = await check_is_clipforge_short(db, raw_source)
        if is_short:
            parent_title = parent_v.title if parent_v else "Original Source Video"
            parent_id = parent_v.youtube_id if parent_v else (cf_clip.video_id if cf_clip else "unknown")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot retry job {job_id}: the input '{raw_source}' is a ClipForge-generated output Short "
                    f"(origin: '{parent_title}', ID: {parent_id}). Output Shorts cannot be processed as source inputs. "
                    f"To re-generate clips, retry or re-process the original source video instead."
                )
            )
    else:
        # Local upload source: locate and verify file on disk
        from pathlib import Path
        from backend.core.config import settings
        candidate_paths = []
        if config.get("local_path"):
            candidate_paths.append(Path(config["local_path"]))

        # Check Video record if linked
        if job.video_id:
            vq = await db.execute(select(Video).where(Video.id == job.video_id))
            vid_rec = vq.scalar_one_or_none()
            if vid_rec and vid_rec.local_path:
                candidate_paths.append(Path(vid_rec.local_path))
                candidate_paths.append(settings.UPLOAD_DIR / vid_rec.local_path)
                candidate_paths.append(settings.STORAGE_DIR / vid_rec.local_path)

        # Check standard upload dir by job_id
        candidate_paths.append(settings.UPLOAD_DIR / job_id / "video.mp4")
        if job.video_id:
            candidate_paths.append(settings.UPLOAD_DIR / job.video_id / "video.mp4")

        # Check raw_source as path
        if raw_source:
            candidate_paths.append(Path(raw_source))

        for cp in candidate_paths:
            try:
                if cp.exists() and cp.is_file() and cp.stat().st_size > 0:
                    resolved_local_path = str(cp.resolve())
                    break
            except Exception:
                pass

        if not resolved_local_path:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot retry local upload job {job_id}: the retained original file has expired or was removed "
                    f"from disk. Please upload the file again to start a new job."
                )
            )

    # Reset job status to pending
    job.status = JobStatus.PENDING.value
    job.progress = 0
    job.current_step = "Re-queued for retry"
    job.error_message = None
    await db.commit()

    # Re-queue as a fresh Celery task
    try:
        from backend.tasks.orchestration import start_video_processing_task

        kwargs = {
            "job_id": job.id,
            "clip_mode": config.get("clip_mode", "ai_highlights"),
            "max_clip_duration": config.get("max_clip_duration"),
            "target_duration": config.get("target_duration"),
            "segmentation_strategy": config.get("segmentation_strategy"),
            "reframe_mode": config.get("reframe_mode"),
            "enable_broll": config.get("enable_broll", False),
            "enable_hook": config.get("enable_hook", False),
            "target_language": config.get("target_language"),
            "clips_count": config.get("clips_count"),
            "num_clips": config.get("clips_count"),
            "publish_destination_id": config.get("publish_destination_id"),
        }

        if is_youtube:
            kwargs["youtube_url"] = raw_source
        else:
            kwargs["local_path"] = resolved_local_path

        # Update config with dispatch kwargs
        config["dispatch_kwargs"] = kwargs
        job.config = json.dumps(config)

        from backend.services.queue_manager import (
            get_active_manual_jobs_count_async,
            get_pending_queue_position_async,
            format_queue_step,
            MAX_CONCURRENT_MANUAL_JOBS,
            dispatch_celery_job,
        )

        active_count = await get_active_manual_jobs_count_async(db)
        if active_count < MAX_CONCURRENT_MANUAL_JOBS:
            task = start_video_processing_task.apply_async(
                kwargs=kwargs,
                task_id=job.id
            )
            job.celery_task_id = task.id
            job.current_step = "Queued"
            await db.commit()
            return {
                "status": "retried",
                "job_id": job.id,
                "source_type": "youtube" if is_youtube else "local",
                "new_celery_task_id": task.id,
                "source": raw_source if is_youtube else resolved_local_path,
                "message": "Job re-queued successfully. Monitor progress at GET /api/jobs/{job_id}",
                "queued": False
            }
        else:
            position = await get_pending_queue_position_async(db, job.id)
            job.celery_task_id = None
            job.current_step = format_queue_step(position)
            await db.commit()
            return {
                "status": "queued",
                "job_id": job.id,
                "source_type": "youtube" if is_youtube else "local",
                "new_celery_task_id": None,
                "source": raw_source if is_youtube else resolved_local_path,
                "message": f"Job queued (#{position} in line - waiting for an active video to finish)",
                "queued": True,
                "queue_position": position
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-queue job: {e}")
