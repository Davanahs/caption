import os
import json
import uuid
import asyncio
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy.orm import Session
from backend.models.database import SyncSessionLocal
from backend.models.models import (
    Clip, DubbingPlan, DubbingSegment, ClipVariant, ArtifactType, TaskExecution
)
from backend.models.dubbing import DubbingRequest, DubbingSegmentInput, DubbingResponse
from backend.services.dubbing_engine import execute_dubbing_plan
from backend.services.sfx_mixer import SFXMixer
from backend.services.artifact_manager import ArtifactManager
from backend.core.task_execution import check_and_claim_execution
from celery.exceptions import Ignore
import subprocess
import tempfile
import shutil

@shared_task(bind=True, max_retries=3)
def generate_dubbing_variant_task(self, request_dict: dict):
    """
    Celery task to generate a dubbed video variant.
    """
    request = DubbingRequest(**request_dict)
    
    # Idempotency key
    idem_key = (
        f"dubbing_{request.clip_id}_{request.target_language}_"
        f"{request.voice_provider}_{request.voice_id}_"
        f"{request.is_voice_clone}_{request.plan_version}"
    )
    
    with SyncSessionLocal() as session:
        # Check idempotency
        worker_id = f"worker-{uuid.uuid4()}" # For testing/local
        try:
            from celery import current_task
            if current_task and current_task.request.id:
                task_id = current_task.request.id
            else:
                task_id = f"sync-{uuid.uuid4()}"
        except:
            task_id = f"sync-{uuid.uuid4()}"
            
        try:
            execution_record = check_and_claim_execution(
                task_id=task_id,
                job_id=request.job_id,
                clip_id=request.clip_id,
                operation="dubbing_variant",
                idempotency_key=idem_key,
                worker_id=worker_id
            )
        except Ignore:
            print(f"[DubbingTask] Idempotent skip for {idem_key}")
            # Find the existing variant
            existing_variant = session.query(ClipVariant).filter(
                ClipVariant.clip_id == request.clip_id,
                ClipVariant.variant_type == ArtifactType.DUBBING_VARIANT,
                ClipVariant.configuration_hash == idem_key,
                ClipVariant.status == "completed"
            ).first()
            if existing_variant:
                return {"status": "skipped", "variant_id": existing_variant.variant_id}
            return {"status": "skipped", "variant_id": None}
            
        if not execution_record:
            return {"status": "failed", "error": "Execution claim failed"}

        try:
            # 1. Fetch source clip and transcript
            clip = session.query(Clip).filter(Clip.id == request.clip_id).first()
            if not clip:
                raise ValueError(f"Clip {request.clip_id} not found")

            # PREREQ-009: Preflight check clip completion and rendered base file presence before TTS
            if clip.status != "completed" or not clip.output_path:
                raise ValueError(f"Clip {request.clip_id} is not render-complete (status: '{clip.status}'). Cannot dub incomplete clip.")

            from pathlib import Path
            from backend.core.config import settings
            out_p = Path(clip.output_path)
            if not out_p.exists() and not out_p.is_absolute():
                out_p = settings.OUTPUT_DIR / clip.output_path
            if not out_p.exists() or out_p.stat().st_size == 0:
                raise ValueError(f"Rendered base video file for clip {request.clip_id} does not exist or is empty on disk: {clip.output_path}.")

            # Use Clip.transcript_segment as canonical transcript, with fallback
            transcript = (clip.transcript_segment or "").strip() or clip.title or "Video clip without speech"
                
            # If segments not provided in request, create one big segment for now
            segments_input = request.segments
            if not segments_input:
                clip_duration = max(clip.end_time - clip.start_time, 1.0)
                segments_input = [DubbingSegmentInput(
                    sequence=1,
                    source_text=transcript,
                    start_time=0.0,
                    end_time=clip_duration
                )]
            
            # 2. Execute dubbing plan (translate, TTS, atempo)
            dubbing_response: DubbingResponse = asyncio.run(execute_dubbing_plan(request, segments_input))
            
            if dubbing_response.status == "failed":
                raise ValueError(f"Dubbing engine failed: {dubbing_response.error_message}")
                
            # 3. Store the DB records for the plan and segments
            db_plan = DubbingPlan(
                clip_id=request.clip_id,
                target_language=request.target_language,
                voice_provider=request.voice_provider,
                voice_id=request.voice_id,
                is_voice_clone=request.is_voice_clone,
                authorization_granted=request.authorization_granted,
                plan_version=request.plan_version,
                status="completed"
            )
            session.add(db_plan)
            session.flush() # get id
            
            for seg in dubbing_response.segments:
                db_seg = DubbingSegment(
                    plan_id=db_plan.id,
                    sequence=seg.sequence,
                    source_text=seg.source_text,
                    translated_text=seg.translated_text,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    generated_audio_reference=seg.generated_audio_reference,
                    generated_audio_duration=seg.generated_audio_duration,
                    fit_speed=seg.fit_speed,
                    status=seg.status
                )
                session.add(db_seg)

            # 4. Mux Audio into Video using SFXMixer
            # Find the best visual variant (e.g., base render or reframe), or fallback to clip.output_path
            video_input_path = None
            base_variant = session.query(ClipVariant).filter(
                ClipVariant.clip_id == request.clip_id,
                ClipVariant.variant_type == "video_render",
                ClipVariant.status == "completed"
            ).order_by(ClipVariant.created_at.desc()).first()
            
            if base_variant and base_variant.artifact_id:
                try:
                    video_input_path = asyncio.run(ArtifactManager().resolve_artifact_path(base_variant.artifact_id))
                except Exception as e:
                    print(f"[DubbingTask] ArtifactManager resolve failed: {e}")
            
            if not video_input_path and clip.output_path and os.path.exists(clip.output_path):
                video_input_path = clip.output_path
                 
            if not video_input_path:
                raise ValueError(f"Base video variant or output file for clip {request.clip_id} not found")

            from backend.models.artifact_sync import managed_upload_sync
            
            dubbing_storage_key = f"outputs/{clip.video_id}/clips/{request.clip_id}/variants/dubbing_{idem_key}.mp4"
            
            with managed_upload_sync(
                owner_type="clip",
                owner_id=request.clip_id,
                artifact_type=ArtifactType.DUBBING_VARIANT,
                storage_key=dubbing_storage_key,
                retention_policy="persistent",
                processing_version=request.plan_version
            ) as temp_out:
                
                # Using SFXMixer to duck original audio and insert the dubbed audio
                ffmpeg_cmd = asyncio.run(SFXMixer.build_ffmpeg_command(
                    video_input_path=video_input_path,
                    sfx_plan=None,
                    output_path=temp_out,
                    artifact_manager=ArtifactManager(),
                    voiceover_plan=None,
                    dubbing_response=dubbing_response
                ))
                
                # Run the command
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0 or not os.path.exists(temp_out):
                    raise RuntimeError(f"FFmpeg muxing failed: {result.stderr[-500:]}")
            
            # Fetch the stored artifact record
            from backend.models.models import ArtifactRecord
            artifact = session.query(ArtifactRecord).filter(ArtifactRecord.storage_key == dubbing_storage_key).first()
            if not artifact:
                raise ValueError("ArtifactRecord not found after managed_upload_sync")
            
            variant = ClipVariant(
                clip_id=request.clip_id,
                variant_type=ArtifactType.DUBBING_VARIANT,
                artifact_id=artifact.id,
                configuration_hash=idem_key,
                status="completed",
                variant_metadata=json.dumps({"plan_id": db_plan.id, "target_language": request.target_language})
            )
            session.add(variant)
            
            # Mark idempotency completed
            ex = session.query(TaskExecution).filter_by(id=execution_record.id).first()
            if ex:
                ex.status = "succeeded"
                ex.result_id = variant.variant_id
            
            session.commit()
            return {"status": "completed", "variant_id": variant.variant_id}
            
        except Exception as e:
            session.rollback()
            # Fetch the record in this session to update it
            ex = session.query(TaskExecution).filter_by(id=execution_record.id).first()
            if ex:
                ex.status = "failed"
                ex.error_message = str(e)
                session.commit()
            raise e
