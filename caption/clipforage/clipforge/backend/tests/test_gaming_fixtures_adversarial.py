"""
test_gaming_fixtures_adversarial.py
===================================
Adversarial stress-test suite for Milestone T1 test infrastructure:
- backend/tests/gaming_test_fixtures.py

Empirically challenges:
1. Synthetic video generation across boundary and extreme dimensions (21:9, 32:9, odd dims, tiny dims, zero audio, invalid dims).
2. ISO Base Media File Format atom parser against non-faststart MP4s, truncated headers, corrupt/zero-byte files, and extended size boxes.
3. Strict R5 Zero-Caption Mandate enforcement against embedded subtitle streams (mov_text), disk subtitle files (.srt, .vtt, .ass, uppercase, nested dirs), and prohibited filtergraph tokens.
4. Opaque-box media assertion boundary failures (wrong resolution, wrong pix_fmt, missing audio, duration drift).
"""

import json
import os
import struct
import subprocess
import tempfile
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


class TestAdversarialSyntheticVideoGeneration:
    """Stress tests for FFmpeg lavfi synthetic video generation."""

    def test_ultrawide_21_9_and_32_9_resolutions(self, tmp_path):
        """Tests that ultra-wide resolutions generate valid faststart MP4s."""
        resolutions = [
            (2560, 1080, "21_9_1080p"),
            (3440, 1440, "21_9_1440p"),
            (3840, 1080, "32_9_superwide"),
        ]
        for w, h, name in resolutions:
            out_file = tmp_path / f"test_{name}.mp4"
            generate_synthetic_video(out_file, width=w, height=h, duration=0.5, fps=24, faststart=True)
            assert out_file.exists()
            assert out_file.stat().st_size > 0

            probe = probe_media(out_file)
            v = next(s for s in probe["streams"] if s["codec_type"] == "video")
            assert v["width"] == w
            assert v["height"] == h
            assert v["codec_name"] == "h264"
            assert v["pix_fmt"] == "yuv420p"

            # Assert faststart
            atoms = assert_faststart_moov_atom(out_file)
            assert atoms.index("moov") < atoms.index("mdat")

    def test_multiple_odd_dimension_boundary_cases(self, tmp_path):
        """Tests odd dimensions automatically switch to yuv444p without encoding failure."""
        odd_resolutions = [
            (1919, 1079),  # -1 px from 1080p
            (1921, 1081),  # +1 px from 1080p
            (1281, 721),   # +1 px from 720p
            (853, 481),    # odd 480p
        ]
        for w, h in odd_resolutions:
            out_file = tmp_path / f"test_odd_{w}x{h}.mp4"
            generate_synthetic_video(out_file, width=w, height=h, duration=0.5, fps=25, faststart=True)
            assert out_file.exists()

            probe = probe_media(out_file)
            v = next(s for s in probe["streams"] if s["codec_type"] == "video")
            assert v["width"] == w
            assert v["height"] == h
            # For odd dimensions, generator must safely select yuv444p
            assert v["pix_fmt"] == "yuv444p"

    def test_small_resolution_boundaries(self, tmp_path):
        """Tests encoding at small dimensions (16x16, 32x32, 64x64)."""
        small_sizes = [(16, 16), (32, 32), (64, 64)]
        for w, h in small_sizes:
            out_file = tmp_path / f"test_small_{w}x{h}.mp4"
            generate_synthetic_video(out_file, width=w, height=h, duration=0.5, fps=20, faststart=True)
            assert out_file.exists()

            probe = probe_media(out_file)
            v = next(s for s in probe["streams"] if s["codec_type"] == "video")
            assert v["width"] == w
            assert v["height"] == h

    def test_zero_audio_synthetic_generation(self, tmp_path):
        """Tests synthetic video generation with audio_freq=None (no audio stream)."""
        out_file = tmp_path / "test_no_audio.mp4"
        generate_synthetic_video(
            out_file,
            width=640,
            height=360,
            duration=0.5,
            audio_freq=None,
            faststart=True,
        )
        assert out_file.exists()

        probe = probe_media(out_file)
        video_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
        audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]

        assert len(video_streams) == 1
        assert len(audio_streams) == 0

        # Assert gaming invariants can pass when expected_audio_codec is None
        res = assert_gaming_video_invariants(
            out_file,
            expected_width=640,
            expected_height=360,
            expected_video_codec="h264",
            expected_pix_fmt="yuv420p",
            expected_audio_codec=None,
            check_faststart=True,
            check_zero_captions=True,
        )
        assert res["audio_codec"] is None

    def test_invalid_resolution_inputs_fail_gracefully(self, tmp_path):
        """Tests that invalid resolutions (0, negative) raise RuntimeError instead of hanging."""
        invalid_sizes = [(0, 0), (-100, 200), (100, -200)]
        for w, h in invalid_sizes:
            out_file = tmp_path / f"test_invalid_{w}x{h}.mp4"
            with pytest.raises(RuntimeError) as exc_info:
                generate_synthetic_video(out_file, width=w, height=h, duration=0.5)
            assert "FFmpeg synthetic video generation failed" in str(exc_info.value)


