"""
Destination Outro Core Service.
Handles media probing (FFprobe, Pillow), validation, canonical storage,
versioning, and lifecycle management for destination channel outros.
"""
import os
import shutil
import subprocess
import struct
import json
import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Any

from PIL import Image
from fastapi import UploadFile
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.models import Channel, DestinationOutro

logger = logging.getLogger(__name__)


# ─── Custom Exceptions ────────────────────────────────────────────────────────

class OutroServiceError(Exception):
    """Base exception for outro service operations."""
    pass


class InvalidOutroError(OutroServiceError):
    """Raised when an uploaded outro file fails container, codec, or duration validation."""
    pass


class OutroNotFoundError(OutroServiceError):
    """Raised when an active outro does not exist for a requested destination channel."""
    pass


class ChannelNotFoundError(OutroServiceError):
    """Raised when a destination channel ID does not exist or is not a valid destination."""
    pass


class OutroRenderError(OutroServiceError):
    """Raised when rendering or verifying a destination clip + outro variant fails."""
    pass


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class OutroProbedMetadata:
    width: int
    height: int
    duration_seconds: float
    fps: Optional[float]
    has_audio: bool
    audio_channels: Optional[int]
    audio_sample_rate: Optional[int]
    video_codec: Optional[str]
    audio_codec: Optional[str]
    file_size_bytes: int
    format_name: Optional[str]


# ─── Path Resolution & Security ───────────────────────────────────────────────

