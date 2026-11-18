"""API Routes — YouTube Publishing"""
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Body, Response, status
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, delete
from pydantic import BaseModel
from backend.models.database import get_db
from backend.models.models import Clip, Channel, DestinationOutro, PublishStatus, PublishTarget, VideoMetadata
from backend.core.config import settings

router = APIRouter(prefix="/api/publish", tags=["publish"])


class PublishRequest(BaseModel):
    clip_id: str
    title: str | None = None
    description: str | None = None
    privacy: str = "private"
    scheduled_at: str | None = None
    made_for_kids: bool = False
    age_restricted: bool = False
    tags: str | None = None
    category: str = "22"
    license: str = "youtube"
    destination_channel_id: str | None = None
    destination_ids: list[str] | None = None
    force: bool = False


class ClipDestinationsUpdateRequest(BaseModel):
    destination_ids: list[str]


class OAuthCallbackRequest(BaseModel):
    # Either provide the raw authorization `code` or the full redirect URL
    # that Google redirected to (e.g. "http://localhost:8080/?code=...&state=...").
    code: str | None = None
    redirect_url: str | None = None


# ─── NEW: Save AI-generated metadata ─────────────────────────────────────────

@router.get("/metadata/{video_id}")
async def get_metadata(video_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch stored AI metadata for a video (used to auto-fill publish form)."""
    result = await db.execute(select(VideoMetadata).where(VideoMetadata.video_id == video_id))
    meta = result.scalar_one_or_none()
    if not meta:
        return {}  # Return empty dict — frontend treats this as "no metadata saved yet"
    return {
        "title": meta.title,
        "description": meta.description,
        "tags": meta.tags.split(",") if meta.tags else [],
        "hashtags": meta.hashtags.split(",") if meta.hashtags else [],
        "pinned_comment": meta.pinned_comment,
    }


@router.post("/metadata/{video_id}")

async def save_metadata(
    video_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Upsert AI-generated (or user-edited) metadata for a video."""
    result = await db.execute(select(VideoMetadata).where(VideoMetadata.video_id == video_id))
    existing = result.scalar_one_or_none()

    tags_str = (
        ",".join(payload.get("tags", []))
        if isinstance(payload.get("tags"), list)
        else payload.get("tags", "")
    )
    hashtags_str = (
        ",".join(payload.get("hashtags", []))
        if isinstance(payload.get("hashtags"), list)
        else payload.get("hashtags", "")
    )

    if existing:
        existing.title = payload.get("title", existing.title)
        existing.description = payload.get("description", existing.description)
        existing.tags = tags_str or existing.tags
        existing.hashtags = hashtags_str or existing.hashtags
        existing.pinned_comment = payload.get("pinned_comment", existing.pinned_comment)
    else:
        meta = VideoMetadata(
            video_id=video_id,
            title=payload.get("title", "Untitled"),
            description=payload.get("description", ""),
            tags=tags_str,
            hashtags=hashtags_str,
            pinned_comment=payload.get("pinned_comment"),
        )
        db.add(meta)

    await db.commit()
    return {"status": "saved", "video_id": video_id}


# ─── Canonical Phase 3.2: Clip Metadata Publishing Editor ────────────────────

VALID_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
}

VALID_PRIVACY = {"public", "unlisted", "private"}
VALID_LICENSES = {"youtube", "creativeCommon"}


class ClipMetadataUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | str | None = None
    category: str | None = None
    license: str | None = None
    privacy: str | None = None
    made_for_kids: bool | None = None
    age_restricted: bool | None = None
    pinned_comment: str | None = None
    publish_destination_id: str | None = None


