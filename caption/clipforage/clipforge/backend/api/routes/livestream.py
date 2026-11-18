"""
Live Stream API Routes — Endpoints for validating YouTube livestreams, starting monitoring,
tracking real-time progress, stopping, and resuming live clipping.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from backend.models.database import get_db
from backend.models.models import LiveStreamJob, LiveStreamSegment, Video, Clip
from backend.services.livestream_service import validate_livestream, get_livestream_metadata
from backend.tasks.livestream_tasks import process_livestream_segment_task
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/livestream", tags=["Live Streaming"])


class ValidateRequest(BaseModel):
    url: str


class StartMonitoringRequest(BaseModel):
    youtube_url: str
    clip_count: int = 10
    clip_generation_mode: str = "ai_highlights"  # "ai_highlights" | "equal_split"


@router.post("/validate")
async def validate_url_endpoint(req: ValidateRequest, db: AsyncSession = Depends(get_db)):
    """
    Validates a YouTube livestream URL.
    Checks live status, detects upcoming/ended/live, and checks if already actively monitored.
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL cannot be empty")

    res = await validate_livestream(url, db)
    if not res.get("valid"):
        raise HTTPException(
            status_code=res.get("status_code", 400),
            detail=res.get("error", "Invalid YouTube livestream URL")
        )
    return res


