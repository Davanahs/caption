import subprocess
import tempfile
import httpx
import os
import threading
from pathlib import Path
from backend.core.config import settings

_model = None


def load_model():
    """Load Whisper model once (cached in memory)."""
    global _model
    if _model is None:
        import whisper
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[Whisper] Loading local '{settings.WHISPER_MODEL}' model on {device}...")
        _model = whisper.load_model(settings.WHISPER_MODEL, device=device)
        print("[Whisper] Local model loaded.")
    return _model


def transcribe_via_groq(video_path: Path) -> dict:
    video_path = Path(video_path)
    """Extract audio and send to Groq API."""
    print(f"[Groq] Transcribing via Groq API...")

    # 1. Extract audio file (mono, 16kHz mp3) or use directly if it is one
    import shutil
    temp_dir = tempfile.gettempdir()
    audio_path = Path(temp_dir) / f"{video_path.stem}_audio.mp3"

    try:
        # Check if already small enough mp3
        is_mp3 = video_path.suffix.lower() == ".mp3"
        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        
        if is_mp3 and file_size_mb <= 24.5:
            print(f"[Groq] Input is already MP3 ({file_size_mb:.1f} MB), skipping extraction.")
            shutil.copy(video_path, audio_path)
        else:
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "libmp3lame", "-ac", "1", "-ar", "16000",
                "-q:a", "5",       # variable bitrate ~130kbps — smaller file
                str(audio_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            print(f"[Groq] Extracted audio file size: {file_size_mb:.1f} MB")
            
        # Groq hard limit is 25 MB
        if file_size_mb > 24.5:
            raise ValueError(
                f"Audio file too large for Groq ({file_size_mb:.1f} MB > 24.5 MB limit). "
                "Falling back to local Whisper."
            )

        # 2. Send to Groq Whisper endpoint
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/mpeg")}
            data = {
                "model": settings.GROQ_MODEL,
                "response_format": "verbose_json",
                "language": "en",
            }

            with httpx.Client(timeout=180.0) as client:
                response = client.post(url, headers=headers, files=files, data=data)

                if not response.is_success:
                    # Log the actual Groq error body so we can debug it
                    try:
                        err_body = response.json()
                    except Exception:
                        err_body = response.text
                    print(f"[Groq] API error {response.status_code}: {err_body}")
                    response.raise_for_status()

                result = response.json()

        return {
            "text": result.get("text", "").strip(),
            "segments": [
                {
                    "id": seg.get("id", idx),
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip(),
                    "words": seg.get("words", []),
                }
                for idx, seg in enumerate(result.get("segments", []))
            ],
        }
    finally:
        if audio_path.exists():
            try:
                os.remove(audio_path)
            except Exception:
                pass


def transcribe_video(video_path: Path, update_fn=None, is_test: bool = False) -> dict:
    video_path = Path(video_path)
    """
    Transcribe video and return full result with timestamps.
    Automatically uses Groq API if GROQ_API_KEY is defined, else falls back to local Whisper.

    update_fn: optional callable(progress: int, step: str) for live DB progress updates.
    
    Canned synthetic transcript is strictly isolated:
    Only returned when is_test is True (verified from trusted backend state)
    AND the file matches an explicit synthetic test fixture.
    Ordinary jobs (is_test=False) always execute real audio transcription (Groq / Whisper).
    """
    is_fixture_file = (
        "synthetic_test_fixture" in video_path.name.lower()
        or video_path.name.lower().startswith("synth_")
        or "test_fixture" in video_path.name.lower()
    )
    if is_test and is_fixture_file:
        if update_fn:
            update_fn(35, "Transcribing audio...")
        return {
            "text": "This is a synthetic test transcript for testing the full end to end processing lifecycle of ClipForge.",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 9.5,
                    "text": "This is a synthetic test transcript for testing the full end to end processing lifecycle",
                    "words": []
                },
                {
                    "id": 1,
                    "start": 9.5,
                    "end": 19.5,
                    "text": "of ClipForge and verifying the pipeline with the configured Celery worker.",
                    "words": []
                }
            ]
        }

    if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip():
        try:
            return transcribe_via_groq(video_path)
        except ValueError as e:
            print(f"[Whisper] Groq transcription fallback (Size Limit): {e}. Falling back to local Whisper...")
        except Exception as e:
            print(f"[Whisper] Groq transcription failed ({type(e).__name__}: {e}). Falling back to local Whisper...")

    # ── Local Whisper fallback ────────────────────────────────────────────────
    # Get audio duration to estimate progress
    duration_sec = 0.0
    try:
        import json as _json
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
            capture_output=True, text=True
        )
        duration_sec = float(_json.loads(probe.stdout).get("format", {}).get("duration", 0))
    except Exception:
        pass

    # Background heartbeat: estimates progress 25→48% over expected transcription time
    _stop_heartbeat = threading.Event()

    def _heartbeat():
        import time
        elapsed = 0
        # Rough rule of thumb: local base Whisper ≈ 4× real-time on CPU
        estimated_total = max((duration_sec * 4), 30)  # at least 30s
        while not _stop_heartbeat.wait(8):
            elapsed += 8
            pct = min(25 + int((elapsed / estimated_total) * 23), 48)
            if update_fn:
                update_fn(pct, f"Transcribing audio... (local Whisper, ~{int(estimated_total - elapsed)}s left)")

    heartbeat = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat.start()

    try:
        model = load_model()
        result = model.transcribe(
            str(video_path),
            word_timestamps=True,
            verbose=False,
            language="en",
            task="transcribe",
            fp16=False,
        )
    finally:
        _stop_heartbeat.set()
        heartbeat.join(timeout=2)

    return {
        "text": result["text"].strip(),
        "segments": [
            {
                "id": seg["id"],
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
                "words": seg.get("words", []),
            }
            for seg in result["segments"]
        ],
    }


def get_transcript_text(segments: list[dict]) -> str:
    """Join all segments into plain text."""
    return " ".join(seg["text"] for seg in segments)


def get_segments_in_range(segments: list[dict], start: float, end: float) -> list[dict]:
    """Get transcript segments that fall within a time range."""
    return [
        seg for seg in segments
        if seg["start"] >= start and seg["end"] <= end
    ]
