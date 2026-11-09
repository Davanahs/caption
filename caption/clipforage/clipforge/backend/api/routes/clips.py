"""API Routes — Clips management"""
import os
import sys
import time
import json
import uuid
import hmac
import hashlib
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, outerjoin, delete
from pydantic import BaseModel

from backend.models.database import get_db, AsyncSessionLocal
from backend.models.models import (
    Clip, Video, Channel, Job, VideoReservationState,
    TaskExecution, TaskExecutionStatus, ArtifactRecord,
    ClipVariant, ClipRetention, ClipSFXPlan, ClipVisualPlan, ClipHookPlan
)
from backend.core.config import settings
from backend.core.storage_identity import resolve_storage_identity_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clips", tags=["clips"])


class UpdateClipRequest(BaseModel):
    title: str | None = None
    description: str | None = None


# ── Storage Cleanup Pydantic Schemas ─────────────────────────────────────────

class CleanupCandidate(BaseModel):
    clip_id: str
    title: str
    score: float | None = None
    category: str
    output_path: str | None = None
    size_bytes: int = 0


class CleanupCounts(BaseModel):
    low_score: int = 0
    unavailable: int = 0
    total_unique: int = 0


class CleanupProtectedCounts(BaseModel):
    published: int = 0
    high_score: int = 0
    active_jobs: int = 0
    active_reservations: int = 0


class CleanupPreviewResponse(BaseModel):
    preview_token: str
    preview_id: str
    expires_at: int
    counts: CleanupCounts
    reclaimable_bytes: int
    reclaimable_human: str
    candidates: List[CleanupCandidate]
    protected_counts: CleanupProtectedCounts


class CleanupExecuteRequest(BaseModel):
    preview_token: str
    candidate_clip_ids: List[str]
    purge_missing_media: bool = False


class CleanupSummary(BaseModel):
    requested_count: int = 0
    deleted_clip_records: int = 0
    purged_physical_files: int = 0
    shared_files_retained: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    confirmed_reclaimed_bytes: int = 0
    confirmed_reclaimed_human: str = "0 B"


class SkippedCandidate(BaseModel):
    clip_id: str
    reason: str


class CleanupExecuteResponse(BaseModel):
    status: str
    summary: CleanupSummary
    deleted_clip_ids: List[str]
    skipped_candidates: List[SkippedCandidate]
    retained_shared_files: List[str]
    recovery_pending: List[str]


