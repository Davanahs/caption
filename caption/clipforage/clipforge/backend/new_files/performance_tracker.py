"""
performance_tracker.py
======================
Phase 4 — Post-upload performance tracking.

Flow:
  1. Wait 5 minutes after upload (let YouTube process the video).
  2. Fetch stats from YouTube Data API v3.
  3. Compute engagement score (0-10).
  4. If score < 8  → trigger auto-optimizer (updates hashtags, description, title).
  5. Wait 5 minutes, then re-track (go to step 2).
  6. Repeat up to MAX_POLLS times or until score >= 8.

All activity is printed to the terminal so it is easy to follow and debug.
"""

import asyncio
import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict

from backend.core.config import settings

# ── Logging setup ─────────────────────────────────────────────────────────────
# Use a dedicated logger that always outputs to the console.
logger = logging.getLogger("clipforge.tracker")
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


# ── Config (overridable via env vars for quick testing) ──────────────────────
import os
INITIAL_WAIT_SECONDS   = int(os.getenv("TRACKER_INITIAL_WAIT_SECONDS", str(5 * 60)))   # default 5 min
RECHECK_WAIT_SECONDS   = int(os.getenv("TRACKER_RECHECK_WAIT_SECONDS",  str(5 * 60)))   # default 5 min
ENGAGEMENT_THRESHOLD   = 8.0
MAX_POLLS              = int(os.getenv("TRACKER_MAX_POLLS", "10"))

print(
    f"[Tracker] Config → initial_wait={INITIAL_WAIT_SECONDS}s  "
    f"recheck_wait={RECHECK_WAIT_SECONDS}s  max_polls={MAX_POLLS}",
    flush=True,
)

# ── In-memory task registry ───────────────────────────────────────────────────
_active_tasks: Dict[str, asyncio.Task] = {}


# ── Engagement score formula ──────────────────────────────────────────────────
def compute_engagement_score(view_count: int, like_count: int, comment_count: int) -> float:
    """
    Simple engagement score (0–10).
      • view_pts      → log-scale, up to 5 pts  (5 pts at ~100 k views)
      • like_ratio    → up to 3 pts
      • comment_ratio → up to 2 pts
    """
    if view_count == 0:
        return 0.0
    view_pts      = min(math.log10(view_count + 1) * 1.0, 5.0)
    like_ratio    = min(like_count    / view_count, 0.3) * 10.0
    comment_ratio = min(comment_count / view_count, 0.2) * 10.0
    return round(min(view_pts + like_ratio + comment_ratio, 10.0), 2)


# ── YouTube API helpers ───────────────────────────────────────────────────────
def _fetch_video_stats(youtube_video_id: str) -> dict:
    """Fetch view/like/comment counts from YouTube Data API v3 (synchronous)."""
    from backend.services.publisher import get_youtube_client
    yt   = get_youtube_client()
    resp = yt.videos().list(part="statistics", id=youtube_video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"YouTube video '{youtube_video_id}' not found or not accessible.")
    stats = items[0].get("statistics", {})
    return {
        "view_count":    int(stats.get("viewCount",    0)),
        "like_count":    int(stats.get("likeCount",    0)),
        "comment_count": int(stats.get("commentCount", 0)),
    }


def _persist_analytics_sync(video_id: str, stats: dict, score: float):
    """Write an analytics snapshot to the database using SQLAlchemy (sync)."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoAnalytics
    from datetime import datetime, timezone
    
    try:
        with SyncSessionLocal() as session:
            analytics = VideoAnalytics(
                video_id=video_id,
                view_count=stats.get("view_count", 0),
                like_count=stats.get("like_count", 0),
                comment_count=stats.get("comment_count", 0),
                view_score=score,
                fetched_at=datetime.now(timezone.utc)
            )
            session.add(analytics)
            session.commit()
    except Exception as e:
        logger.error("[Tracker] DB Error persisting analytics: %s", e)


# ── Banner helpers ────────────────────────────────────────────────────────────
def _banner(title: str):
    width = 60
    logger.info("=" * width)
    logger.info("  %s", title.center(width - 4))
    logger.info("=" * width)


def _section(label: str):
    logger.info("── %s %s", label, "─" * max(0, 56 - len(label)))


# ── Core tracking coroutine ───────────────────────────────────────────────────
# ── Public API ─────────────────────────────────────────────────────────────────
def start_tracking(video_id: str, youtube_video_id: str) -> str:
    """
    Inserts a row into video_tracking_queue for the timestamp-based tracker.
    """
    import uuid
    from datetime import datetime, timedelta, timezone
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoTrackingQueue

    task_id = str(uuid.uuid4())
    try:
        with SyncSessionLocal() as session:
            existing = session.query(VideoTrackingQueue).filter_by(
                clip_id=video_id, 
                youtube_video_id=youtube_video_id
            ).first()

            if not existing:
                now = datetime.now(timezone.utc)
                next_check = now + timedelta(hours=2)  # Default: 2 hours after upload
                
                new_track = VideoTrackingQueue(
                    id=task_id,
                    clip_id=video_id,
                    youtube_video_id=youtube_video_id,
                    uploaded_at=now,
                    next_check_at=next_check,
                    optimization_attempts=0,
                    status="active"
                )
                session.add(new_track)
                session.commit()
                logger.info("[Tracker] (new tracker) Inserted %s to tracking queue (next check: %s)", video_id, next_check.isoformat())
            else:
                task_id = existing.id
                logger.info("[Tracker] (new tracker) Video %s already exists in tracking queue", video_id)
    except Exception as e:
        logger.error("[Tracker] Failed to insert tracking entry: %s", e)

    return task_id


def cancel_tracking(task_id: str) -> bool:
    """Cancel an active tracking task in the queue."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoTrackingQueue
    
    try:
        with SyncSessionLocal() as session:
            trackers = session.query(VideoTrackingQueue).filter(
                (VideoTrackingQueue.id == task_id) | (VideoTrackingQueue.clip_id == task_id)
            ).all()
            
            if trackers:
                for t in trackers:
                    t.status = 'stopped'
                session.commit()
                logger.info("[Tracker] Cancelled tracking for task_id/clip_id=%s", task_id)
                return True
    except Exception as e:
        logger.error("[Tracker] Failed to cancel tracking for %s: %s", task_id, e)
    return False


def list_active_trackers() -> list:
    """Return a list of active trackers from the database."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoTrackingQueue
    
    trackers = []
    try:
        with SyncSessionLocal() as session:
            rows = session.query(VideoTrackingQueue).filter(
                VideoTrackingQueue.status.in_(['active', 'optimized_once'])
            ).all()
            for r in rows:
                trackers.append({
                    "task_id": r.id,
                    "done": False,
                    "clip_id": r.clip_id,
                    "youtube_video_id": r.youtube_video_id,
                    "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
                    "next_check_at": r.next_check_at.isoformat() if r.next_check_at else None,
                    "optimization_attempts": r.optimization_attempts,
                    "last_score": r.last_score,
                    "status": r.status,
                })
    except Exception as e:
        logger.error("[Tracker] Failed to list active trackers: %s", e)
    return trackers

