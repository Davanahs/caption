"""
tests/e2e/e2e_media_helpers.py
==============================
Deterministic media generation and verification helpers for ClipForge E2E tests:
1. generate_synthetic_mp4: Sub-second FFmpeg video generation with audio.
2. generate_synthetic_image: PNG/JPEG image generation with configurable dimensions.
3. parse_top_level_atoms & assert_faststart_moov_atom: MP4 box header parsing.
4. assert_zero_caption_invariant: Verification of zero subtitle streams and zero caption files.
5. assert_filtergraph_zero_caption_invariant: Strict check against caption filters in FFmpeg graphs.
6. probe_media: JSON media inspection via ffprobe.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_binary(binary_name: str) -> str:
    """Locate binary on PATH or fall back to name."""
    found = shutil.which(binary_name)
    if found:
        return found
    for candidate in [
        f"/usr/bin/{binary_name}",
        f"/usr/local/bin/{binary_name}",
        rf"C:\ffmpeg\bin\{binary_name}.exe",
    ]:
        if os.path.exists(candidate):
            return candidate
    return binary_name


FFMPEG_BIN = _resolve_binary("ffmpeg")
FFPROBE_BIN = _resolve_binary("ffprobe")


def generate_synthetic_mp4(
    output_path: Path | str,
    width: int = 1080,
    height: int = 1920,
    duration: float = 3.0,
    fps: int = 30,
    color: str = "blue",
    audio_freq: int = 440,
    faststart: bool = True,
    has_audio: bool = True,
    audio_sample_rate: int = 44100,
    audio_channels: int = 2,
    pix_fmt: str = "yuv420p",
    preset: str = "ultrafast",
) -> Path:
    """
    Generates an authentic MP4 with video and optional audio streams in sub-second time
    using FFmpeg lavfi filters. Strict zero-captions (-sn) and optional faststart.
    """
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
    ]

    if has_audio:
        channel_layout = "stereo" if audio_channels == 2 else "mono"
        cmd.extend([
            "-f", "lavfi",
            "-i", f"sine=frequency={audio_freq}:sample_rate={audio_sample_rate}:duration={duration}",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", str(audio_sample_rate),
            "-ac", str(audio_channels),
        ])
    else:
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", preset,
        "-pix_fmt", pix_fmt,
        "-sn",  # Strict invariant: Zero captions / subtitles
    ])

    if faststart:
        cmd.extend(["-movflags", "+faststart"])

    cmd.append(str(out_p))

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic MP4 failed ({proc.returncode}):\n{proc.stderr}")

    return out_p


def generate_synthetic_image(
    output_path: Path | str,
    width: int = 1080,
    height: int = 1920,
    color: str = "red",
    fmt: str = "png",
) -> Path:
    """
    Generates a static PNG or JPEG outro image via FFmpeg lavfi.
    """
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d=0.1",
        "-vframes", "1",
        str(out_p),
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic image failed ({proc.returncode}):\n{proc.stderr}")

    return out_p


def parse_top_level_atoms(file_path: Path | str) -> List[str]:
    """
    Parses top-level MP4 ISO base media box headers to verify atom ordering.
    """
    p = Path(file_path)
    atoms: List[str] = []
    with open(p, "rb") as f:
        file_size = p.stat().st_size
        while f.tell() < file_size:
            header = f.read(8)
            if len(header) < 8:
                break
            size = int.from_bytes(header[:4], "big")
            atom_type = header[4:8].decode("latin1", errors="replace")
            atoms.append(atom_type)

            if size == 1:
                # 64-bit extended size
                ext_header = f.read(8)
                if len(ext_header) < 8:
                    break
                ext_size = int.from_bytes(ext_header, "big")
                if ext_size < 16:
                    break
                f.seek(ext_size - 16, os.SEEK_CUR)
            elif size == 0:
                # Atom extends to EOF
                break
            elif size >= 8:
                f.seek(size - 8, os.SEEK_CUR)
            else:
                break
    return atoms


def assert_faststart_moov_atom(file_path: Path | str) -> None:
    """
    Asserts that the moov atom occurs before the mdat atom in the output MP4
    satisfying the project's +faststart streaming requirement.
    """
    p = Path(file_path)
    atoms = parse_top_level_atoms(p)
    assert "moov" in atoms, f"Missing 'moov' atom in {p}. Found atoms: {atoms}"
    assert "mdat" in atoms, f"Missing 'mdat' atom in {p}. Found atoms: {atoms}"
    moov_idx = atoms.index("moov")
    mdat_idx = atoms.index("mdat")
    assert moov_idx < mdat_idx, (
        f"Faststart violation in {p}: 'moov' (index {moov_idx}) must precede 'mdat' (index {mdat_idx}). "
        f"Top-level atoms: {atoms}"
    )


def probe_media(file_path: Path | str) -> Dict[str, Any]:
    """
    Runs ffprobe in JSON format on the media file to inspect streams and format.
    """
    p = Path(file_path)
    cmd = [
        FFPROBE_BIN, "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,width,height,duration,channels,sample_rate",
        "-show_entries", "format=duration,size,format_name",
        "-of", "json",
        str(p),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed ({proc.returncode}):\n{proc.stderr}")
    return json.loads(proc.stdout)


def assert_zero_caption_invariant(media_path: Path | str) -> None:
    """
    Strict verification of zero subtitle streams in the media file and zero
    subtitle/caption files in the parent directory.
    """
    p = Path(media_path)
    probe = probe_media(p)
    subs = [s for s in probe.get("streams", []) if s.get("codec_type") == "subtitle"]
    assert len(subs) == 0, f"Prohibited subtitle stream detected in {p}: {subs}"

    caption_exts = {".srt", ".vtt", ".ass", ".sub", ".dfxp", ".ttml"}
    if p.parent.exists():
        dir_files = [f for f in p.parent.glob("*") if f.suffix.lower() in caption_exts]
        assert len(dir_files) == 0, f"Prohibited caption files found in {p.parent}: {dir_files}"


def assert_filtergraph_zero_caption_invariant(filtergraph: str) -> None:
    """
    Asserts that an FFmpeg filtergraph string contains zero subtitle or burned-in caption filters.
    """
    forbidden_tokens = ["subtitles=", "ass=", "drawtext="]
    for token in forbidden_tokens:
        assert token not in filtergraph, (
            f"Prohibited filter token '{token}' detected in FFmpeg filtergraph: {filtergraph}"
        )
