"""
API Routes — YouTube Channels Management
Dedicated router for managing authorized YouTube publishing destinations (/youtube-channels).
Strictly decoupled from monitored source channels and synthetic test channels.
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update, desc, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.models import Channel, ChannelDestination, Clip, DestinationOutro, PublishTarget
from backend.models.outro import (
    OutroMetadata,
    OutroResponse,
    OutroUploadResponse,
    OutroDeleteResponse,
)
from backend.services.outro_service import (
    save_destination_outro,
    get_active_destination_outro,
    remove_destination_outro,
    resolve_safe_outro_path,
    InvalidOutroError,
)
from backend.core.config import settings
from backend.services.publisher import (
    get_oauth_url,
    exchange_code_for_token,
    check_channel_authorization,
    get_destination_auth_metadata,
    fetch_channel_analytics,
    sync_authorized_destinations,
    _resolve_token_dir,
)

router = APIRouter(prefix="/api/youtube-channels", tags=["youtube-channels"])

# ─── In-Flight Concurrency & Cooldown Governance ─────────────────────────────
CHANNEL_STATS_COOLDOWN_SECONDS = 60
_channel_refresh_locks: dict[str, asyncio.Lock] = {}
_locks_mutex = asyncio.Lock()


async def _get_channel_refresh_lock(channel_id: str) -> asyncio.Lock:
    """Retrieve or create an async lock for a channel to prevent concurrent double-fetches."""
    async with _locks_mutex:
        if channel_id not in _channel_refresh_locks:
            _channel_refresh_locks[channel_id] = asyncio.Lock()
        return _channel_refresh_locks[channel_id]


def _get_cooldown_remaining(cached_stats: dict | None, cooldown_seconds: int = CHANNEL_STATS_COOLDOWN_SECONDS) -> int:
    """Calculate remaining seconds until live refresh is allowed. Returns 0 if expired or un-cached."""
    if not cached_stats or not isinstance(cached_stats, dict):
        return 0
    fetched_at_raw = cached_stats.get("fetched_at")
    if not fetched_at_raw:
        return 0
    try:
        fetched_at_str = str(fetched_at_raw)
        if fetched_at_str.endswith("Z"):
            fetched_at_str = fetched_at_str[:-1] + "+00:00"
        fetched_at = datetime.fromisoformat(fetched_at_str)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        elapsed = (now - fetched_at).total_seconds()
        remaining = int(cooldown_seconds - elapsed)
        return max(0, remaining)
    except Exception:
        return 0



# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class PublishingSettingsUpdate(BaseModel):
    default_privacy: str | None = Field(None, description="Default video privacy: public, unlisted, private")
    default_category: str | None = Field(None, description="YouTube Category ID, e.g. 22 for People & Blogs")
    default_tags: str | list[str] | None = Field(None, description="Default tags as comma-separated string or list")
    default_license: str | None = Field(None, description="License type: youtube or creative_commons")
    default_made_for_kids: bool | None = Field(None, description="Whether content is self-declared made for kids")
    default_age_restricted: bool | None = Field(None, description="Whether content is age-restricted")
    watermark_url: str | None = Field(None, description="Optional watermark image URL")
    brand_color_primary: str | None = Field(None, description="Brand primary hex color code")
    brand_logo_position: str | None = Field(None, description="Logo position: top_right, top_left, bottom_right, bottom_left")

    @field_validator("default_privacy")
    @classmethod
    def validate_privacy(cls, v):
        if v is not None and v.lower() not in ("public", "unlisted", "private"):
            raise ValueError("default_privacy must be 'public', 'unlisted', or 'private'")
        return v.lower() if v else v

    @field_validator("default_license")
    @classmethod
    def validate_license(cls, v):
        if v is not None and v.lower() not in ("youtube", "creative_commons"):
            raise ValueError("default_license must be 'youtube' or 'creative_commons'")
        return v.lower() if v else v

    @field_validator("brand_logo_position")
    @classmethod
    def validate_logo_position(cls, v):
        if v is not None and v.lower() not in ("top_right", "top_left", "bottom_right", "bottom_left"):
            raise ValueError("brand_logo_position must be top_right, top_left, bottom_right, or bottom_left")
        return v.lower() if v else v


class ConnectChannelRequest(BaseModel):
    code: str | None = None
    redirect_url: str | None = None
    state: str | None = None


class OutroUpdateRequest(BaseModel):
    duration_seconds: float = Field(..., ge=0.5, le=15.0, description="Display duration for image outro (0.5 - 15.0s)")


# ─── Static Endpoints (Precede dynamic parameter paths) ──────────────────────

@router.get("/oauth-url")
async def get_channel_oauth_url(
    redirect_uri: str | None = None,
    state: str | None = None,
):
    """
    Generate Google OAuth URL with multi-account selection prompt (select_account consent).
    Allows linking additional YouTube channels safely.
    """
    if not state:
        state = f"ch_oauth_{uuid.uuid4().hex[:12]}"

    auth_url = get_oauth_url(
        redirect_uri=redirect_uri,
        state=state,
        prompt="select_account consent",
    )
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="YouTube OAuth is not configured on this server (missing Client ID/Secret).",
        )
    return {"oauth_url": auth_url, "state": state}


@router.post("/connect")
async def connect_youtube_channel(
    body: ConnectChannelRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete OAuth flow by exchanging authorization code or redirect URL.
    Verifies channel identity server-side and saves isolated credentials.
    """
    raw_code = body.code
    redirect_url = body.redirect_url

    if not raw_code and not redirect_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either authorization 'code' or full 'redirect_url' must be provided.",
        )

    code_to_exchange = raw_code
    if not code_to_exchange and redirect_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(redirect_url)
        params = urllib.parse.parse_qs(parsed.query)
        code_to_exchange = params.get("code", [None])[0]
        if not code_to_exchange:
            # Check fragment
            frag_params = urllib.parse.parse_qs(parsed.fragment)
            code_to_exchange = frag_params.get("code", [None])[0]

    if not code_to_exchange:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract authorization code from input.",
        )

    try:
        token_result = exchange_code_for_token(code=code_to_exchange)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth token exchange failed: {str(e)}",
        )

    # Fetch newly connected channel from database
    result = await db.execute(
        select(Channel)
        .options(selectinload(Channel.active_outro))
        .where(Channel.youtube_channel_id == token_result["channel_id"])
    )
    db_ch = result.scalar_one_or_none()

    # Pre-fetch stats
    try:
        stats = await asyncio.to_thread(fetch_channel_analytics, token_result["channel_id"])
        if db_ch:
            db_ch.cached_stats = stats
            await db.commit()
            await db.refresh(db_ch)
    except Exception as stats_err:
        print(f"[connect_youtube_channel] Initial stats fetch note: {stats_err}")

    active_outro_data = None
    if db_ch and db_ch.active_outro and db_ch.active_outro.is_active:
        active_outro_data = serialize_outro(db_ch.active_outro, db_ch.id).model_dump()

    auth_meta = get_destination_auth_metadata(
        token_result["channel_id"],
        db_ch.channel_url if db_ch else None,
        token_result.get("title") or (db_ch.channel_name if db_ch else None),
        bool(db_ch.is_default_destination) if db_ch else True,
    )

    return {
        "status": "connected",
        "channel": {
            "id": db_ch.id if db_ch else token_result.get("id"),
            "youtube_channel_id": token_result["channel_id"],
            "channel_name": token_result.get("title") or (db_ch.channel_name if db_ch else ""),
            "thumbnail_url": db_ch.thumbnail_url if db_ch else token_result.get("thumbnail_url"),
            "google_account_identity": auth_meta["google_account_identity"],
            "upload_permission_status": auth_meta["upload_permission_status"],
            "is_default_destination": db_ch.is_default_destination if db_ch else True,
            "is_authorized": True,
            "ready_for_publishing": bool(db_ch.is_active if db_ch else True),
            "has_outro": active_outro_data is not None,
            "outro_status": "configured" if active_outro_data is not None else "none",
            "active_outro": active_outro_data,
        },
    }


