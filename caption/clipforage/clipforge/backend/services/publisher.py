"""
YouTube Publisher Service — uploads clips to YouTube Shorts
Handles OAuth2 flow and video upload via YouTube Data API v3
"""
import json
import os
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from backend.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def _resolve_token_dir() -> Path:
    """Resolve the directory containing YouTube tokens (Docker /app or host filesystem)."""
    base = Path(settings.YOUTUBE_TOKEN_FILE).parent
    if base.exists():
        return base
    workspace_dir = Path(__file__).resolve().parent.parent.parent / "tokens"
    if workspace_dir.exists():
        return workspace_dir
    return base


def _resolve_token_file(channel_id: str = None) -> Path:
    """Resolve the token file path cross-platform."""
    token_dir = _resolve_token_dir()
    if channel_id:
        return token_dir / f"youtube_token_{channel_id}.json"
    return token_dir / "youtube_token.json"


def get_youtube_client(channel_id: str = None):
    """Build authenticated YouTube API client with robust ID and token resolution."""
    creds = None
    resolved_channel_id = channel_id

    if channel_id:
        # If channel_id is an internal DB ID (non-UC prefix), resolve to youtube_channel_id
        if not channel_id.startswith("UC"):
            try:
                from backend.models.database import SyncSessionLocal
                from backend.models.models import Channel
                with SyncSessionLocal() as session:
                    ch = session.query(Channel).filter(
                        (Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)
                    ).first()
                    if ch and ch.youtube_channel_id:
                        resolved_channel_id = ch.youtube_channel_id
            except Exception:
                pass

    token_file = _resolve_token_file(resolved_channel_id)

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        else:
            raise ValueError(f"YouTube authorization required for destination channel {channel_id or 'default'}. No valid credentials found.")

    client = build("youtube", "v3", credentials=creds)
    
    if resolved_channel_id and resolved_channel_id.startswith("UC"):
        try:
            resp = client.channels().list(part="id", mine=True).execute()
            if not resp.get("items"):
                raise ValueError("Could not determine authenticated YouTube channel.")
            auth_channel_id = resp["items"][0]["id"]
            if auth_channel_id != resolved_channel_id:
                raise ValueError(f"Credential mismatch: requested channel {resolved_channel_id} but authenticated as {auth_channel_id}")
        except Exception as e:
            raise ValueError(f"Channel identity verification failed: {e}")

    return client


class UnsafeStatusRemediationError(ValueError):
    """
    Raised when a YouTube status update payload cannot be constructed safely
    without violating legal/COPPA declarations or privacy invariants
    (e.g., unknown selfDeclaredMadeForKids, or presence of scheduled publishAt).
    """
    pass


def _build_safe_status_update_body(
    video_id: str,
    existing_status: dict | None,
    desired_privacy: str = "private",
    fallback_license: str | None = None,
    fallback_embeddable: bool | None = None,
    fallback_public_stats_viewable: bool | None = None,
    fallback_made_for_kids: bool | None = None,
    fallback_contains_synthetic_media: bool | None = None,
    allow_cancel_scheduled_publish: bool = False,
) -> dict:
    """
    Build a safe YouTube videos.update(part="status") request body conforming to
    official YouTube Data API v3 contracts and field deletion semantics.

    API Semantic Contract:
    YouTube Data API v3 videos.update uses full replacement (PUT) semantics for
    each specified part. Omitting an existing property in an updated part generally
    deletes it or resets it to platform defaults.

    Field Classification & Safeguards:
    1. Read-Only Fields (STRICTLY EXCLUDED):
       - 'uploadStatus', 'failureReason', 'rejectionReason', 'madeForKids'.
       - Submitting any of these causes HTTP 400 Bad Request.
       - 'madeForKids' is YouTube's automated classifier evaluation and must
         NEVER be copied into 'selfDeclaredMadeForKids'.

    2. Mutable Fields Subject to Deletion upon Omission (PRESERVE OR FAIL SAFE):
       - 'license': Must be "youtube" | "creativeCommon". If missing from remote
         status and fallback is unknown, withholding is enforced to prevent
         silently changing or deleting copyright licensing.
       - 'embeddable': Boolean. If missing from remote status and fallback is unknown,
         withholding is enforced to prevent silently deleting embedding permissions.
         Explicit False values are strictly preserved.
       - 'publicStatsViewable': Boolean. If missing from remote status and fallback
         is unknown, withholding is enforced to prevent silently deleting public
         statistics settings. Explicit False values are strictly preserved.

    3. Exempt from Deletion upon Omission (SAFE TO OMIT WHEN UNKNOWN):
       - 'selfDeclaredMadeForKids': Official YouTube Data API documentation explicitly
         states that status.selfDeclaredMadeForKids is EXEMPT from omitted-property
         deletion. It will NOT be deleted or overwritten if omitted. If the uploader's
         declaration is reliably known, it is preserved; if unknown, it is safely
         omitted, allowing privacy remediation to proceed without fabricating a
         COPPA declaration.
       - 'containsSyntheticMedia': Official YouTube Data API documentation explicitly
         states that status.containsSyntheticMedia is EXEMPT from omitted-property
         deletion. If known, it is preserved; if unknown, it is safely omitted.

    4. Scheduled Publication ('publishAt'):
       - A detected 'publishAt' automatically transitions a video to public at the
         scheduled timestamp, directly violating the private-only invariant.
       - Automated remediation is withheld unless 'allow_cancel_scheduled_publish' is True.
    """
    existing = existing_status if isinstance(existing_status, dict) else {}

    # 1. Scheduled publication check
    publish_at = existing.get("publishAt")
    if publish_at:
        if not allow_cancel_scheduled_publish:
            raise UnsafeStatusRemediationError(
                f"Cannot safely remediate video {video_id}: existing status contains scheduled publication "
                f"publishAt='{publish_at}', which is incompatible with private-only enforcement. "
                f"Automated status update withheld for operator manual review."
            )
        else:
            logger.info(
                f"[Publish Safety] Explicit policy applied: canceling scheduled publishAt='{publish_at}' for video {video_id}."
            )

    status_body: dict = {
        "privacyStatus": desired_privacy,
    }

    # 2. License: non-exempt from deletion ("youtube" | "creativeCommon")
    license_val = existing.get("license") if existing.get("license") in ("youtube", "creativeCommon") else None
    if not license_val and fallback_license in ("youtube", "creativeCommon"):
        license_val = fallback_license

    if license_val:
        status_body["license"] = license_val
    else:
        raise UnsafeStatusRemediationError(
            f"Cannot safely determine license for video {video_id}: "
            f"property is missing from remote status and fallback is unknown. "
            f"Automated status update withheld to prevent overwriting or deleting copyright license."
        )

    # 3. Embeddable: non-exempt from deletion (boolean, preserve explicit False or True)
    embeddable_val = None
    if "embeddable" in existing and isinstance(existing["embeddable"], bool):
        embeddable_val = existing["embeddable"]
    elif isinstance(fallback_embeddable, bool):
        embeddable_val = fallback_embeddable

    if embeddable_val is not None:
        status_body["embeddable"] = embeddable_val
    else:
        raise UnsafeStatusRemediationError(
            f"Cannot safely determine embeddable for video {video_id}: "
            f"property is missing from remote status and fallback is unknown. "
            f"Automated status update withheld to prevent destructive property deletion."
        )

    # 4. Public stats viewable: non-exempt from deletion (boolean, preserve explicit False or True)
    public_stats_val = None
    if "publicStatsViewable" in existing and isinstance(existing["publicStatsViewable"], bool):
        public_stats_val = existing["publicStatsViewable"]
    elif isinstance(fallback_public_stats_viewable, bool):
        public_stats_val = fallback_public_stats_viewable

    if public_stats_val is not None:
        status_body["publicStatsViewable"] = public_stats_val
    else:
        raise UnsafeStatusRemediationError(
            f"Cannot safely determine publicStatsViewable for video {video_id}: "
            f"property is missing from remote status and fallback is unknown. "
            f"Automated status update withheld to prevent destructive property deletion."
        )

    # 5. Made for kids: EXEMPT from deletion upon omission per YouTube API documentation.
    # Never copy read-only madeForKids (platform evaluation).
    # Never default an unknown declaration to False.
    # If declaration is known, preserve it; if unknown, safely omit it.
    if "selfDeclaredMadeForKids" in existing and isinstance(existing["selfDeclaredMadeForKids"], bool):
        status_body["selfDeclaredMadeForKids"] = existing["selfDeclaredMadeForKids"]
    elif isinstance(fallback_made_for_kids, bool):
        status_body["selfDeclaredMadeForKids"] = fallback_made_for_kids
    # Else: omit from status_body (preserves existing setting without fabricating declaration)

    # 6. Contains synthetic media: EXEMPT from deletion upon omission per YouTube API documentation.
    if "containsSyntheticMedia" in existing and isinstance(existing["containsSyntheticMedia"], bool):
        status_body["containsSyntheticMedia"] = existing["containsSyntheticMedia"]
    elif isinstance(fallback_contains_synthetic_media, bool):
        status_body["containsSyntheticMedia"] = fallback_contains_synthetic_media
    # Else: omit from status_body (preserves existing disclosure)

    # Strictly exclude read-only fields: uploadStatus, failureReason, rejectionReason, madeForKids

    return {
        "id": video_id,
        "status": status_body,
    }


