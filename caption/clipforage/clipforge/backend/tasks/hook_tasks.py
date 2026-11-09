import asyncio
import hashlib
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Any

from celery.exceptions import Ignore, Retry
from backend.tasks.celery_app import celery_app
from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS
from backend.models.db_sync import update_clip_status_sync

logger = logging.getLogger(__name__)


def _safe_async_run(coro):
    """
    Run an async coroutine safely within a synchronous Celery worker thread.
    If no event loop is currently running in this thread, uses asyncio.run().
    If an event loop is already running in this thread (e.g. during certain async test runners),
    executes the coroutine in a separate worker thread using concurrent.futures to avoid reentrancy crash.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def _normalize_retention_data(raw_json: Optional[str], clip_id: str, clip_duration: float):
    """
    Normalize stored ClipRetention.analysis_json into a validated RetentionAnalysis object.
    Supports:
      1. Raw JSON list of dropoff risk dicts (e.g. from clips.py POST /retention or POST /sfx-plan).
      2. Full RetentionAnalysis dict.
      3. Dictionary containing a "risks" list.
    Returns None if payload is absent, empty, malformed, or invalid without crashing.
    """
    if not raw_json or not str(raw_json).strip():
        return None
    try:
        data = json.loads(raw_json)
    except Exception as e:
        logger.warning(f"Failed to parse retention JSON for clip {clip_id}: {e}")
        return None

    from backend.models.retention import RetentionAnalysis, DropoffRisk, RetentionPoint
    try:
        if isinstance(data, list):
            risks = [DropoffRisk.model_validate(r) for r in data]
            return RetentionAnalysis(
                clip_id=clip_id,
                duration=float(clip_duration),
                analysis_version="1.0",
                points=[],
                risks=risks
            )
        elif isinstance(data, dict):
            if "clip_id" in data and "points" in data and "risks" in data:
                return RetentionAnalysis.model_validate(data)
            elif "risks" in data and isinstance(data["risks"], list):
                risks = [DropoffRisk.model_validate(r) for r in data["risks"]]
                points = [RetentionPoint.model_validate(p) for p in data.get("points", [])]
                return RetentionAnalysis(
                    clip_id=data.get("clip_id", clip_id),
                    duration=float(data.get("duration", clip_duration)),
                    analysis_version=str(data.get("analysis_version", "1.0")),
                    points=points,
                    risks=risks
                )
            else:
                return RetentionAnalysis.model_validate(data)
        else:
            logger.warning(f"Unexpected retention JSON type {type(data)} for clip {clip_id}")
            return None
    except Exception as e:
        logger.warning(f"Failed to validate retention analysis model for clip {clip_id}: {e}")
        return None


@celery_app.task(bind=True, name="analyze_hook_opportunities", **DEFAULT_RETRY_KWARGS)
def analyze_hook_opportunities_task(self, clip_id: str):
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, ContentAnalysis, ClipRetention
    from backend.services.hook_analyzer import hook_analyzer
    
    logger.info(f"Analyzing hook opportunities for clip {clip_id}")
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
                
            content_analysis = session.query(ContentAnalysis).filter_by(clip_id=clip_id).first()
            retention_record = session.query(ClipRetention).filter_by(clip_id=clip_id).order_by(ClipRetention.created_at.desc()).first()
            
            transcript_text = getattr(clip, 'transcript_segment', None)
            clip_duration = clip.end_time - clip.start_time
            
            retention_data = None
            if retention_record and retention_record.analysis_json:
                retention_data = _normalize_retention_data(
                    retention_record.analysis_json,
                    clip_id=clip_id,
                    clip_duration=clip_duration
                )
            
            opportunities = hook_analyzer.analyze_clip_for_hooks(
                clip=clip,
                transcript_text=transcript_text,
                content_analysis=content_analysis,
                retention_data=retention_data,
                clip_duration=clip_duration
            )
            
            # Generate and persist the HookPlan in ClipHookPlan so that GET /api/clips/{clip_id}/hook retrieves it
            from backend.services.hook_planner import hook_planner
            from backend.models.models import ClipHookPlan
            hook_plan = hook_planner.generate_hook_plan(clip_id, opportunities)
            
            db_plan = session.query(ClipHookPlan).filter_by(clip_id=clip_id).first()
            if not db_plan:
                db_plan = ClipHookPlan(
                    clip_id=clip_id,
                    plan_json=hook_plan.model_dump_json(),
                    plan_hash=hook_plan.plan_hash or "hash"
                )
                session.add(db_plan)
            else:
                db_plan.plan_json = hook_plan.model_dump_json()
                db_plan.plan_hash = hook_plan.plan_hash or "hash"
            session.commit()
            
            # Returning as dictionaries
            return [opp.model_dump() for opp in opportunities]
            
    except Exception as e:
        logger.error(f"Error analyzing hook opportunities: {e}")
        raise


@celery_app.task(bind=True, name="apply_hook_plan", **DEFAULT_RETRY_KWARGS)
def apply_hook_task(self, clip_id: str, hook_plan_dict: dict):
    import subprocess
    from backend.models.database import SyncSessionLocal
    from backend.models.models import (
        Clip, Video, ArtifactType, ArtifactStatus, ClipHookPlan,
        ClipSFXPlan, ClipVariant, ArtifactRecord, TaskExecution, TaskExecutionStatus
    )
    from backend.models.hook import HookPlan
    from backend.models.sfx import SFXPlan
    from backend.services.voiceover_engine import voiceover_engine
    from backend.services.artifact_manager import ArtifactManager
    from backend.services.sfx_mixer import SFXMixer
    from backend.services.layout_engine import LayoutEngine
    from backend.core.task_execution import check_and_claim_execution
    from backend.models.artifact_sync import register_artifact_sync, update_artifact_status_sync
    from backend.core.storage import storage_service
    
    logger.info(f"Applying hook plan for clip {clip_id}")
    
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
                
            video = session.query(Video).filter_by(id=clip.video_id).first()
            
            if getattr(clip, 'run_identity', None):
                parts = clip.run_identity.split("_")
                job_id = "_".join(parts[:-2]) if len(parts) > 2 else None
            else:
                job_id = hook_plan_dict.get("job_id")
                
            plan_str = json.dumps(hook_plan_dict, sort_keys=True)
            plan_hash = hashlib.md5(plan_str.encode()).hexdigest()
                
            idemp_key = f"{job_id}_{clip_id}_apply_hook_{plan_hash}"
            try:
                check_and_claim_execution(
                    task_id=self.request.id or str(uuid.uuid4()),
                    job_id=job_id,
                    clip_id=clip_id,
                    operation="apply_hook",
                    idempotency_key=idemp_key,
                    worker_id=self.request.hostname or "mock_worker"
                )
            except Ignore:
                logger.info(f"Skipping apply hook task due to idempotency: {idemp_key}")
                raise
                
            # Parse plan
            hook_plan = HookPlan.model_validate(hook_plan_dict)
            
            # Save the plan to the database
            db_plan = session.query(ClipHookPlan).filter_by(clip_id=clip_id).first()
            if not db_plan:
                db_plan = ClipHookPlan(
                    clip_id=clip_id,
                    plan_json=hook_plan.model_dump_json(),
                    plan_hash=hook_plan.plan_hash or "hash"
                )
                session.add(db_plan)
            else:
                db_plan.plan_json = hook_plan.model_dump_json()
                db_plan.plan_hash = hook_plan.plan_hash or "hash"
            session.commit()
            
            # 1. Execute Voiceover engine
            with tempfile.TemporaryDirectory() as td:
                tmp_dir = Path(td)
                artifact_manager = ArtifactManager()
                
                vo_artifacts = []
                if hook_plan.voiceover_plan and hook_plan.voiceover_plan.segments:
                    vo_artifacts = _safe_async_run(
                        voiceover_engine.execute_plan(
                            clip_id=clip_id,
                            segments=hook_plan.voiceover_plan.segments,
                            output_dir=tmp_dir,
                            provider_name=hook_plan.voiceover_plan.provider
                        )
                    )
                    
                    for seg, art in zip(hook_plan.voiceover_plan.segments, vo_artifacts):
                        seg.artifact = art
                        # Upload artifact to local storage
                        record_info = register_artifact_sync(
                            owner_type="clip",
                            owner_id=clip_id,
                            artifact_type=ArtifactType.AUDIO_VOICEOVER,
                            storage_key=f"outputs/artifacts/{art.artifact_id}.wav",
                            retention_policy="persistent",
                            local_filepath=art.storage_key
                        )
                        update_artifact_status_sync(record_info["storage_key"], ArtifactStatus.READY)
                
                # Fetch SFX Plan if exists
                sfx_plan_db = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).first()
                sfx_plan = None
                if sfx_plan_db and sfx_plan_db.plan_json:
                    sfx_plan = SFXPlan.model_validate_json(sfx_plan_db.plan_json)
                
                # 2. Re-render video using LayoutEngine with zoom interventions
                layout_plan = LayoutEngine.create_vertical_plan(
                    source_w=1920, source_h=1080,
                    canvas_w=1080, canvas_h=1920
                )
                layout_plan.regions[0].zoom_interventions = hook_plan.visual_interventions
                
                video_out_path = tmp_dir / f"{clip_id}_hook_video.mp4"
                
                # Resolve input clip media using managed storage or direct path
                input_clip = None
                if clip.output_path:
                    if os.path.exists(clip.output_path):
                        input_clip = clip.output_path
                    elif storage_service.exists(clip.output_path):
                        temp_in = tmp_dir / f"in_clip_{clip_id}.mp4"
                        storage_service.get(clip.output_path, str(temp_in))
                        input_clip = str(temp_in)
                
                if not input_clip:
                    ar_input = session.query(ArtifactRecord).filter(
                        ArtifactRecord.owner_id == clip_id,
                        ArtifactRecord.owner_type == "clip",
                        ArtifactRecord.artifact_type.in_([
                            ArtifactType.FINAL_CLIP.value,
                            ArtifactType.VERTICAL_CLIP.value,
                            ArtifactType.VIDEO_RENDER.value
                        ]),
                        ArtifactRecord.status.in_([ArtifactStatus.READY.value, ArtifactStatus.CREATED.value])
                    ).order_by(ArtifactRecord.created_at.desc()).first()
                    
                    if ar_input:
                        if os.path.exists(ar_input.storage_key):
                            input_clip = ar_input.storage_key
                        elif storage_service.exists(ar_input.storage_key):
                            temp_in = tmp_dir / f"in_ar_{clip_id}.mp4"
                            storage_service.get(ar_input.storage_key, str(temp_in))
                            input_clip = str(temp_in)
                            
                if not input_clip and video and video.local_path:
                    if os.path.exists(video.local_path):
                        input_clip = video.local_path
                    elif storage_service.exists(video.local_path):
                        temp_in = tmp_dir / f"in_vid_{video.id}.mp4"
                        storage_service.get(video.local_path, str(temp_in))
                        input_clip = str(temp_in)
                        
                if not input_clip:
                    raise ValueError(f"No valid input video found for clip {clip_id} to apply hook onto")
                
                filtergraph = LayoutEngine.build_render_graph(layout_plan, [Path(input_clip)])
                
                # Check if hook text graphics should be rendered as an explicit overlay title
                hook_text = ""
                if hook_plan.concepts:
                    concept = hook_plan.concepts[0]
                    if concept.hook_text:
                        import re
                        hook_text = re.sub(r"\s*\([a-z_]+\)\s*$", "", concept.hook_text).strip()

                temp_txt_file = None
                if hook_text:
                    from backend.services.hook_generator import _resolve_font
                    import textwrap

                    font_path = _resolve_font()
                    font_arg = ""
                    if font_path:
                        escaped_font = font_path.replace("\\", "/").replace(":", r"\\:")
                        font_arg = f":fontfile={escaped_font}"
                    
                    # Wrap text for 1080px portrait framing
                    wrapped_lines = textwrap.wrap(hook_text, width=28)
                    wrapped_text = "\n".join(wrapped_lines) if wrapped_lines else hook_text

                    # Write to a UTF-8 text file to eliminate all filtergraph quoting/character escaping issues
                    tfd, temp_txt_file = tempfile.mkstemp(prefix="cf_hook_txt_", suffix=".txt")
                    with open(tfd, "w", encoding="utf-8") as tf:
                        tf.write(wrapped_text)

                    escaped_txt = temp_txt_file.replace("\\", "/").replace(":", r"\\:")

                    start_t = hook_plan.opportunities[0].start_time if hook_plan.opportunities else 0.0
                    duration_t = hook_plan.concepts[0].target_duration if hook_plan.concepts else 2.5
                    end_t = start_t + duration_t
                    
                    # Drawtext graphic with box backing, safe upper-third positioning
                    drawtext_filter = (
                        f"drawtext=textfile={escaped_txt}{font_arg}:fontsize=54:fontcolor=white:"
                        f"box=1:boxcolor=black@0.65:boxborderw=24:x=(w-text_w)/2:y=h*0.18:"
                        f"enable='between(t,{start_t:.2f},{end_t:.2f})'"
                    )
                    if filtergraph.endswith("[outv]"):
                        filtergraph = filtergraph[:-6] + f"[v_pretxt];[v_pretxt]{drawtext_filter}[outv]"
                    else:
                        filtergraph = filtergraph + f";[outv]{drawtext_filter}[outv_txt]"

                video_cmd = [
                    "ffmpeg", "-y", "-i", input_clip,
                    "-filter_complex", filtergraph,
                    "-map", "[outv]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac",
                    "-movflags", "+faststart",
                    str(video_out_path)
                ]
                logger.info(f"Running layout engine: {' '.join(video_cmd)}")
                try:
                    subprocess.run(video_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                finally:
                    if temp_txt_file and os.path.exists(temp_txt_file):
                        try:
                            os.remove(temp_txt_file)
                        except OSError:
                            pass
                
                # 3. Mix audio (SFX + VO)
                final_out_path = tmp_dir / f"{clip_id}_hook_final.mp4"
                
                # If provider is mock or only created silent test tones, do NOT duck main audio over silence!
                valid_vo_plan = None
                vo_applied = False
                if hook_plan.voiceover_plan and hook_plan.voiceover_plan.segments and vo_artifacts:
                    if hook_plan.voiceover_plan.provider != "mock":
                        valid_vo_plan = hook_plan.voiceover_plan
                        vo_applied = True
                    else:
                        logger.info("Voiceover provider is mock (silent dummy tone). Preserving speech audio without ducking.")

                mix_cmd = _safe_async_run(
                    SFXMixer.build_ffmpeg_command(
                        video_input_path=str(video_out_path),
                        sfx_plan=sfx_plan,
                        output_path=str(final_out_path),
                        artifact_manager=artifact_manager,
                        voiceover_plan=valid_vo_plan
                    )
                )
                logger.info(f"Running SFX Mixer: {' '.join(mix_cmd)}")
                subprocess.run(mix_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # 4. Upload final artifact as a variant
                artifact_id = f"hook_{clip_id}"
                video_id_prefix = video.id if video else "unknown"
                variant_storage_key = f"outputs/{video_id_prefix}/clips/{clip_id}/variants/hook_{plan_hash}.mp4"
                
                record_info = register_artifact_sync(
                    owner_type="clip",
                    owner_id=clip_id,
                    artifact_type=ArtifactType.VIDEO_RENDER,
                    storage_key=variant_storage_key,
                    retention_policy="persistent",
                    local_filepath=str(final_out_path)
                )
                update_artifact_status_sync(variant_storage_key, ArtifactStatus.READY)
                
                ar = session.query(ArtifactRecord).filter_by(storage_key=variant_storage_key).first()
                if not ar:
                    raise RuntimeError(f"ArtifactRecord missing after upload for {variant_storage_key}")
                    
                variant = session.query(ClipVariant).filter_by(
                    clip_id=clip_id,
                    variant_type="hook"
                ).first()
                if not variant:
                    variant = ClipVariant(
                        clip_id=clip_id,
                        variant_type="hook",
                        artifact_id=ar.id,
                        configuration_hash=plan_hash,
                        status="completed",
                        variant_metadata=hook_plan.model_dump_json()
                    )
                    session.add(variant)
                else:
                    variant.artifact_id = ar.id
                    variant.configuration_hash = plan_hash
                    variant.status = "completed"
                    variant.variant_metadata = hook_plan.model_dump_json()
                session.commit()
                
                # Mark execution as succeeded
                if self.request.id:
                    tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
                    if tx:
                        from datetime import datetime, timezone
                        tx.status = TaskExecutionStatus.SUCCEEDED.value
                        tx.completed_at = datetime.now(timezone.utc)
                        session.commit()
                
                logger.info(f"Hook processing complete for clip {clip_id}")
                return {"status": "success", "artifact_id": ar.id, "variant_type": "hook"}
                
    except (Ignore, Retry):
        raise
    except Exception as e:
        logger.error(f"Error applying hook plan: {e}")
        # Mark execution as failed if we have a request id
        if self.request.id:
            from backend.models.database import SyncSessionLocal
            from backend.models.models import TaskExecution, TaskExecutionStatus
            with SyncSessionLocal() as session:
                tx = session.query(TaskExecution).filter_by(id=self.request.id).first()
                if tx and tx.status != TaskExecutionStatus.SUCCEEDED.value:
                    tx.status = TaskExecutionStatus.FAILED.value
                    tx.failure_reason = str(e)
                    session.commit()
        raise

