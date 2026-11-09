"""
Channel Monitor — watches YouTube channels for new videos and auto-triggers pipeline
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.models import Channel, Video, VideoDecision, VideoDecisionStatus
from backend.services.downloader import get_channel_videos
from backend.core.config import settings

logger = logging.getLogger(__name__)


async def check_channel_for_new_videos(channel: Channel, db: AsyncSession) -> list[dict]:
    """
    Check a monitored channel for new videos.
    Deduplicates against both Video (completed/processed) and VideoDecision (pending/in-flight).
    Returns list of newly discovered video metadata dicts.
    """
    try:
        videos = await get_channel_videos(channel.channel_url, max_results=5)
    except Exception as e:
        logger.error(f"[Monitor] Failed to fetch channel {channel.channel_name}: {e}")
        return []

    raw_profile = channel.processing_profile
    if isinstance(raw_profile, str):
        try:
            profile = json.loads(raw_profile)
        except Exception:
            profile = {}
    elif isinstance(raw_profile, dict):
        profile = raw_profile
    else:
        profile = {}

    baseline_info = profile.get("monitoring_baseline") or {}

    # If the channel has never established a monitoring baseline, establish it now
    if not channel.last_checked_at and not baseline_info:
        logger.info(f"[Monitor] Establishing initial monitoring baseline for channel {channel.channel_name}")
        profile_dict = dict(profile)
        top_vid_id = videos[0].get("id") or (videos[0].get("url", "").split("v=")[-1]) if videos else None
        all_vid_ids = [v.get("id") or v.get("url", "").split("v=")[-1] for v in videos if v.get("id") or "v=" in v.get("url", "")]
        profile_dict["monitoring_baseline"] = {
            "baseline_at": datetime.now(timezone.utc).isoformat(),
            "initial_top_video_id": top_vid_id,
            "known_historical_ids": all_vid_ids,
        }
        channel.processing_profile = profile_dict
        channel.last_checked_at = datetime.now(timezone.utc)
        if top_vid_id:
            channel.last_video_id = top_vid_id
        await db.commit()
        # Historical baseline established: do not auto-enqueue these historical videos
        return []

    baseline_str = baseline_info.get("baseline_at")
    known_historical_ids = set(baseline_info.get("known_historical_ids") or [])
    if baseline_info.get("initial_top_video_id"):
        known_historical_ids.add(baseline_info["initial_top_video_id"])

    baseline_dt = None
    if baseline_str:
        try:
            baseline_dt = datetime.fromisoformat(baseline_str)
        except Exception:
            baseline_dt = None
    if not baseline_dt and channel.created_at:
        baseline_dt = channel.created_at
        if baseline_dt.tzinfo is None:
            baseline_dt = baseline_dt.replace(tzinfo=timezone.utc)

    new_videos = []
    for vid in videos:
        yt_id = vid.get("id") or vid.get("url", "").split("v=")[-1]
        if not yt_id:
            continue

        # Guard: Reject known historical videos from automatic ingestion
        if yt_id in known_historical_ids:
            logger.debug(f"[Monitor] Skipping historical baseline video {yt_id} on {channel.channel_name}")
            continue

        # Guard: Check if video is a ClipForge-generated Short (prevent self-ingestion)
        from backend.services.provenance import check_is_clipforge_short
        is_short, cf_clip, parent_v = await check_is_clipforge_short(db, yt_id)
        if is_short:
            parent_title = parent_v.title if parent_v else "Unknown Source"
            logger.info(
                f"[Monitor] Skipping ClipForge-generated Short {yt_id} on channel {channel.channel_name} "
                f"(origin: '{parent_title}') to prevent self-ingestion."
            )
            continue

        # Check if already processed in Video table
        existing_video = await db.execute(
            select(Video.id).where(Video.youtube_id == yt_id).limit(1)
        )
        if existing_video.scalars().first():
            continue

        # Check if decision record already exists for this channel + youtube video
        existing_decision = await db.execute(
            select(VideoDecision.id).where(
                VideoDecision.channel_id == channel.id,
                VideoDecision.youtube_id == yt_id
            ).limit(1)
        )
        if existing_decision.scalars().first():
            continue

        title = vid.get("title") or "Untitled"
        url = vid.get("url") or f"https://www.youtube.com/watch?v={yt_id}"
        duration = vid.get("duration")
        thumbnails = vid.get("thumbnails", [])
        thumbnail_url = thumbnails[0].get("url") if thumbnails else None
        
        # Parse published date if present
        pub_raw = vid.get("upload_date")
        published_at = None
        if pub_raw and len(pub_raw) == 8:
            try:
                published_at = datetime.strptime(pub_raw, "%Y%m%d").replace(tzinfo=timezone.utc)
            except Exception:
                published_at = None

        # Check if published strictly before the baseline
        if published_at and baseline_dt and published_at < baseline_dt:
            logger.info(f"[Monitor] Skipping pre-baseline video {yt_id} (published {published_at} < baseline {baseline_dt}) on {channel.channel_name}")
            continue

        new_videos.append({
            "id": yt_id,
            "title": title,
            "url": url,
            "duration": float(duration) if duration else None,
            "thumbnail_url": thumbnail_url,
            "published_at": published_at,
        })

    # Update last checked timestamp
    channel.last_checked_at = datetime.now(timezone.utc)
    if new_videos:
        channel.last_video_id = new_videos[0]["id"]
    await db.commit()

    return new_videos


async def run_channel_monitor(db: AsyncSession):
    """
    Main monitoring loop — checks all active channels for new videos.
    Creates VideoDecision rows with a durable 20s countdown for auto_clip channels.
    """
    from backend.tasks.orchestration import resolve_video_decision_countdown_task

    result = await db.execute(
        select(Channel).where(
            Channel.is_active == True,
            (Channel.is_destination == False) | (Channel.is_destination == None)
        )
    )
    channels = result.scalars().all()

    logger.info(f"[Monitor] Checking {len(channels)} active source channels (destinations excluded)...")

    for channel in channels:
        new_vids = await check_channel_for_new_videos(channel, db)
        for vid in new_vids:
            yt_id = vid["id"]
            url = vid["url"]
            logger.info(f"[Monitor] New video found: {vid['title']} ({url}) on channel {channel.channel_name}")

            now = datetime.now(timezone.utc)
            deadline = now + timedelta(seconds=20)
            decision_id = str(uuid.uuid4())

            # Snapshot channel profile with explicit provenance
            profile_snapshot = dict(channel.processing_profile or {})
            profile_snapshot["origin"] = "automatic_monitor"

            # If auto_clip is enabled, schedule 20s countdown
            status = (
                VideoDecisionStatus.AWAITING_SETTINGS.value
                if channel.auto_clip
                else "manual_selection_required"
            )

            decision = VideoDecision(
                id=decision_id,
                channel_id=channel.id,
                youtube_id=yt_id,
                video_title=vid["title"],
                youtube_url=url,
                video_thumbnail=vid["thumbnail_url"],
                status=status,
                decision_deadline=deadline,
                channel_profile_snapshot=profile_snapshot,
                overrides=profile_snapshot,
                created_at=now
            )
            db.add(decision)
            # Commit BEFORE scheduling celery task
            await db.commit()

            if channel.auto_clip:
                try:
                    resolve_video_decision_countdown_task.apply_async(
                        args=[decision_id],
                        countdown=20
                    )
                    logger.info(f"[Monitor] Scheduled 20s countdown resolution for decision {decision_id}")
                except Exception as celery_err:
                    logger.error(f"[Monitor] Failed to schedule countdown task: {celery_err}. Sweep will recover.")

    logger.info("[Monitor] Finished channel check cycle.")
