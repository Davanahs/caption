"""
Regression Tests for Work Item PODCAST-ZERO-CUT-FALLBACK-016
============================================================
Logic Domain: L7 (Advanced Multi-Speaker Podcast Framing & Active Speaker Tracking)

Validates the separation of FFmpeg execution success from camera-cut detection count:
1. Successful FFmpeg execution returning zero cuts MUST NOT invoke OpenCV fallback.
2. FFmpeg execution failure (missing binary, non-zero exit code, timeout, launch error)
   MUST invoke the fallback.
3. Multi-cut detection must preserve existing valid cuts and behavior.
4. Dual failure (FFmpeg and fallback) must yield a controlled safe single-shot interval.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backend.services.advanced_podcast_engine as ape


@pytest.fixture(scope="module")
def synthetic_single_shot_video():
    """Generates an isolated, temporary 5.0-second single-shot video without camera cuts."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    temp_dir = tempfile.mkdtemp()
    video_path = Path(temp_dir) / "test_single_shot.mp4"

    cmd = [
        ffmpeg_bin, "-y", "-f", "lavfi",
        "-i", "color=c=blue:s=320x240:d=5:r=25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    yield video_path

    shutil.rmtree(temp_dir, ignore_errors=True)


class TestZeroCutFallbackGovernance:
    """Tests evaluating detector execution state vs. cut count."""

    def test_scenario_1_successful_ffmpeg_zero_cuts_no_fallback(self, synthetic_single_shot_video):
        """
        Scenario 1: FFmpeg runs cleanly (exit code 0), finding 0 cuts.
        REQUIRED: Fallback MUST NOT be invoked.
        NOTE: On unpatched code, this test fails because 0 cuts erroneously triggers fallback.
        """
        with patch.object(
            ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
        ) as mock_hist:
            shots = ape.detect_camera_cuts(synthetic_single_shot_video)

            # Verification 1: Valid whole-video shot interval returned
            assert len(shots) == 1
            assert shots[0][0] == 0.0
            assert pytest.approx(shots[0][1], abs=0.1) == 5.0

            # Verification 2: OpenCV fallback was NOT invoked
            # On the unpatched code, mock_hist.call_count is 25!
            assert mock_hist.call_count == 0, (
                f"DEFECT DETECTED: Fallback was invoked ({mock_hist.call_count} calls) "
                "despite clean FFmpeg execution!"
            )

    def test_scenario_2_successful_execution_one_cut_no_fallback(self, synthetic_single_shot_video):
        """
        Scenario 2: FFmpeg succeeds with 1 detected cut at 2.5s.
        REQUIRED: Cut preserved at 2.5s, exactly 2 shots returned, no fallback.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 2.50\n",
        )

        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) == 2
                assert shots[0] == (0.0, 2.5)
                assert pytest.approx(shots[1][0], abs=0.01) == 2.5
                assert pytest.approx(shots[1][1], abs=0.1) == 5.0
                assert mock_hist.call_count == 0

    def test_scenario_3_successful_execution_multiple_cuts_no_fallback(self, synthetic_single_shot_video):
        """
        Scenario 3: FFmpeg succeeds with multiple valid cuts.
        REQUIRED: All valid cuts preserved, no fallback.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr=(
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 1.50\n"
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 3.20\n"
            ),
        )

        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) == 3
                assert shots[0] == (0.0, 1.5)
                assert shots[1] == (1.5, 3.2)
                assert pytest.approx(shots[2][0], abs=0.01) == 3.2
                assert pytest.approx(shots[2][1], abs=0.1) == 5.0
                assert mock_hist.call_count == 0

    def test_scenario_4_missing_ffmpeg_binary_invokes_fallback(self, synthetic_single_shot_video):
        """
        Scenario 4: FFmpeg binary is missing from system PATH.
        REQUIRED: Genuine execution failure; fallback MUST be invoked.
        """
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
                with patch.object(
                    ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
                ) as mock_hist:
                    shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                    assert len(shots) >= 1
                    assert mock_hist.call_count > 0, "Fallback must be invoked when binary is missing"

    def test_scenario_5_process_launch_exception_invokes_fallback(self, synthetic_single_shot_video):
        """
        Scenario 5: Process launch raises PermissionError / OSError.
        REQUIRED: Fallback MUST be invoked.
        """
        with patch("subprocess.run", side_effect=PermissionError("Execution denied")):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0

    def test_scenario_6_nonzero_exit_code_invokes_fallback(self, synthetic_single_shot_video):
        """
        Scenario 6: FFmpeg exits with non-zero exit code (e.g. exit code 1 due to filter error).
        REQUIRED: Must NOT be treated as zero cuts; fallback MUST be invoked.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=1,
            stdout="",
            stderr="Filtergraph initialization failed: Invalid argument\n",
        )

        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked on non-zero exit code"

    def test_scenario_7_timeout_invokes_fallback(self, synthetic_single_shot_video):
        """
        Scenario 7: FFmpeg execution exceeds timeout.
        REQUIRED: Fallback MUST be invoked.
        """
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0

    def test_scenario_8_malformed_detector_output_with_clean_exit(self, synthetic_single_shot_video):
        """
        Scenario 8: FFmpeg exits 0, but stderr contains corrupt non-numeric tokens.
        REQUIRED: Metadata corruption flagged, partial detections cleared, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="lavfi.scd.time: corrupt_value\nlavfi.scd.time: \n",
        )

        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "OpenCV fallback must be invoked when metadata is corrupt"

    def test_scenario_9_empty_valid_detector_output_returns_single_shot(self, synthetic_single_shot_video):
        """
        Scenario 9: Clean empty stderr string (isolated parser test).
        REQUIRED: Zero-cut result accepted; OpenCV fallback NOT invoked.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) == 1
                assert shots[0] == (0.0, 5.0)
                assert mock_hist.call_count == 0, "Fallback must not run on clean empty stderr"

    def test_scenario_10_multi_camera_video_preserves_authentic_cuts(self):
        """
        Scenario 10: Multi-camera authentic broadcast footage smoke test across full 981.08s source.
        Distinction:
        - 30 independently annotated physical cuts in certified 0-300s window (evaluated in test_independent_camera_cuts.py)
        - 92 detector events and 93 resulting shot intervals across the full 981.08s smoke run.
        - Range 300-981.08s is UNANNOTATED_OPEN.
        """
        authentic_p = Path("uploads/authentic_podcast_test.mp4")
        if not authentic_p.exists():
            pytest.skip("authentic_podcast_test.mp4 not found")

        # Running on authentic video must produce cuts without errors
        shots = ape.detect_camera_cuts(authentic_p)
        assert len(shots) >= 90
        assert shots[0][0] == 0.0

    def test_scenario_11_fallback_failure_returns_safe_whole_video_interval(self, synthetic_single_shot_video):
        """
        Scenario 11: Both FFmpeg fails AND cv2 fails.
        REQUIRED: Returns controlled safe whole-video interval [(0.0, duration)], no unhandled crash.
        """
        mock_proc = subprocess.CompletedProcess(args=["ffmpeg"], returncode=1, stderr="error")

        with patch("subprocess.run", return_value=mock_proc):
            with patch("cv2.VideoCapture") as mock_cap_cls:
                # Mock cap failing
                mock_cap = MagicMock()
                mock_cap.isOpened.return_value = True
                mock_cap.get.side_effect = lambda prop: 25.0 if prop == 5 else 125
                mock_cap.read.return_value = (False, None)
                mock_cap_cls.return_value = mock_cap

                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) == 1
                assert shots[0][0] == 0.0
                assert pytest.approx(shots[0][1], abs=0.1) == 5.0

    # -------------------------------------------------------------------------
    # Planned Metadata-Validation Edge Cases (MV-1 through MV-9) & Boundary Check
    # -------------------------------------------------------------------------

    def test_scenario_12_metadata_validation_negative_timestamp(self, synthetic_single_shot_video):
        """
        MV-1: Negative timestamp in stderr.
        REQUIRED: Metadata flagged corrupt, scdet_succeeded is False, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: -1.50\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked for negative timestamp"

    def test_scenario_13_metadata_validation_timestamp_greater_than_duration(self, synthetic_single_shot_video):
        """
        MV-2: Timestamp strictly greater than duration (8.5s on 5.0s fixture).
        REQUIRED: Metadata flagged corrupt, scdet_succeeded is False, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 8.50\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked for timestamp > duration"

    def test_scenario_14_metadata_validation_timestamp_equal_to_duration(self, synthetic_single_shot_video):
        """
        MV-3: Timestamp exactly equal to duration (5.00s on 5.0s fixture).
        REQUIRED: Excluded by 50ms boundary margin (5.00 >= 4.95), clean execution, NO fallback.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 5.00\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) == 1
                assert shots[0] == (0.0, 5.0)
                assert mock_hist.call_count == 0, "Fallback must not run for boundary timestamp excluded by margin"

    def test_scenario_15_metadata_validation_nan(self, synthetic_single_shot_video):
        """
        MV-4: Timestamp is NaN.
        REQUIRED: Metadata flagged corrupt, scdet_succeeded is False, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: nan\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked for NaN timestamp"

    def test_scenario_16_metadata_validation_positive_infinity(self, synthetic_single_shot_video):
        """
        MV-5: Timestamp is positive infinity (inf).
        REQUIRED: Metadata flagged corrupt, scdet_succeeded is False, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: inf\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked for +inf timestamp"

    def test_scenario_17_metadata_validation_negative_infinity(self, synthetic_single_shot_video):
        """
        MV-6: Timestamp is negative infinity (-inf).
        REQUIRED: Metadata flagged corrupt, scdet_succeeded is False, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: -inf\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked for -inf timestamp"

    def test_scenario_18_metadata_validation_25fps_boundaries_at_0_04_and_4_96(self, synthetic_single_shot_video):
        """
        MV-7: 25 FPS frame boundaries at 0.04s (Frame 1) and 4.96s (Frame 124 on 125-frame 5s video).
        REQUIRED: Both excluded by 50ms margin (0.04 <= 0.05 and 4.96 >= 4.95). NO fallback.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr=(
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 0.04\n"
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 4.96\n"
            ),
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) == 1
                assert shots[0] == (0.0, 5.0)
                assert mock_hist.call_count == 0, "Fallback must not run for valid margin-excluded events"

    def test_scenario_19_metadata_validation_valid_followed_by_malformed(self, synthetic_single_shot_video):
        """
        MV-8: Valid cut at 2.0s followed by malformed token.
        REQUIRED: Partial FFmpeg cut (2.0s) discarded, scdet_succeeded is False, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr=(
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 2.00\n"
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: corrupt_value\n"
            ),
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked when second token is corrupt"
                # On synthetic video where fallback finds 0 cuts, shots returns [(0.0, 5.0)].
                # 2.0 must NOT survive from the partial corrupt FFmpeg output.
                assert (0.0, 2.0) not in shots

    def test_scenario_20_metadata_validation_malformed_followed_by_valid(self, synthetic_single_shot_video):
        """
        MV-9: Malformed token followed by valid cut at 2.0s.
        REQUIRED: Early termination on corrupt token, scdet_times cleared, fallback INVOKED.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr=(
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: corrupt_value\n"
                "[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 2.00\n"
            ),
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert len(shots) >= 1
                assert mock_hist.call_count > 0, "Fallback must be invoked when first token is corrupt"
                assert (0.0, 2.0) not in shots

    def test_scenario_21_boundary_event_at_4_92s_preexisting_tail_truncation(self, synthetic_single_shot_video):
        """
        Empirical evaluation of 4.92s event on 5.00s video:
        - 4.92s is outside the 50ms margin (4.92 < 4.95).
        - 4.92s passes the 0.8s minimum shot duration guard (4.92 - 0.0 >= 0.8).
        - Downstream line 564 appends 5.00 -> [0.0, 4.92, 5.00].
        - Downstream line 572 checks (e - s >= 0.1):
            Interval 1: (0.0, 4.92) -> duration 4.92 >= 0.1 -> retained.
            Interval 2: (4.92, 5.00) -> duration 0.08 < 0.1 -> DISCARDED!
        Result: Returned intervals end at 4.92s, revealing the pre-existing downstream tail truncation defect.
        """
        mock_proc = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=0,
            stdout="",
            stderr="[Parsed_scdet_0 @ 0x1] lavfi.scd.time: 4.92\n",
        )
        with patch("subprocess.run", return_value=mock_proc):
            with patch.object(
                ape, "compute_normalized_hsv_hist", wraps=ape.compute_normalized_hsv_hist
            ) as mock_hist:
                shots = ape.detect_camera_cuts(synthetic_single_shot_video)
                assert mock_hist.call_count == 0, "Clean FFmpeg run must not invoke fallback"
                # Empirically confirms the pre-existing downstream interval truncation limitation:
                assert len(shots) == 1
                assert shots[0] == (0.0, 4.92), (
                    f"Expected (0.0, 4.92) due to downstream 80ms tail discard, got: {shots}"
                )
                assert shots[-1][1] < 5.0, "Confirms 80ms tail (4.92 to 5.00) is discarded by downstream line 572"

