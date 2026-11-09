"""
Unit and Integration Tests for PODCAST-TRACKING-003:
Continuous Intra-Shot Participant-Aware Camera Following for Fixed Two-Person Area.
"""

import os
import json
import time
import shutil
import asyncio
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from backend.services.advanced_podcast_engine import (
    CropTrajectorySmoother,
    calculate_two_person_fixed_boundary_crop,
    build_fixed_boundary_schedule,
    build_intra_shot_crop_expression,
    render_camera_following_video,
    render_fixed_boundary_two_person_video,
)
from backend.services.clip_cutter import get_video_dimensions


@pytest.fixture
def outer_boundary():
    return {"x": 0.10, "y": 0.05, "width": 0.80, "height": 0.90}


@pytest.fixture
def participant_regions():
    return [
        {"id": "speaker_1", "label": "Host", "x": 0.20, "y": 0.20, "width": 0.20, "height": 0.40},
        {"id": "speaker_2", "label": "Guest", "x": 0.60, "y": 0.20, "width": 0.20, "height": 0.40},
    ]


@pytest.fixture
def synthetic_video_path(tmp_path):
    """Generates a deterministic 3-second 1920x1080 25fps synthetic test video with audio."""
    out_file = tmp_path / "synthetic_test_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3.0:size=1920x1080:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=3.0",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-sn",
        str(out_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg video generation failed: {res.stderr}"
    assert out_file.exists()
    return out_file


class TestIntraShotCropExpression:
    """Tests for build_intra_shot_crop_expression and mathematical interpolation."""

    def test_single_point_or_empty_returns_default(self):
        assert build_intra_shot_crop_expression([], 3.0, default_x=450) == "450"
        assert build_intra_shot_crop_expression([(0.0, 500)], 3.0, default_x=450) == "450"

    def test_constant_points_returns_static_x(self):
        pts = [(0.0, 400), (1.0, 400), (2.0, 400)]
        assert build_intra_shot_crop_expression(pts, 2.0, default_x=400) == "400"

    def test_linear_interpolation_expression_structure(self):
        pts = [(0.0, 200), (1.0, 300), (2.0, 400)]
        expr = build_intra_shot_crop_expression(pts, 2.0, default_x=200)
        assert "trunc(" in expr
        assert "if(lt(t" in expr
        assert "/2)*2" in expr

    def test_ffmpeg_evaluates_expression_cleanly(self):
        pts = [(0.0, 100), (1.0, 260), (2.0, 180), (3.0, 320)]
        expr = build_intra_shot_crop_expression(pts, 3.0, default_x=100)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=1920x1080:rate=25",
            "-vf", f"crop=1080:1080:{expr}:0",
            "-f", "null", "-"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"FFmpeg failed to evaluate crop expression: {res.stderr}"


class TestContinuousTrajectoryGeneration:
    """Tests for within-shot trajectory points and boundary containment."""

    def test_intra_shot_sampling_produces_multiple_points(self, synthetic_video_path, outer_boundary, participant_regions):
        schedule = build_fixed_boundary_schedule(
            video_path=synthetic_video_path,
            outer_boundary=outer_boundary,
            participant_regions=participant_regions,
            intra_sample_fps=4.0
        )
        assert len(schedule) >= 1
        shot = schedule[0]
        assert "intra_shot_trajectory" in shot
        traj = shot["intra_shot_trajectory"]
        assert len(traj) >= 2, f"Expected at least 2 intra-shot trajectory points, got {len(traj)}"
        assert shot.get("is_continuous_tracking") is True

        # Check fields of each trajectory point
        for pt in traj:
            assert "t" in pt
            assert "rel_t" in pt
            assert "x" in pt
            assert "y" in pt
            assert "w" in pt
            assert "h" in pt
            assert "norm_x" in pt
            assert "both_faces_fit" in pt
            assert pt["x"] % 2 == 0, "Crop x coordinate must be even"

    def test_trajectory_contained_within_outer_boundary(self, synthetic_video_path, outer_boundary, participant_regions):
        schedule = build_fixed_boundary_schedule(
            video_path=synthetic_video_path,
            outer_boundary=outer_boundary,
            participant_regions=participant_regions,
            intra_sample_fps=4.0
        )
        src_w, src_h = 1920, 1080
        bound_x1 = int(outer_boundary["x"] * src_w)
        bound_x2 = bound_x1 + int(outer_boundary["width"] * src_w)

        for shot in schedule:
            for pt in shot["intra_shot_trajectory"]:
                x1 = pt["x"]
                w = pt["w"]
                assert x1 >= bound_x1, f"Crop x1 ({x1}) escaped left boundary ({bound_x1})"
                assert x1 + w <= bound_x2, f"Crop right edge ({x1 + w}) escaped right boundary ({bound_x2})"

    def test_continuous_crop_tracking_follows_moving_participant(self, outer_boundary):
        """Simulates a participant moving horizontally across 5 successive intra-shot frames."""
        smoother = CropTrajectorySmoother(deadband_norm=0.01, alpha=0.30)
        positions_x = [0.25, 0.35, 0.45, 0.55, 0.65]  # Continuous movement to the right
        recorded_crops = []

        for p_idx, pos in enumerate(positions_x):
            is_cut = (p_idx == 0)
            mock_boxes = [
                {"x": pos, "y": 0.20, "width": 0.15, "height": 0.35},
                {"x": 0.75, "y": 0.20, "width": 0.15, "height": 0.35}
            ]
            crop = calculate_two_person_fixed_boundary_crop(
                outer_boundary=outer_boundary,
                src_w=1920,
                src_h=1080,
                smoother=smoother,
                participant_boxes=mock_boxes,
                is_cut=is_cut
            )
            recorded_crops.append(crop["x"])

        # Validate that crop position actually moved rightward over time
        assert recorded_crops[-1] > recorded_crops[0], f"Expected crop to move right, got {recorded_crops}"
        # Validate that movement is smooth without instant large jumps
        diffs = [abs(recorded_crops[i+1] - recorded_crops[i]) for i in range(len(recorded_crops) - 1)]
        assert all(d <= 200 for d in diffs), f"Excessive jump detected in trajectory: {diffs}"

    def test_camera_cut_resets_smoother_without_drag(self, outer_boundary):
        smoother = CropTrajectorySmoother(deadband_norm=0.02, alpha=0.20)

        # Shot 1 ends with participants framed on the left
        crop1 = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            src_w=1920, src_h=1080,
            smoother=smoother,
            participant_boxes=[
                {"x": 0.12, "y": 0.2, "width": 0.12, "height": 0.3},
                {"x": 0.28, "y": 0.2, "width": 0.12, "height": 0.3}
            ],
            is_cut=True
        )

        # Shot 2 begins after cut with participants framed on the right: is_cut=True must snap immediately
        crop2_snap = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            src_w=1920, src_h=1080,
            smoother=smoother,
            participant_boxes=[
                {"x": 0.60, "y": 0.2, "width": 0.12, "height": 0.3},
                {"x": 0.76, "y": 0.2, "width": 0.12, "height": 0.3}
            ],
            is_cut=True
        )

        # Compare with is_cut=False (which would have suffered EMA lag)
        smoother_lagged = CropTrajectorySmoother(deadband_norm=0.02, alpha=0.20)
        smoother_lagged.prev_center_norm = crop1["norm_x"]
        smoother_lagged.prev_track_id = "two_person_fixed"

        crop2_lagged = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            src_w=1920, src_h=1080,
            smoother=smoother_lagged,
            participant_boxes=[
                {"x": 0.60, "y": 0.2, "width": 0.12, "height": 0.3},
                {"x": 0.76, "y": 0.2, "width": 0.12, "height": 0.3}
            ],
            is_cut=False
        )

        # The snapped crop must be positioned further right than the lagged crop
        assert crop2_snap["x"] > crop1["x"] + 300, f"Expected snap across cut, got {crop1['x']} -> {crop2_snap['x']}"
        assert crop2_snap["x"] > crop2_lagged["x"], f"Snapped crop ({crop2_snap['x']}) must exceed lagged crop ({crop2_lagged['x']})"


    def test_no_solo_collapse_when_participants_far_apart(self, outer_boundary):
        """When participants are too far apart for 9:16 crop width, centers between them without collapsing to solo."""
        far_boxes = [
            {"x": 0.05, "y": 0.2, "width": 0.15, "height": 0.3},
            {"x": 0.85, "y": 0.2, "width": 0.15, "height": 0.3}
        ]
        crop = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            src_w=1920, src_h=1080,
            participant_boxes=far_boxes
        )
        assert crop["geometry_impossible"] is True
        assert crop["both_faces_fit"] is False
        # Must be centered in boundary rather than hugging far left or far right
        assert 0.35 <= crop["norm_x"] <= 0.65