def sanitize_youtube_tags(raw_tags: list[str] | None, max_total_chars: int = 450) -> list[str]:
    """
    Sanitizes tags for YouTube Data API snippet.tags:
    1. Removes '#' prefixes, '<', '>', newlines.
    2. Deduplicates case-insensitively while preserving original order.
    3. Keeps total joined character length under YouTube limits (<= 500 chars, default 450).
    """
    if not raw_tags:
        return []
    
    clean_tags: list[str] = []
    seen = set()
    current_length = 0

    for t in raw_tags:
        if not t:
            continue
        cleaned = str(t).strip().lstrip("#").replace("<", "").replace(">", "").replace("\n", " ").strip()
        if not cleaned:
            continue
        lower_t = cleaned.lower()
        if lower_t in seen:
            continue
        
        tag_cost = len(cleaned) + (1 if clean_tags else 0)
        if current_length + tag_cost > max_total_chars:
            break
            
        clean_tags.append(cleaned)
        seen.add(lower_t)
        current_length += tag_cost

    return clean_tags


def upload_short(
    video_path: Path,
    title: str,
    description: str = "",
    tags: list[str] = None,
    thumbnail_path: Path = None,
    privacy: str = "private",
    made_for_kids: bool | None = None,
    category: str = "22",
    license_type: str | None = None,
    idempotency_key: str = None,
    channel_id: str = None,
    progress_callback: callable = None,
    clip_id: str = None,
) -> dict:
    """
    Upload a video as a YouTube Short.
    Returns: { id, url, title, privacy, status }
    """
    if not channel_id and clip_id:
        from backend.models.database import SyncSessionLocal
        with SyncSessionLocal() as session:
            channel_id = sync_resolve_publish_destination(clip_id, session)

    if not channel_id:
        raise ValueError("Destination channel_id is required for publishing. Publishing without an explicit destination or falling back to a global token is strictly prohibited.")

    # Resolve metadata provenance and ensure original-source attribution if clip_id is provided
    effective_tags = list(tags) if tags else []
    effective_category = category or "22"
    effective_desc = description or ""

    if clip_id:
        try:
            from backend.models.database import SyncSessionLocal
            from backend.models.models import Clip, Video
            from backend.services.source_metadata_engine import load_persisted_source_metadata
            from backend.services.description_attribution import build_attributed_description

            with SyncSessionLocal() as session:
                clip = session.query(Clip).filter_by(id=clip_id).first()
                if clip:
                    # Inherit category if caller passed default
                    if (not effective_category or effective_category == "22") and clip.category:
                        effective_category = clip.category
                    
                    # Inherit tags if caller passed empty
                    if not effective_tags and clip.tags:
                        try:
                            parsed_tags = json.loads(clip.tags) if clip.tags.startswith("[") else [t.strip() for t in clip.tags.split(",") if t.strip()]
                            effective_tags = parsed_tags
                        except Exception:
                            pass

                    video = session.query(Video).filter_by(id=clip.video_id).first() if clip.video_id else None
                    source_meta = load_persisted_source_metadata(clip.video_id) if clip.video_id else None
                    if source_meta:
                        if not effective_tags and source_meta.seo_tags:
                            effective_tags = list(source_meta.seo_tags)
                        if (not effective_category or effective_category == "22") and source_meta.youtube_category_id:
                            effective_category = source_meta.youtube_category_id

                    # Check description attribution
                    source_yt_url = (video.youtube_url if video else None) or (source_meta.source_youtube_url if source_meta else None)
                    source_title = (video.title if video else None) or (source_meta.source_title if source_meta else None)
                    source_channel = getattr(video, "channel_name", None)
                    hashtags = source_meta.description_hashtags if source_meta else None

                    # If description does not have "Original video:" and source is a valid YouTube video
                    if source_yt_url and "Original video:" not in effective_desc:
                        effective_desc = build_attributed_description(
                            clip_description=effective_desc,
                            source_youtube_url=source_yt_url,
                            source_title=source_title,
                            source_channel=source_channel,
                            hashtags=hashtags,
                            include_attribution=True,
                            include_hashtags=True,
                        )
        except Exception as prov_err:
            logger.warning(f"[Publisher] Metadata provenance resolution warning: {prov_err}")

    # Build sanitized tags for snippet.tags (preserving caller's tags + Shorts keywords)
    cleaned_tags = sanitize_youtube_tags(effective_tags + ["Shorts", "viral", "trending"])

    # Ensure #Shorts is present in description without duplicate blocks
    short_desc = effective_desc
    if "#Shorts" not in short_desc and "#shorts" not in short_desc:
        short_desc = f"{short_desc}\n\n#Shorts #viral #trending".strip()
    if idempotency_key and f"[idemp:{idempotency_key}]" not in short_desc:
        short_desc += f"\n\n[idemp:{idempotency_key}]"

    # Test Mode execution
    if getattr(settings, "PUBLISH_MODE", "prod") == "test":
        return _mock_upload_short(
            title=title,
            description=short_desc,
            idempotency_key=idempotency_key,
            progress_callback=progress_callback,
            clip_id=clip_id,
            tags=cleaned_tags,
            privacy=privacy,
            made_for_kids=made_for_kids,
            category=effective_category,
            license_type=license_type or "youtube",
        )

    # Strict Safety Invariant: Live automated uploads MUST be Private
    # User instruction strictly requires Private visibility for all automated uploads.
    # Never fall back to Public or Unlisted in automated workflows.
    effective_privacy = "private"
    if privacy and privacy != "private":
        logger.warning(
            f"[Publish Safety] Automated upload clamped privacy from '{privacy}' to 'private'."
        )

    # Strict Publishing Cadence Invariant: Destination-Scoped 2 Minutes
    # Note: Cadence reservation and non-blocking worker queue rescheduling (retry countdown)
    # is enforced at the task boundary (publish_task / publish_clip_task). Completion timestamp
    # is recorded upon successful upload completion below.

    youtube = get_youtube_client(channel_id=channel_id)

    # YouTube Shorts: add #Shorts to title/description
    if "#Shorts" not in title and "#shorts" not in title:
        short_title = f"{title} #Shorts"
    else:
        short_title = title

    status_payload = {
        "privacyStatus": effective_privacy,
    }
    if license_type:
        status_payload["license"] = license_type
    if made_for_kids is not None:
        status_payload["selfDeclaredMadeForKids"] = bool(made_for_kids)

    body = {
        "snippet": {
            "title": short_title[:100],
            "description": short_desc[:5000],
            "tags": cleaned_tags,
            "categoryId": effective_category,
        },
        "status": status_payload,
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,  # 5MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        chunk_status, response = request.next_chunk()
        if chunk_status and progress_callback:
            try:
                progress_callback(chunk_status.resumable_progress, chunk_status.total_size, chunk_status.progress())
            except Exception:
                pass

    if not response or not isinstance(response, dict) or "id" not in response:
        raise RuntimeError(f"YouTube upload failed: Incomplete API response received: {response}")

    video_id = response["id"]
    status_block = response.get("status") if isinstance(response.get("status"), dict) else None
    confirmed_privacy = status_block.get("privacyStatus") if status_block else None
    initial_remote_privacy = confirmed_privacy

    remediation_status = None

    # Step A: Missing or Ambiguous status handling
    # If insert response omitted privacyStatus (or status block), do not assume public or private.
    # Query remote status with a read-only videos().list(part="status", id=video_id) call.
    if not confirmed_privacy:
        logger.warning(
            f"[Publish Safety] YouTube API insert response for video {video_id} omitted privacyStatus. "
            f"Performing read-only status query to establish remote privacy..."
        )
        try:
            inspect_resp = youtube.videos().list(part="status", id=video_id).execute()
            items = inspect_resp.get("items", []) if isinstance(inspect_resp, dict) else []
            if items and isinstance(items[0], dict):
                remote_status_block = items[0].get("status")
                if isinstance(remote_status_block, dict):
                    status_block = remote_status_block
                    confirmed_privacy = status_block.get("privacyStatus")
                    initial_remote_privacy = confirmed_privacy
                    logger.info(
                        f"[Publish Safety] Read-only status query established remote privacyStatus='{confirmed_privacy}' for video {video_id}."
                    )
                else:
                    logger.warning(
                        f"[Publish Safety] Read-only status query for video {video_id} returned item without status block: {items[0]}"
                    )
            else:
                logger.warning(
                    f"[Publish Safety] Read-only status query for video {video_id} returned no items: {inspect_resp}"
                )
        except Exception as inspect_err:
            logger.error(
                f"[Publish Safety] Read-only status query failed for video {video_id}: {inspect_err}"
            )

    # Step B: Remote Privacy-Mismatch Handling & Safe Emergency Correction
    # If remote privacy is established as "public" when "private" was requested:
    if confirmed_privacy == "public" and effective_privacy == "private":
        logger.warning(
            f"[Publish Safety] Newly created video {video_id} is 'public' remotely when 'private' was requested. "
            f"Building safe status update payload and executing emergency corrective update..."
        )

        # 1. Fetch latest mutable status if status_block lacks properties (e.g. license, embeddable, publicStatsViewable)
        existing_status_for_update = status_block
        needed_props = ("license", "embeddable", "publicStatsViewable")
        if not existing_status_for_update or not all(k in existing_status_for_update for k in needed_props):
            try:
                list_res = youtube.videos().list(part="status", id=video_id).execute()
                items = list_res.get("items", []) if isinstance(list_res, dict) else []
                if items and isinstance(items[0], dict) and isinstance(items[0].get("status"), dict):
                    existing_status_for_update = items[0]["status"]
            except Exception as fetch_err:
                logger.warning(
                    f"[Publish Safety] Could not fetch existing status for video {video_id} before update: {fetch_err}"
                )

        # 2. Build safe status update body preserving mutable fields without read-only properties
        update_body = None
        try:
            update_body = _build_safe_status_update_body(
                video_id=video_id,
                existing_status=existing_status_for_update,
                desired_privacy="private",
                fallback_license=license_type,
                fallback_made_for_kids=made_for_kids,
            )
        except UnsafeStatusRemediationError as unsafe_err:
            remediation_status = f"remediation_withheld: {unsafe_err}"
            logger.critical(
                f"[Publish Safety] Automated privacy remediation withheld for video {video_id}: {unsafe_err}. "
                f"Video remains in remote state '{confirmed_privacy}'. Operator manual review required."
            )

        # 3. Execute emergency videos().update if update body was safely built
        if update_body is not None:
            try:
                update_res = youtube.videos().update(
                    part="status",
                    body=update_body
                ).execute()
                logger.info(f"[Publish Safety] videos().update executed for video {video_id}.")

                # 4. Mandatory Read-Back: Verify remote state with read-only query
                # Do NOT claim corrective action succeeded merely because videos.update returned without exception!
                try:
                    verify_res = youtube.videos().list(part="status", id=video_id).execute()
                    v_items = verify_res.get("items", []) if isinstance(verify_res, dict) else []
                    if v_items and isinstance(v_items[0], dict) and isinstance(v_items[0].get("status"), dict):
                        readback_privacy = v_items[0]["status"].get("privacyStatus")
                        if readback_privacy == "private":
                            confirmed_privacy = "private"
                            remediation_status = "auto_remediated_to_private"
                            status_block = v_items[0]["status"]
                            logger.info(
                                f"[Publish Safety] Emergency correction confirmed via read-back: Video {video_id} remote privacy is 'private'."
                            )
                        else:
                            confirmed_privacy = readback_privacy or "public"
                            remediation_status = f"remediation_readback_still_public_{readback_privacy}"
                            logger.critical(
                                f"[Publish Safety] Emergency correction read-back failed: Video {video_id} remote privacy is '{readback_privacy}' (still not private)!"
                            )
                    else:
                        confirmed_privacy = "unconfirmed"
                        remediation_status = "remediation_readback_incomplete_response"
                        logger.critical(
                            f"[Publish Safety] Emergency correction read-back returned incomplete response for video {video_id}: {verify_res}"
                        )
                except Exception as readback_exc:
                    confirmed_privacy = "unconfirmed"
                    remediation_status = f"remediation_readback_exception: {readback_exc}"
                    logger.critical(
                        f"[Publish Safety] Emergency correction read-back query failed for video {video_id}: {readback_exc}"
                    )
            except Exception as update_exc:
                remediation_status = f"remediation_exception: {update_exc}"
                logger.critical(
                    f"[Publish Safety] Emergency correction update to 'private' failed for video {video_id}: {update_exc}"
                )

    # Set thumbnail if provided
    if thumbnail_path and thumbnail_path.exists():
        try:
            mime = "image/png" if str(thumbnail_path).lower().endswith(".png") else "image/jpeg"
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype=mime),
            ).execute()
        except Exception as e:
            print(f"[Publisher] Thumbnail upload failed: {e}")

    # ── Insert tracking entry after successful upload ───────────────────────
    try:
        from backend.models.database import SyncSessionLocal
        from backend.models.models import VideoTrackingQueue, Clip
        import uuid
        from datetime import datetime, timedelta, timezone

        target_clip_id = clip_id
        if not target_clip_id:
            extracted = Path(video_path).parent.name
            if extracted and extracted not in ("uploads", "outputs", "backend", "tmp", "") and len(extracted) >= 10:
                target_clip_id = extracted
            else:
                target_clip_id = video_id

        with SyncSessionLocal() as session:
            # Respect foreign key relationship with clips table
            if session.query(Clip).filter_by(id=target_clip_id).first():
                existing = session.query(VideoTrackingQueue).filter_by(youtube_video_id=video_id).first()
                if not existing:
                    now = datetime.now(timezone.utc)
                    next_check = now + timedelta(hours=2)
                    queue_item = VideoTrackingQueue(
                        id=str(uuid.uuid4()),
                        clip_id=target_clip_id,
                        youtube_video_id=video_id,
                        uploaded_at=now,
                        next_check_at=next_check,
                        optimization_attempts=0,
                        status="active"
                    )
                    session.add(queue_item)
                    session.commit()
                    print(f"[Publisher] Successfully added {target_clip_id} to tracking queue (next check: {next_check.isoformat()})")
    except Exception as db_err:
        print(f"[Publisher] Failed to insert tracking entry: {db_err}")

    try:
        from backend.services.publishing_cadence import record_destination_published
        if channel_id:
            record_destination_published(channel_id)
    except Exception as cad_err:
        logger.debug(f"[Publisher] Cadence record update: {cad_err}")

    return {
        "id": video_id,
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "title": short_title,
        "privacy": confirmed_privacy if confirmed_privacy else "unconfirmed",
        "status": status_block.get("uploadStatus", "uploaded") if isinstance(status_block, dict) else "unknown",
        "privacy_confirmed": (confirmed_privacy == effective_privacy and remediation_status is None),
        "remediation": remediation_status,
        "initial_remote_privacy": initial_remote_privacy,
    }


