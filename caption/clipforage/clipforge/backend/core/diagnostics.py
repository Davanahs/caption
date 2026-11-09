import shutil
import subprocess
import os
import urllib.request
from backend.core.config import settings

def run_diagnostics() -> dict:
    """Check startup requirements, binaries, and API configurations."""
    results = {
        "ffmpeg": False,
        "ffprobe": False,
        "yt-dlp": False,
        "cloud_apis": {},
        "issues": [],
    }

    # 1. Check binaries
    for binary in ["ffmpeg", "ffprobe", "yt-dlp"]:
        if shutil.which(binary):
            try:
                # Run with basic version check
                cmd = [binary, "--version" if binary == "yt-dlp" else "-version"]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                results[binary] = True
            except Exception:
                # Fallback: if shutil.which finds it, consider it found
                results[binary] = True
        else:
            results["issues"].append(f"Missing external binary: '{binary}'. Please install it and add to PATH.")

    # 2. Check Cloud AI API keys
    has_cloud_api = bool(settings.OPENROUTER_API_KEY or settings.NVIDIA_API_KEY or settings.GROQ_API_KEY)
    if not has_cloud_api:
        results["issues"].append(
            "No Cloud AI API keys configured (OPENROUTER_API_KEY, GROQ_API_KEY, or NVIDIA_API_KEY). Please configure API keys in Settings."
        )

    # 3. Check Cloud API Key configuration status
    for api_name, api_key in [
        ("GROQ_API_KEY", settings.GROQ_API_KEY), 
        ("OPENROUTER_API_KEY", settings.OPENROUTER_API_KEY), 
        ("NVIDIA_API_KEY", settings.NVIDIA_API_KEY)
    ]:
        results["cloud_apis"][api_name] = "Configured" if api_key else "Not Configured"

    # 4. Check directory write permissions
    for directory in [settings.UPLOAD_DIR, settings.OUTPUT_DIR]:
        if not os.access(directory, os.W_OK):
            results["issues"].append(f"Directory is not writable: '{directory}'")

    return results