def get_ffprobe_binary() -> str:
    """Dynamically discover ffprobe binary."""
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        for candidate in [
            "/usr/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        ]:
            if os.path.exists(candidate):
                ffprobe_bin = candidate
                break
    return ffprobe_bin or "ffprobe"


def get_ffmpeg_binary() -> str:
    """Dynamically discover ffmpeg binary."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        for candidate in [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]:
            if os.path.exists(candidate):
                ffmpeg_bin = candidate
                break
    return ffmpeg_bin or "ffmpeg"


def _is_within_any_root(candidate: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            candidate.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def resolve_safe_outro_path(path_or_key: str | Path) -> Path:
    """
    Resolve a stored relative key (e.g. 'uploads/outros/...') or absolute path
    to a concrete, canonical Path while strictly preventing path traversal attacks.
    Supports overridden settings.UPLOAD_DIR / settings.OUTPUT_DIR in isolated tests.
    """
    raw_str = str(path_or_key or "").strip()
    if not raw_str:
        raise InvalidOutroError("Outro file path cannot be empty.")

    str_path = raw_str.replace("\\", "/")
    base_dir = settings.BASE_DIR.resolve()
    upload_dir = settings.UPLOAD_DIR.resolve()
    output_dir = settings.OUTPUT_DIR.resolve()

    if ".." in Path(str_path).parts:
        raise InvalidOutroError(f"Path traversal detected: {path_or_key}")

    if os.path.isabs(raw_str) or os.path.isabs(str_path):
        resolved = Path(raw_str).resolve()
        if not _is_within_any_root(resolved, [base_dir, upload_dir, output_dir]):
            raise InvalidOutroError(f"Path traversal detected: {path_or_key}")
        return resolved

    rel_clean = str_path.lstrip("/")
    if rel_clean.startswith("uploads/"):
        sub_key = rel_clean[len("uploads/"):]
        upload_candidate = (upload_dir / sub_key).resolve()
        base_candidate = (base_dir / rel_clean).resolve()
        resolved = upload_candidate if (upload_candidate.exists() or not base_candidate.exists()) else base_candidate
    elif rel_clean.startswith("outputs/"):
        sub_key = rel_clean[len("outputs/"):]
        output_candidate = (output_dir / sub_key).resolve()
        base_candidate = (base_dir / rel_clean).resolve()
        resolved = output_candidate if (output_candidate.exists() or not base_candidate.exists()) else base_candidate
    else:
        resolved = (base_dir / rel_clean).resolve()

    if not _is_within_any_root(resolved, [base_dir, upload_dir, output_dir]):
        raise InvalidOutroError(f"Path traversal detected: {path_or_key}")

    return resolved


def resolve_clip_base_video_path(clip_output_path: str | Path) -> Path:
    """
    Resolve a base clip's storage key ('outputs/{video_id}/clips/{clip_id}/final.mp4')
    or filesystem path safely without modifying the underlying base asset.
    """
    raw_str = str(clip_output_path or "").strip()
    if not raw_str:
        raise OutroRenderError("Clip has no output_path configured.")

    norm_str = raw_str.replace("\\", "/")
    if ".." in Path(norm_str).parts:
        raise OutroRenderError(f"Invalid clip output path: {clip_output_path}")

    p = Path(raw_str)
    if p.is_absolute():
        return p.resolve()

    output_dir = settings.OUTPUT_DIR.resolve()
    base_dir = settings.BASE_DIR.resolve()
    rel_clean = norm_str.lstrip("/")
    if rel_clean.startswith("outputs/"):
        sub_key = rel_clean[len("outputs/"):]
        out_cand = (output_dir / sub_key).resolve()
        base_cand = (base_dir / rel_clean).resolve()
        resolved = out_cand if (out_cand.exists() or not base_cand.exists()) else base_cand
    else:
        out_cand = (output_dir / rel_clean).resolve()
        base_cand = (base_dir / rel_clean).resolve()
        resolved = out_cand if out_cand.exists() else base_cand

    if not _is_within_any_root(resolved, [output_dir, base_dir]):
        raise OutroRenderError(f"Path traversal detected in clip output_path: {clip_output_path}")
    return resolved


def has_faststart_moov_before_mdat(file_path: Path) -> bool:
    """
    Inspect top-level MP4/QuickTime ISO BMFF atoms and return True iff both
    'moov' and 'mdat' exist and 'moov' appears before 'mdat' (faststart verified).
    """
    if not file_path.exists() or file_path.stat().st_size < 16:
        return False
    moov_offset: int | None = None
    mdat_offset: int | None = None
    file_size = file_path.stat().st_size
    offset = 0
    try:
        with open(file_path, "rb") as f:
            while offset + 8 <= file_size:
                f.seek(offset)
                header = f.read(8)
                if len(header) < 8:
                    break
                size32, atom_type_bytes = struct.unpack(">I4s", header)
                atom_type = atom_type_bytes.decode("latin-1", errors="ignore")
                if atom_type == "moov" and moov_offset is None:
                    moov_offset = offset
                elif atom_type == "mdat" and mdat_offset is None:
                    mdat_offset = offset

                if moov_offset is not None and mdat_offset is not None:
                    return moov_offset < mdat_offset

                if size32 == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    atom_size = struct.unpack(">Q", ext)[0]
                elif size32 == 0:
                    atom_size = file_size - offset
                else:
                    atom_size = size32

                if atom_size < 8:
                    break
                offset += atom_size
    except OSError:
        return False

    return moov_offset is not None and mdat_offset is not None and moov_offset < mdat_offset


# ─── Media Probing ────────────────────────────────────────────────────────────

def probe_media_with_ffprobe(file_path: Path) -> dict:
    """
    Execute ffprobe to extract JSON stream and format metadata.
    """
    if not file_path.exists():
        raise InvalidOutroError(f"Media file not found: {file_path}")

    ffprobe_bin = get_ffprobe_binary()
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries",
        "format=format_name,duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,channels,sample_rate,duration",
        "-of", "json",
        str(file_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise InvalidOutroError("Media probing timed out after 30 seconds.")
    except Exception as e:
        raise InvalidOutroError(f"Failed to execute ffprobe: {e}")

    if result.returncode != 0:
        raise InvalidOutroError(f"FFprobe failed (code {result.returncode}): {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise InvalidOutroError(f"Failed to parse ffprobe JSON output: {e}")

    return data


def validate_video_outro(
    file_path: Path,
    min_duration: float = 0.5,
    max_duration: float = 30.0,
) -> OutroProbedMetadata:
    """
    Validate video outro file container, dimensions, duration, and audio presence.
    """
    if not file_path.exists() or file_path.stat().st_size == 0:
        raise InvalidOutroError("Video outro file is empty or missing.")

    data = probe_media_with_ffprobe(file_path)
    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise InvalidOutroError("No video stream found in uploaded file.")

    v_stream = video_streams[0]
    width = v_stream.get("width")
    height = v_stream.get("height")
    if not width or not height or width <= 0 or height <= 0:
        raise InvalidOutroError(f"Invalid video dimensions: {width}x{height}")

    # Parse duration (prefer format duration, fallback to stream duration)
    raw_duration = format_info.get("duration") or v_stream.get("duration")
    if not raw_duration:
        raise InvalidOutroError("Could not determine video duration.")
    try:
        duration_seconds = float(raw_duration)
    except (ValueError, TypeError):
        raise InvalidOutroError(f"Invalid duration value: {raw_duration}")

    if duration_seconds < min_duration:
        raise InvalidOutroError(
            f"Video outro duration ({duration_seconds:.2f}s) is shorter than minimum allowed ({min_duration}s)."
        )
    if duration_seconds > max_duration:
        raise InvalidOutroError(
            f"Video outro duration ({duration_seconds:.2f}s) exceeds maximum allowed ({max_duration}s)."
        )

    # Parse FPS
    fps = None
    r_frame_rate = v_stream.get("r_frame_rate")
    if r_frame_rate and "/" in r_frame_rate:
        try:
            num, den = r_frame_rate.split("/")
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)
        except Exception:
            fps = None

    # Detect audio stream
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    has_audio = len(audio_streams) > 0
    audio_channels = None
    audio_sample_rate = None
    audio_codec = None

    if has_audio:
        a_stream = audio_streams[0]
        audio_channels = a_stream.get("channels")
        try:
            audio_sample_rate = int(a_stream.get("sample_rate", 0)) or None
        except (ValueError, TypeError):
            audio_sample_rate = None
        audio_codec = a_stream.get("codec_name")

    file_size_bytes = file_path.stat().st_size

    return OutroProbedMetadata(
        width=width,
        height=height,
        duration_seconds=round(duration_seconds, 2),
        fps=fps,
        has_audio=has_audio,
        audio_channels=audio_channels,
        audio_sample_rate=audio_sample_rate,
        video_codec=v_stream.get("codec_name"),
        audio_codec=audio_codec,
        file_size_bytes=file_size_bytes,
        format_name=format_info.get("format_name"),
    )


def validate_image_outro(
    file_path: Path,
    duration_seconds: float = 3.0,
    min_duration: float = 0.5,
    max_duration: float = 15.0,
) -> OutroProbedMetadata:
    """
    Validate image outro format and dimensions using Pillow, and enforce duration bounds.
    """
    if not file_path.exists() or file_path.stat().st_size == 0:
        raise InvalidOutroError("Image outro file is empty or missing.")

    if duration_seconds < min_duration or duration_seconds > max_duration:
        raise InvalidOutroError(
            f"Image outro duration ({duration_seconds}s) must be between {min_duration}s and {max_duration}s."
        )

    try:
        with Image.open(file_path) as img:
            img.verify()
            format_name = img.format
            width, height = img.size
    except Exception as e:
        raise InvalidOutroError(f"Invalid or corrupted image file: {e}")

    allowed_formats = {"PNG", "JPEG", "JPG", "WEBP"}
    if not format_name or format_name.upper() not in allowed_formats:
        raise InvalidOutroError(
            f"Unsupported image format: {format_name}. Allowed: {', '.join(sorted(allowed_formats))}"
        )

    if width <= 0 or height <= 0:
        raise InvalidOutroError(f"Invalid image dimensions: {width}x{height}")

    file_size_bytes = file_path.stat().st_size

    return OutroProbedMetadata(
        width=width,
        height=height,
        duration_seconds=round(duration_seconds, 2),
        fps=None,
        has_audio=False,
        audio_channels=None,
        audio_sample_rate=None,
        video_codec=None,
        audio_codec=None,
        file_size_bytes=file_size_bytes,
        format_name=format_name.lower(),
    )


def validate_outro_file(
    file_path: Path,
    outro_type: str,
    duration_seconds: Optional[float] = None,
) -> OutroProbedMetadata:
    """
    Validate uploaded outro file based on outro_type ('video' or 'image').
    """
    normalized_type = outro_type.strip().lower()
    if normalized_type == "video":
        return validate_video_outro(file_path)
    elif normalized_type == "image":
        parsed_duration = 3.0 if duration_seconds is None else duration_seconds
        return validate_image_outro(file_path, duration_seconds=parsed_duration)
    else:
        raise InvalidOutroError(f"Unsupported outro_type: '{outro_type}'. Must be 'video' or 'image'.")


# ─── Outro Lifecycle & Storage Operations ────────────────────────────────────

async def save_destination_outro(
    channel: Channel,
    file: UploadFile,
    outro_type: str,
    duration_seconds: Optional[float],
    db: AsyncSession,
) -> DestinationOutro:
    """
    Stage uploaded file to temp, validate media metadata, promote to canonical
    storage path (uploads/outros/{channel_id}/outro_{uuid}.{ext}), deactivate previous
    active outro, increment version, and link to channel.
    """
    normalized_type = outro_type.strip().lower()
    ext = Path(file.filename or "").suffix.lower()
    if not ext:
        ext = ".mp4" if normalized_type == "video" else ".png"

    # 1. Stage upload to temporary staging file
    temp_dir = settings.UPLOAD_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"stage_outro_{uuid.uuid4().hex}{ext}"

    max_bytes = 50 * 1024 * 1024 if normalized_type == "video" else 10 * 1024 * 1024
    bytes_read = 0

    try:
        with open(temp_file, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    raise InvalidOutroError(f"Uploaded file exceeds maximum limit of {max_bytes // (1024*1024)}MB.")
                out_f.write(chunk)

        # 2. Validate media
        meta = validate_outro_file(temp_file, normalized_type, duration_seconds)

        # 3. Promote file to canonical destination directory
        channel_id = str(channel.id)
        outros_dir = settings.UPLOAD_DIR / "outros" / channel_id
        outros_dir.mkdir(parents=True, exist_ok=True)

        outro_uuid = uuid.uuid4().hex
        final_filename = f"outro_{outro_uuid}{ext}"
        final_path = outros_dir / final_filename
        storage_key = f"uploads/outros/{channel_id}/{final_filename}"

        shutil.move(str(temp_file), str(final_path))

        # 4. Compute next version number for channel
        result = await db.execute(
            select(func.max(DestinationOutro.version)).where(
                DestinationOutro.channel_id == channel_id
            )
        )
        current_max_ver = result.scalar() or 0
        new_version = current_max_ver + 1

        # 5. Deactivate previous active outro(s)
        await db.execute(
            update(DestinationOutro)
            .where(DestinationOutro.channel_id == channel_id, DestinationOutro.is_active == True)
            .values(is_active=False)
        )

        # 6. Create new DestinationOutro record
        new_outro = DestinationOutro(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            file_path=storage_key,
            original_filename=Path(file.filename or "outro").name,
            file_size_bytes=meta.file_size_bytes,
            outro_type=normalized_type,
            duration_seconds=meta.duration_seconds,
            width=meta.width,
            height=meta.height,
            fps=meta.fps,
            has_audio=meta.has_audio,
            version=new_version,
            is_active=True,
        )
        db.add(new_outro)
        await db.flush()

        # 7. Update channel active_outro_id
        channel.active_outro_id = new_outro.id
        await db.commit()
        await db.refresh(new_outro)

        return new_outro

    except Exception:
        # Cleanup staging file if left behind
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        raise


async def get_active_destination_outro(
    channel_id: str,
    db: AsyncSession,
) -> Optional[DestinationOutro]:
    """
    Retrieve active DestinationOutro for channel.
    """
    result = await db.execute(
        select(DestinationOutro).where(
            DestinationOutro.channel_id == channel_id,
            DestinationOutro.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def remove_destination_outro(
    channel: Channel,
    db: AsyncSession,
) -> bool:
    """
    Unlink active outro from destination channel and mark active outro inactive.
    Preserves historical file on disk for existing PublishTarget integrity (soft-delete).
    """
    channel_id = str(channel.id)

    # Deactivate current outro
    await db.execute(
        update(DestinationOutro)
        .where(DestinationOutro.channel_id == channel_id, DestinationOutro.is_active == True)
        .values(is_active=False)
    )

    # Unlink active outro id
    channel.active_outro_id = None
    await db.commit()
    return True


# ─── Synchronous Helpers for Celery Tasks ─────────────────────────────────────

def get_active_destination_outro_sync(
    channel_id: str,
    session: Session,
) -> Optional[DestinationOutro]:
    """
    Synchronous helper to retrieve active DestinationOutro for worker tasks.
    """
    return session.query(DestinationOutro).filter(
        DestinationOutro.channel_id == channel_id,
        DestinationOutro.is_active == True,
    ).first()


def remove_destination_outro_sync(
    channel_id: str,
    session: Session,
) -> bool:
    """
    Synchronous helper to remove active outro for worker/test tasks.
    """
    ch = session.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        return False

    session.query(DestinationOutro).filter(
        DestinationOutro.channel_id == channel_id,
        DestinationOutro.is_active == True,
    ).update({"is_active": False})

    ch.active_outro_id = None
    session.commit()
    return True


# ─── Destination-Specific Render Engine & Variant Cache ─────────────────────

def _is_real_outro_record(record: Any) -> bool:
    """Guard against unconfigured MagicMock objects in unit test suites."""
    if record is None:
        return False
    return (
        isinstance(getattr(record, "id", None), str)
        and isinstance(getattr(record, "file_path", None), str)
        and getattr(record, "is_active", False) is True
        and getattr(record, "outro_type", None) in ("video", "image")
    )


def _validate_safe_segment(val: str, field_name: str) -> str:
    clean = str(val or "").strip()
    if not clean or "/" in clean or "\\" in clean or ".." in clean:
        raise OutroRenderError(f"Unsafe {field_name} segment: '{val}'")
    return clean


def get_destination_variant_paths(clip: Any, destination_id: str) -> Tuple[str, Path, Path]:
    """
    Return canonical `(storage_key, variant_file_path, meta_file_path)` for a clip + destination.
    Pattern: outputs/{video_id}/clips/{clip_id}/destinations/{destination_id}/final.mp4
    """
    video_seg = _validate_safe_segment(getattr(clip, "video_id", None) or "unknown_video", "video_id")
    clip_seg = _validate_safe_segment(getattr(clip, "id", ""), "clip_id")
    dest_seg = _validate_safe_segment(destination_id, "destination_id")

    storage_key = f"outputs/{video_seg}/clips/{clip_seg}/destinations/{dest_seg}/final.mp4"
    output_root = settings.OUTPUT_DIR.resolve()
    variant_path = (output_root / video_seg / "clips" / clip_seg / "destinations" / dest_seg / "final.mp4").resolve()
    try:
        variant_path.relative_to(output_root)
    except ValueError:
        raise OutroRenderError(f"Destination variant path escaped OUTPUT_DIR: {variant_path}")

    meta_path = variant_path.with_name("variant_meta.json")
    return storage_key, variant_path, meta_path


def _probe_base_video(file_path: Path) -> dict:
    """Probe base clip file for duration, dimensions, audio, and subtitle invariant."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        raise OutroRenderError(f"Base clip video file missing or empty: {file_path}")

    data = probe_media_with_ffprobe(file_path)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    v_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not v_streams:
        raise OutroRenderError(f"Base clip has no video stream: {file_path}")

    v0 = v_streams[0]
    width = int(v0.get("width") or 1080)
    height = int(v0.get("height") or 1920)
    width = max(2, width - (width % 2))
    height = max(2, height - (height % 2))

    raw_dur = fmt.get("duration") or v0.get("duration")
    try:
        duration = float(raw_dur) if raw_dur is not None else 0.0
    except (ValueError, TypeError):
        duration = 0.0
    if duration <= 0.0:
        raise OutroRenderError(f"Base clip duration is invalid ({raw_dur}): {file_path}")

    a_streams = [s for s in streams if s.get("codec_type") == "audio"]
    sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "has_audio": len(a_streams) > 0,
        "subtitle_count": len(sub_streams),
    }


