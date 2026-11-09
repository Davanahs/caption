import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import OptimizationContext, VideoTrackingQueue
from backend.new_files.performance_tracker import (
    compute_engagement_score,
    _fetch_video_stats,
    _persist_analytics_sync,
)
from backend.new_files.auto_optimizer import run_single_optimization
from backend.services.pipeline_analytics import start_phase, complete_phase

logger = logging.getLogger("clipforge.realtime_tracker")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False


# ── Optimization Context Helpers ───────────────────────────────────────────────

def _get_optimization_context(session, clip_id: str) -> dict:
    """Fetch existing optimization context for a clip, or return empty defaults."""
    try:
        ctx = session.query(OptimizationContext).filter_by(clip_id=clip_id).first()
        if ctx:
            return {
                "previous_titles": json.loads(ctx.previous_titles or "[]"),
                "previous_descriptions": json.loads(ctx.previous_descriptions or "[]"),
                "previous_hashtags": json.loads(ctx.previous_hashtags or "[]"),
                "optimization_attempt": ctx.optimization_attempt,
                "optimization_reason": ctx.optimization_reason,
                "previous_scores": json.loads(ctx.previous_scores or "[]"),
            }
    except Exception as e:
        logger.error(f"[RealTimeTracker] get optimization_context error: {e}")
    return {
        "previous_titles": [],
        "previous_descriptions": [],
        "previous_hashtags": [],
        "optimization_attempt": 0,
        "optimization_reason": "",
        "previous_scores": [],
    }


def _update_optimization_context(
    session,
    clip_id: str,
    new_title: str,
    new_description: str,
    new_hashtags: list,
    attempt: int,
    score: float,
    reason: str,
):
    """Upsert the optimization context for a clip after each attempt."""
    try:
        ctx_data = _get_optimization_context(session, clip_id)
        titles = ctx_data["previous_titles"] + [new_title]
        descs = ctx_data["previous_descriptions"] + [new_description]
        tags = ctx_data["previous_hashtags"] + [new_hashtags]
        scores = ctx_data["previous_scores"] + [score]

        ctx = session.query(OptimizationContext).filter_by(clip_id=clip_id).first()
        if ctx:
            ctx.previous_titles = json.dumps(titles)
            ctx.previous_descriptions = json.dumps(descs)
            ctx.previous_hashtags = json.dumps(tags)
            ctx.optimization_attempt = attempt
            ctx.optimization_reason = reason
            ctx.previous_scores = json.dumps(scores)
        else:
            new_ctx = OptimizationContext(
                id=str(uuid.uuid4()),
                clip_id=clip_id,
                previous_titles=json.dumps(titles),
                previous_descriptions=json.dumps(descs),
                previous_hashtags=json.dumps(tags),
                optimization_attempt=attempt,
                optimization_reason=reason,
                previous_scores=json.dumps(scores),
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_ctx)
        session.commit()
        logger.info(f"[RealTimeTracker] Updated optimization_context for clip_id={clip_id} (attempt={attempt})")
    except Exception as e:
        logger.error(f"[RealTimeTracker] Failed to update optimization_context: {e}")


# ── Main Tracker ───────────────────────────────────────────────────────────────