@pytest.mark.asyncio
class TestRealRenderContinuousTracking:
    """Tests executing real FFmpeg renders with dynamic intra-shot camera following."""

    async def test_real_render_executes_with_dynamic_intra_shot_crop(self, synthetic_video_path, tmp_path):
        output_mp4 = tmp_path / "rendered_continuous_follow.mp4"

        # Trajectory with moving crop from x=200 at t=0.0 to x=600 at t=3.0
        shot_schedule = [{
            "shot_id": 1,
            "start_time": 0.0,
            "end_time": 3.0,
            "duration": 3.0,
            "composition": "FIXED_TWO_PERSON_FOLLOW",
            "active_track_id": "both_participants",
            "confidence": 1.0,
            "crop_rect": {"w": 608, "h": 1080, "x": 200, "y": 0},
            "intra_shot_trajectory": [
                {"t": 0.0, "rel_t": 0.0, "x": 200, "y": 0, "w": 608, "h": 1080, "norm_x": 0.104, "norm_w": 0.316, "both_faces_fit": True},
                {"t": 1.0, "rel_t": 1.0, "x": 340, "y": 0, "w": 608, "h": 1080, "norm_x": 0.177, "norm_w": 0.316, "both_faces_fit": True},
                {"t": 2.0, "rel_t": 2.0, "x": 480, "y": 0, "w": 608, "h": 1080, "norm_x": 0.250, "norm_w": 0.316, "both_faces_fit": True},
                {"t": 3.0, "rel_t": 3.0, "x": 600, "y": 0, "w": 608, "h": 1080, "norm_x": 0.312, "norm_w": 0.316, "both_faces_fit": True},
            ],
            "is_continuous_tracking": True
        }]

        rendered_path = await render_camera_following_video(
            video_path=synthetic_video_path,
            output_path=output_mp4,
            shot_schedule=shot_schedule,
            clip_start=0.0,
            clip_end=3.0,
            canvas_w=1080,
            canvas_h=1920
        )
        assert rendered_path.exists()
        assert rendered_path.stat().st_size > 1000

        # FFprobe inspection to verify 1080x1920, H.264, AAC, and strictly 0 subtitle streams
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height",
            "-of", "json",
            str(rendered_path)
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        assert probe_res.returncode == 0
        probe_data = json.loads(probe_res.stdout)
        streams = probe_data.get("streams", [])

        video_stream = next(s for s in streams if s["codec_type"] == "video")
        audio_stream = next(s for s in streams if s["codec_type"] == "audio")
        subtitle_streams = [s for s in streams if s["codec_type"] == "subtitle"]

        assert video_stream["width"] == 1080
        assert video_stream["height"] == 1920
        assert video_stream["codec_name"] == "h264"
        assert audio_stream["codec_name"] == "aac"
        assert len(subtitle_streams) == 0, f"STRICT INVARIANT VIOLATION: {len(subtitle_streams)} subtitle streams found!"

    async def test_rendered_frames_visibly_change_within_same_shot(self, synthetic_video_path, tmp_path):
        """Extracts frames at t=0.5s and t=2.5s within the same single shot to verify crop movement."""
        output_mp4 = tmp_path / "rendered_movement_check.mp4"

        shot_schedule = [{
            "shot_id": 1,
            "start_time": 0.0,
            "end_time": 3.0,
            "duration": 3.0,
            "composition": "FIXED_TWO_PERSON_FOLLOW",
            "active_track_id": "both_participants",
            "confidence": 1.0,
            "crop_rect": {"w": 608, "h": 1080, "x": 200, "y": 0},
            "intra_shot_trajectory": [
                {"t": 0.0, "rel_t": 0.0, "x": 100, "y": 0, "w": 608, "h": 1080, "norm_x": 0.052, "norm_w": 0.316, "both_faces_fit": True},
                {"t": 1.5, "rel_t": 1.5, "x": 350, "y": 0, "w": 608, "h": 1080, "norm_x": 0.182, "norm_w": 0.316, "both_faces_fit": True},
                {"t": 3.0, "rel_t": 3.0, "x": 600, "y": 0, "w": 608, "h": 1080, "norm_x": 0.312, "norm_w": 0.316, "both_faces_fit": True},
            ],
            "is_continuous_tracking": True
        }]

        await render_camera_following_video(
            video_path=synthetic_video_path,
            output_path=output_mp4,
            shot_schedule=shot_schedule,
            clip_start=0.0,
            clip_end=3.0,
            canvas_w=1080,
            canvas_h=1920
        )

        # Extract frames at t=0.5s and t=2.5s
        frame_05 = tmp_path / "frame_05.jpg"
        frame_25 = tmp_path / "frame_25.jpg"

        subprocess.run(["ffmpeg", "-y", "-ss", "0.5", "-i", str(output_mp4), "-frames:v", "1", str(frame_05)], capture_output=True, check=True)
        subprocess.run(["ffmpeg", "-y", "-ss", "2.5", "-i", str(output_mp4), "-frames:v", "1", str(frame_25)], capture_output=True, check=True)

        assert frame_05.exists() and frame_25.exists()
        # Verify frame files have different content (pixel change due to camera following)
        with open(frame_05, "rb") as f1, open(frame_25, "rb") as f2:
            bytes_05 = f1.read()
            bytes_25 = f2.read()
        assert bytes_05 != bytes_25, "Frames at distinct timestamps within moving shot should not be identical"


