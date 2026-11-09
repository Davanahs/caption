import subprocess
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class OutputValidatorError(Exception):
    pass

def validate_video_output(
    video_path: Path,
    expected_duration: float = None,
    require_audio: bool = False,
    expected_width: int = None,
    expected_height: int = None,
    max_duration: float = 60.0,
    duration_tolerance: float = 1.5
):
    """
    Validates that a video file is a valid media artifact.
    Enforces Shorts max_duration limit (default 60.0s ceiling for YouTube Shorts).
    Validates expected_duration within duration_tolerance if provided.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise OutputValidatorError(f"File does not exist: {video_path}")
        
    if video_path.stat().st_size == 0:
        raise OutputValidatorError(f"File is empty (0 bytes): {video_path}")
        
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of", "json", str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise OutputValidatorError(f"ffprobe failed. File may be corrupt: {result.stderr}")
        
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise OutputValidatorError(f"Failed to parse ffprobe output for {video_path}")
        
    format_info = data.get("format", {})
    streams = data.get("streams", [])
    
    if not streams:
        raise OutputValidatorError(f"No streams found in {video_path}")
        
    has_video = False
    has_audio = False
    
    for s in streams:
        if s.get("codec_type") == "video":
            has_video = True
            width = s.get("width")
            height = s.get("height")
            if not width or not height:
                raise OutputValidatorError(f"Video stream missing dimensions: {s}")
            if expected_width is not None and width != expected_width:
                raise OutputValidatorError(f"Width mismatch: expected {expected_width}, got {width}")
            if expected_height is not None and height != expected_height:
                raise OutputValidatorError(f"Height mismatch: expected {expected_height}, got {height}")
        elif s.get("codec_type") == "audio":
            has_audio = True
            
    if not has_video:
        raise OutputValidatorError(f"No video stream found in {video_path}")
        
    if require_audio and not has_audio:
        raise OutputValidatorError(f"Audio stream required but not found in {video_path}")
        
    actual_duration = float(format_info.get("duration", 0.0))
    if actual_duration <= 0.0:
        raise OutputValidatorError(f"Invalid duration {actual_duration} for {video_path}")

    if max_duration is not None and actual_duration > (max_duration + 0.1):
        raise OutputValidatorError(
            f"Duration {actual_duration}s exceeds maximum Shorts duration limit of {max_duration}s"
        )
        
    # If we expect a duration, check if it matches within duration_tolerance
    if expected_duration is not None:
        if abs(actual_duration - expected_duration) > duration_tolerance:
            raise OutputValidatorError(
                f"Duration mismatch: expected ~{expected_duration}s, got {actual_duration}s (tolerance: ±{duration_tolerance}s)"
            )
            
    logger.info(f"Output validation passed for {video_path} (Duration: {actual_duration}s)")
    return True
