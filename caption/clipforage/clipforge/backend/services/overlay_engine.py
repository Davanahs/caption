import asyncio
from pathlib import Path
from backend.services.clip_cutter import run_ffmpeg

async def apply_watermark(
    video_path: Path,
    output_path: Path,
    watermark_url: str,
    position: str = "top_right",
    opacity: float = 0.8
) -> Path:
    """
    Overlays a channel watermark image onto the video.
    position can be: 'top_right', 'top_left', 'bottom_right', 'bottom_left'
    """
    import tempfile
    import urllib.request
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If watermark is a URL, download it temporarily
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        watermark_path = tmp.name
        
    try:
        if watermark_url.startswith("http"):
            urllib.request.urlretrieve(watermark_url, watermark_path)
        else:
            # Assume it's a local path
            watermark_path = watermark_url
            
        margin = 30
        if position == "top_right":
            overlay_expr = f"W-w-{margin}:{margin}"
        elif position == "top_left":
            overlay_expr = f"{margin}:{margin}"
        elif position == "bottom_right":
            overlay_expr = f"W-w-{margin}:H-h-{margin}"
        elif position == "bottom_left":
            overlay_expr = f"{margin}:H-h-{margin}"
        else:
            overlay_expr = f"W-w-{margin}:{margin}"

        # We scale watermark to 150px width, apply opacity, and overlay
        vf_complex = (
            f"[1:v]scale=150:-1,format=rgba,colorchannelmixer=aa={opacity}[wm];"
            f"[0:v][wm]overlay={overlay_expr}:shortest=1"
        )
        
        code, _, err = await run_ffmpeg([
            "-i", str(video_path),
            "-i", watermark_path,
            "-filter_complex", vf_complex,
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "18",
            "-movflags", "+faststart",
            str(output_path)
        ])
        
        if code != 0:
            raise RuntimeError(f"FFmpeg watermark failed: {err}")
            
    finally:
        if watermark_url.startswith("http") and Path(watermark_path).exists():
            try:
                Path(watermark_path).unlink()
            except Exception:
                pass
                
    return output_path