def serialize_outro(outro_record: Any, channel_id: str) -> OutroMetadata:
    return OutroMetadata(
        id=str(outro_record.id),
        channel_id=str(outro_record.channel_id),
        file_path=str(outro_record.file_path),
        original_filename=outro_record.original_filename,
        file_size_bytes=outro_record.file_size_bytes,
        outro_type=outro_record.outro_type,
        duration_seconds=float(outro_record.duration_seconds),
        width=outro_record.width,
        height=outro_record.height,
        fps=outro_record.fps,
        has_audio=bool(outro_record.has_audio),
        version=int(outro_record.version),
        is_active=bool(outro_record.is_active),
        preview_url=f"/api/youtube-channels/{channel_id}/outro/preview",
        created_at=outro_record.created_at.isoformat() if outro_record.created_at else None,
        updated_at=outro_record.updated_at.isoformat() if outro_record.updated_at else None,
    )


# ─── Channel Collection Route ────────────────────────────────────────────────

@router.get("/")
@router.get("")
async def list_youtube_channels(
    include_test: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    List all authorized YouTube publishing destinations.
    - Synchronizes token files on disk.
    - Excludes monitored source channels (is_destination == False).
    - Excludes synthetic test channels by default (is_test == False).
    - Returns cached statistics, publishing settings, connection status,
      and active outro configuration metadata with preview URL.
    """
    # 1. Sync credentials on disk
    sync_authorized_destinations()

    # 2. Query destinations
    query = (
        select(Channel)
        .options(selectinload(Channel.active_outro))
        .where(Channel.is_destination == True)
    )
    if not include_test:
        query = query.where(Channel.is_test == False)

    result = await db.execute(
        query.order_by(Channel.is_default_destination.desc(), Channel.created_at.asc())
    )
    channels = result.scalars().all()
    channel_ids = [c.id for c in channels]

    # Batch-fetch last successful upload, last error, and source mapping counts (avoid N+1 queries)
    last_success_map: dict[str, datetime] = {}
    last_error_map: dict[str, tuple[str, datetime | None]] = {}
    mapped_sources_count_map: dict[str, int] = {}

    if channel_ids:
        pt_success_rows = await db.execute(
            select(PublishTarget.destination_id, func.max(PublishTarget.published_at))
            .where(
                PublishTarget.destination_id.in_(channel_ids),
                PublishTarget.status.in_(["completed", "published"]),
                PublishTarget.published_at.isnot(None),
            )
            .group_by(PublishTarget.destination_id)
        )
        for d_id, ts in pt_success_rows.all():
            if ts:
                last_success_map[d_id] = ts

        clip_success_rows = await db.execute(
            select(Clip.publish_destination_id, func.max(Clip.published_at))
            .where(
                Clip.publish_destination_id.in_(channel_ids),
                Clip.published_at.isnot(None),
                Clip.youtube_short_id.isnot(None),
            )
            .group_by(Clip.publish_destination_id)
        )
        for d_id, ts in clip_success_rows.all():
            if ts and (d_id not in last_success_map or ts > last_success_map[d_id]):
                last_success_map[d_id] = ts

        pt_err_rows = await db.execute(
            select(PublishTarget.destination_id, PublishTarget.error_message, PublishTarget.updated_at)
            .where(
                PublishTarget.destination_id.in_(channel_ids),
                PublishTarget.status.in_(["failed", "manual_review"]),
                PublishTarget.error_message.isnot(None),
            )
            .order_by(PublishTarget.updated_at.desc())
        )
        for d_id, err_msg, err_ts in pt_err_rows.all():
            if d_id not in last_error_map and err_msg:
                last_error_map[d_id] = (err_msg, err_ts)

        clip_err_rows = await db.execute(
            select(Clip.publish_destination_id, Clip.publish_error, Clip.publish_completed_at)
            .where(
                Clip.publish_destination_id.in_(channel_ids),
                Clip.publish_status.in_(["failed", "manual_review"]),
                Clip.publish_error.isnot(None),
            )
            .order_by(Clip.created_at.desc())
        )
        for d_id, err_msg, err_ts in clip_err_rows.all():
            if d_id not in last_error_map and err_msg:
                last_error_map[d_id] = (err_msg, err_ts)

        mapping_counts = await db.execute(
            select(ChannelDestination.destination_channel_id, func.count(ChannelDestination.id))
            .where(ChannelDestination.destination_channel_id.in_(channel_ids))
            .group_by(ChannelDestination.destination_channel_id)
        )
        for d_id, cnt in mapping_counts.all():
            mapped_sources_count_map[d_id] = int(cnt or 0)

    destinations = []
    for c in channels:
        is_auth = check_channel_authorization(c.youtube_channel_id)
        auth_meta = get_destination_auth_metadata(
            c.youtube_channel_id,
            c.channel_url,
            c.channel_name,
            bool(c.is_default_destination),
        )
        upload_perm = auth_meta["upload_permission_status"]
        if is_auth and upload_perm != "missing_scope":
            upload_perm = "granted"
        elif not c.is_active and upload_perm == "missing":
            upload_perm = "revoked"

        # Determine connection status
        if not c.is_active:
            conn_status = "disconnected"
        elif is_auth and upload_perm == "granted":
            conn_status = "connected"
        else:
            conn_status = "needs_reauth"

        active_outro_data = None
        if c.active_outro and c.active_outro.is_active:
            active_outro_data = serialize_outro(c.active_outro, c.id).model_dump()

        last_ok = last_success_map.get(c.id)
        last_err_tuple = last_error_map.get(c.id)
        last_err = last_err_tuple[0] if last_err_tuple else None
        last_err_at = last_err_tuple[1].isoformat() if (last_err_tuple and last_err_tuple[1]) else None

        destinations.append({
            "id": c.id,
            "youtube_channel_id": c.youtube_channel_id,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "thumbnail_url": c.thumbnail_url,
            "google_account_identity": auth_meta["google_account_identity"],
            "is_destination": c.is_destination,
            "is_default_destination": c.is_default_destination,
            "is_active": c.is_active,
            "is_authorized": is_auth,
            "upload_permission_status": upload_perm,
            "status": conn_status,
            "ready_for_publishing": bool(c.is_active and is_auth and c.is_destination and upload_perm == "granted"),
            "has_outro": active_outro_data is not None,
            "outro_status": "configured" if active_outro_data is not None else "none",
            "active_outro": active_outro_data,
            "mapped_sources_count": mapped_sources_count_map.get(c.id, 0),
            "last_successful_upload": last_ok.isoformat() if last_ok else None,
            "last_publishing_error": last_err,
            "last_publishing_error_at": last_err_at,
            "publishing_settings": c.publishing_settings,
            "cached_stats": c.cached_stats,
            "is_test": bool(c.is_test),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return destinations


# ─── Individual Channel Operations ───────────────────────────────────────────

@router.get("/{channel_id}/stats")
async def get_channel_stats(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Lightweight endpoint returning cached channel statistics, connection status,
    and rate-limit cooldown info without disk credential scanning.
    """
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
            Channel.is_test == False,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    is_auth = check_channel_authorization(ch.youtube_channel_id)
    if not ch.is_active:
        conn_status = "disconnected"
    elif is_auth:
        conn_status = "connected"
    else:
        conn_status = "needs_reauth"

    cooldown_remaining = _get_cooldown_remaining(ch.cached_stats, cooldown_seconds=CHANNEL_STATS_COOLDOWN_SECONDS)

    return {
        "channel_id": ch.id,
        "youtube_channel_id": ch.youtube_channel_id,
        "channel_name": ch.channel_name,
        "status": conn_status,
        "is_authorized": is_auth,
        "is_default_destination": ch.is_default_destination,
        "cached_stats": ch.cached_stats,
        "cooldown_remaining_seconds": cooldown_remaining,
        "can_refresh": cooldown_remaining == 0,
    }


@router.post("/{channel_id}/refresh")
async def refresh_channel_stats(
    channel_id: str,
    force: bool = Query(False, description="Bypass the 60-second rate-limit cooldown"),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh channel analytics and bounded Shorts scan from YouTube Data API v3.
    Updates cached_stats for this channel only. Preserves old stats if refresh fails.
    Enforces a 60-second cooldown rate limit unless force=True to conserve YouTube API quota.
    Protects the async event loop by offloading synchronous Google client calls to a worker thread.
    Coalesces concurrent requests using an async per-channel mutex lock.
    """
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
            Channel.is_test == False,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    # Check authorization
    is_auth = check_channel_authorization(ch.youtube_channel_id)
    if not is_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Channel '{ch.channel_name}' ({ch.youtube_channel_id}) is not authorized. Re-authentication required.",
        )

    # Check rate limit cooldown if not forced
    cooldown_remaining = _get_cooldown_remaining(ch.cached_stats, cooldown_seconds=CHANNEL_STATS_COOLDOWN_SECONDS)
    if not force and cooldown_remaining > 0 and ch.cached_stats:
        return {
            "status": "cached",
            "rate_limited": True,
            "cooldown_remaining_seconds": cooldown_remaining,
            "message": f"Channel statistics were refreshed recently. Cooldown active for {cooldown_remaining}s (pass force=true to bypass).",
            "channel_id": ch.id,
            "youtube_channel_id": ch.youtube_channel_id,
            "cached_stats": ch.cached_stats,
        }

    # Acquire channel in-flight lock to coalesce concurrent requests
    lock = await _get_channel_refresh_lock(ch.youtube_channel_id)
    async with lock:
        # Re-check cooldown after acquiring lock in case another coroutine just refreshed
        await db.refresh(ch)
        if not force:
            cooldown_remaining = _get_cooldown_remaining(ch.cached_stats, cooldown_seconds=CHANNEL_STATS_COOLDOWN_SECONDS)
            if cooldown_remaining > 0 and ch.cached_stats:
                return {
                    "status": "cached",
                    "rate_limited": True,
                    "cooldown_remaining_seconds": cooldown_remaining,
                    "message": f"Channel statistics were refreshed recently. Cooldown active for {cooldown_remaining}s (pass force=true to bypass).",
                    "channel_id": ch.id,
                    "youtube_channel_id": ch.youtube_channel_id,
                    "cached_stats": ch.cached_stats,
                }

        try:
            # Rule 12: Offload synchronous blocking YouTube API calls to worker thread
            stats = await asyncio.to_thread(fetch_channel_analytics, ch.youtube_channel_id)
            ch.cached_stats = stats
            await db.commit()
            await db.refresh(ch)
            return {
                "status": "success",
                "rate_limited": False,
                "cooldown_remaining_seconds": CHANNEL_STATS_COOLDOWN_SECONDS,
                "channel_id": ch.id,
                "youtube_channel_id": ch.youtube_channel_id,
                "cached_stats": stats,
            }
        except Exception as e:
            # Preserve old stats and return meaningful error info
            error_msg = str(e)
            if ch.cached_stats:
                updated_cached = dict(ch.cached_stats)
                updated_cached["status"] = "stale"
                updated_cached["warning_metadata"] = f"Refresh failed: {error_msg}. Displaying previous cache."
                ch.cached_stats = updated_cached
                await db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch live statistics from YouTube: {error_msg}",
            )


@router.patch("/{channel_id}/settings")
async def update_channel_publishing_settings(
    channel_id: str,
    body: PublishingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate and save default publishing settings for a destination channel.
    Settings apply to future uploads from ClipForge without mutating published videos.
    """
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
            Channel.is_test == False,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    # Parse and validate incoming settings
    update_data = body.model_dump(exclude_unset=True)

    # Clean tags if list
    if "default_tags" in update_data and isinstance(update_data["default_tags"], list):
        update_data["default_tags"] = ", ".join(update_data["default_tags"])

    # Update channel-level columns if provided
    if "watermark_url" in update_data:
        ch.watermark_url = update_data["watermark_url"]
    if "brand_color_primary" in update_data:
        ch.brand_color_primary = update_data["brand_color_primary"]
    if "brand_logo_position" in update_data:
        ch.brand_logo_position = update_data["brand_logo_position"]

    # Merge into publishing_settings
    current_settings = dict(ch.publishing_settings or {})
    current_settings.update(update_data)
    ch.publishing_settings = current_settings

    await db.commit()
    await db.refresh(ch)

    return {
        "status": "success",
        "channel_id": ch.id,
        "youtube_channel_id": ch.youtube_channel_id,
        "publishing_settings": ch.publishing_settings,
    }


@router.post("/{channel_id}/set-default")
async def set_default_channel_destination(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Transactionally designate the selected channel as the primary default destination.
    Guarantees exactly one active destination is marked as default.
    """
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
            Channel.is_test == False,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    if not ch.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel '{ch.channel_name}' is disconnected and cannot be set as default.",
        )

    # Check authorization
    is_auth = check_channel_authorization(ch.youtube_channel_id)
    if not is_auth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel '{ch.channel_name}' is not authorized. Authorize before setting as default.",
        )

    # 1. Clear all existing defaults
    await db.execute(
        update(Channel)
        .where(Channel.is_default_destination == True)
        .values(is_default_destination=False, default_destination_expires_at=None)
    )

    # 2. Set target channel as default
    ch.is_default_destination = True
    await db.commit()
    await db.refresh(ch)

    return {
        "status": "success",
        "default_channel_id": ch.id,
        "youtube_channel_id": ch.youtube_channel_id,
        "channel_name": ch.channel_name,
        "is_default_destination": True,
    }


@router.post("/{channel_id}/disconnect")
async def disconnect_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Disconnect a YouTube channel from publishing.
    - Sets is_active = False.
    - Clears is_default_destination if it was the default.
    - Retains is_destination = True so it never becomes a monitored source channel!
    - Preserves historical clips, videos, jobs, and past publish records.
    - Archives local credential file safely.
    """
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
            Channel.is_test == False,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    ch.is_active = False
    if ch.is_default_destination:
        ch.is_default_destination = False
        ch.default_destination_expires_at = None

    # Preserve ChannelDestination mappings when a destination is disconnected
    # (never silently delete mappings). Only disable auto_publish on source channels
    # that no longer have any active mapped destination remaining.
    mapped_sources_res = await db.execute(
        select(ChannelDestination.source_channel_id).where(
            ChannelDestination.destination_channel_id == ch.id
        )
    )
    mapped_source_ids = [r[0] for r in mapped_sources_res.all()]

    dep_query = select(Channel).where(Channel.is_destination == False)
    if mapped_source_ids:
        dep_query = dep_query.where(
            or_(
                Channel.publish_destination_id == ch.id,
                Channel.publish_destination_id == ch.youtube_channel_id,
                Channel.id.in_(mapped_source_ids),
            )
        )
    else:
        dep_query = dep_query.where(
            or_(
                Channel.publish_destination_id == ch.id,
                Channel.publish_destination_id == ch.youtube_channel_id,
            )
        )

    dep_result = await db.execute(dep_query)
    for dep_ch in dep_result.scalars().all():
        if dep_ch.publish_destination_id in (ch.id, ch.youtube_channel_id):
            dep_ch.publish_destination_id = None
        # Check if dep_ch still has any OTHER active destination in ChannelDestination
        other_active_res = await db.execute(
            select(ChannelDestination.id)
            .join(Channel, Channel.id == ChannelDestination.destination_channel_id)
            .where(
                ChannelDestination.source_channel_id == dep_ch.id,
                ChannelDestination.destination_channel_id != ch.id,
                ChannelDestination.is_default == True,
                Channel.is_destination == True,
                Channel.is_active == True,
            )
            .limit(1)
        )
        has_other_active = other_active_res.scalar_one_or_none() is not None
        if not has_other_active and not dep_ch.publish_destination_id:
            dep_ch.auto_publish = False

    # Archive token file if present on disk
    try:
        token_dir = _resolve_token_dir()
        chan_file = token_dir / f"youtube_token_{ch.youtube_channel_id}.json"
        if chan_file.exists():
            backup_file = token_dir / f"youtube_token_{ch.youtube_channel_id}.disconnected.json"
            chan_file.replace(backup_file)
    except Exception as e:
        print(f"[disconnect_channel] Token file archive note: {e}")

    await db.commit()
    await db.refresh(ch)

    return {
        "status": "disconnected",
        "channel_id": ch.id,
        "youtube_channel_id": ch.youtube_channel_id,
        "channel_name": ch.channel_name,
        "is_active": False,
        "is_default_destination": False,
        "message": "Channel disconnected. Historical publishing records, clips, and jobs remain preserved.",
    }


@router.delete(
    "/{channel_id}",
    summary="Permanently remove a destination channel record",
    status_code=status.HTTP_200_OK,
)
async def delete_destination_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a YouTube destination channel record.

    Allowed conditions (must meet at least one):
      - Channel has is_test = True (test/fixture channels).
      - Channel is disconnected (is_active = False) AND has zero PublishTarget records.

    Safety rules:
      - Cascades deletion of ChannelDestination mappings and DestinationOutro records.
      - Clears publish_destination_id on any source channels pointing to this channel.
      - Archives token file if present on disk.
      - Never deletes channels that have real publishing history (PublishTarget rows).
    """
    result = await db.execute(
        select(Channel).where(
            (Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id),
            Channel.is_destination == True,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    # Deactivate if active
    if ch.is_active:
        ch.is_active = False

    channel_name = ch.channel_name
    youtube_channel_id = ch.youtube_channel_id

    # 0. Delete associated PublishTarget records (cascade)
    pt_res = await db.execute(
        select(PublishTarget).where(
            (PublishTarget.destination_id == ch.id)
            | (PublishTarget.destination_id == ch.youtube_channel_id)
        )
    )
    for pt in pt_res.scalars().all():
        await db.delete(pt)

    # Clear publish_destination_id on clips pointing to this channel
    clip_res = await db.execute(
        select(Clip).where(
            (Clip.publish_destination_id == ch.id)
            | (Clip.publish_destination_id == ch.youtube_channel_id)
        )
    )
    for c in clip_res.scalars().all():
        c.publish_destination_id = None

    # 1. Delete ChannelDestination mappings (cascade)
    cd_res = await db.execute(
        select(ChannelDestination).where(
            (ChannelDestination.destination_channel_id == ch.id)
            | (ChannelDestination.source_channel_id == ch.id)
        )
    )
    for cd in cd_res.scalars().all():
        await db.delete(cd)

    # 2. Delete DestinationOutro records
    outro_res = await db.execute(
        select(DestinationOutro).where(DestinationOutro.channel_id == ch.id)
    )
    for outro in outro_res.scalars().all():
        await db.delete(outro)

    # 3. Clear publish_destination_id on source channels pointing here
    src_res = await db.execute(
        select(Channel).where(
            (Channel.publish_destination_id == ch.id)
            | (Channel.publish_destination_id == ch.youtube_channel_id),
            Channel.is_destination == False,
        )
    )
    for src in src_res.scalars().all():
        src.publish_destination_id = None
        src.auto_publish = False

    # 4. Archive or delete token file on disk
    try:
        token_dir = _resolve_token_dir()
        chan_file = token_dir / f"youtube_token_{youtube_channel_id}.json"
        disc_file = token_dir / f"youtube_token_{youtube_channel_id}.disconnected.json"
        for f in (chan_file, disc_file):
            if f.exists():
                f.unlink()
    except Exception as e:
        print(f"[delete_destination_channel] Token file cleanup note: {e}")

    # 5. Delete the channel record itself
    await db.delete(ch)
    await db.commit()

    return {
        "status": "deleted",
        "channel_id": channel_id,
        "youtube_channel_id": youtube_channel_id,
        "channel_name": channel_name,
        "message": f"Channel '{channel_name}' has been permanently removed.",
    }


# ─── Channel Outro Operations ────────────────────────────────────────────────

@router.post(
    "/{channel_id}/outro",
    response_model=OutroUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and configure destination channel outro",
)
async def upload_destination_outro(
    channel_id: str,
    file: UploadFile = File(..., description="Outro media file (MP4 video or PNG/JPEG image)"),
    outro_type: str = Form(..., description="Type of outro: 'video' or 'image'"),
    duration_seconds: float | None = Form(
        None, description="Display duration for image outro (seconds, 0.5 - 15.0). Ignored for video."
    ),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    if not ch.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel '{ch.channel_name}' is disconnected. Outros cannot be configured for inactive channels.",
        )

    normalized_type = outro_type.strip().lower()
    if normalized_type not in ("video", "image"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid outro_type '{outro_type}'. Must be 'video' or 'image'.",
        )

    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded or filename is missing.",
        )

    ext = Path(file.filename).suffix.lower()
    allowed_video_exts = {".mp4", ".mov", ".mkv", ".webm"}
    allowed_image_exts = {".png", ".jpg", ".jpeg", ".webp"}

    if normalized_type == "video" and ext not in allowed_video_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video extension '{ext}'. Allowed formats: {', '.join(sorted(allowed_video_exts))}",
        )
    if normalized_type == "image" and ext not in allowed_image_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image extension '{ext}'. Allowed formats: {', '.join(sorted(allowed_image_exts))}",
        )

    parsed_duration = duration_seconds
    if normalized_type == "image":
        if parsed_duration is None:
            parsed_duration = 3.0
        elif parsed_duration < 0.5 or parsed_duration > 15.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image outro duration must be between 0.5 and 15.0 seconds (got {parsed_duration}).",
            )

    try:
        outro_record = await save_destination_outro(
            channel=ch,
            file=file,
            outro_type=normalized_type,
            duration_seconds=parsed_duration,
            db=db,
        )
    except InvalidOutroError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Outro media validation failed: {str(err)}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save destination outro: {str(err)}",
        )

    return OutroUploadResponse(
        status="success",
        message="Outro successfully uploaded and configured",
        channel_id=ch.id,
        outro=serialize_outro(outro_record, ch.id),
    )


@router.get(
    "/{channel_id}/outro",
    response_model=OutroResponse,
    summary="Get active destination outro metadata",
)
async def get_destination_outro(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    if not ch.active_outro_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active outro configured for channel '{ch.channel_name}'.",
        )

    outro_record = await get_active_destination_outro(channel_id=ch.id, db=db)
    if not outro_record or not outro_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active outro for channel '{ch.channel_name}' was not found.",
        )

    return OutroResponse(
        status="success",
        channel_id=ch.id,
        outro=serialize_outro(outro_record, ch.id),
    )


@router.patch(
    "/{channel_id}/outro",
    response_model=OutroResponse,
    summary="Update active image outro display duration",
)
async def update_destination_outro_endpoint(
    channel_id: str,
    body: OutroUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    if not ch.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel '{ch.channel_name}' is disconnected.",
        )

    outro_record = await get_active_destination_outro(channel_id=ch.id, db=db)
    if not outro_record or not outro_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active outro configured for channel '{ch.channel_name}'.",
        )

    if outro_record.outro_type != "image":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image outros support configurable display duration.",
        )

    outro_record.duration_seconds = round(float(body.duration_seconds), 2)
    outro_record.version = int(outro_record.version or 1) + 1
    outro_record.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(outro_record)

    return OutroResponse(
        status="success",
        channel_id=ch.id,
        outro=serialize_outro(outro_record, ch.id),
    )


@router.delete(
    "/{channel_id}/outro",
    response_model=OutroDeleteResponse,
    summary="Remove active outro from destination channel",
)
async def delete_destination_outro_endpoint(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    if not ch.active_outro_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active outro configured for channel '{ch.channel_name}'.",
        )

    await remove_destination_outro(channel=ch, db=db)

    return OutroDeleteResponse(
        status="success",
        channel_id=ch.id,
        message=f"Outro successfully removed from channel '{ch.channel_name}'.",
    )


@router.get(
    "/{channel_id}/outro/preview",
    summary="Stream outro media asset for in-browser playback",
)
async def preview_destination_outro(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(
            ((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)),
            Channel.is_destination == True,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publishing destination channel '{channel_id}' not found.",
        )

    if not ch.active_outro_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active outro configured for channel '{ch.channel_name}'.",
        )

    outro_record = await get_active_destination_outro(channel_id=ch.id, db=db)
    if not outro_record or not outro_record.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outro asset record missing for channel '{ch.channel_name}'.",
        )

    try:
        safe_path = resolve_safe_outro_path(outro_record.file_path)
    except InvalidOutroError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outro file does not exist on disk.",
        )

    if outro_record.outro_type == "video":
        media_type = "video/mp4"
    elif outro_record.outro_type == "image":
        suffix = safe_path.suffix.lower()
        media_type = "image/png" if suffix == ".png" else "image/jpeg"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(safe_path),
        media_type=media_type,
        filename=outro_record.original_filename or safe_path.name,
    )