async def run_realtime_tracker():
    """
    Scans the video_tracking_queue for any due checks (next_check_at <= now)
    where status is 'active' or 'optimized_once'.
    Runs every 1 minute via APScheduler.
    Stores and reuses optimization_context to avoid repeated metadata generation.
    """
    tracker_start = start_phase("system", "tracker execution")
    logger.info("[RealTimeTracker] Scanning video_tracking_queue for due videos...")

    now = datetime.now(timezone.utc)

    try:
        with SyncSessionLocal() as session:
            due_videos = session.query(VideoTrackingQueue).filter(
                VideoTrackingQueue.status.in_(['active', 'optimized_once']),
                VideoTrackingQueue.next_check_at <= now
            ).all()

            if not due_videos:
                logger.info("[RealTimeTracker] No due videos to track in this run.")
                complete_phase("system", "tracker execution", tracker_start)
                return

            logger.info(f"[RealTimeTracker] Found {len(due_videos)} due video(s) to process.")

            for video in due_videos:
                clip_id = video.clip_id
                youtube_video_id = video.youtube_video_id
                attempts = video.optimization_attempts
                status = video.status
                
                logger.info(
                    f"[RealTimeTracker] Processing clip_id={clip_id} "
                    f"(yt={youtube_video_id}, status={status}, attempts={attempts})"
                )

                # 1. Fetch stats
                stats_start = start_phase(clip_id, "tracker execution")
                try:
                    stats = await asyncio.get_event_loop().run_in_executor(
                        None, _fetch_video_stats, youtube_video_id
                    )
                except Exception as exc:
                    logger.warning(
                        f"[RealTimeTracker] Fetch stats failed for yt={youtube_video_id}: {exc}. Using zero values."
                    )
                    stats = {"view_count": 0, "like_count": 0, "comment_count": 0}

                # 2. Compute engagement score
                score = compute_engagement_score(
                    stats["view_count"], stats["like_count"], stats["comment_count"]
                )
                logger.info(
                    f"[RealTimeTracker] Stats for {youtube_video_id}: "
                    f"views={stats['view_count']} likes={stats['like_count']} "
                    f"comments={stats['comment_count']} score={score}"
                )
                complete_phase(clip_id, "tracker execution", stats_start)

                # 3. Persist analytics snapshot locally
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, _persist_analytics_sync, clip_id, stats, score
                    )
                except Exception as db_err:
                    logger.error(f"[RealTimeTracker] Failed to persist analytics for {clip_id}: {db_err}")

                # 4. Load existing optimization_context for this clip (to avoid repeated metadata)
                opt_ctx = _get_optimization_context(session, clip_id)

                # 5. Decision logic
                new_status = status
                new_attempts = attempts
                new_next_check_at = video.next_check_at

                if score >= 8.0:
                    logger.info(f"[RealTimeTracker] 🎉 Score {score} >= 8.0 for clip_id={clip_id}. Mark COMPLETED.")
                    new_status = "completed"
                elif attempts == 0:
                    logger.info(
                        f"[RealTimeTracker] 🔴 Score {score} < 8.0 for clip_id={clip_id}. "
                        f"Triggering optimization #1..."
                    )
                    opt_start = start_phase(clip_id, "optimization")
                    try:
                        new_meta = await run_single_optimization(
                            clip_id, youtube_video_id, score, poll_num=1, opt_ctx=opt_ctx
                        )
                    except Exception as opt_exc:
                        logger.error(f"[RealTimeTracker] Optimization #1 error: {opt_exc}")
                        new_meta = {}
                        complete_phase(clip_id, "optimization", opt_start, success=False, error_message=str(opt_exc))
                    else:
                        complete_phase(clip_id, "optimization", opt_start)
                        # Store context
                        _update_optimization_context(
                            session, clip_id,
                            new_title=new_meta.get("title", ""),
                            new_description=new_meta.get("description", ""),
                            new_hashtags=new_meta.get("hashtags", []),
                            attempt=1,
                            score=score,
                            reason=f"score {score} < 8.0 after 2hr",
                        )

                    new_attempts = 1
                    new_status = "optimized_once"
                    new_next_check_at = now + timedelta(hours=4)

                elif attempts == 1:
                    logger.info(
                        f"[RealTimeTracker] 🔴 Score {score} < 8.0 for clip_id={clip_id}. "
                        f"Triggering optimization #2 (final)..."
                    )
                    opt_start = start_phase(clip_id, "optimization")
                    try:
                        new_meta = await run_single_optimization(
                            clip_id, youtube_video_id, score, poll_num=2, opt_ctx=opt_ctx
                        )
                    except Exception as opt_exc:
                        logger.error(f"[RealTimeTracker] Optimization #2 error: {opt_exc}")
                        new_meta = {}
                        complete_phase(clip_id, "optimization", opt_start, success=False, error_message=str(opt_exc))
                    else:
                        complete_phase(clip_id, "optimization", opt_start)
                        _update_optimization_context(
                            session, clip_id,
                            new_title=new_meta.get("title", ""),
                            new_description=new_meta.get("description", ""),
                            new_hashtags=new_meta.get("hashtags", []),
                            attempt=2,
                            score=score,
                            reason=f"score {score} < 8.0 after 4hr — final attempt",
                        )

                    new_attempts = 2
                    new_status = "stopped"

                # 6. Update queue row
                try:
                    video.status = new_status
                    video.next_check_at = new_next_check_at
                    video.optimization_attempts = new_attempts
                    video.last_score = score
                    session.commit()
                    logger.info(
                        f"[RealTimeTracker] DB Updated for clip_id={clip_id}: "
                        f"status={new_status}, attempts={new_attempts}, next_check={new_next_check_at.isoformat()}"
                    )
                except Exception as db_err:
                    logger.error(f"[RealTimeTracker] Failed to update DB for clip_id={clip_id}: {db_err}")

    except Exception as e:
        logger.error(f"[RealTimeTracker] DB error: {e}")
        complete_phase("system", "tracker execution", tracker_start, success=False, error_message=str(e))
        return

    complete_phase("system", "tracker execution", tracker_start)
    logger.info("[RealTimeTracker] Done processing due videos.")
