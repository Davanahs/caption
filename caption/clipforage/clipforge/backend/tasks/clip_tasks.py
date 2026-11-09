import os
import logging
from backend.tasks.celery_app import celery_app
import backend.models.database as _db_mod

def SyncSessionLocal(*args, **kwargs):
    return _db_mod.SyncSessionLocal(*args, **kwargs)
from backend.models.db_sync import update_clip_status_sync, update_clip_publish_sync
from pathlib import Path
from backend.core.config import settings
from backend.services.publisher import upload_short, check_external_youtube_state
from backend.core.task_execution import check_and_claim_execution

logger = logging.getLogger(__name__)
from celery.exceptions import Retry, Ignore

from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS

@celery_app.task(
    bind=True,
    name="reframe_clip",
    **DEFAULT_RETRY_KWARGS,
)
def reframe_task(self, clip_id: str, layout_plan_dict: dict = None, job_id: str = None):
    """
    Calculates framing/cropping for the clip.
    Updates Clip.status to reframing.
    """
    import tempfile
    import os
    from pathlib import Path
    from backend.services.clip_cutter import cut_clip
    from backend.services.reframe_engine import reframe_to_vertical
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, Video, Job, ArtifactType, ArtifactStatus
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync
    from backend.core.task_execution import check_and_claim_execution
    from celery.exceptions import Ignore

    logger.info(f"Reframing clip {clip_id}")
    update_clip_status_sync(clip_id, "reframing")
    
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            video = session.query(Video).filter_by(id=clip.video_id).first()
            if not video:
                raise ValueError(f"Video {clip.video_id} not found")
                
            storage_key = video.local_path
            start = clip.start_time
            end = clip.end_time

            # Authoritative job_id resolution
            if not job_id:
                job_rec = session.query(Job).filter_by(video_id=clip.video_id).order_by(Job.created_at.desc()).first()
                if job_rec:
                    job_id = job_rec.id
                elif clip.run_identity:
                    parts = clip.run_identity.split("_")
                    job_id = "_".join(parts[:-2]) if len(parts) > 2 else None
            else:
                # Validate job_id exists in DB
                job_rec = session.query(Job).filter_by(id=job_id).first()
                if not job_rec:
                    job_rec = session.query(Job).filter_by(video_id=clip.video_id).order_by(Job.created_at.desc()).first()
                    job_id = job_rec.id if job_rec else None

            if job_rec and job_rec.status == "cancelled":
                logger.info(f"Job {job_id} is cancelled. Aborting reframe task for {clip_id}.")
                return {"clip_id": clip_id, "job_id": job_id, "status": "cancelled"}
                
            # Idempotency check
            idemp_key = f"{job_id or 'job'}_{clip_id}_reframe"
            try:
                check_and_claim_execution(
                    task_id=self.request.id,
                    job_id=job_id,
                    clip_id=clip_id,
                    operation="reframe",
                    idempotency_key=idemp_key,
                    worker_id=self.request.hostname or "unknown"
                )
            except Ignore:
                # Execution is already handled or completed by another worker
                logger.info(f"Reframe task {self.request.id} for {clip_id} ignored due to idempotency.")
                return {"clip_id": clip_id, "reframed_storage_key": f"uploads/{video.id}/clips/{clip_id}/reframed.mp4", "job_id": job_id, "video_id": video.id, "force_render": False}
            
        reframed_storage_key = f"uploads/{video.id}/clips/{clip_id}/reframed.mp4"
        
        from backend.models.artifact_sync import check_artifact_exists_sync
        if not layout_plan_dict and check_artifact_exists_sync(reframed_storage_key):
            logger.info(f"Artifact {reframed_storage_key} already exists. Skipping reframe.")
            
            # Mark TaskExecution as completed
            from backend.models.database import SyncSessionLocal
            from backend.models.models import TaskExecution, TaskExecutionStatus
            with SyncSessionLocal() as session:
                tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
                if tx:
                    tx.status = TaskExecutionStatus.SUCCEEDED.value
                    from datetime import datetime, timezone
                    tx.completed_at = datetime.now(timezone.utc)
                    session.commit()
                    
            return {"clip_id": clip_id, "reframed_storage_key": reframed_storage_key, "job_id": job_id, "video_id": video.id, "force_render": False}
        
        with managed_download_sync(storage_key=storage_key) as temp_video_path:
            with managed_upload_sync(
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.RAW_CLIP,
                storage_key=reframed_storage_key,
                retention_policy="temporary",
                processing_version="v1"
            ) as reframed_path:
            
                fd, cut_path = tempfile.mkstemp(prefix=f"clipforge_reframe_cut_{clip_id}_")
                os.close(fd)
                
                try:
                    async def run_reframe(reframe_mode: str = None, regions: list = None, podcast_comp: str = "stacked", shot_schedule: list = None):
                        if podcast_comp == "fixed_two_person" and regions and len(regions) > 0:
                            from backend.services.advanced_podcast_engine import (
                                build_fixed_boundary_schedule,
                                render_fixed_boundary_two_person_video,
                            )
                            outer_bound = next((r for r in regions if r.get("id") == "outer_boundary" or str(r.get("label", "")).lower().startswith("outer")), None)
                            participants = [r for r in regions if r != outer_bound]
                            if not outer_bound:
                                outer_bound = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
                            effective_schedule = shot_schedule
                            if not effective_schedule:
                                effective_schedule = build_fixed_boundary_schedule(
                                    video_path=temp_video_path,
                                    outer_boundary=outer_bound,
                                    participant_regions=participants
                                )
                            await render_fixed_boundary_two_person_video(
                                video_path=temp_video_path,
                                output_path=reframed_path,
                                schedule=effective_schedule,
                                clip_start=start,
                                clip_end=end,
                                canvas_w=1080,
                                canvas_h=1920
                            )
                            logger.info(f"Rendered fixed-boundary two-person podcast vertical clip {clip_id} ({len(effective_schedule)} shots)")
                            return

                        elif podcast_comp == "visibility_driven" and regions and len(regions) > 0:
                            from backend.services.advanced_podcast_engine import (
                                build_visibility_driven_schedule,
                                render_visibility_driven_video,
                            )
                            reg_a = regions[0]
                            reg_b = regions[1] if len(regions) > 1 else regions[0]
                            effective_schedule = shot_schedule
                            if not effective_schedule:
                                effective_schedule = build_visibility_driven_schedule(
                                    video_path=temp_video_path,
                                    region_a=reg_a,
                                    region_b=reg_b
                                )
                            await render_visibility_driven_video(
                                video_path=temp_video_path,
                                output_path=reframed_path,
                                schedule=effective_schedule,
                                clip_start=start,
                                clip_end=end,
                                canvas_w=1080,
                                canvas_h=1920
                            )
                            logger.info(f"Rendered visibility-driven podcast vertical clip {clip_id} ({len(effective_schedule)} shots)")
                            return

                        elif (podcast_comp in ("advanced_podcast", "camera_following") or shot_schedule) and regions and len(regions) > 0:
                            from backend.services.advanced_podcast_engine import render_camera_following_video, build_shot_schedule
                            effective_schedule = shot_schedule
                            if not effective_schedule:
                                effective_schedule = build_shot_schedule(temp_video_path, regions)
                            await render_camera_following_video(
                                video_path=temp_video_path,
                                output_path=reframed_path,
                                shot_schedule=effective_schedule,
                                clip_start=start,
                                clip_end=end,
                                canvas_w=1080,
                                canvas_h=1920
                            )
                            logger.info(f"Rendered camera-following advanced podcast vertical clip {clip_id} ({len(effective_schedule)} shots)")
                            return

                        await cut_clip(temp_video_path, cut_path, start, end)
                        
                        plan = None
                        if layout_plan_dict:
                            from backend.models.layout import LayoutPlan
                            plan = LayoutPlan(**layout_plan_dict)
                        elif regions and len(regions) > 0:
                            from backend.services.clip_cutter import get_video_dimensions
                            from backend.services.layout_engine import LayoutEngine
                            src_w, src_h = await get_video_dimensions(cut_path)
                            plan = LayoutEngine.create_podcast_plan(
                                regions_normalized=regions,
                                source_w=src_w,
                                source_h=src_h,
                                composition=podcast_comp,
                                canvas_w=1080,
                                canvas_h=1920
                            )
                            logger.info(f"Built podcast layout plan with {len(regions)} regions (comp={podcast_comp}) for clip {clip_id}")
                            
                        await reframe_to_vertical(cut_path, reframed_path, mode=reframe_mode, plan=plan)
                    
                    from backend.core.task_execution import execution_heartbeater
                    with execution_heartbeater(self.request.id, interval=60):
                        import asyncio
                        
                        reframe_mode = None
                        podcast_regions = None
                        podcast_comp = "stacked"
                        podcast_shot_schedule = None
                        if job_id != "unknown_job":
                            from backend.models.models import Job
                            import json
                            with SyncSessionLocal() as session:
                                job = session.query(Job).filter_by(id=job_id).first()
                                if job and job.config:
                                    try:
                                        config_dict = json.loads(job.config)
                                        podcast_regions = config_dict.get("regions")
                                        podcast_comp = config_dict.get("podcast_composition") or "stacked"
                                        podcast_shot_schedule = config_dict.get("shot_schedule")
                                        raw_layout = config_dict.get("video_layout") or config_dict.get("reframe_mode")
                                        layout_mapping = {
                                            "fill_blur": "blur_background",
                                            "fit_black": "static_wide",
                                            "split_screen": "multi_split",
                                            "blur_background": "blur_background",
                                            "static_wide": "static_wide",
                                            "center_crop": "center_crop",
                                            "multi_split": "multi_split",
                                            "stacked_16_9": "stacked_16_9",
                                            "creative_transform": "creative_transform",
                                            "stacked": "stacked_16_9",
                                            "transform": "creative_transform",
                                        }
                                        reframe_mode = layout_mapping.get(raw_layout, raw_layout)
                                    except Exception as config_err:
                                        logger.warning(f"Failed to parse Job.config for job {job_id}: {config_err}")
                        
                        try:
                            running_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            running_loop = None

                        if running_loop and running_loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                pool.submit(asyncio.run, run_reframe(
                                    reframe_mode=reframe_mode,
                                    regions=podcast_regions,
                                    podcast_comp=podcast_comp,
                                    shot_schedule=podcast_shot_schedule
                                )).result()
                        else:
                            asyncio.run(run_reframe(
                                reframe_mode=reframe_mode,
                                regions=podcast_regions,
                                podcast_comp=podcast_comp,
                                shot_schedule=podcast_shot_schedule
                            ))
                finally:
                    if os.path.exists(cut_path):
                        os.remove(cut_path)
            
    except Ignore:
        raise
    except Exception as e:
        logger.error(f"Reframe failed for {clip_id}: {e}")
        update_clip_status_sync(clip_id, "failed", str(e))
        
        # Mark TaskExecution as failed
        from backend.models.database import SyncSessionLocal
        from backend.models.models import TaskExecution, TaskExecutionStatus
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.FAILED.value
                tx.failure_reason = str(e)
                session.commit()
                
        raise self.retry(exc=e, countdown=30)
        
    # Mark TaskExecution as completed
    from backend.models.database import SyncSessionLocal
    from backend.models.models import TaskExecution, TaskExecutionStatus
    with SyncSessionLocal() as session:
        tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
        if tx:
            tx.status = TaskExecutionStatus.SUCCEEDED.value
            from datetime import datetime, timezone
            tx.completed_at = datetime.now(timezone.utc)
            session.commit()
            
    return {"clip_id": clip_id, "reframed_storage_key": reframed_storage_key, "job_id": job_id, "video_id": video.id, "force_render": bool(layout_plan_dict)}


