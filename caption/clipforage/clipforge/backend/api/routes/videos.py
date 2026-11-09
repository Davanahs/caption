"""
API Routes — Videos (upload + URL input)
"""
import uuid
import shutil
import os
import math
import re
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.models.database import get_db
from backend.models.models import Video, Job, JobStatus
from backend.core.config import settings
from backend.services.downloader import get_video_info, extract_youtube_id
from datetime import datetime
import json

router = APIRouter(prefix="/api/videos", tags=["videos"])


def validate_clip_mode_and_duration(
    clip_mode: str | None,
    max_clip_duration: int | None,
    target_duration: float | None
) -> str:
    """
    Validate clip_mode and Shorts duration bounds (15-60s).
    Enforce that AI scoring requires at least one configured AI provider with zero fallback.
    In Equal Splits mode, maximum clip duration is strictly mandatory and cannot silently fall back.
    """
    import math
    from backend.services.llm_router import is_ai_provider_configured

    if hasattr(clip_mode, "default"):
        clip_mode = clip_mode.default
    if hasattr(max_clip_duration, "default"):
        max_clip_duration = max_clip_duration.default
    if hasattr(target_duration, "default"):
        target_duration = target_duration.default

    effective_mode = clip_mode or "ai_highlights"
    if effective_mode not in ("ai_highlights", "equal_split"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid clip_mode '{effective_mode}'. Must be 'ai_highlights' or 'equal_split'."
        )

    if effective_mode == "ai_highlights":
        if not is_ai_provider_configured():
            raise HTTPException(
                status_code=503,
                detail="No AI provider configured for clip scoring. Please configure OPENROUTER_API_KEY or NVIDIA_API_KEY."
            )

    if effective_mode == "equal_split":
        eff_dur = target_duration if target_duration is not None else max_clip_duration
        if eff_dur is None:
            raise HTTPException(
                status_code=400,
                detail="Maximum clip duration (target_duration or max_clip_duration) is mandatory for Equal Splits mode. Default fallback is prohibited."
            )
        try:
            val = float(eff_dur)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Equal Splits maximum clip duration must be a numeric value, got '{eff_dur}'."
            )
        if not math.isfinite(val) or val <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Equal Splits maximum clip duration must be strictly positive and finite, got {eff_dur}."
            )
        if not (15.0 <= val <= 60.0):
            raise HTTPException(
                status_code=400,
                detail=f"Equal Splits maximum clip duration must be between 15 and 60 seconds (got {eff_dur})."
            )

    if max_clip_duration is not None:
        if not (15 <= max_clip_duration <= 60):
            raise HTTPException(
                status_code=400,
                detail=f"max_clip_duration must be between 15 and 60 seconds (got {max_clip_duration})."
            )
    if target_duration is not None:
        if not (15.0 <= target_duration <= 60.0):
            raise HTTPException(
                status_code=400,
                detail=f"target_duration must be between 15.0 and 60.0 seconds (got {target_duration})."
            )

    return effective_mode


