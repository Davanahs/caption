"""
backend.services.queue_manager
==============================
Centralized concurrency gate and FIFO queue manager for manual video processing.

Rule:
- At most MAX_CONCURRENT_MANUAL_JOBS (5) manual videos can be actively processing at once.
- When capacity is reached, new manual jobs are accepted with status='pending' and placed in a FIFO queue.
- The UI displays queue position: "Queued (#X in line - waiting for an active video to finish)".
- Terminal transitions (completed, failed, cancelled) or periodic heartbeats trigger automatic dequeuing.
- Monitored channel automation jobs (channel_id is set) bypass this limit.
"""

import json
import inspect
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.models import Job, JobStatus

logger = logging.getLogger("clipforge.queue_manager")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  [QueueManager] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

MAX_CONCURRENT_MANUAL_JOBS = 5

ACTIVE_PROCESSING_STATUSES = [
    JobStatus.DOWNLOADING.value,
    JobStatus.VALIDATING.value,
    JobStatus.TRANSCRIBING.value,
    JobStatus.ANALYZING.value,
    JobStatus.SELECTING.value,
    JobStatus.CLIPPING_IN_PROGRESS.value,
]


def is_manual_job_filter():
    """Return SQL filter matching manual jobs (no channel_id associated)."""
    return or_(Job.channel_id.is_(None), Job.channel_id == "")


def is_active_manual_job_filter():
    """
    Return SQL filter matching manual jobs currently occupying active processing capacity.
    Includes:
    - Jobs in active processing pipeline stages (downloading, validating, transcribing, analyzing, selecting, clipping)
    - Jobs dispatched to Celery awaiting worker execution (status='pending' AND celery_task_id IS NOT NULL)
    """
    return and_(
        is_manual_job_filter(),
        or_(
            Job.status.in_(ACTIVE_PROCESSING_STATUSES),
            and_(Job.status == JobStatus.PENDING.value, Job.celery_task_id.is_not(None)),
        ),
    )


def get_active_manual_jobs_count_sync(session: Session) -> int:
    """Return number of manual jobs currently actively processing in the pipeline."""
    query = (
        session.query(func.count(Job.id))
        .filter(is_active_manual_job_filter())
    )
    return query.scalar() or 0


async def get_active_manual_jobs_count_async(db: AsyncSession) -> int:
    """Async: Return number of manual jobs currently actively processing."""
    stmt = (
        select(func.count(Job.id))
        .where(is_active_manual_job_filter())
    )
    result = await db.execute(stmt)
    if hasattr(result, "scalar"):
        val = result.scalar()
        if inspect.isawaitable(val):
            val = await val
        try:
            return int(val) if val is not None else 0
        except (TypeError, ValueError):
            return 0
    return 0


def get_pending_queue_position_sync(session: Session, job_id: Optional[str] = None) -> int:
    """
    Return queue position (1-based index) among pending manual jobs waiting in queue.
    If job_id is provided, counts how many pending manual jobs were created before this one + 1.
    """
    if job_id:
        target_job = session.query(Job).filter_by(id=job_id).first()
        if target_job:
            earlier_count = (
                session.query(func.count(Job.id))
                .filter(is_manual_job_filter())
                .filter(Job.status == JobStatus.PENDING.value)
                .filter(Job.celery_task_id.is_(None))
                .filter(Job.created_at < target_job.created_at)
                .scalar()
            ) or 0
            return earlier_count + 1

    total_pending = (
        session.query(func.count(Job.id))
        .filter(is_manual_job_filter())
        .filter(Job.status == JobStatus.PENDING.value)
        .filter(Job.celery_task_id.is_(None))
        .scalar()
    ) or 0
    return total_pending + 1


async def get_pending_queue_position_async(db: AsyncSession, job_id: Optional[str] = None) -> int:
    """Async: Return queue position (1-based index) among pending manual jobs waiting in queue."""
    if job_id:
        target_stmt = select(Job).where(Job.id == job_id)
        res = await db.execute(target_stmt)
        target_job = res.scalar_one_or_none() if hasattr(res, "scalar_one_or_none") else None
        if inspect.isawaitable(target_job):
            target_job = await target_job
        if target_job and hasattr(target_job, "created_at"):
            stmt = (
                select(func.count(Job.id))
                .where(is_manual_job_filter())
                .where(Job.status == JobStatus.PENDING.value)
                .where(Job.celery_task_id.is_(None))
                .where(Job.created_at < target_job.created_at)
            )
            count_res = await db.execute(stmt)
            val = count_res.scalar() if hasattr(count_res, "scalar") else 0
            if inspect.isawaitable(val):
                val = await val
            try:
                return (int(val) if val is not None else 0) + 1
            except (TypeError, ValueError):
                return 1

    stmt = (
        select(func.count(Job.id))
        .where(is_manual_job_filter())
        .where(Job.status == JobStatus.PENDING.value)
        .where(Job.celery_task_id.is_(None))
    )
    res = await db.execute(stmt)
    val = res.scalar() if hasattr(res, "scalar") else 0
    if inspect.isawaitable(val):
        val = await val
    try:
        return (int(val) if val is not None else 0) + 1
    except (TypeError, ValueError):
        return 1


