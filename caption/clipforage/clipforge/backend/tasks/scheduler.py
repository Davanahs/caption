"""
scheduler.py
============
Background loop that checks for clips with publish_status='queued'
and publishes them when their scheduled time is reached.

After a successful upload, the performance tracker is scheduled to
start 5 minutes later (the tracker handles the delay internally).
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from backend.models.database import AsyncSessionLocal
from backend.models.models import Clip
from backend.services.publisher import upload_short
from backend.models.artifact_sync import managed_download_sync

# ── Logging setup ─────────────────────────────────────────────────────────────
logger = logging.getLogger("clipforge.scheduler")
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


async def run_auto_publisher():
    """
    Check the DB for queued clips whose scheduled time has arrived
    and publish them to YouTube.  Called periodically by the FastAPI
    lifespan background loop.
    """
    logger.debug("[AutoPublisher] Running scheduled publish check…")

    try:
        from backend.models.models import ABExperiment
        
        # 1. Claim a task atomically
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Clip)
                .where(Clip.publish_status == "queued")
                .where(Clip.scheduled_at <= now)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            clip = result.scalar_one_or_none()
            if not clip:
                logger.debug("[AutoPublisher] No clips ready to publish right now.")
                return
                
            logger.info(
                "\n%s\n  [AutoPublisher] 🚀 Claiming: %s  (id=%s)\n%s",
                "=" * 60, clip.title, clip.id, "=" * 60,
            )
            clip.publish_status = "publishing"
            await db.commit()
            
            # extract needed info for the upload while we have the object
            clip_id = clip.id
            clip_title = clip.title
            clip_desc = clip.description or ""
            clip_category = clip.category or "22"
            try:
                import json
                clip_tags = json.loads(clip.tags) if (clip.tags and clip.tags.startswith("[")) else ([t.strip() for t in clip.tags.split(",") if t.strip()] if clip.tags else [])
            except Exception:
                clip_tags = []
            clip_output_path = str(clip.output_path)
            clip_thumb_path = str(clip.thumbnail_path) if clip.thumbnail_path else None
            clip_privacy = "private"
            
            # Resolve channel for credential routing
            from backend.services.publisher import async_resolve_publish_destination
            
            youtube_channel_id = await async_resolve_publish_destination(clip.id, db)
            
            if not youtube_channel_id:
                logger.error(f"[AutoPublisher] Clip {clip.id} is missing a publish_destination_id or legacy fallback is blocked.")
                # Abort publish attempt for this clip
                clip.publish_status = "failed"
                clip.error_message = "Missing publish destination."
                await db.commit()
                return
            
        # 2. Validate and Upload OUTSIDE the transaction
        def _upload_wrapper():
            with managed_download_sync(storage_key=clip_output_path) as vid_path:
                if clip_thumb_path:
                    with managed_download_sync(storage_key=clip_thumb_path) as th_path:
                        return upload_short(
                            video_path=Path(vid_path),
                            title=clip_title,
                            description=clip_desc,
                            tags=clip_tags,
                            category=clip_category,
                            thumbnail_path=Path(th_path),
                            privacy=clip_privacy,
                            channel_id=youtube_channel_id,
                            clip_id=clip_id,
                        )
                else:
                    return upload_short(
                        video_path=Path(vid_path),
                        title=clip_title,
                        description=clip_desc,
                        tags=clip_tags,
                        category=clip_category,
                        thumbnail_path=None,
                        privacy=clip_privacy,
                        channel_id=youtube_channel_id,
                        clip_id=clip_id,
                    )

        try:
            publish_result = await asyncio.to_thread(_upload_wrapper)
        except Exception as exc:
            logger.error(f"[AutoPublisher] ❌ Publish failed for clip {clip_id}: {exc}")
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Clip).where(Clip.id == clip_id))
                c = result.scalar_one()
                c.publish_status = "failed"
                c.error_message = f"Publish failed: {exc}"
                await db.commit()
            return
            
        # 3. Mark success and activate experiment atomically
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Clip).where(Clip.id == clip_id).with_for_update())
            c = result.scalar_one()
            
            confirmed_privacy = publish_result.get("privacy", "unconfirmed")
            c.youtube_short_id = publish_result["id"]
            c.privacy = confirmed_privacy
            c.published_at = datetime.utcnow()
            remediation = publish_result.get("remediation")
            is_confirmed_private = publish_result.get("privacy_confirmed") if "privacy_confirmed" in publish_result else (confirmed_privacy == "private" and not remediation)
            if is_confirmed_private:
                c.publish_status = "published"
                logger.info(f"[AutoPublisher] ✅ Upload successful! YT ID: {publish_result['id']}")
            else:
                c.publish_status = "manual_review"
                if remediation == "auto_remediated_to_private":
                    c.publish_error = (
                        f"Operational Alert: Video {publish_result['id']} returned 'public' upon upload; "
                        f"auto-remediated to 'private' via safe update and verified via read-back. Preserved for review."
                    )
                elif remediation and any(k in remediation for k in ("exception", "failed", "still_public", "readback", "incomplete", "withheld")):
                    c.publish_error = (
                        f"CRITICAL PRIVACY ALERT: Video {publish_result['id']} returned 'public' and remediation could not be confirmed ({remediation}). "
                        f"VIDEO MAY BE PUBLIC ON YOUTUBE! Immediate operator review required."
                    )
                else:
                    c.publish_error = f"Remote privacy mismatch or unconfirmed: '{confirmed_privacy}'"
                logger.warning(f"[AutoPublisher] ⚠️ Upload completed but required review: {c.publish_error}")
            
            exp_result = await db.execute(
                select(ABExperiment)
                .where(ABExperiment.clip_id == clip_id)
                .with_for_update()
            )
            exp = exp_result.scalar_one_or_none()
            if exp and exp.status == "pending_publish":
                exp.youtube_short_id = publish_result["id"]
                exp.status = "running"
                exp.started_at = datetime.utcnow()
                logger.info(f"[AutoPublisher] 🧪 Activated A/B Experiment for clip {clip_id}")
                
            await db.commit()
            
        # 4. Schedule performance tracker
        try:
            from backend.services.performance_tracker import start_tracking
            task_id = start_tracking(clip_id, publish_result["id"])
            logger.info(f"[AutoPublisher] ⏱ Performance tracker scheduled (starts in 5 min). task_id={task_id}")
        except Exception as tracker_err:
            logger.warning(f"[AutoPublisher] ⚠ Tracker not started for {clip_id}: {tracker_err}")

    except Exception as exc:
        logger.error(f"[AutoPublisher] Unexpected error in publish loop: {exc}")


async def run_tracker_job():
    """
    Check the DB tracking queue and run performance evaluations / optimizations
    for due videos. Called periodically by the FastAPI background scheduler.
    """
    from backend.services.realtime_tracker import run_realtime_tracker
    try:
        await run_realtime_tracker()
    except Exception as exc:
        logger.error("[TrackerJob] Unexpected error in realtime tracker: %s", exc)