class TestAdversarialMoovAtomParser:
    """Stress tests for ISO Base Media File Format atom parsing and faststart verification."""

    def test_non_faststart_video_triggers_faststart_violation(self, tmp_path):
        """
        Generates an MP4 without -movflags +faststart.
        Empirically verifies that mdat precedes moov and assert_faststart_moov_atom fails.
        """
        out_file = tmp_path / "non_faststart.mp4"
        generate_synthetic_video(out_file, width=320, height=240, duration=0.5, faststart=False)

        atoms = parse_top_level_atoms(out_file)
        assert "moov" in atoms
        assert "mdat" in atoms
        # In non-faststart files, mdat must precede moov
        assert atoms.index("mdat") < atoms.index("moov")

        with pytest.raises(AssertionError) as exc_info:
            assert_faststart_moov_atom(out_file)
        assert "Faststart violation" in str(exc_info.value)
        assert "'moov' atom" in str(exc_info.value)
        assert "must precede 'mdat' atom" in str(exc_info.value)

    def test_missing_moov_atom_fails_assertion(self, tmp_path):
        """Constructs an MP4 file missing the 'moov' atom."""
        corrupt_file = tmp_path / "missing_moov.mp4"
        # Write ftyp and mdat boxes manually
        ftyp_payload = b"isom\x00\x00\x02\x00isomiso2mp41"
        ftyp_box = struct.pack(">I4s", len(ftyp_payload) + 8, b"ftyp") + ftyp_payload
        mdat_box = struct.pack(">I4s", 16, b"mdat") + b"\x00" * 8
        corrupt_file.write_bytes(ftyp_box + mdat_box)

        atoms = parse_top_level_atoms(corrupt_file)
        assert "moov" not in atoms
        assert "mdat" in atoms

        with pytest.raises(AssertionError) as exc_info:
            assert_faststart_moov_atom(corrupt_file)
        assert "Missing 'moov' atom" in str(exc_info.value)

    def test_missing_mdat_atom_fails_assertion(self, tmp_path):
        """Constructs an MP4 file missing the 'mdat' atom."""
        corrupt_file = tmp_path / "missing_mdat.mp4"
        ftyp_payload = b"isom\x00\x00\x02\x00isomiso2mp41"
        ftyp_box = struct.pack(">I4s", len(ftyp_payload) + 8, b"ftyp") + ftyp_payload
        moov_box = struct.pack(">I4s", 16, b"moov") + b"\x00" * 8
        corrupt_file.write_bytes(ftyp_box + moov_box)

        atoms = parse_top_level_atoms(corrupt_file)
        assert "moov" in atoms
        assert "mdat" not in atoms

        with pytest.raises(AssertionError) as exc_info:
            assert_faststart_moov_atom(corrupt_file)
        assert "Missing 'mdat' atom" in str(exc_info.value)

    def test_corrupt_and_truncated_files_do_not_crash_parser(self, tmp_path):
        """Tests that 0-byte, 3-byte, and random-byte files are parsed safely without unhandled crashes."""
        # 1. Zero-byte file
        zero_file = tmp_path / "zero.mp4"
        zero_file.write_bytes(b"")
        assert parse_top_level_atoms(zero_file) == []
        with pytest.raises(AssertionError):
            assert_faststart_moov_atom(zero_file)

        # 2. Truncated header (3 bytes)
        trunc_file = tmp_path / "trunc.mp4"
        trunc_file.write_bytes(b"\x00\x00\x10")
        assert parse_top_level_atoms(trunc_file) == []
        with pytest.raises(AssertionError):
            assert_faststart_moov_atom(trunc_file)

        # 3. 7-byte header (1 byte short of 8)
        trunc7_file = tmp_path / "trunc7.mp4"
        trunc7_file.write_bytes(b"\x00\x00\x00\x07fty")
        assert parse_top_level_atoms(trunc7_file) == []

        # 4. Binary noise (1024 bytes)
        noise_file = tmp_path / "noise.mp4"
        noise_file.write_bytes(os.urandom(1024))
        noise_atoms = parse_top_level_atoms(noise_file)
        assert isinstance(noise_atoms, list)
        with pytest.raises(AssertionError):
            assert_faststart_moov_atom(noise_file)

    def test_extended_64bit_size_box_parsing(self, tmp_path):
        """Verifies parsing of ISO boxes with 64-bit extended size (size == 1)."""
        ext_file = tmp_path / "ext_size.mp4"
        # Construct ftyp box
        ftyp_payload = b"isom"
        ftyp_box = struct.pack(">I4s", len(ftyp_payload) + 8, b"ftyp") + ftyp_payload

        # Construct moov box with size == 1 (extended 64-bit size = 32 bytes total)
        moov_box = struct.pack(">I4sQ", 1, b"moov", 32) + b"\x00" * 16

        # Construct mdat box
        mdat_box = struct.pack(">I4s", 16, b"mdat") + b"\x00" * 8

        ext_file.write_bytes(ftyp_box + moov_box + mdat_box)

        atoms = parse_top_level_atoms(ext_file)
        assert atoms == ["ftyp", "moov", "mdat"]
        # Faststart should pass because moov precedes mdat
        assert_faststart_moov_atom(ext_file)

    def test_zero_size_box_terminates_parser(self, tmp_path):
        """Verifies that an atom with size == 0 (extends to EOF) terminates parsing cleanly."""
        eof_file = tmp_path / "eof_size.mp4"
        ftyp_box = struct.pack(">I4s", 12, b"ftyp") + b"isom"
        # moov extends to EOF
        moov_box = struct.pack(">I4s", 0, b"moov") + b"\x00" * 32
        eof_file.write_bytes(ftyp_box + moov_box)

        atoms = parse_top_level_atoms(eof_file)
        assert atoms == ["ftyp", "moov"]


