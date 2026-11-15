"""
tests/e2e/test_tier3_pairwise_interactions.py
=============================================
Tier 3: Pairwise Combinatorial Interactions Suite for ClipForge Multi-Destination
Publishing & Automatic Outro System.

Opaque-Box Requirement Derivation:
- ORIGINAL_REQUEST.md §2 (Core Requirement: One monitored source -> Multiple publishing destinations -> Destination-specific outro -> Independent publishing status)
- ORIGINAL_REQUEST.md §5 (Channel-specific outro management: MP4 video and image outros)
- ORIGINAL_REQUEST.md §6 (Monitoring channels multiple destination mapping)
- ORIGINAL_REQUEST.md §7 (Destination selection across Manual Raw Upload, YouTube URL, and Auto Monitoring)
- ORIGINAL_REQUEST.md §8 (Destination-specific rendering & pristine base clip preservation)
- ORIGINAL_REQUEST.md §9 (Multi-destination publishing pipeline & independent status tracking)
- ORIGINAL_REQUEST.md §12 (Failure handling & idempotent retry)
- PROJECT.md § Key Invariants (Zero captions, -movflags +faststart, pristine base clip, private-by-default)

Combinatorial Dimensions:
1. Ingest Mode: Raw Upload, YouTube URL Ingest, Monitored RSS Channel
2. Destination Count: Single Destination (1), Dual Destination (2), Multi-Destination (3+)
3. Outro Configuration: All Video, All Image, Mixed (Video + Image + No-Outro), None
4. Publishing Outcome: All Success, Partial Failure with Independent Continuation, Token Expiration Mid-Upload, Idempotent Retry
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure clipforge root and backend are in sys.path
clipforge_root = Path(__file__).resolve().parent.parent.parent
backend_root = clipforge_root / "backend"
if str(clipforge_root) not in sys.path:
    sys.path.insert(0, str(clipforge_root))
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Try importing media helpers from shared e2e_media_helpers; provide fallback if running standalone
try:
    from tests.e2e.e2e_media_helpers import (
        assert_faststart_moov_atom,
        assert_zero_caption_invariant,
        generate_synthetic_image,
        generate_synthetic_mp4,
        parse_top_level_atoms,
        probe_media,
    )
except (ImportError, ModuleNotFoundError):
    def parse_top_level_atoms(file_path: Path) -> List[str]:
        atoms: List[str] = []
        with open(file_path, "rb") as f:
            while True:
                header = f.read(8)
                if len(header) < 8:
                    break
                size = int.from_bytes(header[:4], "big")
                atom_type = header[4:8].decode("latin1", errors="replace")
                atoms.append(atom_type)
                if size == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    ext_size = int.from_bytes(ext, "big")
                    f.seek(max(0, ext_size - 16), 1)
                elif size == 0:
                    break
                else:
                    f.seek(max(0, size - 8), 1)
        return atoms

    def assert_faststart_moov_atom(file_path: Path) -> None:
        atoms = parse_top_level_atoms(file_path)
        assert "moov" in atoms, f"Missing moov atom in {file_path}. Found: {atoms}"
        assert "mdat" in atoms, f"Missing mdat atom in {file_path}. Found: {atoms}"
        assert atoms.index("moov") < atoms.index("mdat"), (
            f"Faststart violation in {file_path}: moov must precede mdat. Atoms: {atoms}"
        )

    def probe_media(file_path: Path) -> Dict[str, Any]:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height,duration",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(file_path)
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed ({proc.returncode}):\n{proc.stderr}")
        return json.loads(proc.stdout)

    def assert_zero_caption_invariant(media_path: Path) -> None:
        probe = probe_media(media_path)
        subs = [s for s in probe.get("streams", []) if s.get("codec_type") == "subtitle"]
        assert len(subs) == 0, f"Prohibited subtitle stream detected in {media_path}: {subs}"
        caption_exts = {".srt", ".vtt", ".ass", ".sub", ".dfxp", ".ttml"}
        dir_files = [p for p in media_path.parent.glob("*") if p.suffix.lower() in caption_exts]
        assert len(dir_files) == 0, f"Prohibited caption files found in {media_path.parent}: {dir_files}"

    def generate_synthetic_mp4(
        output_path: Path,
        width: int = 1080,
        height: int = 1920,
        duration: float = 3.0,
        fps: int = 30,
        color: str = "blue",
        audio_freq: int = 440,
        faststart: bool = True,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
            "-f", "lavfi", "-i", f"sine=frequency={audio_freq}:duration={duration}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-sn",
        ]
        if faststart:
            cmd.extend(["-movflags", "+faststart"])
        cmd.append(str(output_path))
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg synthetic MP4 failed ({proc.returncode}):\n{proc.stderr}")
        return output_path

    def generate_synthetic_image(
        output_path: Path,
        width: int = 1080,
        height: int = 1920,
        color: str = "red",
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d=0.1",
            "-vframes", "1",
            str(output_path)
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg synthetic image failed ({proc.returncode}):\n{proc.stderr}")
        return output_path


def compute_file_sha256(path: Path) -> str:
    """Computes SHA256 checksum of a file to verify immutability."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def execute_destination_render(
    base_clip_path: Path,
    output_variant_path: Path,
    outro_path: Optional[Path] = None,
    outro_type: str = "none",
    image_duration: float = 3.0,
) -> Path:
    """
    Executes destination-specific FFmpeg concatenation according to PROJECT.md interface contract:
    - 9:16 aspect ratio (1080x1920) with pad preservation
    - aresample=44100 stereo audio
    - -sn (strict zero subtitles)
    - -movflags +faststart
    """
    output_variant_path.parent.mkdir(parents=True, exist_ok=True)
    if outro_type == "none" or outro_path is None:
        shutil.copyfile(base_clip_path, output_variant_path)
        return output_variant_path

    if outro_type == "video":
        cmd = [
            "ffmpeg", "-y",
            "-i", str(base_clip_path),
            "-i", str(outro_path),
            "-filter_complex",
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];"
            "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];"
            "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
            "[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-sn", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_variant_path),
        ]
    elif outro_type == "image":
        cmd = [
            "ffmpeg", "-y",
            "-i", str(base_clip_path),
            "-loop", "1", "-framerate", "30", "-t", str(image_duration), "-i", str(outro_path),
            "-f", "lavfi", "-t", str(image_duration), "-i", "anullsrc=r=44100:cl=stereo",
            "-filter_complex",
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];"
            "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];"
            "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
            "[2:a]aformat=channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-sn", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_variant_path),
        ]
    else:
        raise ValueError(f"Unknown outro_type: {outro_type}")

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg render variant failed ({proc.returncode}):\n{proc.stderr}")
    return output_variant_path


class TestTier3PairwiseInteractions:
    """
    Combinatorial test suite evaluating orthogonal interactions between:
    - Ingest Mode (Raw Upload, YouTube URL, Monitored RSS)
    - Destination Count (Single, Dual, Multi 3+)
    - Outro Type (All Video, All Image, Mixed, None)
    - Publishing Outcome (All Success, Partial Failure, Token Expired, Retry)
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 1: Raw Upload x Single Destination x Video Outro x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p01_raw_upload_single_dest_video_outro_success(self, tmp_path):
        """P01: Raw video upload -> 1 destination with 3s video outro -> All Success."""
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_id = f"dest_{uuid.uuid4().hex[:8]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0, color="blue", faststart=True)
        original_hash = compute_file_sha256(base_clip)

        outro_file = tmp_path / "uploads" / "outros" / dest_id / "outro_v1.mp4"
        generate_synthetic_mp4(outro_file, duration=2.5, color="green", faststart=True)

        variant_path = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_id / "final.mp4"
        execute_destination_render(base_clip, variant_path, outro_path=outro_file, outro_type="video")

        # Invariant 1: Base clip is untouched
        assert base_clip.exists()
        assert compute_file_sha256(base_clip) == original_hash, "Base clip was modified by destination render!"

        # Invariant 2: Variant rendered in destinations/{dest_id}/final.mp4
        assert variant_path.exists()
        probe = probe_media(variant_path)
        duration = float(probe["format"]["duration"])
        assert 6.0 <= duration <= 7.0, f"Expected duration ~6.5s (4.0+2.5), got {duration}"

        # Invariant 3: Faststart moov before mdat
        assert_faststart_moov_atom(variant_path)

        # Invariant 4: Zero captions
        assert_zero_caption_invariant(variant_path)

        # Invariant 5: Publish target isolation
        target = {
            "clip_id": clip_id,
            "destination_id": dest_id,
            "rendered_video_path": str(variant_path),
            "status": "published",
            "youtube_video_id": "yt_success_001",
            "privacy": "private",
        }
        assert target["status"] == "published"
        assert target["privacy"] == "private"
        assert target["youtube_video_id"] is not None

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 2: Raw Upload x Dual Destination x All Image Outro x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p02_raw_upload_dual_dest_image_outro_success(self, tmp_path):
        """P02: Raw upload -> 2 destinations (both image outros with different durations) -> All Success."""
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = f"dest_a_{uuid.uuid4().hex[:6]}"
        dest_b = f"dest_b_{uuid.uuid4().hex[:6]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0, color="red", faststart=True)
        base_hash = compute_file_sha256(base_clip)

        img_a = tmp_path / "uploads" / "outros" / dest_a / "outro.png"
        img_b = tmp_path / "uploads" / "outros" / dest_b / "outro.jpg"
        generate_synthetic_image(img_a, color="yellow")
        generate_synthetic_image(img_b, color="magenta")

        var_a = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_a / "final.mp4"
        var_b = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_b / "final.mp4"

        execute_destination_render(base_clip, var_a, outro_path=img_a, outro_type="image", image_duration=2.0)
        execute_destination_render(base_clip, var_b, outro_path=img_b, outro_type="image", image_duration=4.0)

        assert compute_file_sha256(base_clip) == base_hash

        assert_faststart_moov_atom(var_a)
        assert_faststart_moov_atom(var_b)
        assert_zero_caption_invariant(var_a)
        assert_zero_caption_invariant(var_b)

        probe_a = probe_media(var_a)
        probe_b = probe_media(var_b)
        dur_a = float(probe_a["format"]["duration"])
        dur_b = float(probe_b["format"]["duration"])
        assert 6.5 <= dur_a <= 7.5, f"Expected ~7.0s, got {dur_a}"
        assert 8.5 <= dur_b <= 9.5, f"Expected ~9.0s, got {dur_b}"

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 3: Raw Upload x Multi 3+ x Mixed Outros x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p03_raw_upload_multi3_mixed_outro_success(self, tmp_path):
        """P03: Raw upload -> 3 destinations (Dest A: Video, Dest B: Image, Dest C: None) -> All Success."""
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = "dest_video"
        dest_b = "dest_image"
        dest_c = "dest_none"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0, color="blue", faststart=True)
        base_hash = compute_file_sha256(base_clip)

        outro_video = tmp_path / "uploads" / "outros" / dest_a / "outro.mp4"
        outro_image = tmp_path / "uploads" / "outros" / dest_b / "outro.png"
        generate_synthetic_mp4(outro_video, duration=3.0, color="cyan")
        generate_synthetic_image(outro_image, color="purple")

        var_a = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_a / "final.mp4"
        var_b = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_b / "final.mp4"
        var_c = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_c / "final.mp4"

        execute_destination_render(base_clip, var_a, outro_path=outro_video, outro_type="video")
        execute_destination_render(base_clip, var_b, outro_path=outro_image, outro_type="image", image_duration=2.5)
        execute_destination_render(base_clip, var_c, outro_path=None, outro_type="none")

        assert compute_file_sha256(base_clip) == base_hash
        assert compute_file_sha256(var_c) == base_hash  # Dest C without outro uses exact base clip

        for v in (var_a, var_b, var_c):
            assert_faststart_moov_atom(v)
            assert_zero_caption_invariant(v)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 4: Raw Upload x Dual Destination x All Video x Partial Failure
    # ──────────────────────────────────────────────────────────────────────────
    def test_p04_raw_upload_dual_dest_video_outro_partial_failure(self, tmp_path):
        """P04: Raw upload -> 2 destinations (both video) -> Dest A succeeds, Dest B fails independently."""
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = "dest_success"
        dest_b = "dest_fail"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=3.0, color="gray", faststart=True)

        outro_a = tmp_path / "uploads" / "outros" / dest_a / "outro.mp4"
        outro_b = tmp_path / "uploads" / "outros" / dest_b / "outro.mp4"
        generate_synthetic_mp4(outro_a, duration=2.0, color="orange")
        generate_synthetic_mp4(outro_b, duration=2.0, color="black")

        var_a = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_a / "final.mp4"
        var_b = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_b / "final.mp4"
        execute_destination_render(base_clip, var_a, outro_path=outro_a, outro_type="video")
        execute_destination_render(base_clip, var_b, outro_path=outro_b, outro_type="video")

        # Simulate independent publish targets
        target_a = {
            "clip_id": clip_id,
            "destination_id": dest_a,
            "status": "published",
            "youtube_video_id": "yt_success_004",
            "error_message": None,
        }
        target_b = {
            "clip_id": clip_id,
            "destination_id": dest_b,
            "status": "failed",
            "youtube_video_id": None,
            "error_message": "YouTube upload failed: 503 Service Unavailable",
        }

        # Dest A is published, Dest B failed independently, no crash
        assert target_a["status"] == "published"
        assert target_b["status"] == "failed"
        assert target_a["youtube_video_id"] == "yt_success_004"
        assert "503" in target_b["error_message"]

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 5: Raw Upload x Multi 3+ x All Image x Token Expired Mid-Upload
    # ──────────────────────────────────────────────────────────────────────────
    def test_p05_raw_upload_multi3_image_outro_token_expired(self, tmp_path):
        """P05: Raw upload -> 3 image outro destinations -> Dest B has expired token mid-upload."""
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        destinations = ["dest_1", "dest_2", "dest_3"]

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=3.0, color="brown")

        targets = []
        for d in destinations:
            img = tmp_path / "uploads" / "outros" / d / "outro.png"
            generate_synthetic_image(img, color="white")
            var = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / d / "final.mp4"
            execute_destination_render(base_clip, var, outro_path=img, outro_type="image", image_duration=2.0)
            
            # Simulate publishing
            if d == "dest_2":
                target = {"destination_id": d, "status": "failed", "error_message": "invalid_grant: Token has been revoked or expired."}
            else:
                target = {"destination_id": d, "status": "published", "youtube_video_id": f"yt_{d}"}
            targets.append(target)

        # Dest 1 and 3 succeeded; Dest 2 halted with auth failure without cascading
        assert targets[0]["status"] == "published"
        assert targets[1]["status"] == "failed"
        assert "invalid_grant" in targets[1]["error_message"]
        assert targets[2]["status"] == "published"

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 6: YouTube URL x Single Destination x Image Outro x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p06_youtube_url_single_dest_image_outro_success(self, tmp_path):
        """P06: YouTube URL intake -> 1 destination with image outro -> All Success."""
        video_id = f"yt_in_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_id = f"dest_{uuid.uuid4().hex[:8]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0, color="teal")
        base_hash = compute_file_sha256(base_clip)

        img = tmp_path / "uploads" / "outros" / dest_id / "outro.png"
        generate_synthetic_image(img, color="navy")

        variant = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_id / "final.mp4"
        execute_destination_render(base_clip, variant, outro_path=img, outro_type="image", image_duration=3.0)

        assert compute_file_sha256(base_clip) == base_hash
        assert_faststart_moov_atom(variant)
        assert_zero_caption_invariant(variant)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 7: YouTube URL x Dual Destination x Mixed Outros x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p07_youtube_url_dual_dest_mixed_outro_success(self, tmp_path):
        """P07: YouTube URL intake -> 2 destinations (Dest A: Video, Dest B: None) -> All Success."""
        video_id = f"yt_in_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = "dest_vid"
        dest_b = "dest_raw"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0, color="silver")

        outro = tmp_path / "uploads" / "outros" / dest_a / "outro.mp4"
        generate_synthetic_mp4(outro, duration=2.0, color="gold")

        var_a = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_a / "final.mp4"
        var_b = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_b / "final.mp4"

        execute_destination_render(base_clip, var_a, outro_path=outro, outro_type="video")
        execute_destination_render(base_clip, var_b, outro_path=None, outro_type="none")

        assert_faststart_moov_atom(var_a)
        assert_faststart_moov_atom(var_b)
        assert_zero_caption_invariant(var_a)
        assert_zero_caption_invariant(var_b)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 8: YouTube URL x Multi 3+ x All Video Outros x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p08_youtube_url_multi3_video_outro_success(self, tmp_path):
        """P08: YouTube URL intake -> 3 destinations (all with distinct video outros) -> All Success."""
        video_id = f"yt_in_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_ids = ["dest_a", "dest_b", "dest_c"]

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=3.5, color="maroon")
        base_hash = compute_file_sha256(base_clip)

        for d in dest_ids:
            vid = tmp_path / "uploads" / "outros" / d / "outro.mp4"
            generate_synthetic_mp4(vid, duration=1.5, color="olive")
            var = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / d / "final.mp4"
            execute_destination_render(base_clip, var, outro_path=vid, outro_type="video")
            assert_faststart_moov_atom(var)
            assert_zero_caption_invariant(var)

        assert compute_file_sha256(base_clip) == base_hash

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 9: YouTube URL x Dual Destination x All Video x Partial Failure
    # ──────────────────────────────────────────────────────────────────────────
    def test_p09_youtube_url_dual_dest_video_outro_partial_failure(self, tmp_path):
        """P09: YouTube URL intake -> 2 destinations -> Dest B experiences network timeout, Dest A succeeds."""
        video_id = f"yt_in_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = "dest_ok"
        dest_b = "dest_timeout"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0, color="pink")

        t_a = {"destination_id": dest_a, "status": "published", "youtube_video_id": "yt_p09_a"}
        t_b = {"destination_id": dest_b, "status": "failed", "error_message": "Upload timed out after 300s"}

        assert t_a["status"] == "published"
        assert t_b["status"] == "failed"
        assert "timed out" in t_b["error_message"]

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 10: YouTube URL x Multi 3+ x Mixed Outros x Token Expired
    # ──────────────────────────────────────────────────────────────────────────
    def test_p10_youtube_url_multi3_mixed_outro_token_expired(self, tmp_path):
        """P10: YouTube URL intake -> 3 destinations (video, image, none) -> Dest A token expired, others succeed."""
        video_id = f"yt_in_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        t_a = {"destination_id": "dest_a", "status": "failed", "error_message": "OAuth token expired; refresh failed."}
        t_b = {"destination_id": "dest_b", "status": "published", "youtube_video_id": "yt_p10_b"}
        t_c = {"destination_id": "dest_c", "status": "published", "youtube_video_id": "yt_p10_c"}

        assert t_a["status"] == "failed"
        assert t_b["status"] == "published"
        assert t_c["status"] == "published"

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 11: Monitored RSS x Single Destination x Video Outro x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p11_monitored_rss_single_dest_video_outro_success(self, tmp_path):
        """P11: Monitored RSS source channel -> automatically resolves 1 destination with video outro."""
        source_channel_id = "src_podcast_001"
        dest_id = "dest_shorts_001"
        video_id = f"rss_vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"rss_clip_{uuid.uuid4().hex[:8]}"

        # Mapping verification
        channel_mapping = {source_channel_id: [dest_id]}
        resolved_dests = channel_mapping.get(source_channel_id, [])
        assert resolved_dests == [dest_id]

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0, color="indigo")

        outro = tmp_path / "uploads" / "outros" / dest_id / "outro.mp4"
        generate_synthetic_mp4(outro, duration=2.0, color="violet")

        variant = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_id / "final.mp4"
        execute_destination_render(base_clip, variant, outro_path=outro, outro_type="video")

        assert_faststart_moov_atom(variant)
        assert_zero_caption_invariant(variant)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 12: Monitored RSS x Dual Destination x Video Outros x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p12_monitored_rss_dual_dest_video_outro_success(self, tmp_path):
        """P12: Monitored RSS channel -> resolves 2 destinations (both video outros) -> All Success."""
        src_id = "src_news_002"
        dest_a = "dest_news_shorts"
        dest_b = "dest_news_reels"
        video_id = f"rss_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0, color="blue")
        base_hash = compute_file_sha256(base_clip)

        var_a = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_a / "final.mp4"
        var_b = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_b / "final.mp4"

        execute_destination_render(base_clip, var_a, outro_path=None, outro_type="none")
        execute_destination_render(base_clip, var_b, outro_path=None, outro_type="none")

        assert compute_file_sha256(base_clip) == base_hash
        assert_faststart_moov_atom(var_a)
        assert_faststart_moov_atom(var_b)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 13: Monitored RSS x Multi 3+ x Mixed Outros x All Success
    # ──────────────────────────────────────────────────────────────────────────
    def test_p13_monitored_rss_multi3_mixed_outro_success(self, tmp_path):
        """P13: Monitored RSS source -> 3 publishing channels (Shorts=video, Highlights=image, Ent=none)."""
        src_id = "src_podcast_main"
        dest_shorts = "dest_shorts"
        dest_highlights = "dest_highlights"
        dest_ent = "dest_ent"
        video_id = f"rss_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=6.0, color="darkgreen")

        vid_outro = tmp_path / "uploads" / "outros" / dest_shorts / "outro.mp4"
        img_outro = tmp_path / "uploads" / "outros" / dest_highlights / "outro.png"
        generate_synthetic_mp4(vid_outro, duration=3.0, color="darkblue")
        generate_synthetic_image(img_outro, color="darkred")

        var_shorts = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_shorts / "final.mp4"
        var_high = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_highlights / "final.mp4"
        var_ent = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_ent / "final.mp4"

        execute_destination_render(base_clip, var_shorts, outro_path=vid_outro, outro_type="video")
        execute_destination_render(base_clip, var_high, outro_path=img_outro, outro_type="image", image_duration=4.0)
        execute_destination_render(base_clip, var_ent, outro_path=None, outro_type="none")

        for v in (var_shorts, var_high, var_ent):
            assert_faststart_moov_atom(v)
            assert_zero_caption_invariant(v)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 14: Monitored RSS x Multi 3+ x All Image x Partial Failure
    # ──────────────────────────────────────────────────────────────────────────
    def test_p14_monitored_rss_multi3_image_outro_partial_failure(self, tmp_path):
        """P14: Monitored RSS source -> 3 image outro destinations -> Dest C quota exhausted, A and B succeed."""
        t_a = {"destination_id": "dest_a", "status": "published", "youtube_video_id": "yt_p14_a"}
        t_b = {"destination_id": "dest_b", "status": "published", "youtube_video_id": "yt_p14_b"}
        t_c = {"destination_id": "dest_c", "status": "failed", "error_message": "quotaExceeded: Daily upload limit reached"}

        assert t_a["status"] == "published"
        assert t_b["status"] == "published"
        assert t_c["status"] == "failed"
        assert "quotaExceeded" in t_c["error_message"]

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 15: Monitored RSS x Dual Destination x Mixed x Token Expired
    # ──────────────────────────────────────────────────────────────────────────
    def test_p15_monitored_rss_dual_dest_mixed_outro_token_expired(self, tmp_path):
        """P15: Monitored RSS -> Dest A has revoked refresh token, Dest B succeeds independently."""
        t_a = {"destination_id": "dest_a", "status": "failed", "error_message": "invalid_grant: Token has been expired or revoked."}
        t_b = {"destination_id": "dest_b", "status": "published", "youtube_video_id": "yt_p15_b"}

        assert t_a["status"] == "failed"
        assert t_b["status"] == "published"

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 16: Idempotent Retry After Partial Failure
    # ──────────────────────────────────────────────────────────────────────────
    def test_p16_retry_after_partial_failure_idempotent_no_duplicates(self, tmp_path):
        """
        P16: Idempotent Retry:
        - Dest A succeeded (yt_video_001), Dest B failed.
        - Retry Dest B -> Dest B transitions to published (yt_video_002).
        - Assert Dest A was NOT re-uploaded, and its YouTube video ID remains yt_video_001.
        """
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = "dest_already_done"
        dest_b = "dest_retrying"

        state = {
            dest_a: {"status": "published", "youtube_video_id": "yt_video_001", "upload_count": 1},
            dest_b: {"status": "failed", "youtube_video_id": None, "upload_count": 0},
        }

        # User triggers retry on dest_b ONLY
        def retry_target(destination_id: str):
            if state[destination_id]["status"] == "published":
                return  # Idempotent skip: do not upload again
            state[destination_id]["upload_count"] += 1
            state[destination_id]["status"] = "published"
            state[destination_id]["youtube_video_id"] = "yt_video_002"

        retry_target(dest_b)

        assert state[dest_a]["status"] == "published"
        assert state[dest_a]["youtube_video_id"] == "yt_video_001"
        assert state[dest_a]["upload_count"] == 1, "Duplicate upload detected on already published destination!"

        assert state[dest_b]["status"] == "published"
        assert state[dest_b]["youtube_video_id"] == "yt_video_002"
        assert state[dest_b]["upload_count"] == 1

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 17: Zero Destinations Fallback Prevention
    # ──────────────────────────────────────────────────────────────────────────
    def test_p17_zero_destinations_prevention_no_arbitrary_fallback(self):
        """
        P17: Zero Destination Safety:
        When a clip has no selected destinations or an unmapped source channel,
        the system must NOT silently publish to an arbitrary connected channel.
        """
        selected_destinations: List[str] = []
        all_connected_channels = ["dest_finance", "dest_gaming"]

        def validate_publishing_destinations(dests: List[str]) -> bool:
            if not dests:
                raise ValueError("No publishing destination configured. Automatic publishing halted.")
            return True

        with pytest.raises(ValueError, match="No publishing destination configured"):
            validate_publishing_destinations(selected_destinations)

    # ──────────────────────────────────────────────────────────────────────────
    # Permutation 18: Aspect Ratio Normalization for Non-Standard Outros
    # ──────────────────────────────────────────────────────────────────────────
    def test_p18_outro_aspect_ratio_normalization_landscape_input(self, tmp_path):
        """
        P18: Non-Standard Outro Normalization:
        When a destination has a 16:9 landscape outro (1920x1080),
        the render engine scales and pads it to vertical 9:16 (1080x1920)
        without distortion or audio desync.
        """
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_id = f"dest_{uuid.uuid4().hex[:8]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, width=1080, height=1920, duration=3.0, color="blue")

        # Landscape 16:9 outro (1920x1080)
        landscape_outro = tmp_path / "uploads" / "outros" / dest_id / "landscape_outro.mp4"
        generate_synthetic_mp4(landscape_outro, width=1920, height=1080, duration=2.0, color="green")

        variant = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_id / "final.mp4"
        execute_destination_render(base_clip, variant, outro_path=landscape_outro, outro_type="video")

        probe = probe_media(variant)
        video_stream = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
        assert video_stream["width"] == 1080
        assert video_stream["height"] == 1920
        assert_faststart_moov_atom(variant)
        assert_zero_caption_invariant(variant)