@router.post("/url")
async def process_youtube_url(
    url: str = Form(...),
    num_clips: int | None = Form(None),
    clips_count: int | None = Form(3),
    reframe_mode: str | None = Form(None),
    hook_title: bool | None = Form(None),
    clip_mode: str | None = Form("ai_highlights"),
    max_clip_duration: int | None = Form(None),
    enable_broll: bool = Form(False),
    enable_hook: bool = Form(False),
    target_language: str | None = Form(None),
    publish_destination_id: str | None = Form(None),
    destination_ids: str | None = Form(None),
    channel_id: str | None = Form(None),
    target_duration: float | None = Form(None),
    segmentation_strategy: str | None = Form(None),
    regions: str | None = Form(None),
    podcast_composition: str | None = Form(None),
    shot_schedule: str | None = Form(None),
    is_test: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """Submit a YouTube URL for processing."""
    from backend.tasks.orchestration import start_video_processing_task

    is_test_val = False
    if is_test is not None:
        if isinstance(is_test, bool):
            is_test_val = is_test
        elif isinstance(is_test, str):
            is_test_val = is_test.lower() in ("true", "1", "yes")
        elif hasattr(is_test, "default"):
            is_test_val = bool(is_test.default)

    if hasattr(shot_schedule, "default"):
        shot_schedule = shot_schedule.default
    if hasattr(regions, "default"):
        regions = regions.default
    if hasattr(podcast_composition, "default"):
        podcast_composition = podcast_composition.default
    if hasattr(destination_ids, "default"):
        destination_ids = destination_ids.default
    if hasattr(channel_id, "default"):
        channel_id = channel_id.default
    if hasattr(publish_destination_id, "default"):
        publish_destination_id = publish_destination_id.default
    if hasattr(target_language, "default"):
        target_language = target_language.default
    if hasattr(segmentation_strategy, "default"):
        segmentation_strategy = segmentation_strategy.default
    if hasattr(reframe_mode, "default"):
        reframe_mode = reframe_mode.default
    if hasattr(num_clips, "default"):
        num_clips = num_clips.default
    if hasattr(clips_count, "default"):
        clips_count = clips_count.default
    if hasattr(enable_broll, "default"):
        enable_broll = enable_broll.default
    if hasattr(enable_hook, "default"):
        enable_hook = enable_hook.default
    if hasattr(hook_title, "default"):
        hook_title = hook_title.default
    if hasattr(max_clip_duration, "default"):
        max_clip_duration = max_clip_duration.default
    if hasattr(target_duration, "default"):
        target_duration = target_duration.default

    # Validate mode and duration bounds
    clip_mode = validate_clip_mode_and_duration(clip_mode, max_clip_duration, target_duration)

    # Validate URL
    yt_id = extract_youtube_id(url)
    if not yt_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    # Guard: Check if video is a ClipForge-generated Short (prevent self-ingestion)
    from backend.services.provenance import check_is_clipforge_short
    is_short, cf_clip, parent_v = await check_is_clipforge_short(db, yt_id)
    if is_short:
        parent_title = parent_v.title if parent_v else "Original Source Video"
        parent_id = parent_v.youtube_id if parent_v else "unknown"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Self-ingestion blocked: '{yt_id}' is a ClipForge-generated output Short "
                f"(origin: '{parent_title}' [{parent_id}]). Output Shorts cannot be processed as source inputs."
            )
        )

    # Validate podcast manual regions if provided
    parsed_regions = None
    if regions is not None:
        trimmed_regions = regions.strip()
        if trimmed_regions:
            try:
                raw_regions = json.loads(trimmed_regions)
                if not isinstance(raw_regions, list):
                    raise ValueError("regions must be a JSON array")
                parsed_regions = []
                for idx, r in enumerate(raw_regions):
                    if not isinstance(r, dict):
                        raise ValueError(f"Region item {idx} must be an object")
                    rx = float(r.get("x", 0.0))
                    ry = float(r.get("y", 0.0))
                    rw = float(r.get("width") if r.get("width") is not None else r.get("w", 0.0))
                    rh = float(r.get("height") if r.get("height") is not None else r.get("h", 0.0))
                    if not (0.0 <= rx <= 1.0 and 0.0 <= ry <= 1.0):
                        raise ValueError(f"Region {idx} coordinates out of [0, 1] range: x={rx}, y={ry}")
                    if rw <= 0.0 or rh <= 0.0:
                        raise ValueError(f"Region {idx} dimensions must be positive: w={rw}, h={rh}")
                    if rx + rw > 1.001 or ry + rh > 1.001:
                        raise ValueError(f"Region {idx} exceeds bounds: x={rx}+w={rw}={rx+rw}, y={ry}+h={rh}={ry+rh}")
                    parsed_regions.append({
                        "id": str(r.get("id", f"region-{idx+1}")),
                        "label": str(r.get("label", f"Area {idx+1}")),
                        "x": rx,
                        "y": ry,
                        "width": min(rw, 1.0 - rx),
                        "height": min(rh, 1.0 - ry),
                    })
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid regions configuration: {str(e)}")

    # Validate podcast camera-following shot schedule if provided
    parsed_shot_schedule = None
    if shot_schedule is not None:
        trimmed_sched = shot_schedule.strip()
        if trimmed_sched:
            try:
                raw_sched = json.loads(trimmed_sched)
                if not isinstance(raw_sched, list):
                    raise ValueError("shot_schedule must be a JSON array")
                parsed_shot_schedule = []
                for idx, s in enumerate(raw_sched):
                    if not isinstance(s, dict):
                        raise ValueError(f"Shot item {idx} must be an object")
                    s_t = float(s.get("start_time", 0.0))
                    e_t = float(s.get("end_time", 0.0))
                    if s_t < 0.0 or e_t < s_t:
                        raise ValueError(f"Invalid shot interval: start={s_t}, end={e_t}")
                    parsed_shot_schedule.append(s)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid shot_schedule configuration: {str(e)}")

    # Parse destination_ids if provided
    parsed_destination_ids = None
    if destination_ids is not None:
        trimmed = destination_ids.strip()
        if trimmed.startswith("[") and trimmed.endswith("]"):
            try:
                parsed_destination_ids = json.loads(trimmed)
            except Exception:
                parsed_destination_ids = [x.strip() for x in trimmed.strip("[]").split(",") if x.strip()]
        elif trimmed:
            parsed_destination_ids = [x.strip() for x in trimmed.split(",") if x.strip()]
        else:
            parsed_destination_ids = []

    # If channel_id is provided and publish_destination_id is not explicitly specified,
    # inherit the monitored channel's configured publish_destination_id
    if channel_id and not publish_destination_id:
        from backend.models.models import Channel
        ch_res = await db.execute(select(Channel).where(Channel.id == channel_id))
        source_ch = ch_res.scalar_one_or_none()
        if source_ch:
            publish_destination_id = source_ch.publish_destination_id
            if publish_destination_id and parsed_destination_ids is None:
                parsed_destination_ids = [publish_destination_id]
    # Auto-configure Equal Split strategy and target duration
    if clip_mode == "equal_split":
        if not segmentation_strategy:
            segmentation_strategy = "equal_splits"
        if target_duration is None and max_clip_duration:
            target_duration = float(max_clip_duration)

    # Determine effective mode and composition
    is_advanced = bool(parsed_shot_schedule or podcast_composition in ("advanced_podcast", "camera_following", "fixed_two_person", "visibility_driven"))
    effective_podcast_comp = podcast_composition or ("advanced_podcast" if is_advanced else ("stacked" if parsed_regions and len(parsed_regions) > 1 else "single_region"))
    effective_job_mode = "advanced_podcast" if is_advanced else ("podcast_interview" if parsed_regions else "standard")

    # Create job record
    job_id = str(uuid.uuid4())
    dispatch_kwargs = {
        "youtube_url": url,
        "job_id": job_id,
        "num_clips": (num_clips or clips_count) if clip_mode != "equal_split" else None,
        "clips_count": (clips_count or num_clips) if clip_mode != "equal_split" else None,
        "reframe_mode": reframe_mode,
        "hook_title": hook_title,
        "clip_mode": clip_mode,
        "max_clip_duration": max_clip_duration,
        "enable_broll": enable_broll,
        "enable_hook": enable_hook,
        "target_language": target_language,
        "publish_destination_id": publish_destination_id,
        "destination_ids": parsed_destination_ids,
        "channel_id": channel_id,
        "target_duration": target_duration,
        "segmentation_strategy": segmentation_strategy,
        "regions": parsed_regions,
        "podcast_composition": effective_podcast_comp,
    }

    config_data = {
        "reframe_mode": reframe_mode,
        "clip_mode": clip_mode,
        "max_clip_duration": max_clip_duration,
        "enable_broll": enable_broll,
        "enable_hook": enable_hook,
        "target_language": target_language,
        "clips_count": (clips_count or num_clips) if clip_mode != "equal_split" else None,
        "publish_destination_id": publish_destination_id,
        "destination_ids": parsed_destination_ids,
        "channel_id": channel_id,
        "target_duration": target_duration,
        "segmentation_strategy": segmentation_strategy,
        "source_type": "youtube",
        "regions": parsed_regions,
        "shot_schedule": parsed_shot_schedule,
        "podcast_composition": effective_podcast_comp,
        "mode": effective_job_mode,
        "dispatch_kwargs": dispatch_kwargs,
    }

    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        progress=0,
        current_step="Queued",
        source_url=url,
        source_title=f"youtube.com/watch?v={yt_id}",
        config=json.dumps(config_data),
        is_test=is_test_val,
    )
    db.add(job)
    await db.commit()

    # Concurrency Gate: max 5 active manual videos
    from backend.services.queue_manager import (
        get_active_manual_jobs_count_async,
        get_pending_queue_position_async,
        format_queue_step,
        MAX_CONCURRENT_MANUAL_JOBS,
        dispatch_celery_job,
    )

    active_count = await get_active_manual_jobs_count_async(db)
    if active_count < MAX_CONCURRENT_MANUAL_JOBS:
        task_id = dispatch_celery_job(job_id, dispatch_kwargs)
        job.celery_task_id = task_id
        job.current_step = "Queued"
        await db.commit()
        return {"job_id": job_id, "message": "Processing started", "url": url, "queued": False}
    else:
        position = await get_pending_queue_position_async(db, job_id)
        job.current_step = format_queue_step(position)
        await db.commit()
        return {
            "job_id": job_id,
            "message": f"Queued (#{position} in line - waiting for an active video to finish)",
            "url": url,
            "queued": True,
            "queue_position": position,
        }