class TestPerformanceBenchmark:
    """Benchmark comparing static shot-level reframing vs continuous intra-shot tracking."""

    def test_benchmark_tracking_overhead_is_bounded(self, synthetic_video_path, outer_boundary, participant_regions):
        # 1. Measure shot-level (intra_sample_fps=0)
        t0 = time.perf_counter()
        schedule_static = build_fixed_boundary_schedule(
            video_path=synthetic_video_path,
            outer_boundary=outer_boundary,
            participant_regions=participant_regions,
            intra_sample_fps=0
        )
        t_static = time.perf_counter() - t0

        # 2. Measure continuous intra-shot tracking (intra_sample_fps=4)
        t1 = time.perf_counter()
        schedule_continuous = build_fixed_boundary_schedule(
            video_path=synthetic_video_path,
            outer_boundary=outer_boundary,
            participant_regions=participant_regions,
            intra_sample_fps=4.0
        )
        t_continuous = time.perf_counter() - t1

        print(f"\n[BENCHMARK] Static shot-level: {t_static:.4f}s | Continuous intra-shot (4 FPS): {t_continuous:.4f}s")
        assert len(schedule_static) == len(schedule_continuous)
        assert t_continuous < 5.0, f"Continuous tracking took too long: {t_continuous:.2f}s"
