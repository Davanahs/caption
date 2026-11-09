"""API Routes — Channel Automation & Intelligent Decision Lifecycle"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
import enum
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from pydantic import BaseModel, Field, model_validator
from backend.models.database import get_db
from backend.models.models import Channel, Video, VideoDecision, VideoDecisionStatus, Job, JobStatus, Clip
from backend.services.downloader import get_channel_videos, extract_youtube_id
from backend.core.config import settings
from backend.core.sanitizer import sanitize_user_facing_error
from backend.models.db_sync import create_job_sync
from backend.tasks.orchestration import resolve_video_decision_sync

logger = logging.getLogger(__name__)
KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/api/channels", tags=["channels"])


def format_ist(dt: datetime | None) -> str | None:
    """Format UTC datetime into human-readable Asia/Kolkata (IST) string."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KOLKATA_TZ).strftime("%d %b %Y, %I:%M:%S %p IST")


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class ChannelProcessingProfile(BaseModel):
    duration_mode: Literal["fixed", "adaptive"] = "adaptive"
    target_duration: float | None = Field(default=None, description="Target clip duration in seconds (15.0 - 60.0s)")
    min_clip_duration: float = Field(default=15.0, description="Minimum clip duration in seconds (>=15.0s)")
    max_clip_duration: float = Field(default=60.0, description="Maximum clip duration in seconds (<=60.0s)")
    clips_count: int = Field(default=3, ge=1, le=10, description="Number of clips to generate (1-10)")
    video_layout: Literal[
        "fill_blur",
        "fit_black",
        "split_screen",
        "center_crop",
        "blur_background",
        "multi_split",
        "stacked_16_9",
        "creative_transform",
        "static_wide",
    ] = Field(default="fill_blur", description="Layout framing mode")
    scoring_mode: Literal["ai"] = Field(default="ai", description="Scoring method (AI required, no heuristic fallback)")
    segmentation_strategy: Literal["scene", "transcript", "equal_splits", "hook_peak_fall"] = Field(default="scene", description="Segmentation method")
    caption_burn_in: bool = Field(default=False, description="Zero caption burn-in enforced")

    @model_validator(mode="after")
    def validate_profile(self):
        if self.caption_burn_in:
            raise ValueError("Caption burn-in is strictly disabled under ClipForge freeze rules.")
        if self.min_clip_duration < 15.0 or self.min_clip_duration > 60.0:
            raise ValueError("min_clip_duration must be between 15.0 and 60.0 seconds.")
        if self.max_clip_duration < 15.0 or self.max_clip_duration > 60.0:
            raise ValueError("max_clip_duration must be between 15.0 and 60.0 seconds.")
        if self.min_clip_duration > self.max_clip_duration:
            raise ValueError(f"min_clip_duration ({self.min_clip_duration}) cannot exceed max_clip_duration ({self.max_clip_duration}).")
        if self.duration_mode == "fixed":
            if self.target_duration is None:
                raise ValueError("target_duration is required when duration_mode is 'fixed'.")
            if self.target_duration < 15.0 or self.target_duration > 60.0:
                raise ValueError(f"target_duration ({self.target_duration}) must be between 15.0 and 60.0 seconds.")
        return self


DEFAULT_PROCESSING_PROFILE = ChannelProcessingProfile().model_dump()


class AddChannelRequest(BaseModel):
    channel_url: str
    auto_clip: bool = False
    auto_publish: bool = False
    publish_destination_id: str | None = None
    processing_profile: ChannelProcessingProfile | dict | None = None


class UpdateChannelRequest(BaseModel):
    auto_clip: bool | None = None
    auto_publish: bool | None = None
    is_active: bool | None = None
    publish_destination_id: str | None = None
    processing_profile: ChannelProcessingProfile | dict | None = None


class CustomizeDecisionRequest(BaseModel):
    lease_token: str | None = None
    force: bool = False


class SaveAndProcessRequest(BaseModel):
    overrides: ChannelProcessingProfile | dict | None = None
    lease_token: str | None = None
    expected_status: str | None = None


class ProcessVideoRequest(BaseModel):
    video_id: str
    video_url: str
    video_title: str | None = None
    overrides: ChannelProcessingProfile | dict | None = None


class ProcessVideoItem(BaseModel):
    video_id: str
    video_url: str
    video_title: str | None = None
    overrides: ChannelProcessingProfile | dict | None = None


class BatchProcessVideosRequest(BaseModel):
    videos: list[ProcessVideoItem] = Field(..., min_length=1)
    requested_count: int | None = Field(default=None, ge=1, le=20, description="Authoritative ceiling on source videos to process")
    overrides: ChannelProcessingProfile | dict | None = None


class HistoricalSelectionMode(str, enum.Enum):
    LATEST = "latest"
    MOST_VIEWED = "most_viewed"
    UPLOADED_SINCE = "uploaded_since"
    NEW_ONLY = "new_only"


class HistoricalPreviewRequest(BaseModel):
    mode: HistoricalSelectionMode = HistoricalSelectionMode.LATEST
    count: int = Field(default=3, ge=1, le=50)
    since_date: str | None = None
    max_search_depth: int = Field(default=50, ge=1, le=250)


class HistoricalProcessRequest(BaseModel):
    mode: HistoricalSelectionMode = HistoricalSelectionMode.LATEST
    video_ids: list[str] = Field(default_factory=list)
    requested_count: int | None = Field(default=None, ge=1, le=20, description="Authoritative ceiling on source videos to process")
    overrides: ChannelProcessingProfile | dict | None = None