def format_queue_step(position: int) -> str:
    """Return human-readable stage indicator for queued videos."""
    return f"Queued (#{position} in line - waiting for an active video to finish)"


def build_dispatch_kwargs_from_job(job: Job) -> Dict[str, Any]:
    """Reconstruct Celery task kwargs from job config and attributes."""
    config_dict = {}
    if job.config:
        try:
            config_dict = json.loads(job.config) if isinstance(job.config, str) else job.config
        except Exception:
            config_dict = {}

    if isinstance(config_dict, dict) and "dispatch_kwargs" in config_dict:
        kwargs = dict(config_dict["dispatch_kwargs"])
        kwargs["job_id"] = job.id
        return kwargs

    is_youtube = bool(job.source_url and ("youtube.com" in job.source_url or "youtu.be" in job.source_url))
    kwargs: Dict[str, Any] = {
        "job_id": job.id,
        "clip_mode": config_dict.get("clip_mode", "ai_highlights"),
        "reframe_mode": config_dict.get("reframe_mode"),
        "hook_title": config_dict.get("hook_title"),
        "max_clip_duration": config_dict.get("max_clip_duration"),
        "enable_broll": config_dict.get("enable_broll", False),
        "enable_hook": config_dict.get("enable_hook", False),
        "target_language": config_dict.get("target_language"),
        "publish_destination_id": config_dict.get("publish_destination_id"),
        "destination_ids": config_dict.get("destination_ids"),
        "channel_id": job.channel_id,
        "target_duration": config_dict.get("target_duration"),
        "segmentation_strategy": config_dict.get("segmentation_strategy"),
        "regions": config_dict.get("regions"),
        "shot_schedule": config_dict.get("shot_schedule"),
        "podcast_composition": config_dict.get("podcast_composition"),
    }
    num_clips = config_dict.get("num_clips") or config_dict.get("clips_count")
    if config_dict.get("clip_mode") != "equal_split":
        kwargs["num_clips"] = num_clips
        kwargs["clips_count"] = num_clips

    if is_youtube:
        kwargs["youtube_url"] = job.source_url
    else:
        kwargs["local_path"] = config_dict.get("local_path") or job.source_url

    return kwargs


def dispatch_celery_job(job_id: str, kwargs: Dict[str, Any]) -> str:
    """Dispatch Celery task and return task_id."""
    from backend.tasks.orchestration import start_video_processing_task
    task = start_video_processing_task.apply_async(kwargs=kwargs, task_id=job_id)
    return task.id


def update_pending_queue_positions_sync(session: Session) -> None:
    """Recalculate and update current_step for all pending manual jobs."""
    pending_jobs = (
        session.query(Job)
        .filter(is_manual_job_filter())
        .filter(Job.status == JobStatus.PENDING.value)
        .filter(Job.celery_task_id.is_(None))
        .order_by(Job.created_at.asc())
        .all()
    )
    for idx, job in enumerate(pending_jobs, start=1):
        job.current_step = format_queue_step(idx)
    session.commit()


async def update_pending_queue_positions_async(db: AsyncSession) -> None:
    """Async: Recalculate and update current_step for all pending manual jobs."""
    stmt = (
        select(Job)
        .where(is_manual_job_filter())
        .where(Job.status == JobStatus.PENDING.value)
        .where(Job.celery_task_id.is_(None))
        .order_by(Job.created_at.asc())
    )
    result = await db.execute(stmt)
    pending_jobs = result.scalars().all()
    for idx, job in enumerate(pending_jobs, start=1):
        job.current_step = format_queue_step(idx)
    await db.commit()


