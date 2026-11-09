"""
equal_splitter.py
=================
Generates equally-sized clip segments from a video.

Splits total video duration into N equal parts using ffprobe to measure
duration, then returns clip boundary tuples. The actual cutting is handled
by the same existing cut_clip / reframe pipeline used by AI clips.
"""

import asyncio
import logging
import subprocess
import json
from pathlib import Path

logger = logging.getLogger("clipforge.equal_splitter")


def get_video_duration(video_path: Path) -> float:
    """Use ffprobe to get the exact video duration in seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception as exc:
        logger.error(f"[EqualSplitter] ffprobe failed: {exc}")
        # Fallback: try streams
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", str(video_path)],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and stream.get("duration"):
                    return float(stream["duration"])
        except Exception:
            pass
        return 0.0


def generate_equal_split_segments(
    video_path: Path,
    clip_count: int,
    max_clip_duration: int | None = None,
) -> list[dict]:
    """
    Compute equal-split clip boundaries for a video.

    Args:
        video_path: Path to the source video file.
        clip_count: Number of equal clips to generate.
        max_clip_duration: Maximum allowed clip duration in seconds (defaults to settings.MAX_CLIP_DURATION).

    Returns:
        List of dicts with segment properties.
    """
    if clip_count <= 0:
        raise ValueError("clip_count must be >= 1")

    total_duration = get_video_duration(video_path)
    if total_duration <= 0:
        raise RuntimeError(
            f"Could not determine duration for video: {video_path}. "
            "Ensure the file is valid and ffprobe is installed."
        )

    logger.info(
        f"[EqualSplitter] Video duration: {total_duration:.2f}s, "
        f"splitting into {clip_count} equal clip(s)."
    )

    # Max allowed clip duration (user setting or default 49s)
    default_max = getattr(settings, 'MAX_CLIP_DURATION', 49)
    max_allowed = max_clip_duration if (max_clip_duration and max_clip_duration > 0) else default_max
    if max_allowed > 60:
        max_allowed = 60  # Absolute cap for Shorts format

    raw_segment_duration = total_duration / clip_count
    # Cap segment duration so no clip exceeds max_allowed (49 seconds)
    segment_duration = min(raw_segment_duration, float(max_allowed))
    
    # Re-calculate clip count if raw duration exceeded limit
    actual_clips_to_generate = clip_count
    if raw_segment_duration > max_allowed:
        import math
        actual_clips_to_generate = math.ceil(total_duration / segment_duration)
        logger.info(
            f"[EqualSplitter] Adjusted clip count from {clip_count} to {actual_clips_to_generate} "
            f"to enforce YouTube Shorts max limit of {segment_duration}s per clip."
        )

    segments = []
    for i in range(actual_clips_to_generate):
        start = i * segment_duration
        if start >= total_duration:
            break
        end = min((i + 1) * segment_duration, total_duration)
        actual_duration = end - start
        if actual_duration < 5.0 and i > 0:
            # Skip tiny trailing fragment under 5s
            break
            
        minutes = int(start // 60)
        seconds = int(start % 60)
        title = f"Segment {i + 1} ({minutes:02d}:{seconds:02d})"

        segments.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(actual_duration, 3),
            "title": title,
            "text": "",       # transcript segment populated later by transcriber
            "score": 5.0,     # neutral score — equal split clips have no AI scoring
            "description": "",
            "hashtags": "",
            "pinned_comment": "",
        })
        logger.info(
            f"[EqualSplitter]  Segment {i+1}/{actual_clips_to_generate}: "
            f"{start:.2f}s → {end:.2f}s ({actual_duration:.2f}s)"
        )

    return segments
