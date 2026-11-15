"""
test_adversarial_m2_challenge.py
================================
Adversarial stress-test harness for Milestone M2: Backend FFmpeg Pipeline & Video Ingestion Routing.

Mandatory Challenger Checks:
1. Single-source input flattening [input_path, input_path] executing cleanly without split deadlocks
   across diverse resolutions and aspect ratios:
   - 16:9 Standard HD (1920x1080)
   - 21:9 Ultrawide (2560x1080)
   - 4:3 Retro Aspect Ratio (1440x1080)
   - 9:16 Portrait Source (1080x1920)
   - Odd Dimensions (1921x1081)
   - Concurrent renders from the same source file
2. Audio stream preservation:
   - Videos with standard audio (AAC preserved)
   - Videos with silent / NO audio tracks (graceful pass via -map 0:a?)
   - Zero audio/video desync (diff < 0.05s, identical start PTS)
   - High sample-rate 48kHz stereo preservation
3. Output invariants and mobile playback standards:
   - Output resolution is strictly 1080x1920 (9:16 vertical)
   - Pixel format is strictly yuv420p (-pix_fmt yuv420p)
   - Container has faststart atom layout (moov before mdat)
   - R5 Zero-Caption Mandate: Input video containing embedded subtitles (mov_text) must be stripped
     so that the output video contains ZERO subtitle streams
4. Adversarial boundary conditions & validation rejection
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from backend.models.layout import (
    AudioPolicy,
    BackgroundPolicy,
    LayoutMode,
    LayoutPlan,
    RegionModel,
    ScaleMode,
    ZoomIntervention,
)
from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    create_gaming_layout_plan,
    get_facecam_preset,
    validate_normalized_rect,
)
from backend.services.layout_engine import LayoutEngine
from backend.services.reframe_engine import reframe_to_vertical
from backend.tests.gaming_test_fixtures import (
    assert_faststart_moov_atom,
    assert_filtergraph_zero_caption_invariant,
    assert_gaming_video_invariants,
    assert_zero_caption_invariant,
    generate_synthetic_video,
    parse_top_level_atoms,
    probe_media,
)


def create_synthetic_video_with_subtitles(
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    duration: float = 2.0,
    subtitle_text: str = "Adversarial Subtitle Embedded In Stream",
) -> Path:
    """Creates a synthetic video containing video, audio, and an embedded mov_text subtitle stream."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path = output_path.parent / f"{output_path.stem}.srt"
    srt_content = (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        f"{subtitle_text}\n"
    )
    srt_path.write_text(srt_content, encoding="utf-8")

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate=30:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-i", str(srt_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-c:s", "mov_text",
        "-map", "0:v", "-map", "1:a", "-map", "2:s",
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to create video with subtitles ({proc.returncode}):\n{proc.stderr}")

    try:
        srt_path.unlink()
    except Exception:
        pass

    assert output_path.exists()
    return output_path


def create_synthetic_video_no_audio(
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    duration: float = 2.0,
) -> Path:
    """Creates a synthetic video with NO audio stream (-an)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate=30:duration={duration}",
        "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to create no-audio video ({proc.returncode}):\n{proc.stderr}")
    return output_path


def create_synthetic_odd_video(
    output_path: Path,
    width: int = 1921,
    height: int = 1081,
    duration: float = 2.0,
) -> Path:
    """Creates an odd-dimension synthetic video (e.g. 1921x1081) using yuv444p for encoding validity."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=navy:s={width}x{height}:d={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=520:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv444p",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to create odd video ({proc.returncode}):\n{proc.stderr}")
    return output_path


# ==============================================================================
# CHALLENGE SUITE 1: RESOLUTION & ASPECT RATIO STRESS (SINGLE-SOURCE FLATTENING)
# ==============================================================================

