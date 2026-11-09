"""
API Routes — Performance Analytics (Phase 4)

Endpoints:
  POST /api/analytics/track/{video_id}          — start tracking a published clip
  POST /api/analytics/cancel/{task_id}          — cancel an active tracker
  GET  /api/analytics/active                    — list active tracker task IDs
  GET  /api/analytics/{video_id}                — fetch stored analytics snapshots
"""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from backend.models.database import get_db
from backend.models.models import VideoAnalytics, Clip, Video
from backend.core.config import settings

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class TrackRequest(BaseModel):
    youtube_video_id: str | None = None   # The real YouTube video ID (e.g. "dQw4w9WgXcQ"), optional if clip has youtube_short_id


@router.post("/track/{video_id}")
async def start_tracker(video_id: str, body: TrackRequest = TrackRequest(), db: AsyncSession = Depends(get_db)):
    """
    Start polling YouTube stats every 12 h for 3 days for a published video.

    - video_id          : internal ClipForge clip/video UUID
    - youtube_video_id  : the real YouTube video ID returned after upload (optional if clip published)
    """
    from backend.new_files.performance_tracker import start_tracking
    
    yt_id = (body.youtube_video_id or "").strip()
    if not yt_id:
        # Resolve from Clip or Video
        clip_res = await db.execute(select(Clip).where(Clip.id == video_id))
        clip = clip_res.scalar_one_or_none()
        if clip and clip.youtube_short_id:
            yt_id = clip.youtube_short_id
        elif getattr(settings, "TEST_MODE", True):
            yt_id = f"test_yt_{video_id[:8]}"
        else:
            raise HTTPException(
                status_code=400,
                detail="youtube_video_id is required or clip must have a published youtube_short_id",
            )

    try:
        task_id = await asyncio.to_thread(start_tracking, video_id, yt_id)
        return {
            "status": "tracking_started",
            "task_id": task_id,
            "video_id": video_id,
            "youtube_video_id": yt_id,
            "message": "Polling every 12 h for 3 days (6 polls total). Use task_id to cancel.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cancel/{task_id}")
async def cancel_tracker(task_id: str):
    """Cancel an active performance-tracking task."""
    from backend.new_files.performance_tracker import cancel_tracking
    cancelled = await asyncio.to_thread(cancel_tracking, task_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"No active tracker found for task_id '{task_id}'. It may have already finished.",
        )
    return {"status": "cancelled", "task_id": task_id}


@router.get("/active")
async def list_active():
    """List all currently active performance tracker task IDs."""
    from backend.new_files.performance_tracker import list_active_trackers
    active = await asyncio.to_thread(list_active_trackers)
    return {"active_trackers": active}


# ── Phase 14: A/B Experiments & Reinforcement Learning Insights ───────────────

@router.get("/ab-tests")
async def get_ab_tests():
    """
    Return all live and completed A/B title experiments.
    GET /api/analytics/ab-tests
    """
    from backend.services.ab_testing_engine import get_ab_experiments_summary
    return get_ab_experiments_summary()


@router.get("/insights")
async def get_channel_insights():
    """
    Return reinforcement learning patterns (winning titles, lowest performing titles, VSI benchmarks).
    GET /api/analytics/insights
    """
    from backend.services.ab_testing_engine import get_winning_patterns
    return get_winning_patterns()


# ── Phase 1: SEO Analysis & Summary endpoints ─────────────────────────────────


@router.get("/summary")
async def get_pipeline_summary(db: AsyncSession = Depends(get_db)):
    """
    Return a high-level pipeline health summary for the dashboard.
    Reads from: pipeline_metrics, seo_analysis, optimization_context, video_tracking_queue.
    GET /api/analytics/summary
    """
    from sqlalchemy import select, func
    from backend.models.models import PipelineMetrics, SEOAnalysis, OptimizationContext, VideoTrackingQueue

    try:
        # Pipeline metrics totals
        pm = await db.execute(select(func.count(), func.avg(PipelineMetrics.duration_ms)).where(PipelineMetrics.success == True))
        pm_res = pm.first()
        pm_failed = await db.execute(select(func.count()).where(PipelineMetrics.success == False))
        pm_failed_res = pm_failed.first()

        # SEO analysis
        seo = await db.execute(select(func.count(), func.avg(SEOAnalysis.seo_score), func.avg(SEOAnalysis.ctr_score)))
        seo_res = seo.first()

        # Optimizations
        opts = await db.execute(select(func.count(OptimizationContext.id)))
        opts_res = opts.first()

        # Tracking queue
        queue_active = await db.execute(select(func.count()).where(VideoTrackingQueue.status.in_(['active', 'optimized_once'])))
        queue_active_res = queue_active.first()
        queue_completed = await db.execute(select(func.count()).where(VideoTrackingQueue.status == 'completed'))
        queue_completed_res = queue_completed.first()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {
        "pipeline": {
            "successful_phases": (pm_res[0] if pm_res else 0) or 0,
            "failed_phases": (pm_failed_res[0] if pm_failed_res else 0) or 0,
            "avg_phase_duration_ms": round((pm_res[1] if pm_res and pm_res[1] else 0) or 0, 1),
        },
        "seo": {
            "total_seo_snapshots": (seo_res[0] if seo_res else 0) or 0,
            "avg_seo_score": round((seo_res[1] if seo_res and seo_res[1] else 0) or 0, 1),
            "avg_ctr_score": round((seo_res[2] if seo_res and seo_res[2] else 0) or 0, 1),
        },
        "optimizer": {
            "total_optimization_attempts": (opts_res[0] if opts_res else 0) or 0,
        },
        "tracking": {
            "active_videos": (queue_active_res[0] if queue_active_res else 0) or 0,
            "completed_videos": (queue_completed_res[0] if queue_completed_res else 0) or 0,
        },
    }