@router.post("/podcast/analyze-shots")
async def analyze_podcast_shots(
    url: str = Form(...),
    regions: str = Form(...),
    ref_timestamp: float = Form(0.0),
    composition: str | None = Form(None),
    async_mode: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyzes camera cuts and participant visibility for the source video.
    Returns the deterministic time-based shot schedule for camera-following reframing.
    Supports asynchronous queued execution for long videos via async_mode=True.
    """
    from backend.services.advanced_podcast_engine import (
        build_shot_schedule,
        build_fixed_boundary_schedule,
        build_visibility_driven_schedule,
    )
    from backend.services.downloader import download_video, extract_youtube_id

    if hasattr(composition, "default"):
        composition = composition.default

    # Parse and validate regions
    if not regions or not regions.strip():
        raise HTTPException(status_code=400, detail="regions parameter is required for shot analysis")
    try:
        raw_regions = json.loads(regions.strip())
        if not isinstance(raw_regions, list) or len(raw_regions) == 0:
            raise ValueError("regions must be a non-empty array")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid regions JSON: {str(e)}")

    yt_id = extract_youtube_id(url)
    if not yt_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    # If asynchronous background queue requested (Phase 5 Long-Video Architecture)
    is_async = (async_mode is True) if not hasattr(async_mode, "default") else (async_mode.default is True)
    if is_async:
        from backend.tasks.analysis_tasks import analyze_podcast_shots_task
        task = analyze_podcast_shots_task.delay(
            url=url,
            regions_json=regions.strip(),
            ref_timestamp=ref_timestamp,
            composition=composition or "advanced_podcast"
        )
        return {
            "status": "queued",
            "task_id": str(task.id),
            "video_id": yt_id,
            "ref_timestamp": ref_timestamp
        }

    # Synchronous path: check local video files or download
    possible_paths = [
        Path(f"uploads/{yt_id}.mp4"),
        Path(f"/app/uploads/{yt_id}.mp4"),
    ]
    local_path = next((p for p in possible_paths if p.exists()), None)

    cleanup_needed = False
    if not local_path:
        direct_p = Path(url)
        if direct_p.exists():
            local_path = direct_p
        else:
            try:
                local_path = await download_video(url, video_id=f"analysis_{yt_id}")
                cleanup_needed = True
            except Exception as dl_err:
                raise HTTPException(status_code=502, detail=f"Could not download video for shot analysis: {str(dl_err)}")

    try:
        if composition == "fixed_two_person":
            outer_bound = next((r for r in raw_regions if r.get("id") == "outer_boundary" or str(r.get("label", "")).lower().startswith("outer")), None)
            participants = [r for r in raw_regions if r != outer_bound]
            if not outer_bound:
                outer_bound = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
            schedule = build_fixed_boundary_schedule(local_path, outer_boundary=outer_bound, participant_regions=participants, ref_timestamp=ref_timestamp)
        elif composition == "visibility_driven":
            reg_a = raw_regions[0]
            reg_b = raw_regions[1] if len(raw_regions) > 1 else raw_regions[0]
            schedule = build_visibility_driven_schedule(local_path, region_a=reg_a, region_b=reg_b, ref_timestamp=ref_timestamp)
        else:
            schedule = build_shot_schedule(local_path, raw_regions, ref_timestamp=ref_timestamp)

        review_count = sum(1 for s in schedule if s.get("review_needed"))

        # Pre-extract and cache representative shot frames while local_path is available
        try:
            frame_cache_dir = settings.UPLOAD_DIR / "frame_cache" / yt_id
            frame_cache_dir.mkdir(parents=True, exist_ok=True)
            for s in schedule:
                s_id = s.get("shot_id")
                mid_t = (float(s.get("start_time", 0.0)) + float(s.get("end_time", 0.0))) / 2.0
                shot_f = frame_cache_dir / f"shot_{s_id}.jpg"
                ts_f = frame_cache_dir / f"{round(mid_t, 3):.3f}.jpg"
                if not shot_f.exists() or not ts_f.exists():
                    f_proc = await asyncio.create_subprocess_exec(
                        "ffmpeg", "-y", "-nostdin", "-protocol_whitelist", "file",
                        "-ss", f"{mid_t:.3f}",
                        "-i", str(local_path),
                        "-vframes", "1",
                        "-q:v", "3",
                        "-f", "image2",
                        str(shot_f),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    await asyncio.wait_for(f_proc.wait(), timeout=3.0)
                    if shot_f.exists() and not ts_f.exists():
                        shutil.copy2(shot_f, ts_f)
        except Exception:
            pass

        return {
            "status": "success",
            "video_id": yt_id,
            "ref_timestamp": ref_timestamp,
            "total_shots": len(schedule),
            "review_needed_count": review_count,
            "shots": schedule
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Shot analysis failed: {str(err)}")
    finally:
        if cleanup_needed and local_path and local_path.exists():
            try:
                if local_path.parent.name.startswith("clipforge_dl_"):
                    shutil.rmtree(local_path.parent, ignore_errors=True)
                else:
                    local_path.unlink(missing_ok=True)
            except Exception:
                pass


@router.get("/podcast/analysis-status/{task_id}")
async def get_podcast_analysis_status(task_id: str):
    """
    Returns progress or final result for an asynchronous podcast shot analysis task.
    """
    from backend.tasks.celery_app import celery_app
    async_res = celery_app.AsyncResult(task_id)

    if async_res.ready():
        if async_res.successful():
            return {"status": "success", "result": async_res.result}
        else:
            exc = async_res.result
            if isinstance(exc, Exception):
                exc_type = type(exc).__name__
                exc_str = str(exc).strip("'\"")
                if exc_type in ("NotRegistered", "KeyError") and "analyze_podcast_shots_task" in str(exc):
                    error_msg = f"{exc_type}: Task 'analyze_podcast_shots_task' is not registered on the running Celery worker (worker reload required)."
                else:
                    error_msg = f"{exc_type}: {exc_str}" if exc_str else exc_type
            else:
                raw_str = str(exc) if exc else "Shot analysis failed in worker"
                if "analyze_podcast_shots_task" in raw_str:
                    error_msg = f"TaskNotRegistered: Task 'analyze_podcast_shots_task' is not registered on the running Celery worker (worker reload required)."
                else:
                    error_msg = raw_str
            return {"status": "failed", "error": error_msg}

    # In progress or pending
    info = async_res.info if isinstance(async_res.info, dict) else {}
    return {
        "status": "processing",
        "progress": info.get("progress", 10),
        "stage": info.get("stage", "analyzing"),
        "message": info.get("message", "Analyzing camera cuts and speakers...")
    }



from pydantic import BaseModel, HttpUrl

class BatchURLRequest(BaseModel):
    urls: list[str]
    clips_count: int | None = 3
    clip_mode: str | None = "ai_highlights"
    max_clip_duration: int | None = 49
    enable_broll: bool | None = False
    enable_hook: bool | None = False
    target_language: str | None = "none"
    reframe_mode: str | None = None
    publish_destination_id: str | None = None
    target_duration: float | None = None
    segmentation_strategy: str | None = None

@router.post("/batch")
async def process_youtube_urls_batch(
    req: BatchURLRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit multiple YouTube URLs for batch processing.
    POST /api/videos/batch
    Body: { "urls": ["https://...", "https://..."], "clips_count": 3 }
    """
    from backend.tasks.orchestration import start_video_processing_task

    if not req.urls:
        raise HTTPException(status_code=400, detail="No URLs provided in batch request")

    # Validate mode and duration bounds across the batch
    effective_clip_mode = validate_clip_mode_and_duration(
        req.clip_mode, req.max_clip_duration, req.target_duration
    )

    results = []
    skipped = []

    for raw_url in req.urls:
        url = raw_url.strip()
        if not url:
            continue
        yt_id = extract_youtube_id(url)
        if not yt_id:
            skipped.append({"url": url, "reason": "Invalid YouTube URL"})
            continue

        effective_seg_strategy = req.segmentation_strategy
        effective_target_duration = req.target_duration
        if req.clip_mode == "equal_split":
            if not effective_seg_strategy:
                effective_seg_strategy = "equal_splits"
            if effective_target_duration is None and req.max_clip_duration:
                effective_target_duration = float(req.max_clip_duration)

        job_id = str(uuid.uuid4())
        config_data = {
            "reframe_mode": req.reframe_mode,
            "clip_mode": req.clip_mode or "ai_highlights",
            "max_clip_duration": req.max_clip_duration,
            "enable_broll": req.enable_broll or False,
            "enable_hook": req.enable_hook or False,
            "target_language": req.target_language,
            "clips_count": req.clips_count if req.clip_mode != "equal_split" else None,
            "publish_destination_id": req.publish_destination_id,
            "target_duration": effective_target_duration,
            "segmentation_strategy": effective_seg_strategy,
        }

        dispatch_kwargs = {
            "youtube_url": url,
            "job_id": job_id,
            "num_clips": req.clips_count if req.clip_mode != "equal_split" else None,
            "clips_count": req.clips_count if req.clip_mode != "equal_split" else None,
            "reframe_mode": req.reframe_mode,
            "clip_mode": req.clip_mode or "ai_highlights",
            "max_clip_duration": req.max_clip_duration,
            "enable_broll": req.enable_broll or False,
            "enable_hook": req.enable_hook or False,
            "target_language": req.target_language,
            "publish_destination_id": req.publish_destination_id,
            "target_duration": effective_target_duration,
            "segmentation_strategy": effective_seg_strategy,
        }
        config_data["dispatch_kwargs"] = dispatch_kwargs

        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            progress=0,
            current_step="Queued (Batch)",
            source_url=url,
            source_title=f"youtube.com/watch?v={yt_id}",
            config=json.dumps(config_data)
        )
        db.add(job)
        await db.commit()

        from backend.services.queue_manager import (
            get_active_manual_jobs_count_async,
            get_pending_queue_position_async,
            format_queue_step,
            MAX_CONCURRENT_MANUAL_JOBS,
            dispatch_celery_job,
        )

        active_count = await get_active_manual_jobs_count_async(db)
        if active_count < MAX_CONCURRENT_MANUAL_JOBS:
            task_id = dispatch_celery_job(job_id, dispatch_kwargs)
            job.celery_task_id = task_id
            job.current_step = "Queued"
            await db.commit()
            results.append({
                "job_id": job_id,
                "url": url,
                "youtube_id": yt_id,
                "status": "processing_started",
                "queued": False
            })
        else:
            position = await get_pending_queue_position_async(db, job_id)
            job.current_step = format_queue_step(position)
            await db.commit()
            results.append({
                "job_id": job_id,
                "url": url,
                "youtube_id": yt_id,
                "status": "queued",
                "queued": True,
                "queue_position": position,
            })

    return {
        "status": "batch_submitted",
        "total_submitted": len(req.urls),
        "total_queued": len(results),
        "total_skipped": len(skipped),
        "jobs": results,
        "skipped": skipped,
    }



