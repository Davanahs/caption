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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.models import Channel
from backend.core.config import settings
from backend.services.publisher import (
    get_oauth_url,
    exchange_code_for_token,
    check_channel_authorization,
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
        select(Channel).where(Channel.youtube_channel_id == token_result["channel_id"])
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

    return {
        "status": "connected",
        "channel": {
            "id": db_ch.id if db_ch else token_result.get("id"),
            "youtube_channel_id": token_result["channel_id"],
            "channel_name": token_result.get("title") or (db_ch.channel_name if db_ch else ""),
            "thumbnail_url": db_ch.thumbnail_url if db_ch else token_result.get("thumbnail_url"),
            "is_default_destination": db_ch.is_default_destination if db_ch else True,
            "is_authorized": True,
        },
    }


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
    - Returns cached statistics, publishing settings, and connection status.
    """
    # 1. Sync credentials on disk
    sync_authorized_destinations()

    # 2. Query destinations
    query = select(Channel).where(Channel.is_destination == True)
    if not include_test:
        query = query.where(Channel.is_test == False)

    result = await db.execute(
        query.order_by(Channel.is_default_destination.desc(), Channel.created_at.asc())
    )
    channels = result.scalars().all()

    destinations = []
    for c in channels:
        is_auth = check_channel_authorization(c.youtube_channel_id)
        
        # Determine status
        if not c.is_active:
            conn_status = "disconnected"
        elif is_auth:
            conn_status = "connected"
        else:
            conn_status = "needs_reauth"

        destinations.append({
            "id": c.id,
            "youtube_channel_id": c.youtube_channel_id,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "thumbnail_url": c.thumbnail_url,
            "is_destination": c.is_destination,
            "is_default_destination": c.is_default_destination,
            "is_active": c.is_active,
            "is_authorized": is_auth,
            "status": conn_status,
            "publishing_settings": c.publishing_settings,
            "cached_stats": c.cached_stats,
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

    # Ensure every dependent source profile can no longer auto-publish using the disconnected destination
    dep_result = await db.execute(
        select(Channel).where(
            Channel.is_destination == False,
            (Channel.publish_destination_id == ch.id) | (Channel.publish_destination_id == ch.youtube_channel_id),
        )
    )
    for dep_ch in dep_result.scalars().all():
        dep_ch.auto_publish = False
        dep_ch.publish_destination_id = None

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