def dispatch_next_queued_manual_jobs_sync(session: Optional[Session] = None) -> int:
    """
    Synchronous FIFO Queue Drain:
    Checks if active manual processing jobs < MAX_CONCURRENT_MANUAL_JOBS (5).
    If slots are available, claims and dispatches the oldest pending manual jobs.
    Returns the number of jobs dispatched.
    """
    from backend.models.database import SyncSessionLocal

    owns_session = session is None
    s = session or SyncSessionLocal()
    dispatched_count = 0

    try:
        active_count = get_active_manual_jobs_count_sync(s)
        available_slots = MAX_CONCURRENT_MANUAL_JOBS - active_count

        if available_slots <= 0:
            logger.debug(f"Concurrency limit reached ({active_count}/{MAX_CONCURRENT_MANUAL_JOBS} active). No slots.")
            update_pending_queue_positions_sync(s)
            return 0

        # Query up to available_slots oldest pending manual jobs that have not been dispatched
        pending_jobs = (
            s.query(Job)
            .filter(is_manual_job_filter())
            .filter(Job.status == JobStatus.PENDING.value)
            .filter(Job.celery_task_id.is_(None))
            .order_by(Job.created_at.asc())
            .limit(available_slots)
            .all()
        )

        for job in pending_jobs:
            try:
                kwargs = build_dispatch_kwargs_from_job(job)
                task_id = dispatch_celery_job(job.id, kwargs)
                job.celery_task_id = task_id
                job.current_step = "Starting pipeline..."
                job.updated_at = datetime.now(timezone.utc)
                dispatched_count += 1
                logger.info(f"Dequeued and dispatched manual job {job.id} (task_id={task_id}).")
            except Exception as dispatch_err:
                logger.error(f"Failed to dispatch queued job {job.id}: {dispatch_err}")

        s.commit()

        # Update remaining queued jobs' numbers
        update_pending_queue_positions_sync(s)

    except Exception as e:
        logger.error(f"Error in dispatch_next_queued_manual_jobs_sync: {e}")
        s.rollback()
    finally:
        if owns_session:
            s.close()

    return dispatched_count


async def dispatch_next_queued_manual_jobs_async(db: Optional[AsyncSession] = None) -> int:
    """
    Async FIFO Queue Drain:
    Checks if active manual processing jobs < MAX_CONCURRENT_MANUAL_JOBS (5).
    If slots are available, claims and dispatches the oldest pending manual jobs.
    Returns the number of jobs dispatched.
    """
    from backend.models.database import AsyncSessionLocal

    owns_db = db is None
    session = db or AsyncSessionLocal()
    dispatched_count = 0

    try:
        active_count = await get_active_manual_jobs_count_async(session)
        available_slots = MAX_CONCURRENT_MANUAL_JOBS - active_count

        if available_slots <= 0:
            await update_pending_queue_positions_async(session)
            return 0

        stmt = (
            select(Job)
            .where(is_manual_job_filter())
            .where(Job.status == JobStatus.PENDING.value)
            .where(Job.celery_task_id.is_(None))
            .order_by(Job.created_at.asc())
            .limit(available_slots)
        )
        result = await session.execute(stmt)
        pending_jobs = result.scalars().all()

        for job in pending_jobs:
            try:
                kwargs = build_dispatch_kwargs_from_job(job)
                task_id = dispatch_celery_job(job.id, kwargs)
                job.celery_task_id = task_id
                job.current_step = "Starting pipeline..."
                job.updated_at = datetime.now(timezone.utc)
                dispatched_count += 1
                logger.info(f"[Async] Dequeued and dispatched manual job {job.id} (task_id={task_id}).")
            except Exception as dispatch_err:
                logger.error(f"Failed to dispatch queued job {job.id}: {dispatch_err}")

        await session.commit()
        await update_pending_queue_positions_async(session)

    except Exception as e:
        logger.error(f"Error in dispatch_next_queued_manual_jobs_async: {e}")
        await session.rollback()
    finally:
        if owns_db:
            await session.close()

    return dispatched_count


def trigger_queue_drain_background() -> None:
    """
    Non-blocking trigger for FIFO queue drain.
    Can be safely called inside Celery tasks or callbacks.
    """
    try:
        from backend.tasks.orchestration import celery_app
        drain_manual_queue_task.delay()
    except Exception as e:
        logger.warning(f"Failed to dispatch drain_manual_queue_task via Celery: {e}. Executing inline...")
        dispatch_next_queued_manual_jobs_sync()


# Celery task for background queue draining
from backend.tasks.celery_app import celery_app

@celery_app.task(name="backend.services.queue_manager.drain_manual_queue")
def drain_manual_queue_task():
    """Celery task invoked to drain the queued manual jobs."""
    dispatched = dispatch_next_queued_manual_jobs_sync()
    return {"dispatched": dispatched}