def _mock_upload_short(
    title: str,
    description: str,
    idempotency_key: str,
    progress_callback: callable = None,
    clip_id: str = None,
    tags: list[str] = None,
    privacy: str = "private",
    made_for_kids: bool | None = None,
    category: str = "22",
    license_type: str = "youtube",
) -> dict:
    import uuid
    import time
    
    print("[Publisher] Running in TEST mode. Simulating upload...")
    if progress_callback:
        try:
            progress_callback(500, 1000, 0.5)
        except Exception:
            pass
    time.sleep(1) # simulate network delay
    if progress_callback:
        try:
            progress_callback(1000, 1000, 1.0)
        except Exception:
            pass
    video_id = f"mock_{uuid.uuid4().hex[:8]}"
    
    if idempotency_key:
        mock_file = Path(settings.BASE_DIR) / "mock_external_state.json"
        data = {}
        if mock_file.exists():
            try:
                with open(mock_file, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[idempotency_key] = {
            "video_id": video_id,
            "title": title,
            "description": description,
            "tags": tags or [],
            "privacy": privacy,
            "made_for_kids": made_for_kids,
            "category": category,
            "license": license_type,
        }
        with open(mock_file, "w") as f:
            json.dump(data, f)

    # Insert tracking queue in mock test mode if clip exists
    if clip_id:
        try:
            from backend.models.database import SyncSessionLocal
            from backend.models.models import VideoTrackingQueue, Clip
            from datetime import datetime, timedelta, timezone
            with SyncSessionLocal() as session:
                if session.query(Clip).filter_by(id=clip_id).first():
                    existing = session.query(VideoTrackingQueue).filter_by(youtube_video_id=video_id).first()
                    if not existing:
                        now = datetime.now(timezone.utc)
                        next_check = now + timedelta(hours=2)
                        session.add(VideoTrackingQueue(
                            id=str(uuid.uuid4()),
                            clip_id=clip_id,
                            youtube_video_id=video_id,
                            uploaded_at=now,
                            next_check_at=next_check,
                            optimization_attempts=0,
                            status="active"
                        ))
                        session.commit()
        except Exception as e:
            pass
            
    return {
        "id": video_id,
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "title": f"{title} (Mock)",
        "description": description,
        "tags": tags or [],
        "privacy": privacy,
        "made_for_kids": made_for_kids,
        "category": category,
        "license": license_type,
        "privacy_confirmed": (privacy == "private"),
        "remediation": None,
    }


def check_external_youtube_state(idempotency_key: str, channel_id: str = None) -> str | None:
    """
    Checks if a video was already published with the given idempotency key.
    
    Returns:
        - video_id (str): if the video was found on YouTube
        - None: if definitely not found (safe to retry)
        - "MANUAL_REVIEW_REQUIRED": if search depth was exhausted
          and the upload may exist beyond the search window
    """
    is_test = os.environ.get("PUBLISH_MODE") == "test" or getattr(settings, "PUBLISH_MODE", "prod") == "test"
    mock_file = Path(settings.BASE_DIR) / "mock_external_state.json"
    if is_test or (mock_file.exists() and idempotency_key):
        if mock_file.exists():
            try:
                with open(mock_file, "r") as f:
                    data = json.load(f)
                val = data.get(idempotency_key)
                if val is not None:
                    if isinstance(val, dict):
                        return val.get("video_id")
                    return val
            except Exception:
                pass
        if is_test:
            return None

    # Prod mode: check via YouTube API with pagination
    MAX_PAGES = 3  # 50 results per page = 150 videos max
    try:
        youtube = get_youtube_client(channel_id=channel_id)
        next_page_token = None
        total_checked = 0
        
        for page in range(MAX_PAGES):
            request_params = {
                "part": "id,snippet",
                "forMine": True,
                "type": "video",
                "maxResults": 50,
                "order": "date",
            }
            if next_page_token:
                request_params["pageToken"] = next_page_token
                
            request = youtube.search().list(**request_params)
            response = request.execute()
            
            items = response.get("items", [])
            if not items:
                break
                
            for item in items:
                video_id = item["id"]["videoId"]
                vid_req = youtube.videos().list(part="snippet", id=video_id)
                vid_resp = vid_req.execute()
                if vid_resp.get("items"):
                    desc = vid_resp["items"][0]["snippet"]["description"]
                    if f"[idemp:{idempotency_key}]" in desc:
                        return video_id
                total_checked += 1
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                # No more pages — we've searched everything
                return None
        
        # Exhausted MAX_PAGES but more results exist
        # Cannot confidently say the upload doesn't exist
        print(f"[Publisher] Reconciliation searched {total_checked} videos "
              f"but more exist. Manual review required for key: {idempotency_key}")
        return "MANUAL_REVIEW_REQUIRED"
        
    except Exception as e:
        print(f"[Publisher] Failed to check external state: {e}")
        return None




def update_video_metadata(
    youtube_video_id: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    channel_id: str = None,
) -> dict:
    """
    Update the title, description, and tags of an already-published YouTube video.
    Used by the Phase 5 auto-optimizer.

    Returns the updated video resource snippet.
    """
    # Enforce YouTube 500-char tag payload safety (limit to 450 chars)
    raw_tags = (tags or []) + ["shorts", "viral", "trending"]
    cleaned_tags = []
    current_tag_len = 0
    for tag in raw_tags:
        if current_tag_len + len(tag) + 1 <= 450:
            cleaned_tags.append(tag)
            current_tag_len += len(tag) + 1

    if getattr(settings, "PUBLISH_MODE", "prod") == "test":
        return {
            "title": title[:100],
            "description": description[:5000],
            "tags": cleaned_tags,
            "categoryId": "22",
        }

    youtube = get_youtube_client(channel_id=channel_id)

    # Fetch current snippet (categoryId is required in the update body)
    current = youtube.videos().list(
        part="snippet",
        id=youtube_video_id,
    ).execute()
    if not current.get("items"):
        raise RuntimeError(f"Video '{youtube_video_id}' not found on YouTube.")

    snippet = current["items"][0]["snippet"]
    snippet["title"] = title[:100]
    snippet["description"] = description[:5000]
    snippet["tags"] = cleaned_tags

    response = youtube.videos().update(
        part="snippet",
        body={"id": youtube_video_id, "snippet": snippet},
    ).execute()
    return response.get("snippet", {})


def get_channel_info(channel_id: str = None) -> dict:
    """Get authenticated user's channel info, prioritizing real credentials."""
    try:
        youtube = get_youtube_client(channel_id=channel_id)
        response = youtube.channels().list(part="snippet,statistics", mine=True).execute()
        if response.get("items"):
            ch = response["items"][0]
            return {
                "id": ch["id"],
                "title": ch["snippet"]["title"],
                "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
                "subscribers": ch["statistics"].get("subscriberCount", 0),
            }
    except Exception:
        token_file = Path(settings.YOUTUBE_TOKEN_FILE)
        if getattr(settings, "PUBLISH_MODE", "prod") == "test" and not token_file.exists():
            return {
                "id": channel_id or "UC_test_channel_default",
                "title": "ClipForge Test Channel",
                "thumbnail": "https://example.com/thumb.jpg",
                "subscribers": 1000,
            }
        try:
            from backend.models.database import SyncSessionLocal
            from backend.models.models import Channel
            with SyncSessionLocal() as session:
                ch = session.query(Channel).filter(
                    (Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id) | (Channel.is_destination == True)
                ).first()
                if ch:
                    return {
                        "id": ch.youtube_channel_id,
                        "title": ch.channel_name,
                        "thumbnail": ch.thumbnail_url or "https://example.com/thumb.jpg",
                        "subscribers": 0,
                    }
        except Exception:
            pass
    return {}


def check_auth_status(channel_id: str = None) -> bool:
    """Check if YouTube OAuth is configured and credentials are valid."""
    try:
        get_youtube_client(channel_id=channel_id)
        return True
    except Exception:
        token_file = Path(settings.YOUTUBE_TOKEN_FILE)
        if getattr(settings, "PUBLISH_MODE", "prod") == "test" and not token_file.exists():
            return True
        return False


def check_channel_authorization(youtube_channel_id: str = None) -> bool:
    """Verify if a specific destination channel has valid credentials on disk."""
    if not youtube_channel_id:
        return False
    try:
        token_dir = _resolve_token_dir()
        # 1. Direct channel-specific token
        chan_file = token_dir / f"youtube_token_{youtube_channel_id}.json"
        if chan_file.exists():
            creds = Credentials.from_authorized_user_file(str(chan_file), SCOPES)
            return bool(creds and (creds.valid or creds.refresh_token))

        # 2. Primary default token
        default_file = token_dir / "youtube_token.json"
        if default_file.exists():
            # Check if this youtube_channel_id is the primary authorized channel
            from backend.models.database import SyncSessionLocal
            from backend.models.models import Channel
            with SyncSessionLocal() as session:
                default_ch = session.query(Channel).filter_by(is_default_destination=True, is_destination=True).first()
                if default_ch and (default_ch.youtube_channel_id == youtube_channel_id or default_ch.id == youtube_channel_id):
                    creds = Credentials.from_authorized_user_file(str(default_file), SCOPES)
                    return bool(creds and (creds.valid or creds.refresh_token))

        return False
    except Exception:
        return False


def sync_authorized_destinations():
    """
    Scans the tokens directory for authenticated YouTube credentials.
    Reconciles and upserts verified publishing destinations into the channels table.
    Ensures internal channels table accurately reflects genuine user-authorized destinations.
    """
    token_dir = _resolve_token_dir()
    if not token_dir.exists():
        return

    from backend.models.database import SyncSessionLocal
    from backend.models.models import Channel
    import uuid

    # Look for all youtube_token*.json files
    token_files = list(token_dir.glob("youtube_token*.json"))
    for tf in token_files:
        try:
            creds = Credentials.from_authorized_user_file(str(tf), SCOPES)
            if not creds:
                continue
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(tf, "w") as f:
                        f.write(creds.to_json())
                else:
                    continue

            client = build("youtube", "v3", credentials=creds)
            resp = client.channels().list(part="id,snippet", mine=True).execute()
            if not resp.get("items"):
                continue

            item = resp["items"][0]
            ch_id = item["id"]
            ch_title = item["snippet"]["title"]
            ch_thumb = item["snippet"].get("thumbnails", {}).get("default", {}).get("url")

            with SyncSessionLocal() as session:
                existing = session.query(Channel).filter_by(youtube_channel_id=ch_id).first()
                if not existing:
                    new_ch = Channel(
                        id=str(uuid.uuid4()),
                        youtube_channel_id=ch_id,
                        channel_name=ch_title,
                        channel_url=f"https://youtube.com/channel/{ch_id}",
                        thumbnail_url=ch_thumb,
                        is_destination=True,
                        is_default_destination=True,
                        is_active=True,
                        is_test=False,
                    )
                    session.add(new_ch)
                    session.commit()
                else:
                    existing.channel_name = ch_title
                    if ch_thumb:
                        existing.thumbnail_url = ch_thumb
                    existing.is_destination = True
                    existing.is_active = True
                    existing.is_test = False
                    session.commit()
        except Exception:
            continue


def _parse_iso_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration string into seconds."""
    if not duration_str:
        return 0
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds or 0)


def fetch_channel_analytics(channel_id: str) -> dict:
    """
    Fetch official channel statistics and bounded Shorts scan from YouTube Data API v3.
    Accepts internal channel ID or YouTube channel ID.
    Returns:
    {
        "subscriber_count": int | None,
        "video_count": int,
        "view_count": int,
        "shorts_count": int,
        "shorts_scan_coverage": str,
        "shorts_classification_method": str,
        "likes_count": int | None,
        "likes_scope": str,
        "fetched_at": str,
        "status": "fresh",
        "warning_metadata": str | None,
    }
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Resolve to actual YouTube Channel ID and internal DB channel
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Channel

    resolved_yt_id = channel_id
    with SyncSessionLocal() as session:
        ch = session.query(Channel).filter(
            (Channel.id == channel_id) | (Channel.youtube_channel_id == channel_id)
        ).first()
        if ch and ch.youtube_channel_id:
            resolved_yt_id = ch.youtube_channel_id

    # If test mode and no real credentials exist
    token_file = _resolve_token_file(resolved_yt_id)
    if not token_file.exists() and getattr(settings, "PUBLISH_MODE", "prod") == "test":
        return {
            "subscriber_count": 1000,
            "video_count": 12,
            "view_count": 45000,
            "shorts_count": 8,
            "shorts_scan_coverage": "12 recent uploads scanned (Test Mode)",
            "shorts_classification_method": "Duration <= 60s or #Shorts tag in scanned uploads",
            "likes_count": 3200,
            "likes_scope": "Summed across 12 scanned uploads",
            "fetched_at": now_iso,
            "status": "test_mock",
            "warning_metadata": "Mock metrics generated in test mode",
        }

    youtube = get_youtube_client(channel_id=resolved_yt_id)
    resp = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        id=resolved_yt_id,
    ).execute()

    if not resp.get("items"):
        raise ValueError(f"Channel {resolved_yt_id} not found on YouTube.")

    item = resp["items"][0]
    stats = item.get("statistics", {})
    content_details = item.get("contentDetails", {})

    hidden_subs = stats.get("hiddenSubscriberCount", False)
    sub_count = None if hidden_subs else int(stats.get("subscriberCount", 0))
    video_count = int(stats.get("videoCount", 0))
    view_count = int(stats.get("viewCount", 0))

    shorts_count = 0
    likes_count = 0
    scanned_count = 0
    uploads_playlist_id = content_details.get("relatedPlaylists", {}).get("uploads")

    if uploads_playlist_id and video_count > 0:
        try:
            pl_resp = youtube.playlistItems().list(
                part="contentDetails,snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
            ).execute()
            pl_items = pl_resp.get("items", [])
            scanned_count = len(pl_items)

            video_ids = [
                it["contentDetails"]["videoId"]
                for it in pl_items
                if "contentDetails" in it and "videoId" in it["contentDetails"]
            ]
            if video_ids:
                # Batch request video details (up to 50 ids supported in YouTube API videos.list)
                v_resp = youtube.videos().list(
                    part="contentDetails,statistics,snippet",
                    id=",".join(video_ids),
                ).execute()

                for v_item in v_resp.get("items", []):
                    dur_str = v_item.get("contentDetails", {}).get("duration", "")
                    sec = _parse_iso_duration(dur_str)

                    v_title = v_item.get("snippet", {}).get("title", "")
                    v_desc = v_item.get("snippet", {}).get("description", "")
                    is_shorts_tag = "#shorts" in v_title.lower() or "#shorts" in v_desc.lower()

                    # Official classification rule: duration <= 60 seconds (or tagged #shorts)
                    if (sec > 0 and sec <= 60) or is_shorts_tag:
                        shorts_count += 1

                    v_stats = v_item.get("statistics", {})
                    if "likeCount" in v_stats:
                        try:
                            likes_count += int(v_stats["likeCount"])
                        except (ValueError, TypeError):
                            pass
        except Exception as scan_err:
            print(f"[fetch_channel_analytics] Bounded scan warning for {resolved_yt_id}: {scan_err}")

    coverage_label = (
        f"{scanned_count} recent upload{'s' if scanned_count != 1 else ''} scanned"
        if scanned_count > 0
        else "0 uploads available to scan"
    )
    likes_scope_label = f"Total likes across {scanned_count} scanned upload{'s' if scanned_count != 1 else ''}"

    return {
        "subscriber_count": sub_count,
        "video_count": video_count,
        "view_count": view_count,
        "shorts_count": shorts_count,
        "shorts_scan_coverage": coverage_label,
        "shorts_classification_method": "Duration <= 60s or #Shorts tag in scanned uploads (YouTube Data API v3)",
        "likes_count": likes_count if scanned_count > 0 else 0,
        "likes_scope": likes_scope_label,
        "fetched_at": now_iso,
        "status": "fresh",
        "warning_metadata": None if scanned_count == video_count else f"Channel has {video_count} total videos; scan bounded to {scanned_count} most recent uploads.",
    }


