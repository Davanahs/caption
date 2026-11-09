"""
Provenance & Self-Ingestion Guard Service.

Provides fast queries and helpers to identify ClipForge-generated Shorts,
trace their parent source videos, and prevent output Shorts from re-entering
the processing pipeline as new source videos.
"""
from typing import Optional, Tuple, Dict, Any, List
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from backend.models.models import Clip, Video


def extract_yt_id(url_or_id: str) -> Optional[str]:
    """
    Helper to extract the 11-char YouTube ID from a URL or return a clean ID.
    Supports:
      - Raw 11-char ID
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - URLs with tracking parameters (?si=..., &t=...)
    """
    if not url_or_id:
        return None
    url_str = str(url_or_id).strip()

    # If it is already a pure 11-char ID without url chars
    if len(url_str) == 11 and not any(c in url_str for c in "/?=#&%"):
        return url_str

    if "shorts/" in url_str:
        part = url_str.split("shorts/")[-1]
        match = re.match(r"^([a-zA-Z0-9_-]{11})", part)
        if match:
            return match.group(1)

    if "v=" in url_str:
        part = url_str.split("v=")[-1]
        match = re.match(r"^([a-zA-Z0-9_-]{11})", part)
        if match:
            return match.group(1)

    if "youtu.be/" in url_str:
        part = url_str.split("youtu.be/")[-1]
        match = re.match(r"^([a-zA-Z0-9_-]{11})", part)
        if match:
            return match.group(1)

    # General regex fallback for any 11-char sequence after a slash or equal sign
    fallback_match = re.search(r"(?:/|=)([a-zA-Z0-9_-]{11})(?:[?&#/]|$)", url_str)
    if fallback_match:
        return fallback_match.group(1)

    return url_str.split("/")[-1].split("?")[0] if url_str else None


async def check_is_clipforge_short(
    db: AsyncSession,
    url_or_id: str
) -> Tuple[bool, Optional[Clip], Optional[Video]]:
    """
    Check if a given YouTube ID or URL corresponds to a ClipForge-generated Short.
    Returns:
      (is_clipforge_short, matching_clip, parent_video)
    """
    yt_id = extract_yt_id(url_or_id)
    if not yt_id:
        return False, None, None

    cq = await db.execute(select(Clip).where(Clip.youtube_short_id == yt_id))
    clip = cq.scalars().first()
    if not clip:
        from backend.models.models import VideoTrackingQueue
        tq = await db.execute(select(VideoTrackingQueue).where(VideoTrackingQueue.youtube_video_id == yt_id))
        t_rec = tq.scalars().first()
        if t_rec and t_rec.clip_id:
            cq2 = await db.execute(select(Clip).where(Clip.id == t_rec.clip_id))
            clip = cq2.scalars().first()
    if not clip:
        from backend.models.models import PublishRecord
        pr_q = await db.execute(select(PublishRecord).where(PublishRecord.external_id == yt_id))
        pr_rec = pr_q.scalars().first()
        if pr_rec and pr_rec.clip_id:
            cq3 = await db.execute(select(Clip).where(Clip.id == pr_rec.clip_id))
            clip = cq3.scalars().first()
    if not clip:
        return False, None, None

    parent_video = None
    if clip.video_id:
        pvq = await db.execute(select(Video).where(Video.id == clip.video_id))
        parent_video = pvq.scalars().first()

    return True, clip, parent_video


def check_is_clipforge_short_sync(
    session: Session,
    url_or_id: str
) -> Tuple[bool, Optional[Clip], Optional[Video]]:
    """
    Synchronous version of check_is_clipforge_short for Celery worker tasks or SyncSessionLocal.
    """
    yt_id = extract_yt_id(url_or_id)
    if not yt_id:
        return False, None, None

    clip = session.query(Clip).filter_by(youtube_short_id=yt_id).first()
    if not clip:
        from backend.models.models import VideoTrackingQueue
        t_rec = session.query(VideoTrackingQueue).filter_by(youtube_video_id=yt_id).first()
        if t_rec and t_rec.clip_id:
            clip = session.query(Clip).filter_by(id=t_rec.clip_id).first()
    if not clip:
        from backend.models.models import PublishRecord
        pr_rec = session.query(PublishRecord).filter_by(external_id=yt_id).first()
        if pr_rec and pr_rec.clip_id:
            clip = session.query(Clip).filter_by(id=pr_rec.clip_id).first()
    if not clip:
        return False, None, None

    parent_video = None
    if clip.video_id:
        parent_video = session.query(Video).filter_by(id=clip.video_id).first()

    return True, clip, parent_video


async def get_clipforge_shorts_map(
    db: AsyncSession,
    yt_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Bulk lookup for a list of YouTube IDs or URLs.
    Returns mapping:
      yt_id -> {
        "clip_id": str,
        "clip_title": str,
        "parent_video_id": str,
        "parent_source_id": str | None,
        "parent_source_title": str
      }
    """
    if not yt_ids:
        return {}

    clean_ids = [extract_yt_id(y) for y in yt_ids if y]
    clean_ids = [y for y in clean_ids if y]
    if not clean_ids:
        return {}

    cq = await db.execute(select(Clip).where(Clip.youtube_short_id.in_(clean_ids)))
    matching_clips = cq.scalars().all()
    if not matching_clips:
        return {}

    parent_vids = [c.video_id for c in matching_clips if c.video_id]
    parent_map = {}
    if parent_vids:
        vq = await db.execute(select(Video).where(Video.id.in_(parent_vids)))
        for v in vq.scalars().all():
            parent_map[v.id] = v

    result = {}
    for c in matching_clips:
        pv = parent_map.get(c.video_id)
        result[c.youtube_short_id] = {
            "clip_id": c.id,
            "clip_title": c.title,
            "parent_video_id": c.video_id,
            "parent_source_id": pv.youtube_id if pv else None,
            "parent_source_title": pv.title if pv else "Unknown Source Video"
        }

    return result