@router.get("/")
async def list_clips(
    video_id: str | None = None,
    channel_id: str | None = None,
    destination_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List generated clips, optionally filtered by video and date range.
    JOINs with the Video table to include source_title and source_url.
    """
    try:
        query = (
            select(Clip, Video.title.label("source_title"), Video.youtube_url.label("source_url"))
            .outerjoin(Video, Clip.video_id == Video.id)
            .order_by(desc(Clip.created_at))
        )
        if video_id:
            query = query.where(Clip.video_id == video_id)

        if channel_id:
            query = query.where(Video.channel_id == channel_id)

        if destination_id:
            query = query.where(Clip.publish_destination_id == destination_id)

        if from_date:
            try:
                start = datetime.fromisoformat(from_date)
                query = query.where(Clip.created_at >= start)
            except ValueError:
                raise HTTPException(status_code=400, detail="from_date must be ISO format YYYY-MM-DD or full timestamp")

        if to_date:
            try:
                end = datetime.fromisoformat(to_date)
                query = query.where(Clip.created_at <= end)
            except ValueError:
                raise HTTPException(status_code=400, detail="to_date must be ISO format YYYY-MM-DD or full timestamp")

        result = await db.execute(query.limit(100))
        clips = result.scalars().all()
        
        # Get source video info for each clip
        response = []
        for clip in clips:
            try:
                # Fetch video info separately
                video_result = await db.execute(select(Video).where(Video.id == clip.video_id))
                video = video_result.scalar_one_or_none()
                
                channel_name = None
                if video and video.channel_id:
                    ch_res = await db.execute(select(Channel).where(Channel.id == video.channel_id))
                    ch = ch_res.scalar_one_or_none()
                    if ch:
                        channel_name = ch.channel_name

                # Handle datetime and other fields safely
                item = {
                    "id": clip.id,
                    "video_id": clip.video_id,
                    "title": clip.title or "Untitled",
                    "description": clip.description,
                    "duration": float(clip.duration) if clip.duration else 0,
                    "score": float(clip.score) if clip.score else 0,
                    "start_time": float(clip.start_time) if clip.start_time else 0,
                    "end_time": float(clip.end_time) if clip.end_time else 0,
                    "thumbnail_path": clip.thumbnail_path,
                    "output_path": clip.output_path,
                    "publish_status": clip.publish_status or "draft",
                    "publish_destination_id": clip.publish_destination_id,
                    "youtube_short_id": clip.youtube_short_id,
                    "privacy": clip.privacy or "public",
                    "tags": clip.tags or "",
                    "category": clip.category or "22",
                    "license": clip.license or "youtube",
                    "made_for_kids": clip.made_for_kids or False,
                    "age_restricted": clip.age_restricted or False,
                    "pinned_comment": clip.pinned_comment or "",
                    "created_at": clip.created_at.isoformat() if clip.created_at else None,
                    # ── source video info ──────────────────────────────────────
                    "source_title": video.title if video else None,
                    "source_url": video.youtube_url if video else None,
                    "channel_id": video.channel_id if video else None,
                    "source_channel_name": channel_name,
                }
                response.append(item)
            except Exception as e:
                print(f"Error processing clip {clip.id}: {e}")
                continue
        
        return response
    except Exception as e:
        print(f"Error in list_clips: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing clips: {str(e)}")


# ── Storage Cleanup Helpers & Invariant Enforcement ──────────────────────────

class CrossDeviceLinkError(RuntimeError):
    """Raised when source and quarantine paths reside on different filesystem devices."""
    pass


class CanonicalContainmentError(ValueError):
    """Raised when target path violates canonical directory containment."""
    pass


def format_bytes_human(num_bytes: int) -> str:
    """Formats raw bytes into human-readable metric string."""
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    val = float(num_bytes)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(val)} B"
    return f"{val:.2f} {units[unit_idx]}"


def validate_canonical_containment(target_path: Path | str, approved_root: Path) -> Path:
    """
    Enforces strict canonical path containment using resolved Path.relative_to().
    Rejects traversals, symlinks escaping the root, and root destruction.
    """
    if not target_path:
        raise CanonicalContainmentError("Target path cannot be empty")
        
    resolved_root = approved_root.resolve(strict=True)
    target = Path(target_path)
    if not target.is_absolute():
        rel_str = str(target_path).replace("\\", "/").lstrip("/")
        if rel_str.startswith("outputs/"):
            rel_str = rel_str[len("outputs/"):]
        target = resolved_root / rel_str
    resolved_target = target.resolve(strict=False)
    
    # 1. Root destruction barrier
    if resolved_target == resolved_root:
        raise CanonicalContainmentError(f"Security violation: Target is the storage root itself: {target_path}")
        
    # 2. Strict relative_to containment check
    try:
        rel = resolved_target.relative_to(resolved_root)
    except ValueError:
        raise CanonicalContainmentError(f"Path traversal detected: {target_path} is outside approved root {approved_root}")
        
    # 3. Guard against '.' or empty relative segments
    if str(rel) in ("", ".", ".."):
        raise CanonicalContainmentError(f"Invalid containment target: {target_path}")
        
    # 4. Strict subpath containment
    parts = rel.parts
    if not parts or any(p in ("..", "/") for p in parts):
        raise CanonicalContainmentError(f"Invalid path segments in target: {rel}")
        
    # 5. File extension whitelist if file
    ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".json", ".wav"}
    if resolved_target.suffix and resolved_target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise CanonicalContainmentError(f"Unsupported file type for cleanup: {resolved_target.suffix}")
        
    return resolved_target


def verify_filesystem_colocation(source_dir: Path, quarantine_dir: Path) -> None:
    """
    Verifies that source and quarantine directories reside on the exact same filesystem device.
    Uses os.stat().st_dev. On Linux/Unix, also cross-checks statvfs (f_fsid) where available.
    Fails closed: if devices differ or cannot be verified, raises CrossDeviceLinkError.
    NEVER falls back to copy-and-delete across device boundaries.
    """
    resolved_source = source_dir.resolve(strict=False)
    resolved_quar = quarantine_dir.resolve(strict=False)
    
    # Ensure probe directory or parent exists for stat inspection
    source_probe = resolved_source if resolved_source.exists() else resolved_source.parent
    quar_probe = resolved_quar if resolved_quar.exists() else resolved_quar.parent
    
    if not source_probe.exists() or not quar_probe.exists():
        raise CrossDeviceLinkError(
            f"Cannot verify filesystem co-location: directory probe path does not exist "
            f"(source={source_probe}, quarantine={quar_probe})"
        )
        
    source_stat = os.stat(source_probe)
    quar_stat = os.stat(quar_probe)
    
    if source_stat.st_dev != quar_stat.st_dev:
        raise CrossDeviceLinkError(
            f"Filesystem co-location preflight check failed: "
            f"Source directory ({source_probe}, dev={source_stat.st_dev}) and quarantine directory "
            f"({quar_probe}, dev={quar_stat.st_dev}) reside on different filesystem devices. "
            f"Atomic os.replace() is impossible across mount boundaries, and fallback "
            f"to non-atomic copy-and-delete is strictly prohibited."
        )
        
    if hasattr(os, "statvfs"):
        try:
            source_vfs = os.statvfs(source_probe)
            quar_vfs = os.statvfs(quar_probe)
            if source_vfs.f_fsid != 0 and quar_vfs.f_fsid != 0 and source_vfs.f_fsid != quar_vfs.f_fsid:
                raise CrossDeviceLinkError(
                    f"Filesystem statvfs check failed: f_fsid mismatch between "
                    f"source ({source_vfs.f_fsid}) and quarantine ({quar_vfs.f_fsid})."
                )
        except OSError:
            pass


def sync_directory(dir_path: Path) -> None:
    """Synchronizes a directory descriptor on platforms where supported."""
    if hasattr(os, "O_DIRECTORY"):
        try:
            fd = os.open(str(dir_path), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass


def update_journal_file(journal_file: Path, journal_data: Dict[str, Any], journal_dir: Path) -> None:
    """Atomically flushes, syncs, replaces journal and syncs parent directory."""
    tmp_file = journal_file.parent / f"{journal_file.name}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(journal_data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, journal_file)
    sync_directory(journal_dir)


def generate_preview_token(
    candidate_clip_ids: List[str],
    score_threshold: float = 5.0,
    purge_missing_media: bool = False,
    secret_key: Optional[str] = None,
    expires_at: Optional[int] = None
) -> Tuple[str, str, int]:
    """Generates a cryptographically signed HMAC-SHA256 preview token with a 15-minute lease."""
    valid_secret = resolve_storage_identity_secret(secret_key)
    preview_id = str(uuid.uuid4())
    issued_at = int(time.time())
    if expires_at is None:
        expires_at = issued_at + 900  # 15 minutes lease
    
    sorted_ids = sorted(candidate_clip_ids)
    candidate_ids_hash = hashlib.sha256(",".join(sorted_ids).encode("utf-8")).hexdigest()
    
    payload = {
        "preview_id": preview_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "candidate_ids_hash": candidate_ids_hash,
        "candidate_count": len(sorted_ids),
        "score_threshold": float(score_threshold),
        "purge_missing_media": bool(purge_missing_media),
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(valid_secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
    
    payload_b64 = base64.urlsafe_b64encode(canonical_bytes).decode("ascii").rstrip("=")
    token = f"{payload_b64}.{signature}"
    return token, preview_id, expires_at


def validate_preview_token(
    preview_token: str,
    submitted_clip_ids: List[str],
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """Strictly validates HMAC-SHA256 preview token structure, signature, expiration, and candidates hash."""
    if not preview_token or not isinstance(preview_token, str) or "." not in preview_token:
        raise HTTPException(status_code=400, detail="Invalid preview token structure")
        
    parts = preview_token.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Malformed preview token")
        
    payload_b64, provided_sig = parts[0], parts[1]
    
    try:
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
        canonical_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(canonical_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode preview token payload: {e}")
        
    required_claims = {"preview_id", "issued_at", "expires_at", "candidate_ids_hash", "candidate_count"}
    if not required_claims.issubset(payload.keys()):
        raise HTTPException(status_code=400, detail="Preview token missing required claims")
        
    valid_secret = resolve_storage_identity_secret(secret_key)
    expected_sig = hmac.new(valid_secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(status_code=401, detail="Cryptographic verification failed for preview token")
        
    now = int(time.time())
    if now > payload["expires_at"]:
        raise HTTPException(status_code=400, detail="Preview token has expired (15 minute lease window exceeded)")
        
    submitted_sorted = sorted(submitted_clip_ids)
    submitted_hash = hashlib.sha256(",".join(submitted_sorted).encode("utf-8")).hexdigest()
    
    if not hmac.compare_digest(submitted_hash, payload["candidate_ids_hash"]):
        raise HTTPException(
            status_code=400,
            detail="Submitted candidate clip IDs do not match reviewed preview token candidate set"
        )
        
    return payload


# ── Storage Cleanup Endpoints ────────────────────────────────────────────────

@router.get("/cleanup/preview", response_model=CleanupPreviewResponse)
async def preview_cleanup(
    score_threshold: float = Query(5.0, description="Clips scored below this threshold are eligible for pruning"),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes a read-only preview of cleanup candidates below the score threshold.
    Returns counts, estimated space recovery, candidate list, and HMAC integrity token.
    Mutates zero database records and zero physical files.
    """
    try:
        result = await db.execute(select(Clip))
        all_clips = result.scalars().all()
        
        published_count = 0
        high_score_count = 0
        active_jobs_count = 0
        active_reservations_count = 0
        
        eligible_candidates: List[CleanupCandidate] = []
        unavailable_count = 0
        low_score_count = 0
        reclaimable_bytes = 0
        
        for clip in all_clips:
            # Check published status
            is_published = (clip.publish_status == "published") or (bool(clip.youtube_short_id and str(clip.youtube_short_id).strip()))
            if is_published:
                published_count += 1
                continue
                
            # Check score threshold
            clip_score = float(clip.score) if clip.score is not None else 0.0
            if clip_score >= score_threshold:
                high_score_count += 1
                continue
                
            # Check parent job active state
            if clip.video_id:
                job_res = await db.execute(
                    select(Job).where(Job.video_id == clip.video_id).order_by(desc(Job.created_at)).limit(1)
                )
                parent_job = job_res.scalar_one_or_none()
                if parent_job and parent_job.status not in ["completed", "completed_with_failures", "failed", "cancelled"]:
                    active_jobs_count += 1
                    continue
                    
                # Check video reservation state
                vid_res = await db.execute(select(Video).where(Video.id == clip.video_id))
                parent_video = vid_res.scalar_one_or_none()
                if parent_video and parent_video.reservation_state in [
                    VideoReservationState.INITIAL.value,
                    VideoReservationState.HEADROOM_ONLY.value
                ]:
                    active_reservations_count += 1
                    continue

            # Candidate is eligible. Check media on disk
            media_path = None
            size_bytes = 0
            category = "low_score"
            
            if clip.output_path:
                try:
                    resolved_p = validate_canonical_containment(clip.output_path, settings.OUTPUT_DIR)
                    if resolved_p.exists() and resolved_p.is_file():
                        media_path = str(resolved_p.relative_to(settings.OUTPUT_DIR)).replace("\\", "/")
                        size_bytes = resolved_p.stat().st_size
                    else:
                        category = "unavailable"
                except Exception:
                    category = "unavailable"
            else:
                category = "unavailable"
                
            if category == "unavailable":
                unavailable_count += 1
            else:
                low_score_count += 1
                reclaimable_bytes += size_bytes
                
            eligible_candidates.append(
                CleanupCandidate(
                    clip_id=clip.id,
                    title=clip.title or "Untitled Clip",
                    score=clip_score,
                    category=category,
                    output_path=media_path,
                    size_bytes=size_bytes
                )
            )
            
        candidate_ids = [c.clip_id for c in eligible_candidates]
        token, preview_id, expires_at = generate_preview_token(
            candidate_clip_ids=candidate_ids,
            score_threshold=score_threshold,
            purge_missing_media=False
        )
        
        return CleanupPreviewResponse(
            preview_token=token,
            preview_id=preview_id,
            expires_at=expires_at,
            counts=CleanupCounts(
                low_score=low_score_count,
                unavailable=unavailable_count,
                total_unique=len(eligible_candidates)
            ),
            reclaimable_bytes=reclaimable_bytes,
            reclaimable_human=format_bytes_human(reclaimable_bytes),
            candidates=eligible_candidates,
            protected_counts=CleanupProtectedCounts(
                published=published_count,
                high_score=high_score_count,
                active_jobs=active_jobs_count,
                active_reservations=active_reservations_count
            )
        )
    except Exception as e:
        logger.error(f"[CleanupPreview] Error generating cleanup preview: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to generate cleanup preview: {str(e)}")


@router.post("/cleanup/execute", response_model=CleanupExecuteResponse)
async def execute_cleanup(
    body: CleanupExecuteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Safely executes storage cleanup for reviewed candidate clips.
    Validates HMAC token, enforces same-filesystem co-location, stages via 6-step crash-durable
    journaling, deletes DB records, and physically purges quarantined files.
    """
    try:
        # 1. Validate Preview Token (HMAC-SHA256, expiry, candidate match)
        payload = validate_preview_token(body.preview_token, body.candidate_clip_ids)
        
        # 2. Filesystem Co-Location Verification
        quarantine_root = settings.OUTPUT_DIR / ".storage_quarantine"
        quarantine_root.mkdir(parents=True, exist_ok=True)
        verify_filesystem_colocation(settings.OUTPUT_DIR, quarantine_root)
        
        # 3. Setup batch directories
        batch_id = str(uuid.uuid4())
        batch_quarantine_dir = quarantine_root / f"batch_{batch_id}"
        batch_quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        journal_root = settings.BASE_DIR / "storage_cleanup_journals"
        journal_root.mkdir(parents=True, exist_ok=True)
        batch_journal_dir = journal_root / f"batch_{batch_id}"
        batch_journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = batch_journal_dir / "journal.json"
        
        journal_data: Dict[str, Any] = {
            "batch_id": batch_id,
            "preview_id": payload.get("preview_id"),
            "batch_state": "PREPARING",
            "created_at": int(time.time()),
            "items": []
        }
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        # 4. Re-evaluate candidates from DB & check invariants
        skipped_candidates: List[SkippedCandidate] = []
        staging_items: List[Dict[str, Any]] = []
        clips_to_delete: List[Clip] = []
        retained_shared_files: List[str] = []
        
        for clip_id in body.candidate_clip_ids:
            res = await db.execute(select(Clip).where(Clip.id == clip_id))
            clip = res.scalar_one_or_none()
            if not clip:
                skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="clip_not_found"))
                continue
                
            # Invariant: Published status
            if (clip.publish_status == "published") or (bool(clip.youtube_short_id and str(clip.youtube_short_id).strip())):
                skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="published_clip"))
                continue
                
            # Invariant: Score threshold (< 5.0)
            clip_score = float(clip.score) if clip.score is not None else 0.0
            if clip_score >= payload.get("score_threshold", 5.0):
                skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="score_exceeds_threshold"))
                continue
                
            # Invariant: Parent Job active
            if clip.video_id:
                job_res = await db.execute(
                    select(Job).where(Job.video_id == clip.video_id).order_by(desc(Job.created_at)).limit(1)
                )
                parent_job = job_res.scalar_one_or_none()
                if parent_job and parent_job.status not in ["completed", "completed_with_failures", "failed", "cancelled"]:
                    skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="parent_job_active"))
                    continue
                    
                # Invariant: Storage Reservation
                vid_res = await db.execute(select(Video).where(Video.id == clip.video_id))
                parent_video = vid_res.scalar_one_or_none()
                if parent_video and parent_video.reservation_state in [
                    VideoReservationState.INITIAL.value,
                    VideoReservationState.HEADROOM_ONLY.value
                ]:
                    skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="active_storage_reservation"))
                    continue
                    
            # Invariant: Active Celery Tasks
            task_res = await db.execute(
                select(TaskExecution).where(
                    TaskExecution.clip_id == clip.id,
                    TaskExecution.status.in_([TaskExecutionStatus.RUNNING.value, "pending", "retrying"])
                )
            )
            if task_res.scalars().first():
                skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="active_celery_task"))
                continue
                
            # Invariant: Media presence & containment
            file_to_move: Optional[Path] = None
            if clip.output_path:
                try:
                    resolved_p = validate_canonical_containment(clip.output_path, settings.OUTPUT_DIR)
                    if resolved_p.exists() and resolved_p.is_file():
                        file_to_move = resolved_p
                except Exception as e:
                    logger.warning(f"Canonical containment error for clip {clip_id}: {e}")
                    
            if not file_to_move:
                if not body.purge_missing_media:
                    skipped_candidates.append(
                        SkippedCandidate(clip_id=clip_id, reason="unavailable_media_retained_by_default")
                    )
                    continue
                else:
                    clips_to_delete.append(clip)
                    continue
                    
            # Invariant: Shared reference check
            shared_clip_res = await db.execute(
                select(Clip).where(Clip.id != clip.id, Clip.output_path == clip.output_path)
            )
            if shared_clip_res.scalars().first():
                retained_shared_files.append(str(file_to_move))
                clips_to_delete.append(clip)
                continue
                
            shared_art_res = await db.execute(
                select(ArtifactRecord).where(
                    ArtifactRecord.owner_id != clip.id,
                    (ArtifactRecord.storage_key == clip.output_path) | (ArtifactRecord.storage_key.like(f"%{clip.id}%"))
                )
            )
            if shared_art_res.scalars().first():
                retained_shared_files.append(str(file_to_move))
                clips_to_delete.append(clip)
                continue
                
            # Invariant: Writer locks
            parent_dir = file_to_move.parent
            tmp_files = list(parent_dir.glob(".tmp_*")) + list(parent_dir.glob("*.part"))
            if tmp_files:
                skipped_candidates.append(SkippedCandidate(clip_id=clip_id, reason="file_write_in_progress"))
                continue
                
            # Staging target
            target_filename = f"{clip.id}_{file_to_move.name}"
            target_quar_path = batch_quarantine_dir / target_filename
            staging_items.append({
                "clip_id": clip.id,
                "source_path": file_to_move,
                "dest_path": target_quar_path,
                "size_bytes": file_to_move.stat().st_size
            })
            clips_to_delete.append(clip)

        # 5. Execute 6-Step Crash-Durable Staging
        journal_data["batch_state"] = "STAGING"
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        for item in staging_items:
            item_entry = {
                "clip_id": item["clip_id"],
                "canonical_source": str(item["source_path"]),
                "quarantine_destination": str(item["dest_path"]),
                "expected_size_bytes": item["size_bytes"],
                "item_state": "INTENT_DECLARED"
            }
            journal_data["items"].append(item_entry)
            update_journal_file(journal_file, journal_data, batch_journal_dir)
            
            # Atomic same-filesystem move
            os.replace(item["source_path"], item["dest_path"])
            
            # Synchronise directories
            sync_directory(item["source_path"].parent)
            sync_directory(item["dest_path"].parent)
            
            # Persist completed staging
            item_entry["item_state"] = "STAGED"
            update_journal_file(journal_file, journal_data, batch_journal_dir)
            
        journal_data["batch_state"] = "STAGED"
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        # 6. Database Commit
        journal_data["batch_state"] = "DB_COMMITTING"
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        deleted_clip_ids = []
        for clip in clips_to_delete:
            deleted_clip_ids.append(clip.id)
            await db.execute(delete(ClipVariant).where(ClipVariant.clip_id == clip.id))
            await db.execute(delete(ClipRetention).where(ClipRetention.clip_id == clip.id))
            await db.execute(delete(ClipSFXPlan).where(ClipSFXPlan.clip_id == clip.id))
            await db.execute(delete(ClipVisualPlan).where(ClipVisualPlan.clip_id == clip.id))
            await db.execute(delete(ClipHookPlan).where(ClipHookPlan.clip_id == clip.id))
            await db.execute(delete(ArtifactRecord).where(
                ArtifactRecord.owner_type == "clip",
                ArtifactRecord.owner_id == clip.id
            ))
            await db.delete(clip)
            
        await db.commit()
        
        journal_data["batch_state"] = "DB_COMMITTED"
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        # 7. Physical Purge from Quarantine
        journal_data["batch_state"] = "PURGING"
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        confirmed_reclaimed_bytes = 0
        purged_files_count = 0
        
        for item in staging_items:
            dest = Path(item["dest_path"])
            if dest.exists() and dest.is_file():
                sz = dest.stat().st_size
                dest.unlink(missing_ok=True)
                confirmed_reclaimed_bytes += sz
                purged_files_count += 1
                
        try:
            batch_quarantine_dir.rmdir()
        except OSError:
            pass
            
        journal_data["batch_state"] = "COMPLETED"
        update_journal_file(journal_file, journal_data, batch_journal_dir)
        
        return CleanupExecuteResponse(
            status="success",
            summary=CleanupSummary(
                requested_count=len(body.candidate_clip_ids),
                deleted_clip_records=len(deleted_clip_ids),
                purged_physical_files=purged_files_count,
                shared_files_retained=len(retained_shared_files),
                skipped_count=len(skipped_candidates),
                failed_count=0,
                confirmed_reclaimed_bytes=confirmed_reclaimed_bytes,
                confirmed_reclaimed_human=format_bytes_human(confirmed_reclaimed_bytes)
            ),
            deleted_clip_ids=deleted_clip_ids,
            skipped_candidates=skipped_candidates,
            retained_shared_files=retained_shared_files,
            recovery_pending=[]
        )
    except Exception as e:
        logger.error(f"[CleanupExecute] Error executing cleanup: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to execute cleanup: {str(e)}")


async def reconcile_quarantine() -> Dict[str, Any]:
    """
    Scans storage_cleanup_journals and .storage_quarantine for unfinished batches.
    Executes the 6-boundary recovery protocol deterministically.
    """
    journal_root = settings.BASE_DIR / "storage_cleanup_journals"
    if not journal_root.exists():
        return {"status": "ok", "reconciled_batches": 0}
        
    quarantine_root = settings.OUTPUT_DIR / ".storage_quarantine"
    reconciled_count = 0
    blocked_count = 0
    
    for batch_dir in journal_root.iterdir():
        if not batch_dir.is_dir() or not batch_dir.name.startswith("batch_"):
            continue
            
        journal_file = batch_dir / "journal.json"
        if not journal_file.exists():
            continue
            
        try:
            with open(journal_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"[Recovery] Unreadable journal file {journal_file}: {e}")
            continue
            
        batch_state = data.get("batch_state")
        items = data.get("items", [])
        batch_id = data.get("batch_id", batch_dir.name.replace("batch_", ""))
        batch_quar_dir = quarantine_root / f"batch_{batch_id}"
        
        if batch_state in ["COMPLETED", "CANCELLED_UNMOVED", "ROLLED_BACK"]:
            if batch_quar_dir.exists():
                try:
                    for f_item in batch_quar_dir.iterdir():
                        f_item.unlink(missing_ok=True)
                    batch_quar_dir.rmdir()
                except OSError:
                    pass
            continue
            
        try:
            async with AsyncSessionLocal() as session:
                clip_ids = [it.get("clip_id") for it in items if it.get("clip_id")]
                existing_clips = []
                if clip_ids:
                    res = await session.execute(select(Clip.id).where(Clip.id.in_(clip_ids)))
                    existing_clips = res.scalars().all()
                    
                if batch_state in ["PREPARING", "STAGING"]:
                    for it in items:
                        src = Path(it["canonical_source"])
                        dst = Path(it["quarantine_destination"])
                        if dst.exists() and not src.exists():
                            src.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(dst, src)
                            sync_directory(src.parent)
                            it["item_state"] = "ROLLED_BACK"
                        elif src.exists() and not dst.exists():
                            it["item_state"] = "CANCELLED_UNMOVED"
                            
                    data["batch_state"] = "ROLLED_BACK"
                    update_journal_file(journal_file, data, batch_dir)
                    if batch_quar_dir.exists():
                        try:
                            batch_quar_dir.rmdir()
                        except OSError:
                            pass
                    reconciled_count += 1
                    
                elif batch_state == "STAGED":
                    if existing_clips:
                        for it in items:
                            src = Path(it["canonical_source"])
                            dst = Path(it["quarantine_destination"])
                            if dst.exists():
                                src.parent.mkdir(parents=True, exist_ok=True)
                                os.replace(dst, src)
                                sync_directory(src.parent)
                                it["item_state"] = "ROLLED_BACK"
                        data["batch_state"] = "ROLLED_BACK"
                        update_journal_file(journal_file, data, batch_dir)
                        if batch_quar_dir.exists():
                            try:
                                batch_quar_dir.rmdir()
                            except OSError:
                                pass
                        reconciled_count += 1
                    else:
                        data["batch_state"] = "PURGING"
                        update_journal_file(journal_file, data, batch_dir)
                        if batch_quar_dir.exists():
                            for f_item in batch_quar_dir.iterdir():
                                f_item.unlink(missing_ok=True)
                            try:
                                batch_quar_dir.rmdir()
                            except OSError:
                                pass
                        data["batch_state"] = "COMPLETED"
                        update_journal_file(journal_file, data, batch_dir)
                        reconciled_count += 1
                        
                elif batch_state in ["DB_COMMITTING", "DB_COMMITTED", "PURGING"]:
                    if not existing_clips:
                        if batch_quar_dir.exists():
                            for f_item in batch_quar_dir.iterdir():
                                f_item.unlink(missing_ok=True)
                            try:
                                batch_quar_dir.rmdir()
                            except OSError:
                                pass
                        data["batch_state"] = "COMPLETED"
                        update_journal_file(journal_file, data, batch_dir)
                        reconciled_count += 1
                    else:
                        for it in items:
                            src = Path(it["canonical_source"])
                            dst = Path(it["quarantine_destination"])
                            if dst.exists():
                                src.parent.mkdir(parents=True, exist_ok=True)
                                os.replace(dst, src)
                                sync_directory(src.parent)
                                it["item_state"] = "ROLLED_BACK"
                        data["batch_state"] = "ROLLED_BACK"
                        update_journal_file(journal_file, data, batch_dir)
                        reconciled_count += 1
                        
        except Exception as e:
            logger.error(f"[Recovery] Error reconciling batch {batch_id}: {e}", exc_info=True)
            data["batch_state"] = "BLOCKED_AWAITING_RECOVERY"
            update_journal_file(journal_file, data, batch_dir)
            blocked_count += 1
                
    return {"status": "ok", "reconciled_batches": reconciled_count, "blocked_batches": blocked_count}


@router.get("/{clip_id}")
async def get_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.patch("/{clip_id}")
async def update_clip(clip_id: str, body: UpdateClipRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if body.title is not None:
        clip.title = body.title
    if body.description is not None:
        clip.description = body.description
    await db.commit()
    return {"message": "Clip updated"}


@router.delete("/{clip_id}")
async def delete_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    # Delete files
    for path in [clip.output_path, clip.thumbnail_path]:
        if path and Path(path).exists():
            Path(path).unlink(missing_ok=True)
    # Clean related artifacts if any
    from backend.models.models import ArtifactRecord
    await db.execute(delete(ArtifactRecord).where(
        ArtifactRecord.owner_type == "clip",
        ArtifactRecord.owner_id == clip_id
    ))
    await db.delete(clip)
    await db.commit()
    return {"message": "Clip deleted"}


@router.get("/{clip_id}/download")
async def download_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip or not clip.output_path:
        raise HTTPException(status_code=404, detail="Clip file not found")
    path = Path(clip.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found on disk")
    return FileResponse(str(path), media_type="video/mp4", filename=f"{clip.title}.mp4")


@router.get("/{clip_id}/thumbnail")
async def get_thumbnail(clip_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip or not clip.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    path = Path(clip.thumbnail_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found on disk")
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/{clip_id}/variants")
async def list_clip_variants(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Lists completed enhancement variants available for preview and download."""
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    result = await db.execute(
        select(ClipVariant).where(
            ClipVariant.clip_id == clip_id,
            ClipVariant.status.in_(["completed", "ready"])
        ).order_by(ClipVariant.created_at.desc())
    )
    variants = list(result.scalars().all())

    labels = {
        "hook": "Hook Overlay",
        "broll": "B-Roll Enhanced",
        "sfx": "SFX Enhanced",
        "sfx_variant": "SFX Enhanced",
        "dubbing_variant": "Dubbed Version",
        "dubbing": "Dubbed Version",
        "autofix": "Auto-Fix Preview",
    }

    base_dir = Path(settings.BASE_DIR).resolve()
    response_list = []
    for v in variants:
        ar_result = await db.execute(select(ArtifactRecord).where(ArtifactRecord.id == v.artifact_id))
        ar = ar_result.scalar_one_or_none()
        if not ar:
            continue

        local_path = (base_dir / ar.storage_key).resolve()
        if not local_path.exists():
            continue

        meta = {}
        if v.variant_metadata:
            try:
                meta = json.loads(v.variant_metadata)
            except Exception:
                meta = {}

        response_list.append({
            "variant_id": v.variant_id,
            "variant_type": v.variant_type,
            "label": labels.get(v.variant_type, v.variant_type.replace("_", " ").title()),
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "download_url": f"/api/clips/{clip_id}/variants/{v.variant_id}/download",
            "metadata": meta
        })

    return response_list


@router.get("/{clip_id}/variants/{variant_id}/download")
async def download_clip_variant(clip_id: str, variant_id: str, db: AsyncSession = Depends(get_db)):
    """Downloads or streams an enhancement variant MP4 with full Range header support."""
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    var_result = await db.execute(
        select(ClipVariant).where(
            ClipVariant.clip_id == clip_id,
            ClipVariant.variant_id == variant_id
        )
    )
    variant = var_result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Clip variant not found")

    ar_result = await db.execute(select(ArtifactRecord).where(ArtifactRecord.id == variant.artifact_id))
    ar = ar_result.scalar_one_or_none()
    if not ar:
        raise HTTPException(status_code=404, detail="Artifact record for variant not found")

    base_dir = Path(settings.BASE_DIR).resolve()
    file_path = (base_dir / ar.storage_key).resolve()

    # Security check: Ensure file path is strictly within base_dir to prevent path traversal
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: path traversal detected")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Variant file not found on disk")

    return FileResponse(
        str(file_path),
        media_type="video/mp4",
        filename=f"{clip.title}_{variant.variant_type}.mp4"
    )



# ── Feature 1: Metadata Review Routes ───────────────────────────────────────

class MetadataUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | str | None = None
    pinned_comment: str | None = None
    privacy: str | None = None
    made_for_kids: bool | None = None
    category: str | None = None
    license: str | None = None
    publish_destination_id: str | None = None


@router.get("/{clip_id}/metadata")
async def get_clip_metadata_route(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Get full metadata for a clip to populate the review UI."""
    import json
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    tags = []
    if clip.tags:
        try:
            tags = json.loads(clip.tags)
        except Exception:
            tags = [t.strip() for t in clip.tags.split(",") if t.strip()]
    return {
        "id": clip.id,
        "title": clip.title,
        "description": clip.description or "",
        "tags": tags,
        "pinned_comment": clip.pinned_comment or "",
        "metadata_status": clip.metadata_status,
        "privacy": clip.privacy,
        "made_for_kids": clip.made_for_kids,
        "category": clip.category,
        "license": clip.license or "youtube",
        "publish_destination_id": clip.publish_destination_id,
        "publish_status": clip.publish_status,
        "youtube_short_id": clip.youtube_short_id,
        "analytics": {
            "views": clip.analytics_views,
            "likes": clip.analytics_likes,
            "comments": clip.analytics_comments,
            "engagement_rate": clip.analytics_engagement_rate,
            "view_score": clip.analytics_view_score,
            "check_count": clip.analytics_check_count,
            "optimization_attempts": clip.optimization_attempts,
        },
    }


@router.patch("/{clip_id}/metadata")
async def update_clip_metadata(
    clip_id: str, body: MetadataUpdateRequest, db: AsyncSession = Depends(get_db)
):
    """Update clip metadata from the review UI before publishing."""
    import json
    from backend.models.models import PublishStatus
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if clip.publish_status == PublishStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="Cannot edit metadata of an already published clip.")
    if body.title is not None:
        title_clean = body.title.strip()
        if not title_clean:
            raise HTTPException(status_code=422, detail="Title cannot be empty")
        clip.title = title_clean[:100]
    if body.description is not None:
        clip.description = body.description[:5000]
    if body.tags is not None:
        raw_tags = body.tags
        if isinstance(raw_tags, str):
            tag_list = [t.strip().lstrip("#") for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tag_list = [str(t).strip().lstrip("#") for t in raw_tags if str(t).strip()]
        else:
            tag_list = []
        clip.tags = json.dumps(tag_list[:50])
    if body.pinned_comment is not None:
        clip.pinned_comment = body.pinned_comment[:200]
    if body.privacy is not None:
        clip.privacy = body.privacy
    if body.made_for_kids is not None:
        clip.made_for_kids = body.made_for_kids
    if body.category is not None:
        clip.category = body.category
    if body.license is not None:
        clip.license = body.license
    if "publish_destination_id" in body.model_fields_set:
        clip.publish_destination_id = body.publish_destination_id or None
    clip.metadata_status = "ready"
    await db.commit()
    return {
        "message": "Metadata updated",
        "title": clip.title,
        "description": clip.description,
        "license": clip.license,
        "category": clip.category,
        "privacy": clip.privacy,
        "publish_destination_id": clip.publish_destination_id,
    }


@router.post("/{clip_id}/publish")
async def publish_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Upload clip to YouTube with the reviewed metadata.
    Triggered when user clicks 'Publish' in the review UI.
    """
    import json
    from datetime import datetime
    from backend.services.publisher import upload_short
    from backend.services.auto_optimizer import post_pinned_comment

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if not clip.output_path or not Path(clip.output_path).exists():
        raise HTTPException(status_code=400, detail="Clip file not found on disk")
    if clip.publish_status == "published":
        return {"message": "Already published", "youtube_short_id": clip.youtube_short_id}

    if not clip.publish_destination_id:
        raise HTTPException(
            status_code=400,
            detail="Publish destination channel is required. Please assign a destination channel before publishing."
        )

    from backend.models.models import Channel
    dest_res = await db.execute(
        select(Channel).where(
            (Channel.id == clip.publish_destination_id) | (Channel.youtube_channel_id == clip.publish_destination_id),
            Channel.is_destination == True,
            Channel.is_active == True,
        )
    )
    dest_channel = dest_res.scalar_one_or_none()
    if not dest_channel:
        raise HTTPException(
            status_code=400,
            detail="Invalid destination channel: not found, inactive, or not an authorized destination."
        )

    from backend.services.publisher import check_channel_authorization
    if not check_channel_authorization(dest_channel.youtube_channel_id):
        raise HTTPException(
            status_code=400,
            detail="Destination channel is not authorized or OAuth credentials are invalid."
        )

    resolved_channel_id = str(dest_channel.youtube_channel_id or dest_channel.id)

    tags = []
    if clip.tags:
        try:
            tags = json.loads(clip.tags)
        except Exception:
            tags = [t.strip() for t in clip.tags.split(",") if t.strip()]

    import asyncio
    try:
        result_yt = await asyncio.to_thread(
            upload_short,
            video_path=Path(clip.output_path),
            title=clip.title or "My Short",
            description=clip.description or "",
            tags=tags,
            thumbnail_path=Path(clip.thumbnail_path) if clip.thumbnail_path else None,
            privacy="private",
            made_for_kids=clip.made_for_kids if isinstance(clip.made_for_kids, bool) else None,
            category=clip.category or "22",
            channel_id=resolved_channel_id,
            clip_id=clip.id,
        )
        youtube_short_id = result_yt["id"]
        confirmed_privacy = result_yt.get("privacy", "unconfirmed")
        clip.youtube_short_id = youtube_short_id
        clip.privacy = confirmed_privacy

        # Post pinned comment if set (non-blocking)
        if clip.pinned_comment:
            try:
                await asyncio.to_thread(post_pinned_comment, youtube_short_id, clip.pinned_comment)
            except Exception as ce:
                print(f"[Publish] Pinned comment failed: {ce}")

        remediation = result_yt.get("remediation")
        is_confirmed_private = result_yt.get("privacy_confirmed") if "privacy_confirmed" in result_yt else (confirmed_privacy == "private" and not remediation)

        if is_confirmed_private:
            clip.publish_status = "published"
            msg = "Published successfully"
        else:
            clip.publish_status = "manual_review"
            if remediation == "auto_remediated_to_private":
                clip.publish_error = (
                    f"Operational Alert: Video {youtube_short_id} returned 'public' upon upload; "
                    f"auto-remediated to 'private' via safe update and verified via read-back. Preserved for review."
                )
                msg = "Upload completed with privacy mismatch; auto-remediated to private and verified. Manual review required."
            elif remediation and any(k in remediation for k in ("exception", "failed", "still_public", "readback", "incomplete")):
                clip.publish_error = (
                    f"CRITICAL PRIVACY ALERT: Video {youtube_short_id} returned 'public' and remediation could not be confirmed ({remediation}). "
                    f"VIDEO MAY BE PUBLIC ON YOUTUBE!"
                )
                msg = "CRITICAL: Upload returned public and auto-remediation could not be confirmed! Video may be public on YouTube."
            else:
                clip.publish_error = f"Remote privacy mismatch or unconfirmed: '{confirmed_privacy}'"
                msg = "Upload completed with privacy mismatch; manual review required"

        clip.youtube_short_id = youtube_short_id
        clip.published_at = datetime.utcnow()
        clip.metadata_status = "approved"
        await db.commit()

        return {
            "message": msg,
            "youtube_short_id": youtube_short_id,
            "url": result_yt["url"],
            "privacy": confirmed_privacy,
            "status": clip.publish_status,
            "remediation": remediation,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {e}")


@router.get("/{clip_id}/retention")
async def get_clip_retention(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Phase 10: Generate and return Retention Heatmap data."""
    from backend.models.models import ClipRetention
    import json
    
    # 1. Check if we already have it in DB
    result = await db.execute(select(ClipRetention).where(ClipRetention.clip_id == clip_id))
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "clip_id": clip_id,
            "overall_score": existing.overall_score,
            "risks": json.loads(existing.analysis_json)
        }
        
    # 2. If not, generate it
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip or not clip.output_path:
        raise HTTPException(status_code=404, detail="Clip or video file not found")
        
    import asyncio
    from backend.services.virality_predictor import ViralityPredictor
    predictor = ViralityPredictor()
    
    # Run analysis off the event loop via worker thread
    try:
        analysis = await asyncio.to_thread(predictor.analyze_clip, clip.output_path, clip_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media analysis failed: {e}")
    
    # 3. Store in DB
    risks_dict = [r.model_dump() for r in analysis.risks]
    new_record = ClipRetention(
        clip_id=clip_id,
        overall_score=analysis.overall_score,
        analysis_json=json.dumps(risks_dict)
    )
    db.add(new_record)
    await db.commit()
    
    return {
        "clip_id": clip_id,
        "overall_score": analysis.overall_score,
        "risks": risks_dict
    }


@router.post("/{clip_id}/autofix")
async def apply_autofix(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Phase 10: 1-Click Auto-Fix. Applies non-destructive zoom interventions as an autofix variant."""
    from backend.models.models import ClipRetention
    import json
    from backend.tasks.clip_tasks import apply_autofix_task
    from backend.services.autofix_planner import AutoFixPlanner
    from backend.services.layout_engine import LayoutEngine
    from backend.models.retention import DropoffRisk
    
    # 1. Get clip and retention data
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    ret_result = await db.execute(select(ClipRetention).where(ClipRetention.clip_id == clip_id))
    retention = ret_result.scalar_one_or_none()
    if not retention:
        raise HTTPException(status_code=400, detail="Retention analysis not found. Call /retention first.")
        
    risks = [DropoffRisk(**r) for r in json.loads(retention.analysis_json)]
    
    # 2. Get the base layout plan
    base_plan = LayoutEngine.create_vertical_plan(1080, 1920)
    # 3. Apply AutoFix
    planner = AutoFixPlanner()
    new_plan = planner.generate_plan(base_plan, risks)
    
    # 4. Trigger non-destructive variant task
    task = apply_autofix_task.delay(clip_id=clip_id, layout_plan_dict=new_plan.model_dump())
    
    return {
        "message": "Auto-fix variant rendering started.",
        "task_id": task.id,
        "clip_id": clip_id,
        "interventions": len(new_plan.regions[0].zoom_interventions)
    }


@router.get("/{clip_id}/sfx-plan")
async def get_clip_sfx_plan(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Phase 2.1.1B: Read-only retrieval of existing persisted SFX Plan."""
    from backend.models.models import ClipSFXPlan
    import json
    
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    plan_result = await db.execute(select(ClipSFXPlan).where(ClipSFXPlan.clip_id == clip_id))
    plan_record = plan_result.scalar_one_or_none()
    if not plan_record:
        raise HTTPException(status_code=404, detail="SFX plan not found. Explicitly generate plan first.")
        
    return json.loads(plan_record.plan_json)


@router.post("/{clip_id}/sfx-plan")
async def generate_clip_sfx_plan(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Phase 2.1.1B: Explicit generation and persistence of an SFX Plan based on retention risks."""
    from backend.models.models import ClipRetention
    from backend.services.sfx_planner import SFXPlanner
    import json
    import asyncio
    from pathlib import Path
    
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    ret_result = await db.execute(select(ClipRetention).where(ClipRetention.clip_id == clip_id))
    retention = ret_result.scalar_one_or_none()
    if not retention:
        if not clip.output_path or not Path(clip.output_path).exists():
            raise HTTPException(status_code=400, detail="Clip video file not found or not rendered")
            
        from backend.services.virality_predictor import ViralityPredictor
        predictor = ViralityPredictor()
        try:
            analysis = await asyncio.to_thread(predictor.analyze_clip, clip.output_path, clip_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Media analysis failed: {e}")
            
        risks_dict = [r.model_dump() for r in analysis.risks]
        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=analysis.overall_score,
            analysis_json=json.dumps(risks_dict)
        )
        db.add(retention)
        await db.commit()
        await db.refresh(retention)
        
    # Generate SFX Plan
    planner = SFXPlanner()
    try:
        plan = await planner.generate_plan(clip_id=clip_id, db=db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return plan.model_dump()



@router.post("/{clip_id}/sfx-apply")
async def apply_sfx(clip_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Phase 11: Applies an SFX Plan to a clip via Celery task."""
    from backend.tasks.clip_tasks import apply_sfx_task
    from backend.models.sfx import SFXPlan
    
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    # Validate payload
    try:
        plan = SFXPlan(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid SFX plan: {e}")
        
    if not plan.placements:
        return {
            "applied": False,
            "message": "No suitable sound-effect placements were found. The clip was not modified.",
            "task_id": None,
            "clip_id": clip_id
        }

    # Trigger SFX task
    task = apply_sfx_task.delay(clip_id=clip_id, sfx_plan_dict=plan.model_dump())
    
    return {"applied": True, "message": "SFX apply task started", "task_id": task.id, "clip_id": clip_id}


@router.get("/{clip_id}/broll-plan")
async def get_clip_broll_plan(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Phase 12: Generate and return a B-roll Plan based on transcript keywords."""
    from backend.services.broll_planner import BrollPlanner
    
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    transcript = clip.transcript_segment or clip.description or ""
    
    # Generate B-roll Plan
    planner = BrollPlanner()
    try:
        plan = await planner.create_plan(
            db=db,
            clip_id=clip_id,
            transcript=[{"word": word, "start": i*1.5, "end": (i+1)*1.5} for i, word in enumerate(transcript.split())], # Mock transcript for testing
            clip_start_time=0.0,
            clip_end_time=float(clip.duration) if clip.duration else 10.0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return plan.model_dump()


@router.post("/{clip_id}/broll-apply")
async def apply_broll(clip_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Phase 12: Applies a B-roll Plan to a clip via Celery task."""
    from backend.tasks.clip_tasks import apply_broll_task
    from backend.models.broll import BrollPlan
    
    clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    # Validate payload
    try:
        plan = BrollPlan(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid B-roll plan: {e}")
        
    if not plan.placements:
        return {
            "applied": False,
            "message": "No B-roll placements found in plan. Clip was not modified.",
            "task_id": None,
            "clip_id": clip_id
        }

    # Trigger B-roll task
    task = apply_broll_task.delay(clip_id=clip_id, broll_plan_dict=plan.model_dump())
    
    return {"applied": True, "message": "B-roll apply task started", "task_id": task.id, "clip_id": clip_id}


# ──── Phase 13: Hook & Voiceover Endpoints ────

@router.get("/{clip_id}/hook")
async def get_hook_plan(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve the stored HookPlan for a clip."""
    from backend.models.models import ClipHookPlan
    import json

    result = await db.execute(select(ClipHookPlan).where(ClipHookPlan.clip_id == clip_id))
    plan_record = result.scalar_one_or_none()
    if not plan_record:
        raise HTTPException(status_code=404, detail="Hook plan not found")
    return json.loads(plan_record.plan_json)


@router.post("/{clip_id}/hook/plan")
async def generate_hook_plan_endpoint(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger hook opportunity analysis for a clip."""
    from backend.tasks.hook_tasks import analyze_hook_opportunities_task

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    task = analyze_hook_opportunities_task.delay(clip_id=clip_id)
    return {"message": "Hook opportunity analysis started", "task_id": task.id, "clip_id": clip_id}


@router.post("/{clip_id}/hook/apply")
async def apply_hook_plan_endpoint(clip_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Apply a validated HookPlan to a clip (voiceover + kinetic zoom + audio mix)."""
    from backend.tasks.hook_tasks import apply_hook_task
    from backend.models.hook import HookPlan

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    try:
        plan = HookPlan(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid Hook plan: {e}")

    task = apply_hook_task.delay(clip_id=clip_id, hook_plan_dict=plan.model_dump())
    return {"message": "Hook apply task started", "task_id": task.id, "clip_id": clip_id}
