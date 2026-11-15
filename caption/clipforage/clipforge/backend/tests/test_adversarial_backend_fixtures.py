"""
clipforge/backend/tests/test_adversarial_backend_fixtures.py
===========================================================
Adversarial Challenge & Stress Test Suite for Backend Test Infrastructure:
- backend/tests/gaming_test_fixtures.py
- docs/engineering/gaming_geometry_golden_vectors.json
- backend/services/gaming_geometry.py

Probes edge cases, stress vectors, and boundary limits:
1. Extreme dimensions (8K 7680x4320, 128x128, odd 1001x777, tiny spans) against geometry & FFmpeg filters.
2. Corrupted, truncated, and malformed MP4 files against atom parsing and faststart verification.
3. Synthetic fixture generation under non-existent directories and invalid parameters.
4. R5 zero-caption invariant verification with actual subtitle streams embedded in MP4.
"""

import json
import os
import shutil
import struct
import subprocess
from pathlib import Path
import pytest

from backend.tests.gaming_test_fixtures import (
    generate_synthetic_video,
    create_synthetic_1080p_gameplay,
    create_synthetic_4k_ultrawide,
    create_synthetic_odd_dimension,
    create_synthetic_portrait,
    probe_media,
    parse_top_level_atoms,
    assert_faststart_moov_atom,
    assert_zero_caption_invariant,
    assert_filtergraph_zero_caption_invariant,
    assert_gaming_video_invariants,
)
from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    create_gaming_layout_plan,
    get_facecam_preset,
    to_canvas_overlay,
    to_even_pixel,
    to_even_span,
    to_gameplay_canvas_framing,
    to_source_crop,
    validate_gaming_layout,
    validate_normalized_rect,
    PixelRect,
    NormalizedRect,
)


# ==============================================================================
# SECTION 1: EXTREME DIMENSIONS & CODEC ALIGNMENT STRESS TESTS
# ==============================================================================