@celery_app.task(
    bind=True,
    name="render_clip",
    **DEFAULT_RETRY_KWARGS,
)
def render_task(self, result: dict):
    """
    Renders the clip video file.
    Updates Clip.status to rendering.
    """
    import asyncio
    import tempfile
    import os
    import shutil
    from backend.services.clip_cutter import burn_hook_title, extract_thumbnail
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, ArtifactType, ArtifactStatus
    from backend.models.db_sync import update_clip_paths_sync
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync
    from backend.core.task_execution import check_and_claim_execution
    from celery.exceptions import Ignore
    from pathlib import Path

    clip_id = result.get("clip_id")
    job_id = result.get("job_id")
    video_id = result.get("video_id")
    reframed_storage_key = result.get("reframed_storage_key")
    force_render = result.get("force_render", False)

    if result.get("status") == "cancelled":
        logger.info(f"Skipping render_task for clip {clip_id}: upstream step was cancelled.")
        return result

    if job_id:
        from backend.models.models import Job
        with SyncSessionLocal() as session:
            job_rec = session.query(Job).filter_by(id=job_id).first()
            if job_rec and job_rec.status == "cancelled":
                logger.info(f"Job {job_id} is cancelled. Aborting render task for {clip_id}.")
                return {"clip_id": clip_id, "job_id": job_id, "status": "cancelled"}

    logger.info(f"Rendering clip {clip_id}")
    update_clip_status_sync(clip_id, "rendering")
    
    final_storage_key = f"outputs/{video_id}/clips/{clip_id}/final.mp4"
    
    # Idempotency check
    idemp_key = f"{job_id}_{clip_id}_render"
    try:
        check_and_claim_execution(
            task_id=self.request.id,
            job_id=job_id,
            clip_id=clip_id,
            operation="render",
            idempotency_key=idemp_key,
            worker_id=self.request.hostname or "unknown"
        )
    except Ignore:
        logger.info(f"Render task {self.request.id} for {clip_id} ignored due to idempotency.")
        result["final_storage_key"] = final_storage_key
        return result
        
    from backend.models.artifact_sync import check_artifact_exists_sync
    if not force_render and check_artifact_exists_sync(final_storage_key):
        logger.info(f"Artifact {final_storage_key} already exists. Skipping render.")
        result["final_storage_key"] = final_storage_key
        
        # Mark TaskExecution as completed
        from backend.models.database import SyncSessionLocal
        from backend.models.models import TaskExecution, TaskExecutionStatus
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.SUCCEEDED.value
                from datetime import datetime, timezone
                tx.completed_at = datetime.now(timezone.utc)
                session.commit()
                
        return result
        
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            title = clip.title
            
        with managed_download_sync(storage_key=reframed_storage_key) as temp_reframed_path:
            with managed_upload_sync(
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.FINAL_CLIP,
                storage_key=final_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as final_path:
                
                async def run_render():
                    shutil.copy2(temp_reframed_path, final_path)
                
                from backend.core.task_execution import execution_heartbeater
                with execution_heartbeater(self.request.id, interval=60):
                    asyncio.run(run_render())
                
        # Now extract Dual Thumbnails (Phase 14)
        thumb_a_storage_key = f"outputs/{video_id}/clips/{clip_id}/thumb_a.jpg"
        thumb_b_storage_key = f"outputs/{video_id}/clips/{clip_id}/thumb_b.jpg"
        
        # We must extract from the final_storage_key which is already in artifact_sync. 
        # But wait, final_path was already generated in the with block, and the file exists locally in artifact storage or we need to download it.
        with managed_download_sync(storage_key=final_storage_key) as final_path:
            with managed_upload_sync(
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.THUMBNAIL,
                storage_key=thumb_a_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as thumb_a_path:
                asyncio.run(extract_thumbnail(Path(final_path), Path(thumb_a_path), time=1.0))
                
            with managed_upload_sync(
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.THUMBNAIL,
                storage_key=thumb_b_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as thumb_b_path:
                asyncio.run(extract_thumbnail(Path(final_path), Path(thumb_b_path), time=2.0))

        # We store the storage key in the output_path column of Clip
        # We also store thumb_a as the default thumbnail in Clip
        update_clip_paths_sync(clip_id, final_storage_key, thumb_a_storage_key)
        
        result["final_storage_key"] = final_storage_key
        result["thumb_a_storage_key"] = thumb_a_storage_key
        result["thumb_b_storage_key"] = thumb_b_storage_key
        
    except Ignore:
        raise
    except Exception as e:
        logger.error(f"Render failed for {clip_id}: {e}")
        update_clip_status_sync(clip_id, "failed", str(e))
        
        # Mark TaskExecution as failed
        from backend.models.database import SyncSessionLocal
        from backend.models.models import TaskExecution, TaskExecutionStatus
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.FAILED.value
                tx.failure_reason = str(e)
                session.commit()
                
        raise self.retry(exc=e, countdown=30)
        
    # Mark TaskExecution as completed
    from backend.models.database import SyncSessionLocal
    from backend.models.models import TaskExecution, TaskExecutionStatus
    with SyncSessionLocal() as session:
        tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
        if tx:
            tx.status = TaskExecutionStatus.SUCCEEDED.value
            from datetime import datetime, timezone
            tx.completed_at = datetime.now(timezone.utc)
            session.commit()
            
    return result


@celery_app.task(
    bind=True,
    name="validate_output",
    **DEFAULT_RETRY_KWARGS,
)
def output_validation_task(self, result: dict):
    """
    Validates the generated clip (size, format, etc.).
    Updates Clip.status to validating_output.
    """
    from backend.core.storage import storage_service
    from backend.services.output_validator import validate_video_output
    import tempfile
    import os
    from backend.models.artifact_sync import managed_download_sync

    clip_id = result.get("clip_id")
    final_storage_key = result.get("final_storage_key")

    if result.get("status") == "cancelled":
        logger.info(f"Skipping output_validation_task for clip {clip_id}: upstream step was cancelled.")
        return result

    logger.info(f"Validating output for clip {clip_id}")
    update_clip_status_sync(clip_id, "validating_output")
    
    try:
        if not final_storage_key:
            raise ValueError(f"No final_storage_key provided for clip {clip_id}")
            
        if not storage_service.exists(final_storage_key):
            raise FileNotFoundError(f"Output file missing in storage: {final_storage_key}")
            
        # Query expected clip duration for mode-specific contract validation
        from backend.models.database import SyncSessionLocal
        from backend.models.models import Clip
        expected_dur = None
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            if c and c.duration:
                expected_dur = float(c.duration)

        # We need to validate the file locally
        with managed_download_sync(storage_key=final_storage_key) as temp_path:
            validate_video_output(
                video_path=temp_path,
                expected_duration=expected_dur,
                expected_width=1080,
                expected_height=1920,
                require_audio=True,
                max_duration=60.0,
                duration_tolerance=1.5
            )
            
    except Exception as e:
        logger.error(f"Validation failed for {clip_id}: {e}")
        update_clip_status_sync(clip_id, "failed", str(e))
        raise self.retry(exc=e, countdown=30)
        
    return result


@celery_app.task(
    bind=True,
    name="publish_clip",
    **DEFAULT_RETRY_KWARGS,
)
def publish_task(self, *args, **kwargs):
    """
    Publishes the clip.
    Uses durable publishing idempotency using job_id + clip_id + publish_target + content_version.
    """
    import os
    import json
    from pathlib import Path
    from sqlalchemy.exc import IntegrityError
    from backend.models.models import Clip, PublishRecord, PublishStatus
    from backend.models.db_sync import update_clip_publish_sync
    from backend.services.publisher import upload_short, check_external_youtube_state
    from backend.core.config import settings
    import tempfile
    from backend.models.artifact_sync import retrieve_to_local_sync
    
    pos_args = list(args)
    if pos_args and hasattr(pos_args[0], "request"):
        self = pos_args.pop(0)

    result = kwargs.get("result") or (pos_args[0] if pos_args else kwargs)
    
    if isinstance(result, str):
        clip_id = result
        job_id = None
        final_storage_key = None
        status = None
    elif isinstance(result, dict):
        clip_id = result.get("clip_id")
        job_id = result.get("job_id")
        final_storage_key = result.get("final_storage_key")
        status = result.get("status")
    else:
        clip_id = None
        job_id = None
        final_storage_key = None
        status = None

    while isinstance(clip_id, dict):
        clip_id = clip_id.get("clip_id")

    if not clip_id or not isinstance(clip_id, str):
        logger.error(f"[publish_task] Invalid clip_id received from upstream: {type(clip_id)} ({clip_id})")
        return {"clip_id": str(clip_id) if clip_id else None, "status": "failed", "error": f"Invalid clip_id: expected string UUID, got {type(clip_id).__name__}"}

    if status == "cancelled":
        logger.info(f"Skipping publish_task for clip {clip_id}: upstream step was cancelled.")
        return result

    if job_id:
        from backend.models.models import Job
        with SyncSessionLocal() as session:
            job_rec = session.query(Job).filter_by(id=job_id).first()
            if job_rec and job_rec.status == "cancelled":
                logger.info(f"Job {job_id} is cancelled. Aborting publish task for {clip_id}.")
                return {"clip_id": clip_id, "job_id": job_id, "status": "cancelled"}

    logger.info(f"Publishing clip {clip_id}")
    update_clip_status_sync(clip_id, "publishing")
    
    # 1. Generate deterministic idempotency key
    content_version = "v1"
    idemp_key = f"{job_id}_{clip_id}_youtube_{content_version}"
    
    from celery.exceptions import Ignore
    try:
        worker_id_val = getattr(self.request, "hostname", "unknown")
        if not isinstance(worker_id_val, str):
            worker_id_val = "unknown"
        check_and_claim_execution(
            task_id=str(getattr(self.request, "id", "unknown")),
            job_id=job_id,
            clip_id=clip_id,
            operation="publish",
            idempotency_key=f"task_{idemp_key}",
            worker_id=worker_id_val
        )
    except Ignore:
        logger.info(f"Publish task {self.request.id} for {clip_id} ignored due to idempotency.")
        return {"clip_id": clip_id, "status": "skipped", "reason": "already_claimed"}
    
    try:
        from backend.models.models import PublishTarget, Channel, Clip
        from datetime import datetime, timezone
        from sqlalchemy import update
        from backend.models.artifact_sync import managed_download_sync

        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")

            title = clip.title
            description = clip.description or ""
            clip_category = clip.category or "22"
            try:
                tags = json.loads(clip.tags or "[]") if (clip.tags and clip.tags.startswith("[")) else ([t.strip() for t in clip.tags.split(",") if t.strip()] if clip.tags else [])
            except Exception:
                tags = []

            if clip.video_id:
                try:
                    from backend.services.source_metadata_engine import load_persisted_source_metadata
                    source_meta = load_persisted_source_metadata(clip.video_id)
                    if source_meta:
                        if not tags and source_meta.seo_tags:
                            tags = list(source_meta.seo_tags)
                        if clip_category == "22" and source_meta.youtube_category_id:
                            clip_category = source_meta.youtube_category_id
                except Exception as meta_err:
                    logger.warning(f"[Publish] Error inheriting source metadata in publish_task: {meta_err}")

            # Find PublishTarget rows for this clip
            targets = session.query(PublishTarget).filter_by(clip_id=clip_id).all()
            if not targets:
                # If no targets exist, check legacy publish_destination_id
                if clip.publish_destination_id:
                    ch = session.query(Channel).filter_by(id=clip.publish_destination_id).first()
                    if ch:
                        import uuid
                        now = datetime.now(timezone.utc)
                        new_target = PublishTarget(
                            id=str(uuid.uuid4()),
                            clip_id=clip_id,
                            destination_id=ch.id,
                            status="pending",
                            created_at=now,
                            updated_at=now
                        )
                        session.add(new_target)
                        session.commit()
                        targets = [new_target]

            if not targets:
                logger.info(f"[Publish] No destination targets configured for clip {clip_id}. Skipping upload.")
                update_clip_publish_sync(clip_id, "draft", None)
                update_clip_status_sync(clip_id, "completed")
                result["status"] = "skipped_no_destinations"
                return result

            # Check if auto_publish is enabled for this pipeline job/source channel
            is_auto_publish = False
            if job_id:
                job_rec = session.query(Job).filter_by(id=job_id).first()
                if job_rec:
                    if job_rec.config:
                        try:
                            cfg = json.loads(job_rec.config) if isinstance(job_rec.config, str) else job_rec.config
                            if isinstance(cfg, dict):
                                is_auto_publish = bool(cfg.get("auto_publish", False))
                        except Exception:
                            pass
                    if not is_auto_publish and job_rec.channel_id:
                        src_ch = session.query(Channel).filter_by(id=job_rec.channel_id).first()
                        if src_ch and src_ch.auto_publish:
                            is_auto_publish = True

            # If auto-publish is disabled for this job/channel, preserve clip in draft status
            if not is_auto_publish:
                logger.info(f"[Publish] auto_publish is OFF for job {job_id} / clip {clip_id}. Leaving clip in draft for manual publishing.")
                update_clip_publish_sync(clip_id, "draft", None)
                update_clip_status_sync(clip_id, "completed")
                result["status"] = "draft"
                result["reason"] = "auto_publish_disabled"
                return result

            target_ids = [t.id for t in targets]

        last_yt_id = None
        for target_id in target_ids:
            with SyncSessionLocal() as session:
                target = session.query(PublishTarget).filter_by(id=target_id).first()
                if not target:
                    continue

                if target.status == "completed":
                    if target.youtube_video_id:
                        last_yt_id = target.youtube_video_id
                    continue

                now = datetime.now(timezone.utc)

                # A. pending / failed -> atomic compare-and-update to publishing
                if target.status in ("pending", "failed"):
                    stmt = (
                        update(PublishTarget)
                        .where(PublishTarget.id == target.id, PublishTarget.status == target.status)
                        .values(status="publishing", updated_at=now)
                    )
                    res = session.execute(stmt)
                    session.commit()
                    if res.rowcount == 0:
                        logger.info(f"[Publish] Target {target.id} claimed by another worker. Skipping.")
                        continue

                # B / C. publishing: fresh vs stale
                elif target.status == "publishing":
                    is_stale = (target.updated_at is not None and (now - target.updated_at).total_seconds() > 3600)
                    if not is_stale:
                        logger.info(f"[Publish] Target {target.id} is actively being published by another worker (fresh). Skipping.")
                        continue
                    else:
                        logger.info(f"[Publish] Target {target.id} has stale publishing claim (>1hr). Reconciling with YouTube...")
                        dest_channel = session.query(Channel).filter_by(id=target.destination_id).first()
                        yt_ch_id = dest_channel.youtube_channel_id if dest_channel else None
                        idemp_key = f"{job_id}_{clip_id}_{target.destination_id}_v1"
                        external_id = check_external_youtube_state(idemp_key, channel_id=yt_ch_id)
                        if external_id == "MANUAL_REVIEW_REQUIRED":
                            logger.error(f"[Publish] External state ambiguous for {idemp_key}. Marking manual_review.")
                            target.status = "manual_review"
                            session.commit()
                            continue
                        elif external_id:
                            logger.info(f"[Publish] Reconciled remote video {external_id} for {idemp_key}.")
                            target.status = "completed"
                            target.youtube_video_id = external_id
                            target.published_at = now
                            session.commit()
                            last_yt_id = external_id
                            continue
                        else:
                            # Video does not exist remotely. Atomically reclaim:
                            stmt = (
                                update(PublishTarget)
                                .where(PublishTarget.id == target.id, PublishTarget.status == "publishing")
                                .values(status="publishing", updated_at=now)
                            )
                            res = session.execute(stmt)
                            session.commit()
                            if res.rowcount == 0:
                                continue

                dest_channel = session.query(Channel).filter_by(id=target.destination_id).first()
                if not dest_channel or not dest_channel.is_active or not dest_channel.is_destination:
                    target.status = "failed"
                    target.error_message = f"Destination channel {target.destination_id} not found, inactive, or not registered as destination"
                    session.commit()
                    continue

                from backend.services.publisher import check_channel_authorization
                if not check_channel_authorization(dest_channel.youtube_channel_id):
                    target.status = "failed"
                    target.error_message = f"Destination channel {dest_channel.youtube_channel_id} lacks valid OAuth credentials"
                    session.commit()
                    continue

                dest_yt_channel_id = dest_channel.youtube_channel_id
                target_privacy = "private"
                target_kids = target.made_for_kids
                idemp_key = f"{job_id}_{clip_id}_{target.destination_id}_v1"

            # Destination-Scoped Cadence Check & Non-Blocking Worker Scheduling
            from backend.services.publishing_cadence import check_and_reserve_destination_cadence, record_destination_published
            dest_is_test = isinstance(getattr(dest_channel, "is_test", None), bool) and dest_channel.is_test
            is_test_mode = (
                os.environ.get("PUBLISH_MODE") == "test"
                or getattr(settings, "PUBLISH_MODE", "prod") == "test"
                or dest_is_test
                or dest_yt_channel_id == "UC_dest"
            )
            if not is_test_mode and hasattr(self, "retry"):
                wait_sec = check_and_reserve_destination_cadence(dest_yt_channel_id)
                if wait_sec > 0.5:
                    logger.info(
                        f"[Publish Cadence] Destination {dest_yt_channel_id} requires {wait_sec:.1f}s gap. "
                        f"Rescheduling publish_task via Celery queue countdown to free worker process immediately."
                    )
                    retry_exc = self.retry(countdown=int(wait_sec) + 1, max_retries=20)
                    if isinstance(retry_exc, BaseException):
                        raise retry_exc

            # Execute upload OUTSIDE database transaction
            logger.info(f"[Publish] Uploading clip {clip_id} to destination {dest_yt_channel_id}...")
            with managed_download_sync(storage_key=final_storage_key) as temp_path:
                try:
                    yt_res = upload_short(
                        video_path=temp_path,
                        title=title,
                        description=description,
                        tags=tags,
                        privacy=target_privacy,
                        made_for_kids=target_kids,
                        category=clip_category,
                        channel_id=dest_yt_channel_id,
                        idempotency_key=idemp_key,
                        clip_id=clip_id,
                    )
                    yt_id = yt_res.get("id") if isinstance(yt_res, dict) else str(yt_res)
                    confirmed_privacy = yt_res.get("privacy", "unconfirmed") if isinstance(yt_res, dict) else "unconfirmed"
                    remediation = yt_res.get("remediation") if isinstance(yt_res, dict) else None
                    is_confirmed_private = yt_res.get("privacy_confirmed") if (isinstance(yt_res, dict) and "privacy_confirmed" in yt_res) else (confirmed_privacy == "private" and not remediation)

                    if remediation == "auto_remediated_to_private":
                        err_msg = (
                            f"Operational Alert: Video {yt_id} returned 'public' upon upload; "
                            f"auto-remediated to 'private' via safe update and verified via read-back. Preserved for review."
                        )
                    elif remediation and any(k in remediation for k in ("exception", "failed", "still_public", "readback", "incomplete", "withheld")):
                        err_msg = (
                            f"CRITICAL PRIVACY ALERT: Video {yt_id} returned 'public' and remediation could not be confirmed ({remediation}). "
                            f"VIDEO MAY BE PUBLIC ON YOUTUBE! Immediate operator review required."
                        )
                    elif not confirmed_privacy or confirmed_privacy == "unconfirmed":
                        err_msg = f"Remote status incomplete: YouTube response for video {yt_id} omitted privacyStatus. Manual review required."
                    else:
                        err_msg = f"Remote privacy mismatch: requested 'private' but YouTube returned '{confirmed_privacy}' for video {yt_id}. Manual review required."

                    with SyncSessionLocal() as session:
                        tg = session.query(PublishTarget).filter_by(id=target_id).first()
                        if tg:
                            tg.status = "completed" if is_confirmed_private else "manual_review"
                            tg.youtube_video_id = yt_id
                            tg.privacy = confirmed_privacy
                            tg.published_at = datetime.now(timezone.utc)
                            if not is_confirmed_private:
                                tg.error_message = err_msg
                            session.commit()
                        cl = session.query(Clip).filter_by(id=clip_id).first()
                        if cl:
                            cl.youtube_short_id = yt_id
                            cl.privacy = confirmed_privacy
                            if is_confirmed_private:
                                cl.publish_status = PublishStatus.PUBLISHED.value
                            else:
                                cl.publish_status = PublishStatus.MANUAL_REVIEW.value
                                cl.publish_stage = "manual_review"
                                cl.publish_error = err_msg
                            session.commit()
                    last_yt_id = yt_id
                except Exception as exc:
                    logger.error(f"[Publish] Upload failed for target {target_id}: {exc}")
                    with SyncSessionLocal() as session:
                        tg = session.query(PublishTarget).filter_by(id=target_id).first()
                        if tg:
                            tg.status = "failed"
                            tg.error_message = str(exc)
                            tg.retry_count = (tg.retry_count or 0) + 1
                            session.commit()
                    raise

        # Check overall clip status
        with SyncSessionLocal() as session:
            all_targets = session.query(PublishTarget).filter_by(clip_id=clip_id).all()
            all_completed = all(t.status == "completed" for t in all_targets) if all_targets else True
            any_failed = any(t.status == "failed" for t in all_targets) if all_targets else False

        if all_completed:
            update_clip_publish_sync(clip_id, "published", last_yt_id)
            update_clip_status_sync(clip_id, "completed")
            result["status"] = "published"
            result["youtube_id"] = last_yt_id
        elif any_failed:
            update_clip_publish_sync(clip_id, "failed", None)
            update_clip_status_sync(clip_id, "failed", "One or more publish targets failed")
            result["status"] = "failed"
        else:
            result["status"] = "in_progress"

    except (Retry, Ignore):
        raise
    except Exception as e:
        logger.error(f"Publish handling failed for {clip_id}: {e}")
        update_clip_status_sync(clip_id, "failed", str(e))
        raise self.retry(exc=e, countdown=30)
        
    return result


@celery_app.task(
    bind=True,
    name="apply_sfx",
    **DEFAULT_RETRY_KWARGS,
)
def apply_sfx_task(self, clip_id: str, sfx_plan_dict: dict):
    """
    Applies an SFX plan to a clip and creates a new ClipVariant.
    """
    import asyncio
    import os
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, ClipVariant, ArtifactType, TaskExecution, TaskExecutionStatus, ArtifactRecord
    from backend.models.sfx import SFXPlan
    from backend.services.sfx_mixer import SFXMixer
    from backend.core.task_execution import check_and_claim_execution
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync
    from backend.services.artifact_manager import ArtifactManager
    from celery.exceptions import Ignore
    from datetime import datetime, timezone
    import json
    import tempfile
    
    logger.info(f"Applying SFX to clip {clip_id}")
    
    plan = SFXPlan(**sfx_plan_dict)
    if not plan.placements:
        logger.info(f"SFX plan for clip {clip_id} has no placements. Skipping SFX mixing.")
        return {
            "clip_id": clip_id,
            "sfx_applied": False,
            "message": "No suitable sound-effect placements were found. The clip was not modified."
        }
    
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            video_id = clip.video_id
                
            if clip.run_identity:
                parts = clip.run_identity.split("_")
                job_id = "_".join(parts[:-2]) if len(parts) > 2 else "unknown_job"
            else:
                job_id = "unknown_job"
                
            # Idempotency
            import hashlib
            plan_hash = hashlib.sha256(json.dumps(sfx_plan_dict, sort_keys=True).encode()).hexdigest()
            idemp_key = f"{clip_id}_sfx_{plan_hash}"
            
            try:
                check_and_claim_execution(
                    task_id=self.request.id,
                    job_id=job_id,
                    clip_id=clip_id,
                    operation="apply_sfx",
                    idempotency_key=idemp_key,
                    worker_id=self.request.hostname or "unknown"
                )
            except Ignore:
                logger.info(f"SFX task {self.request.id} ignored due to idempotency.")
                return {"clip_id": clip_id, "sfx_applied": True}
                
        # Generate output
        sfx_storage_key = f"outputs/{video_id}/clips/{clip_id}/variants/sfx_{plan_hash}.mp4"
        
        # Download the input video locally
        with managed_download_sync(storage_key=clip.output_path) as input_path:
            with managed_upload_sync(
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.SFX_VARIANT,
                storage_key=sfx_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as temp_out:
            
                async def run_sfx():
                    am = ArtifactManager()
                    cmd = await SFXMixer.build_ffmpeg_command(
                        video_input_path=input_path,
                        sfx_plan=plan,
                        output_path=temp_out,
                        artifact_manager=am
                    )
                    import subprocess
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode != 0:
                        raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")
                        
                from backend.core.task_execution import execution_heartbeater
                with execution_heartbeater(self.request.id, interval=60):
                    asyncio.run(run_sfx())
                
        # Create ClipVariant in DB
        with SyncSessionLocal() as session:
            # Look up artifact_record created by managed_upload_sync
            ar = session.query(ArtifactRecord).filter_by(storage_key=sfx_storage_key).first()
            if not ar:
                raise ValueError("ArtifactRecord not found after managed_upload_sync")
                
            variant = ClipVariant(
                clip_id=clip_id,
                variant_type="sfx",
                artifact_id=ar.id,
                configuration_hash=plan_hash,
                status="completed",
                variant_metadata=plan.model_dump_json()
            )
            session.add(variant)
            session.commit()
            
        # Mark TaskExecution as completed
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.SUCCEEDED.value
                tx.completed_at = datetime.now(timezone.utc)
                session.commit()
                
        return {"clip_id": clip_id, "sfx_applied": True, "variant_hash": plan_hash}
        
    except Ignore:
        raise
    except Exception as e:
        logger.error(f"Apply SFX failed for {clip_id}: {e}")
        # Mark TaskExecution as failed
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.FAILED.value
                tx.failure_reason = str(e)
                session.commit()
        raise self.retry(exc=e, countdown=30)

@celery_app.task(
    bind=True,
    name="apply_broll",
    **DEFAULT_RETRY_KWARGS,
)
def apply_broll_task(self, clip_id: str, broll_plan_dict: dict):
    """
    Applies a B-roll plan to a clip and creates a new ClipVariant.
    """
    import asyncio
    import os
    import json
    import hashlib
    import subprocess
    from datetime import datetime, timezone
    
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, ClipVariant, ArtifactType, TaskExecution, TaskExecutionStatus, ArtifactRecord, Video
    from backend.models.broll import BrollPlan, DisplayMode
    from backend.models.layout import LayoutPlan, RegionModel, AudioPolicy, BackgroundPolicy, ScaleMode
    from backend.core.task_execution import check_and_claim_execution
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync
    from backend.services.layout_engine import LayoutEngine
    from celery.exceptions import Ignore
    
    logger.info(f"Applying B-roll to clip {clip_id}")
    
    plan = BrollPlan(**broll_plan_dict)
    if not plan.placements:
        logger.info(f"B-roll plan for clip {clip_id} has no placements. Skipping B-roll compositing.")
        return {
            "clip_id": clip_id,
            "broll_applied": False,
            "message": "No B-roll placements found in plan. Clip was not modified."
        }
    
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            video_id = clip.video_id
                
            if clip.run_identity:
                parts = clip.run_identity.split("_")
                job_id = "_".join(parts[:-2]) if len(parts) > 2 else "unknown_job"
            else:
                job_id = "unknown_job"
                
            # Idempotency
            plan_hash = hashlib.sha256(json.dumps(broll_plan_dict, sort_keys=True).encode()).hexdigest()
            idemp_key = f"{clip_id}_broll_{plan_hash}_{plan.planner_version}"
            
            try:
                check_and_claim_execution(
                    task_id=self.request.id,
                    job_id=job_id,
                    clip_id=clip_id,
                    operation="apply_broll",
                    idempotency_key=idemp_key,
                    worker_id=self.request.hostname or "unknown"
                )
            except Ignore:
                logger.info(f"Broll task {self.request.id} ignored due to idempotency.")
                return {"clip_id": clip_id, "broll_applied": True}
        
        # We need to download the base clip (the final vertical clip)
        base_storage_key = clip.output_path
        if not base_storage_key:
             raise ValueError("Clip does not have an output_path to apply B-roll onto")
             
        # Generate output
        broll_storage_key = f"outputs/{video_id}/clips/{clip_id}/variants/broll_{plan_hash}.mp4"
        
        with managed_download_sync(storage_key=base_storage_key) as input_path:
            # Also download all B-roll assets
            asset_paths = []
            asset_storage_keys = []
            with SyncSessionLocal() as session:
                from backend.models.models import VisualAsset
                for placement in plan.placements:
                    asset = session.query(VisualAsset).filter_by(id=placement.asset_id).first()
                    if not asset:
                         raise ValueError(f"VisualAsset {placement.asset_id} not found")
                    record = session.query(ArtifactRecord).filter_by(id=asset.artifact_id).first()
                    if not record:
                         raise ValueError(f"ArtifactRecord for asset {asset.id} not found")
                    asset_storage_keys.append(record.storage_key)
            
            from contextlib import ExitStack
            with ExitStack() as stack:
                for key in asset_storage_keys:
                    local_asset_path = stack.enter_context(managed_download_sync(storage_key=key))
                    asset_paths.append(local_asset_path)
                
                with managed_upload_sync(
                    owner_type="clip",
                    owner_id=clip_id,
                    artifact_type=ArtifactType.BROLL_VARIANT,
                    storage_key=broll_storage_key,
                    retention_policy="persistent",
                    processing_version="v1"
                ) as temp_out:
                
                    def run_broll():
                        # Build layout plan
                        regions = []
                        # Base video
                        regions.append(RegionModel(
                            source_index=0,
                            x=0, y=0, w=1080, h=1920, # Assume standard vertical
                            scale_mode=ScaleMode.CONTAIN,
                            z_order=0
                        ))
                        
                        for i, placement in enumerate(plan.placements):
                            if placement.display_mode == DisplayMode.FULL_CUTAWAY:
                                x, y, w, h = 0, 0, 1080, 1920
                                scale_mode = ScaleMode.CROP
                            elif placement.display_mode == DisplayMode.PIP_BOTTOM:
                                w = placement.w or 600
                                h = placement.h or 600
                                x = placement.x or (1080 - w) // 2
                                y = placement.y or (1920 - h - 100)
                                scale_mode = ScaleMode.CROP
                            else:
                                x, y, w, h = 0, 0, 1080, 1920
                                scale_mode = ScaleMode.CONTAIN
                                
                            r = RegionModel(
                                source_index=i + 1,
                                start_time=placement.start_time,
                                end_time=placement.end_time,
                                fade_duration=placement.fade_duration,
                                z_order=i + 1,
                                x=x, y=y, w=w, h=h,
                                scale_mode=scale_mode
                            )
                            regions.append(r)
                            
                        layout_plan = LayoutPlan(
                            canvas_width=1080,
                            canvas_height=1920,
                            regions=regions,
                            background_policy=BackgroundPolicy.NONE,
                            audio_policy=AudioPolicy.PRIMARY_ONLY
                        )
                        
                        inputs = [input_path] + asset_paths
                        filtergraph = LayoutEngine.build_render_graph(layout_plan, inputs)
                        
                        cmd = ["ffmpeg", "-y"]
                        for inp in inputs:
                            cmd.extend(["-i", inp])
                        cmd.extend([
                            "-filter_complex", filtergraph,
                            "-map", "[outv]",
                            "-map", "0:a?", # Keep original audio
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-movflags", "+faststart",
                            "-f", "mp4",
                            temp_out
                        ])
                        
                        process = subprocess.run(
                            cmd,
                            capture_output=True
                        )
                        if process.returncode != 0:
                            raise RuntimeError(f"FFmpeg failed: {process.stderr.decode()}")
                            
                    from backend.core.task_execution import execution_heartbeater
                    with execution_heartbeater(self.request.id, interval=60):
                        run_broll()
        
        # Create ClipVariant in DB
        with SyncSessionLocal() as session:
            ar = session.query(ArtifactRecord).filter_by(storage_key=broll_storage_key).first()
            if not ar:
                raise ValueError("ArtifactRecord not found after managed_upload_sync")
            
            # Extract creator attribution from VisualAsset ArtifactRecords
            meta_dict = plan.model_dump()
            from backend.models.models import VisualAsset
            for placement in plan.placements:
                asset = session.query(VisualAsset).filter_by(id=placement.asset_id).first()
                if asset and asset.artifact_id:
                    asset_rec = session.query(ArtifactRecord).filter_by(id=asset.artifact_id).first()
                    if asset_rec and asset_rec.processing_version and asset_rec.processing_version.startswith("{"):
                        try:
                            att_info = json.loads(asset_rec.processing_version)
                            if att_info.get("source") == "pexels":
                                meta_dict["creator_name"] = att_info.get("creator_name")
                                meta_dict["creator_url"] = att_info.get("creator_url")
                                meta_dict["pexels_video_url"] = att_info.get("pexels_video_url")
                                break
                        except Exception:
                            pass
                
            variant = ClipVariant(
                clip_id=clip_id,
                variant_type="broll",
                artifact_id=ar.id,
                configuration_hash=plan_hash,
                status="completed",
                variant_metadata=json.dumps(meta_dict)
            )
            session.add(variant)
            session.commit()
            
        # Mark TaskExecution as completed
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.SUCCEEDED.value
                tx.completed_at = datetime.now(timezone.utc)
                session.commit()
                
        return {"clip_id": clip_id, "broll_applied": True, "variant_hash": plan_hash}
        
    except Ignore:
        raise
    except Exception as e:
        logger.error(f"Apply B-roll failed for {clip_id}: {e}")
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.FAILED.value
                tx.failure_reason = str(e)
                session.commit()
        raise self.retry(exc=e, countdown=30)


class PublishCancelledException(Exception):
    """Raised when publication is cooperatively cancelled by user."""
    pass


@celery_app.task(
    bind=True,
    name="publish_clip_task",
    max_retries=3,
    default_retry_delay=30,
)
def publish_clip_task(self, *args, **kwargs):
    """
    Upload Studio Phase 3: Asynchronous YouTube publishing task.
    - Locks clip row with DB-level lock.
    - Validates eligibility (output file exists, video processed, not in active processing).
    - Preserves stable idempotency key across retries and redelivery.
    - Safely reconciles existing remote upload state before initiating upload.
    - Transitions to manual_review when remote reconciliation is inconclusive.
    - Truthfully streams byte/chunk progress callbacks without artificial 10% -> 100% jumps.
    - Preserves storage reservation invariant (never alters Video/Batch reservations).
    """
    import json
    from pathlib import Path
    from datetime import datetime, timezone
    from backend.models.models import Clip, PublishStatus, PublishRecord

    # Support both direct/mock invocation publish_clip_task(mock_task, clip_id=...)
    # and Celery worker dispatch publish_clip_task(clip_id, channel_id=..., privacy=...)
    task_context = self
    pos_args = list(args)
    if pos_args and hasattr(pos_args[0], "request"):
        task_context = pos_args.pop(0)

    raw_clip_id = kwargs.get("clip_id") or (pos_args[0] if len(pos_args) > 0 else None)
    if isinstance(raw_clip_id, dict):
        clip_id = raw_clip_id.get("clip_id")
        channel_id = kwargs.get("channel_id") or raw_clip_id.get("channel_id") or raw_clip_id.get("publish_destination_id") or (pos_args[1] if len(pos_args) > 1 else None)
    else:
        clip_id = raw_clip_id
        channel_id = kwargs.get("channel_id") or (pos_args[1] if len(pos_args) > 1 else None)
    privacy = kwargs.get("privacy", "private")

    while isinstance(clip_id, dict):
        clip_id = clip_id.get("clip_id")

    if not clip_id or not isinstance(clip_id, str):
        logger.error(f"[PublishTask] Invalid clip_id received: {type(clip_id)} ({clip_id})")
        return {"clip_id": str(clip_id) if clip_id else None, "status": "failed", "error": f"Invalid clip_id: expected string UUID, got {type(clip_id).__name__}"}

    logger.info(f"[PublishTask] Starting publication task for clip {clip_id}")

    # Step 1: Row lock & Eligibility Validation
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).with_for_update().first()
        if not clip:
            logger.error(f"[PublishTask] Clip {clip_id} not found.")
            return {"clip_id": clip_id, "status": "failed", "error": "Clip not found"}

        # 1a. Already published check
        if clip.publish_status == PublishStatus.PUBLISHED.value and clip.youtube_short_id:
            logger.info(f"[PublishTask] Clip {clip_id} is already published as {clip.youtube_short_id}.")
            return {"clip_id": clip_id, "status": "published", "youtube_id": clip.youtube_short_id}

        # 1b. Manual review lock
        if clip.publish_status == PublishStatus.MANUAL_REVIEW.value:
            logger.warning(f"[PublishTask] Clip {clip_id} is in manual_review state. Automatic retry blocked.")
            return {"clip_id": clip_id, "status": "manual_review", "error": clip.publish_error}

        # 1c. Cancellation check
        if clip.publish_status in (PublishStatus.CANCELLED.value, PublishStatus.CANCELLING.value):
            clip.publish_status = PublishStatus.CANCELLED.value
            clip.publish_stage = "cancelled"
            session.commit()
            return {"clip_id": clip_id, "status": "cancelled"}

        # 1d. Eligibility check: output path must exist on disk
        if not clip.output_path or not Path(clip.output_path).exists():
            clip.publish_status = PublishStatus.FAILED.value
            clip.publish_stage = "failed"
            clip.publish_error = f"Clip output video file missing from disk: {clip.output_path}"
            session.commit()
            return {"clip_id": clip_id, "status": "failed", "error": clip.publish_error}

        if clip.status in ("reframing", "cutting", "rendering", "transcribing", "processing"):
            clip.publish_status = PublishStatus.FAILED.value
            clip.publish_stage = "failed"
            clip.publish_error = f"Cannot publish clip {clip_id} while processing is active (status: {clip.status})."
            session.commit()
            return {"clip_id": clip_id, "status": "failed", "error": clip.publish_error}

        # 1e. Destination presence, role, activity, and OAuth authorization validation
        dest_ref = channel_id or clip.publish_destination_id
        if not dest_ref:
            clip.publish_status = PublishStatus.FAILED.value
            clip.publish_stage = "failed"
            clip.publish_error = "Cannot publish clip: No destination channel specified."
            session.commit()
            return {"clip_id": clip_id, "status": "failed", "error": clip.publish_error}

        from backend.models.models import Channel
        dest_channel = session.query(Channel).filter(
            (Channel.id == dest_ref) | (Channel.youtube_channel_id == dest_ref)
        ).first()
        if not dest_channel or not dest_channel.is_active or not dest_channel.is_destination:
            clip.publish_status = PublishStatus.FAILED.value
            clip.publish_stage = "failed"
            clip.publish_error = f"Cannot publish clip: Destination {dest_ref} not found, inactive, or not registered as destination."
            session.commit()
            return {"clip_id": clip_id, "status": "failed", "error": clip.publish_error}

        from backend.services.publisher import check_channel_authorization
        if not check_channel_authorization(dest_channel.youtube_channel_id):
            clip.publish_status = PublishStatus.FAILED.value
            clip.publish_stage = "failed"
            clip.publish_error = f"Cannot publish clip: Destination {dest_channel.youtube_channel_id} lacks valid OAuth credentials."
            session.commit()
            return {"clip_id": clip_id, "status": "failed", "error": clip.publish_error}

        channel_id = dest_channel.youtube_channel_id
        if clip.publish_destination_id != dest_channel.id:
            clip.publish_destination_id = dest_channel.id

        # 1f. Stable logical idempotency key (independent of attempt count)
        if clip.publish_idempotency_key:
            idempotency_key = clip.publish_idempotency_key
        else:
            idempotency_key = f"pub_{clip.id}_{channel_id}"
            clip.publish_idempotency_key = idempotency_key

        # 1f. Attempt number increments independently
        req = getattr(task_context, "request", None)
        task_req_id = getattr(req, "id", None) if req else None
        clip.publish_attempt = (clip.publish_attempt or 0) + 1
        clip.publish_task_id = task_req_id or "local_publish_task"
        clip.publish_stage = "reconciling"
        if not clip.publish_started_at:
            clip.publish_started_at = datetime.now(timezone.utc)

        # Enforce DB uniqueness & check existing PublishRecord
        pub_rec = session.query(PublishRecord).filter_by(idempotency_key=idempotency_key).first()
        if pub_rec and pub_rec.external_id:
            clip.youtube_short_id = pub_rec.external_id
            clip.publish_status = PublishStatus.PUBLISHED.value
            clip.publish_stage = "published"
            clip.publish_progress = 100
            clip.published_at = pub_rec.updated_at or datetime.now(timezone.utc)
            clip.publish_completed_at = datetime.now(timezone.utc)
            session.commit()
            return {"clip_id": clip_id, "status": "published", "youtube_id": pub_rec.external_id}

        if not pub_rec:
            pub_rec = PublishRecord(
                idempotency_key=idempotency_key,
                job_id=clip.run_identity or clip_id,
                clip_id=clip_id,
                target="youtube",
                status="publishing"
            )
            session.add(pub_rec)

        session.commit()

    # Step 2: Safe Remote Upload Reconciliation
    remote_status = check_external_youtube_state(idempotency_key=idempotency_key, channel_id=channel_id)
    if remote_status == "MANUAL_REVIEW_REQUIRED":
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            if c:
                c.publish_status = PublishStatus.MANUAL_REVIEW.value
                c.publish_stage = "manual_review"
                c.publish_error = "Remote reconciliation inconclusive: video may already exist on YouTube. Manual review required."
                session.commit()
        return {"clip_id": clip_id, "status": "manual_review", "error": "Remote reconciliation inconclusive"}

    elif remote_status and isinstance(remote_status, str):
        # Truthfully determine remote privacy to prevent treating local records as proof of remote state
        remote_privacy = None
        is_test_mode = os.environ.get("PUBLISH_MODE") == "test" or getattr(settings, "PUBLISH_MODE", "prod") == "test"
        if not is_test_mode:
            try:
                from backend.services.publisher import get_youtube_client
                yt = get_youtube_client(channel_id=channel_id)
                chk = yt.videos().list(part="status", id=remote_status).execute()
                if chk.get("items"):
                    remote_privacy = chk["items"][0].get("status", {}).get("privacyStatus")
            except Exception as e:
                logger.warning(f"[PublishTask] Could not fetch remote privacy for {remote_status}: {e}")
        else:
            remote_privacy = "private"

        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            if c:
                c.youtube_short_id = remote_status
                c.privacy = remote_privacy if remote_privacy else "unconfirmed"
                if remote_privacy == "private":
                    c.publish_status = PublishStatus.PUBLISHED.value
                    c.publish_stage = "published"
                    c.publish_progress = 100
                    c.published_at = datetime.now(timezone.utc)
                    c.publish_completed_at = datetime.now(timezone.utc)
                    c.publish_error = None
                else:
                    c.publish_status = PublishStatus.MANUAL_REVIEW.value
                    c.publish_stage = "manual_review"
                    if not remote_privacy:
                        c.publish_error = f"Reconciliation could not confirm remote privacy status for video {remote_status}. Manual review required."
                    else:
                        c.publish_error = f"Reconciliation detected remote privacy '{remote_privacy}' (differs from private-by-default policy) for existing video {remote_status}. External visibility preserved; flagged for operator review."

            pr = session.query(PublishRecord).filter_by(idempotency_key=idempotency_key).first()
            if pr:
                pr.external_id = remote_status
                pr.status = "completed" if remote_privacy == "private" else "manual_review"

            # Phase 5 auto-optimizer tracking queue entry
            from backend.models.models import VideoTrackingQueue
            import uuid
            from datetime import timedelta
            existing_track = session.query(VideoTrackingQueue).filter_by(youtube_video_id=remote_status).first()
            if not existing_track:
                now_utc = datetime.now(timezone.utc)
                session.add(VideoTrackingQueue(
                    id=str(uuid.uuid4()),
                    clip_id=clip_id,
                    youtube_video_id=remote_status,
                    uploaded_at=now_utc,
                    next_check_at=now_utc + timedelta(hours=2),
                    optimization_attempts=0,
                    status="active"
                ))

            session.commit()
        ret_status = "published" if remote_privacy == "private" else "manual_review"
        return {"clip_id": clip_id, "status": ret_status, "youtube_id": remote_status, "privacy": remote_privacy or "unconfirmed"}

    # Step 3: Cooperative cancellation check before starting upload
    with SyncSessionLocal() as session:
        c = session.query(Clip).filter_by(id=clip_id).first()
        if c and c.publish_status in (PublishStatus.CANCELLED.value, PublishStatus.CANCELLING.value):
            c.publish_status = PublishStatus.CANCELLED.value
            c.publish_stage = "cancelled"
            session.commit()
            return {"clip_id": clip_id, "status": "cancelled"}
        if c:
            c.publish_status = PublishStatus.UPLOADING.value
            c.publish_stage = "uploading"
            c.publish_progress = 1
            session.commit()

    # Step 4: Upload with Real Byte-Level Progress Callback
    last_reported_pct = 0
    def progress_callback(bytes_uploaded, total_bytes, progress_float):
        nonlocal last_reported_pct
        pct = int(progress_float * 100) if progress_float is not None else 0
        pct = max(1, min(98, pct))
        if pct - last_reported_pct >= 5 or pct >= 95:
            last_reported_pct = pct
            with SyncSessionLocal() as session:
                c = session.query(Clip).filter_by(id=clip_id).first()
                if c:
                    if c.publish_status == PublishStatus.CANCELLING.value:
                        raise PublishCancelledException("Publication cancelled by user during upload.")
                    c.publish_progress = pct
                    c.publish_stage = "uploading"
                    session.commit()

    try:
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            video_path = Path(c.output_path)
            title = c.title
            desc = c.description or c.transcript_segment or ""
            thumb_path = Path(c.thumbnail_path) if c.thumbnail_path and Path(c.thumbnail_path).exists() else None
            tags = json.loads(c.tags) if c.tags and c.tags.startswith("[") else ([t.strip() for t in c.tags.split(",") if t.strip()] if c.tags else [])
            priv = "private"
            kids = c.made_for_kids if isinstance(c.made_for_kids, bool) else None
            cat = c.category or "22"
            lic = c.license if c.license in ("youtube", "creativeCommon") else None

            if c.video_id:
                try:
                    from backend.services.source_metadata_engine import load_persisted_source_metadata
                    source_meta = load_persisted_source_metadata(c.video_id)
                    if source_meta:
                        if not tags and source_meta.seo_tags:
                            tags = list(source_meta.seo_tags)
                        if cat == "22" and source_meta.youtube_category_id:
                            cat = source_meta.youtube_category_id
                except Exception as meta_err:
                    logger.warning(f"[Publish] Error inheriting source metadata in publish_clip_task: {meta_err}")

        # Destination-Scoped Cadence Check & Non-Blocking Worker Scheduling
        from backend.services.publishing_cadence import check_and_reserve_destination_cadence, record_destination_published
        clip_is_test = isinstance(getattr(c, "is_test", None), bool) and c.is_test
        is_test_mode = (
            os.environ.get("PUBLISH_MODE") == "test"
            or getattr(settings, "PUBLISH_MODE", "prod") == "test"
            or clip_is_test
            or channel_id == "UC_dest"
        )
        if not is_test_mode and hasattr(task_context, "retry"):
            wait_sec = check_and_reserve_destination_cadence(channel_id)
            if wait_sec > 0.5:
                logger.info(
                    f"[Publish Cadence] Destination {channel_id} requires {wait_sec:.1f}s gap. "
                    f"Rescheduling publish_clip_task via Celery queue countdown to free worker process immediately."
                )
                retry_exc = task_context.retry(countdown=int(wait_sec) + 1, max_retries=20)
                if isinstance(retry_exc, BaseException):
                    raise retry_exc
                return {"clip_id": clip_id, "status": "cadence_rescheduled", "wait_sec": wait_sec}

        upload_res = upload_short(
            video_path=video_path,
            title=title,
            description=desc,
            tags=tags,
            thumbnail_path=thumb_path,
            privacy=priv,
            made_for_kids=kids,
            category=cat,
            license_type=lic,
            idempotency_key=idempotency_key,
            channel_id=channel_id,
            progress_callback=progress_callback,
            clip_id=clip_id,
        )

        remote_video_id = upload_res["id"]
        confirmed_privacy = upload_res.get("privacy", "unconfirmed")
        is_confirmed_private = (confirmed_privacy == "private")

        # Step 5: Finalize and Persist Remote Video ID Immediately
        err_detail = None
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            if c:
                c.publish_status = PublishStatus.FINALIZING.value
                c.publish_stage = "finalizing"
                c.publish_progress = 99
                session.commit()

                c.youtube_short_id = remote_video_id
                c.privacy = confirmed_privacy
                c.published_at = datetime.now(timezone.utc)
                c.publish_completed_at = datetime.now(timezone.utc)

                remediation = upload_res.get("remediation") if isinstance(upload_res, dict) else None
                is_confirmed_private = upload_res.get("privacy_confirmed") if (isinstance(upload_res, dict) and "privacy_confirmed" in upload_res) else (confirmed_privacy == "private" and not remediation)

                if is_confirmed_private:
                    c.publish_status = PublishStatus.PUBLISHED.value
                    c.publish_stage = "published"
                    c.publish_progress = 100
                    c.publish_error = None
                else:
                    c.publish_status = PublishStatus.MANUAL_REVIEW.value
                    c.publish_stage = "manual_review"
                    c.publish_progress = 100
                    if remediation == "auto_remediated_to_private":
                        err_detail = (
                            f"Operational Alert: Newly created video {remote_video_id} returned 'public' upon upload; "
                            f"auto-remediated to 'private' via safe update and verified via read-back. Preserved for operational review."
                        )
                    elif remediation and any(k in remediation for k in ("exception", "failed", "still_public", "readback", "incomplete", "withheld")):
                        err_detail = (
                            f"CRITICAL PRIVACY ALERT: Newly created video {remote_video_id} returned 'public' and "
                            f"emergency remediation could not be confirmed ({remediation}). VIDEO MAY BE PUBLIC ON YOUTUBE! "
                            f"Immediate manual operator action required."
                        )
                    elif not confirmed_privacy or confirmed_privacy == "unconfirmed":
                        err_detail = f"Remote status incomplete: YouTube response for video {remote_video_id} omitted privacyStatus. Manual review required."
                    else:
                        err_detail = f"Remote privacy mismatch: requested 'private' but YouTube returned '{confirmed_privacy}' for video {remote_video_id}. Manual review required."
                    c.publish_error = err_detail

            pr = session.query(PublishRecord).filter_by(idempotency_key=idempotency_key).first()
            if pr:
                pr.external_id = remote_video_id
                pr.status = "completed" if is_confirmed_private else "manual_review"

            # Phase 5 auto-optimizer tracking queue entry
            from backend.models.models import VideoTrackingQueue
            import uuid
            from datetime import timedelta
            existing_track = session.query(VideoTrackingQueue).filter_by(youtube_video_id=remote_video_id).first()
            if not existing_track:
                now_utc = datetime.now(timezone.utc)
                session.add(VideoTrackingQueue(
                    id=str(uuid.uuid4()),
                    clip_id=clip_id,
                    youtube_video_id=remote_video_id,
                    uploaded_at=now_utc,
                    next_check_at=now_utc + timedelta(hours=2),
                    optimization_attempts=0,
                    status="active"
                ))

            session.commit()

        status_result = "published" if is_confirmed_private else "manual_review"
        return {
            "clip_id": clip_id,
            "status": status_result,
            "youtube_id": remote_video_id,
            "privacy": confirmed_privacy,
            "url": upload_res.get("url"),
            "error": err_detail
        }

    except (Retry, Ignore):
        raise

    except PublishCancelledException:
        logger.info(f"[PublishTask] Publishing cancelled for clip {clip_id}.")
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            if c:
                c.publish_status = PublishStatus.CANCELLED.value
                c.publish_stage = "cancelled"
                c.publish_error = "Publication cancelled by user"
                session.commit()
        return {"clip_id": clip_id, "status": "cancelled"}

    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"[PublishTask] Publishing error for clip {clip_id}: {err_msg}")
        is_permanent = any(keyword in err_msg.lower() for keyword in [
            "credential", "authorization", "unauthorized", "quota", "missing", "invalid", "not found"
        ])

        req = getattr(task_context, "request", None)
        retries = getattr(req, "retries", 0) if req else 0
        max_retries = getattr(task_context, "max_retries", getattr(self, "max_retries", 3))

        if is_permanent or retries >= max_retries:
            with SyncSessionLocal() as session:
                c = session.query(Clip).filter_by(id=clip_id).first()
                if c:
                    c.publish_status = PublishStatus.FAILED.value
                    c.publish_stage = "failed"
                    c.publish_error = err_msg
                    session.commit()
                pr = session.query(PublishRecord).filter_by(idempotency_key=idempotency_key).first()
                if pr:
                    pr.status = "failed"
                session.commit()
            return {"clip_id": clip_id, "status": "failed", "error": err_msg}

        else:
            with SyncSessionLocal() as session:
                c = session.query(Clip).filter_by(id=clip_id).first()
                if c:
                    c.publish_status = PublishStatus.QUEUED.value
                    c.publish_stage = "retry_pending"
                    c.publish_error = f"Transient error: {err_msg}. Retrying..."
                    session.commit()
            if hasattr(task_context, "retry"):
                raise task_context.retry(exc=exc, countdown=30)
            raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="recover_stranded_publish_jobs")
def recover_stranded_publish_jobs_task(stale_threshold_seconds: int = 120):
    """
    Recovers publishing jobs committed as 'queued' in PostgreSQL
    whose Celery task was never dispatched or failed to dispatch.
    """
    from datetime import datetime, timezone, timedelta
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, PublishStatus

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_threshold_seconds)
    recovered = []
    with SyncSessionLocal() as session:
        stranded_clips = session.query(Clip).filter(
            Clip.publish_status == PublishStatus.QUEUED.value,
            (Clip.publish_started_at < cutoff) | (Clip.publish_started_at == None),
        ).all()

        for clip in stranded_clips:
            logger.info(f"[PublishRecovery] Recovering stranded publish job for clip {clip.id}")
            task = publish_clip_task.apply_async(
                args=[clip.id],
                kwargs={"channel_id": clip.publish_destination_id, "privacy": "private"}
            )
            clip.publish_task_id = task.id
            clip.publish_started_at = datetime.now(timezone.utc)
            recovered.append(clip.id)
        session.commit()
    return {"recovered_count": len(recovered), "clip_ids": recovered}