def get_oauth_url(redirect_uri: str = None, state: str = None, prompt: str = "select_account consent") -> str:
    """Generate OAuth authorization URL for first-time setup or connecting additional channels."""
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        if getattr(settings, "PUBLISH_MODE", "prod") == "test":
            return f"https://accounts.google.com/o/oauth2/auth?mock=1&prompt={prompt}&state={state or ''}"
        return ""
    
    redirect_uri = redirect_uri or settings.YOUTUBE_OAUTH_REDIRECT_URI
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/api/publish/oauth-callback"

    client_config = {
        "installed": {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = redirect_uri
    kwargs = {"prompt": prompt}
    if state:
        kwargs["state"] = state
    auth_url, _ = flow.authorization_url(**kwargs)
    return auth_url


def exchange_code_for_token(code: str, redirect_uri: str = None) -> dict:
    """Exchange OAuth authorization code for credentials and save token."""
    if getattr(settings, "PUBLISH_MODE", "prod") == "test" and code.startswith("mock_"):
        channel_id = "UC_mock_channel_123"
        channel_name = "ClipForge Mock Channel"
        from backend.models.database import SyncSessionLocal
        from backend.models.models import Channel
        import uuid
        with SyncSessionLocal() as session:
            db_channel = session.query(Channel).filter_by(youtube_channel_id=channel_id).first()
            if not db_channel:
                db_channel = Channel(
                    id=str(uuid.uuid4()),
                    youtube_channel_id=channel_id,
                    channel_name=channel_name,
                    channel_url=f"https://youtube.com/channel/{channel_id}",
                    thumbnail_url="https://yt3.ggpht.com/default_mock.jpg",
                    is_destination=True,
                    is_default_destination=False,
                    is_active=True,
                    is_test=True,
                )
                session.add(db_channel)
                session.commit()
            return {
                "id": db_channel.id,
                "channel_id": channel_id,
                "title": channel_name,
                "thumbnail_url": db_channel.thumbnail_url,
            }

    redirect_uri = redirect_uri or settings.YOUTUBE_OAUTH_REDIRECT_URI
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/api/publish/oauth-callback"

    client_config = {
        "installed": {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    # Get channel info to find channel_id
    client = build("youtube", "v3", credentials=creds)
    resp = client.channels().list(part="id,snippet", mine=True).execute()
    if not resp.get("items"):
        raise ValueError("Could not determine authenticated YouTube channel.")
    
    channel_info = resp["items"][0]
    channel_id = channel_info["id"]
    channel_name = channel_info["snippet"]["title"]
    channel_thumb = channel_info["snippet"].get("thumbnails", {}).get("default", {}).get("url")
    
    # Save the token to its channel-isolated file
    token_file = Path(settings.YOUTUBE_TOKEN_FILE)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    channel_token_file = token_file.parent / f"youtube_token_{channel_id}.json"
    with open(channel_token_file, "w") as f:
        f.write(creds.to_json())

    # Upsert the Channel as a destination in DB
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Channel
    import uuid

    with SyncSessionLocal() as session:
        has_default = session.query(Channel).filter_by(is_destination=True, is_default_destination=True).first() is not None
        db_channel = session.query(Channel).filter_by(youtube_channel_id=channel_id).first()
        if not db_channel:
            db_channel = Channel(
                id=str(uuid.uuid4()),
                youtube_channel_id=channel_id,
                channel_name=channel_name,
                channel_url=f"https://youtube.com/channel/{channel_id}",
                thumbnail_url=channel_thumb,
                is_destination=True,
                is_default_destination=not has_default,
                is_active=True,
                is_test=False,
                publishing_settings={
                    "default_privacy": "public",
                    "default_category": "22",
                    "default_license": "youtube",
                    "default_made_for_kids": False,
                    "default_age_restricted": False,
                    "default_tags": "shorts, viral",
                    "watermark_url": None,
                    "brand_color_primary": None,
                    "brand_logo_position": "top_right",
                }
            )
            session.add(db_channel)
        else:
            db_channel.is_destination = True
            db_channel.is_active = True
            db_channel.is_test = False
            if channel_name:
                db_channel.channel_name = channel_name
            if channel_thumb:
                db_channel.thumbnail_url = channel_thumb
            if not has_default and not db_channel.is_default_destination:
                db_channel.is_default_destination = True
            if not db_channel.publishing_settings:
                db_channel.publishing_settings = {
                    "default_privacy": "public",
                    "default_category": "22",
                    "default_license": "youtube",
                    "default_made_for_kids": False,
                    "default_age_restricted": False,
                    "default_tags": "shorts, viral",
                    "watermark_url": db_channel.watermark_url,
                    "brand_color_primary": db_channel.brand_color_primary,
                    "brand_logo_position": db_channel.brand_logo_position or "top_right",
                }
        
        session.commit()
        db_id = db_channel.id
        
    return {
        "id": db_id,
        "channel_id": channel_id,
        "title": channel_name,
        "thumbnail_url": channel_thumb,
    }


def validate_destination_ids(destination_ids: list[str], session) -> list[str]:
    """
    Validates every destination ID before creating PublishTargets.
    Raises ValueError on any invalid destination. Never silently substitutes.
    """
    from backend.models.models import Channel
    from backend.core.config import settings

    validated = []
    for dest_id in destination_ids:
        channel = session.query(Channel).filter_by(id=dest_id).first()
        if not channel:
            raise ValueError(f"Destination {dest_id} does not exist")
        if not channel.is_destination:
            raise ValueError(
                f"Channel {dest_id} ({channel.channel_name}) "
                f"is not configured as a publishing destination for this tenant"
            )
        if not channel.is_active:
            raise ValueError(
                f"Destination {dest_id} ({channel.channel_name}) is inactive"
            )
        # Verify credential file exists
        token_file = Path(settings.YOUTUBE_TOKEN_FILE).parent / f"youtube_token_{channel.youtube_channel_id}.json"
        if not token_file.exists():
            default_token = Path(settings.YOUTUBE_TOKEN_FILE)
            if not default_token.exists():
                raise ValueError(
                    f"No YouTube credentials for destination {channel.channel_name} ({channel.youtube_channel_id})"
                )
        validated.append(dest_id)

    return validated


def resolve_publish_destinations(
    job_config: dict | None,
    source_channel_id: str | None,
    session
) -> list[str]:
    """
    Resolves destinations according to multi-destination v3 semantics:
    1. If job_config contains "destination_ids":
       - Explicit empty list ([]) -> BLOCKS publishing. Returns [] (never falls back to defaults).
       - Explicit non-empty list -> Validates and returns validated destination IDs.
    2. If "destination_ids" key is absent from job_config:
       - Uses source-channel defaults from ChannelDestination where is_default=True.
       - Falls back to legacy Channel.is_default_destination=True if no ChannelDestination rows exist.
       - Returns list of validated destination IDs.
    """
    from backend.models.models import Channel, ChannelDestination
    from datetime import datetime, timezone

    if job_config and "destination_ids" in job_config:
        explicit_dests = job_config.get("destination_ids")
        if explicit_dests is not None:
            if isinstance(explicit_dests, list):
                if len(explicit_dests) == 0:
                    # Explicit empty list: BLOCK publishing. Never fallback to defaults.
                    return []
                return validate_destination_ids(explicit_dests, session)
            elif isinstance(explicit_dests, str):
                try:
                    parsed = json.loads(explicit_dests)
                    if isinstance(parsed, list):
                        if len(parsed) == 0:
                            return []
                        return validate_destination_ids(parsed, session)
                except Exception:
                    pass

    # Check job_config single destination if provided
    if job_config and "publish_destination_id" in job_config:
        pub_dest = job_config.get("publish_destination_id")
        if pub_dest:
            return validate_destination_ids([pub_dest], session)
        elif pub_dest is None or pub_dest == "":
            # Explicit None/empty in job_config: preserve intentional None (Select at publish time)
            return []

    # destination_ids is absent -> Use source-channel defaults from ChannelDestination
    if source_channel_id:
        now = datetime.now(timezone.utc)
        cd_rows = session.query(ChannelDestination).filter(
            ChannelDestination.source_channel_id == source_channel_id,
            ChannelDestination.is_default == True,
            (ChannelDestination.expires_at.is_(None) | (ChannelDestination.expires_at > now))
        ).all()
        if cd_rows:
            dest_ids = [cd.destination_channel_id for cd in cd_rows]
            try:
                return validate_destination_ids(dest_ids, session)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Error validating source defaults for {source_channel_id}: {e}")

        # Check source channel's direct publish_destination_id
        src_channel = session.query(Channel).filter_by(id=source_channel_id).first()
        if src_channel:
            if src_channel.publish_destination_id:
                try:
                    return validate_destination_ids([src_channel.publish_destination_id], session)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Error validating source channel publish_destination_id for {source_channel_id}: {e}")
            else:
                # Monitored channel explicitly configured with None (Select at publish time)
                # Preserve intentional None — do NOT silently fall back to arbitrary default accounts
                return []

    # Fallback to legacy global default if present and no channel-specific context exists
    default_ch = session.query(Channel).filter_by(is_default_destination=True, is_active=True).first()
    if default_ch:
        try:
            return validate_destination_ids([default_ch.id], session)
        except Exception:
            return []

    return []


def sync_resolve_publish_destination(clip_id: str, session) -> str | None:
    """
    Resolves the authoritative YouTube channel ID for publishing a clip.
    Enforces the LEGACY_FALLBACK_CUTOFF rule.
    Returns: The youtube_channel_id (str) or None if blocked.
    """
    from backend.models.models import Clip, Channel, Video
    from datetime import datetime, timezone
    
    LEGACY_FALLBACK_CUTOFF = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    clip = session.query(Clip).filter_by(id=clip_id).first()
    if not clip:
        return None
        
    if clip.publish_destination_id:
        channel = session.query(Channel).filter_by(id=clip.publish_destination_id).first()
        if channel and channel.is_active and channel.is_destination and check_channel_authorization(channel.youtube_channel_id):
            return channel.youtube_channel_id
        return None
        
    is_legacy = clip.created_at and clip.created_at < LEGACY_FALLBACK_CUTOFF
    if is_legacy:
        if clip.video_id:
            video = session.query(Video).filter_by(id=clip.video_id).first()
            if video and video.channel_id:
                channel = session.query(Channel).filter_by(id=video.channel_id).first()
                if channel and channel.is_active and channel.is_destination and check_channel_authorization(channel.youtube_channel_id):
                    return channel.youtube_channel_id
    
    return None


async def async_resolve_publish_destination(clip_id: str, session) -> str | None:
    """
    Async version of resolve_publish_destination.
    """
    from backend.models.models import Clip, Channel, Video
    from sqlalchemy import select
    from datetime import datetime, timezone
    
    LEGACY_FALLBACK_CUTOFF = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    result = await session.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        return None
        
    if clip.publish_destination_id:
        ch_result = await session.execute(select(Channel).where(Channel.id == clip.publish_destination_id))
        channel = ch_result.scalar_one_or_none()
        if channel and channel.is_active and channel.is_destination and check_channel_authorization(channel.youtube_channel_id):
            return channel.youtube_channel_id
        return None
        
    is_legacy = clip.created_at and clip.created_at < LEGACY_FALLBACK_CUTOFF
    if is_legacy:
        if clip.video_id:
            video_result = await session.execute(select(Video).where(Video.id == clip.video_id))
            video = video_result.scalar_one_or_none()
            if video and video.channel_id:
                ch_result = await session.execute(select(Channel).where(Channel.id == video.channel_id))
                channel = ch_result.scalar_one_or_none()
                if channel and channel.is_active and channel.is_destination and check_channel_authorization(channel.youtube_channel_id):
                    return channel.youtube_channel_id
                
    return None