@router.post("/start")
async def start_monitoring_endpoint(req: StartMonitoringRequest, db: AsyncSession = Depends(get_db)):
    """
    Initializes a new live stream monitoring job and triggers the first processing batch.
    """
    url = req.youtube_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")

    # 1. Validate stream
    val_res = await validate_livestream(url, db)
    if not val_res.get("valid"):
        raise HTTPException(status_code=400, detail=val_res.get("error", "Invalid URL"))

    if val_res.get("is_already_monitored"):
        raise HTTPException(
            status_code=409,
            detail=f"This livestream is already actively monitored (Job: {val_res.get('existing_job_id')})."
        )

    yt_id = val_res["youtube_id"]
    title = val_res["title"]
    thumb = val_res["thumbnail_url"]
    channel_name = val_res["channel_name"]
    channel_id = val_res["channel_id"]
    is_live = val_res["is_live"]
    live_status = val_res["live_status"]
    raw_dur = float(val_res["duration"] or 0.0)

    # 2. Create parent Video record (so clips in Clip table link to an authentic Video)
    video_id = str(uuid.uuid4())
    video = Video(
        id=video_id,
        title=title,
        youtube_url=url,
        youtube_id=yt_id,
        thumbnail_url=thumb,
        duration=raw_dur,
        channel_id=channel_id,
        transcription_status="pending",
        scene_detection_status="pending",
    )
    db.add(video)

    # 3. Create LiveStreamJob
    job_id = str(uuid.uuid4())
    job = LiveStreamJob(
        id=job_id,
        video_id=video_id,
        youtube_url=url,
        youtube_id=yt_id,
        video_title=title,
        thumbnail_url=thumb,
        channel_name=channel_name,
        channel_id=channel_id,
        status="processing",
        live_status=live_status if live_status else ("is_live" if is_live else "not_live"),
        current_step="Starting live stream monitoring pipeline...",
        total_duration=raw_dur,
        processed_until=0.0,
        newly_detected_duration=0.0,
        clips_count=max(1, min(50, req.clip_count)),
        clip_generation_mode="equal_split" if req.clip_generation_mode == "equal_split" else "ai_highlights",
        monitoring_interval_minutes=20,
        next_check_at=datetime.now(timezone.utc) + timedelta(minutes=20),
        stop_requested=False,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 4. Dispatch initial background task
    try:
        task = process_livestream_segment_task.delay(job_id=job.id, is_initial=True)
        job.active_task_id = task.id
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to enqueue livestream Celery task: {e}")

    return {
        "success": True,
        "job_id": job.id,
        "video_id": video.id,
        "title": job.video_title,
        "status": job.status,
        "message": "Live stream monitoring started successfully."
    }


@router.get("/jobs")
async def list_livestream_jobs(db: AsyncSession = Depends(get_db)):
    """
    Returns all livestream jobs with summary stats.
    """
    stmt = (
        select(LiveStreamJob)
        .options(selectinload(LiveStreamJob.segments))
        .order_by(desc(LiveStreamJob.created_at))
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()

    items = []
    for j in jobs:
        # Fetch clip count for this job's video
        clip_count = 0
        if j.video_id:
            c_stmt = select(Clip).where(Clip.video_id == j.video_id)
            c_res = await db.execute(c_stmt)
            clip_count = len(c_res.scalars().all())

        items.append({
            "id": j.id,
            "video_id": j.video_id,
            "youtube_url": j.youtube_url,
            "youtube_id": j.youtube_id,
            "video_title": j.video_title,
            "thumbnail_url": j.thumbnail_url,
            "channel_name": j.channel_name,
            "status": j.status,
            "live_status": j.live_status,
            "current_step": j.current_step,
            "total_duration": j.total_duration,
            "processed_until": j.processed_until,
            "clips_count": j.clips_count,
            "clip_generation_mode": j.clip_generation_mode,
            "monitoring_interval_minutes": j.monitoring_interval_minutes,
            "next_check_at": j.next_check_at.isoformat() if j.next_check_at else None,
            "last_processed_at": j.last_processed_at.isoformat() if j.last_processed_at else None,
            "stop_requested": j.stop_requested,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "clips_generated": clip_count,
            "segments_count": len(j.segments)
        })

    return {"items": items, "total": len(items)}


@router.get("/active")
async def get_active_livestream_jobs(db: AsyncSession = Depends(get_db)):
    """
    Returns currently active livestream monitoring jobs (status: monitoring, processing, waiting).
    Used by the Live Streaming page and Main Dashboard.
    """
    stmt = (
        select(LiveStreamJob)
        .where(LiveStreamJob.status.in_(["monitoring", "processing", "waiting"]))
        .order_by(desc(LiveStreamJob.updated_at))
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()

    items = []
    for j in jobs:
        clip_count = 0
        if j.video_id:
            c_stmt = select(Clip).where(Clip.video_id == j.video_id)
            c_res = await db.execute(c_stmt)
            clip_count = len(c_res.scalars().all())

        items.append({
            "id": j.id,
            "video_id": j.video_id,
            "youtube_url": j.youtube_url,
            "youtube_id": j.youtube_id,
            "video_title": j.video_title,
            "thumbnail_url": j.thumbnail_url,
            "channel_name": j.channel_name,
            "status": j.status,
            "live_status": j.live_status,
            "current_step": j.current_step,
            "total_duration": j.total_duration,
            "processed_until": j.processed_until,
            "clips_count": j.clips_count,
            "clip_generation_mode": j.clip_generation_mode,
            "monitoring_interval_minutes": j.monitoring_interval_minutes,
            "next_check_at": j.next_check_at.isoformat() if j.next_check_at else None,
            "last_processed_at": j.last_processed_at.isoformat() if j.last_processed_at else None,
            "clips_generated": clip_count,
            "created_at": j.created_at.isoformat() if j.created_at else None
        })

    return {"active_jobs": items, "count": len(items)}


@router.get("/{job_id}")
async def get_livestream_job_details(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns comprehensive details of a live stream job: timeline, segments, and generated clips.
    """
    stmt = (
        select(LiveStreamJob)
        .options(selectinload(LiveStreamJob.segments))
        .where(LiveStreamJob.id == job_id)
    )
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Live stream job not found")

    # Fetch generated clips
    clips_list = []
    if job.video_id:
        c_stmt = select(Clip).where(Clip.video_id == job.video_id).order_by(desc(Clip.created_at))
        c_res = await db.execute(c_stmt)
        for c in c_res.scalars().all():
            clips_list.append({
                "id": c.id,
                "video_id": c.video_id,
                "title": c.title,
                "description": c.description,
                "start_time": c.start_time,
                "end_time": c.end_time,
                "duration": c.duration,
                "score": c.score,
                "output_path": c.output_path,
                "thumbnail_path": c.thumbnail_path,
                "status": c.status,
                "publish_status": c.publish_status,
                "created_at": c.created_at.isoformat() if c.created_at else None
            })

    # Format segments
    segments_list = []
    for s in job.segments:
        segments_list.append({
            "id": s.id,
            "segment_index": s.segment_index,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "duration": s.duration,
            "clips_generated": s.clips_generated,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })

    return {
        "id": job.id,
        "video_id": job.video_id,
        "youtube_url": job.youtube_url,
        "youtube_id": job.youtube_id,
        "video_title": job.video_title,
        "thumbnail_url": job.thumbnail_url,
        "channel_name": job.channel_name,
        "channel_id": job.channel_id,
        "status": job.status,
        "live_status": job.live_status,
        "current_step": job.current_step,
        "total_duration": job.total_duration,
        "processed_until": job.processed_until,
        "newly_detected_duration": job.newly_detected_duration,
        "clips_count": job.clips_count,
        "clip_generation_mode": job.clip_generation_mode,
        "monitoring_interval_minutes": job.monitoring_interval_minutes,
        "next_check_at": job.next_check_at.isoformat() if job.next_check_at else None,
        "last_processed_at": job.last_processed_at.isoformat() if job.last_processed_at else None,
        "stop_requested": job.stop_requested,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "segments": segments_list,
        "clips": clips_list,
        "clips_generated_count": len(clips_list)
    }


@router.post("/{job_id}/stop")
async def stop_monitoring_endpoint(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Prominently stops monitoring for a live stream.
    Cancels future scheduled checks, safely handles running tasks, preserves completed clips & checkpoints.
    """
    stmt = select(LiveStreamJob).where(LiveStreamJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Live stream job not found")

    job.stop_requested = True
    job.status = "stopped"
    job.current_step = "Monitoring stopped by user. Checkpoint and clips preserved."
    job.next_check_at = None

    # Revoke Celery task if running
    if job.active_task_id:
        try:
            celery_app.control.revoke(job.active_task_id, terminate=False)
        except Exception as e:
            logger.warning(f"Failed to revoke task {job.active_task_id}: {e}")

    await db.commit()
    await db.refresh(job)

    return {
        "success": True,
        "job_id": job.id,
        "status": job.status,
        "message": "Monitoring stopped successfully. All clips and checkpoints have been preserved."
    }


@router.post("/{job_id}/resume")
async def resume_monitoring_endpoint(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Resumes monitoring from the last successful checkpoint.
    """
    stmt = select(LiveStreamJob).where(LiveStreamJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Live stream job not found")

    if job.status in ["monitoring", "processing"]:
        return {"success": True, "message": "Job is already active."}

    job.stop_requested = False
    job.status = "processing"
    job.current_step = f"Resuming live stream monitoring from checkpoint ({job.processed_until:.1f}s)..."
    job.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=job.monitoring_interval_minutes)
    await db.commit()

    # Enqueue segment processing task
    try:
        task = process_livestream_segment_task.delay(job_id=job.id, is_initial=False)
        job.active_task_id = task.id
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to enqueue resume task: {e}")

    return {
        "success": True,
        "job_id": job.id,
        "status": job.status,
        "message": f"Monitoring resumed from {job.processed_until:.1f}s checkpoint."
    }


@router.delete("/{job_id}")
async def delete_livestream_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Deletes a live stream monitoring record.
    """
    stmt = select(LiveStreamJob).where(LiveStreamJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Live stream job not found")

    job.stop_requested = True
    if job.active_task_id:
        try:
            celery_app.control.revoke(job.active_task_id, terminate=True)
        except Exception:
            pass

    await db.delete(job)
    await db.commit()
    return {"success": True, "message": "Live stream job deleted"}


@router.post("/{job_id}/check-now")
async def check_livestream_now_endpoint(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Manually triggers an immediate capture and processing cycle of the latest footage
    without waiting for the scheduled 20-minute timer.
    """
    stmt = select(LiveStreamJob).where(LiveStreamJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Live stream job not found")

    job.status = "processing"
    job.stop_requested = False
    job.current_step = "Immediate check triggered. Capturing newly available footage..."
    await db.commit()

    try:
        task = process_livestream_segment_task.delay(job_id=job.id, is_initial=False)
        job.active_task_id = task.id
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to enqueue check-now task: {e}")

    return {
        "success": True,
        "job_id": job.id,
        "status": job.status,
        "message": "Immediate footage check triggered."
    }