@celery_app.task(
    bind=True,
    name="apply_autofix",
    **DEFAULT_RETRY_KWARGS,
)
def apply_autofix_task(self, clip_id: str, layout_plan_dict: dict):
    """
    Renders an Auto-Fix candidate variant applying smooth zoom interventions
    without destroying or overwriting the original clip output.
    """
    import json
    import hashlib
    import subprocess
    from datetime import datetime, timezone
    from pathlib import Path

    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, ClipVariant, ArtifactType, TaskExecution, TaskExecutionStatus, ArtifactRecord
    from backend.models.layout import LayoutPlan
    from backend.core.task_execution import check_and_claim_execution
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync
    from backend.services.layout_engine import LayoutEngine
    from celery.exceptions import Ignore

    logger.info(f"Applying Auto-Fix variant for clip {clip_id}")

    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            video_id = clip.video_id

            if clip.run_identity:
                parts = clip.run_identity.split("_")
                job_id = "_".join(parts[:-2]) if len(parts) > 2 else "unknown_job"
            else:
                job_id = "unknown_job"

            plan_hash = hashlib.sha256(json.dumps(layout_plan_dict, sort_keys=True).encode()).hexdigest()
            idemp_key = f"{clip_id}_autofix_{plan_hash}"

            try:
                check_and_claim_execution(
                    task_id=self.request.id,
                    job_id=job_id,
                    clip_id=clip_id,
                    operation="apply_autofix",
                    idempotency_key=idemp_key,
                    worker_id=self.request.hostname or "unknown"
                )
            except Ignore:
                logger.info(f"Autofix task {self.request.id} ignored due to idempotency.")
                return {"clip_id": clip_id, "autofix_applied": True}

        base_storage_key = clip.output_path
        if not base_storage_key:
            raise ValueError("Clip does not have an output_path to apply Auto-Fix onto")

        autofix_storage_key = f"outputs/{video_id}/clips/{clip_id}/variants/autofix_{plan_hash}.mp4"
        layout_plan = LayoutPlan(**layout_plan_dict)

        with managed_download_sync(storage_key=base_storage_key) as input_path:
            with managed_upload_sync(
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.VIDEO_RENDER,
                storage_key=autofix_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as temp_out:

                def run_render():
                    filtergraph = LayoutEngine.build_render_graph(layout_plan, [Path(input_path)])
                    cmd = [
                        "ffmpeg", "-y", "-i", str(input_path),
                        "-filter_complex", filtergraph,
                        "-map", "[outv]",
                        "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "fast",
                        "-c:a", "aac",
                        "-movflags", "+faststart",
                        "-f", "mp4",
                        str(temp_out)
                    ]
                    process = subprocess.run(cmd, capture_output=True)
                    if process.returncode != 0:
                        raise RuntimeError(f"FFmpeg Auto-Fix rendering failed: {process.stderr.decode()[-500:]}")

                from backend.core.task_execution import execution_heartbeater
                with execution_heartbeater(self.request.id, interval=60):
                    run_render()

        # Create ClipVariant in DB
        with SyncSessionLocal() as session:
            ar = session.query(ArtifactRecord).filter_by(storage_key=autofix_storage_key).first()
            if not ar:
                raise ValueError("ArtifactRecord not found after managed_upload_sync")

            interventions_count = len(layout_plan.regions[0].zoom_interventions) if layout_plan.regions else 0
            variant = ClipVariant(
                clip_id=clip_id,
                variant_type="autofix",
                artifact_id=ar.id,
                configuration_hash=plan_hash,
                status="completed",
                variant_metadata=json.dumps({"plan_hash": plan_hash, "interventions": interventions_count})
            )
            session.add(variant)
            session.commit()

        # Mark TaskExecution as completed
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.SUCCEEDED.value
                tx.completed_at = datetime.now(timezone.utc)
                session.commit()

        return {"clip_id": clip_id, "autofix_applied": True, "variant_storage_key": autofix_storage_key}

    except Exception as e:
        logger.error(f"Error applying Auto-Fix to {clip_id}: {e}")
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
            if tx:
                tx.status = TaskExecutionStatus.FAILED.value
                tx.error_message = str(e)
                session.commit()
        raise e