class TestAdversarialR5ZeroCaptionInvariant:
    """Adversarially injects subtitles into media and filtergraphs to verify negative detection."""

    def test_embedded_subtitle_stream_immediately_caught_by_zero_caption_invariant(self, tmp_path):
        """
        Injects a genuine mov_text subtitle stream into an MP4 file.
        Verifies that assert_zero_caption_invariant immediately raises an AssertionError.
        """
        srt_file = tmp_path / "temp.srt"
        srt_file.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nAdversarial Injected Caption\n",
            encoding="utf-8",
        )

        sub_mp4 = tmp_path / "embedded_sub.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:duration=1:rate=25",
            "-f", "lavfi", "-i", "sine=duration=1",
            "-i", str(srt_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-c:s", "mov_text",
            str(sub_mp4),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0, f"FFmpeg failed to create test video:\n{res.stderr}"

        # Clean up disk srt file so only the embedded subtitle stream exists
        srt_file.unlink()

        # 1. Verify probe sees the subtitle stream
        probe = probe_media(sub_mp4)
        sub_streams = [s for s in probe["streams"] if s["codec_type"] == "subtitle"]
        assert len(sub_streams) == 1
        assert sub_streams[0]["codec_name"] == "mov_text"

        # 2. Verify assert_zero_caption_invariant triggers R5 Violation
        with pytest.raises(AssertionError) as exc_info:
            assert_zero_caption_invariant(sub_mp4, check_directory=False)
        assert "R5 Violation" in str(exc_info.value)
        assert "contains 1 subtitle stream(s)" in str(exc_info.value)

        # 3. Verify assert_gaming_video_invariants also fails on the same file
        with pytest.raises(AssertionError) as exc_info2:
            assert_gaming_video_invariants(
                sub_mp4,
                expected_width=320,
                expected_height=240,
                check_zero_captions=True,
            )
        assert "R5 Violation" in str(exc_info2.value)

    def test_all_subtitle_file_extensions_detected_in_directory(self, tmp_path):
        """Verifies that all standard subtitle file formats are caught by directory scanning."""
        video_file = tmp_path / "clean_video.mp4"
        create_synthetic_1080p_gameplay(video_file, duration=0.5)

        extensions = [".srt", ".vtt", ".ass", ".sub", ".dfxp", ".ttml"]
        for ext in extensions:
            sub_file = tmp_path / f"leak{ext}"
            sub_file.write_text("Dummy subtitle content", encoding="utf-8")

            with pytest.raises(AssertionError) as exc_info:
                assert_zero_caption_invariant(video_file, check_directory=True)
            assert "R5 Violation: Found caption/subtitle artifact files" in str(exc_info.value)
            assert f"leak{ext}" in str(exc_info.value)

            # Cleanup for next iteration
            sub_file.unlink()

    def test_case_insensitive_subtitle_extensions_detected(self, tmp_path):
        """Verifies uppercase extensions like .SRT, .VTT, .ASS are caught."""
        video_file = tmp_path / "clean_video.mp4"
        create_synthetic_1080p_gameplay(video_file, duration=0.5)

        for ext in [".SRT", ".VTT", ".Ass", ".DFXP"]:
            sub_file = tmp_path / f"UPPERCASE{ext}"
            sub_file.write_text("Uppercase extension content", encoding="utf-8")

            with pytest.raises(AssertionError) as exc_info:
                assert_zero_caption_invariant(video_file, check_directory=True)
            assert "R5 Violation" in str(exc_info.value)

            sub_file.unlink()

    def test_nested_subdirectory_subtitle_detected(self, tmp_path):
        """Verifies that subtitle files hidden in nested subdirectories are caught via rglob."""
        video_file = tmp_path / "clean_video.mp4"
        create_synthetic_1080p_gameplay(video_file, duration=0.5)

        nested_dir = tmp_path / "subfolder" / "deep_captions"
        nested_dir.mkdir(parents=True)
        hidden_srt = nested_dir / "hidden.srt"
        hidden_srt.write_text("Hidden subtitle content", encoding="utf-8")

        with pytest.raises(AssertionError) as exc_info:
            assert_zero_caption_invariant(video_file, check_directory=True)
        assert "R5 Violation" in str(exc_info.value)
        assert "hidden.srt" in str(exc_info.value)

    def test_filtergraph_rejects_subtitles_ass_and_drawtext_variants(self):
        """Verifies that all forbidden caption filters trigger R5 violations regardless of case."""
        clean_graph = "[0:v]crop=1920:1080:0:0,scale=1080:1920[v0];[v0]setsar=1[outv]"
        assert_filtergraph_zero_caption_invariant(clean_graph)

        prohibited = [
            "subtitles=subs.srt",
            "SUBTITLES=subs.srt",
            "ass=subs.ass",
            "ASS=subs.ass",
            "drawtext=text='Game Over':x=10:y=10",
            "DrawText=text='Player 1'",
            "DRAWTEXT=text='Victory'",
        ]
        for p in prohibited:
            bad_graph = f"{clean_graph};[outv]{p}[finalv]"
            with pytest.raises(AssertionError) as exc_info:
                assert_filtergraph_zero_caption_invariant(bad_graph)
            assert "R5 Violation" in str(exc_info.value)


class TestAdversarialVideoInvariantsAssertions:
    """Stress tests boundary failures for assert_gaming_video_invariants."""

    def test_fails_on_horizontal_resolution_mismatch(self, tmp_path):
        """Tests that a 1920x1080 horizontal video fails when expecting 9:16 vertical (1080x1920)."""
        out_file = tmp_path / "horizontal.mp4"
        create_synthetic_1080p_gameplay(out_file, duration=0.5)

        with pytest.raises(AssertionError) as exc_info:
            assert_gaming_video_invariants(
                out_file,
                expected_width=1080,
                expected_height=1920,
            )
        assert "Width mismatch: expected 1080, got 1920" in str(exc_info.value)

    def test_fails_on_pixel_format_mismatch(self, tmp_path):
        """Tests failure when pix_fmt is yuv444p but yuv420p is expected."""
        out_file = tmp_path / "odd_fmt.mp4"
        generate_synthetic_video(out_file, width=320, height=240, duration=0.5, pix_fmt="yuv444p")

        with pytest.raises(AssertionError) as exc_info:
            assert_gaming_video_invariants(
                out_file,
                expected_width=320,
                expected_height=240,
                expected_pix_fmt="yuv420p",
            )
        assert "Pixel format mismatch: expected yuv420p, got yuv444p" in str(exc_info.value)

    def test_fails_on_missing_audio_stream_when_audio_expected(self, tmp_path):
        """Tests failure when video has 0 audio streams but expected_audio_codec='aac'."""
        out_file = tmp_path / "silent.mp4"
        generate_synthetic_video(out_file, width=320, height=240, duration=0.5, audio_freq=None)

        with pytest.raises(AssertionError) as exc_info:
            assert_gaming_video_invariants(
                out_file,
                expected_width=320,
                expected_height=240,
                expected_audio_codec="aac",
            )
        assert "Expected at least 1 audio stream, found 0" in str(exc_info.value)

    def test_fails_on_duration_drift_outside_tolerance(self, tmp_path):
        """Tests failure when actual duration drifts beyond duration_tolerance."""
        out_file = tmp_path / "short.mp4"
        generate_synthetic_video(out_file, width=320, height=240, duration=1.0)

        with pytest.raises(AssertionError) as exc_info:
            assert_gaming_video_invariants(
                out_file,
                expected_width=320,
                expected_height=240,
                expected_duration=5.0,  # Expected 5s, actual ~1s
                duration_tolerance=0.25,
            )
        assert "Duration mismatch: expected 5.0s ±0.25s" in str(exc_info.value)