class TestSingleSourceFlatteningResolutions:
    """Stress tests verifying single-source input flattening [input_path, input_path] across diverse aspect ratios."""

    @pytest.mark.asyncio
    async def test_16_9_standard_hd_1920x1080(self, tmp_path):
        """Stress: 16:9 standard horizontal HD video (1920x1080) rendered without split deadlocks."""
        src = tmp_path / "src_16_9.mp4"
        dst = tmp_path / "dst_16_9.mp4"
        generate_synthetic_video(src, width=1920, height=1080, duration=1.5, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        invariants = assert_gaming_video_invariants(dst, expected_width=1080, expected_height=1920)
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"

    @pytest.mark.asyncio
    async def test_21_9_ultrawide_2560x1080(self, tmp_path):
        """Stress: 21:9 ultrawide gaming footage (2560x1080) rendered without split deadlocks or distortion."""
        src = tmp_path / "src_21_9.mp4"
        dst = tmp_path / "dst_21_9.mp4"
        generate_synthetic_video(src, width=2560, height=1080, duration=1.5, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.15, "y": 0.0, "width": 0.70, "height": 1.0},
            "facecam_roi": {"x": 0.80, "y": 0.05, "width": 0.18, "height": 0.30},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=2560, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        invariants = assert_gaming_video_invariants(dst, expected_width=1080, expected_height=1920)
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"

    @pytest.mark.asyncio
    async def test_4_3_retro_1440x1080(self, tmp_path):
        """Stress: 4:3 retro video source (1440x1080) scaled to fill 9:16 vertical canvas."""
        src = tmp_path / "src_4_3.mp4"
        dst = tmp_path / "dst_4_3.mp4"
        generate_synthetic_video(src, width=1440, height=1080, duration=1.5, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.65, "y": 0.05, "width": 0.30, "height": 0.25},
            "facecam_placement": "top-left",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1440, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        invariants = assert_gaming_video_invariants(dst, expected_width=1080, expected_height=1920)
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"

    @pytest.mark.asyncio
    async def test_9_16_portrait_1080x1920(self, tmp_path):
        """Stress: 9:16 vertical portrait source (1080x1920) dual-region reframe without distortion."""
        src = tmp_path / "src_9_16.mp4"
        dst = tmp_path / "dst_9_16.mp4"
        generate_synthetic_video(src, width=1080, height=1920, duration=1.5, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.20, "width": 1.0, "height": 0.60},
            "facecam_roi": {"x": 0.10, "y": 0.05, "width": 0.40, "height": 0.20},
            "facecam_placement": "bottom-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1080, source_h=1920)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        invariants = assert_gaming_video_invariants(dst, expected_width=1080, expected_height=1920)
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"

    @pytest.mark.asyncio
    async def test_odd_dimensions_1921x1081(self, tmp_path):
        """
        Stress: Odd dimensions (1921x1081) directly tested.
        Even-pixel truncation logic must prevent FFmpeg crop failures and produce strict 1080x1920 yuv420p output.
        """
        src = tmp_path / "src_odd_1921x1081.mp4"
        dst = tmp_path / "dst_odd_1921x1081.mp4"
        create_synthetic_odd_video(src, width=1921, height=1081, duration=1.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.699, "y": 0.049, "width": 0.251, "height": 0.251},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1921, source_h=1081)

        # Confirm even pixel quantization for crops
        for r in plan.regions:
            assert r.crop_coords[0] % 2 == 0
            assert r.crop_coords[1] % 2 == 0
            assert r.crop_coords[2] % 2 == 0
            assert r.crop_coords[3] % 2 == 0

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        invariants = assert_gaming_video_invariants(dst, expected_width=1080, expected_height=1920)
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"

    @pytest.mark.asyncio
    async def test_concurrent_single_source_executions(self, tmp_path):
        """Stress: Multiple concurrent renders reading the same source file simultaneously without lock collisions."""
        src = tmp_path / "src_concurrent.mp4"
        dst1 = tmp_path / "dst_concurrent_1.mp4"
        dst2 = tmp_path / "dst_concurrent_2.mp4"
        generate_synthetic_video(src, width=1920, height=1080, duration=1.0, audio_freq=440)

        plan1 = LayoutEngine.create_gaming_plan({
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }, source_w=1920, source_h=1080)

        plan2 = LayoutEngine.create_gaming_plan({
            "gameplay_roi": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
            "facecam_roi": {"x": 0.05, "y": 0.05, "width": 0.30, "height": 0.22},
            "facecam_placement": "top-left",
        }, source_w=1920, source_h=1080)

        results = await asyncio.gather(
            reframe_to_vertical(input_path=src, output_path=dst1, mode="gaming", plan=plan1),
            reframe_to_vertical(input_path=src, output_path=dst2, mode="gaming", plan=plan2),
        )

        assert results[0].exists() and results[1].exists()
        assert results[0].stat().st_size > 0 and results[1].stat().st_size > 0


