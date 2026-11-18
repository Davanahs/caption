"""
Live Stream Service — Handles YouTube live stream detection, segment downloading,
and lifecycle orchestration for ClipForge Live Streaming.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.models import LiveStreamJob, LiveStreamSegment, Video
from backend.services.downloader import extract_youtube_id, get_yt_dlp_base_args

logger = logging.getLogger(__name__)


async def get_livestream_metadata(url: str) -> dict:
    """
    Inspects a YouTube URL using yt-dlp to extract live status and stream info.
    """
    yt_id = extract_youtube_id(url)
    if not yt_id:
        return {"valid": False, "error": "Invalid YouTube URL format"}

    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--quiet",
    ]
    cmd.extend(get_yt_dlp_base_args())
    cmd.append(url)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_text = stderr.decode('utf-8', errors='ignore')
            if "unavailable" in err_text.lower():
                return {"valid": False, "error": "This video is unavailable or does not exist."}
            elif "private" in err_text.lower():
                return {"valid": False, "error": "This video is private."}

            # Attempt YouTube oEmbed fallback before reporting error
            try:
                import urllib.request
                oe_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={yt_id}&format=json"
                req_oe = urllib.request.Request(oe_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_oe, timeout=5) as resp:
                    if resp.status == 200:
                        oe_data = json.loads(resp.read().decode('utf-8'))
                        return {
                            "valid": True,
                            "youtube_id": yt_id,
                            "title": oe_data.get("title", f"Livestream {yt_id}"),
                            "thumbnail_url": oe_data.get("thumbnail_url", f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg"),
                            "channel_name": oe_data.get("author_name", "YouTube Streamer"),
                            "channel_id": None,
                            "is_live": True,
                            "live_status": "is_live",
                            "duration": 0.0,
                            "raw_info": {"webpage_url": url},
                            "message": "Stream metadata retrieved via YouTube oEmbed."
                        }
            except Exception as oe_err:
                logger.warning(f"[LiveStreamService] oEmbed fallback failed: {oe_err}")

            return {"valid": False, "error": f"Failed to retrieve video information: {err_text[-120:].strip()}"}

        data = json.loads(stdout.decode('utf-8', errors='ignore'))
    except Exception as e:
        return {"valid": False, "error": str(e)}

    is_live = bool(data.get("is_live", False))
    live_status = data.get("live_status", "not_live")
    if not live_status or live_status == "none":
        live_status = "is_live" if is_live else "not_live"

    duration = data.get("duration")
    if duration is not None:
        try:
            duration = float(duration)
        except (ValueError, TypeError):
            duration = 0.0
    elif is_live or live_status == "is_live":
        import time
        release_ts = data.get("release_timestamp") or data.get("timestamp")
        epoch = data.get("epoch") or time.time()
        if release_ts:
            try:
                duration = max(0.0, float(epoch - release_ts))
            except Exception:
                duration = 0.0
        else:
            duration = 0.0
    else:
        duration = 0.0

    thumbnail = data.get("thumbnail") or (data.get("thumbnails")[-1]["url"] if data.get("thumbnails") else None)
    title = data.get("title", f"Livestream {yt_id}")
    channel_name = data.get("uploader") or data.get("channel") or "YouTube Channel"
    channel_id = data.get("channel_id")

    return {
        "valid": True,
        "youtube_id": yt_id,
        "title": title,
        "thumbnail_url": thumbnail,
        "channel_name": channel_name,
        "channel_id": channel_id,
        "is_live": is_live,
        "live_status": live_status,
        "duration": duration,
        "raw_info": {
            "webpage_url": data.get("webpage_url", url),
            "formats_count": len(data.get("formats", [])),
        }
    }


async def validate_livestream(url: str, db: AsyncSession) -> dict:
    """
    Validates the YouTube livestream URL and checks for duplicate active monitoring jobs.
    """
    meta = await get_livestream_metadata(url)
    if not meta.get("valid"):
        return {
            "valid": False,
            "error": meta.get("error", "Unable to inspect YouTube URL"),
            "status_code": 400
        }

    yt_id = meta["youtube_id"]

    # Check for active monitoring jobs
    stmt = select(LiveStreamJob).where(
        LiveStreamJob.youtube_id == yt_id,
        LiveStreamJob.status.in_(["monitoring", "processing", "waiting"])
    )
    res = await db.execute(stmt)
    existing_job = res.scalars().first()

    is_already_monitored = existing_job is not None
    existing_job_id = existing_job.id if existing_job else None

    # Construct descriptive user-friendly message
    if is_already_monitored:
        message = f"This live stream is already actively being monitored (Job ID: {existing_job_id[:8]}...)."
    elif meta["is_live"] or meta["live_status"] == "is_live":
        message = "Live stream is currently active and ready for automatic clip monitoring."
    elif meta["live_status"] == "is_upcoming":
        message = "This is a scheduled upcoming livestream that has not started broadcasting yet."
    elif meta["live_status"] == "was_live":
        message = "This livestream has already ended and is now an archived video."
    else:
        message = "This video is not a livestream (it is a standard uploaded video)."

    return {
        "valid": True,
        "youtube_id": yt_id,
        "title": meta["title"],
        "thumbnail_url": meta["thumbnail_url"],
        "channel_name": meta["channel_name"],
        "channel_id": meta["channel_id"],
        "is_live": meta["is_live"],
        "live_status": meta["live_status"],
        "duration": meta["duration"],
        "is_already_monitored": is_already_monitored,
        "existing_job_id": existing_job_id,
        "message": message
    }