def _parse_list(val) -> list[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
        return [x.strip() for x in val.split(",") if x.strip()]
    return []


@router.get("/seo/{video_id}")
async def get_seo_analysis(video_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return all SEO analysis snapshots for a clip, newest first.
    These are written by auto_optimizer after each optimization attempt.
    GET /api/analytics/seo/{video_id}
    """
    from backend.models.models import SEOAnalysis

    try:
        result = await db.execute(
            select(SEOAnalysis)
            .where(SEOAnalysis.clip_id == video_id)
            .order_by(desc(SEOAnalysis.created_at))
        )
        rows = result.scalars().all()
        if not rows:
            # Check if video_id is a parent Video.id
            clips_res = await db.execute(select(Clip.id).where(Clip.video_id == video_id))
            clip_ids = clips_res.scalars().all()
            if clip_ids:
                result = await db.execute(
                    select(SEOAnalysis)
                    .where(SEOAnalysis.clip_id.in_(clip_ids))
                    .order_by(desc(SEOAnalysis.created_at))
                )
                rows = result.scalars().all()
            else:
                # Check if video_id is a Clip.id with parent video_id
                clip_res = await db.execute(select(Clip).where(Clip.id == video_id))
                clip = clip_res.scalar_one_or_none()
                if clip and clip.video_id:
                    result = await db.execute(
                        select(SEOAnalysis)
                        .where(SEOAnalysis.clip_id == clip.video_id)
                        .order_by(desc(SEOAnalysis.created_at))
                    )
                    rows = result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not rows:
        return {
            "video_id": video_id,
            "total_snapshots": 0,
            "latest_seo_score": None,
            "latest_ctr_score": None,
            "snapshots": [],
        }

    snapshots = []
    for r in rows:
        seo_data = {}
        try:
            seo_data = json.loads(r.seo_json) if r.seo_json else {}
        except Exception:
            pass

        missing_kw = _parse_list(r.missing_keywords) or _parse_list(seo_data.get("missing_keywords"))
        rec_tags = _parse_list(r.recommended_hashtags) or _parse_list(seo_data.get("recommended_hashtags"))
        weak_tags = _parse_list(r.weak_hashtags) or _parse_list(seo_data.get("weak_hashtags"))

        snapshots.append({
            "clip_id": r.clip_id,
            "seo_score": r.seo_score,
            "ctr_score": r.ctr_score,
            "discoverability_score": r.discoverability_score,
            "missing_keywords": missing_kw,
            "recommended_hashtags": rec_tags,
            "weak_hashtags": weak_tags,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "title": seo_data.get("title", ""),
            "tags": _parse_list(seo_data.get("tags")),
            "hashtags": _parse_list(seo_data.get("hashtags")),
            "view_score_at_optimization": seo_data.get("view_score_at_optimization", 0),
        })

    return {
        "video_id": video_id,
        "total_snapshots": len(snapshots),
        "latest_seo_score": snapshots[0]["seo_score"] if snapshots else None,
        "latest_ctr_score": snapshots[0]["ctr_score"] if snapshots else None,
        "snapshots": snapshots,
    }


@router.get("/{video_id}")
async def get_analytics(video_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return all stored analytics snapshots for a video, newest first.
    Also returns the latest view_score and a trend indicator.
    """
    result = await db.execute(
        select(VideoAnalytics)
        .where(VideoAnalytics.video_id == video_id)
        .order_by(desc(VideoAnalytics.fetched_at))
    )
    rows = result.scalars().all()
    if not rows:
        # Check if video_id is a Clip.id whose parent video_id might have rows
        clip_res = await db.execute(select(Clip).where(Clip.id == video_id))
        clip = clip_res.scalar_one_or_none()
        if clip and clip.video_id and clip.video_id != video_id:
            result = await db.execute(
                select(VideoAnalytics)
                .where(VideoAnalytics.video_id == clip.video_id)
                .order_by(desc(VideoAnalytics.fetched_at))
            )
            rows = result.scalars().all()
        elif not clip:
            # Maybe video_id is a Video.id whose clips have rows
            clips_res = await db.execute(select(Clip.id).where(Clip.video_id == video_id))
            clip_ids = clips_res.scalars().all()
            if clip_ids:
                result = await db.execute(
                    select(VideoAnalytics)
                    .where(VideoAnalytics.video_id.in_(clip_ids))
                    .order_by(desc(VideoAnalytics.fetched_at))
                )
                rows = result.scalars().all()

    if not rows:
        return {
            "video_id": video_id,
            "latest_score": None,
            "trend": "stable",
            "total_polls": 0,
            "snapshots": [],
        }

    snapshots = [
        {
            "id": r.id,
            "view_count": r.view_count,
            "like_count": r.like_count,
            "comment_count": r.comment_count,
            "view_score": r.view_score,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
        }
        for r in rows
    ]

    latest = snapshots[0]
    # Simple trend: compare latest vs previous snapshot
    trend = "stable"
    if len(snapshots) >= 2:
        delta = (latest["view_score"] or 0) - (snapshots[1]["view_score"] or 0)
        if delta > 0.5:
            trend = "up"
        elif delta < -0.5:
            trend = "down"

    return {
        "video_id": video_id,
        "latest_score": latest["view_score"],
        "trend": trend,
        "total_polls": len(snapshots),
        "snapshots": snapshots,
    }


# ── Phase 5: Auto-optimizer endpoints ────────────────────────────────────────

class OptimizeRequest(BaseModel):
    youtube_video_id: str | None = None  # The real YouTube video ID to update


@router.post("/optimize/{video_id}")
async def trigger_optimizer(video_id: str, body: OptimizeRequest = OptimizeRequest(), db: AsyncSession = Depends(get_db)):
    """
    Manually trigger the auto-optimizer for a video right now.
    Useful for testing or forcing an optimization before the 3-day window.
    """
    from backend.new_files.auto_optimizer import start_optimizer
    
    yt_id = (body.youtube_video_id or "").strip()
    if not yt_id:
        clip_res = await db.execute(select(Clip).where(Clip.id == video_id))
        clip = clip_res.scalar_one_or_none()
        if clip and clip.youtube_short_id:
            yt_id = clip.youtube_short_id
        elif getattr(settings, "TEST_MODE", True):
            yt_id = f"test_yt_{video_id[:8]}"
        else:
            raise HTTPException(
                status_code=400,
                detail="youtube_video_id is required or clip must have a published youtube_short_id",
            )

    try:
        task = start_optimizer(video_id, yt_id)
        return {
            "status": "optimizer_started",
            "video_id": video_id,
            "youtube_video_id": yt_id,
            "message": f"Will optimize up to 3 times if score < {8.0}.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/optimize/{video_id}/flag")
async def set_auto_optimize_flag(
    video_id: str,
    auto_optimize: bool,
    db: AsyncSession = Depends(get_db),
):
    """
    Enable or disable auto-optimization for a video.
    PATCH /api/analytics/optimize/{video_id}/flag?auto_optimize=false
    """
    # Try as Video.id
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        # Try as Clip.id → resolve parent Video
        clip_res = await db.execute(select(Clip).where(Clip.id == video_id))
        clip = clip_res.scalar_one_or_none()
        if clip:
            res2 = await db.execute(select(Video).where(Video.id == clip.video_id))
            video = res2.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")
    video.auto_optimize = auto_optimize
    await db.commit()
    return {
        "target_id": video_id,
        "video_id": video.id,
        "auto_optimize": video.auto_optimize,
        "message": f"Auto-optimize {'enabled' if auto_optimize else 'disabled'}.",
    }


@router.get("/optimize/{video_id}/log")
async def get_optimization_log(video_id: str, db: AsyncSession = Depends(get_db)):
    """Return all optimization attempt logs for a video, newest first."""
    from backend.models.models import OptimizationLog
    result = await db.execute(
        select(OptimizationLog)
        .where(OptimizationLog.video_id == video_id)
        .order_by(desc(OptimizationLog.created_at))
    )
    rows = result.scalars().all()
    if not rows:
        clip_res = await db.execute(select(Clip).where(Clip.id == video_id))
        clip = clip_res.scalar_one_or_none()
        if clip and clip.video_id and clip.video_id != video_id:
            result = await db.execute(
                select(OptimizationLog)
                .where(OptimizationLog.video_id == clip.video_id)
                .order_by(desc(OptimizationLog.created_at))
            )
            rows = result.scalars().all()
        elif not clip:
            clips_res = await db.execute(select(Clip.id).where(Clip.video_id == video_id))
            clip_ids = clips_res.scalars().all()
            if clip_ids:
                result = await db.execute(
                    select(OptimizationLog)
                    .where(OptimizationLog.video_id.in_(clip_ids))
                    .order_by(desc(OptimizationLog.created_at))
                )
                rows = result.scalars().all()

    return {
        "video_id": video_id,
        "total_attempts": len(rows),
        "log": [
            {
                "id": r.id,
                "attempt": r.attempt,
                "new_title": r.new_title,
                "view_score": r.view_score,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }

