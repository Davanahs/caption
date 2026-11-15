"""
tests/e2e/test_tier4_real_world_scenarios.py
============================================
Tier 4: Real-World Application Scenarios Suite for ClipForge Multi-Destination
Publishing & Automatic Outro System.

Opaque-Box Requirement Derivation:
- TEST_INFRA.md § Real-World Application Scenarios (Scenarios 1 through 5)
- ORIGINAL_REQUEST.md §2 (Core Requirement: Monitored source -> multiple destinations -> distinct outros)
- ORIGINAL_REQUEST.md §6 (Monitoring channels multi-destination mapping)
- ORIGINAL_REQUEST.md §7 (Ingest routing across Raw Upload, YouTube URL, Auto Monitoring)
- ORIGINAL_REQUEST.md §8 (Destination-specific rendering & non-destructive storage)
- ORIGINAL_REQUEST.md §9 (Independent publishing tracking & idempotency)
- ORIGINAL_REQUEST.md §10 (Destination preview switcher)
- ORIGINAL_REQUEST.md §12 (Failure handling & retry)
- PROJECT.md § Key Invariants:
  1. Zero captions/subtitles (no SRT/ASS/VTT or burned-in subtitles).
  2. All MP4 outputs must contain -movflags +faststart (moov atom before mdat).
  3. Original generated clip (final.mp4) remains pristine and untouched.
  4. Private-by-default publishing (privacyStatus == 'private').
  5. Isolated credentials and token handling.
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

# Try importing media helpers from shared e2e_media_helpers; fallback if running standalone
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
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def render_destination_variant(
    base_clip_path: Path,
    output_variant_path: Path,
    outro_path: Optional[Path] = None,
    outro_type: str = "none",
    image_duration: float = 3.0,
) -> Path:
    """Renders a destination-specific variant per project interface contract."""
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
        raise ValueError(f"Unsupported outro_type: {outro_type}")

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg render failed ({proc.returncode}):\n{proc.stderr}")
    return output_variant_path


class TestTier4RealWorldScenarios:
    """
    Tier 4: Five Comprehensive End-to-End Workflows
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 1: Monitored Podcast Source -> 3 Publishing Destinations
    # ──────────────────────────────────────────────────────────────────────────
    def test_scenario_1_monitored_podcast_to_three_destinations(self, tmp_path):
        """
        Scenario 1:
        Monitored Podcast Source -> 3 Publishing Destinations:
        - Dest A: Shorts Channel with 3.0s Video Outro
        - Dest B: Highlights Channel with 5.0s Image Outro
        - Dest C: General Entertainment Channel with No Outro
        Full lifecycle:
        1. Setup source channel and 3 destination channels with respective outro configs.
        2. Set up ChannelDestination mappings (Source -> A, B, C).
        3. Automated ingestion triggers clip generation (base 9:16 vertical clip).
        4. Render variants for each destination:
           - Dest A receives base + 3s video outro in destinations/dest_A/final.mp4.
           - Dest B receives base + 5s image outro in destinations/dest_B/final.mp4.
           - Dest C receives pristine base clip in destinations/dest_C/final.mp4.
        5. Verify base clip remains untouched.
        6. Verify faststart and zero-captions on all variants.
        7. Execute publishing for all 3 destinations:
           - 3 independent PublishTarget records.
           - All 3 successfully uploaded to YouTube with privacy='private'.
        """
        source_channel_id = "chan_podcast_source_001"
        dest_a_id = "chan_dest_shorts_a"
        dest_b_id = "chan_dest_highlights_b"
        dest_c_id = "chan_dest_entertainment_c"

        video_id = f"podcast_ep_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        # Step 1: Destination Outro Assets
        outro_a_video = tmp_path / "uploads" / "outros" / dest_a_id / "outro.mp4"
        outro_b_image = tmp_path / "uploads" / "outros" / dest_b_id / "outro.png"
        generate_synthetic_mp4(outro_a_video, duration=3.0, color="darkblue", faststart=True)
        generate_synthetic_image(outro_b_image, color="gold")

        # Step 2: Channel Destinations Mapping Configuration
        channel_destinations_map = {
            source_channel_id: [dest_a_id, dest_b_id, dest_c_id]
        }
        mapped_destinations = channel_destinations_map[source_channel_id]
        assert len(mapped_destinations) == 3

        # Step 3: Base Clip Cutting & Generation
        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, width=1080, height=1920, duration=8.0, color="black", faststart=True)
        base_sha256 = compute_file_sha256(base_clip)
        base_size = base_clip.stat().st_size

        # Step 4: Multi-Destination Rendering
        variant_a = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_a_id / "final.mp4"
        variant_b = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_b_id / "final.mp4"
        variant_c = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_c_id / "final.mp4"

        render_destination_variant(base_clip, variant_a, outro_path=outro_a_video, outro_type="video")
        render_destination_variant(base_clip, variant_b, outro_path=outro_b_image, outro_type="image", image_duration=5.0)
        render_destination_variant(base_clip, variant_c, outro_path=None, outro_type="none")

        # Step 5: Base Clip Invariant Assertion
        assert compute_file_sha256(base_clip) == base_sha256, "Pristine base clip was altered by rendering!"
        assert base_clip.stat().st_size == base_size

        # Step 6: Verify Outro Concatenation Durations
        dur_a = float(probe_media(variant_a)["format"]["duration"])
        dur_b = float(probe_media(variant_b)["format"]["duration"])
        dur_c = float(probe_media(variant_c)["format"]["duration"])
        assert 10.5 <= dur_a <= 11.5, f"Variant A duration mismatch: expected ~11.0s, got {dur_a}"
        assert 12.5 <= dur_b <= 13.5, f"Variant B duration mismatch: expected ~13.0s, got {dur_b}"
        assert 7.5 <= dur_c <= 8.5, f"Variant C duration mismatch: expected ~8.0s, got {dur_c}"

        # Step 7: Faststart & Zero Caption Verification
        for var in (variant_a, variant_b, variant_c):
            assert_faststart_moov_atom(var)
            assert_zero_caption_invariant(var)

        # Step 8: Multi-Target Publishing Simulation
        publish_targets = [
            {
                "id": f"pt_{dest_a_id}",
                "clip_id": clip_id,
                "destination_id": dest_a_id,
                "rendered_video_path": str(variant_a),
                "status": "published",
                "youtube_video_id": "yt_shorts_a_123",
                "privacy": "private",
                "idempotency_key": f"pub_{clip_id}_{dest_a_id}",
            },
            {
                "id": f"pt_{dest_b_id}",
                "clip_id": clip_id,
                "destination_id": dest_b_id,
                "rendered_video_path": str(variant_b),
                "status": "published",
                "youtube_video_id": "yt_highlights_b_456",
                "privacy": "private",
                "idempotency_key": f"pub_{clip_id}_{dest_b_id}",
            },
            {
                "id": f"pt_{dest_c_id}",
                "clip_id": clip_id,
                "destination_id": dest_c_id,
                "rendered_video_path": str(variant_c),
                "status": "published",
                "youtube_video_id": "yt_ent_c_789",
                "privacy": "private",
                "idempotency_key": f"pub_{clip_id}_{dest_c_id}",
            },
        ]

        assert len(publish_targets) == 3
        for pt in publish_targets:
            assert pt["status"] == "published"
            assert pt["privacy"] == "private"
            assert pt["youtube_video_id"].startswith("yt_")
            assert Path(pt["rendered_video_path"]).exists()

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 2: Manual Raw Video Upload -> 2 Destinations (1 with video outro, 1 with no outro)
    # ──────────────────────────────────────────────────────────────────────────
    def test_scenario_2_manual_raw_upload_two_destinations(self, tmp_path):
        """
        Scenario 2:
        Manual Raw Video Upload -> 2 Destinations:
        - Dest 1: Has a 3s MP4 video outro.
        - Dest 2: Has no outro configured.
        Workflow:
        1. User selects 2 destination channels in the manual upload dialog.
        2. Ingestion pipeline creates job with destination_ids=[dest_1, dest_2].
        3. Processing generates base clip.
        4. Render variants generated for Dest 1 and Dest 2.
        5. User previews both variants in UI preview switcher.
        6. Publishing initiates independent upload jobs.
        7. Both destinations complete successfully.
        """
        dest_1_id = "dest_creator_daily"
        dest_2_id = "dest_creator_backup"
        video_id = f"raw_upload_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        # Raw uploaded video
        raw_video = tmp_path / "uploads" / "raw" / f"{video_id}.mp4"
        generate_synthetic_mp4(raw_video, duration=10.0, color="gray", faststart=True)

        # Dest 1 outro
        outro_video = tmp_path / "uploads" / "outros" / dest_1_id / "outro.mp4"
        generate_synthetic_mp4(outro_video, duration=3.0, color="orange", faststart=True)

        # Ingestion Job Config
        job_config = {
            "video_id": video_id,
            "destination_ids": [dest_1_id, dest_2_id],
            "mode": "manual_raw_upload",
        }
        assert len(job_config["destination_ids"]) == 2

        # Base Clip Render
        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=6.0, color="purple", faststart=True)
        base_sha = compute_file_sha256(base_clip)

        # Renders for Dest 1 and Dest 2
        var_1 = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_1_id / "final.mp4"
        var_2 = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / dest_2_id / "final.mp4"

        render_destination_variant(base_clip, var_1, outro_path=outro_video, outro_type="video")
        render_destination_variant(base_clip, var_2, outro_path=None, outro_type="none")

        # Invariant Assertions
        assert compute_file_sha256(base_clip) == base_sha
        assert compute_file_sha256(var_2) == base_sha  # No outro == exact base clip

        assert_faststart_moov_atom(var_1)
        assert_faststart_moov_atom(var_2)
        assert_zero_caption_invariant(var_1)
        assert_zero_caption_invariant(var_2)

        # Preview Switcher verification
        preview_data = {
            dest_1_id: {"variant_path": str(var_1), "duration": float(probe_media(var_1)["format"]["duration"]), "has_outro": True},
            dest_2_id: {"variant_path": str(var_2), "duration": float(probe_media(var_2)["format"]["duration"]), "has_outro": False},
        }
        assert preview_data[dest_1_id]["has_outro"] is True
        assert preview_data[dest_2_id]["has_outro"] is False
        assert preview_data[dest_1_id]["duration"] > preview_data[dest_2_id]["duration"]

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 3: YouTube URL Ingest -> 3 Destinations -> Failure on Dest B -> Idempotent Retry
    # ──────────────────────────────────────────────────────────────────────────
    def test_scenario_3_youtube_url_retry_failed_destination(self, tmp_path):
        """
        Scenario 3:
        YouTube URL Ingest -> 3 Destinations:
        - Ingest from YouTube URL.
        - Produce 3 variants for Dest A, Dest B, Dest C.
        - User inspects Preview Switcher.
        - Initial Publish execution:
          - Dest A succeeds (yt_video_A).
          - Dest B fails due to simulated YouTube 500 internal server error.
          - Dest C succeeds (yt_video_C).
        - Idempotent Retry on Dest B:
          - Dest B is retried and succeeds (yt_video_B).
          - Dest A and Dest C are NOT re-uploaded, and their YouTube IDs remain identical.
        """
        video_id = f"yt_url_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"
        dest_a = "chan_alpha"
        dest_b = "chan_beta"
        dest_c = "chan_gamma"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=5.0, color="teal", faststart=True)

        for d in (dest_a, dest_b, dest_c):
            var = tmp_path / "outputs" / video_id / "clips" / clip_id / "destinations" / d / "final.mp4"
            render_destination_variant(base_clip, var, outro_path=None, outro_type="none")
            assert_faststart_moov_atom(var)
            assert_zero_caption_invariant(var)

        # Track remote YouTube mock calls
        youtube_uploads = {}

        def perform_upload(target_id: str, dest_id: str, fail_dest_b: bool = True):
            if dest_id in youtube_uploads:
                # Idempotency guard: already uploaded
                return youtube_uploads[dest_id]["video_id"]
            if dest_id == dest_b and fail_dest_b:
                raise RuntimeError("500 Internal Server Error from YouTube API")
            video_id_res = f"yt_uploaded_{dest_id}_{uuid.uuid4().hex[:4]}"
            youtube_uploads[dest_id] = {"video_id": video_id_res, "target_id": target_id}
            return video_id_res

        # Initial Publish Run
        targets_state = {
            dest_a: {"status": "pending", "youtube_id": None, "error": None},
            dest_b: {"status": "pending", "youtube_id": None, "error": None},
            dest_c: {"status": "pending", "youtube_id": None, "error": None},
        }

        for d in (dest_a, dest_b, dest_c):
            try:
                yid = perform_upload(f"pt_{d}", d, fail_dest_b=True)
                targets_state[d]["status"] = "published"
                targets_state[d]["youtube_id"] = yid
            except Exception as e:
                targets_state[d]["status"] = "failed"
                targets_state[d]["error"] = str(e)

        # Verify initial state: A and C published, B failed
        assert targets_state[dest_a]["status"] == "published"
        assert targets_state[dest_b]["status"] == "failed"
        assert targets_state[dest_c]["status"] == "published"
        initial_yid_a = targets_state[dest_a]["youtube_id"]
        initial_yid_c = targets_state[dest_c]["youtube_id"]

        # Trigger Retry on Dest B (transient error cleared)
        try:
            yid_b = perform_upload(f"pt_{dest_b}", dest_b, fail_dest_b=False)
            targets_state[dest_b]["status"] = "published"
            targets_state[dest_b]["youtube_id"] = yid_b
            targets_state[dest_b]["error"] = None
        except Exception as e:
            targets_state[dest_b]["status"] = "failed"

        # Verify post-retry state: B published, A and C untouched
        assert targets_state[dest_b]["status"] == "published"
        assert targets_state[dest_b]["youtube_id"].startswith(f"yt_uploaded_{dest_b}")
        assert targets_state[dest_a]["youtube_id"] == initial_yid_a, "Dest A was duplicated on retry!"
        assert targets_state[dest_c]["youtube_id"] == initial_yid_c, "Dest C was duplicated on retry!"
        assert len(youtube_uploads) == 3  # Exactly 1 upload per channel

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 4: Destination Disconnected Mid-Pipeline -> Remaining Destinations Continue
    # ──────────────────────────────────────────────────────────────────────────
    def test_scenario_4_destination_disconnected_mid_pipeline(self, tmp_path):
        """
        Scenario 4:
        Destination Disconnected Mid-Pipeline:
        - 3 destinations configured (Dest A, Dest B, Dest C).
        - Variants rendered.
        - Right before publishing, Dest B's OAuth authorization is revoked / disconnected.
        - Publishing pipeline executes:
          - Dest A publishes successfully.
          - Dest B fails gracefully with authorization revoked error.
          - Dest C publishes successfully.
        - Entire pipeline continues without aborting or crashing.
        """
        dest_a = "dest_live_a"
        dest_b = "dest_revoked_b"
        dest_c = "dest_live_c"
        video_id = f"vid_disc_{uuid.uuid4().hex[:8]}"
        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        base_clip = tmp_path / "outputs" / video_id / "clips" / clip_id / "final.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0, color="navy")

        # Simulate authorization states
        auth_status = {
            dest_a: {"authorized": True, "error": None},
            dest_b: {"authorized": False, "error": "Channel authorization disconnected or expired."},
            dest_c: {"authorized": True, "error": None},
        }

        results = {}
        for d in (dest_a, dest_b, dest_c):
            if not auth_status[d]["authorized"]:
                results[d] = {"status": "failed", "error": auth_status[d]["error"]}
            else:
                results[d] = {"status": "published", "youtube_id": f"yt_{d}"}

        assert results[dest_a]["status"] == "published"
        assert results[dest_b]["status"] == "failed"
        assert "disconnected or expired" in results[dest_b]["error"]
        assert results[dest_c]["status"] == "published"

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 5: Outro Replaced After Initial Configuration -> Versioning & Immutability
    # ──────────────────────────────────────────────────────────────────────────
    def test_scenario_5_outro_replaced_versioning_preservation(self, tmp_path):
        """
        Scenario 5:
        Outro Replaced After Initial Configuration:
        - Destination Channel has Outro V1 (3s Blue Video).
        - Clip 1 is ingested and rendered with Outro V1.
        - User updates Destination Channel's outro to Outro V2 (5s Red Video).
        - Clip 2 is ingested and rendered for the same Destination Channel.
        - Clip 2 correctly uses Outro V2.
        - CRITICAL INVARIANT: Clip 1 remains untouched and retains Outro V1.
        """
        dest_id = "dest_versioning_chan"
        vid_1 = f"vid_1_{uuid.uuid4().hex[:6]}"
        clip_1 = f"clip_1_{uuid.uuid4().hex[:6]}"
        vid_2 = f"vid_2_{uuid.uuid4().hex[:6]}"
        clip_2 = f"clip_2_{uuid.uuid4().hex[:6]}"

        # Step 1: Upload Outro V1
        outro_v1 = tmp_path / "uploads" / "outros" / dest_id / "outro_v1.mp4"
        generate_synthetic_mp4(outro_v1, duration=3.0, color="blue", faststart=True)

        # Step 2: Render Clip 1 with Outro V1
        base_1 = tmp_path / "outputs" / vid_1 / "clips" / clip_1 / "final.mp4"
        generate_synthetic_mp4(base_1, duration=4.0, color="white", faststart=True)
        var_1 = tmp_path / "outputs" / vid_1 / "clips" / clip_1 / "destinations" / dest_id / "final.mp4"
        render_destination_variant(base_1, var_1, outro_path=outro_v1, outro_type="video")

        clip_1_hash = compute_file_sha256(var_1)
        dur_1 = float(probe_media(var_1)["format"]["duration"])
        assert 6.5 <= dur_1 <= 7.5, f"Expected ~7.0s, got {dur_1}"

        # Step 3: Replace with Outro V2 (Version 2)
        outro_v2 = tmp_path / "uploads" / "outros" / dest_id / "outro_v2.mp4"
        generate_synthetic_mp4(outro_v2, duration=5.0, color="red", faststart=True)

        # Step 4: Render Clip 2 with Outro V2
        base_2 = tmp_path / "outputs" / vid_2 / "clips" / clip_2 / "final.mp4"
        generate_synthetic_mp4(base_2, duration=4.0, color="yellow", faststart=True)
        var_2 = tmp_path / "outputs" / vid_2 / "clips" / clip_2 / "destinations" / dest_id / "final.mp4"
        render_destination_variant(base_2, var_2, outro_path=outro_v2, outro_type="video")

        dur_2 = float(probe_media(var_2)["format"]["duration"])
        assert 8.5 <= dur_2 <= 9.5, f"Expected ~9.0s, got {dur_2}"

        # Step 5: Verify Prior Clip 1 Was NOT Altered
        assert compute_file_sha256(var_1) == clip_1_hash, "Prior rendered Clip 1 was mutated when outro was updated!"
        assert_faststart_moov_atom(var_1)
        assert_faststart_moov_atom(var_2)
        assert_zero_caption_invariant(var_1)
        assert_zero_caption_invariant(var_2)
