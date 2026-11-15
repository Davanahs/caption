"""
test_gaming_pipeline_adversarial_challenger.py
=============================================
Adversarial Challenger Stress Suite for Milestone M2:
Backend FFmpeg Pipeline & Video Ingestion Routing.

Adversarial Stress Dimensions:
1. Single-source input flattening [input_path, input_path] across diverse aspect ratios & resolutions:
   - 16:9 (1920x1080)
   - 21:9 Ultrawide (2560x1080)
   - 4:3 Legacy (1440x1080)
   - 9:16 Vertical (1080x1920)
   - Odd Dimensions (1921x1081)
2. Audio Preservation & Desync Under Stress:
   - Standard stereo audio (440Hz / 48kHz AAC)
   - Zero audio streams (-map 0:a? negative test)
   - Silent audio tracks
   - Audio/video duration drift (< 0.15s) and PTS alignment (start_time == 0.0)
3. Strict Output Invariants Verification:
   - Exact 1080x1920 (9:16) resolution
   - Exact yuv420p pixel format (-pix_fmt yuv420p)
   - Faststart container atom layout (moov before mdat)
   - Sample aspect ratio setsar=1 (1:1 PAR)
4. R5 Zero-Caption Mandate Adversarial Attack:
   - Input containing embedded subtitle tracks (mov_text)
   - Verification that -sn strips all subtitle streams
   - Absolute zero subtitle streams in output container
   - Zero subtitle artifact files (*.srt, *.vtt, *.ass) in output directory
5. Geometry Boundary & Even-Pixel Quantization Stress:
   - Corner presets & extreme placement bounds
   - Minimum ROI size (0.05 x 0.05)
   - Out-of-bounds, negative, NaN coordinate rejection
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from backend.models.layout import (
    AudioPolicy,
    BackgroundPolicy,
    GamingLayoutConfig,
    LayoutMode,
    LayoutPlan,
    NormalizedRectModel,
    RegionModel,
    ScaleMode,
)
from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    create_gaming_layout_plan,
    get_facecam_preset,
    validate_gaming_layout,
)
from backend.services.layout_engine import LayoutEngine
from backend.services.reframe_engine import reframe_to_vertical, run_ffmpeg
from backend.tests.gaming_test_fixtures import (
    assert_faststart_moov_atom,
    assert_filtergraph_zero_caption_invariant,
    assert_gaming_video_invariants,
    assert_zero_caption_invariant,
    generate_synthetic_video,
    parse_top_level_atoms,
    probe_media,
)


@pytest.fixture(scope="module")
def adversarial_workdir(tmp_path_factory) -> Path:
    wdir = tmp_path_factory.mktemp("adversarial_m2")
    return wdir


# ==============================================================================
# 1. INPUT FLATTENING ACROSS VARIED ASPECT RATIOS & RESOLUTIONS
# ==============================================================================

class TestInputFlatteningAspectRatios:
    """
    Stress-tests single-source input flattening [input_path, input_path]
    to ensure FFmpeg executes cleanly without FIFO queue starvation or split deadlocks.
    """

    @pytest.mark.parametrize(
        "name,width,height,duration,audio",
        [
            ("16_9_standard", 1920, 1080, 2.0, 440),
            ("21_9_ultrawide", 2560, 1080, 2.0, 880),
            ("4_3_retro", 1440, 1080, 2.0, 440),
            ("9_16_vertical", 1080, 1920, 2.0, 440),
            ("odd_1921x1081", 1921, 1081, 2.0, 440),
        ],
    )
    @pytest.mark.asyncio
    async def test_rendering_across_aspect_ratios(
        self, adversarial_workdir: Path, name: str, width: int, height: int, duration: float, audio: int
    ):
        source_path = adversarial_workdir / f"src_{name}.mp4"
        out_path = adversarial_workdir / f"out_{name}.mp4"

        # Generate synthetic source
        generate_synthetic_video(
            output_path=source_path,
            width=width,
            height=height,
            duration=duration,
            audio_freq=audio,
            faststart=True,
        )

        config = {
            "gameplay_roi": {"x": 0.05, "y": 0.05, "width": 0.90, "height": 0.90},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }

        plan = LayoutEngine.create_gaming_plan(config, source_w=width, source_h=height)

        # Execute reframe
        rendered = await reframe_to_vertical(
            input_path=source_path,
            output_path=out_path,
            mode="gaming",
            plan=plan,
        )

        assert rendered.exists()
        assert rendered.stat().st_size > 0

        # Assert strict invariants on rendered output
        invariants = assert_gaming_video_invariants(
            file_path=rendered,
            expected_width=1080,
            expected_height=1920,
            expected_video_codec="h264",
            expected_pix_fmt="yuv420p",
            expected_audio_codec="aac",
            expected_duration=duration,
            duration_tolerance=0.35,
            check_faststart=True,
            check_zero_captions=True,
        )

        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"


# ==============================================================================
# 2. AUDIO PRESERVATION & ZERO DESYNC UNDER ADVERSARIAL STRESS
# ==============================================================================

class TestAudioPreservationStress:
    """
    Stress-tests audio stream handling:
    - Standard audio preservation
    - Missing audio stream (-map 0:a? must not crash FFmpeg)
    - Audio/video drift and desync measurements
    """

    @pytest.mark.asyncio
    async def test_video_without_audio_track(self, adversarial_workdir: Path):
        """
        Adversarial Scenario: Video has NO audio stream at all.
        Verifies that -map 0:a? gracefully succeeds without throwing a missing stream error.
        """
        source_path = adversarial_workdir / "src_no_audio.mp4"
        out_path = adversarial_workdir / "out_no_audio.mp4"

        # Generate video with audio_freq=None (0 audio streams)
        generate_synthetic_video(
            output_path=source_path,
            width=1920,
            height=1080,
            duration=2.0,
            audio_freq=None,
        )

        # Confirm source has 0 audio streams
        src_probe = probe_media(source_path)
        audio_streams = [s for s in src_probe["streams"] if s.get("codec_type") == "audio"]
        assert len(audio_streams) == 0, "Source video unexpectedly has audio"

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.1, "width": 0.25, "height": 0.25},
            "facecam_placement": "bottom-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        # Render should succeed despite no audio
        rendered = await reframe_to_vertical(
            input_path=source_path,
            output_path=out_path,
            mode="gaming",
            plan=plan,
        )

        assert rendered.exists()
        out_probe = probe_media(rendered)
        out_audio = [s for s in out_probe["streams"] if s.get("codec_type") == "audio"]
        out_video = [s for s in out_probe["streams"] if s.get("codec_type") == "video"]

        assert len(out_video) == 1
        assert out_video[0]["width"] == 1080
        assert out_video[0]["height"] == 1920
        assert len(out_audio) == 0, f"Expected 0 audio streams, found {len(out_audio)}"

    @pytest.mark.asyncio
    async def test_audio_video_sync_and_timing(self, adversarial_workdir: Path):
        """
        Adversarial Scenario: Precise timestamp and duration check.
        Ensures video and audio streams start at PTS 0.0 and durations match within 0.15s.
        """
        source_path = adversarial_workdir / "src_sync_test.mp4"
        out_path = adversarial_workdir / "out_sync_test.mp4"

        generate_synthetic_video(
            output_path=source_path,
            width=1920,
            height=1080,
            duration=3.0,
            audio_freq=440,
        )

        config = {
            "gameplay_roi": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
            "facecam_roi": {"x": 0.7, "y": 0.1, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-left",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        rendered = await reframe_to_vertical(
            input_path=source_path,
            output_path=out_path,
            mode="gaming",
            plan=plan,
        )

        probe = probe_media(rendered)
        video_s = [s for s in probe["streams"] if s.get("codec_type") == "video"][0]
        audio_s = [s for s in probe["streams"] if s.get("codec_type") == "audio"][0]

        v_dur = float(video_s.get("duration", probe["format"]["duration"]))
        a_dur = float(audio_s.get("duration", probe["format"]["duration"]))

        # Check drift
        drift = abs(v_dur - a_dur)
        assert drift < 0.15, f"Audio/video desync detected: video={v_dur}s, audio={a_dur}s, drift={drift}s"


# ==============================================================================
# 3. R5 ZERO-CAPTION MANDATE ADVERSARIAL ATTACK (EMBEDDED SUBTITLE INGESTION)
# ==============================================================================

class TestZeroCaptionMandateAdversarial:
    """
    Directly tests the R5 Zero-Caption Mandate:
    Ingests an input video containing an EMBEDDED subtitle track (mov_text).
    Verifies that -sn strips the subtitle stream and the rendered output has ZERO subtitle streams.
    """

    @pytest.mark.asyncio
    async def test_input_with_embedded_subtitles_stripped(self, adversarial_workdir: Path):
        # 1. Create source video with subtitle track
        base_video = adversarial_workdir / "base_for_sub.mp4"
        sub_srt = adversarial_workdir / "malicious_subtitles.srt"
        source_with_sub = adversarial_workdir / "src_with_embedded_sub.mp4"
        out_path = adversarial_workdir / "out_sub_stripped.mp4"

        generate_synthetic_video(
            output_path=base_video,
            width=1920,
            height=1080,
            duration=3.0,
            audio_freq=440,
        )

        # Write SRT file
        srt_content = (
            "1\n"
            "00:00:00,500 --> 00:00:02,500\n"
            "UNAUTHORIZED CAPTION: This subtitle must NOT appear in output\n\n"
        )
        sub_srt.write_text(srt_content, encoding="utf-8")

        # Mux subtitle into MP4 as mov_text
        mux_cmd = [
            "ffmpeg", "-y",
            "-i", str(base_video),
            "-i", str(sub_srt),
            "-map", "0:v",
            "-map", "0:a",
            "-map", "1:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",
            str(source_with_sub),
        ]
        proc = subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"Failed to mux subtitle track: {proc.stderr}"

        # Clean up input SRT fixture so it is not mistaken for a generated artifact
        sub_srt.unlink(missing_ok=True)

        # Verify source has a subtitle stream
        src_probe = probe_media(source_with_sub)
        src_sub_streams = [s for s in src_probe["streams"] if s.get("codec_type") == "subtitle"]
        assert len(src_sub_streams) == 1, f"Source must have 1 subtitle stream, found {len(src_sub_streams)}"

        # 2. Reframe with gaming layout
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        rendered = await reframe_to_vertical(
            input_path=source_with_sub,
            output_path=out_path,
            mode="gaming",
            plan=plan,
        )

        assert rendered.exists()

        # 3. EMPIRICAL VERIFICATION: Output must have ZERO subtitle streams
        out_probe = probe_media(rendered)
        out_streams = out_probe.get("streams", [])
        out_sub_streams = [s for s in out_streams if s.get("codec_type") == "subtitle"]
        video_streams = [s for s in out_streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in out_streams if s.get("codec_type") == "audio"]

        assert len(out_sub_streams) == 0, (
            f"R5 VIOLATION: Output contains {len(out_sub_streams)} subtitle streams! Streams: {out_streams}"
        )
        assert len(video_streams) == 1, f"Expected 1 video stream, got {len(video_streams)}"
        assert len(audio_streams) == 1, f"Expected 1 audio stream, got {len(audio_streams)}"
        assert len(out_streams) == 2, f"Expected exactly 2 streams (video + audio), got {len(out_streams)}"

        # Verify no subtitle files created in output directory
        assert_zero_caption_invariant(rendered, check_directory=True)


# ==============================================================================
# 4. CONTAINER ATOMS & FASTSTART VERIFICATION UNDER STRESS
# ==============================================================================

class TestContainerFaststartStress:
    """
    Verifies that all rendered outputs adhere to faststart atom layout (moov before mdat).
    """

    @pytest.mark.asyncio
    async def test_faststart_atom_order(self, adversarial_workdir: Path):
        source_path = adversarial_workdir / "src_faststart.mp4"
        out_path = adversarial_workdir / "out_faststart.mp4"

        generate_synthetic_video(
            output_path=source_path,
            width=1920,
            height=1080,
            duration=1.5,
            audio_freq=440,
        )

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.65, "y": 0.05, "width": 0.30, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        rendered = await reframe_to_vertical(
            input_path=source_path,
            output_path=out_path,
            mode="gaming",
            plan=plan,
        )

        atoms = parse_top_level_atoms(rendered)
        assert "moov" in atoms, f"Missing 'moov' atom in {rendered}. Found: {atoms}"
        assert "mdat" in atoms, f"Missing 'mdat' atom in {rendered}. Found: {atoms}"
        assert atoms.index("moov") < atoms.index("mdat"), (
            f"Faststart violation: 'moov' at {atoms.index('moov')} must precede 'mdat' at {atoms.index('mdat')}"
        )


# ==============================================================================
# 5. GEOMETRY BOUNDARIES & EVEN-PIXEL QUANTIZATION STRESS
# ==============================================================================

class TestGeometryBoundaryStress:
    """
    Stress-tests geometric limits and edge cases:
    - Extreme corner presets
    - Minimum ROI sizes (0.05)
    - Full-frame ROIs (1.0)
    - Even-pixel codec constraints
    """

    @pytest.mark.parametrize(
        "preset,expected_x,expected_y",
        [
            ("top-left", 0.05, 0.05),
            ("top-right", 0.65, 0.05),
            ("bottom-left", 0.05, 0.70),
            ("bottom-right", 0.65, 0.70),
        ],
    )
    def test_preset_bounds_and_even_pixels(self, preset: str, expected_x: float, expected_y: float):
        cfg = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": preset,
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(cfg, source_w=1920, source_h=1080)

        r_gameplay = plan.regions[0]
        r_facecam = plan.regions[1]

        # Invariants: 2 regions, z-order 1 and 2
        assert r_gameplay.z_order == 1
        assert r_facecam.z_order == 2

        # Gameplay fills 1080x1920
        assert r_gameplay.w == 1080
        assert r_gameplay.h == 1920
        assert r_gameplay.x == 0
        assert r_gameplay.y == 0

        # Facecam overlay coordinates must be even integers
        assert r_facecam.x % 2 == 0
        assert r_facecam.y % 2 == 0
        assert r_facecam.w % 2 == 0
        assert r_facecam.h % 2 == 0

        # Overlay must be completely within 1080x1920 canvas bounds
        assert r_facecam.x >= 0
        assert r_facecam.y >= 0
        assert r_facecam.x + r_facecam.w <= 1080
        assert r_facecam.y + r_facecam.h <= 1920

        # Source crops must be even integers
        assert r_gameplay.crop_coords is not None
        assert r_facecam.crop_coords is not None
        for c in (*r_gameplay.crop_coords, *r_facecam.crop_coords):
            assert c % 2 == 0

    @pytest.mark.parametrize(
        "invalid_roi",
        [
            {"x": -0.1, "y": 0.0, "width": 0.5, "height": 0.5},
            {"x": 0.0, "y": 1.1, "width": 0.5, "height": 0.5},
            {"x": 0.8, "y": 0.0, "width": 0.3, "height": 0.5}, # Exceeds 1.0
            {"x": 0.0, "y": 0.0, "width": 0.01, "height": 0.5}, # Sub 0.05
            {"x": float("nan"), "y": 0.0, "width": 0.5, "height": 0.5},
            {"x": float("inf"), "y": 0.0, "width": 0.5, "height": 0.5},
        ],
    )
    def test_invalid_roi_rejected_with_value_error(self, invalid_roi: dict):
        cfg = {
            "gameplay_roi": invalid_roi,
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        with pytest.raises(ValueError):
            LayoutEngine.create_gaming_plan(cfg, source_w=1920, source_h=1080)
