"""
Performance Tracker — polls YouTube Analytics every 12h for 3 days after upload.

ViewScore formula:
  engagement_rate = ((likes + comments) / views) * 100
  ViewScore = (views/100) + (likes/10) + (comments/5) + (engagement_rate * 5)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import Clip


# ── ViewScore Calculation ─────────────────────────────────────────────────────

def calculate_view_score(views: int, likes: int, comments: int) -> tuple[float, float]:
    """
    Returns (view_score, engagement_rate).
    engagement_rate is in percent.
    """
    if views <= 0:
        return 0.0, 0.0
    engagement_rate = ((likes + comments) / views) * 100
    view_score = (views / 100) + (likes / 10) + (comments / 5) + (engagement_rate * 5)
    return round(view_score, 2), round(engagement_rate, 2)


# ── YouTube Analytics Fetch ───────────────────────────────────────────────────

def fetch_video_analytics(youtube_short_id: str) -> dict:
    """
    Fetch real-time video statistics from YouTube Data API v3.
    Returns: { views, likes, comments, engagement_rate, view_score }
    """
    from backend.services.publisher import get_youtube_client

    youtube = get_youtube_client()
    response = youtube.videos().list(
        part="statistics",
        id=youtube_short_id
    ).execute()

    items = response.get("items", [])
    if not items:
        raise ValueError(f"No YouTube video found for id: {youtube_short_id}")

    stats = items[0].get("statistics", {})
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))

    view_score, engagement_rate = calculate_view_score(views, likes, comments)

    return {
        "views": views,
        "likes": likes,
        "comments": comments,
        "engagement_rate": engagement_rate,
        "view_score": view_score,
    }


# ── DB Analytics Update ───────────────────────────────────────────────────────

def save_analytics_snapshot(clip_id: str, analytics: dict) -> None:
    """Save the latest analytics snapshot to the DB."""
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if clip:
                clip.analytics_views = analytics["views"]
                clip.analytics_likes = analytics["likes"]
                clip.analytics_comments = analytics["comments"]
                clip.analytics_engagement_rate = analytics["engagement_rate"]
                clip.analytics_view_score = analytics["view_score"]
                clip.analytics_last_checked = datetime.now(timezone.utc).isoformat()
                session.commit()
                print(f"[Tracker] Saved analytics for clip {clip_id}: ViewScore={analytics['view_score']}")
    except Exception as e:
        print(f"[Tracker] Error saving analytics snapshot: {e}")


# ── Scheduler Logic ───────────────────────────────────────────────────────────

def get_clips_needing_tracking() -> list[dict]:
    """
    Returns published clips that:
    - Were published within the last 3 days (72h tracking window)
    - Have fewer than 6 analytics checks (every 12h × 6 = 72h)
    - Have a youtube_short_id
    - Need optimization (optimization_attempts < 3 OR view_score not yet >= 8)
    """
    try:
        with SyncSessionLocal() as session:
            three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
            clips = session.query(Clip).filter(
                Clip.publish_status == 'published',
                Clip.youtube_short_id.isnot(None),
                Clip.analytics_check_count < 6,
                Clip.optimization_attempts < 3,
                Clip.analytics_view_score < 8.0,
                Clip.published_at > three_days_ago
            ).all()
            
            return [
                {
                    "id": c.id, "youtube_short_id": c.youtube_short_id,
                    "analytics_check_count": c.analytics_check_count or 0,
                    "analytics_last_checked": c.analytics_last_checked,
                    "optimization_attempts": c.optimization_attempts or 0,
                    "analytics_view_score": c.analytics_view_score or 0.0,
                    "title": c.title,
                    "transcript_segment": c.transcript_segment,
                }
                for c in clips
            ]
    except Exception as e:
        print(f"[Tracker] Error getting clips needing tracking: {e}")
        return []


def should_check_now(clip: dict, interval_hours: int = 12) -> bool:
    """Return True if it's time for the next analytics check (every 12h)."""
    last_checked = clip.get("analytics_last_checked")
    if not last_checked:
        return True
    try:
        last_dt = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_dt >= timedelta(hours=interval_hours)
    except Exception:
        return True


def increment_check_count(clip_id: str) -> None:
    """Increment the analytics check count for a clip."""
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if clip:
                clip.analytics_check_count = (clip.analytics_check_count or 0) + 1
                session.commit()
    except Exception as e:
        print(f"[Tracker] Error incrementing check count: {e}")
