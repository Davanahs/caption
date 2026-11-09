"""
ClipForge Settings Route
Canonical Phase 5.1 (C-09) — Settings Backend Persistence Architecture (REQ-GAP-001)

Provides GET /api/settings and PUT /api/settings endpoints for dynamic system configuration,
credential masking, runtime synchronization, and durable file persistence.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_FILE = settings.BASE_DIR / "data" / "settings.json"
ALLOWED_WHISPER_MODELS = {"tiny", "base", "small", "medium", "large"}
ALLOWED_REFRAME_MODES = {"blur", "fit", "crop", "template"}
SECRET_MASK = "••••••••"


class SettingsResponse(BaseModel):
    YOUTUBE_CLIENT_ID: str
    YOUTUBE_CLIENT_SECRET_SET: bool
    YOUTUBE_CLIENT_SECRET_MASKED: str
    OPENROUTER_API_KEY_SET: bool = False
    OPENROUTER_API_KEY_MASKED: str = ""
    OPENROUTER_MODEL: str = "deepseek/deepseek-r1:free"
    GROQ_API_KEY_SET: bool = False
    GROQ_API_KEY_MASKED: str = ""
    GROQ_MODEL: str = "whisper-large-v3-turbo"
    NVIDIA_API_KEY_SET: bool = False
    NVIDIA_API_KEY_MASKED: str = ""
    NVIDIA_MODEL: str = "meta/llama-3.1-405b-instruct"
    WHISPER_MODEL: str
    CLIPS_PER_VIDEO: int
    CHANNEL_CHECK_INTERVAL_MINUTES: int
    PUBLISH_MODE: str
    SCORING_MODE: str
    REFRAME_MODE: str
    CONTENT_ID_BYPASS: bool
    last_updated_at: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: Optional[str] = None
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_MODEL: Optional[str] = None
    WHISPER_MODEL: Optional[str] = None
    CLIPS_PER_VIDEO: Optional[int] = Field(None, ge=1, le=20)
    CHANNEL_CHECK_INTERVAL_MINUTES: Optional[int] = Field(None, ge=5, le=1440)
    REFRAME_MODE: Optional[str] = None
    CONTENT_ID_BYPASS: Optional[bool] = None


def load_persisted_settings_data() -> dict:
    """Reads persisted settings from data/settings.json if it exists."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_persisted_settings_data(data: dict) -> None:
    """Persists settings dict to data/settings.json atomically."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = SETTINGS_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp_file.replace(SETTINGS_FILE)


def apply_settings_to_runtime(data: dict) -> None:
    """Applies persisted settings dictionary to active runtime settings object."""
    dynamic_keys = [
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "NVIDIA_API_KEY",
        "NVIDIA_MODEL",
        "WHISPER_MODEL",
        "CLIPS_PER_VIDEO",
        "CHANNEL_CHECK_INTERVAL_MINUTES",
        "REFRAME_MODE",
        "CONTENT_ID_BYPASS",
    ]
    for key in dynamic_keys:
        if key in data and data[key] is not None:
            val = data[key]
            # Convert types if needed
            if key == "CLIPS_PER_VIDEO":
                val = int(val)
            elif key == "CHANNEL_CHECK_INTERVAL_MINUTES":
                val = int(val)
            elif key == "CONTENT_ID_BYPASS":
                val = bool(val)
            setattr(settings, key, val)


def init_dynamic_settings() -> None:
    """Invoked on backend boot to load dynamic settings into memory."""
    data = load_persisted_settings_data()
    if data:
        apply_settings_to_runtime(data)


@router.get("", response_model=SettingsResponse)
@router.get("/", response_model=SettingsResponse)
async def get_settings():
    """
    Returns active system configurations with sensitive secrets masked.
    Guarantees client secrets are never exposed in plaintext over API.
    """
    persisted = load_persisted_settings_data()
    has_secret = bool(settings.YOUTUBE_CLIENT_SECRET and settings.YOUTUBE_CLIENT_SECRET.strip())
    masked_secret = SECRET_MASK if has_secret else ""

    has_openrouter = bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip())
    has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
    has_nvidia = bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY.strip())

    return SettingsResponse(
        YOUTUBE_CLIENT_ID=settings.YOUTUBE_CLIENT_ID or "",
        YOUTUBE_CLIENT_SECRET_SET=has_secret,
        YOUTUBE_CLIENT_SECRET_MASKED=masked_secret,
        OPENROUTER_API_KEY_SET=has_openrouter,
        OPENROUTER_API_KEY_MASKED=SECRET_MASK if has_openrouter else "",
        OPENROUTER_MODEL=settings.OPENROUTER_MODEL or "deepseek/deepseek-r1:free",
        GROQ_API_KEY_SET=has_groq,
        GROQ_API_KEY_MASKED=SECRET_MASK if has_groq else "",
        GROQ_MODEL=settings.GROQ_MODEL or "whisper-large-v3-turbo",
        NVIDIA_API_KEY_SET=has_nvidia,
        NVIDIA_API_KEY_MASKED=SECRET_MASK if has_nvidia else "",
        NVIDIA_MODEL=settings.NVIDIA_MODEL or "meta/llama-3.1-405b-instruct",
        WHISPER_MODEL=settings.WHISPER_MODEL,
        CLIPS_PER_VIDEO=settings.CLIPS_PER_VIDEO,
        CHANNEL_CHECK_INTERVAL_MINUTES=settings.CHANNEL_CHECK_INTERVAL_MINUTES,
        PUBLISH_MODE=settings.PUBLISH_MODE,
        SCORING_MODE=settings.SCORING_MODE,
        REFRAME_MODE=settings.REFRAME_MODE,
        CONTENT_ID_BYPASS=settings.CONTENT_ID_BYPASS,
        last_updated_at=persisted.get("last_updated_at"),
    )


@router.put("", response_model=SettingsResponse)
@router.put("/", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdateRequest):
    """
    Updates system settings with validation, dynamic runtime application,
    and durable persistence in data/settings.json.
    """
    # 1. Validation
    if payload.WHISPER_MODEL is not None:
        model_clean = payload.WHISPER_MODEL.strip().lower()
        if model_clean not in ALLOWED_WHISPER_MODELS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid WHISPER_MODEL '{payload.WHISPER_MODEL}'. Must be one of: {', '.join(sorted(ALLOWED_WHISPER_MODELS))}"
            )

    if payload.REFRAME_MODE is not None:
        reframe_clean = payload.REFRAME_MODE.strip().lower()
        if reframe_clean not in ALLOWED_REFRAME_MODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid REFRAME_MODE '{payload.REFRAME_MODE}'. Must be one of: {', '.join(sorted(ALLOWED_REFRAME_MODES))}"
            )

    if payload.CLIPS_PER_VIDEO is not None and (payload.CLIPS_PER_VIDEO < 1 or payload.CLIPS_PER_VIDEO > 20):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CLIPS_PER_VIDEO must be between 1 and 20"
        )

    if payload.CHANNEL_CHECK_INTERVAL_MINUTES is not None and (
        payload.CHANNEL_CHECK_INTERVAL_MINUTES < 5 or payload.CHANNEL_CHECK_INTERVAL_MINUTES > 1440
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CHANNEL_CHECK_INTERVAL_MINUTES must be between 5 and 1440"
        )

    # 2. Load existing persisted settings
    persisted = load_persisted_settings_data()

    # 3. Apply updates
    if payload.YOUTUBE_CLIENT_ID is not None:
        persisted["YOUTUBE_CLIENT_ID"] = payload.YOUTUBE_CLIENT_ID.strip()

    # Only update secret if provided and not the mask placeholder
    if payload.YOUTUBE_CLIENT_SECRET is not None:
        secret_clean = payload.YOUTUBE_CLIENT_SECRET.strip()
        if secret_clean and secret_clean != SECRET_MASK:
            persisted["YOUTUBE_CLIENT_SECRET"] = secret_clean

    if payload.OPENROUTER_API_KEY is not None:
        openrouter_clean = payload.OPENROUTER_API_KEY.strip()
        if openrouter_clean and openrouter_clean != SECRET_MASK:
            persisted["OPENROUTER_API_KEY"] = openrouter_clean

    if payload.OPENROUTER_MODEL is not None:
        persisted["OPENROUTER_MODEL"] = payload.OPENROUTER_MODEL.strip()

    if payload.GROQ_API_KEY is not None:
        groq_clean = payload.GROQ_API_KEY.strip()
        if groq_clean and groq_clean != SECRET_MASK:
            persisted["GROQ_API_KEY"] = groq_clean

    if payload.GROQ_MODEL is not None:
        persisted["GROQ_MODEL"] = payload.GROQ_MODEL.strip()

    if payload.NVIDIA_API_KEY is not None:
        nvidia_clean = payload.NVIDIA_API_KEY.strip()
        if nvidia_clean and nvidia_clean != SECRET_MASK:
            persisted["NVIDIA_API_KEY"] = nvidia_clean

    if payload.NVIDIA_MODEL is not None:
        persisted["NVIDIA_MODEL"] = payload.NVIDIA_MODEL.strip()

    if payload.WHISPER_MODEL is not None:
        persisted["WHISPER_MODEL"] = payload.WHISPER_MODEL.strip().lower()

    if payload.CLIPS_PER_VIDEO is not None:
        persisted["CLIPS_PER_VIDEO"] = payload.CLIPS_PER_VIDEO

    if payload.CHANNEL_CHECK_INTERVAL_MINUTES is not None:
        persisted["CHANNEL_CHECK_INTERVAL_MINUTES"] = payload.CHANNEL_CHECK_INTERVAL_MINUTES

    if payload.REFRAME_MODE is not None:
        persisted["REFRAME_MODE"] = payload.REFRAME_MODE.strip().lower()

    if payload.CONTENT_ID_BYPASS is not None:
        persisted["CONTENT_ID_BYPASS"] = payload.CONTENT_ID_BYPASS

    now_iso = datetime.now(timezone.utc).isoformat()
    persisted["last_updated_at"] = now_iso

    # 4. Save to durable store
    save_persisted_settings_data(persisted)

    # 5. Apply to runtime in-memory settings
    apply_settings_to_runtime(persisted)

    # 6. Return response
    has_secret = bool(settings.YOUTUBE_CLIENT_SECRET and settings.YOUTUBE_CLIENT_SECRET.strip())
    masked_secret = SECRET_MASK if has_secret else ""

    has_openrouter = bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip())
    has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
    has_nvidia = bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY.strip())

    return SettingsResponse(
        YOUTUBE_CLIENT_ID=settings.YOUTUBE_CLIENT_ID or "",
        YOUTUBE_CLIENT_SECRET_SET=has_secret,
        YOUTUBE_CLIENT_SECRET_MASKED=masked_secret,
        OPENROUTER_API_KEY_SET=has_openrouter,
        OPENROUTER_API_KEY_MASKED=SECRET_MASK if has_openrouter else "",
        OPENROUTER_MODEL=settings.OPENROUTER_MODEL or "deepseek/deepseek-r1:free",
        GROQ_API_KEY_SET=has_groq,
        GROQ_API_KEY_MASKED=SECRET_MASK if has_groq else "",
        GROQ_MODEL=settings.GROQ_MODEL or "whisper-large-v3-turbo",
        NVIDIA_API_KEY_SET=has_nvidia,
        NVIDIA_API_KEY_MASKED=SECRET_MASK if has_nvidia else "",
        NVIDIA_MODEL=settings.NVIDIA_MODEL or "meta/llama-3.1-405b-instruct",
        WHISPER_MODEL=settings.WHISPER_MODEL,
        CLIPS_PER_VIDEO=settings.CLIPS_PER_VIDEO,
        CHANNEL_CHECK_INTERVAL_MINUTES=settings.CHANNEL_CHECK_INTERVAL_MINUTES,
        PUBLISH_MODE=settings.PUBLISH_MODE,
        SCORING_MODE=settings.SCORING_MODE,
        REFRAME_MODE=settings.REFRAME_MODE,
        CONTENT_ID_BYPASS=settings.CONTENT_ID_BYPASS,
        last_updated_at=now_iso,
    )