def compute_outro_signature(outro: DestinationOutro, base_video_path: Path) -> dict:
    """Compute a deterministic cache key capturing outro asset, version, duration, and base clip."""
    base_size = None
    base_mtime_ns = None
    if base_video_path.exists():
        st = base_video_path.stat()
        base_size = st.st_size
        base_mtime_ns = st.st_mtime_ns

    return {
        "outro_id": str(outro.id),
        "outro_version": int(outro.version or 1),
        "outro_type": str(outro.outro_type),
        "duration_seconds": round(float(outro.duration_seconds), 2),
        "outro_file_path": str(outro.file_path),
        "base_size": base_size,
        "base_mtime_ns": base_mtime_ns,
    }


def _read_variant_meta(meta_path: Path) -> Optional[dict]:
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _is_valid_cached_variant(variant_path: Path, meta_path: Path, expected_sig: dict) -> bool:
    if not variant_path.exists() or variant_path.stat().st_size == 0:
        return False
    meta = _read_variant_meta(meta_path)
    if not meta or meta.get("signature") != expected_sig:
        return False
    try:
        probe_data = probe_media_with_ffprobe(variant_path)
        streams = probe_data.get("streams", [])
        v_streams = [s for s in streams if s.get("codec_type") == "video"]
        a_streams = [s for s in streams if s.get("codec_type") == "audio"]
        s_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        if not v_streams or not a_streams or s_streams:
            return False
        if not has_faststart_moov_before_mdat(variant_path):
            return False
        return True
    except Exception:
        return False


