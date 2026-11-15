"""
gaming_test_fixtures.py
=======================
Reusable test fixtures, synthetic media generators, opaque-box ffprobe inspectors,
and mock database/Celery task helpers for ClipForge Dual-Region Gaming Layout tests.

Designed for opaque-box requirement verification across Tiers 1-4.
Strictly adheres to:
- MASTER_ENGINEERING_RULEBOOK.md
- R5 Zero-Caption Invariant (zero subtitle streams, zero caption files, zero drawtext filters)
- Faststart MP4 atom verification (moov atom precedes mdat atom)
- YUV420p even-pixel alignment
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock


# ==============================================================================
# 1. MP4 ATOM PARSING & FASTSTART VERIFICATION
# ==============================================================================

def parse_top_level_atoms(file_path: Path) -> List[str]:
    """
    Parses top-level ISO Base Media File Format (MP4) box/atom headers.
    Returns list of 4-character atom types in sequential order (e.g. ['ftyp', 'moov', 'mdat']).
    """
    atoms: List[str] = []
    with open(file_path, "rb") as f:
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            size = int.from_bytes(header[:4], "big")
            atom_type = header[4:8].decode("latin1", errors="replace")
            atoms.append(atom_type)
            if size == 1:  # 64-bit extended size
                ext_header = f.read(8)
                if len(ext_header) < 8:
                    break
                ext_size = int.from_bytes(ext_header, "big")
                f.seek(max(0, ext_size - 16), 1)
            elif size == 0:  # Box extends to end of file
                break
            else:
                f.seek(max(0, size - 8), 1)
    return atoms


def assert_faststart_moov_atom(file_path: Path) -> List[str]:
    """
    Asserts that the MP4 file has -movflags +faststart applied,
    meaning the 'moov' atom appears before the 'mdat' atom.
    """
    atoms = parse_top_level_atoms(file_path)
    assert "moov" in atoms, f"Missing 'moov' atom in MP4 file {file_path}. Found atoms: {atoms}"
    assert "mdat" in atoms, f"Missing 'mdat' atom in MP4 file {file_path}. Found atoms: {atoms}"
    moov_idx = atoms.index("moov")
    mdat_idx = atoms.index("mdat")
    assert moov_idx < mdat_idx, (
        f"Faststart violation in {file_path}: 'moov' atom (index {moov_idx}) "
        f"must precede 'mdat' atom (index {mdat_idx}). Top-level atoms: {atoms}"
    )
    return atoms


# ==============================================================================
# 2. DETERMINISTIC SYNTHETIC VIDEO GENERATORS (FFMPEG LAVFI)
# ==============================================================================

def generate_synthetic_video(
    output_path: Path,
    width: int,
    height: int,
    duration: float = 3.0,
    fps: int = 30,
    video_color: str = "black",
    boxes: Optional[List[Dict[str, Any]]] = None,
    audio_freq: Optional[int] = 440,
    pix_fmt: str = "yuv420p",
    faststart: bool = True,
) -> Path:
    """
    Generates a deterministic synthetic MP4 video file using FFmpeg lavfi sources.
    Requires no external downloads and completes in sub-second time.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Base video filter source
    vf_parts = [f"testsrc=size={width}x{height}:rate={fps}:duration={duration}"]
    if video_color != "testsrc":
        vf_parts = [f"color=c={video_color}:s={width}x{height}:d={duration}"]

    if boxes:
        for b in boxes:
            bx = b.get("x", 0)
            by = b.get("y", 0)
            bw = b.get("w", 100)
            bh = b.get("h", 100)
            color = b.get("color", "blue")
            vf_parts.append(f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:c={color}:t=fill")

    vf_chain = ",".join(vf_parts)

    # For odd dimensions, libx264 yuv420p fails because chroma subsampling requires
    # dimensions divisible by 2. Use yuv444p for odd dimension synthetic sources.
    effective_pix_fmt = pix_fmt
    if (width % 2 != 0 or height % 2 != 0) and pix_fmt == "yuv420p":
        effective_pix_fmt = "yuv444p"

    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", vf_chain]

    if audio_freq is not None:
        cmd.extend(["-f", "lavfi", "-i", f"sine=frequency={audio_freq}:duration={duration}"])
        cmd.extend(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k"])
    else:
        cmd.extend(["-map", "0:v"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-threads", "2",
        "-pix_fmt", effective_pix_fmt,
    ])

    if faststart:
        cmd.extend(["-movflags", "+faststart"])

    cmd.append(str(output_path))

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic video generation failed ({proc.returncode}):\n{proc.stderr}")

    assert output_path.exists(), f"Output synthetic video not found at {output_path}"
    assert output_path.stat().st_size > 0, f"Output synthetic video is empty at {output_path}"
    return output_path


def create_synthetic_1080p_gameplay(
    output_path: Path,
    duration: float = 5.0,
    fps: int = 30,
) -> Path:
    """
    Recipe 1: Standard 1080p Horizontal Gameplay (1920x1080, 5s, 30fps).
    Features blue gameplay main zone and green facecam corner zone with 440Hz sine audio.
    """
    boxes = [
        {"x": 192, "y": 108, "w": 1536, "h": 864, "color": "blue"},
        {"x": 1344, "y": 54, "w": 480, "h": 270, "color": "green"},
    ]
    return generate_synthetic_video(
        output_path=output_path,
        width=1920,
        height=1080,
        duration=duration,
        fps=fps,
        boxes=boxes,
        audio_freq=440,
        faststart=True,
    )


def create_synthetic_4k_ultrawide(
    output_path: Path,
    duration: float = 3.0,
    fps: int = 30,
) -> Path:
    """
    Recipe 2: 4K Ultrawide 21:9 Gameplay (3840x1600, 3s, 30fps).
    Features red action viewport and yellow webcam zone with 880Hz sine audio.
    """
    boxes = [
        {"x": 384, "y": 160, "w": 3072, "h": 1280, "color": "red"},
        {"x": 192, "y": 80, "w": 576, "h": 480, "color": "yellow"},
    ]
    return generate_synthetic_video(
        output_path=output_path,
        width=3840,
        height=1600,
        duration=duration,
        fps=fps,
        boxes=boxes,
        audio_freq=880,
        faststart=True,
    )


def create_synthetic_odd_dimension(
    output_path: Path,
    duration: float = 2.0,
    fps: int = 30,
    width: int = 1919,
    height: int = 1079,
) -> Path:
    """
    Recipe 3: Odd-Dimension Gameplay (default 1919x1079, 2s, 30fps).
    Verifies codec alignment truncates odd pixels safely without failure.
    """
    return generate_synthetic_video(
        output_path=output_path,
        width=width,
        height=height,
        duration=duration,
        fps=fps,
        boxes=[{"x": 100, "y": 100, "w": 800, "h": 600, "color": "magenta"}],
        audio_freq=440,
        faststart=True,
    )


def create_synthetic_portrait(
    output_path: Path,
    duration: float = 3.0,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """
    Recipe 4: Portrait 9:16 Video (1080x1920, 3s, 30fps).
    Verifies behavior when source is already in 9:16 vertical orientation.
    """
    return generate_synthetic_video(
        output_path=output_path,
        width=width,
        height=height,
        duration=duration,
        fps=fps,
        boxes=[{"x": 100, "y": 200, "w": 880, "h": 1200, "color": "cyan"}],
        audio_freq=440,
        faststart=True,
    )


# ==============================================================================
# 3. OPAQUE-BOX INSPECTION FUNCTIONS (FFPROBE)
# ==============================================================================

def probe_media(file_path: Path) -> Dict[str, Any]:
    """
    Runs ffprobe in JSON format on target media file.
    Returns parsed dictionary containing 'streams' and 'format'.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Media file does not exist: {file_path}")

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,duration,channels,sample_rate",
        "-show_entries", "format=format_name,duration,size,bit_rate",
        "-of", "json",
        str(file_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed ({proc.returncode}) on {file_path}:\n{proc.stderr}")

    return json.loads(proc.stdout)


def assert_zero_caption_invariant(
    media_path: Path,
    check_directory: bool = True,
    directory_path: Optional[Path] = None,
) -> None:
    """
    Strict R5 Zero-Caption Mandate Verification:
    1. Runs ffprobe and asserts 0 streams have codec_type == 'subtitle'.
    2. Scans the media's directory (or directory_path) and asserts 0 subtitle files exist
       (*.srt, *.vtt, *.ass, *.sub, *.dfxp, *.ttml).
    """
    media_path = Path(media_path)
    probe_data = probe_media(media_path)
    streams = probe_data.get("streams", [])

    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    assert len(subtitle_streams) == 0, (
        f"R5 Violation: Rendered output {media_path} contains {len(subtitle_streams)} "
        f"subtitle stream(s): {subtitle_streams}"
    )

    if check_directory:
        scan_dir = directory_path or media_path.parent
        if scan_dir.exists():
            caption_extensions = {".srt", ".vtt", ".ass", ".sub", ".dfxp", ".ttml"}
            found_caption_files = [
                p for p in scan_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in caption_extensions
            ]
            assert len(found_caption_files) == 0, (
                f"R5 Violation: Found caption/subtitle artifact files in {scan_dir}: {found_caption_files}"
            )


def assert_filtergraph_zero_caption_invariant(filtergraph: str) -> None:
    """
    Verifies that an FFmpeg complex filtergraph string does not contain
    any caption burning filters (subtitles=, ass=, drawtext=).
    """
    forbidden_filters = ["subtitles=", "ass=", "drawtext="]
    for ff in forbidden_filters:
        assert ff not in filtergraph.lower(), (
            f"R5 Violation: Filtergraph contains prohibited caption filter '{ff}':\n{filtergraph}"
        )


def assert_gaming_video_invariants(
    file_path: Path,
    expected_width: int = 1080,
    expected_height: int = 1920,
    expected_video_codec: str = "h264",
    expected_pix_fmt: str = "yuv420p",
    expected_audio_codec: Optional[str] = "aac",
    expected_duration: Optional[float] = None,
    duration_tolerance: float = 0.25,
    check_faststart: bool = True,
    check_zero_captions: bool = True,
) -> Dict[str, Any]:
    """
    Comprehensive opaque-box verification for rendered gaming output MP4:
    - 9:16 vertical resolution (1080x1920)
    - Codec parity (h264, yuv420p, aac)
    - Even-pixel boundaries
    - Moov atom faststart
    - Strict R5 zero captions
    """
    file_path = Path(file_path)
    assert file_path.exists(), f"File does not exist: {file_path}"
    assert file_path.stat().st_size > 0, f"File is empty: {file_path}"

    probe_data = probe_media(file_path)
    streams = probe_data.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    assert len(video_streams) == 1, f"Expected exactly 1 video stream, found {len(video_streams)}"
    v = video_streams[0]

    # Geometry & Codec checks
    assert v.get("width") == expected_width, (
        f"Width mismatch: expected {expected_width}, got {v.get('width')}"
    )
    assert v.get("height") == expected_height, (
        f"Height mismatch: expected {expected_height}, got {v.get('height')}"
    )
    assert v.get("codec_name") == expected_video_codec, (
        f"Video codec mismatch: expected {expected_video_codec}, got {v.get('codec_name')}"
    )
    if expected_pix_fmt:
        assert v.get("pix_fmt") == expected_pix_fmt, (
            f"Pixel format mismatch: expected {expected_pix_fmt}, got {v.get('pix_fmt')}"
        )

    # Even-pixel checks
    assert v.get("width") % 2 == 0, f"Width {v.get('width')} must be even"
    assert v.get("height") % 2 == 0, f"Height {v.get('height')} must be even"

    # Audio checks
    if expected_audio_codec:
        assert len(audio_streams) >= 1, "Expected at least 1 audio stream, found 0"
        a = audio_streams[0]
        assert a.get("codec_name") == expected_audio_codec, (
            f"Audio codec mismatch: expected {expected_audio_codec}, got {a.get('codec_name')}"
        )

    # Duration check if requested
    if expected_duration is not None:
        fmt = probe_data.get("format", {})
        actual_dur = float(fmt.get("duration", 0.0))
        assert abs(actual_dur - expected_duration) <= duration_tolerance, (
            f"Duration mismatch: expected {expected_duration}s ±{duration_tolerance}s, got {actual_dur}s"
        )

    # Faststart check
    if check_faststart:
        assert_faststart_moov_atom(file_path)

    # R5 Zero-caption check
    if check_zero_captions:
        assert_zero_caption_invariant(file_path, check_directory=True)

    return {
        "width": v.get("width"),
        "height": v.get("height"),
        "video_codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
        "format": probe_data.get("format", {}),
    }


# ==============================================================================
# 4. MOCK DATABASE AND CELERY EXECUTION HELPERS
# ==============================================================================

class MockJob:
    """Lightweight stand-in for backend.models.models.Job."""
    def __init__(
        self,
        job_id: str = "job-gaming-001",
        status: str = "PENDING",
        config: Optional[str] = None,
        video_id: Optional[str] = "vid-123",
        source_url: Optional[str] = "https://youtube.com/watch?v=dQw4w9WgXcQ",
        source_title: Optional[str] = "Gameplay Session",
        progress: int = 0,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.id = job_id
        self.status = status
        self.config = config or json.dumps({
            "mode": "gaming",
            "gaming_layout": {
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
                "facecam_placement": "top-right",
                "facecam_output_rect": {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.22},
            }
        })
        self.video_id = video_id
        self.source_url = source_url
        self.source_title = source_title
        self.progress = progress
        self.current_step = current_step
        self.error_message = error_message


class MockAsyncSession:
    """
    Mock SQLAlchemy AsyncSession for testing API intake and persistence
    without touching a physical database file.
    """
    def __init__(self, initial_jobs: Optional[List[Any]] = None):
        self.jobs: Dict[str, Any] = {}
        if initial_jobs:
            for j in initial_jobs:
                self.jobs[j.id] = j
        self.added_objects: List[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, instance: Any) -> None:
        self.added_objects.append(instance)
        if hasattr(instance, "id") and instance.id:
            self.jobs[instance.id] = instance

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, instance: Any) -> None:
        pass

    async def execute(self, statement: Any) -> MagicMock:
        mock_result = MagicMock()
        # Default behavior: scalar_one_or_none returns matching job or first added
        if self.added_objects:
            mock_result.scalar_one_or_none.return_value = self.added_objects[-1]
            mock_result.scalars.return_value.all.return_value = list(self.jobs.values())
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
        return mock_result


def create_mock_db_session(initial_jobs: Optional[List[Any]] = None) -> MockAsyncSession:
    """Factory creating an in-memory MockAsyncSession."""
    return MockAsyncSession(initial_jobs=initial_jobs)


class MockCeleryAsyncResult:
    """Mock representing Celery's AsyncResult return object."""
    def __init__(self, task_id: str = "celery-task-gaming-001", state: str = "PENDING"):
        self.id = task_id
        self.state = state
        self.status = state
        self.result = None

    def ready(self) -> bool:
        return self.state in {"SUCCESS", "FAILURE"}

    def successful(self) -> bool:
        return self.state == "SUCCESS"

    def get(self, timeout: Optional[float] = None) -> Any:
        return self.result


def create_mock_celery_task(task_id: str = "celery-task-gaming-001") -> MagicMock:
    """Creates a mock Celery task object for mocking apply_async."""
    mock_task = MagicMock()
    mock_task.id = task_id
    mock_task.apply_async.return_value = MockCeleryAsyncResult(task_id=task_id)
    return mock_task
