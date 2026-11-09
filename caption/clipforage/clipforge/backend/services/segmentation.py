"""
backend/services/segmentation.py
================================
Deterministic video segmentation strategies for ClipForge.
Supports fixed target duration splitting and equal division clip count splitting.
"""
import math
import logging

logger = logging.getLogger(__name__)

MAX_EQUAL_SPLIT_CLIPS = 120  # Informational reference limit


def generate_equal_splits(
    video_duration: float,
    num_clips: int | None = None,
    target_duration: float | None = None,
    max_clip_duration: float | None = None,
) -> list[dict]:
    """
    Compute deterministic equal-length split boundaries covering the entire source video.

    Semantics (Definitive Equal Splits Specification):
    1. Validation:
       - video_duration must be positive, non-zero, and finite (raises ValueError).
       - In Equal Splits mode (target_duration or max_clip_duration provided):
         * Duration limit Lmax is mandatory, must be numeric, strictly positive (> 0), and finite.
         * A missing, None, zero, negative, NaN, or infinite duration limit cleanly raises ValueError.
         * A missing duration must NEVER silently produce three clips or fall back to a default count.
         * A manually supplied num_clips is completely ignored when target duration is specified.
       - In manual division mode (when target duration is omitted and num_clips is explicitly supplied):
         * num_clips must be a positive integer (raises ValueError if <= 0 or non-integer).
         * Divides total video duration evenly into N = num_clips equal segments.
       - If NEITHER target_duration NOR num_clips is provided:
         * Cleanly raises ValueError: Missing maximum clip duration. No default fallback is permitted.

    2. Equal Splits Formula:
       - N = max(1, math.ceil(D / Lmax))
       - If D <= Lmax, N = 1 (one clip covering the entire source video).
       - The actual clip duration for every generated clip is:
           actual_clip_duration = D / N
         This guarantees that actual_clip_duration <= Lmax.
       - The complete source timeline is partitioned into exactly N contiguous, equal-duration intervals:
           start_i = i * (D / N)
           end_i = (i + 1) * (D / N)   [with end_(N-1) = D exactly]
           duration_i = end_i - start_i
       - Guarantees:
           start_0 == 0.0
           end_(N-1) == D
           end_i == start_(i+1) (zero gaps, zero overlaps)
           sum(duration_i) == D (100% full coverage, zero discarded footage)
           Every clip has identical duration D / N (no shortened remainder clip).

    Returns:
        List of candidate segment dicts with start, end, duration, score=1.0, title, etc.
    """
    if video_duration is None:
        raise ValueError("Video duration is required, got None")
    try:
        vid_dur = float(video_duration)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Video duration must be a numeric value, got {video_duration}") from exc

    if not math.isfinite(vid_dur) or vid_dur <= 0:
        raise ValueError(f"Video duration must be strictly positive and finite, got {video_duration}")

    # Resolve effective duration limit (Lmax)
    eff_target = target_duration if target_duration is not None else max_clip_duration

    if eff_target is not None:
        try:
            target_dur = float(eff_target)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Target duration must be a numeric value, got {eff_target}") from exc

        if not math.isfinite(target_dur) or target_dur <= 0:
            raise ValueError(f"Target/maximum clip duration must be strictly positive and finite, got {eff_target}")

        # Equal Splits mode:
        # N = ceil(D / Lmax)
        # If D <= Lmax, N = 1
        # Any supplied num_clips is strictly ignored in Equal Splits mode
        n = max(1, math.ceil(vid_dur / target_dur))
    elif num_clips is not None:
        # Manual clip count division mode (preserved for backwards compatibility with non-Equal-Splits callers)
        try:
            parsed_num = int(num_clips)
            if parsed_num <= 0:
                raise ValueError(f"num_clips must be a positive integer, got {num_clips}")
            n = parsed_num
        except (ValueError, TypeError) as exc:
            raise ValueError(f"num_clips must be a positive integer, got {num_clips}") from exc
    else:
        # Zero fallback rule: Missing maximum duration must NEVER silently produce 3 clips
        raise ValueError(
            "Maximum clip duration (target_duration) is mandatory for Equal Splits. "
            "A missing duration must never silently produce clips or fall back to a default count."
        )

    # Generate exactly N equal intervals covering [0, vid_dur]
    intervals = []
    for i in range(n):
        # Calculate boundaries from original duration and index to avoid cumulative rounding errors
        start = 0.0 if i == 0 else i * (vid_dur / n)
        end = vid_dur if i == n - 1 else (i + 1) * (vid_dur / n)
        dur = end - start
        intervals.append((start, end, dur))

    clips = []
    total = len(intervals)
    for i, (start, end, dur) in enumerate(intervals):
        if dur <= 0:
            continue
        clips.append({
            "start": start,
            "end": end,
            "duration": dur,
            "text": "",
            "score": 1.0,
            "title": f"Part {i + 1} of {total}",
            "description": f"Part {i + 1} of {total}",
            "hashtags": "#Shorts #ClipForge",
            "pinned_comment": f"Check out Part {i + 1} of {total}!",
        })

    return clips


def generate_equal_splits_by_duration(video_duration: float, max_clip_duration: float) -> list[dict]:
    """
    Dedicated Equal Splits interface: strictly requires maximum clip duration (Lmax)
    and computes N = ceil(D / Lmax).
    """
    if max_clip_duration is None:
        raise ValueError("max_clip_duration is mandatory for Equal Splits.")
    return generate_equal_splits(video_duration=video_duration, target_duration=max_clip_duration)


def generate_equal_divisions_by_count(video_duration: float, num_clips: int) -> list[dict]:
    """
    Dedicated manual division interface: divides video duration evenly into num_clips equal segments.
    """
    if num_clips is None:
        raise ValueError("num_clips is mandatory for manual clip count division.")
    return generate_equal_splits(video_duration=video_duration, num_clips=num_clips, target_duration=None)