def render_clip_with_outro(
    base_video_path: Path,
    output_path: Path,
    outro: DestinationOutro,
    max_total_duration: Optional[float] = 180.0,
) -> dict:
    """
    Append a destination-specific outro (MP4 video or static image with configured display duration)
    to `base_video_path` into a separate `output_path` without ever modifying `base_video_path`.

    Enforces:
    - Aspect-ratio preservation (no unwanted stretching; black letterbox/pillarbox padding)
    - Uniform codec / pixel format (yuv420p), 30fps, stereo AAC 44100 Hz (synthesizes silent
      audio track if either base clip or outro lacks audio so FFmpeg concat never fails)
    - `-sn` subtitle exclusion invariant
    - `-movflags +faststart` verified via MP4 atom order (`moov` before `mdat`)
    - Atomic temp-file write + post-render FFprobe verification before promotion
    """
    base_video_path = Path(base_video_path)
    output_path = Path(output_path)

    base_info = _probe_base_video(base_video_path)
    base_dur = float(base_info["duration"])
    target_w = int(base_info["width"])
    target_h = int(base_info["height"])

    try:
        outro_path = resolve_safe_outro_path(outro.file_path)
    except InvalidOutroError as exc:
        raise OutroRenderError(f"Outro path invalid or unsafe: {exc}") from exc

    if not outro_path.exists() or outro_path.stat().st_size == 0:
        raise OutroNotFoundError(
            f"Configured outro file is missing or unavailable on disk: {outro.file_path}"
        )

    outro_type = str(outro.outro_type or "").strip().lower()
    if outro_type == "video":
        try:
            outro_meta = validate_video_outro(outro_path)
        except InvalidOutroError as exc:
            raise OutroRenderError(f"Video outro validation failed: {exc}") from exc
        outro_dur = float(outro_meta.duration_seconds)
        outro_has_audio = bool(outro_meta.has_audio)
    elif outro_type == "image":
        outro_dur = float(outro.duration_seconds or 3.0)
        try:
            validate_image_outro(outro_path, duration_seconds=outro_dur)
        except InvalidOutroError as exc:
            raise OutroRenderError(f"Image outro validation failed: {exc}") from exc
        outro_has_audio = False
    else:
        raise OutroRenderError(f"Unsupported outro type '{outro.outro_type}'.")

    expected_total = base_dur + outro_dur
    if max_total_duration is not None and expected_total > (max_total_duration + 0.1):
        raise OutroRenderError(
            f"Combined clip ({base_dur:.2f}s) + outro ({outro_dur:.2f}s) = {expected_total:.2f}s "
            f"exceeds maximum Shorts duration limit of {max_total_duration:.1f}s."
        )

    filter_parts = [
        (
            f"[0:v]format=rgba,scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v0]"
        )
    ]

    if base_info["has_audio"]:
        filter_parts.append(
            "[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
            "aresample=async=1:first_pts=0,asetpts=PTS-STARTPTS[a0]"
        )
    else:
        filter_parts.append(
            f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={base_dur:.3f},"
            "asetpts=PTS-STARTPTS[a0]"
        )

    ffmpeg_bin = get_ffmpeg_binary()
    inputs = ["-i", str(base_video_path)]

    if outro_type == "video":
        inputs.extend(["-i", str(outro_path)])
        filter_parts.append(
            f"[1:v]format=rgba,scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v1]"
        )
        if outro_has_audio:
            filter_parts.append(
                "[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                "aresample=async=1:first_pts=0,asetpts=PTS-STARTPTS[a1]"
            )
        else:
            filter_parts.append(
                f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={outro_dur:.3f},"
                "asetpts=PTS-STARTPTS[a1]"
            )
    else:
        # Composite image centered onto uniform black canvas so transparent PNG/WebP never distorts or leaks alpha
        inputs.extend(["-loop", "1", "-framerate", "30", "-t", f"{outro_dur:.3f}", "-i", str(outro_path)])
        filter_parts.append(
            f"color=c=black:s={target_w}x{target_h}:r=30:d={outro_dur:.3f}[bg1];"
            f"[1:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,format=rgba[fg1];"
            f"[bg1][fg1]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p,"
            f"trim=duration={outro_dur:.3f},setpts=PTS-STARTPTS[v1]"
        )
        filter_parts.append(
            f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={outro_dur:.3f},"
            "asetpts=PTS-STARTPTS[a1]"
        )

    filter_parts.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]")
    filter_complex = ";".join(filter_parts)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.parent / f".tmp_{output_path.stem}_{uuid.uuid4().hex[:8]}.mp4"

    cmd = [
        ffmpeg_bin,
        "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-sn",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(tmp_path),
    ]

    try:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired as exc:
            raise OutroRenderError("FFmpeg destination outro render timed out after 300s.") from exc
        except Exception as exc:
            raise OutroRenderError(f"Failed to launch FFmpeg for outro render: {exc}") from exc

        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "").strip()[-800:]
            raise OutroRenderError(f"FFmpeg outro render failed (code {proc.returncode}): {stderr_tail}")

        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise OutroRenderError("Rendered destination output is missing or 0 bytes.")

        probe_out = probe_media_with_ffprobe(tmp_path)
        streams = probe_out.get("streams", [])
        fmt = probe_out.get("format", {})
        v_streams = [s for s in streams if s.get("codec_type") == "video"]
        a_streams = [s for s in streams if s.get("codec_type") == "audio"]
        s_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        if not v_streams:
            raise OutroRenderError("Rendered destination output contains no video stream.")
        if not a_streams:
            raise OutroRenderError("Rendered destination output contains no audio stream.")
        if s_streams:
            raise OutroRenderError("Rendered destination output violated zero-subtitle invariant.")

        out_w = int(v_streams[0].get("width") or 0)
        out_h = int(v_streams[0].get("height") or 0)
        if out_w != target_w or out_h != target_h:
            raise OutroRenderError(
                f"Rendered dimension mismatch: expected {target_w}x{target_h}, got {out_w}x{out_h}"
            )

        actual_dur = float(fmt.get("duration") or v_streams[0].get("duration") or 0.0)
        if actual_dur <= 0.0:
            raise OutroRenderError(f"Rendered output has invalid duration: {actual_dur}")
        if abs(actual_dur - expected_total) > 0.75:
            raise OutroRenderError(
                f"Rendered duration mismatch: expected ~{expected_total:.2f}s, got {actual_dur:.2f}s"
            )
        if max_total_duration is not None and actual_dur > (max_total_duration + 0.1):
            raise OutroRenderError(
                f"Rendered duration {actual_dur:.2f}s exceeds limit {max_total_duration:.1f}s"
            )

        if not has_faststart_moov_before_mdat(tmp_path):
            raise OutroRenderError("Rendered MP4 failed faststart check (moov atom not placed before mdat).")

        os.replace(str(tmp_path), str(output_path))
        return {
            "output_path": str(output_path),
            "width": out_w,
            "height": out_h,
            "base_duration": round(base_dur, 2),
            "outro_duration": round(outro_dur, 2),
            "combined_duration": round(actual_dur, 2),
            "faststart": True,
            "subtitle_count": 0,
            "ffmpeg_cmd": cmd,
        }
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def render_or_reuse_destination_variant_from_records(
    clip: Any,
    dest_channel: Any,
    active_outro: Optional[Any],
    force: bool = False,
    local_base_path: Optional[Path] = None,
) -> dict:
    """
    Pure/session-free variant renderer & cache lookup using already-fetched records/snapshots.
    Leaves `clip.output_path` (`final.mp4`) completely untouched.
    """
    if not dest_channel or not getattr(dest_channel, "is_destination", False):
        dest_ref = getattr(dest_channel, "id", None) or "unknown"
        raise ChannelNotFoundError(f"Destination channel '{dest_ref}' not found.")

    base_path = Path(local_base_path).resolve() if local_base_path else resolve_clip_base_video_path(clip.output_path)
    base_info = _probe_base_video(base_path)
    base_dur = float(base_info["duration"])

    if not _is_real_outro_record(active_outro):
        active_outro = None

    variant_key, variant_path, meta_path = get_destination_variant_paths(clip, str(dest_channel.id))

    if active_outro is None:
        for stale in (variant_path, meta_path):
            if stale.exists():
                try:
                    stale.unlink()
                except OSError:
                    pass
        return {
            "has_outro": False,
            "video_path": str(base_path),
            "storage_key": str(clip.output_path or base_path),
            "outro_id": None,
            "outro_version": None,
            "outro_type": None,
            "base_duration": round(base_dur, 2),
            "outro_duration": 0.0,
            "combined_duration": round(base_dur, 2),
            "rendered": False,
            "reused_cache": False,
        }

    expected_sig = compute_outro_signature(active_outro, base_path)
    if not force and _is_valid_cached_variant(variant_path, meta_path, expected_sig):
        cached_meta = _read_variant_meta(meta_path) or {}
        combined_dur = float(cached_meta.get("combined_duration") or (base_dur + float(active_outro.duration_seconds)))
        return {
            "has_outro": True,
            "video_path": str(variant_path),
            "storage_key": variant_key,
            "outro_id": str(active_outro.id),
            "outro_version": int(active_outro.version or 1),
            "outro_type": str(active_outro.outro_type),
            "base_duration": round(base_dur, 2),
            "outro_duration": round(float(active_outro.duration_seconds), 2),
            "combined_duration": round(combined_dur, 2),
            "rendered": False,
            "reused_cache": True,
        }

    render_stats = render_clip_with_outro(
        base_video_path=base_path,
        output_path=variant_path,
        outro=active_outro,
    )

    meta_payload = {
        "signature": expected_sig,
        "clip_id": str(clip.id),
        "destination_id": str(dest_channel.id),
        "storage_key": variant_key,
        "outro_id": str(active_outro.id),
        "outro_version": int(active_outro.version or 1),
        "outro_type": str(active_outro.outro_type),
        "base_duration": render_stats["base_duration"],
        "outro_duration": render_stats["outro_duration"],
        "combined_duration": render_stats["combined_duration"],
        "width": render_stats["width"],
        "height": render_stats["height"],
        "faststart": True,
        "rendered_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp_meta = meta_path.with_suffix(".tmp.json")
    with open(tmp_meta, "w", encoding="utf-8") as mf:
        json.dump(meta_payload, mf, indent=2)
    os.replace(str(tmp_meta), str(meta_path))

    return {
        "has_outro": True,
        "video_path": str(variant_path),
        "storage_key": variant_key,
        "outro_id": str(active_outro.id),
        "outro_version": int(active_outro.version or 1),
        "outro_type": str(active_outro.outro_type),
        "base_duration": render_stats["base_duration"],
        "outro_duration": render_stats["outro_duration"],
        "combined_duration": render_stats["combined_duration"],
        "rendered": True,
        "reused_cache": False,
    }


def render_or_reuse_destination_variant_sync(
    clip: Any,
    destination_id: str,
    session: Session,
    force: bool = False,
    local_base_path: Optional[Path] = None,
) -> dict:
    """
    Synchronous render-or-reuse entrypoint for destination-specific clip outputs.
    - Leaves `clip.output_path` (`final.mp4`) completely untouched.
    - If the destination has no active outro, deletes any stale cached variant and returns base clip info.
    - If an active outro exists and a matching validated cache exists (unless `force=True`), reuses it.
    """
    ch = session.query(Channel).filter(
        Channel.id == destination_id,
        Channel.is_destination == True,
    ).first()
    if not ch:
        raise ChannelNotFoundError(f"Destination channel '{destination_id}' not found.")

    active_outro = get_active_destination_outro_sync(ch.id, session)
    return render_or_reuse_destination_variant_from_records(
        clip=clip,
        dest_channel=ch,
        active_outro=active_outro,
        force=force,
        local_base_path=local_base_path,
    )


def get_destination_preview_info_from_records(
    clip: Any,
    dest_channel: Any,
    active_outro: Optional[Any],
) -> dict:
    """
    Non-mutating preview metadata computation from already-fetched records/snapshots.
    """
    if not dest_channel or not getattr(dest_channel, "is_destination", False):
        dest_ref = getattr(dest_channel, "id", None) or "unknown"
        raise ChannelNotFoundError(f"Destination channel '{dest_ref}' not found.")

    base_file_missing = False
    preview_error: Optional[str] = None
    base_path: Optional[Path] = None
    try:
        base_path = resolve_clip_base_video_path(clip.output_path)
        base_info = _probe_base_video(base_path)
        base_dur = float(base_info["duration"])
    except OutroRenderError as exc:
        base_file_missing = True
        preview_error = str(exc)
        base_dur = float(getattr(clip, "duration", 0.0) or 0.0)

    if not _is_real_outro_record(active_outro):
        active_outro = None

    variant_key, variant_path, meta_path = get_destination_variant_paths(clip, str(dest_channel.id))

    if active_outro is None:
        return {
            "clip_id": str(clip.id),
            "destination_id": str(dest_channel.id),
            "destination_name": dest_channel.channel_name,
            "is_active": bool(dest_channel.is_active),
            "has_outro": False,
            "outro": None,
            "outro_file_missing": False,
            "base_file_missing": base_file_missing,
            "preview_error": preview_error,
            "base_duration": round(base_dur, 2),
            "outro_duration": 0.0,
            "combined_duration": round(base_dur, 2),
            "exceeds_shorts_limit": base_dur > 60.0,
            "variant_ready": not base_file_missing,
            "stale_variant": False,
            "storage_key": str(clip.output_path or (base_path or "")),
            "preview_url": f"/api/publish/clips/{clip.id}/destinations/{dest_channel.id}/preview",
        }

    outro_missing = False
    try:
        resolved_outro = resolve_safe_outro_path(active_outro.file_path)
        outro_missing = not (resolved_outro.exists() and resolved_outro.stat().st_size > 0)
    except InvalidOutroError:
        outro_missing = True

    outro_dur = round(float(active_outro.duration_seconds), 2)
    combined_dur = round(base_dur + outro_dur, 2)
    variant_matches = False
    stale_variant = False
    if not base_file_missing and base_path is not None and not outro_missing:
        expected_sig = compute_outro_signature(active_outro, base_path)
        meta = _read_variant_meta(meta_path)
        variant_matches = bool(
            variant_path.exists()
            and variant_path.stat().st_size > 0
            and meta
            and meta.get("signature") == expected_sig
        )
        stale_variant = bool(variant_path.exists() and not variant_matches)

    return {
        "clip_id": str(clip.id),
        "destination_id": str(dest_channel.id),
        "destination_name": dest_channel.channel_name,
        "is_active": bool(dest_channel.is_active),
        "has_outro": True,
        "outro_file_missing": outro_missing,
        "base_file_missing": base_file_missing,
        "preview_error": preview_error,
        "outro": {
            "id": str(active_outro.id),
            "outro_type": str(active_outro.outro_type),
            "duration_seconds": outro_dur,
            "version": int(active_outro.version or 1),
            "original_filename": active_outro.original_filename,
            "width": active_outro.width,
            "height": active_outro.height,
            "preview_url": f"/api/youtube-channels/{dest_channel.id}/outro/preview",
        },
        "base_duration": round(base_dur, 2),
        "outro_duration": outro_dur,
        "combined_duration": combined_dur,
        "exceeds_shorts_limit": combined_dur > 60.0,
        "variant_ready": variant_matches,
        "stale_variant": stale_variant,
        "storage_key": variant_key,
        "preview_url": f"/api/publish/clips/{clip.id}/destinations/{dest_channel.id}/preview",
    }


def get_destination_preview_info_sync(
    clip: Any,
    destination_id: str,
    session: Session,
) -> dict:
    """
    Non-mutating inspection returning base duration, active outro metadata, combined
    Shorts compatibility, and whether a matching destination variant is already cached.
    """
    ch = session.query(Channel).filter(
        Channel.id == destination_id,
        Channel.is_destination == True,
    ).first()
    if not ch:
        raise ChannelNotFoundError(f"Destination channel '{destination_id}' not found.")

    active_outro = get_active_destination_outro_sync(ch.id, session)
    return get_destination_preview_info_from_records(
        clip=clip,
        dest_channel=ch,
        active_outro=active_outro,
    )


async def render_or_reuse_destination_variant(
    clip_id: str,
    destination_id: str,
    force: bool = False,
) -> dict:
    """
    Async wrapper for FastAPI routes (runs FFmpeg/FFprobe rendering off the event loop).
    """
    import asyncio
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip as ClipModel

    def _run_sync() -> dict:
        with SyncSessionLocal() as session:
            clip_obj = session.query(ClipModel).filter(ClipModel.id == clip_id).first()
            if not clip_obj:
                raise OutroRenderError(f"Clip '{clip_id}' not found.")
            return render_or_reuse_destination_variant_sync(
                clip=clip_obj,
                destination_id=destination_id,
                session=session,
                force=force,
            )

    return await asyncio.to_thread(_run_sync)


async def get_destination_preview_info(
    clip_id: str,
    destination_id: str,
) -> dict:
    """Async wrapper for non-mutating preview metadata retrieval."""
    import asyncio
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip as ClipModel

    def _run_sync() -> dict:
        with SyncSessionLocal() as session:
            clip_obj = session.query(ClipModel).filter(ClipModel.id == clip_id).first()
            if not clip_obj:
                raise OutroRenderError(f"Clip '{clip_id}' not found.")
            return get_destination_preview_info_sync(
                clip=clip_obj,
                destination_id=destination_id,
                session=session,
            )

    return await asyncio.to_thread(_run_sync)
