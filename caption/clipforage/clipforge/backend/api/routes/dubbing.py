import json
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.database import get_db
from backend.models.models import Clip, DubbingPlan, DubbingSegment, ClipVariant, ArtifactType, Job
from backend.models.dubbing import DubbingRequest
from backend.tasks.dubbing_tasks import generate_dubbing_variant_task
from backend.tasks.celery_app import celery_app

router = APIRouter(tags=["Dubbing"])

SUPPORTED_LANGUAGES = [
    {"code": "es", "name": "Spanish", "native_name": "Español", "default_voice": "es-ES-AlvaroNeural", "voice_provider": "edge_tts"},
    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी", "default_voice": "hi-IN-MadhurNeural", "voice_provider": "edge_tts"},
    {"code": "de", "name": "German", "native_name": "Deutsch", "default_voice": "de-DE-ConradNeural", "voice_provider": "edge_tts"},
    {"code": "ja", "name": "Japanese", "native_name": "日本語", "default_voice": "ja-JP-KeitaNeural", "voice_provider": "edge_tts"},
    {"code": "pt", "name": "Portuguese", "native_name": "Português", "default_voice": "pt-BR-AntonioNeural", "voice_provider": "edge_tts"},
    {"code": "fr", "name": "French", "native_name": "Français", "default_voice": "fr-FR-HenriNeural", "voice_provider": "edge_tts"},
]

SUPPORTED_LANGUAGE_CODES = {l["code"] for l in SUPPORTED_LANGUAGES}


@router.get("/api/dubbing/languages")
@router.get("/api/clips/dubbing/languages")
async def get_dubbing_languages():
    """
    Returns list of supported target languages and default voices for auto-dubbing.
    """
    return {"languages": SUPPORTED_LANGUAGES}


@router.get("/api/dubbing/tasks/{task_id}")
async def get_dubbing_task_status(task_id: str):
    """
    Polls Celery async task execution status for a dubbing job.
    """
    try:
        res = celery_app.AsyncResult(task_id)
        ready = res.ready()
        return {
            "task_id": task_id,
            "status": res.status,
            "ready": ready,
            "result": res.result if ready else None
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "UNKNOWN",
            "ready": False,
            "error": str(e)
        }


@router.get("/api/dubbing/{clip_id}")
@router.get("/api/clips/{clip_id}/dubbing")
async def get_clip_dubbing(clip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves all dubbing plans and generated dubbed variants for a given clip.
    """
    clip_result = await db.execute(select(Clip).filter(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    plans_res = await db.execute(
        select(DubbingPlan).filter(DubbingPlan.clip_id == clip_id).order_by(DubbingPlan.created_at.desc())
    )
    plans = plans_res.scalars().all()

    variants_res = await db.execute(
        select(ClipVariant).filter(
            ClipVariant.clip_id == clip_id,
            ClipVariant.variant_type == ArtifactType.DUBBING_VARIANT.value
        )
    )
    variants = variants_res.scalars().all()

    lang_map = {l["code"]: l["name"] for l in SUPPORTED_LANGUAGES}

    formatted_plans = []
    for p in plans:
        # Match variant by plan_id inside variant_metadata
        matched_variant = None
        for v in variants:
            if v.variant_metadata and p.id in v.variant_metadata:
                matched_variant = v
                break

        formatted_plans.append({
            "id": p.id,
            "plan_id": p.id,
            "target_language": p.target_language,
            "target_language_name": lang_map.get(p.target_language.lower(), p.target_language),
            "voice_provider": p.voice_provider,
            "voice_id": p.voice_id,
            "is_voice_clone": p.is_voice_clone,
            "status": p.status,
            "error_message": p.error_message,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "variant_id": matched_variant.variant_id if matched_variant else None,
            "variant_status": matched_variant.status if matched_variant else None,
        })

    return {
        "clip_id": clip_id,
        "plans": formatted_plans
    }


@router.post("/api/dubbing/{clip_id}")
@router.post("/api/clips/{clip_id}/dub")
@router.post("/clips/{clip_id}/dub")
async def trigger_dubbing(clip_id: str, request: DubbingRequest, db: AsyncSession = Depends(get_db)):
    """
    Trigger multi-language auto-dubbing for a clip.
    """
    if clip_id != request.clip_id:
        raise HTTPException(status_code=400, detail="Path clip_id does not match request body")

    result = await db.execute(select(Clip).filter(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    target_lang = request.target_language.lower().strip()
    if target_lang not in SUPPORTED_LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target language '{request.target_language}'. Supported: {sorted(list(SUPPORTED_LANGUAGE_CODES))}"
        )

    if request.is_voice_clone and not request.authorization_granted:
        raise HTTPException(status_code=403, detail="Voice clone requested but authorization not granted")

    # PREREQ-009: Preflight check clip completion and rendered base file presence
    if clip.status != "completed" or not clip.output_path:
        raise HTTPException(
            status_code=400,
            detail=f"Clip {clip.id} is not render-complete (status: '{clip.status}'). Dubbing requires a completed base clip."
        )

    out_p = Path(clip.output_path)
    if not out_p.is_absolute():
        from backend.core.config import settings
        out_p = settings.OUTPUT_DIR / clip.output_path
    if not out_p.exists() or out_p.stat().st_size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Rendered base video file for clip {clip.id} does not exist or is empty on disk: {clip.output_path}."
        )

    # Resolve job_id if not explicitly provided
    if not request.job_id:
        job_result = await db.execute(
            select(Job.id).filter(Job.video_id == clip.video_id).order_by(Job.created_at.desc())
        )
        found_job = job_result.scalar_one_or_none()
        request.job_id = found_job or f"dub-job-{clip.id[:8]}"

    # Resolve default voice if set to 'default' or empty
    if not request.voice_id or request.voice_id.lower() == "default":
        for l in SUPPORTED_LANGUAGES:
            if l["code"] == target_lang:
                request.voice_id = l["default_voice"]
                break

    task = generate_dubbing_variant_task.delay(request.model_dump())
    return {
        "message": "Dubbing task triggered",
        "task_id": task.id,
        "clip_id": clip_id,
        "target_language": target_lang,
        "status": "pending"
    }