class TestExtremeDimensionsAndGeometryStress:
    """Stress-tests geometry calculations and FFmpeg filter handling under extreme resolutions."""

    @pytest.mark.parametrize("width,height", [
        (7680, 4320),   # 8K UHD 16:9
        (128, 128),     # Tiny square
        (1001, 777),    # Asymmetric odd dimensions
        (5120, 1440),   # 32:9 Super Ultrawide
        (720, 1280),    # 9:16 Vertical SD
        (1919, 1079),   # 1080p minus 1
        (1921, 1081),   # 1080p plus 1
    ])
    def test_to_source_crop_extreme_dimensions_even_parity(self, width, height):
        """Verifies that to_source_crop always yields even coordinates and strictly bounded dimensions."""
        norm_roi = {"x": 0.1, "y": 0.15, "width": 0.7, "height": 0.65}
        crop = to_source_crop(norm_roi, width, height)

        assert crop.x % 2 == 0, f"Crop x ({crop.x}) not even for {width}x{height}"
        assert crop.y % 2 == 0, f"Crop y ({crop.y}) not even for {width}x{height}"
        assert crop.w % 2 == 0, f"Crop w ({crop.w}) not even for {width}x{height}"
        assert crop.h % 2 == 0, f"Crop h ({crop.h}) not even for {width}x{height}"

        # Bounds check
        even_max_w = (width // 2) * 2
        even_max_h = (height // 2) * 2
        assert crop.x + crop.w <= even_max_w, f"Crop exceeds max width for {width}x{height}"
        assert crop.y + crop.h <= even_max_h, f"Crop exceeds max height for {width}x{height}"

    def test_8k_full_plan_and_filtergraph(self):
        """Verifies complete gaming plan generation for 8K (7680x4320) source video."""
        config = {
            "gameplay_roi": {"x": 0.05, "y": 0.05, "width": 0.90, "height": 0.90},
            "facecam_roi": {"x": 0.75, "y": 0.05, "width": 0.20, "height": 0.20},
            "facecam_placement": "top-right",
            "src_w": 7680,
            "src_h": 4320,
        }
        plan = calculate_gaming_coordinates(config)
        assert plan.gameplay_crop.w % 2 == 0
        assert plan.gameplay_crop.h % 2 == 0
        assert plan.facecam_crop.w % 2 == 0
        assert plan.facecam_crop.h % 2 == 0
        assert plan.facecam_dest.w % 2 == 0
        assert plan.facecam_dest.h % 2 == 0

        # Check FFmpeg filter strings format
        assert "crop=" in plan.ffmpeg_gameplay_crop
        assert "crop=" in plan.ffmpeg_facecam_crop
        assert "scale=" in plan.ffmpeg_facecam_scale
        assert "overlay=" in plan.ffmpeg_overlay

    def test_odd_resolution_1001x777_synthetic_generation(self, tmp_path):
        """Tests that generate_synthetic_video safely generates odd 1001x777 video using yuv444p fallback."""
        out_file = tmp_path / "odd_1001x777.mp4"
        created = generate_synthetic_video(
            output_path=out_file,
            width=1001,
            height=777,
            duration=1.0,
            fps=25,
            video_color="testsrc",
        )
        assert created.exists()
        assert created.stat().st_size > 0

        probe = probe_media(created)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert v_stream["width"] == 1001
        assert v_stream["height"] == 777
        # yuv444p should be selected for odd dimension to prevent libx264 chroma subsampling failure
        assert v_stream["pix_fmt"] == "yuv444p"

    def test_tiny_resolution_128x128_synthetic_generation(self, tmp_path):
        """Tests that generate_synthetic_video handles tiny 128x128 dimensions without crashing."""
        out_file = tmp_path / "tiny_128x128.mp4"
        created = generate_synthetic_video(
            output_path=out_file,
            width=128,
            height=128,
            duration=1.0,
            fps=25,
            video_color="blue",
        )
        assert created.exists()
        probe = probe_media(created)
        v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert v_stream["width"] == 128
        assert v_stream["height"] == 128
        assert v_stream["pix_fmt"] == "yuv420p"

    def test_boundary_limits_zero_or_negative_dimensions_raise_value_error(self):
        """Tests that passing zero or negative dimensions to to_source_crop raises ValueError."""
        with pytest.raises(ValueError, match="Source dimensions must be positive"):
            to_source_crop({"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, 0, 1080)

        with pytest.raises(ValueError, match="Source dimensions must be positive"):
            to_source_crop({"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, 1920, -100)


# ==============================================================================
# SECTION 2: CORRUPTED, TRUNCATED, AND MALFORMED MP4 ATOM PARSING TESTS
# ==============================================================================

class TestCorruptedAndTruncatedMp4Atoms:
    """Stress-tests atom parsing and faststart moov assertion against corrupted binary payloads."""

    def test_empty_file_atom_parsing(self, tmp_path):
        empty_file = tmp_path / "empty.mp4"
        empty_file.write_bytes(b"")

        atoms = parse_top_level_atoms(empty_file)
        assert atoms == []

        with pytest.raises(AssertionError, match="Missing 'moov' atom"):
            assert_faststart_moov_atom(empty_file)

    def test_truncated_header_less_than_8_bytes(self, tmp_path):
        for num_bytes in [1, 2, 4, 7]:
            trunc_file = tmp_path / f"trunc_{num_bytes}.mp4"
            trunc_file.write_bytes(b"\x00" * num_bytes)

            atoms = parse_top_level_atoms(trunc_file)
            assert atoms == []

            with pytest.raises(AssertionError, match="Missing 'moov' atom"):
                assert_faststart_moov_atom(trunc_file)

    def test_valid_ftyp_but_truncated_moov(self, tmp_path):
        """File has valid ftyp box but cuts off before moov or mdat."""
        trunc_file = tmp_path / "ftyp_only.mp4"
        # 8-byte ftyp header + 8 bytes payload
        trunc_file.write_bytes(
            struct.pack(">I4s", 16, b"ftyp") + b"isom\x00\x00\x02\x00"
        )
        atoms = parse_top_level_atoms(trunc_file)
        assert atoms == ["ftyp"]

        with pytest.raises(AssertionError, match="Missing 'moov' atom"):
            assert_faststart_moov_atom(trunc_file)

    def test_moov_present_but_mdat_missing(self, tmp_path):
        """File has ftyp and moov, but mdat is missing."""
        f = tmp_path / "missing_mdat.mp4"
        data = (
            struct.pack(">I4s", 16, b"ftyp") + b"isom\x00\x00\x02\x00" +
            struct.pack(">I4s", 8, b"moov")
        )
        f.write_bytes(data)
        atoms = parse_top_level_atoms(f)
        assert atoms == ["ftyp", "moov"]

        with pytest.raises(AssertionError, match="Missing 'mdat' atom"):
            assert_faststart_moov_atom(f)

    def test_mdat_before_moov_fails_faststart(self, tmp_path):
        """File has mdat before moov (non-faststart MP4 violation)."""
        f = tmp_path / "mdat_first.mp4"
        data = (
            struct.pack(">I4s", 16, b"ftyp") + b"isom\x00\x00\x02\x00" +
            struct.pack(">I4s", 20, b"mdat") + (b"\x00" * 12) +
            struct.pack(">I4s", 8, b"moov")
        )
        f.write_bytes(data)
        atoms = parse_top_level_atoms(f)
        assert atoms == ["ftyp", "mdat", "moov"]

        with pytest.raises(AssertionError, match="Faststart violation"):
            assert_faststart_moov_atom(f)

    def test_extended_64bit_size_box_parsing(self, tmp_path):
        """Verifies handling of 64-bit extended box size (size == 1)."""
        f = tmp_path / "extended_size.mp4"
        # Box header with size=1, type=moov, ext_size=24 (8 header + 8 ext_size + 8 payload)
        data = (
            struct.pack(">I4s", 1, b"moov") + struct.pack(">Q", 24) + (b"\x00" * 8) +
            struct.pack(">I4s", 8, b"mdat")
        )
        f.write_bytes(data)
        atoms = parse_top_level_atoms(f)
        assert atoms == ["moov", "mdat"]
        assert_faststart_moov_atom(f)

    def test_box_size_zero_extends_to_eof(self, tmp_path):
        """Verifies handling of size == 0 (box extends to EOF)."""
        f = tmp_path / "size_zero.mp4"
        data = (
            struct.pack(">I4s", 16, b"ftyp") + b"isom\x00\x00\x02\x00" +
            struct.pack(">I4s", 0, b"mdat") + (b"\xaa" * 100)
        )
        f.write_bytes(data)
        atoms = parse_top_level_atoms(f)
        assert atoms == ["ftyp", "mdat"]

        with pytest.raises(AssertionError, match="Missing 'moov' atom"):
            assert_faststart_moov_atom(f)

    def test_random_garbage_binary_does_not_crash_interpreter(self, tmp_path):
        """Verifies that completely invalid random bytes do not cause a crash or segfault."""
        garbage_file = tmp_path / "garbage.mp4"
        # Random binary bytes
        garbage_file.write_bytes(b"\xff\xfe\xfd\xfc\x01\x02\x03\x04\x88\x99\xaa\xbb\xcc\xdd\xee\xff" * 10)

        # Must return atoms without crashing
        atoms = parse_top_level_atoms(garbage_file)
        assert isinstance(atoms, list)
        with pytest.raises(AssertionError):
            assert_faststart_moov_atom(garbage_file)


# ==============================================================================
# SECTION 3: SYNTHETIC FIXTURE GENERATION ROBUSTNESS
# ==============================================================================

class TestSyntheticFixtureGenerationRobustness:
    """Stress-tests synthetic video generator under environmental conditions."""

    def test_auto_creates_deeply_nested_non_existent_directory(self, tmp_path):
        """Verifies that generate_synthetic_video automatically creates non-existent parent dirs."""
        deep_dir = tmp_path / "deep" / "nested" / "path" / "subfolder"
        assert not deep_dir.exists()

        target_file = deep_dir / "synthetic_nested.mp4"
        created = generate_synthetic_video(
            output_path=target_file,
            width=320,
            height=240,
            duration=1.0,
            fps=25,
        )
        assert created.exists()
        assert deep_dir.exists()
        assert created.stat().st_size > 0

    def test_invalid_color_raises_runtime_error(self, tmp_path):
        """Verifies that an invalid FFmpeg filter parameter raises RuntimeError with stderr info."""
        target_file = tmp_path / "invalid_color.mp4"
        with pytest.raises(RuntimeError) as exc_info:
            generate_synthetic_video(
                output_path=target_file,
                width=320,
                height=240,
                duration=1.0,
                fps=25,
                video_color="non_existent_color_name_xyz_123",
            )
        assert "FFmpeg synthetic video generation failed" in str(exc_info.value)


# ==============================================================================
# SECTION 4: R5 ZERO-CAPTION INVARIANT WITH ACTUAL EMBEDDED SUBTITLES
# ==============================================================================

class TestR5ZeroCaptionWithEmbeddedSubtitles:
    """
    Critical adversarial probe:
    Creates an actual MP4 video file containing an embedded subtitle stream (mov_text)
    and verifies that probe_media, assert_zero_caption_invariant, and
    assert_gaming_video_invariants RELIABLY fail and report the violation.
    """

    @pytest.fixture
    def mp4_with_mov_text_subtitles(self, tmp_path) -> Path:
        """Generates an MP4 containing video, audio, AND a mov_text subtitle stream."""
        sub_file = tmp_path / "input_subtitles.srt"
        sub_file.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n[Cheering]\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\nVictory Royale!\n",
            encoding="utf-8"
        )

        out_file = tmp_path / "video_with_subtitles.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-i", str(sub_file),
            "-map", "0:v", "-map", "1:a", "-map", "2:s",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-c:s", "mov_text",
            "-movflags", "+faststart",
            str(out_file)
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"FFmpeg failed to create test subtitle video: {proc.stderr}"
        assert out_file.exists()

        # Sanity check via ffprobe directly
        probe = probe_media(out_file)
        subtitle_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "subtitle"]
        assert len(subtitle_streams) >= 1, "Fixture failed to embed subtitle stream!"

        # Remove the srt file so the directory check doesn't trigger before the stream check
        sub_file.unlink()
        return out_file

    def test_probe_media_detects_subtitle_stream(self, mp4_with_mov_text_subtitles):
        """Verifies that probe_media extracts the subtitle stream metadata."""
        probe = probe_media(mp4_with_mov_text_subtitles)
        streams = probe["streams"]
        sub_stream = next((s for s in streams if s["codec_type"] == "subtitle"), None)
        assert sub_stream is not None
        assert sub_stream["codec_name"] == "mov_text"

    def test_assert_zero_caption_invariant_fails_on_embedded_subtitles(self, mp4_with_mov_text_subtitles):
        """
        Verifies that assert_zero_caption_invariant raises AssertionError
        specifically citing the subtitle stream (even when no srt files exist in dir).
        """
        with pytest.raises(AssertionError) as exc_info:
            assert_zero_caption_invariant(mp4_with_mov_text_subtitles, check_directory=False)

        error_msg = str(exc_info.value)
        assert "R5 Violation" in error_msg
        assert "subtitle stream(s)" in error_msg
        assert "mov_text" in error_msg

    def test_assert_gaming_video_invariants_fails_on_embedded_subtitles(self, mp4_with_mov_text_subtitles):
        """Verifies that the high-level assert_gaming_video_invariants catches embedded subtitles."""
        with pytest.raises(AssertionError) as exc_info:
            assert_gaming_video_invariants(
                mp4_with_mov_text_subtitles,
                expected_width=320,
                expected_height=240,
                check_faststart=True,
                check_zero_captions=True,
            )
        assert "R5 Violation" in str(exc_info.value)
        assert "subtitle stream" in str(exc_info.value)


# ==============================================================================
# SECTION 5: OPAQUE-BOX INVARIANT NEGATIVE BOUNDARY CHECKS
# ==============================================================================

class TestOpaqueBoxInvariantsNegativeBoundaries:
    """Probes negative paths and boundary rejection in assert_gaming_video_invariants."""

    def test_missing_audio_stream_raises_assertion_error(self, tmp_path):
        """Video generated without audio (audio_freq=None) fails when expected_audio_codec is set."""
        no_audio_file = tmp_path / "no_audio.mp4"
        generate_synthetic_video(
            output_path=no_audio_file,
            width=320,
            height=240,
            duration=1.0,
            fps=25,
            audio_freq=None,
        )
        with pytest.raises(AssertionError, match="Expected at least 1 audio stream, found 0"):
            assert_gaming_video_invariants(
                no_audio_file,
                expected_width=320,
                expected_height=240,
                expected_audio_codec="aac",
            )

        # But succeeds when expected_audio_codec=None
        res = assert_gaming_video_invariants(
            no_audio_file,
            expected_width=320,
            expected_height=240,
            expected_audio_codec=None,
        )
        assert res["audio_codec"] is None

    def test_dimension_mismatch_raises_assertion_error(self, tmp_path):
        """Mismatch in expected width or height triggers clear assertion error."""
        vfile = tmp_path / "dim_test.mp4"
        generate_synthetic_video(output_path=vfile, width=640, height=360, duration=1.0)

        with pytest.raises(AssertionError, match="Width mismatch: expected 1080, got 640"):
            assert_gaming_video_invariants(vfile, expected_width=1080, expected_height=360)

        with pytest.raises(AssertionError, match="Height mismatch: expected 1920, got 360"):
            assert_gaming_video_invariants(vfile, expected_width=640, expected_height=1920)

    def test_duration_mismatch_raises_assertion_error(self, tmp_path):
        """Duration outside tolerance triggers assertion error."""
        vfile = tmp_path / "dur_test.mp4"
        generate_synthetic_video(output_path=vfile, width=320, height=240, duration=2.0)

        with pytest.raises(AssertionError, match="Duration mismatch"):
            assert_gaming_video_invariants(
                vfile,
                expected_width=320,
                expected_height=240,
                expected_duration=5.0,
                duration_tolerance=0.5,
            )

    def test_odd_dimension_codec_violation_in_invariants(self, tmp_path):
        """Odd dimension video fails the even-pixel invariant in assert_gaming_video_invariants."""
        odd_file = tmp_path / "odd_1001x777_inv.mp4"
        generate_synthetic_video(output_path=odd_file, width=1001, height=777, duration=1.0)

        with pytest.raises(AssertionError, match="must be even"):
            assert_gaming_video_invariants(
                odd_file,
                expected_width=1001,
                expected_height=777,
                expected_pix_fmt="yuv444p",
            )

    def test_filtergraph_case_insensitivity_and_variants(self):
        """Verifies assert_filtergraph_zero_caption_invariant catches uppercase and mixed case filters."""
        for bad_filter in ["DRAWTEXT=text='hi'", "Subtitles=subs.srt", "ASS=subs.ass"]:
            graph = f"[0:v]crop=100:100:0:0[v0];[v0]{bad_filter}[outv]"
            with pytest.raises(AssertionError, match="R5 Violation"):
                assert_filtergraph_zero_caption_invariant(graph)

