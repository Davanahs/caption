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

            has_queued_targets = False
            if not youtube_channel_id and isinstance(clip_id, str):
                try:
                    from backend.models.database import SyncSessionLocal
                    from backend.models.models import PublishTarget as PTModel
                    with SyncSessionLocal() as sync_db:
                        has_queued_targets = (
                            sync_db.query(PTModel)
                            .filter(
                                PTModel.clip_id == clip_id,
                                PTModel.status.in_(["queued", "scheduled", "pending"]),
                            )
                            .count()
                            > 0
                        )
                except Exception:
                    has_queued_targets = False

            if not youtube_channel_id and not has_queued_targets:
                logger.error(f"[AutoPublisher] Clip {clip.id} is missing a publish_destination_id or legacy fallback is blocked.")
                # Abort publish attempt for this clip
                clip.publish_status = "failed"
                clip.publish_error = "Missing publish destination."
                await db.commit()
                return
            
        # 2. Validate and Upload OUTSIDE the transaction
        def _upload_wrapper():
            from backend.services.publisher import check_channel_authorization
            from backend.services.outro_service import render_or_reuse_destination_variant_sync

            real_target_ids: list[str] = []
            try:
                from backend.models.database import SyncSessionLocal
                from backend.models.models import PublishTarget as PTModel
                if isinstance(clip_id, str):
                    with SyncSessionLocal() as sync_db:
                        pts = (
                            sync_db.query(PTModel)
                            .filter(
                                PTModel.clip_id == clip_id,
                                PTModel.status.in_(["queued", "scheduled", "pending", "failed"]),
                            )
                            .order_by(PTModel.created_at.asc())
                            .all()
                        )
                        for pt in pts:
                            if isinstance(getattr(pt, "id", None), str) and isinstance(getattr(pt, "destination_id", None), str):
                                real_target_ids.append(pt.id)
            except Exception:
                real_target_ids = []

            def _execute_targets_or_single(vid_path: str | Path, th_path: Path | None):
                if real_target_ids:
                    from backend.models.database import SyncSessionLocal
                    from backend.models.models import PublishTarget as PTModel, Channel as ChannelModel, Clip as ClipModel
                    success_results: list[dict] = []
                    target_errors: list[str] = []
                    now_utc = datetime.now(timezone.utc)

                    for tid in real_target_ids:
                        try:
                            with SyncSessionLocal() as sync_db:
                                pt = sync_db.query(PTModel).filter(PTModel.id == tid).first()
                                if not pt:
                                    continue
                                if pt.status in ("completed", "published") and pt.youtube_video_id:
                                    success_results.append({
                                        "id": pt.youtube_video_id,
                                        "privacy": pt.privacy or "private",
                                        "privacy_confirmed": (pt.privacy or "private") == "private",
                                        "remediation": None,
                                    })
                                    continue

                                dest_ch = sync_db.query(ChannelModel).filter(
                                    ChannelModel.id == pt.destination_id,
                                    ChannelModel.is_destination == True,
                                ).first()
                                if not dest_ch or not dest_ch.is_active:
                                    pt.status = "failed"
                                    pt.publish_stage = "failed"
                                    pt.error_message = "Destination channel is inactive or missing."
                                    sync_db.commit()
                                    target_errors.append(f"{pt.destination_id}: inactive/missing")
                                    continue

                                if not check_channel_authorization(dest_ch.youtube_channel_id):
                                    pt.status = "failed"
                                    pt.publish_stage = "failed"
                                    pt.error_message = "Destination OAuth authorization missing or expired."
                                    sync_db.commit()
                                    target_errors.append(f"{dest_ch.channel_name}: unauthorized")
                                    continue

                                clip_row = sync_db.query(ClipModel).filter(ClipModel.id == clip_id).first()
                                pt.status = "uploading"
                                pt.publish_stage = "uploading"
                                pt.publish_started_at = now_utc
                                sync_db.commit()

                                upload_vid_path = Path(vid_path)
                                applied_outro_id = None
                                variant_key = None
                                if clip_row and isinstance(getattr(dest_ch, "active_outro_id", None), str) and dest_ch.active_outro_id.strip():
                                    variant_info = render_or_reuse_destination_variant_sync(
                                        clip=clip_row,
                                        destination_id=dest_ch.id,
                                        session=sync_db,
                                        local_base_path=Path(vid_path),
                                    )
                                    upload_vid_path = Path(variant_info["video_path"])
                                    applied_outro_id = variant_info.get("outro_id")
                                    variant_key = variant_info.get("storage_key")

                                res = upload_short(
                                    video_path=upload_vid_path,
                                    title=clip_title,
                                    description=clip_desc,
                                    tags=clip_tags,
                                    category=clip_category,
                                    thumbnail_path=th_path,
                                    privacy="private",
                                    idempotency_key=pt.idempotency_key or f"pub_{clip_id}_{dest_ch.id}",
                                    channel_id=dest_ch.youtube_channel_id or dest_ch.id,
                                    clip_id=clip_id,
                                )
                                done_utc = datetime.now(timezone.utc)
                                conf_priv = res.get("privacy", "unconfirmed")
                                rem = res.get("remediation")
                                is_priv_ok = res.get("privacy_confirmed") if "privacy_confirmed" in res else (conf_priv == "private" and not rem)

                                pt.youtube_video_id = res["id"]
                                pt.privacy = conf_priv
                                pt.status = "published" if is_priv_ok else "manual_review"
                                pt.publish_stage = pt.status
                                pt.publish_progress = 100.0 if is_priv_ok else 99.0
                                pt.published_at = done_utc
                                pt.publish_completed_at = done_utc
                                pt.rendered_video_path = str(upload_vid_path)
                                if variant_key:
                                    pt.artifact_storage_key = variant_key
                                if applied_outro_id:
                                    pt.outro_applied_id = applied_outro_id
                                if not is_priv_ok:
                                    pt.error_message = f"Remote privacy check requires manual review: {conf_priv}"
                                else:
                                    pt.error_message = None
                                sync_db.commit()
                                success_results.append(res)
                        except Exception as target_exc:
                            try:
                                with SyncSessionLocal() as err_db:
                                    err_pt = err_db.query(PTModel).filter(PTModel.id == tid).first()
                                    if err_pt:
                                        err_pt.status = "failed"
                                        err_pt.publish_stage = "failed"
                                        err_pt.retry_count = int(err_pt.retry_count or 0) + 1
                                        err_pt.error_message = str(target_exc)[:500]
                                        err_db.commit()
                            except Exception:
                                pass
                            target_errors.append(str(target_exc))

                    if not success_results:
                        raise RuntimeError("; ".join(target_errors) or "All scheduled destinations failed")

                    primary = dict(success_results[0])
                    primary["multi_target_handled"] = True
                    primary["all_succeeded"] = len(target_errors) == 0
                    if target_errors:
                        primary["partial_error"] = (
                            f"{len(success_results)}/{len(real_target_ids)} destinations succeeded; "
                            f"{len(target_errors)} failed: {target_errors[0]}"
                        )
                    return primary

                # Single/legacy path (also supports mock DB contexts cleanly)
                final_vid_path = Path(vid_path)
                try:
                    if isinstance(youtube_channel_id, str) and isinstance(clip_id, str):
                        from backend.models.database import SyncSessionLocal
                        from backend.models.models import Channel as ChannelModel, Clip as ClipModel
                        with SyncSessionLocal() as sync_db:
                            dest_ch = sync_db.query(ChannelModel).filter(
                                (ChannelModel.youtube_channel_id == youtube_channel_id) | (ChannelModel.id == youtube_channel_id),
                                ChannelModel.is_destination == True,
                            ).first()
                            clip_row = sync_db.query(ClipModel).filter(ClipModel.id == clip_id).first()
                            if (
                                dest_ch
                                and clip_row
                                and isinstance(getattr(dest_ch, "active_outro_id", None), str)
                                and dest_ch.active_outro_id.strip()
                            ):
                                variant_info = render_or_reuse_destination_variant_sync(
                                    clip=clip_row,
                                    destination_id=dest_ch.id,
                                    session=sync_db,
                                    local_base_path=Path(vid_path),
                                )
                                final_vid_path = Path(variant_info["video_path"])
                except Exception as outro_exc:
                    if isinstance(youtube_channel_id, str):
                        logger.warning(f"[AutoPublisher] Outro check warning for {clip_id}: {outro_exc}")

                return upload_short(
                    video_path=final_vid_path,
                    title=clip_title,
                    description=clip_desc,
                    tags=clip_tags,
                    category=clip_category,
                    thumbnail_path=th_path,
                    privacy=clip_privacy,
                    channel_id=youtube_channel_id,
                    clip_id=clip_id,
                )

            with managed_download_sync(storage_key=clip_output_path) as vid_path:
                if clip_thumb_path:
                    with managed_download_sync(storage_key=clip_thumb_path) as th_path:
                        return _execute_targets_or_single(vid_path, Path(th_path))
                else:
                    return _execute_targets_or_single(vid_path, None)

        try:
            publish_result = await asyncio.to_thread(_upload_wrapper)
        except Exception as exc:
            logger.error(f"[AutoPublisher] ❌ Publish failed for clip {clip_id}: {exc}")
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Clip).where(Clip.id == clip_id))
                c = result.scalar_one()
                c.publish_status = "failed"
                c.publish_error = f"Publish failed: {exc}"
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
            if publish_result.get("multi_target_handled") and not publish_result.get("all_succeeded", True):
                c.publish_status = "failed"
                c.publish_error = publish_result.get("partial_error") or "One or more destinations failed."
                logger.warning(f"[AutoPublisher] ⚠️ Partial multi-destination publish for clip {clip_id}: {c.publish_error}")
            elif is_confirmed_private:
                c.publish_status = "published"
                c.publish_error = None
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

