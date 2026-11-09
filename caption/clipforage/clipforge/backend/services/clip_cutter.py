"""
Clip Cutter - FFmpeg-based video cutting and utility functions.
"""
import asyncio
import json
import os
import textwrap
import sys
from pathlib import Path
from backend.core.config import settings

async def run_ffmpeg(args: list[str]) -> tuple[int, str, str]:
    cmd = ["ffmpeg", "-y"] + args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()

async def get_video_dimensions(video_path: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(video_path)
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    data = json.loads(stdout.decode())
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream["width"], stream["height"]
    return 1920, 1080

async def cut_clip(input_path: str, output_path: str, start: float, end: float) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start
    code, _, err = await run_ffmpeg([
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        "-c", "copy",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(output_path)
    ])
    if code != 0:
        raise RuntimeError(f"FFmpeg cut failed: {err}")
    return output_path

async def burn_hook_title(input_path: Path, output_path: Path, title: str) -> Path:
    import shutil
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # User Baseline Request: Disable Hook title rendering
    shutil.copy(str(input_path), str(output_path))
    return output_path

    # Old logic preserved below but skipped
    possible_fonts = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    font_path = ""
    for f in possible_fonts:
        if Path(f).exists():
            font_path = f.replace(":", "\\\\:") if sys.platform == "win32" else f
            break
    
    if not font_path:
        font_path = "Arial" # Fallback hoping fontconfig works
        
    text = textwrap.shorten(title, width=50, placeholder="...")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\u2019") # Use smart quote to avoid FFmpeg parser issues
    vf = f"drawtext=fontfile='{font_path}':text='{text}':fontcolor=white:fontsize=72:box=1:boxcolor=black@0.5:boxborderw=10:x=(w-text_w)/2:y=(h-text_h)/4"
    code, _, err = await run_ffmpeg([
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-preset", "fast",
        "-crf", "18",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(output_path)
    ])
    if code != 0:
        raise RuntimeError(f"FFmpeg burn hook failed: {err}")
    return output_path

def _find_default_template() -> Path | None:
    candidates = [
        settings.BASE_DIR / "Gemini_Generated_Image_2rh1j72rh1j72rh1.png",
        settings.BASE_DIR.parent / "Gemini_Generated_Image_2rh1j72rh1j72rh1.png",
        Path("Gemini_Generated_Image_2rh1j72rh1j72rh1.png"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

async def extract_thumbnail(video_path: Path, output_path: Path, time: float = 1.0) -> Path:
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    code, _, err = await run_ffmpeg([
        "-ss", str(time),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        "-f", "mjpeg",
        str(output_path)
    ])
    if code != 0:
        raise RuntimeError(f"Thumbnail extraction failed: {err}")
    return output_path

async def swap_clip_audio(video_path: Path, clean_audio_path: Path, output_path: Path) -> Path:
    video_path = Path(video_path)
    clean_audio_path = Path(clean_audio_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    code, _, err = await run_ffmpeg([
        "-i", str(video_path),
        "-i", str(clean_audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(output_path)
    ])
    if code != 0:
        raise RuntimeError(f"FFmpeg audio swap failed: {err}")
    return output_path