def parse_date_boundary(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    s = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_youtube_rss_dates_sync(channel_yt_id: str) -> dict[str, str]:
    import urllib.request
    import xml.etree.ElementTree as ET
    dates = {}
    if not channel_yt_id or channel_yt_id.startswith("synth_") or channel_yt_id.startswith("mock_"):
        return dates
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_yt_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        for entry in root.findall("atom:entry", ns):
            vid_elem = entry.find("yt:videoId", ns)
            pub_elem = entry.find("atom:published", ns)
            if vid_elem is not None and vid_elem.text and pub_elem is not None and pub_elem.text:
                dates[vid_elem.text.strip()] = pub_elem.text.strip()
    except Exception as e:
        logger.debug(f"[RSS Date Fetch] Skipped or failed for {channel_yt_id}: {e}")
    return dates


# ── Channel Management Endpoints ─────────────────────────────────────────────

@router.post("/")
async def add_channel(body: AddChannelRequest, db: AsyncSession = Depends(get_db)):
    """Add a YouTube channel for monitoring with persistent processing profile."""
    try:
        videos = await get_channel_videos(body.channel_url, max_results=1)
        channel_name = "Unknown Channel"
        channel_id = str(uuid.uuid4())[:8]
        if isinstance(videos, list) and videos:
            vid = videos[0]
            channel_name = vid.get("playlist_channel") or vid.get("playlist_uploader") or vid.get("channel") or vid.get("uploader") or "Unknown Channel"
            channel_id = vid.get("playlist_channel_id") or vid.get("channel_id") or channel_id
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch channel info: {e}")

    # Check if already added
    existing = await db.execute(
        select(Channel).where(Channel.youtube_channel_id == channel_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Channel already being monitored")

    if body.auto_publish and not body.publish_destination_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot enable auto-publish without selecting a valid publish destination."
        )

    if body.publish_destination_id:
        dest_res = await db.execute(
            select(Channel).where(Channel.id == body.publish_destination_id, Channel.is_destination == True)
        )
        dest_ch = dest_res.scalar_one_or_none()
        if not dest_ch:
            raise HTTPException(status_code=400, detail="Invalid publish destination: channel does not exist or is not registered as a destination")
        if not dest_ch.is_active:
            raise HTTPException(status_code=400, detail="Publish destination channel is not active")
        if body.auto_publish:
            from backend.services.publisher import check_channel_authorization
            if not check_channel_authorization(dest_ch.youtube_channel_id):
                raise HTTPException(status_code=400, detail="Publish destination channel is not authorized or OAuth credentials are invalid")

    # Validate and serialize processing profile
    profile_data = None
    if body.processing_profile:
        if isinstance(body.processing_profile, dict):
            try:
                validated_profile = ChannelProcessingProfile(**body.processing_profile)
                profile_data = validated_profile.model_dump()
            except Exception as val_err:
                raise HTTPException(status_code=422, detail=f"Invalid processing profile: {val_err}")
        else:
            profile_data = body.processing_profile.model_dump()
    else:
        # Default profile
        profile_data = ChannelProcessingProfile().model_dump()

    now = datetime.now(timezone.utc)
    top_video_id = None
    historical_ids = []
    if isinstance(videos, list) and videos:
        top_video_id = videos[0].get("id") or (videos[0].get("url", "").split("v=")[-1])
        historical_ids = [v.get("id") or v.get("url", "").split("v=")[-1] for v in videos if v.get("id") or "v=" in v.get("url", "")]

    # Baseline watermark in processing profile
    profile_data["monitoring_baseline"] = {
        "baseline_at": now.isoformat(),
        "initial_top_video_id": top_video_id,
        "known_historical_ids": historical_ids,
    }

    channel = Channel(
        id=str(uuid.uuid4()),
        youtube_channel_id=channel_id,
        channel_name=channel_name,
        channel_url=body.channel_url,
        auto_clip=body.auto_clip,
        auto_publish=body.auto_publish,
        publish_destination_id=body.publish_destination_id,
        processing_profile=profile_data,
        last_video_id=top_video_id,
        last_checked_at=now,
    )
    db.add(channel)
    await db.commit()
    return {
        "message": "Channel added",
        "channel_name": channel_name,
        "id": channel.id,
        "publish_destination_id": channel.publish_destination_id,
        "processing_profile": channel.processing_profile,
    }


@router.get("/")
async def list_channels(
    include_destinations: bool = False,
    include_test: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """List monitored source channels, separating them from publishing destinations and test fixtures."""
    query = select(Channel)
    if not include_destinations:
        query = query.where(Channel.is_destination == False)
    if not include_test:
        query = query.where(Channel.is_test == False)

    result = await db.execute(query.order_by(desc(Channel.created_at)))
    channels = result.scalars().all()
    return [
        {
            "id": c.id,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "youtube_channel_id": c.youtube_channel_id,
            "thumbnail_url": c.thumbnail_url,
            "is_active": c.is_active,
            "auto_clip": c.auto_clip,
            "auto_publish": c.auto_publish,
            "publish_destination_id": c.publish_destination_id,
            "processing_profile": c.processing_profile,
            "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
            "last_checked_at_ist": format_ist(c.last_checked_at),
            "clips_generated": c.clips_generated,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in channels
    ]


@router.patch("/{channel_id}")
async def update_channel(channel_id: str, body: UpdateChannelRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if body.is_active is not None:
        channel.is_active = body.is_active
    if body.auto_clip is not None:
        channel.auto_clip = body.auto_clip

    # Validate destination channel updates if provided
    new_dest_id = channel.publish_destination_id
    if body.publish_destination_id is not None:
        if body.publish_destination_id == "":
            channel.publish_destination_id = None
            new_dest_id = None
        else:
            dest_res = await db.execute(
                select(Channel).where(Channel.id == body.publish_destination_id, Channel.is_destination == True)
            )
            dest_ch = dest_res.scalar_one_or_none()
            if not dest_ch:
                raise HTTPException(status_code=400, detail="Invalid publish destination: channel does not exist or is not registered as a destination")
            if not dest_ch.is_active:
                raise HTTPException(status_code=400, detail="Publish destination channel is not active")
            channel.publish_destination_id = body.publish_destination_id
            new_dest_id = body.publish_destination_id

    # Auto-publish validation
    target_auto_publish = body.auto_publish if body.auto_publish is not None else channel.auto_publish
    if target_auto_publish:
        if not new_dest_id:
            raise HTTPException(
                status_code=422,
                detail="Cannot enable auto-publish without a valid publish destination."
            )
        dest_res = await db.execute(
            select(Channel).where(Channel.id == new_dest_id, Channel.is_destination == True)
        )
        dest_obj = dest_res.scalar_one_or_none()
        if not dest_obj or not dest_obj.is_active:
            raise HTTPException(status_code=400, detail="Publish destination channel is not active or invalid")
        from backend.services.publisher import check_channel_authorization
        if not check_channel_authorization(dest_obj.youtube_channel_id):
            raise HTTPException(status_code=400, detail="Publish destination channel is not authorized or OAuth credentials are invalid")
        channel.auto_publish = True
    else:
        if body.auto_publish is not None:
            channel.auto_publish = False
        elif body.publish_destination_id is not None and not new_dest_id:
            # If destination was cleared and auto_publish was not explicitly supplied, disable auto_publish
            channel.auto_publish = False

    if body.processing_profile is not None:
        if isinstance(body.processing_profile, dict):
            try:
                validated = ChannelProcessingProfile(**body.processing_profile)
                channel.processing_profile = validated.model_dump()
            except Exception as val_err:
                raise HTTPException(status_code=422, detail=f"Invalid processing profile: {val_err}")
        else:
            channel.processing_profile = body.processing_profile.model_dump()

    await db.commit()
    return {
        "message": "Channel updated",
        "processing_profile": channel.processing_profile,
        "auto_clip": channel.auto_clip,
        "auto_publish": channel.auto_publish,
    }


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Channel).where((Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Ensure every dependent source profile can no longer auto-publish using the deleted destination
    dep_result = await db.execute(
        select(Channel).where(
            Channel.is_destination == False,
            (Channel.publish_destination_id == channel.id) | (Channel.publish_destination_id == channel.youtube_channel_id),
        )
    )
    for dep_ch in dep_result.scalars().all():
        dep_ch.auto_publish = False
        dep_ch.publish_destination_id = None

    await db.delete(channel)
    await db.commit()
    return {"message": "Channel removed"}


@router.post("/{channel_id}/check-now")
async def check_channel_now(channel_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger an immediate channel check."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    from backend.services.channel_monitor import check_channel_for_new_videos
    from backend.tasks.orchestration import resolve_video_decision_countdown_task

    new_vids = await check_channel_for_new_videos(channel, db)
    created_decisions = []

    for vid in new_vids:
        yt_id = vid["id"]
        url = vid["url"]
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=20)
        decision_id = str(uuid.uuid4())
        profile_snapshot = channel.processing_profile or {}

        status = (
            VideoDecisionStatus.AWAITING_SETTINGS.value
            if channel.auto_clip
            else "manual_selection_required"
        )

        decision = VideoDecision(
            id=decision_id,
            channel_id=channel.id,
            youtube_id=yt_id,
            video_title=vid["title"],
            youtube_url=url,
            video_thumbnail=vid.get("thumbnail_url"),
            status=status,
            decision_deadline=deadline,
            channel_profile_snapshot=profile_snapshot,
            overrides=profile_snapshot,
            created_at=now
        )
        db.add(decision)
        await db.commit()

        if channel.auto_clip:
            try:
                resolve_video_decision_countdown_task.apply_async(
                    args=[decision_id],
                    countdown=20
                )
            except Exception as celery_err:
                logger.error(f"Failed to dispatch countdown task: {celery_err}")

        created_decisions.append({
            "decision_id": decision_id,
            "youtube_id": yt_id,
            "title": vid["title"],
            "status": status,
            "deadline": deadline.isoformat(),
        })

    return {
        "new_videos_found": len(new_vids),
        "decisions": created_decisions,
    }


# ── Paginated Video Discovery ────────────────────────────────────────────────

@router.get("/{channel_id}/videos")
async def get_channel_recent_videos(
    channel_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    sort: str = Query(default="latest", pattern="^(latest|most_viewed)$"),
    scan_depth: int = Query(default=50, ge=10, le=250),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch paginated channel video history with processing and decision statuses.
    Supports 'latest' upload ordering or 'most_viewed' numeric view-count ranking within scan scope.
    Contract: items, page, page_size, has_more, sort, scan_scope.
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    scan_scope = None
    if sort == "most_viewed":
        # Fetch candidate inventory up to scan_depth to perform honest view-count ranking
        try:
            discovery = await get_channel_videos(
                channel.channel_url,
                start_index=1,
                page_size=scan_depth,
                return_page_meta=True
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch channel videos for ranking: {e}")

        all_candidates = discovery.get("items", []) if isinstance(discovery, dict) else (discovery or [])
        scan_scope = len(all_candidates)

        def _sort_key(v):
            raw_vc = v.get("view_count")
            vc = None
            if raw_vc is not None:
                try:
                    vc = int(raw_vc)
                except (ValueError, TypeError):
                    vc = None
            # Numeric descending with nulls placed last (-1 mapped to 1)
            primary = -(vc) if vc is not None else 1
            # Secondary tie-breaker: upload timestamp/date descending
            raw_ts = v.get("timestamp")
            ts = 0
            if raw_ts is not None:
                try:
                    ts = int(raw_ts)
                except (ValueError, TypeError):
                    ts = 0
            if ts == 0 and v.get("upload_date"):
                try:
                    ts = int(datetime.strptime(str(v["upload_date"]).strip()[:8], "%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
                except Exception:
                    ts = 0
            # Tertiary tie-breaker: video ID ascending
            vid_id = str(v.get("id") or "")
            return (primary, -ts, vid_id)

        all_candidates.sort(key=_sort_key)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        items = all_candidates[start_idx:end_idx]
        has_more = end_idx < len(all_candidates)
    else:
        # Standard chronological pagination
        try:
            discovery = await get_channel_videos(
                channel.channel_url,
                page=page,
                page_size=page_size,
                return_page_meta=True
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch channel videos: {e}")

        items = discovery.get("items", []) if isinstance(discovery, dict) else (discovery or [])
        has_more = discovery.get("has_more", False) if isinstance(discovery, dict) else False

    # Collect YouTube IDs for bulk lookup
    yt_ids = [vid.get("id") or (vid.get("url", "").split("v=")[-1] if "v=" in vid.get("url", "") else None) for vid in items if vid]
    yt_ids = [y for y in yt_ids if y]

    # Query existing processed Videos
    processed_query = await db.execute(
        select(Video.youtube_id).where(Video.youtube_id.in_(yt_ids))
    )
    processed_ids = set(processed_query.scalars().all())

    # Query active/historical VideoDecisions for this channel
    decisions_query = await db.execute(
        select(VideoDecision).where(
            VideoDecision.channel_id == channel.id,
            VideoDecision.youtube_id.in_(yt_ids)
        )
    )
    decisions_map = {d.youtube_id: d for d in decisions_query.scalars().all()}

    # Bulk provenance lookup to identify ClipForge-generated Shorts
    from backend.services.provenance import get_clipforge_shorts_map
    shorts_map = await get_clipforge_shorts_map(db, yt_ids)

    # Look up jobs associated with these decisions to resolve real status and error provenance
    job_ids = [d.job_id for d in decisions_map.values() if d.job_id]
    jobs_map = {}
    if job_ids:
        jobs_q = await db.execute(
            select(Job.id, Job.status, Job.error_message).where(Job.id.in_(job_ids))
        )
        for j_id, j_status, j_err in jobs_q.all():
            jobs_map[j_id] = {"status": j_status, "error_message": j_err}

    formatted_items = []
    for vid in items:
        yt_id = vid.get("id") or (vid.get("url", "").split("v=")[-1] if "v=" in vid.get("url", "") else None)
        if not yt_id:
            continue

        decision = decisions_map.get(yt_id)
        job_info = jobs_map.get(decision.job_id) if (decision and decision.job_id) else None
        job_status = job_info["status"] if job_info else None
        job_error = sanitize_user_facing_error(job_info["error_message"]) if job_info else None

        cf_short_info = shorts_map.get(yt_id)
        is_gen_short = cf_short_info is not None

        # A video is only treated as processed if a Clip was successfully generated, the Job completed, or it is an output Short
        is_processed = bool((yt_id in processed_ids) or (job_status == JobStatus.COMPLETED.value) or is_gen_short)

        # Resolve thumbnail URL
        thumb_url = None
        if vid.get("thumbnails"):
            for t in vid.get("thumbnails", []):
                if isinstance(t, dict) and t.get("url"):
                    thumb_url = t.get("url")
                    break
        elif vid.get("thumbnail"):
            thumb_url = vid.get("thumbnail")

        if not thumb_url and yt_id and not yt_id.startswith("synth_") and not yt_id.startswith("vid_"):
            thumb_url = f"https://i.ytimg.com/vi/{yt_id}/mqdefault.jpg"

        # Safe view count integer parsing
        raw_vc = vid.get("view_count")
        view_cnt = None
        if raw_vc is not None:
            try:
                view_cnt = int(raw_vc)
            except (ValueError, TypeError):
                view_cnt = None

        formatted_items.append({
            "id": yt_id,
            "title": vid.get("title", "Untitled"),
            "thumbnail": thumb_url,
            "duration": vid.get("duration"),
            "url": vid.get("url") or f"https://www.youtube.com/watch?v={yt_id}",
            "is_processed": is_processed,
            "is_generated_short": is_gen_short,
            "parent_source_id": cf_short_info["parent_source_id"] if cf_short_info else None,
            "parent_source_title": cf_short_info["parent_source_title"] if cf_short_info else None,
            "generated_short_title": cf_short_info["clip_title"] if cf_short_info else None,
            "published_at": vid.get("upload_date"),
            "view_count": view_cnt,
            "decision_id": decision.id if decision else None,
            "decision_status": "failed" if job_status == "failed" else (decision.status if decision else None),
            "decision_deadline": decision.decision_deadline.isoformat() if decision and decision.decision_deadline else None,
            "job_id": decision.job_id if decision else None,
            "job_status": job_status,
            "job_error": job_error,
        })

    return {
        "channel_id": channel.id,
        "channel_name": channel.channel_name,
        "items": formatted_items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "sort": sort,
        "scan_scope": scan_scope
    }


@router.post("/{channel_id}/process-video")
async def process_channel_video(
    channel_id: str,
    body: ProcessVideoRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually submit a specific discovered YouTube video for processing.
    Honors channel defaults or custom per-video overrides.
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Validate overrides if supplied
    effective_config = channel.processing_profile or {}
    if body.overrides:
        if isinstance(body.overrides, dict):
            try:
                validated = ChannelProcessingProfile(**body.overrides)
                effective_config = validated.model_dump()
            except Exception as val_err:
                raise HTTPException(status_code=422, detail=f"Invalid overrides: {val_err}")
        else:
            effective_config = body.overrides.model_dump()

    # Guard: Check if video is a ClipForge-generated Short (prevent self-ingestion)
    from backend.services.provenance import check_is_clipforge_short
    is_short, cf_clip, parent_v = await check_is_clipforge_short(db, body.video_id)
    if is_short:
        parent_title = parent_v.title if parent_v else "Original Source Video"
        parent_id = parent_v.youtube_id if parent_v else "unknown"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Self-ingestion blocked: '{body.video_id}' is a ClipForge-generated output Short "
                f"(origin: '{parent_title}' [{parent_id}]). Output Shorts cannot be processed as source inputs."
            )
        )

    # Check for existing decision or create one
    existing_dec = await db.execute(
        select(VideoDecision).where(
            VideoDecision.channel_id == channel.id,
            VideoDecision.youtube_id == body.video_id
        )
    )
    decision = existing_dec.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    terminal_statuses = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]

    if not decision:
        decision_id = str(uuid.uuid4())
        decision = VideoDecision(
            id=decision_id,
            channel_id=channel.id,
            youtube_id=body.video_id,
            video_title=body.video_title or f"Video {body.video_id}",
            youtube_url=body.video_url,
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,  # Awaiting settings allows resolve_video_decision_sync to create Job!
            decision_deadline=now,
            channel_profile_snapshot=channel.processing_profile or DEFAULT_PROCESSING_PROFILE,
            overrides=effective_config,
            created_at=now
        )
        db.add(decision)
        await db.commit()
    else:
        decision_id = decision.id
        # If already has a job, check if job is active
        if decision.job_id:
            job_check = await db.execute(select(Job).where(Job.id == decision.job_id))
            existing_job = job_check.scalar_one_or_none()
            if existing_job and existing_job.status not in terminal_statuses:
                return {
                    "message": "Video is already being processed",
                    "job_id": decision.job_id,
                    "decision_id": decision_id,
                    "status": "already_processing",
                    "effective_config": effective_config
                }
            # If job was terminal or missing, reset job_id and status to allow fresh re-processing
            decision.job_id = None
            decision.status = VideoDecisionStatus.AWAITING_SETTINGS.value
            decision.overrides = effective_config
            await db.commit()
        elif decision.status in (VideoDecisionStatus.RESOLVED_CUSTOM.value, VideoDecisionStatus.RESOLVED_DEFAULTS.value):
            # Stranded decision without job_id: reset status so resolution creates job
            decision.status = VideoDecisionStatus.AWAITING_SETTINGS.value
            decision.overrides = effective_config
            await db.commit()

    # Resolve and trigger processing job
    res = resolve_video_decision_sync(
        decision_id=decision_id,
        action="custom" if body.overrides else "apply_defaults",
        custom_overrides=effective_config
    )
    return {
        "message": "Video queued for processing",
        "job_id": res.get("job_id"),
        "decision_id": decision_id,
        "status": "queued",
        "effective_config": effective_config
    }


@router.post("/{channel_id}/process-videos-batch")
async def process_channel_videos_batch(
    channel_id: str,
    body: BatchProcessVideosRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit multiple discovered YouTube videos for sequential processing.
    Validates items individually and reports exact per-item status.
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Global batch overrides or channel defaults
    batch_config = channel.processing_profile or {}
    if body.overrides:
        if isinstance(body.overrides, dict):
            try:
                validated = ChannelProcessingProfile(**body.overrides)
                batch_config = validated.model_dump()
            except Exception as val_err:
                raise HTTPException(status_code=422, detail=f"Invalid batch overrides: {val_err}")
        else:
            batch_config = body.overrides.model_dump()

    unique_items_count = len({itm.video_id for itm in body.videos if itm.video_id})

    # Section 5.4 Count Enforcement:
    requested_limit = body.requested_count
    if requested_limit is not None:
        if unique_items_count > requested_limit:
            raise HTTPException(
                status_code=422,
                detail=f"Submitted unique video IDs ({unique_items_count}) exceeds requested_count ({requested_limit})."
            )

    items_results = []
    queued_count = 0
    already_processing_count = 0
    already_processed_count = 0
    rejected_count = 0
    seen_batch_ids = set()

    terminal_statuses = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]

    for item in body.videos:
        if item.video_id and item.video_id in seen_batch_ids:
            already_processing_count += 1
            items_results.append({
                "video_id": item.video_id,
                "video_title": item.video_title or f"Video {item.video_id}",
                "status": "already_processing",
                "message": "Duplicate item within batch payload"
            })
            continue

        if item.video_id:
            seen_batch_ids.add(item.video_id)
        if not item.video_id or not item.video_url:
            rejected_count += 1
            items_results.append({
                "video_id": item.video_id or "unknown",
                "video_title": item.video_title or "Unknown",
                "status": "rejected",
                "error": "Missing video_id or video_url"
            })
            continue

        item_config = dict(batch_config)
        item_config["origin"] = "manual_popular"
        if item.overrides:
            if isinstance(item.overrides, dict):
                try:
                    val = ChannelProcessingProfile(**item.overrides)
                    item_config.update(val.model_dump())
                    item_config["origin"] = "manual_popular"
                except Exception as val_err:
                    rejected_count += 1
                    items_results.append({
                        "video_id": item.video_id,
                        "video_title": item.video_title or f"Video {item.video_id}",
                        "status": "rejected",
                        "error": f"Invalid item overrides: {val_err}"
                    })
                    continue
            else:
                item_config.update(item.overrides.model_dump())
                item_config["origin"] = "manual_popular"

        # Check existing decision
        existing_dec = await db.execute(
            select(VideoDecision).where(
                VideoDecision.channel_id == channel.id,
                VideoDecision.youtube_id == item.video_id
            )
        )
        decision = existing_dec.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        # Check existing Video and Job records to prevent duplicate reprocessing
        vid_check = await db.execute(select(Video).where(Video.youtube_id == item.video_id))
        existing_v = vid_check.scalar_one_or_none()

        existing_job = None
        if decision and decision.job_id:
            job_check = await db.execute(select(Job).where(Job.id == decision.job_id))
            existing_job = job_check.scalar_one_or_none()

        is_already_completed = False
        if existing_v and existing_v.is_processed:
            is_already_completed = True
        elif existing_job and existing_job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value):
            is_already_completed = True

        if is_already_completed:
            already_processed_count += 1
            items_results.append({
                "video_id": item.video_id,
                "video_title": item.video_title or (existing_v.title if existing_v else None) or (decision.video_title if decision else None) or f"Video {item.video_id}",
                "status": "already_processed",
                "job_id": decision.job_id if decision else (existing_job.id if existing_job else None),
                "decision_id": decision.id if decision else None
            })
            continue

        if existing_job and existing_job.status not in terminal_statuses:
            already_processing_count += 1
            items_results.append({
                "video_id": item.video_id,
                "video_title": item.video_title or decision.video_title,
                "status": "already_processing",
                "job_id": decision.job_id,
                "decision_id": decision.id
            })
            continue

        if decision:
            decision.job_id = None
            decision.status = VideoDecisionStatus.AWAITING_SETTINGS.value
            decision.overrides = item_config
            await db.commit()
            decision_id = decision.id
        else:
            decision_id = str(uuid.uuid4())
            decision = VideoDecision(
                id=decision_id,
                channel_id=channel.id,
                youtube_id=item.video_id,
                video_title=item.video_title or f"Video {item.video_id}",
                youtube_url=item.video_url,
                status=VideoDecisionStatus.AWAITING_SETTINGS.value,
                decision_deadline=now,
                channel_profile_snapshot=channel.processing_profile or DEFAULT_PROCESSING_PROFILE,
                overrides=item_config,
                created_at=now
            )
            db.add(decision)
            await db.commit()

        # Resolve and trigger processing job
        res = resolve_video_decision_sync(
            decision_id=decision_id,
            action="custom" if item.overrides or body.overrides else "apply_defaults",
            custom_overrides=item_config
        )

        job_id = res.get("job_id")
        if job_id:
            queued_count += 1
            items_results.append({
                "video_id": item.video_id,
                "video_title": item.video_title or decision.video_title,
                "status": "queued",
                "job_id": job_id,
                "decision_id": decision_id
            })
        else:
            rejected_count += 1
            items_results.append({
                "video_id": item.video_id,
                "video_title": item.video_title or decision.video_title,
                "status": "failed",
                "error": res.get("error", "Job dispatch failed"),
                "decision_id": decision_id
            })

    total_submitted = len(body.videos)
    shortage = max(0, requested_limit - total_submitted) if requested_limit is not None else 0

    return {
        "total_requested": requested_limit if requested_limit is not None else total_submitted,
        "total_submitted": total_submitted,
        "queued_count": queued_count,
        "already_processing_count": already_processing_count,
        "already_processed_count": already_processed_count,
        "rejected_count": rejected_count,
        "shortage": shortage,
        "items": items_results
    }


# ── Historical Video Discovery & Selection Endpoints ─────────────────────────

@router.post("/{channel_id}/historical-preview")
async def preview_historical_videos(
    channel_id: str,
    body: HistoricalPreviewRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Preview and rank historical channel videos based on recency, view count, or date cutoff.
    Returns preview candidate items annotated with deduplication, processing, and publication state.
    """
    import asyncio
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Resolve destination channel name
    dest_name = "ClipSee"
    effective_dest_id = channel.publish_destination_id
    if effective_dest_id:
        dest_q = await db.execute(select(Channel).where(Channel.id == effective_dest_id))
        d_obj = dest_q.scalar_one_or_none()
        if d_obj:
            dest_name = d_obj.channel_name
    else:
        def_dest_q = await db.execute(
            select(Channel).where(Channel.is_destination == True, Channel.is_default_destination == True)
        )
        def_dest = def_dest_q.scalar_one_or_none()
        if def_dest:
            dest_name = def_dest.channel_name

    effective_privacy = "private"

    if body.mode == HistoricalSelectionMode.NEW_ONLY:
        return {
            "channel_id": channel.id,
            "channel_name": channel.channel_name,
            "mode": "new_only",
            "requested_count": 0,
            "since_date": None,
            "total_discovered": 0,
            "eligible_found": 0,
            "already_processed": 0,
            "will_queue": 0,
            "destination_channel_name": dest_name,
            "effective_privacy": effective_privacy,
            "has_view_counts": True,
            "limitations": [
                "New uploads only mode selected. Historical backfill is bypassed. Continuous monitoring remains active to automatically process future uploads."
            ],
            "message": "New uploads only mode selected. Historical backfill is bypassed. Continuous monitoring remains active to automatically process future uploads.",
            "items": []
        }

    # Fetch candidate videos up to max_search_depth using safe paginated chunking
    raw_items = []
    seen_raw_ids = set()
    offset = 1
    remaining_to_fetch = body.max_search_depth

    while remaining_to_fetch > 0:
        fetch_size = min(100, remaining_to_fetch)
        try:
            discovery = await get_channel_videos(
                channel.channel_url,
                start_index=offset,
                page_size=fetch_size,
                return_page_meta=True
            )
        except Exception as e:
            if offset == 1:
                raise HTTPException(status_code=400, detail=f"Failed to fetch channel videos for preview: {e}")
            break

        page_items = discovery.get("items", []) if isinstance(discovery, dict) else (discovery or [])
        if not page_items:
            break

        added_this_page = 0
        for item in page_items:
            i_id = item.get("id") or item.get("url", "").split("v=")[-1]
            if i_id and i_id not in seen_raw_ids:
                seen_raw_ids.add(i_id)
                raw_items.append(item)
                added_this_page += 1

        offset += len(page_items)
        remaining_to_fetch = body.max_search_depth - len(raw_items)
        if isinstance(discovery, dict) and not discovery.get("has_more", False) or added_this_page == 0:
            break

    # Fetch RSS published dates for precise ISO timestamps if available
    rss_dates = await asyncio.to_thread(fetch_youtube_rss_dates_sync, channel.youtube_channel_id or "")

    # Parse cutoff date boundary
    cutoff_dt = parse_date_boundary(body.since_date)
    cutoff_ts = int(cutoff_dt.timestamp()) if cutoff_dt else None

    # Collect IDs for DB lookup
    candidate_ids = []
    parsed_candidates = []

    for vid in raw_items:
        yt_id = vid.get("id") or vid.get("url", "").split("v=")[-1]
        if not yt_id:
            continue
        candidate_ids.append(yt_id)

        # Thumbnail resolution
        thumb_url = None
        if vid.get("thumbnails"):
            for t in vid.get("thumbnails", []):
                if isinstance(t, dict) and t.get("url"):
                    thumb_url = t.get("url")
                    break
        elif vid.get("thumbnail"):
            thumb_url = vid.get("thumbnail")
        if not thumb_url and not yt_id.startswith("synth_") and not yt_id.startswith("vid_"):
            thumb_url = f"https://i.ytimg.com/vi/{yt_id}/mqdefault.jpg"

        # Date & Timestamp resolution
        sort_ts = 0
        published_display = None
        if yt_id in rss_dates:
            published_display = rss_dates[yt_id]
            try:
                dt = datetime.fromisoformat(published_display)
                sort_ts = int(dt.timestamp())
            except Exception:
                pass

        if sort_ts == 0:
            if vid.get("timestamp"):
                sort_ts = int(vid["timestamp"])
                published_display = datetime.fromtimestamp(sort_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            elif vid.get("upload_date"):
                raw_d = str(vid["upload_date"]).strip()
                if len(raw_d) == 8:
                    try:
                        dt = datetime.strptime(raw_d, "%Y%m%d").replace(tzinfo=timezone.utc)
                        sort_ts = int(dt.timestamp())
                        published_display = dt.strftime("%Y-%m-%d")
                    except Exception:
                        published_display = raw_d
                else:
                    published_display = raw_d

        # View count resolution
        view_cnt = None
        if vid.get("view_count") is not None:
            try:
                view_cnt = int(vid["view_count"])
            except (ValueError, TypeError):
                view_cnt = None

        parsed_candidates.append({
            "id": yt_id,
            "title": vid.get("title") or "Untitled",
            "url": vid.get("url") or f"https://www.youtube.com/watch?v={yt_id}",
            "thumbnail": thumb_url,
            "duration": vid.get("duration"),
            "sort_ts": sort_ts,
            "published_at": published_display,
            "view_count": view_cnt,
        })

    # DB lookups for deduplication against Video and VideoDecision
    processed_q = await db.execute(select(Video).where(or_(Video.youtube_id.in_(candidate_ids), Video.id.in_(candidate_ids))))
    processed_videos = {}
    for v in processed_q.scalars().all():
        if v.youtube_id:
            processed_videos[v.youtube_id] = v
        if v.id:
            processed_videos[v.id] = v

    decisions_q = await db.execute(
        select(VideoDecision).where(
            VideoDecision.channel_id == channel.id,
            VideoDecision.youtube_id.in_(candidate_ids)
        )
    )
    decisions_map = {d.youtube_id: d for d in decisions_q.scalars().all()}

    # Look up clips for processed videos to determine publication status
    clips_status_map = {}
    if processed_videos:
        v_ids = [v.id for v in processed_videos.values()]
        clips_q = await db.execute(
            select(Clip.video_id, Clip.publish_status, Clip.youtube_short_id)
            .where(Clip.video_id.in_(v_ids))
        )
        for v_id, pub_status, yt_short in clips_q.all():
            if pub_status == "published" and yt_short:
                clips_status_map[v_id] = "published"
            elif v_id not in clips_status_map:
                clips_status_map[v_id] = pub_status or "completed"

    # Bulk provenance lookup to identify ClipForge-generated Shorts
    from backend.services.provenance import get_clipforge_shorts_map
    shorts_map = await get_clipforge_shorts_map(db, candidate_ids)

    # Annotate candidates with DB status
    annotated = []
    for c in parsed_candidates:
        yt_id = c["id"]
        v_obj = processed_videos.get(yt_id)
        d_obj = decisions_map.get(yt_id)
        cf_short = shorts_map.get(yt_id)

        is_gen_short = cf_short is not None
        is_processed = bool(v_obj is not None or (d_obj and d_obj.job_id is not None) or is_gen_short)
        processing_status = "unprocessed"
        publication_status = "none"

        if is_gen_short:
            processing_status = "completed"
            publication_status = "clipforge_short"
        elif v_obj:
            processing_status = "completed"
            publication_status = clips_status_map.get(v_obj.id, "processed")
        elif d_obj:
            if d_obj.job_id:
                processing_status = "processing"
            else:
                processing_status = d_obj.status or "awaiting_settings"

        # Check date filter (inclusive)
        is_date_eligible = True
        if cutoff_ts is not None and c["sort_ts"] > 0:
            if c["sort_ts"] < cutoff_ts:
                is_date_eligible = False

        c["is_processed"] = is_processed
        c["is_generated_short"] = is_gen_short
        c["parent_source_id"] = cf_short["parent_source_id"] if cf_short else None
        c["parent_source_title"] = cf_short["parent_source_title"] if cf_short else None
        c["processing_status"] = processing_status
        c["publication_status"] = publication_status
        c["is_date_eligible"] = is_date_eligible
        c["decision_id"] = d_obj.id if d_obj else None
        c["job_id"] = d_obj.job_id if d_obj else None
        annotated.append(c)

    # Filter eligible items: Exclude ClipForge-generated Shorts and apply date cutoff if requested
    if body.mode in (HistoricalSelectionMode.UPLOADED_SINCE, HistoricalSelectionMode.LATEST) and cutoff_ts is not None:
        eligible_items = [c for c in annotated if not c.get("is_generated_short") and c["is_date_eligible"]]
    else:
        eligible_items = [c for c in annotated if not c.get("is_generated_short")]

    limitations = []
    has_view_counts = True

    # Sorting with deterministic tie-breakers
    if body.mode == HistoricalSelectionMode.MOST_VIEWED:
        missing_views = sum(1 for c in eligible_items if c["view_count"] is None)
        if missing_views > 0:
            has_view_counts = False
            limitations.append(f"{missing_views} candidate video(s) did not expose numeric view counts in YouTube metadata.")
        if len(raw_items) >= body.max_search_depth:
            limitations.append(f"Rankings are evaluated across the {len(raw_items)} scanned channel videos. Older videos beyond search depth are not ranked.")
        # Sort by view_count DESC (missing last), then sort_ts DESC, then id ASC
        eligible_items.sort(key=lambda x: (-(x["view_count"] if x["view_count"] is not None else -1), -x["sort_ts"], x["id"]))
    else:
        # Sort by sort_ts DESC, then id ASC
        eligible_items.sort(key=lambda x: (-x["sort_ts"], x["id"]))

    total_discovered = len(annotated)
    eligible_found = len(eligible_items)
    already_processed_count = sum(1 for c in eligible_items if c["is_processed"])

    # Determine which uncompleted items should be queued to satisfy requested count
    target_unprocessed = [c for c in eligible_items if not c["is_processed"]][:body.count]
    target_queue_ids = {c["id"] for c in target_unprocessed}

    # Present top preview items
    preview_limit = max(body.count, min(15, len(eligible_items)))
    preview_slice = eligible_items[:preview_limit]

    items_output = []
    for c in preview_slice:
        items_output.append({
            "id": c["id"],
            "title": c["title"],
            "url": c["url"],
            "thumbnail": c["thumbnail"],
            "duration": c["duration"],
            "published_at": c["published_at"],
            "view_count": c["view_count"],
            "is_processed": c["is_processed"],
            "processing_status": c["processing_status"],
            "publication_status": c["publication_status"],
            "selected_for_queue": (c["id"] in target_queue_ids),
            "decision_id": c.get("decision_id"),
            "job_id": c.get("job_id"),
        })

    will_queue = len(target_queue_ids)

    scope_type = "exhaustive" if len(raw_items) < body.max_search_depth else "bounded"
    candidate_scope = {
        "scanned_count": len(raw_items),
        "search_depth_limit": body.max_search_depth,
        "scope_type": scope_type,
        "description": f"Evaluated {len(raw_items)} most recent channel videos (Search Depth: {body.max_search_depth}). {'All available channel videos included.' if scope_type == 'exhaustive' else f'Rankings reflect this verified {len(raw_items)}-video scan window.'}"
    }
    if scope_type == "bounded":
        limitations.append(f"Candidate scope notice: Evaluated the {len(raw_items)} most recent channel uploads. Candidates older than rank {body.max_search_depth} are outside this scan window.")

    return {
        "channel_id": channel.id,
        "channel_name": channel.channel_name,
        "mode": body.mode.value,
        "requested_count": body.count,
        "since_date": body.since_date,
        "total_discovered": total_discovered,
        "eligible_found": eligible_found,
        "already_processed": already_processed_count,
        "will_queue": will_queue,
        "destination_channel_name": dest_name,
        "effective_privacy": effective_privacy,
        "has_view_counts": has_view_counts,
        "candidate_scope": candidate_scope,
        "limitations": limitations,
        "items": items_output
    }


@router.post("/{channel_id}/historical-process")
async def process_historical_batch(
    channel_id: str,
    body: HistoricalProcessRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Queue selected historical source videos into the native monitoring pipeline.
    Preserves ongoing channel Auto Monitor and Auto Publish configurations.
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if body.mode == HistoricalSelectionMode.NEW_ONLY:
        channel.is_active = True
        await db.commit()
        return {
            "channel_id": channel.id,
            "channel_name": channel.channel_name,
            "mode": "new_only",
            "message": "Continuous Auto Monitor active for future uploads. Historical videos were not backfilled.",
            "total_selected": 0,
            "queued_count": 0,
            "already_processing_count": 0,
            "results": []
        }

    if not body.video_ids:
        raise HTTPException(status_code=400, detail="No video IDs selected for historical processing.")

    # Deduplicate while preserving order
    seen = set()
    unique_vids = []
    for vid in body.video_ids:
        if vid and vid not in seen:
            seen.add(vid)
            unique_vids.append(vid)

    # Section 5.4 Count Enforcement:
    requested_limit = body.requested_count
    if requested_limit is not None:
        if len(unique_vids) > requested_limit:
            raise HTTPException(
                status_code=422,
                detail=f"Selected historical video IDs ({len(unique_vids)}) exceeds requested_count ({requested_limit})."
            )

    # Bounded safety cap (maximum 20 videos per historical batch)
    MAX_HISTORICAL_BATCH = 20
    if len(unique_vids) > MAX_HISTORICAL_BATCH:
        unique_vids = unique_vids[:MAX_HISTORICAL_BATCH]

    # Effective profile
    effective_config = dict(channel.processing_profile or DEFAULT_PROCESSING_PROFILE)
    effective_config["origin"] = "manual_historical"
    if body.overrides:
        if isinstance(body.overrides, dict):
            try:
                val = ChannelProcessingProfile(**body.overrides)
                effective_config.update(val.model_dump())
                effective_config["origin"] = "manual_historical"
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Invalid profile overrides: {e}")
        else:
            effective_config.update(body.overrides.model_dump())
            effective_config["origin"] = "manual_historical"

    terminal_statuses = [
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_FAILURES.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]

    results = []
    queued_count = 0
    already_processing_count = 0
    already_processed_count = 0

    # Bulk provenance lookup to reject ClipForge-generated Shorts
    from backend.services.provenance import get_clipforge_shorts_map
    shorts_map = await get_clipforge_shorts_map(db, unique_vids)

    for ytid in unique_vids:
        # Guard: Reject ClipForge-generated Shorts to prevent self-ingestion
        if ytid in shorts_map:
            cf_info = shorts_map[ytid]
            results.append({
                "video_id": ytid,
                "title": cf_info.get("clip_title") or f"Short {ytid}",
                "status": "rejected_clipforge_short",
                "error": f"Self-ingestion blocked: '{ytid}' is an output Short generated from '{cf_info.get('parent_source_title')}'. Output Shorts cannot be processed as source inputs."
            })
            continue

        # Query existing decision
        dec_q = await db.execute(
            select(VideoDecision).where(
                VideoDecision.channel_id == channel.id,
                VideoDecision.youtube_id == ytid
            )
        )
        decision = dec_q.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        # Check existing Video and Job records to prevent duplicate reprocessing
        vid_check = await db.execute(select(Video).where(Video.youtube_id == ytid))
        existing_v = vid_check.scalar_one_or_none()

        existing_job = None
        if decision and decision.job_id:
            job_check = await db.execute(select(Job).where(Job.id == decision.job_id))
            existing_job = job_check.scalar_one_or_none()

        is_already_completed = False
        if existing_v and existing_v.is_processed:
            is_already_completed = True
        elif existing_job and existing_job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value):
            is_already_completed = True

        if is_already_completed:
            already_processed_count += 1
            results.append({
                "video_id": ytid,
                "title": (existing_v.title if existing_v else None) or (decision.video_title if decision else None) or f"Video {ytid}",
                "status": "already_processed",
                "job_id": decision.job_id if decision else (existing_job.id if existing_job else None),
                "decision_id": decision.id if decision else None
            })
            continue

        if existing_job and existing_job.status not in terminal_statuses:
            already_processing_count += 1
            results.append({
                "video_id": ytid,
                "title": decision.video_title,
                "status": "already_processing",
                "job_id": decision.job_id,
                "decision_id": decision.id
            })
            continue

        if decision:
            decision.job_id = None
            decision.status = VideoDecisionStatus.AWAITING_SETTINGS.value
            decision.overrides = effective_config
            await db.commit()
            decision_id = decision.id
        else:
            decision_id = str(uuid.uuid4())
            decision = VideoDecision(
                id=decision_id,
                channel_id=channel.id,
                youtube_id=ytid,
                video_title=f"Video {ytid}",
                youtube_url=f"https://www.youtube.com/watch?v={ytid}",
                status=VideoDecisionStatus.AWAITING_SETTINGS.value,
                decision_deadline=now,
                channel_profile_snapshot=channel.processing_profile or DEFAULT_PROCESSING_PROFILE,
                overrides=effective_config,
                created_at=now
            )
            db.add(decision)
            await db.commit()

        # Trigger native Celery resolution
        res = resolve_video_decision_sync(
            decision_id=decision_id,
            action="custom" if body.overrides else "apply_defaults",
            custom_overrides=effective_config
        )

        job_id = res.get("job_id")
        if job_id:
            queued_count += 1
            results.append({
                "video_id": ytid,
                "title": decision.video_title,
                "status": "queued",
                "job_id": job_id,
                "decision_id": decision_id
            })
        else:
            results.append({
                "video_id": ytid,
                "title": decision.video_title,
                "status": "failed",
                "error": res.get("error", "Failed to start Celery job"),
                "decision_id": decision_id
            })

    # Preserve continuous monitoring
    channel.is_active = True
    await db.commit()

    total_selected = len(unique_vids)
    shortage = max(0, requested_limit - total_selected) if requested_limit is not None else 0

    return {
        "channel_id": channel.id,
        "channel_name": channel.channel_name,
        "mode": body.mode.value,
        "total_requested": requested_limit if requested_limit is not None else total_selected,
        "total_selected": total_selected,
        "queued_count": queued_count,
        "already_processing_count": already_processing_count,
        "already_processed_count": already_processed_count,
        "shortage": shortage,
        "results": results
    }


# ── Decision Lifecycle Endpoints ─────────────────────────────────────────────

@router.get("/decisions/pending")
async def list_pending_decisions(db: AsyncSession = Depends(get_db)):
    """List all currently active decisions in countdown or customization."""
    result = await db.execute(
        select(VideoDecision, Channel.channel_name)
        .join(Channel, VideoDecision.channel_id == Channel.id)
        .where(VideoDecision.status.in_([
            VideoDecisionStatus.AWAITING_SETTINGS.value,
            VideoDecisionStatus.CUSTOMIZING.value,
        ]))
        .order_by(desc(VideoDecision.created_at))
    )
    rows = result.all()
    now = datetime.now(timezone.utc)

    items = []
    for d, ch_name in rows:
        remaining_seconds = 0
        if d.status == VideoDecisionStatus.AWAITING_SETTINGS.value and d.decision_deadline:
            deadline = d.decision_deadline if d.decision_deadline.tzinfo else d.decision_deadline.replace(tzinfo=timezone.utc)
            remaining_seconds = max(0, int((deadline - now).total_seconds()))
        elif d.status == VideoDecisionStatus.CUSTOMIZING.value and d.customization_lease_expires_at:
            lease = d.customization_lease_expires_at if d.customization_lease_expires_at.tzinfo else d.customization_lease_expires_at.replace(tzinfo=timezone.utc)
            remaining_seconds = max(0, int((lease - now).total_seconds()))

        items.append({
            "id": d.id,
            "channel_id": d.channel_id,
            "channel_name": ch_name,
            "youtube_id": d.youtube_id,
            "video_title": d.video_title,
            "youtube_url": d.youtube_url,
            "thumbnail_url": d.video_thumbnail,
            "status": d.status,
            "decision_deadline": d.decision_deadline.isoformat() if d.decision_deadline else None,
            "remaining_seconds": remaining_seconds,
            "channel_profile_snapshot": d.channel_profile_snapshot,
            "overrides": {k: v for k, v in (d.overrides or {}).items() if k != "_lease_token"} if isinstance(d.overrides, dict) else d.overrides,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "created_at_ist": format_ist(d.created_at),
        })

    return items


def _handle_decision_result(res: dict, decision_id: str):
    """
    Handle resolve_video_decision_sync result dictionary and convert error/conflict
    signals into appropriate HTTP 404, 409, or 400 exceptions.
    """
    if res.get("status") == "not_found" or res.get("status_code") == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=res.get("error", f"Decision {decision_id} not found")
        )
    if res.get("conflict"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": res.get("error", f"Conflict on decision {decision_id}"),
                "conflict_type": res.get("conflict_type", "conflict"),
                "status": res.get("status"),
                "job_id": res.get("job_id"),
                "lease_expires_at": res.get("lease_expires_at"),
            }
        )
    if "error" in res:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res["error"]
        )
    return res


@router.post("/decisions/{decision_id}/apply-defaults")
async def apply_defaults_decision(
    decision_id: str,
    body: CustomizeDecisionRequest | None = None,
    channel_id: str | None = Query(default=None),
):
    """User manually resolves decision immediately using channel default profile."""
    lease_token = body.lease_token if body else None
    force = body.force if body else False
    res = resolve_video_decision_sync(
        decision_id=decision_id,
        action="apply_defaults",
        lease_token=lease_token,
        force_customize=force,
        channel_id=channel_id,
    )
    return _handle_decision_result(res, decision_id)


@router.post("/decisions/{decision_id}/customize")
async def customize_decision(
    decision_id: str,
    body: CustomizeDecisionRequest | None = None,
    channel_id: str | None = Query(default=None),
):
    """User opens the customization modal, granting a 120s customization lease."""
    lease_token = body.lease_token if body else None
    force = body.force if body else False
    res = resolve_video_decision_sync(
        decision_id=decision_id,
        action="customize",
        lease_token=lease_token,
        force_customize=force,
        channel_id=channel_id,
    )
    return _handle_decision_result(res, decision_id)


@router.post("/decisions/{decision_id}/save-and-process")
async def save_and_process_decision(
    decision_id: str,
    body: SaveAndProcessRequest,
    channel_id: str | None = Query(default=None),
):
    """User saves per-video custom overrides and immediately triggers pipeline processing."""
    overrides_dict = {}
    if body.overrides:
        if isinstance(body.overrides, dict):
            try:
                validated = ChannelProcessingProfile(**body.overrides)
                overrides_dict = validated.model_dump()
            except Exception as val_err:
                raise HTTPException(status_code=422, detail=f"Invalid overrides: {val_err}")
        else:
            overrides_dict = body.overrides.model_dump()

    res = resolve_video_decision_sync(
        decision_id=decision_id,
        action="custom",
        custom_overrides=overrides_dict,
        expected_status=body.expected_status,
        lease_token=body.lease_token,
        channel_id=channel_id,
    )
    return _handle_decision_result(res, decision_id)


@router.post("/decisions/{decision_id}/cancel")
async def cancel_decision(
    decision_id: str,
    channel_id: str | None = Query(default=None),
):
    """User cancels video processing; decision permanently remains cancelled."""
    res = resolve_video_decision_sync(
        decision_id=decision_id,
        action="cancel",
        channel_id=channel_id,
    )
    return _handle_decision_result(res, decision_id)


@router.get("/decisions/history")
async def list_decision_history(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full audit history of video decisions with IST and UTC timestamps and failure provenance."""
    result = await db.execute(
        select(
            VideoDecision,
            Channel.channel_name,
            Job.status,
            Job.pipeline_started_at,
            Job.completed_at,
            Job.error_message,
            Job.current_step,
            Job.source_title,
            Job.source_url,
            Video.title,
            Video.youtube_id
        )
        .join(Channel, VideoDecision.channel_id == Channel.id)
        .outerjoin(Job, VideoDecision.job_id == Job.id)
        .outerjoin(Video, Job.video_id == Video.id)
        .order_by(desc(VideoDecision.created_at))
        .limit(limit)
    )
    rows = result.all()

    # Pre-fetch any clip origins where dec.youtube_id corresponds to a generated Short
    yt_ids = [dec.youtube_id for dec, *_ in rows if dec.youtube_id]
    origin_map = {}
    if yt_ids:
        clip_origins = await db.execute(
            select(
                Clip.youtube_short_id,
                Clip.title.label("clip_title"),
                Video.id.label("origin_video_id"),
                Video.youtube_id.label("origin_youtube_id"),
                Video.youtube_url.label("origin_youtube_url"),
                Video.title.label("origin_video_title"),
                Video.thumbnail_url.label("origin_thumbnail_url"),
            )
            .join(Video, Clip.video_id == Video.id)
            .where(Clip.youtube_short_id.in_(yt_ids))
        )
        origin_map = {row.youtube_short_id: row for row in clip_origins.all()}

    items = []
    for dec, ch_name, job_status, started_at, completed_at, err_msg, cur_step, j_src_title, j_src_url, v_title, v_yt_id in rows:
        canonical_yt_id = dec.youtube_id or v_yt_id or (extract_youtube_id(dec.youtube_url or j_src_url or "") if (dec.youtube_url or j_src_url) else None)
        canonical_title = dec.video_title or v_title or j_src_title or "Untitled Source Video"
        canonical_url = dec.youtube_url or (f"https://www.youtube.com/watch?v={canonical_yt_id}" if canonical_yt_id else None)

        thumb = dec.video_thumbnail

        orig = origin_map.get(dec.youtube_id)
        if orig:
            is_generated_short = True
            generated_short_id = dec.youtube_id
            generated_short_url = f"https://www.youtube.com/shorts/{dec.youtube_id}"
            generated_short_title = dec.video_title or orig.clip_title

            source_yt_id = orig.origin_youtube_id or canonical_yt_id
            source_title = orig.origin_video_title or canonical_title
            source_url = orig.origin_youtube_url or (f"https://www.youtube.com/watch?v={source_yt_id}" if source_yt_id else None)
            if not thumb and orig.origin_thumbnail_url:
                thumb = orig.origin_thumbnail_url
        else:
            is_generated_short = False
            generated_short_id = None
            generated_short_url = None
            generated_short_title = None

            source_yt_id = canonical_yt_id
            source_title = canonical_title
            source_url = canonical_url

        if not thumb and source_yt_id and not source_yt_id.startswith("synth_") and not source_yt_id.startswith("vid_"):
            thumb = f"https://i.ytimg.com/vi/{source_yt_id}/mqdefault.jpg"

        # Sanitize user-facing error message to protect client UI from raw SQL/driver dumps
        clean_err = sanitize_user_facing_error(err_msg)

        items.append({
            "id": dec.id,
            "channel_id": dec.channel_id,
            "channel_name": ch_name,
            "youtube_id": canonical_yt_id,
            "video_title": canonical_title,
            "is_generated_short": is_generated_short,
            "generated_short_id": generated_short_id,
            "generated_short_url": generated_short_url,
            "generated_short_title": generated_short_title,
            "source_video_title": source_title,
            "source_youtube_id": source_yt_id,
            "source_youtube_url": source_url,
            "youtube_url": canonical_url,
            "thumbnail_url": thumb,
            "status": dec.status,
            "resolved_at": dec.resolved_at.isoformat() if dec.resolved_at else None,
            "resolved_at_ist": format_ist(dec.resolved_at),
            "overrides": dec.overrides,
            "job_id": dec.job_id,
            "job_status": job_status,
            "job_error": clean_err,
            "error_message": clean_err,
            "current_step": cur_step,
            "pipeline_started_at": started_at.isoformat() if started_at else None,
            "pipeline_started_at_ist": format_ist(started_at),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "completed_at_ist": format_ist(completed_at),
            "created_at": dec.created_at.isoformat() if dec.created_at else None,
            "created_at_ist": format_ist(dec.created_at),
        })

    return items