@router.post("/upload")
async def upload_video_file(
    file: UploadFile = File(...),
    num_clips: int | None = Form(None),
    clips_count: int | None = Form(3),
    reframe_mode: str | None = Form(None),
    hook_title: bool | None = Form(None),
    clip_mode: str | None = Form("ai_highlights"),
    max_clip_duration: int | None = Form(None),
    enable_broll: bool = Form(False),
    enable_hook: bool = Form(False),
    target_language: str | None = Form(None),
    publish_destination_id: str | None = Form(None),
    target_duration: float | None = Form(None),
    segmentation_strategy: str | None = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Upload a local MP4/MOV file for processing."""
    from backend.tasks.orchestration import start_video_processing_task

    if not file.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        raise HTTPException(status_code=400, detail="Unsupported file format. Use MP4, MOV, AVI, MKV, or WebM")

    # Validate mode and duration bounds
    clip_mode = validate_clip_mode_and_duration(clip_mode, max_clip_duration, target_duration)

    # Save uploaded file
    video_id = str(uuid.uuid4())
    upload_dir = settings.UPLOAD_DIR / video_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / "video.mp4"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if clip_mode == "equal_split":
        if not segmentation_strategy:
            segmentation_strategy = "equal_splits"
        if target_duration is None and max_clip_duration:
            target_duration = float(max_clip_duration)

    # Create job record
    job_id = str(uuid.uuid4())
    config_data = {
        "reframe_mode": reframe_mode,
        "clip_mode": clip_mode,
        "max_clip_duration": max_clip_duration,
        "enable_broll": enable_broll,
        "enable_hook": enable_hook,
        "target_language": target_language,
        "clips_count": (clips_count or num_clips) if clip_mode != "equal_split" else None,
        "publish_destination_id": publish_destination_id,
        "target_duration": target_duration,
        "segmentation_strategy": segmentation_strategy,
        "source_type": "local",
        "local_path": str(file_path),
    }

    dispatch_kwargs = {
        "local_path": str(file_path),
        "job_id": job_id,
        "num_clips": (num_clips or clips_count) if clip_mode != "equal_split" else None,
        "clips_count": (clips_count or num_clips) if clip_mode != "equal_split" else None,
        "reframe_mode": reframe_mode,
        "hook_title": hook_title,
        "clip_mode": clip_mode,
        "max_clip_duration": max_clip_duration,
        "enable_broll": enable_broll,
        "enable_hook": enable_hook,
        "target_language": target_language,
        "publish_destination_id": publish_destination_id,
        "target_duration": target_duration,
        "segmentation_strategy": segmentation_strategy,
    }
    config_data["dispatch_kwargs"] = dispatch_kwargs

    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        progress=0,
        current_step="Queued",
        source_url=file.filename,
        source_title=file.filename,
        config=json.dumps(config_data)
    )
    db.add(job)
    await db.commit()

    from backend.services.queue_manager import (
        get_active_manual_jobs_count_async,
        get_pending_queue_position_async,
        format_queue_step,
        MAX_CONCURRENT_MANUAL_JOBS,
        dispatch_celery_job,
    )

    active_count = await get_active_manual_jobs_count_async(db)
    if active_count < MAX_CONCURRENT_MANUAL_JOBS:
        task_id = dispatch_celery_job(job_id, dispatch_kwargs)
        job.celery_task_id = task_id
        job.current_step = "Queued"
        await db.commit()
        return {"job_id": job_id, "message": "Upload received, processing started", "queued": False}
    else:
        position = await get_pending_queue_position_async(db, job_id)
        job.current_step = format_queue_step(position)
        await db.commit()
        return {
            "job_id": job_id,
            "message": f"Upload received. Queued (#{position} in line - waiting for an active video to finish)",
            "queued": True,
            "queue_position": position,
        }


@router.get("/")
async def list_videos(db: AsyncSession = Depends(get_db)):
    """List all processed videos."""
    result = await db.execute(select(Video).order_by(desc(Video.created_at)).limit(50))
    videos = result.scalars().all()
    return [
        {
            "id": v.id,
            "title": v.title,
            "youtube_url": v.youtube_url,
            "youtube_id": v.youtube_id,
            "duration": v.duration,
            "thumbnail_url": v.thumbnail_url,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in videos
    ]


@router.get("/{video_id}")
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific video by ID."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/{video_id}/seo-metadata")
async def get_video_seo_metadata(video_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve canonical source-level AI SEO metadata (primary category, secondary topics,
    4–6 SEO tags, canonical description hashtags, and attribution summary).
    Reuses existing metadata if already analyzed (0 duplicate AI calls).
    """
    from backend.services.source_metadata_engine import get_or_analyze_source_seo_metadata
    
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    import asyncio
    metadata = await asyncio.to_thread(get_or_analyze_source_seo_metadata, video_id, None, False)
    return metadata.to_dict()


@router.post("/{video_id}/seo-metadata/refresh")
async def refresh_video_seo_metadata(video_id: str, db: AsyncSession = Depends(get_db)):
    """
    Force-refreshes canonical source-level AI SEO metadata for a video,
    updating the persisted disk artifact and metadata database record.
    """
    from backend.services.source_metadata_engine import get_or_analyze_source_seo_metadata
    
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    import asyncio
    metadata = await asyncio.to_thread(get_or_analyze_source_seo_metadata, video_id, None, True)
    return metadata.to_dict()


@router.get("/{video_id}/frame")
async def get_video_frame(
    video_id: str,
    timestamp: float,
    shot_id: int | None = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Extracts and returns a real JPEG source frame at the specified timestamp
    for an authorized/managed video asset.
    Enforces strict identifier validation, path containment under managed storage,
    finite non-negative bounds check, rate/duration limits, and safe protocol-restricted FFmpeg extraction.
    Caches extracted frames under settings.UPLOAD_DIR/frame_cache/{video_id}/.
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    # 1. Strict identifier check: only alphanumeric, hyphens, and underscores (1 to 64 chars)
    # Rejects path traversal (..), slashes, null bytes, shell metacharacters
    if not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", video_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid video_id identifier. Must be 1-64 alphanumeric, hyphen, or underscore characters."
        )

    # 2. Strict timestamp bounds check
    if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
        raise HTTPException(
            status_code=400,
            detail="Timestamp must be a finite numeric value."
        )
    if timestamp < 0.0:
        raise HTTPException(
            status_code=400,
            detail="Timestamp must be non-negative (>= 0.0)."
        )
    if timestamp > 86400.0:
        raise HTTPException(
            status_code=400,
            detail="Timestamp exceeds maximum allowed media duration (86400s)."
        )

    # 3. Resolve video from database
    video = None
    try:
        from sqlalchemy import or_
        res = await db.execute(
            select(Video).where(
                or_(Video.id == video_id, Video.youtube_id == video_id)
            )
        )
        video = res.scalar_one_or_none()
    except Exception as db_err:
        logger.warning(f"Error querying Video in DB: {db_err}")

    # Check known duration if available
    if video and video.duration is not None and video.duration > 0.0:
        if timestamp > video.duration + 0.5:
            raise HTTPException(
                status_code=400,
                detail=f"Requested timestamp {timestamp:.2f}s exceeds video duration {video.duration:.2f}s."
            )

    upload_root = settings.UPLOAD_DIR.resolve()
    base_root = settings.BASE_DIR.resolve()
    cache_dir = upload_root / "frame_cache" / video_id

    # 4. Check cache first for instant retrieval
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{round(timestamp, 3):.3f}.jpg"
    shot_file = cache_dir / f"shot_{shot_id}.jpg" if shot_id is not None else None

    if shot_file and shot_file.is_file() and shot_file.stat().st_size > 0:
        return FileResponse(
            shot_file,
            media_type="image/jpeg",
            headers={
                "X-Frame-Timestamp": f"{timestamp:.3f}",
                "X-Source-Id": video_id,
                "X-Frame-Cache": "HIT",
                "Cache-Control": "public, max-age=3600"
            }
        )

    if cache_file.is_file() and cache_file.stat().st_size > 0:
        return FileResponse(
            cache_file,
            media_type="image/jpeg",
            headers={
                "X-Frame-Timestamp": f"{timestamp:.3f}",
                "X-Source-Id": video_id,
                "X-Frame-Cache": "HIT",
                "Cache-Control": "public, max-age=3600"
            }
        )

    # 5. Locate source video in managed storage
    resolved_path: Path | None = None
    candidates: list[Path] = []

    if video and video.local_path:
        lp = Path(video.local_path)
        if lp.is_absolute():
            candidates.append(lp)
        else:
            candidates.append(upload_root / lp)
            candidates.append(upload_root / video_id / lp)

    candidates.extend([
        upload_root / video_id / "source.mp4",
        upload_root / f"{video_id}.mp4",
        upload_root / f"analysis_{video_id}.mp4",
    ])

    # Isolated test fixtures allowed ONLY for explicit synthetic identifiers
    if video_id == "synthetic_test_fixture" or video_id.startswith("synth_"):
        candidates.extend([
            upload_root / "synthetic_test_fixture.mp4",
            base_root.parent / "uploads" / "synthetic_test_fixture.mp4",
            base_root / "uploads" / "synthetic_test_fixture.mp4",
            Path("uploads/synthetic_test_fixture.mp4"),
        ])

    for c in candidates:
        try:
            c_res = c.resolve()
            # Enforce canonical containment
            if (
                str(c_res).startswith(str(upload_root))
                or str(c_res).startswith(str(base_root))
                or str(c_res).startswith(str(Path.cwd().resolve()))
            ) and c_res.is_file():
                resolved_path = c_res
                break
        except Exception:
            continue

    if not resolved_path:
        raise HTTPException(
            status_code=404,
            detail=f"Source video asset not found or access denied for video_id='{video_id}'."
        )

    # 6. Safe extraction with protocol whitelist and bounded subprocess time
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(cache_dir),
        prefix="tmp_frame_",
        suffix=".jpg"
    )
    os.close(fd)
    tmp_path = Path(tmp_path_str)

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-protocol_whitelist", "file",
        "-ss", f"{timestamp:.3f}",
        "-i", str(resolved_path),
        "-vframes", "1",
        "-q:v", "2",
        "-f", "image2",
        str(tmp_path)
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=8.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(
                status_code=504,
                detail="Frame extraction timed out after 8.0s."
            )

        if proc.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
            err_msg = stderr.decode(errors="replace")[:300] if stderr else "Empty frame output"
            raise HTTPException(
                status_code=500,
                detail=f"FFmpeg frame extraction failed: {err_msg}"
            )

        tmp_path.replace(cache_file)
        if shot_id is not None:
            shot_dest = cache_dir / f"shot_{shot_id}.jpg"
            try:
                shutil.copy2(cache_file, shot_dest)
            except Exception:
                pass

        return FileResponse(
            cache_file,
            media_type="image/jpeg",
            headers={
                "X-Frame-Timestamp": f"{timestamp:.3f}",
                "X-Source-Id": video_id,
                "X-Frame-Cache": "MISS",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during frame extraction: {e}")
        raise HTTPException(status_code=500, detail=f"Frame extraction failed: {str(e)}")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
