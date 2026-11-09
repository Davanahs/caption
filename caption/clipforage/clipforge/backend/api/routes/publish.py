"""API Routes — YouTube Publishing"""
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Body, Response, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from pydantic import BaseModel
from backend.models.database import get_db
from backend.models.models import Clip, VideoMetadata, PublishStatus
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
        "privacy": clip.privacy or "public",
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
            "privacy": clip.privacy or "public",
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

    destinations = []
    for c in channels:
        is_auth = check_channel_authorization(c.youtube_channel_id)
        destinations.append({
            "id": c.id,
            "youtube_channel_id": c.youtube_channel_id,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "thumbnail_url": c.thumbnail_url,
            "is_default_destination": c.is_default_destination,
            "default_destination_expires_at": c.default_destination_expires_at.isoformat() if c.default_destination_expires_at else None,
            "is_authorized": is_auth,
            "status": "connected" if is_auth else "needs_reauth",
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


@router.post("/publish-now", status_code=status.HTTP_202_ACCEPTED)
async def publish_now(body: PublishRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Upload Studio Phase 3: Durable Asynchronous Publishing.
    - Validates eligibility (output file exists, video not processing).
    - Reuses/returns active publishing operation if in progress (status 202).
    - Blocks normal publish if in manual_review (HTTP 409).
    - Commits PostgreSQL transaction first ('queued') before Celery dispatch.
    - Dispatches publish_clip_task with stable logical idempotency key.
    - Returns 202 Accepted.
    """
    result = await db.execute(select(Clip).where(Clip.id == body.clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Already published check
    if clip.publish_status == PublishStatus.PUBLISHED.value and clip.youtube_short_id:
        response.status_code = status.HTTP_200_OK
        return {
            "status": "published",
            "message": "Clip is already published",
            "youtube_url": f"https://www.youtube.com/shorts/{clip.youtube_short_id}",
            "video_id": clip.youtube_short_id,
        }

    # Already actively running check -> idempotent reuse
    if clip.publish_status in (PublishStatus.QUEUED.value, PublishStatus.UPLOADING.value, PublishStatus.FINALIZING.value):
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": clip.publish_status,
            "clip_id": clip.id,
            "task_id": clip.publish_task_id,
            "progress": clip.publish_progress,
            "stage": clip.publish_stage,
            "message": "Publishing operation is already in progress.",
        }

    # Manual review gating
    if clip.publish_status == PublishStatus.MANUAL_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clip publication is in manual_review state. Automatic publishing is blocked until manual resolution."
        )

    # Output file validation
    if not clip.output_path or not Path(clip.output_path).exists():
        raise HTTPException(status_code=400, detail="Clip video file not found on disk")

    # Save metadata attributes to DB record
    clip.privacy = body.privacy
    clip.made_for_kids = body.made_for_kids
    clip.age_restricted = body.age_restricted
    clip.tags = body.tags
    clip.category = body.category
    # Determine and strictly validate effective destination channel
    effective_dest_id = body.destination_channel_id or clip.publish_destination_id
    if not effective_dest_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Publish destination channel is required. Please select an authorized destination."
        )

    from backend.models.models import Channel
    dest_res = await db.execute(
        select(Channel).where(
            (Channel.id == effective_dest_id) | (Channel.youtube_channel_id == effective_dest_id),
            Channel.is_destination == True,
            Channel.is_active == True,
        )
    )
    dest_ch = dest_res.scalar_one_or_none()
    if not dest_ch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination channel: not found, inactive, or not an authorized destination."
        )

    from backend.services.publisher import check_channel_authorization
    if not check_channel_authorization(dest_ch.youtube_channel_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination channel is not authorized or OAuth credentials are invalid."
        )

    clip.publish_destination_id = dest_ch.id
    if body.title:
        clip.title = body.title
    if body.description:
        clip.description = body.description

    # Assign stable logical idempotency key
    idempotency_key = clip.publish_idempotency_key or f"pub_{clip.id}_{dest_ch.id}"
    clip.publish_idempotency_key = idempotency_key
    clip.publish_status = PublishStatus.QUEUED.value
    clip.publish_stage = "queued"
    clip.publish_progress = 0
    clip.publish_error = None
    clip.publish_started_at = datetime.now(timezone.utc)

    # Commit PostgreSQL transaction FIRST (Requirement 3: Durable PostgreSQL-to-Celery Dispatch)
    await db.commit()
    await db.refresh(clip)

    # Dispatch Celery task
    from backend.tasks.clip_tasks import publish_clip_task
    try:
        task = publish_clip_task.apply_async(
            args=[clip.id],
            kwargs={
                "channel_id": dest_ch.id,
                "privacy": body.privacy,
            }
        )
        clip.publish_task_id = task.id
        await db.commit()
    except Exception as exc:
        print(f"[PublishAPI] Celery dispatch warning: {exc}. Job remains queued in DB and will be recovered.")

    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "status": "queued",
        "clip_id": clip.id,
        "task_id": clip.publish_task_id,
        "idempotency_key": idempotency_key,
        "message": "Publishing job queued successfully",
    }


@router.get("/status/{clip_id}")
async def get_publish_status_route(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Get live publishing status, progress, stage, attempt count, and remote video ID."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

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
    }


@router.post("/clips/{clip_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_publish_clip(clip_id: str, body: RetryPublishRequest = None, db: AsyncSession = Depends(get_db)):
    """
    Retries publishing for a failed or stuck clip.
    - Rejects if already published.
    - Rejects if active publishing is in-flight.
    - If in manual_review, requires force=True to acknowledge resolution.
    - Commits DB first, dispatches task, returns 202 Accepted.
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

    clip.publish_status = PublishStatus.QUEUED.value
    clip.publish_stage = "queued"
    clip.publish_error = None
    clip.publish_progress = 0
    clip.publish_started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(clip)

    from backend.tasks.clip_tasks import publish_clip_task
    try:
        task = publish_clip_task.apply_async(
            args=[clip.id],
            kwargs={
                "channel_id": clip.publish_destination_id,
                "privacy": "private"
            }
        )
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
    Cooperative cancellation of a publishing job.
    - Rejects if already published.
    - If queued, scheduled, draft, failed, or manual_review, immediately cancels and revokes Celery task.
    - If uploading or finalizing, sets 'cancelling' so the worker halts safely.
    """
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if clip.publish_status == PublishStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="Cannot cancel a publication that has already succeeded.")

    if clip.publish_status == PublishStatus.CANCELLED.value:
        return {"status": "cancelled", "clip_id": clip.id, "message": "Publication already cancelled."}

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


@router.post("/schedule")
async def schedule_publish(body: PublishRequest, db: AsyncSession = Depends(get_db)):
    """Schedule a clip for later publishing."""
    result = await db.execute(select(Clip).where(Clip.id == body.clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Determine and strictly validate effective destination channel
    effective_dest_id = body.destination_channel_id or clip.publish_destination_id
    if not effective_dest_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Publish destination channel is required. Please select an authorized destination."
        )

    from backend.models.models import Channel
    dest_res = await db.execute(
        select(Channel).where(
            (Channel.id == effective_dest_id) | (Channel.youtube_channel_id == effective_dest_id),
            Channel.is_destination == True,
            Channel.is_active == True,
        )
    )
    dest_ch = dest_res.scalar_one_or_none()
    if not dest_ch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination channel: not found, inactive, or not an authorized destination."
        )

    from backend.services.publisher import check_channel_authorization
    if not check_channel_authorization(dest_ch.youtube_channel_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination channel is not authorized or OAuth credentials are invalid."
        )

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

    out_p = Path(clip.output_path)
    if not out_p.is_absolute():
        from backend.core.config import settings
        out_p = settings.OUTPUT_DIR / clip.output_path
    if not out_p.exists() or out_p.stat().st_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rendered video artifact does not exist or is empty on disk: {clip.output_path}."
        )

    clip.publish_status = "queued"
    clip.scheduled_at = scheduled_time
    clip.publish_destination_id = dest_ch.id
    clip.privacy = body.privacy
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
    return {"message": "Clip scheduled", "scheduled_at": scheduled_time.isoformat() if scheduled_time else None}


@router.get("/queue")
async def get_publish_queue(
    status_filter: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get all clips in the publish queue or recent publish history."""
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
            "privacy": c.privacy or "public",
            "thumbnail_path": c.thumbnail_path,
        }
        for c in clips
    ]