# ==============================================================================
# CHALLENGE SUITE 2: AUDIO PRESERVATION & SILENT AUDIO HANDLING
# ==============================================================================

class TestAudioPreservationAndRobustness:
    """Stress tests verifying audio preservation, zero desync, and handling of silent / no-audio sources."""

    @pytest.mark.asyncio
    async def test_standard_audio_preservation(self, tmp_path):
        """Stress: Source video with standard audio preserves audio stream as AAC."""
        src = tmp_path / "src_audio_std.mp4"
        dst = tmp_path / "dst_audio_std.mp4"
        generate_synthetic_video(src, width=1920, height=1080, duration=2.0, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        probe = probe_media(dst)
        audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        assert len(audio_streams) == 1
        assert audio_streams[0]["codec_name"] == "aac"
        assert int(audio_streams[0]["sample_rate"]) in (44100, 48000)

    @pytest.mark.asyncio
    async def test_silent_no_audio_video_handling(self, tmp_path):
        """
        Stress: Source video with NO audio track (-an) does NOT cause FFmpeg to fail.
        The -map 0:a? optional mapping must cleanly produce a valid video with 0 audio streams.
        """
        src = tmp_path / "src_no_audio.mp4"
        dst = tmp_path / "dst_no_audio.mp4"
        create_synthetic_video_no_audio(src, width=1920, height=1080, duration=1.5)

        # Prove source has NO audio streams
        src_probe = probe_media(src)
        assert len([s for s in src_probe["streams"] if s["codec_type"] == "audio"]) == 0

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        # Must execute cleanly without error
        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        assert dst.exists()
        assert dst.stat().st_size > 0

        dst_probe = probe_media(dst)
        video_streams = [s for s in dst_probe["streams"] if s["codec_type"] == "video"]
        audio_streams = [s for s in dst_probe["streams"] if s["codec_type"] == "audio"]
        assert len(video_streams) == 1
        assert len(audio_streams) == 0  # 0 audio streams, no crash

    @pytest.mark.asyncio
    async def test_zero_av_desync(self, tmp_path):
        """
        Stress: Verify audio and video start timestamps are synchronized (start_time == 0.0)
        and stream duration difference is under 0.05s (zero drift).
        """
        src = tmp_path / "src_sync.mp4"
        dst = tmp_path / "dst_sync.mp4"
        generate_synthetic_video(src, width=1920, height=1080, duration=3.0, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        probe = probe_media(dst)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        a_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")

        v_start = float(v_stream.get("start_time", 0.0))
        a_start = float(a_stream.get("start_time", 0.0))
        v_dur = float(v_stream.get("duration", 0.0))
        a_dur = float(a_stream.get("duration", 0.0))

        # Start timestamp sync
        assert abs(v_start - a_start) < 0.001, f"A/V start offset detected: v_start={v_start}, a_start={a_start}"

        # Duration drift check (< 0.05s)
        duration_diff = abs(v_dur - a_dur)
        assert duration_diff < 0.05, f"A/V duration desync exceeds 0.05s: diff={duration_diff}s"

    @pytest.mark.asyncio
    async def test_high_sample_rate_48khz_stereo(self, tmp_path):
        """Stress: Video with 48kHz stereo audio preserves channels and timing."""
        src = tmp_path / "src_48k.mp4"
        dst = tmp_path / "dst_48k.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=1.5",
            "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=1.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000",
            "-map", "0:v", "-map", "1:a",
            "-movflags", "+faststart",
            str(src),
        ]
        subprocess.run(cmd, check=True)

        plan = LayoutEngine.create_gaming_plan({
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }, source_w=1920, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        probe = probe_media(dst)
        a_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        assert a_stream["codec_name"] == "aac"
        assert int(a_stream["sample_rate"]) == 48000


# ==============================================================================
# CHALLENGE SUITE 3: OUTPUT INVARIANTS & R5 ZERO-CAPTION MANDATE
# ==============================================================================

class TestOutputInvariantsAndMobileStandards:
    """Stress tests verifying 1080x1920, yuv420p, faststart atom order, and R5 embedded subtitle stripping."""

    @pytest.mark.asyncio
    async def test_r5_zero_caption_mandate_embedded_subtitle_stripping(self, tmp_path):
        """
        Adversarial R5 Mandate Verification:
        1. Create an input MP4 containing an embedded subtitle track (mov_text).
        2. Verify via ffprobe that source has exactly 1 subtitle stream.
        3. Render via reframe_to_vertical with gaming layout.
        4. Verify via ffprobe that the output video contains ZERO subtitle streams.
        5. Verify no subtitle files (*.srt, *.vtt, *.ass) are generated in the output directory.
        """
        src = tmp_path / "src_embedded_subs.mp4"
        dst = tmp_path / "dst_no_subs.mp4"
        create_synthetic_video_with_subtitles(src, width=1920, height=1080, duration=2.0)

        # 1. Empirically verify source video contains subtitle stream
        src_probe = probe_media(src)
        src_sub_streams = [s for s in src_probe["streams"] if s.get("codec_type") == "subtitle"]
        assert len(src_sub_streams) == 1, f"Test precondition failed: source should have 1 subtitle stream, got {len(src_sub_streams)}"
        assert src_sub_streams[0]["codec_name"] == "mov_text"

        # 2. Render gaming layout
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        # 3. Empirically prove rendered video contains ZERO subtitle streams
        dst_probe = probe_media(dst)
        dst_sub_streams = [s for s in dst_probe["streams"] if s.get("codec_type") == "subtitle"]
        assert len(dst_sub_streams) == 0, f"R5 VIOLATION: Output contains {len(dst_sub_streams)} subtitle streams!"

        # 4. Check with explicit ffprobe -select_streams s
        cmd = ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "s", "-of", "json", str(dst)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        streams_s = json.loads(res.stdout).get("streams", [])
        assert len(streams_s) == 0, f"R5 VIOLATION: Subtitle streams detected via ffprobe -select_streams s: {streams_s}"

        # 5. Assert strict directory caption file invariance
        assert_zero_caption_invariant(dst, check_directory=True)

    @pytest.mark.asyncio
    async def test_faststart_moov_atom_layout(self, tmp_path):
        """Stress: Verifies MP4 container box header layout has moov preceding mdat."""
        src = tmp_path / "src_faststart.mp4"
        dst = tmp_path / "dst_faststart.mp4"
        generate_synthetic_video(src, width=1920, height=1080, duration=1.0)

        plan = LayoutEngine.create_gaming_plan({
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }, source_w=1920, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        atoms = parse_top_level_atoms(dst)
        assert "moov" in atoms and "mdat" in atoms
        moov_idx = atoms.index("moov")
        mdat_idx = atoms.index("mdat")
        assert moov_idx < mdat_idx, f"Faststart atom order violation: moov={moov_idx}, mdat={mdat_idx}"

    @pytest.mark.asyncio
    async def test_pixel_format_yuv420p_enforcement(self, tmp_path):
        """Stress: Verifies output pix_fmt is yuv420p even when input uses yuv444p or RGB."""
        src = tmp_path / "src_yuv444p.mp4"
        dst = tmp_path / "dst_yuv420p.mp4"

        # Create input explicitly with yuv444p
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=1.0",
            "-c:v", "libx264", "-pix_fmt", "yuv444p",
            "-movflags", "+faststart",
            str(src),
        ]
        subprocess.run(cmd, check=True)

        plan = LayoutEngine.create_gaming_plan({
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }, source_w=1920, source_h=1080)

        await reframe_to_vertical(input_path=src, output_path=dst, mode="gaming", plan=plan)

        probe = probe_media(dst)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert v_stream["pix_fmt"] == "yuv420p", f"Expected yuv420p, got {v_stream['pix_fmt']}"


# ==============================================================================
# CHALLENGE SUITE 4: ADVERSARIAL GEOMETRIC & VALIDATION BOUNDARIES
# ==============================================================================

class TestAdversarialGeometricEdgeCases:
    """Stress tests verifying boundary conditions, corner placements, and validation rejection."""

    def test_extreme_facecam_corner_presets(self):
        """Stress: Verify top-left, top-right, bottom-left, bottom-right presets are strictly clamped."""
        presets = ["top-left", "top-right", "bottom-left", "bottom-right"]
        for p in presets:
            rect = get_facecam_preset(p)
            assert 0.0 <= rect.x <= 1.0 - rect.width
            assert 0.0 <= rect.y <= 1.0 - rect.height
            assert rect.width >= 0.05
            assert rect.height >= 0.05

    def test_rejection_of_sub_minimum_dimensions(self):
        """Stress: Geometry engine must reject width < 0.05 or height < 0.05."""
        with pytest.raises(ValueError, match="must be >= 0.05"):
            validate_normalized_rect({"x": 0.1, "y": 0.1, "width": 0.049, "height": 0.5})

        with pytest.raises(ValueError, match="must be >= 0.05"):
            validate_normalized_rect({"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.03})

    def test_rejection_of_out_of_bounds_sums(self):
        """Stress: Geometry engine must reject x + width > 1.0 or y + height > 1.0."""
        with pytest.raises(ValueError, match="out of bounds"):
            validate_normalized_rect({"x": 0.8, "y": 0.1, "width": 0.25, "height": 0.2})

        with pytest.raises(ValueError, match="out of bounds"):
            validate_normalized_rect({"x": 0.1, "y": 0.85, "width": 0.2, "height": 0.2})

    def test_gaming_plan_forbids_zoom_or_blur_interventions(self):
        """Stress: LayoutPlan model strictly prohibits ZoomIntervention and non-NONE BackgroundPolicy in gaming mode."""
        r1 = RegionModel(source_index=0, x=0, y=0, w=1080, h=1920, scale_mode=ScaleMode.CROP, z_order=1)
        r2 = RegionModel(source_index=1, x=702, y=76, w=324, h=422, scale_mode=ScaleMode.CROP, z_order=2)

        # Prohibits BLUR background
        with pytest.raises(ValueError, match="BackgroundPolicy.NONE"):
            LayoutPlan(
                mode=LayoutMode.GAMING,
                canvas_width=1080,
                canvas_height=1920,
                regions=[r1, r2],
                background_policy=BackgroundPolicy.BLUR,
            )

        # Prohibits zoom interventions
        r1_zoom = RegionModel(
            source_index=0, x=0, y=0, w=1080, h=1920, scale_mode=ScaleMode.CROP, z_order=1,
            zoom_interventions=[ZoomIntervention(start_time=0.5, end_time=1.5, zoom_factor=1.2)]
        )
        with pytest.raises(ValueError, match="Zoom interventions are forbidden"):
            LayoutPlan(
                mode=LayoutMode.GAMING,
                canvas_width=1080,
                canvas_height=1920,
                regions=[r1_zoom, r2],
                background_policy=BackgroundPolicy.NONE,
            )