@router.get("/clips/{clip_id}/metadata")
async def get_clip_publish_metadata(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch stored publishing metadata for a clip."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    tags = []
    if clip.tags:
        if clip.tags.startswith("["):
            try:
                import json
                tags = json.loads(clip.tags)
            except Exception:
                tags = [t.strip() for t in clip.tags.split(",") if t.strip()]
        else:
            tags = [t.strip() for t in clip.tags.split(",") if t.strip()]

    category = clip.category or "22"
    if clip.video_id:
        try:
            from backend.services.source_metadata_engine import load_persisted_source_metadata
            source_meta = load_persisted_source_metadata(clip.video_id)
            if source_meta:
                if not tags and source_meta.seo_tags:
                    tags = list(source_meta.seo_tags)
                if (not clip.category or clip.category == "22") and source_meta.youtube_category_id:
                    category = source_meta.youtube_category_id
        except Exception:
            pass

    return {
        "id": clip.id,
        "video_id": clip.video_id,
        "title": clip.title,
        "description": clip.description or "",
        "tags": tags,
        "category": category,
        "license": clip.license or "youtube",
        "privacy": clip.privacy or "private",
        "made_for_kids": clip.made_for_kids if clip.made_for_kids is not None else False,
        "age_restricted": clip.age_restricted if clip.age_restricted is not None else False,
        "pinned_comment": clip.pinned_comment or "",
        "publish_destination_id": clip.publish_destination_id,
        "scheduled_at": clip.scheduled_at.isoformat() if clip.scheduled_at else None,
        "publish_status": clip.publish_status,
        "duration": clip.duration,
        "metadata_status": clip.metadata_status or "ready",
    }


@router.patch("/clips/{clip_id}/metadata")
async def update_clip_publish_metadata(
    clip_id: str,
    body: ClipMetadataUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update publishing metadata for a clip with strict server-side validation.
    Preserves omitted fields (partial patch semantics).
    """
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Disallow editing of already published clips
    if clip.publish_status == PublishStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="Cannot edit metadata of an already published clip.")

    if body.title is not None:
        title_clean = body.title.strip()
        if not title_clean:
            raise HTTPException(status_code=422, detail="Title cannot be empty")
        if len(title_clean) > 100:
            raise HTTPException(status_code=422, detail="Title cannot exceed 100 characters")
        clip.title = title_clean

    if body.description is not None:
        if len(body.description) > 5000:
            raise HTTPException(status_code=422, detail="Description cannot exceed 5000 characters")
        clip.description = body.description

    if body.tags is not None:
        raw_tags = body.tags
        if isinstance(raw_tags, str):
            tag_list = [t.strip().lstrip("#") for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tag_list = [str(t).strip().lstrip("#") for t in raw_tags if str(t).strip()]
        else:
            raise HTTPException(status_code=422, detail="Tags must be a list of strings or comma-separated string")
        
        if len(tag_list) > 50:
            raise HTTPException(status_code=422, detail="Tags cannot exceed 50 items")
        clip.tags = ",".join(tag_list)

    if body.category is not None:
        if body.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=422, 
                detail=f"Invalid YouTube category ID: '{body.category}'. Valid categories: {list(VALID_CATEGORIES.keys())}"
            )
        clip.category = body.category

    if body.license is not None:
        if body.license not in VALID_LICENSES:
            raise HTTPException(
                status_code=422, 
                detail=f"Invalid license: '{body.license}'. Must be one of: {sorted(list(VALID_LICENSES))}"
            )
        clip.license = body.license

    if body.privacy is not None:
        if body.privacy not in VALID_PRIVACY:
            raise HTTPException(
                status_code=422, 
                detail=f"Invalid privacy: '{body.privacy}'. Must be one of: {sorted(list(VALID_PRIVACY))}"
            )
        clip.privacy = body.privacy

    if body.made_for_kids is not None:
        clip.made_for_kids = bool(body.made_for_kids)

    if body.age_restricted is not None:
        clip.age_restricted = bool(body.age_restricted)

    if body.pinned_comment is not None:
        if len(body.pinned_comment) > 200:
            raise HTTPException(status_code=422, detail="Pinned comment cannot exceed 200 characters")
        clip.pinned_comment = body.pinned_comment

    if "publish_destination_id" in body.model_fields_set:
        if not body.publish_destination_id:
            clip.publish_destination_id = None
        else:
            from backend.models.models import Channel
            dest_res = await db.execute(
                select(Channel).where(Channel.id == body.publish_destination_id, Channel.is_destination == True)
            )
            if not dest_res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Invalid destination channel: not found or not an authorized destination")
            clip.publish_destination_id = body.publish_destination_id

    clip.metadata_status = "ready"
    await db.commit()
    await db.refresh(clip)

    tags = [t.strip() for t in clip.tags.split(",") if t.strip()] if clip.tags else []
    return {
        "status": "success",
        "message": "Clip metadata updated successfully",
        "metadata": {
            "id": clip.id,
            "video_id": clip.video_id,
            "title": clip.title,
            "description": clip.description or "",
            "tags": tags,
            "category": clip.category or "22",
            "license": clip.license or "youtube",
            "privacy": clip.privacy or "private",
            "made_for_kids": clip.made_for_kids if clip.made_for_kids is not None else False,
            "age_restricted": clip.age_restricted if clip.age_restricted is not None else False,
            "pinned_comment": clip.pinned_comment or "",
            "publish_destination_id": clip.publish_destination_id,
            "scheduled_at": clip.scheduled_at.isoformat() if clip.scheduled_at else None,
            "publish_status": clip.publish_status,
            "duration": clip.duration,
            "metadata_status": clip.metadata_status,
        }
    }


# ─── EXISTING ROUTES (unchanged) ──────────────────────────────────────────────

@router.get("/destinations")
async def get_destinations(include_test: bool = False, db: AsyncSession = Depends(get_db)):
    """
    Get all connected YouTube publishing destinations.
    - Reconciles authorized YouTube credentials on disk into the database.
    - Excludes automated test fixtures by default (include_test=False).
    - Verifies credential validity for each channel and reports truthful authorization status.
    """
    from backend.models.models import Channel
    from backend.services.publisher import sync_authorized_destinations, check_channel_authorization

    # Synchronize any token files on disk
    sync_authorized_destinations()

    query = select(Channel).where(Channel.is_destination == True)
    if not include_test:
        query = query.where(Channel.is_test == False)

    result = await db.execute(
        query.order_by(Channel.is_default_destination.desc(), Channel.created_at.asc())
    )
    channels = result.scalars().all()

    outro_ids = [c.active_outro_id for c in channels if getattr(c, "active_outro_id", None)]
    outros_by_id: dict[str, DestinationOutro] = {}
    if outro_ids:
        outro_res = await db.execute(
            select(DestinationOutro).where(DestinationOutro.id.in_(outro_ids), DestinationOutro.is_active == True)
        )
        for o in outro_res.scalars().all():
            outros_by_id[o.id] = o

    destinations = []
    for c in channels:
        is_auth = check_channel_authorization(c.youtube_channel_id)
        outro = outros_by_id.get(c.active_outro_id) if c.active_outro_id else None
        outro_summary = (
            {
                "id": outro.id,
                "outro_type": outro.outro_type,
                "duration_seconds": float(outro.duration_seconds),
                "version": int(outro.version or 1),
                "original_filename": outro.original_filename,
                "preview_url": f"/api/youtube-channels/{c.id}/outro/preview",
            }
            if outro
            else None
        )
        destinations.append({
            "id": c.id,
            "youtube_channel_id": c.youtube_channel_id,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "thumbnail_url": c.thumbnail_url,
            "is_default_destination": c.is_default_destination,
            "default_destination_expires_at": c.default_destination_expires_at.isoformat() if c.default_destination_expires_at else None,
            "is_active": bool(c.is_active),
            "is_authorized": is_auth,
            "status": "disconnected" if not c.is_active else ("connected" if is_auth else "needs_reauth"),
            "ready_for_publishing": bool(c.is_active and is_auth),
            "active_outro_id": outro.id if outro else None,
            "has_outro": outro is not None,
            "outro": outro_summary,
        })

    return destinations


class SetDefaultDestinationRequest(BaseModel):
    channel_id: str
    expires_in_hours: int | None = None


@router.post("/destinations/default")
async def set_default_destination(body: SetDefaultDestinationRequest, db: AsyncSession = Depends(get_db)):
    """Set a specific channel as the default publishing destination with optional expiration."""
    from backend.models.models import Channel
    from sqlalchemy import update
    from datetime import datetime, timedelta, timezone
    
    # Reset all defaults
    await db.execute(
        update(Channel)
        .where(Channel.is_default_destination == True)
        .values(is_default_destination=False, default_destination_expires_at=None)
    )
    
    # Set new default
    result = await db.execute(select(Channel).where(Channel.id == body.channel_id, Channel.is_destination == True))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Destination channel not found")
        
    channel.is_default_destination = True
    if body.expires_in_hours:
        channel.default_destination_expires_at = datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours)
    else:
        channel.default_destination_expires_at = None
        
    await db.commit()
    return {"message": "Default destination updated"}


@router.get("/auth-status")
async def auth_status():
    """Check if YouTube OAuth is configured."""
    from backend.services.publisher import check_auth_status, get_oauth_url
    is_auth = check_auth_status()
    return {
        "authenticated": is_auth,
        "oauth_url": get_oauth_url() if not is_auth else None,
    }


@router.get("/channel-info")
async def channel_info():
    """Get authenticated user's YouTube channel details."""
    from backend.services.publisher import get_channel_info
    try:
        return get_channel_info()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/oauth-url")
async def get_oauth_url_route(response: Response):
    """Generate OAuth URL pointing to the backend callback so no local server is needed."""
    from backend.services.publisher import get_oauth_url
    import secrets
    
    state = secrets.token_urlsafe(32)
    url = get_oauth_url(state=state)
    if not url:
        raise HTTPException(status_code=400, detail="YouTube API credentials not configured in .env")
        
    response = RedirectResponse(url=url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600
    )
    return response


@router.get("/oauth-callback")
async def oauth_callback_get(request: Request):
    """
    Handle Google OAuth redirect via GET. Exchanges code for credentials,
    saves youtube_token.json, then redirects to frontend dashboard.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code in callback")

    expected_state = request.cookies.get("oauth_state")
    if expected_state and state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state (CSRF protection failed)")

    from backend.services.publisher import exchange_code_for_token
    
    # Try the main redirect URI or derive it from request
    redirect_uri = settings.YOUTUBE_OAUTH_REDIRECT_URI
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/api/publish/oauth-callback"

    try:
        channel_info = exchange_code_for_token(code, redirect_uri)
        print(f"[OAuth] GET Callback - YouTube token saved successfully for channel: {channel_info['title']}")
    except Exception as e:
        print(f"[OAuth] GET Callback - Failed to exchange token: {e}")
        # fallback to a generic error redirect or raise
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {e}")
        
    # Redirect user back to frontend settings page
    frontend_origin = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3000"
    response = RedirectResponse(url=f"{frontend_origin}/publish?oauth=success")
    response.delete_cookie("oauth_state")
    return response


@router.post("/oauth-callback")
async def oauth_callback_post(body: OAuthCallbackRequest):
    """
    Accept POSTed JSON containing either `code` or a full `redirect_url` (paste from browser).
    Exchanges the authorization code for tokens and saves them to `youtube_token_{channel_id}.json`.
    """
    print(f"[OAuth] Received request body for oauth callback post. Code present: {bool(body.code)}")
    
    # Extract code from either the code field or a full redirect URL
    code = None
    redirect_uri = settings.YOUTUBE_OAUTH_REDIRECT_URI
    redirect_uris_to_try = [redirect_uri]  
    
    if body.redirect_url:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(body.redirect_url)
        qs = parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        
        base_uri = f"{parsed.scheme}://{parsed.netloc}"
        path_uri = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.path and parsed.path != "/" else base_uri
        
        redirect_uris_to_try = [path_uri, base_uri]
        redirect_uri = path_uri
    elif body.code:
        code = body.code

    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code or redirect_url in request body")

    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="YouTube API credentials not configured in .env")

    from backend.services.publisher import exchange_code_for_token
    
    last_error = None
    for attempt_redirect_uri in redirect_uris_to_try:
        try:
            print(f"[OAuth] Attempting token exchange with redirect_uri: {attempt_redirect_uri}")
            channel_info = exchange_code_for_token(code, attempt_redirect_uri)
            print(f"[OAuth] ✅ YouTube token saved successfully for channel: {channel_info['title']}")
            return {
                "status": "success", 
                "message": f"YouTube authorized successfully as {channel_info['title']}",
                "channel": channel_info
            }
        except Exception as e:
            last_error = str(e)
            print(f"[OAuth] ⚠️ Failed with redirect_uri '{attempt_redirect_uri}': {last_error}")
    
    raise HTTPException(
        status_code=400, 
        detail=f"OAuth token exchange failed: {last_error}"
    )


class RetryPublishRequest(BaseModel):
    force: bool = False


def _resolve_clip_local_path(output_path: str | None) -> Path | None:
    if not output_path or not isinstance(output_path, str):
        return None
    direct = Path(output_path)
    if direct.exists():
        return direct
    try:
        from backend.services.outro_service import resolve_clip_base_video_path
        resolved = resolve_clip_base_video_path(output_path)
        if resolved.exists():
            return resolved
    except Exception:
        pass
    return None


async def _validate_active_destinations(raw_refs: list[str], db: AsyncSession) -> list[Channel]:
    """Validate and resolve canonical Channel objects in request order with zero silent substitution."""
    from backend.services.publisher import check_channel_authorization

    resolved: list[Channel] = []
    seen: set[str] = set()
    for ref in raw_refs:
        if not ref or not isinstance(ref, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid destination channel reference.",
            )
        dest_res = await db.execute(
            select(Channel).where(
                (Channel.id == ref) | (Channel.youtube_channel_id == ref),
                Channel.is_destination == True,
                Channel.is_active == True,
            )
        )
        dest_ch = dest_res.scalar_one_or_none()
        if not dest_ch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid destination channel '{ref}': not found, inactive, or not an authorized destination.",
            )
        if not check_channel_authorization(dest_ch.youtube_channel_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Destination channel '{dest_ch.channel_name}' is not authorized or OAuth credentials are invalid.",
            )
        if dest_ch.id not in seen:
            seen.add(dest_ch.id)
            resolved.append(dest_ch)
    return resolved


async def _serialize_targets_for_clips(clip_ids: list[str], db: AsyncSession) -> dict[str, list[dict]]:
    """Batch-load PublishTarget rows + Channel + active DestinationOutro summaries for clips."""
    out: dict[str, list[dict]] = {cid: [] for cid in clip_ids}
    if not clip_ids:
        return out

    pt_res = await db.execute(
        select(PublishTarget)
        .where(PublishTarget.clip_id.in_(clip_ids))
        .order_by(PublishTarget.created_at.asc())
    )
    targets = pt_res.scalars().all()
    if not targets:
        return out

    dest_ids = list({t.destination_id for t in targets if t.destination_id})
    channels_by_id: dict[str, Channel] = {}
    outros_by_id: dict[str, DestinationOutro] = {}
    if dest_ids:
        ch_res = await db.execute(select(Channel).where(Channel.id.in_(dest_ids)))
        for ch in ch_res.scalars().all():
            channels_by_id[ch.id] = ch

        outro_ids = list({
            ch.active_outro_id
            for ch in channels_by_id.values()
            if getattr(ch, "active_outro_id", None)
        } | {
            t.outro_applied_id
            for t in targets
            if getattr(t, "outro_applied_id", None)
        })
        if outro_ids:
            o_res = await db.execute(select(DestinationOutro).where(DestinationOutro.id.in_(outro_ids)))
            for o in o_res.scalars().all():
                outros_by_id[o.id] = o

    for t in targets:
        ch = channels_by_id.get(t.destination_id)
        active_outro = outros_by_id.get(ch.active_outro_id) if (ch and ch.active_outro_id) else None
        if active_outro and not active_outro.is_active:
            active_outro = None
        applied_outro = outros_by_id.get(t.outro_applied_id) if t.outro_applied_id else None

        active_outro_summary = (
            {
                "id": active_outro.id,
                "outro_type": active_outro.outro_type,
                "duration_seconds": float(active_outro.duration_seconds),
                "version": int(active_outro.version or 1),
                "original_filename": active_outro.original_filename,
                "preview_url": f"/api/youtube-channels/{ch.id}/outro/preview" if ch else None,
            }
            if active_outro
            else None
        )
        out[t.clip_id].append({
            "id": t.id,
            "clip_id": t.clip_id,
            "destination_id": t.destination_id,
            "destination_name": ch.channel_name if ch else "Unknown Destination",
            "destination_youtube_channel_id": ch.youtube_channel_id if ch else None,
            "destination_thumbnail_url": ch.thumbnail_url if ch else None,
            "is_active": bool(ch.is_active) if ch else False,
            "status": t.status,
            "publish_stage": t.publish_stage or t.status,
            "publish_progress": float(t.publish_progress or 0.0),
            "youtube_video_id": t.youtube_video_id,
            "youtube_url": f"https://www.youtube.com/shorts/{t.youtube_video_id}" if t.youtube_video_id else None,
            "error_message": t.error_message,
            "retry_count": int(t.retry_count or 0),
            "privacy": t.privacy or "private",
            "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
            "published_at": t.published_at.isoformat() if t.published_at else None,
            "publish_started_at": t.publish_started_at.isoformat() if t.publish_started_at else None,
            "publish_completed_at": t.publish_completed_at.isoformat() if t.publish_completed_at else None,
            "rendered_video_path": t.rendered_video_path,
            "artifact_storage_key": t.artifact_storage_key,
            "outro_applied_id": t.outro_applied_id,
            "outro_applied_version": int(applied_outro.version) if applied_outro else None,
            "has_outro": active_outro is not None,
            "active_outro": active_outro_summary,
            "preview_url": f"/api/publish/clips/{t.clip_id}/destinations/{t.destination_id}/preview",
            "preview_info_url": f"/api/publish/clips/{t.clip_id}/destinations/{t.destination_id}/preview-info",
        })
    return out


async def _recompute_clip_aggregate_async(clip: Clip, db: AsyncSession) -> list[PublishTarget]:
    """Recompute aggregate Clip publish fields truthfully from its PublishTarget rows."""
    res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    targets = list(res.scalars().all())
    if not targets:
        return []

    done_statuses = {"completed", "published"}
    active_statuses = {"queued", "uploading", "finalizing", "publishing"}
    first_yt = next((t.youtube_video_id for t in targets if t.status in done_statuses and t.youtube_video_id), None)
    if first_yt and not clip.youtube_short_id:
        clip.youtube_short_id = first_yt

    active_targets = [t for t in targets if t.status in active_statuses]
    if active_targets:
        if any(t.status in ("uploading", "finalizing", "publishing") for t in active_targets):
            clip.publish_status = PublishStatus.UPLOADING.value
            clip.publish_stage = "uploading"
        else:
            clip.publish_status = PublishStatus.QUEUED.value
            clip.publish_stage = "queued"
        avg = sum(float(t.publish_progress or 0.0) for t in targets) / max(1, len(targets))
        clip.publish_progress = int(max(0, min(99, round(avg))))
        return targets

    non_cancelled = [t for t in targets if t.status != "cancelled"]
    if any(t.status == "manual_review" for t in targets):
        clip.publish_status = PublishStatus.MANUAL_REVIEW.value
        clip.publish_stage = "manual_review"
    elif non_cancelled and all(t.status in done_statuses for t in non_cancelled):
        clip.publish_status = PublishStatus.PUBLISHED.value
        clip.publish_stage = "published"
        clip.publish_progress = 100
        clip.publish_error = None
    elif not non_cancelled:
        clip.publish_status = PublishStatus.CANCELLED.value
        clip.publish_stage = "cancelled"
        clip.publish_error = "Cancelled by user."
    elif any(t.status == "failed" for t in targets):
        failed = [t for t in targets if t.status == "failed"]
        succeeded = [t for t in targets if t.status in done_statuses]
        clip.publish_status = PublishStatus.FAILED.value
        clip.publish_stage = "failed"
        sample = next((t.error_message for t in failed if t.error_message), "Upload failed")
        if succeeded:
            clip.publish_error = f"{len(succeeded)}/{len(non_cancelled)} destinations succeeded; {len(failed)} failed: {sample}"
        else:
            clip.publish_error = sample
    return targets


@router.post("/publish-now", status_code=status.HTTP_202_ACCEPTED)
async def publish_now(body: PublishRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Upload Studio Phase 3 & Multi-Destination Asynchronous Publishing.
    - Supports single destination_channel_id or multi-destination destination_ids list.
    - Validates eligibility and OAuth credentials for every selected destination before queueing.
    - Creates/updates per-destination PublishTarget rows while skipping already-completed targets idempotently.
    - Commits PostgreSQL transaction first ('queued') before dispatching per-target Celery tasks.
    - Enforces private-by-default privacy policy.
    """
    result = await db.execute(select(Clip).where(Clip.id == body.clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    existing_res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    existing_targets = list(existing_res.scalars().all())
    existing_by_dest = {t.destination_id: t for t in existing_targets}

    if body.destination_ids is not None:
        if len(body.destination_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Publish destination channel is required. Please select an authorized destination.",
            )
        raw_dest_ids = list(dict.fromkeys(body.destination_ids))
    elif body.destination_channel_id:
        raw_dest_ids = [body.destination_channel_id]
    elif existing_targets:
        raw_dest_ids = [t.destination_id for t in existing_targets if t.destination_id]
    elif clip.publish_destination_id:
        raw_dest_ids = [clip.publish_destination_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Publish destination channel is required. Please select an authorized destination.",
        )

    is_republish = (
        clip.publish_status == PublishStatus.DRAFT.value 
        or getattr(body, "force", False)
        or not clip.youtube_short_id
    )

    # Single-destination or legacy already-published check
    done_statuses = {"completed", "published"}
    if not is_republish and body.destination_ids is None and clip.publish_status == PublishStatus.PUBLISHED.value and clip.youtube_short_id:
        if not existing_targets or all(t.status in done_statuses for t in existing_targets):
            response.status_code = status.HTTP_200_OK
            return {
                "status": "published",
                "message": "Clip is already published",
                "youtube_url": f"https://www.youtube.com/shorts/{clip.youtube_short_id}",
                "video_id": clip.youtube_short_id,
            }

    # Manual review gating
    if clip.publish_status == PublishStatus.MANUAL_REVIEW.value and not body.destination_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clip publication is in manual_review state. Automatic publishing is blocked until manual resolution.",
        )

    # Already actively running check when no explicit target override supplied
    if body.destination_ids is None and clip.publish_status in (
        PublishStatus.QUEUED.value, PublishStatus.UPLOADING.value, PublishStatus.FINALIZING.value
    ):
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": clip.publish_status,
            "clip_id": clip.id,
            "task_id": clip.publish_task_id,
            "progress": clip.publish_progress,
            "stage": clip.publish_stage,
            "message": "Publishing operation is already in progress.",
        }

    # Output file validation
    if not _resolve_clip_local_path(clip.output_path):
        raise HTTPException(status_code=400, detail="Clip video file not found on disk")

    # Validate every destination strictly
    resolved_channels = await _validate_active_destinations(raw_dest_ids, db)

    # If user passed destination_ids and ALL of those targets are already published, return 200 cleanly
    if not is_republish and all(
        (d.id in existing_by_dest and existing_by_dest[d.id].status in done_statuses and existing_by_dest[d.id].youtube_video_id)
        for d in resolved_channels
    ):
        first_done = existing_by_dest[resolved_channels[0].id]
        response.status_code = status.HTTP_200_OK
        serialized = await _serialize_targets_for_clips([clip.id], db)
        return {
            "status": "published",
            "message": "Clip is already published to all selected destinations",
            "youtube_url": f"https://www.youtube.com/shorts/{first_done.youtube_video_id}",
            "video_id": first_done.youtube_video_id,
            "targets": serialized.get(clip.id, []),
        }

    # Save metadata attributes to DB record
    selected_privacy = body.privacy if body.privacy in ("public", "unlisted", "private") else "public"
    clip.privacy = selected_privacy
    clip.made_for_kids = body.made_for_kids
    clip.age_restricted = body.age_restricted
    clip.tags = body.tags
    clip.category = body.category
    clip.publish_destination_id = resolved_channels[0].id
    if body.title:
        clip.title = body.title
    if body.description:
        clip.description = body.description

    now = datetime.now(timezone.utc)
    queued_targets: list[PublishTarget] = []
    for dest_ch in resolved_channels:
        pt = existing_by_dest.get(dest_ch.id)
        if not is_republish:
            if pt and pt.status in done_statuses and pt.youtube_video_id:
                continue
        if pt and pt.status in ("queued", "uploading", "finalizing", "publishing"):
            continue
        fresh_suffix = uuid.uuid4().hex[:8]
        idemp = f"pub_{clip.id}_{dest_ch.id}_{fresh_suffix}" if is_republish else (pt.idempotency_key if pt and pt.idempotency_key else f"pub_{clip.id}_{dest_ch.id}")
        if not pt:
            pt = PublishTarget(
                id=str(uuid.uuid4()),
                clip_id=clip.id,
                destination_id=dest_ch.id,
                status="queued",
                privacy=selected_privacy,
                made_for_kids=bool(body.made_for_kids),
                age_restricted=bool(body.age_restricted),
                publish_stage="queued",
                publish_progress=0.0,
                publish_started_at=now,
                idempotency_key=idemp,
                created_at=now,
                updated_at=now,
            )
            db.add(pt)
            existing_by_dest[dest_ch.id] = pt
        else:
            pt.status = "queued"
            pt.publish_stage = "queued"
            pt.publish_progress = 0.0
            pt.privacy = selected_privacy
            pt.made_for_kids = bool(body.made_for_kids)
            pt.age_restricted = bool(body.age_restricted)
            pt.error_message = None
            pt.youtube_video_id = None
            pt.publish_started_at = now
            pt.idempotency_key = idemp
        queued_targets.append(pt)

    # Remove stale pending/draft targets not in the explicit multi-destination selection
    if body.destination_ids is not None:
        selected_ids = {d.id for d in resolved_channels}
        for existing_dest_id, existing_pt in list(existing_by_dest.items()):
            if existing_dest_id not in selected_ids and existing_pt.status in ("pending", "cancelled"):
                await db.delete(existing_pt)

    primary_idemp = queued_targets[0].idempotency_key if queued_targets else f"pub_{clip.id}_{resolved_channels[0].id}_{uuid.uuid4().hex[:8]}"
    clip.publish_idempotency_key = primary_idemp
    if is_republish:
        clip.youtube_short_id = None
    if queued_targets:
        clip.publish_status = PublishStatus.QUEUED.value
        clip.publish_stage = "queued"
        clip.publish_progress = 0
        clip.publish_error = None
        clip.publish_started_at = now

    # Commit PostgreSQL transaction FIRST (Durable PostgreSQL-to-Celery Dispatch)
    await db.commit()
    await db.refresh(clip)
    for pt in queued_targets:
        await db.refresh(pt)

    # Dispatch independent Celery task per queued target
    from backend.tasks.clip_tasks import publish_clip_task
    dispatched_task_ids: list[str] = []
    for pt in queued_targets:
        try:
            task = publish_clip_task.apply_async(
                args=[clip.id],
                kwargs={
                    "channel_id": pt.destination_id,
                    "target_id": pt.id,
                    "privacy": "private",
                },
            )
            t_id = getattr(task, "id", None)
            if isinstance(t_id, str):
                pt.publish_task_id = t_id
                dispatched_task_ids.append(t_id)
                clip.publish_task_id = t_id
        except Exception as exc:
            print(f"[PublishAPI] Celery dispatch warning for target {pt.id}: {exc}. Target remains queued and will be recovered.")

    if dispatched_task_ids:
        await db.commit()

    serialized = await _serialize_targets_for_clips([clip.id], db)
    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "status": "queued",
        "clip_id": clip.id,
        "task_id": clip.publish_task_id,
        "idempotency_key": primary_idemp,
        "targets": serialized.get(clip.id, []),
        "message": f"Publishing queued for {len(queued_targets)} destination(s)",
    }


@router.get("/status/{clip_id}")
async def get_publish_status_route(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Get live publishing status, progress, stage, attempt count, and per-destination targets."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    serialized = await _serialize_targets_for_clips([clip.id], db)
    return {
        "clip_id": clip.id,
        "publish_status": clip.publish_status,
        "publish_progress": clip.publish_progress,
        "publish_stage": clip.publish_stage,
        "publish_attempt": clip.publish_attempt,
        "publish_error": clip.publish_error,
        "youtube_short_id": clip.youtube_short_id,
        "youtube_url": f"https://www.youtube.com/shorts/{clip.youtube_short_id}" if clip.youtube_short_id else None,
        "published_at": clip.published_at.isoformat() if clip.published_at else None,
        "publish_started_at": clip.publish_started_at.isoformat() if clip.publish_started_at else None,
        "publish_task_id": clip.publish_task_id,
        "idempotency_key": clip.publish_idempotency_key,
        "targets": serialized.get(clip.id, []),
    }


@router.post("/clips/{clip_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_publish_clip(clip_id: str, body: RetryPublishRequest = None, db: AsyncSession = Depends(get_db)):
    """
    Retries publishing for a failed or stuck clip (or any non-completed PublishTargets without duplicating succeeded siblings).
    """
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if clip.publish_status == PublishStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="Cannot retry an already published clip.")

    if clip.publish_status in (PublishStatus.QUEUED.value, PublishStatus.UPLOADING.value, PublishStatus.FINALIZING.value):
        raise HTTPException(status_code=409, detail="Publishing is already actively running.")

    force = body.force if body else False
    if clip.publish_status == PublishStatus.MANUAL_REVIEW.value and not force:
        raise HTTPException(
            status_code=400,
            detail="Clip is in manual_review state. Confirm that remote video does not exist or provide force=True to proceed."
        )

    pt_res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    all_targets = list(pt_res.scalars().all())
    retryable_targets = [
        t for t in all_targets
        if t.status in ("failed", "cancelled", "pending", "manual_review")
        and (t.status != "manual_review" or force)
    ]

    now = datetime.now(timezone.utc)
    for t in retryable_targets:
        t.status = "queued"
        t.publish_stage = "queued"
        t.error_message = None
        t.publish_progress = 0.0
        t.publish_started_at = now
        t.idempotency_key = t.idempotency_key or f"pub_{clip.id}_{t.destination_id}"

    clip.publish_status = PublishStatus.QUEUED.value
    clip.publish_stage = "queued"
    clip.publish_error = None
    clip.publish_progress = 0
    clip.publish_started_at = now
    await db.commit()
    await db.refresh(clip)

    from backend.tasks.clip_tasks import publish_clip_task
    try:
        if retryable_targets:
            for t in retryable_targets:
                task = publish_clip_task.apply_async(
                    args=[clip.id],
                    kwargs={
                        "channel_id": t.destination_id,
                        "target_id": t.id,
                        "privacy": t.privacy or clip.privacy or "public",
                        "force": force,
                    },
                )
                if isinstance(getattr(task, "id", None), str):
                    t.publish_task_id = task.id
                    clip.publish_task_id = task.id
        else:
            task = publish_clip_task.apply_async(
                args=[clip.id],
                kwargs={
                    "channel_id": clip.publish_destination_id,
                    "privacy": clip.privacy or "public",
                    "force": force,
                },
            )
            if isinstance(getattr(task, "id", None), str):
                clip.publish_task_id = task.id
        await db.commit()
    except Exception as exc:
        print(f"[PublishAPI] Retry dispatch warning: {exc}")

    return {
        "status": "queued",
        "clip_id": clip.id,
        "task_id": clip.publish_task_id,
        "message": "Retry publication queued successfully."
    }


@router.post("/clips/{clip_id}/cancel")
async def cancel_publish_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Cooperative cancellation of a publishing job across the clip and any non-completed PublishTargets.
    """
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if clip.publish_status == PublishStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="Cannot cancel a publication that has already succeeded.")

    if clip.publish_status == PublishStatus.CANCELLED.value:
        return {"status": "cancelled", "clip_id": clip.id, "message": "Publication already cancelled."}

    pt_res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    all_targets = list(pt_res.scalars().all())
    for t in all_targets:
        if t.status in ("completed", "published", "cancelled"):
            continue
        if t.status in ("queued", "pending", "scheduled", "failed", "manual_review"):
            t.status = "cancelled"
            t.publish_stage = "cancelled"
            t.error_message = "Cancelled by user."
            if t.publish_task_id:
                try:
                    from backend.tasks.celery_app import celery_app
                    celery_app.control.revoke(t.publish_task_id, terminate=True)
                except Exception:
                    pass
        else:
            t.status = "cancelling"
            t.publish_stage = "cancelling"

    if clip.publish_status in (
        PublishStatus.QUEUED.value,
        PublishStatus.DRAFT.value,
        PublishStatus.SCHEDULED.value,
        PublishStatus.FAILED.value,
        PublishStatus.MANUAL_REVIEW.value,
    ):
        clip.publish_status = PublishStatus.CANCELLED.value
        clip.publish_stage = "cancelled"
        clip.publish_error = "Cancelled by user."
        if clip.publish_task_id:
            try:
                from backend.tasks.celery_app import celery_app
                celery_app.control.revoke(clip.publish_task_id, terminate=True)
            except Exception:
                pass
        await db.commit()
        return {"status": "cancelled", "clip_id": clip.id, "message": "Publication cancelled immediately."}

    clip.publish_status = PublishStatus.CANCELLING.value
    clip.publish_stage = "cancelling"
    await db.commit()
    return {
        "status": "cancelling",
        "clip_id": clip.id,
        "message": "Cancellation requested. Worker will halt upload cooperatively."
    }


@router.get("/clips/{clip_id}/targets")
async def get_clip_publish_targets(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Return all destination PublishTarget rows (with outro and preview metadata) for a clip."""
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    serialized = await _serialize_targets_for_clips([clip.id], db)
    targets = serialized.get(clip.id, [])
    return {
        "clip_id": clip.id,
        "publish_status": clip.publish_status,
        "publish_destination_id": clip.publish_destination_id,
        "destination_ids": [t["destination_id"] for t in targets],
        "targets": targets,
    }


@router.put("/clips/{clip_id}/destinations")
async def update_clip_destinations(
    clip_id: str,
    body: ClipDestinationsUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update selected publishing destinations for a clip before publishing.
    - Protects already-published and actively uploading targets from silent deletion.
    - Validates added destinations (active + authorized) before persisting.
    - Supports removing destinations cleanly (including clearing pending destinations with []).
    """
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    raw_dest_ids = list(dict.fromkeys(body.destination_ids or []))
    resolved_channels = await _validate_active_destinations(raw_dest_ids, db) if raw_dest_ids else []
    selected_ids = {c.id for c in resolved_channels}

    existing_res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    existing_targets = list(existing_res.scalars().all())
    existing_by_dest = {t.destination_id: t for t in existing_targets}

    protected_statuses = {"completed", "published", "uploading", "finalizing", "publishing", "cancelling"}
    for t in existing_targets:
        if t.destination_id not in selected_ids and t.status in protected_statuses:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot remove destination '{t.destination_id}' because its publish status is '{t.status}'.",
            )

    for t in existing_targets:
        if t.destination_id not in selected_ids:
            await db.delete(t)

    now = datetime.now(timezone.utc)
    for ch in resolved_channels:
        if ch.id not in existing_by_dest:
            db.add(PublishTarget(
                id=str(uuid.uuid4()),
                clip_id=clip.id,
                destination_id=ch.id,
                status="pending",
                privacy="private",
                publish_stage="pending",
                publish_progress=0.0,
                idempotency_key=f"pub_{clip.id}_{ch.id}",
                created_at=now,
                updated_at=now,
            ))

    await db.flush()
    remaining_res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    remaining = list(remaining_res.scalars().all())
    if resolved_channels:
        clip.publish_destination_id = resolved_channels[0].id
    elif not remaining:
        clip.publish_destination_id = None

    await _recompute_clip_aggregate_async(clip, db)
    await db.commit()

    serialized = await _serialize_targets_for_clips([clip.id], db)
    targets = serialized.get(clip.id, [])
    return {
        "status": "updated",
        "clip_id": clip.id,
        "destination_ids": [t["destination_id"] for t in targets],
        "targets": targets,
    }


@router.post("/targets/{target_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_publish_target(
    target_id: str,
    body: RetryPublishRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Retry a single failed/cancelled/manual_review PublishTarget without re-publishing sibling destinations.
    """
    t_res = await db.execute(select(PublishTarget).where(PublishTarget.id == target_id))
    target = t_res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Publish target not found")

    if target.status in ("completed", "published"):
        raise HTTPException(status_code=400, detail="Cannot retry an already published destination target.")

    if target.status in ("queued", "uploading", "finalizing", "publishing"):
        raise HTTPException(status_code=409, detail="Publishing for this destination is already actively running.")

    force = body.force if body else False
    if target.status == "manual_review" and not force:
        raise HTTPException(
            status_code=400,
            detail="Target is in manual_review state. Confirm remote state or pass force=True to retry.",
        )

    c_res = await db.execute(select(Clip).where(Clip.id == target.clip_id))
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Parent clip not found")

    if not _resolve_clip_local_path(clip.output_path):
        raise HTTPException(status_code=400, detail="Clip video file not found on disk")

    await _validate_active_destinations([target.destination_id], db)

    now = datetime.now(timezone.utc)
    target.status = "queued"
    target.publish_stage = "queued"
    target.publish_progress = 0.0
    target.error_message = None
    target.publish_started_at = now
    target.privacy = target.privacy or clip.privacy or "public"
    target.idempotency_key = target.idempotency_key or f"pub_{target.clip_id}_{target.destination_id}"

    await _recompute_clip_aggregate_async(clip, db)
    await db.commit()
    await db.refresh(target)

    from backend.tasks.clip_tasks import publish_clip_task
    try:
        task = publish_clip_task.apply_async(
            args=[target.clip_id],
            kwargs={
                "channel_id": target.destination_id,
                "target_id": target.id,
                "privacy": target.privacy or "public",
                "force": force,
            },
        )
        t_id = getattr(task, "id", None)
        if isinstance(t_id, str):
            target.publish_task_id = t_id
            await db.commit()
    except Exception as exc:
        print(f"[PublishAPI] Target retry dispatch warning: {exc}")

    serialized = await _serialize_targets_for_clips([target.clip_id], db)
    target_payload = next((t for t in serialized.get(target.clip_id, []) if t["id"] == target.id), None)
    return {
        "status": "queued",
        "target_id": target.id,
        "clip_id": target.clip_id,
        "destination_id": target.destination_id,
        "task_id": target.publish_task_id,
        "target": target_payload,
        "message": "Destination target retry queued successfully.",
    }


@router.post("/targets/{target_id}/cancel")
async def cancel_publish_target(target_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a single destination PublishTarget independently without cancelling sibling destinations."""
    t_res = await db.execute(select(PublishTarget).where(PublishTarget.id == target_id))
    target = t_res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Publish target not found")

    if target.status in ("completed", "published"):
        raise HTTPException(status_code=400, detail="Cannot cancel a destination upload that has already succeeded.")

    c_res = await db.execute(select(Clip).where(Clip.id == target.clip_id))
    clip = c_res.scalar_one_or_none()

    if target.status == "cancelled":
        return {"status": "cancelled", "target_id": target.id, "clip_id": target.clip_id, "message": "Target already cancelled."}

    if target.status in ("queued", "pending", "scheduled", "failed", "manual_review"):
        target.status = "cancelled"
        target.publish_stage = "cancelled"
        target.error_message = "Cancelled by user."
        if target.publish_task_id:
            try:
                from backend.tasks.celery_app import celery_app
                celery_app.control.revoke(target.publish_task_id, terminate=True)
            except Exception:
                pass
        if clip:
            await _recompute_clip_aggregate_async(clip, db)
        await db.commit()
        return {"status": "cancelled", "target_id": target.id, "clip_id": target.clip_id, "message": "Target publication cancelled immediately."}

    target.status = "cancelling"
    target.publish_stage = "cancelling"
    if clip:
        await _recompute_clip_aggregate_async(clip, db)
    await db.commit()
    return {
        "status": "cancelling",
        "target_id": target.id,
        "clip_id": target.clip_id,
        "message": "Cancellation requested. Worker will halt destination upload cooperatively.",
    }


async def _load_clip_dest_outro_snapshots(
    clip_id: str,
    destination_id: str,
    db: AsyncSession,
):
    c_res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    ch_res = await db.execute(
        select(Channel).where(
            ((Channel.id == destination_id) | (Channel.youtube_channel_id == destination_id)),
            Channel.is_destination == True,
        )
    )
    ch = ch_res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail=f"Destination channel '{destination_id}' not found")

    active_outro = None
    if getattr(ch, "active_outro_id", None):
        o_res = await db.execute(
            select(DestinationOutro).where(
                DestinationOutro.id == ch.active_outro_id,
                DestinationOutro.is_active == True,
            )
        )
        active_outro = o_res.scalar_one_or_none()
    if active_outro is None:
        o_res = await db.execute(
            select(DestinationOutro)
            .where(DestinationOutro.channel_id == ch.id, DestinationOutro.is_active == True)
            .order_by(DestinationOutro.version.desc())
        )
        active_outro = o_res.scalars().first()

    clip_snap = SimpleNamespace(
        id=str(clip.id),
        video_id=clip.video_id,
        title=clip.title,
        output_path=clip.output_path,
        duration=float(clip.duration or 0.0),
    )
    dest_snap = SimpleNamespace(
        id=str(ch.id),
        youtube_channel_id=ch.youtube_channel_id,
        channel_name=ch.channel_name,
        is_destination=bool(ch.is_destination),
        is_active=bool(ch.is_active),
        active_outro_id=ch.active_outro_id,
    )
    outro_snap = (
        SimpleNamespace(
            id=str(active_outro.id),
            channel_id=str(active_outro.channel_id),
            file_path=str(active_outro.file_path),
            original_filename=active_outro.original_filename,
            outro_type=str(active_outro.outro_type),
            duration_seconds=float(active_outro.duration_seconds),
            width=active_outro.width,
            height=active_outro.height,
            fps=active_outro.fps,
            has_audio=bool(active_outro.has_audio),
            version=int(active_outro.version or 1),
            is_active=bool(active_outro.is_active),
        )
        if active_outro
        else None
    )
    return clip_snap, dest_snap, outro_snap


@router.get("/clips/{clip_id}/destinations/{destination_id}/preview-info")
async def get_destination_preview_info_route(
    clip_id: str,
    destination_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Non-mutating preview metadata for a clip + destination (base duration, outro metadata, combined duration)."""
    from backend.services.outro_service import get_destination_preview_info_from_records

    clip_snap, dest_snap, outro_snap = await _load_clip_dest_outro_snapshots(clip_id, destination_id, db)
    info = await asyncio.to_thread(
        get_destination_preview_info_from_records,
        clip_snap,
        dest_snap,
        outro_snap,
    )
    return info


@router.get("/clips/{clip_id}/destinations/{destination_id}/preview")
async def stream_destination_preview_route(
    clip_id: str,
    destination_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate (or reuse cached) destination-specific rendered preview MP4 with active outro appended,
    or stream the untouched base clip if the destination has no configured outro.
    """
    from backend.services.outro_service import (
        render_or_reuse_destination_variant_from_records,
        OutroNotFoundError,
        InvalidOutroError,
        OutroRenderError,
    )

    clip_snap, dest_snap, outro_snap = await _load_clip_dest_outro_snapshots(clip_id, destination_id, db)
    try:
        variant = await asyncio.to_thread(
            render_or_reuse_destination_variant_from_records,
            clip_snap,
            dest_snap,
            outro_snap,
            force,
        )
    except OutroNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidOutroError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except OutroRenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    video_path = Path(variant["video_path"])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Rendered preview video not found on disk")

    safe_name = "".join(c if c.isalnum() or c in ("-", "_", " ") else "_" for c in (clip_snap.title or clip_snap.id)).strip()[:60] or clip_snap.id
    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{safe_name}_{dest_snap.id[:8]}.mp4",
    )


@router.post("/schedule")
async def schedule_publish(body: PublishRequest, db: AsyncSession = Depends(get_db)):
    """Schedule a clip for later publishing (single or multi-destination)."""
    result = await db.execute(select(Clip).where(Clip.id == body.clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    existing_res = await db.execute(select(PublishTarget).where(PublishTarget.clip_id == clip.id))
    existing_targets = list(existing_res.scalars().all())
    existing_by_dest = {t.destination_id: t for t in existing_targets}

    if body.destination_ids is not None:
        if len(body.destination_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Publish destination channel is required. Please select an authorized destination.",
            )
        raw_dest_ids = list(dict.fromkeys(body.destination_ids))
    elif body.destination_channel_id:
        raw_dest_ids = [body.destination_channel_id]
    elif existing_targets:
        raw_dest_ids = [t.destination_id for t in existing_targets if t.destination_id]
    elif clip.publish_destination_id:
        raw_dest_ids = [clip.publish_destination_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Publish destination channel is required. Please select an authorized destination.",
        )

    resolved_channels = await _validate_active_destinations(raw_dest_ids, db)
    dest_ch = resolved_channels[0]

    # Validate non-null, valid, future scheduled_at (PREREQ-005)
    if not body.scheduled_at or not str(body.scheduled_at).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_at is required for scheduling a clip."
        )

    try:
        scheduled_time = datetime.fromisoformat(body.scheduled_at.strip())
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scheduled_at ISO-8601 datetime format: '{body.scheduled_at}'."
        )

    # Normalize timezone to UTC
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
    else:
        scheduled_time = scheduled_time.astimezone(timezone.utc)

    now_utc = datetime.now(timezone.utc)
    if scheduled_time <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"scheduled_at must be in the future (requested: {scheduled_time.isoformat()}, current UTC: {now_utc.isoformat()})."
        )

    # Verify rendered output artifact exists before queueing (PREREQ-005)
    if clip.status != "completed" or not clip.output_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clip {clip.id} rendering is not complete (status: '{clip.status}'). Only completed clips with rendered output can be scheduled."
        )

    out_p = _resolve_clip_local_path(clip.output_path)
    if not out_p or out_p.stat().st_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rendered video artifact does not exist or is empty on disk: {clip.output_path}."
        )

    for ch in resolved_channels:
        pt = existing_by_dest.get(ch.id)
        idemp = f"pub_{clip.id}_{ch.id}"
        if not pt:
            db.add(PublishTarget(
                id=str(uuid.uuid4()),
                clip_id=clip.id,
                destination_id=ch.id,
                status="queued",
                privacy="private",
                made_for_kids=bool(body.made_for_kids),
                age_restricted=bool(body.age_restricted),
                scheduled_at=scheduled_time,
                publish_stage="scheduled",
                publish_progress=0.0,
                idempotency_key=idemp,
                created_at=now_utc,
                updated_at=now_utc,
            ))
        elif pt.status not in ("completed", "published"):
            pt.status = "queued"
            pt.publish_stage = "scheduled"
            pt.scheduled_at = scheduled_time
            pt.privacy = "private"
            pt.made_for_kids = bool(body.made_for_kids)
            pt.age_restricted = bool(body.age_restricted)
            pt.idempotency_key = pt.idempotency_key or idemp

    clip.publish_status = "queued"
    clip.scheduled_at = scheduled_time
    clip.publish_destination_id = dest_ch.id
    clip.privacy = "private"
    clip.made_for_kids = body.made_for_kids
    clip.age_restricted = body.age_restricted
    clip.tags = body.tags
    clip.category = body.category
    clip.license = body.license
    if body.title:
        clip.title = body.title
    if body.description:
        clip.description = body.description
    await db.commit()
    serialized = await _serialize_targets_for_clips([clip.id], db)
    return {
        "message": "Clip scheduled",
        "scheduled_at": scheduled_time.isoformat() if scheduled_time else None,
        "targets": serialized.get(clip.id, []),
    }


@router.get("/queue")
async def get_publish_queue(
    status_filter: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get all clips in the publish queue or recent publish history, enriched with per-destination targets."""
    query = select(Clip).where(
        Clip.publish_status.isnot(None),
        Clip.publish_status != PublishStatus.DRAFT.value
    )
    if status_filter:
        query = query.where(Clip.publish_status == status_filter)

    query = query.order_by(
        desc(func.coalesce(Clip.publish_started_at, Clip.scheduled_at, Clip.published_at, Clip.created_at))
    ).limit(limit)

    result = await db.execute(query)
    clips = result.scalars().all()
    clip_ids = [c.id for c in clips]
    targets_map = await _serialize_targets_for_clips(clip_ids, db)

    return [
        {
            "id": c.id,
            "title": c.title,
            "publish_status": c.publish_status,
            "publish_stage": c.publish_stage,
            "publish_progress": c.publish_progress or 0,
            "publish_error": c.publish_error,
            "publish_attempt": c.publish_attempt or 0,
            "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
            "published_at": c.published_at.isoformat() if c.published_at else None,
            "publish_started_at": c.publish_started_at.isoformat() if c.publish_started_at else None,
            "youtube_short_id": c.youtube_short_id,
            "youtube_url": f"https://youtube.com/shorts/{c.youtube_short_id}" if c.youtube_short_id else None,
            "publish_destination_id": c.publish_destination_id,
            "destination_ids": [t["destination_id"] for t in targets_map.get(c.id, [])],
            "targets": targets_map.get(c.id, []),
            "privacy": c.privacy or "private",
            "thumbnail_path": c.thumbnail_path,
        }
        for c in clips
    ]
