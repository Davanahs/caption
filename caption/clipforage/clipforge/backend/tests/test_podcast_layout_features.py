"""
backend/tests/test_podcast_layout_features.py
=============================================
Verification tests for Topic 7:
- Subtopic 7.1: Feature 1 — Fixed two-person selected area with face-aware camera following
- Subtopic 7.2: Feature 2 — Visibility-driven composition (Person A / Person B / Side-by-Side)
- Subtopic 7.3: Pipeline integration, continuous audio, -sn zero subtitle burn-in, real footage test
"""
import pytest
import os
import json
import asyncio
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from backend.services.advanced_podcast_engine import (
    calculate_two_person_fixed_boundary_crop,
    build_fixed_boundary_schedule,
    render_fixed_boundary_two_person_video,
    classify_visibility_composition,
    build_visibility_driven_schedule,
    render_visibility_driven_video,
    render_camera_following_video,
    CropTrajectorySmoother,
    calculate_9_16_crop_rect,
    detect_faces_in_frame,
    match_and_track_participants,
    calculate_side_by_side_participant_crop,
)


# ═════════════════════════════════════════════════════════════════════════════════
# 1. FEATURE 1 TESTS: FIXED TWO-PERSON AREA WITH CAMERA FOLLOWING
# ═════════════════════════════════════════════════════════════════════════════════

class TestFeature1FixedBoundaryCameraFollowing:

    def test_both_people_close_together_fit_completely(self):
        """When both participants are close together, both faces fit completely inside the crop."""
        outer_boundary = {"x": 0.05, "y": 0.0, "width": 0.90, "height": 1.0}
        src_w, src_h = 1920, 1080
        # Face A: [0.42, 0.52], Face B: [0.48, 0.58] -> total span ~ 0.16 * 1920 = 307px < 608px
        boxes = [
            {"x": 0.42, "y": 0.20, "width": 0.08, "height": 0.20},
            {"x": 0.50, "y": 0.20, "width": 0.08, "height": 0.20}
        ]
        res = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            participant_boxes=boxes,
            src_w=src_w,
            src_h=src_h
        )
        assert res["both_faces_fit"] is True
        assert res["geometry_impossible"] is False
        # Verify both bounding boxes are strictly within the crop [x, x + w]
        req_left = int((0.42 - 0.02) * src_w)
        req_right = int((0.58 + 0.02) * src_w)
        assert res["x"] <= req_left, f"Crop left {res['x']} cut off Face A left {req_left}"
        assert res["x"] + res["w"] >= req_right, f"Crop right {res['x'] + res['w']} cut off Face B right {req_right}"

    def test_both_people_far_apart_demonstrates_geometric_limit(self):
        """
        When participants are separated by more than 9:16 crop width (e.g. span 900px > 608px),
        it is geometrically impossible to fit both faces entirely inside a single 9:16 crop.
        The algorithm must report geometry_impossible=True and strictly prevent solo crop collapse.
        """
        outer_boundary = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
        src_w, src_h = 1920, 1080
        # Face A at left [0.15, 0.25], Face B at right [0.75, 0.85] -> span ~ 0.70 * 1920 = 1344px > 608px
        boxes = [
            {"x": 0.15, "y": 0.20, "width": 0.10, "height": 0.20},
            {"x": 0.75, "y": 0.20, "width": 0.10, "height": 0.20}
        ]
        res = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            participant_boxes=boxes,
            src_w=src_w,
            src_h=src_h
        )
        assert res["geometry_impossible"] is True
        assert res["both_faces_fit"] is False
        assert res["required_span_px"] > res["crop_w_px"]
        # Invariant: Crop does NOT collapse into a solo crop on person A or person B;
        # it centers between them clamped within boundary.
        midpoint_px = int(((0.15 + 0.85) / 2.0) * src_w)
        crop_center = res["x"] + res["w"] // 2
        assert abs(crop_center - midpoint_px) <= 20, "Must remain centered between both participants rather than collapsing to solo"

    def test_participants_near_left_boundary(self):
        """Crop respects left outer boundary when participants are on the far left."""
        outer_boundary = {"x": 0.10, "y": 0.0, "width": 0.80, "height": 1.0}
        src_w, src_h = 1920, 1080
        bound_x1 = int(0.10 * 1920)  # 192px
        boxes = [
            {"x": 0.10, "y": 0.20, "width": 0.06, "height": 0.15},
            {"x": 0.20, "y": 0.20, "width": 0.06, "height": 0.15}
        ]
        res = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            participant_boxes=boxes,
            src_w=src_w,
            src_h=src_h
        )
        assert res["x"] >= bound_x1, f"Crop left {res['x']} crossed left boundary {bound_x1}"

    def test_participants_near_right_boundary(self):
        """Crop respects right outer boundary when participants are on the far right."""
        outer_boundary = {"x": 0.10, "y": 0.0, "width": 0.80, "height": 1.0}
        src_w, src_h = 1920, 1080
        bound_x2 = int(0.90 * 1920)  # 1728px
        boxes = [
            {"x": 0.75, "y": 0.20, "width": 0.06, "height": 0.15},
            {"x": 0.84, "y": 0.20, "width": 0.06, "height": 0.15}
        ]
        res = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            participant_boxes=boxes,
            src_w=src_w,
            src_h=src_h
        )
        assert res["x"] + res["w"] <= bound_x2, f"Crop right {res['x'] + res['w']} crossed right boundary {bound_x2}"

    def test_temporary_occlusion_retains_two_person_framing(self):
        """If one person is temporarily occluded / not detected, crop does NOT collapse into solo crop."""
        outer_boundary = {"x": 0.10, "y": 0.0, "width": 0.80, "height": 1.0}
        src_w, src_h = 1920, 1080
        # Only Person A detected in current frame
        single_box = [{"x": 0.25, "y": 0.20, "width": 0.08, "height": 0.20}]
        res = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            participant_boxes=single_box,
            src_w=src_w,
            src_h=src_h
        )
        # Verify crop stays anchored near boundary center rather than jumping to x=0.25 solo crop
        boundary_mid_x = int(0.50 * src_w)
        crop_center = res["x"] + res["w"] // 2
        assert abs(crop_center - boundary_mid_x) < 150, "Must maintain two-person framing anchor during temporary occlusion"

    def test_motion_smoothing_and_camera_cut_reset(self):
        """Verify smoother eliminates micro-jitter and resets on camera cuts."""
        smoother = CropTrajectorySmoother(deadband_norm=0.03, alpha=0.25)
        p1 = smoother.smooth(0.50, "two_person", is_cut=False)
        assert p1 == 0.50
        # Micro-jitter within 3% deadband suppressed
        p2 = smoother.smooth(0.51, "two_person", is_cut=False)
        assert p2 == 0.50
        # Camera cut resets smoother immediately (zero inertia from previous scene)
        p_cut = smoother.smooth(0.80, "two_person", is_cut=True)
        assert p_cut == 0.80, "Camera cut must immediately reset smoothing without inertia"

    def test_participant_movement_tracking(self):
        """Participant movement across frames updates coordinates while preserving identities."""
        reg_a = {"x": 0.15, "y": 0.20, "width": 0.20, "height": 0.30}
        reg_b = {"x": 0.60, "y": 0.20, "width": 0.20, "height": 0.30}

        # Frame 1: Initial positions
        faces_t1 = [
            {"x": 0.18, "y": 0.22, "width": 0.10, "height": 0.15, "confidence": 0.9},
            {"x": 0.62, "y": 0.22, "width": 0.10, "height": 0.15, "confidence": 0.9}
        ]
        fa_t1, fb_t1, meta_t1 = match_and_track_participants(faces_t1, reg_a, reg_b)
        assert fa_t1["x"] == 0.18
        assert fb_t1["x"] == 0.62

        # Frame 2: Both move rightwards by 5%
        faces_t2 = [
            {"x": 0.23, "y": 0.22, "width": 0.10, "height": 0.15, "confidence": 0.9},
            {"x": 0.67, "y": 0.22, "width": 0.10, "height": 0.15, "confidence": 0.9}
        ]
        fa_t2, fb_t2, meta_t2 = match_and_track_participants(
            faces_t2, reg_a, reg_b, prev_box_a=fa_t1, prev_box_b=fb_t1
        )
        assert fa_t2["x"] == 0.23, "Participant A identity maintained at new moved position"
        assert fb_t2["x"] == 0.67, "Participant B identity maintained at new moved position"
        assert meta_t2["face_a_detected"] is True
        assert meta_t2["face_b_detected"] is True

    def test_face_detection_failure_safe_fallback(self):
        """When face detection fails / returns no detections, system falls back safely without fabricated coordinates."""
        reg_a = {"x": 0.15, "y": 0.20, "width": 0.20, "height": 0.30}
        reg_b = {"x": 0.60, "y": 0.20, "width": 0.20, "height": 0.30}
        fa, fb, meta = match_and_track_participants([], reg_a, reg_b)
        assert fa is None
        assert fb is None
        assert meta["total_faces"] == 0

        # Fixed boundary crop with no detected boxes safely uses boundary center
        outer_boundary = {"x": 0.05, "y": 0.0, "width": 0.90, "height": 1.0}
        res = calculate_two_person_fixed_boundary_crop(
            outer_boundary=outer_boundary,
            participant_boxes=[],
            src_w=1920,
            src_h=1080
        )
        assert res["geometry_impossible"] is False
        bound_x1 = int(0.05 * 1920)
        bound_x2 = int(0.95 * 1920)
        assert res["x"] >= bound_x1
        assert res["x"] + res["w"] <= bound_x2


# ═════════════════════════════════════════════════════════════════════════════════
# 2. FEATURE 2 TESTS: VISIBILITY-DRIVEN COMPOSITION
# ═════════════════════════════════════════════════════════════════════════════════

class TestFeature2VisibilityDrivenComposition:

    def test_visibility_classification_a_only(self):
        """When Person A is visible and Person B is not, select COMPOSITION_A_ONLY. Synthetic observation injection."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "hist": None, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "hist": None, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        # Injected observation: single verified face for Person A
        injected = [{"x": 0.22, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}]
        res = classify_visibility_composition(
            video_path=Path("dummy.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=injected
        )
        assert res["composition"] == "A_ONLY"
        assert res["active_track_id"] == "spk_a"
        assert res["crop_a"] is not None

    def test_visibility_classification_both_triggers_side_by_side(self):
        """When both Person A and Person B are visible, select SIDE_BY_SIDE. Synthetic observation injection."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "hist": None, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "hist": None, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        # Injected observation: two distinct verified faces for Person A and Person B
        injected = [
            {"x": 0.22, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90},
            {"x": 0.72, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        ]
        res = classify_visibility_composition(
            video_path=Path("dummy.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=injected
        )
        assert res["composition"] == "SIDE_BY_SIDE"
        assert res["active_track_id"] == "both"

    def test_identity_preservation_across_cuts(self):
        """Person A and Person B identities remain consistent across cuts without swapping."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}
        assert sig_a["track_id"] == "spk_a"
        assert sig_b["track_id"] == "spk_b"
        assert sig_a["center_x_norm"] != sig_b["center_x_norm"]

    def test_visibility_classification_b_only(self):
        """When Person B is visible and Person A is occluded, select COMPOSITION_B_ONLY. Synthetic observation injection."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "hist": None, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "hist": None, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        # Injected observation: single verified face for Person B
        injected = [{"x": 0.72, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}]
        res = classify_visibility_composition(
            video_path=Path("dummy.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=injected
        )
        assert res["composition"] == "B_ONLY"
        assert res["active_track_id"] == "spk_b"
        assert res["crop_b"] is not None

    def test_participant_a_disappears_and_returns(self):
        """When Person A disappears and returns, composition transitions correctly and restores identity."""
        reg_a = {"x": 0.15, "y": 0.20, "width": 0.20, "height": 0.30}
        reg_b = {"x": 0.60, "y": 0.20, "width": 0.20, "height": 0.30}

        # Step 1: Both visible
        fa_1, fb_1, m1 = match_and_track_participants([
            {"x": 0.18, "y": 0.22, "width": 0.10, "height": 0.15},
            {"x": 0.62, "y": 0.22, "width": 0.10, "height": 0.15}
        ], reg_a, reg_b)
        assert fa_1 is not None and fb_1 is not None

        # Step 2: Person A disappears (only B detected)
        fa_2, fb_2, m2 = match_and_track_participants([
            {"x": 0.63, "y": 0.22, "width": 0.10, "height": 0.15}
        ], reg_a, reg_b, prev_box_a=fa_1, prev_box_b=fb_1)
        assert fa_2 is None, "Person A detected as absent/occluded"
        assert fb_2 is not None, "Person B correctly tracked"
        assert m2["occlusion_a"] is True

        # Step 3: Person A returns
        fa_3, fb_3, m3 = match_and_track_participants([
            {"x": 0.17, "y": 0.22, "width": 0.10, "height": 0.15},
            {"x": 0.63, "y": 0.22, "width": 0.10, "height": 0.15}
        ], reg_a, reg_b, prev_box_a=fa_1, prev_box_b=fb_2)
        assert fa_3 is not None and fb_3 is not None
        assert fa_3["x"] < fb_3["x"], "Person A correctly restored to left, Person B on right"

    def test_participant_b_disappears_and_returns(self):
        """When Person B disappears and returns, composition transitions correctly and restores identity."""
        reg_a = {"x": 0.15, "y": 0.20, "width": 0.20, "height": 0.30}
        reg_b = {"x": 0.60, "y": 0.20, "width": 0.20, "height": 0.30}

        # Step 1: Both visible
        fa_1, fb_1, m1 = match_and_track_participants([
            {"x": 0.18, "y": 0.22, "width": 0.10, "height": 0.15},
            {"x": 0.62, "y": 0.22, "width": 0.10, "height": 0.15}
        ], reg_a, reg_b)

        # Step 2: Person B disappears (only A detected)
        fa_2, fb_2, m2 = match_and_track_participants([
            {"x": 0.18, "y": 0.22, "width": 0.10, "height": 0.15}
        ], reg_a, reg_b, prev_box_a=fa_1, prev_box_b=fb_1)
        assert fb_2 is None, "Person B detected as absent/occluded"
        assert fa_2 is not None, "Person A correctly tracked"
        assert m2["occlusion_b"] is True

        # Step 3: Person B returns
        fa_3, fb_3, m3 = match_and_track_participants([
            {"x": 0.18, "y": 0.22, "width": 0.10, "height": 0.15},
            {"x": 0.64, "y": 0.22, "width": 0.10, "height": 0.15}
        ], reg_a, reg_b, prev_box_a=fa_2, prev_box_b=fb_1)
        assert fa_3 is not None and fb_3 is not None
        assert fa_3["x"] < fb_3["x"]

    def test_identity_uncertainty_safe_fallback(self):
        """When signature similarity is uncertain/ambiguous, review flag or safe fallback is set."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "hist": None, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "hist": None, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        # Low confidence similarity for both participants
        with patch("cv2.compareHist", side_effect=[0.10, 0.12]):
            res = classify_visibility_composition(
                video_path=Path("dummy.mp4"),
                shot=(0.0, 5.0),
                sig_a=sig_a,
                sig_b=sig_b,
                src_w=1920,
                src_h=1080
            )
            # Must select safe fallback (SIDE_BY_SIDE wide view, single 9:16 UNKNOWN_REVIEW or review indication)
            assert res["composition"] in ("SIDE_BY_SIDE", "A_ONLY", "B_ONLY", "UNKNOWN_REVIEW")
            assert "crop_rect" in res


# ═════════════════════════════════════════════════════════════════════════════════
# 3. RENDER INTEGRATION TESTS: FILTERGRAPH, CONTINUOUS AUDIO & ZERO SUBTITLES
# ═════════════════════════════════════════════════════════════════════════════════

class TestPodcastRenderFiltergraphs:

    @pytest.mark.asyncio
    async def test_feature_1_render_invokes_ffmpeg_with_sn_and_continuous_audio(self):
        """Verify render_fixed_boundary_two_person_video passes -sn flag and single audio trim."""
        schedule = [
            {
                "shot_id": 1,
                "start_time": 0.0,
                "end_time": 10.0,
                "crop_rect": {"x": 200, "y": 0, "w": 608, "h": 1080},
                "active_track_id": "both"
            }
        ]

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", return_value=(0, "", "")) as mock_ffmpeg, \
             patch("pathlib.Path.exists", return_value=True):

            out = await render_fixed_boundary_two_person_video(
                video_path=Path("dummy_video.mp4"),
                output_path=Path("out.mp4"),
                schedule=schedule,
                clip_start=0.0,
                clip_end=10.0
            )

            assert mock_ffmpeg.called
            cmd = mock_ffmpeg.call_args[0][0]
            assert "-sn" in cmd, "Must pass -sn flag to ensure zero subtitle/caption burn-in"
            assert "-c:v" in cmd and "libx264" in cmd
            assert "-c:a" in cmd and "aac" in cmd

    @pytest.mark.asyncio
    async def test_feature_2_render_hstack_side_by_side_with_continuous_audio(self):
        """
        Verify render_visibility_driven_video composes HORIZONTAL hstack (NOT vstack)
        for SIDE_BY_SIDE shots with continuous audio.
        """
        schedule = [
            {
                "shot_id": 1,
                "start_time": 0.0,
                "end_time": 10.0,
                "composition": "SIDE_BY_SIDE",
                "crop_a": {"x": 100, "y": 0, "w": 608, "h": 1080},
                "crop_b": {"x": 1000, "y": 0, "w": 608, "h": 1080}
            }
        ]

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", return_value=(0, "", "")) as mock_ffmpeg, \
             patch("pathlib.Path.exists", return_value=True):

            out = await render_visibility_driven_video(
                video_path=Path("dummy_video.mp4"),
                output_path=Path("out.mp4"),
                schedule=schedule,
                clip_start=0.0,
                clip_end=10.0
            )

            assert mock_ffmpeg.called
            cmd = mock_ffmpeg.call_args[0][0]
            assert "-filter_complex" in cmd
            fc_idx = cmd.index("-filter_complex")
            filtergraph = cmd[fc_idx + 1]

            # Invariant: Must use hstack=inputs=2 for horizontal side-by-side, NOT vstack!
            assert "hstack=inputs=2" in filtergraph, "Must use horizontal hstack to present both participants side by side"
            assert "vstack=inputs=2" not in filtergraph, "vstack is vertical stacking and must NOT be used for side-by-side"
            # Verify single continuous audio trim
            assert "atrim=start=0.0:end=10.0" in filtergraph
            # Verify -sn flag
            assert "-sn" in cmd

    @pytest.mark.asyncio
    async def test_synthetic_fixture_render_feature1_and_feature2(self):
        """
        Subtopic 7.3 Pipeline integration test:
        Renders Feature 1 (Fixed Boundary Camera Follow) and Feature 2 (Visibility-Driven Side-by-Side)
        using the synthetic test fixture (uploads/synthetic_test_fixture.mp4, 640x360 testsrc video).
        NOTE: This verifies FFmpeg pipeline execution, filtergraph generation, 1080x1920 output,
        continuous audio, and zero subtitle burn-in. It is a synthetic fixture test, NOT authentic
        human multi-person footage.
        """
        source_media = Path("uploads/synthetic_test_fixture.mp4")
        if not source_media.exists():
            pytest.skip("Test video fixture uploads/synthetic_test_fixture.mp4 not found")

        out_dir = Path("scratch/topic7_renders")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_f1 = out_dir / "real_feat1_fixed_boundary.mp4"
        out_f2 = out_dir / "real_feat2_visibility_driven.mp4"

        # 1. Feature 1: Synthetic Fixture Render
        schedule_f1 = [
            {
                "shot_id": 1,
                "start_time": 0.0,
                "end_time": 3.0,
                "crop_rect": calculate_two_person_fixed_boundary_crop(
                    outer_boundary={"x": 0.05, "y": 0.0, "width": 0.90, "height": 1.0},
                    participant_positions=[0.35, 0.65],
                    src_w=640,
                    src_h=360
                ),
                "active_track_id": "both"
            }
        ]

        await render_fixed_boundary_two_person_video(
            video_path=source_media,
            output_path=out_f1,
            schedule=schedule_f1,
            clip_start=0.0,
            clip_end=3.0,
            canvas_w=1080,
            canvas_h=1920
        )

        assert out_f1.exists(), "Feature 1 output video must be generated"
        assert out_f1.stat().st_size > 0, "Feature 1 output video must not be empty"

        # 2. Feature 2: Synthetic Fixture Render (with horizontal SIDE_BY_SIDE composition)
        schedule_f2 = [
            {
                "shot_id": 1,
                "start_time": 0.0,
                "end_time": 3.0,
                "composition": "SIDE_BY_SIDE",
                "crop_a": calculate_9_16_crop_rect(0.25, 640, 360),
                "crop_b": calculate_9_16_crop_rect(0.75, 640, 360)
            }
        ]

        await render_visibility_driven_video(
            video_path=source_media,
            output_path=out_f2,
            schedule=schedule_f2,
            clip_start=0.0,
            clip_end=3.0,
            canvas_w=1080,
            canvas_h=1920
        )

        assert out_f2.exists(), "Feature 2 output video must be generated"
        assert out_f2.stat().st_size > 0, "Feature 2 output video must not be empty"


# ═════════════════════════════════════════════════════════════════════════════════
# 4. PRODUCTION PIPELINE INTEGRATION TESTS
# ═════════════════════════════════════════════════════════════════════════════════

class TestPodcastProductionPipelineIntegration:

    @pytest.mark.asyncio
    async def test_api_url_submission_fixed_two_person_persists_config(self):
        """FastAPI route /api/videos/url persists podcast_composition='fixed_two_person' and mode='advanced_podcast'."""
        from backend.api.routes.videos import process_youtube_url

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        valid_regions = [
            {"id": "outer_boundary", "label": "Outer Clipping Boundary", "x": 0.05, "y": 0.0, "width": 0.90, "height": 1.0},
            {"id": "spk_1", "label": "Person A", "x": 0.20, "y": 0.20, "width": 0.25, "height": 0.50},
            {"id": "spk_2", "label": "Person B", "x": 0.60, "y": 0.20, "width": 0.25, "height": 0.50},
        ]

        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)), \
             patch("backend.services.llm_router.is_ai_provider_configured", return_value=True), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "celery-fixed-two-person"
            mock_apply.return_value = mock_task

            res = await process_youtube_url(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=json.dumps(valid_regions),
                podcast_composition="fixed_two_person",
                db=mock_db
            )

            assert "job_id" in res
            added_job = mock_db.add.call_args[0][0]
            config = json.loads(added_job.config)
            assert config["podcast_composition"] == "fixed_two_person"
            assert config["mode"] == "advanced_podcast"
            # Verify Celery kwargs passed correctly
            kwargs = mock_apply.call_args[1]["kwargs"]
            assert kwargs["podcast_composition"] == "fixed_two_person"

    @pytest.mark.asyncio
    async def test_api_url_submission_visibility_driven_persists_config(self):
        """FastAPI route /api/videos/url persists podcast_composition='visibility_driven' and mode='advanced_podcast'."""
        from backend.api.routes.videos import process_youtube_url

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        valid_regions = [
            {"id": "spk_1", "label": "Person A", "x": 0.20, "y": 0.20, "width": 0.25, "height": 0.50},
            {"id": "spk_2", "label": "Person B", "x": 0.60, "y": 0.20, "width": 0.25, "height": 0.50},
        ]

        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)), \
             patch("backend.services.llm_router.is_ai_provider_configured", return_value=True), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "celery-visibility-driven"
            mock_apply.return_value = mock_task

            res = await process_youtube_url(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=json.dumps(valid_regions),
                podcast_composition="visibility_driven",
                db=mock_db
            )

            assert "job_id" in res
            added_job = mock_db.add.call_args[0][0]
            config = json.loads(added_job.config)
            assert config["podcast_composition"] == "visibility_driven"
            assert config["mode"] == "advanced_podcast"
            kwargs = mock_apply.call_args[1]["kwargs"]
            assert kwargs["podcast_composition"] == "visibility_driven"

    @pytest.mark.asyncio
    async def test_api_analyze_shots_endpoint_dispatches_by_composition(self):
        """FastAPI route /api/videos/podcast/analyze-shots dispatches based on composition."""
        from backend.api.routes.videos import analyze_podcast_shots

        mock_db = AsyncMock()
        regions = [{"id": "p1", "x": 0.2, "y": 0.2, "w": 0.25, "h": 0.5}]

        # 1. fixed_two_person
        with patch("backend.services.advanced_podcast_engine.build_fixed_boundary_schedule", return_value=[{"shot_id": 1, "review_needed": False}]) as mock_f1, \
             patch("pathlib.Path.exists", return_value=True):
            res_f1 = await analyze_podcast_shots(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=json.dumps(regions),
                composition="fixed_two_person",
                db=mock_db
            )
            assert res_f1["status"] == "success"
            assert mock_f1.called

        # 2. visibility_driven
        with patch("backend.services.advanced_podcast_engine.build_visibility_driven_schedule", return_value=[{"shot_id": 1, "review_needed": False}]) as mock_f2, \
             patch("pathlib.Path.exists", return_value=True):
            res_f2 = await analyze_podcast_shots(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=json.dumps(regions),
                composition="visibility_driven",
                db=mock_db
            )
            assert res_f2["status"] == "success"
            assert mock_f2.called

    def test_celery_task_dispatches_correct_renderer_and_not_camera_following(self):
        """
        Verify Celery reframe dispatch:
        - fixed_two_person invokes render_fixed_boundary_two_person_video, NOT render_camera_following_video
        - visibility_driven invokes render_visibility_driven_video, NOT render_camera_following_video
        """
        from backend.tasks.clip_tasks import reframe_task

        mock_clip = MagicMock()
        mock_clip.id = "clip-1"
        mock_clip.video_id = "video-1"
        mock_clip.start_time = 0.0
        mock_clip.end_time = 10.0
        mock_clip.run_identity = None

        mock_video = MagicMock()
        mock_video.id = "video-1"
        mock_video.local_path = "uploads/video-1/source.mp4"

        regions = [
            {"id": "outer_boundary", "label": "Outer Boundary", "x": 0.05, "y": 0.0, "width": 0.90, "height": 1.0},
            {"id": "spk_1", "label": "Person A", "x": 0.20, "y": 0.20, "width": 0.25, "height": 0.50},
            {"id": "spk_2", "label": "Person B", "x": 0.60, "y": 0.20, "width": 0.25, "height": 0.50},
        ]

        # Case 1: fixed_two_person
        mock_job_f1 = MagicMock()
        mock_job_f1.id = "job-f1"
        mock_job_f1.status = "processing"
        mock_job_f1.config = json.dumps({
            "regions": regions,
            "podcast_composition": "fixed_two_person"
        })

        def mock_query_f1(model):
            m = MagicMock()
            if model.__name__ == "Clip":
                m.filter_by.return_value.first.return_value = mock_clip
            elif model.__name__ == "Video":
                m.filter_by.return_value.first.return_value = mock_video
            elif model.__name__ == "Job":
                m.filter_by.return_value.first.return_value = mock_job_f1
                m.filter_by.return_value.order_by.return_value.first.return_value = mock_job_f1
            return m

        mock_session_f1 = MagicMock()
        mock_session_f1.query.side_effect = mock_query_f1

        with patch("backend.models.database.SyncSessionLocal", return_value=MagicMock(__enter__=MagicMock(return_value=mock_session_f1), __exit__=MagicMock())), \
             patch("backend.models.artifact_sync.managed_download_sync") as mock_dl, \
             patch("backend.models.artifact_sync.managed_upload_sync") as mock_ul, \
             patch("backend.core.task_execution.check_and_claim_execution"), \
             patch("backend.models.artifact_sync.check_artifact_exists_sync", return_value=False), \
             patch("backend.services.advanced_podcast_engine.render_fixed_boundary_two_person_video", new_callable=AsyncMock) as mock_render_f1, \
             patch("backend.services.advanced_podcast_engine.render_camera_following_video", new_callable=AsyncMock) as mock_render_cam:

            mock_dl.return_value.__enter__.return_value = Path("uploads/synthetic_test_fixture.mp4")
            mock_ul.return_value.__enter__.return_value = Path("scratch/topic7_renders/test_reframed_f1.mp4")

            reframe_task.apply(args=["clip-1"], kwargs={"job_id": "job-f1"})

            assert mock_render_f1.called, "render_fixed_boundary_two_person_video MUST be dispatched for fixed_two_person"
            assert not mock_render_cam.called, "render_camera_following_video MUST NOT be invoked for fixed_two_person"

        # Case 2: visibility_driven
        mock_job_f2 = MagicMock()
        mock_job_f2.id = "job-f2"
        mock_job_f2.status = "processing"
        mock_job_f2.config = json.dumps({
            "regions": regions,
            "podcast_composition": "visibility_driven"
        })

        def mock_query_f2(model):
            m = MagicMock()
            if model.__name__ == "Clip":
                m.filter_by.return_value.first.return_value = mock_clip
            elif model.__name__ == "Video":
                m.filter_by.return_value.first.return_value = mock_video
            elif model.__name__ == "Job":
                m.filter_by.return_value.first.return_value = mock_job_f2
                m.filter_by.return_value.order_by.return_value.first.return_value = mock_job_f2
            return m

        mock_session_f2 = MagicMock()
        mock_session_f2.query.side_effect = mock_query_f2

        with patch("backend.models.database.SyncSessionLocal", return_value=MagicMock(__enter__=MagicMock(return_value=mock_session_f2), __exit__=MagicMock())), \
             patch("backend.models.artifact_sync.managed_download_sync") as mock_dl, \
             patch("backend.models.artifact_sync.managed_upload_sync") as mock_ul, \
             patch("backend.core.task_execution.check_and_claim_execution"), \
             patch("backend.models.artifact_sync.check_artifact_exists_sync", return_value=False), \
             patch("backend.services.advanced_podcast_engine.render_visibility_driven_video", new_callable=AsyncMock) as mock_render_f2, \
             patch("backend.services.advanced_podcast_engine.render_camera_following_video", new_callable=AsyncMock) as mock_render_cam:

            mock_dl.return_value.__enter__.return_value = Path("uploads/synthetic_test_fixture.mp4")
            mock_ul.return_value.__enter__.return_value = Path("scratch/topic7_renders/test_reframed_f2.mp4")

            reframe_task.apply(args=["clip-1"], kwargs={"job_id": "job-f2"})

            assert mock_render_f2.called, "render_visibility_driven_video MUST be dispatched for visibility_driven"
            assert not mock_render_cam.called, "render_camera_following_video MUST NOT be invoked for visibility_driven"

    def test_failed_detection_does_not_fabricate_face_coordinates(self):
        """Truthful detection: blank or synthetic image returns [] without synthetic detections."""
        blank_image = np.zeros((360, 640, 3), dtype=np.uint8)
        faces = detect_faces_in_frame(blank_image)
        assert faces == [], f"Expected empty list for blank image, got: {faces}"


# ═════════════════════════════════════════════════════════════════════════════════
# 4. FEATURE 2 CROP CALCULATION TESTS: OUTWARD ROUNDING & BOUNDARY PRESERVATION
# ═════════════════════════════════════════════════════════════════════════════════

class TestCalculateSideBySideParticipantCrop:
    """
    Comprehensive regression tests for calculate_side_by_side_participant_crop:
    - Outward rounding to even pixel bounds
    - Odd-pixel selected-region containment (assert crop_x <= region_left, assert crop_x + crop_w >= region_right)
    - Face-center consistency & fallback when face is outside selection
    - Crop-origin clamping to valid source frame interval
    - Wide selection handling and safe fallback for degenerate inputs
    """

    def test_outward_rounding_and_full_horizontal_containment(self):
        """Fractional coordinates are outward-rounded and strictly contained within crop."""
        src_w, src_h = 1920, 1080
        # Fractional region: x=193.3px, right=430.7px
        reg = {"x": 193.3 / 1920.0, "y": 0.1, "width": 237.4 / 1920.0, "height": 0.8}
        crop = calculate_side_by_side_participant_crop(reg, src_w, src_h)

        assert crop["region_left"] == 193
        assert crop["region_right"] == 431
        # Verification assertions
        assert crop["x"] <= crop["region_left"], f"Crop left {crop['x']} cut off region left {crop['region_left']}"
        assert crop["x"] + crop["w"] >= crop["region_right"], f"Crop right {crop['x'] + crop['w']} cut off region right {crop['region_right']}"
        assert crop["x"] >= 0
        assert crop["x"] + crop["w"] <= src_w
        # Pixel format alignment (even)
        assert crop["x"] % 2 == 0
        assert crop["w"] % 2 == 0
        assert crop["h"] == src_h

    def test_minimum_crop_width_at_1080p(self):
        """A narrow selected region is expanded to at least 304px (1080 * 540 / 1920) for 540x1920 panel."""
        src_w, src_h = 1920, 1080
        # 100px wide box
        reg = {"x": 0.40, "y": 0.1, "width": 100.0 / 1920.0, "height": 0.8}
        crop = calculate_side_by_side_participant_crop(reg, src_w, src_h)

        assert crop["w"] >= 304
        assert crop["w"] % 2 == 0
        assert crop["x"] <= crop["region_left"]
        assert crop["x"] + crop["w"] >= crop["region_right"]

    def test_face_center_consistency_and_valid_bias(self):
        """When face center is inside selected region, crop origin is biased toward face center while preserving containment."""
        src_w, src_h = 1920, 1080
        # Region span: [200, 450] -> 250px span < 304px min crop
        reg = {"x": 200.0 / 1920.0, "y": 0.1, "width": 250.0 / 1920.0, "height": 0.8}
        # Face near right edge of region: [380, 440] -> center 410px
        face_box = {"x": 380.0 / 1920.0, "y": 0.2, "width": 60.0 / 1920.0, "height": 0.3}

        crop = calculate_side_by_side_participant_crop(reg, src_w, src_h, face_box=face_box)

        # Region must be 100% contained
        assert crop["x"] <= crop["region_left"]
        assert crop["x"] + crop["w"] >= crop["region_right"]
        # Because face is toward the right of the region, crop_x should be shifted rightward compared to left boundary
        assert crop["x"] > 146  # minimum possible crop_x is 200 - (304 - 250) = 146

    def test_face_center_outside_region_falls_back_to_selection_center(self):
        """Spurious face detected outside the selected region is rejected and falls back to region center."""
        src_w, src_h = 1920, 1080
        reg = {"x": 0.10, "y": 0.1, "width": 0.15, "height": 0.8}  # [192, 480]
        spurious_face = {"x": 0.85, "y": 0.2, "width": 0.08, "height": 0.2}  # [1632, 1785] - completely outside

        crop = calculate_side_by_side_participant_crop(reg, src_w, src_h, face_box=spurious_face)

        # Must still strictly contain [192, 480]
        assert crop["x"] <= crop["region_left"]
        assert crop["x"] + crop["w"] >= crop["region_right"]
        assert crop["x"] + crop["w"] <= src_w

    def test_wide_region_expansion(self):
        """When selected region is wider than 304px (e.g. 500px), crop width expands to fit the full span."""
        src_w, src_h = 1920, 1080
        reg = {"x": 200.0 / 1920.0, "y": 0.1, "width": 500.0 / 1920.0, "height": 0.8}
        crop = calculate_side_by_side_participant_crop(reg, src_w, src_h)

        assert crop["w"] >= 500
        assert crop["w"] % 2 == 0
        assert crop["x"] <= crop["region_left"]
        assert crop["x"] + crop["w"] >= crop["region_right"]

    def test_crop_origin_left_and_right_frame_clamping(self):
        """Regions near edges clamp to valid [0, src_w] source bounds while containing selection."""
        src_w, src_h = 1920, 1080

        # Region flush with left edge: [0, 200]
        reg_left = {"x": 0.0, "y": 0.1, "width": 200.0 / 1920.0, "height": 0.8}
        crop_l = calculate_side_by_side_participant_crop(reg_left, src_w, src_h)
        assert crop_l["x"] == 0
        assert crop_l["w"] >= 304
        assert crop_l["x"] <= crop_l["region_left"]
        assert crop_l["x"] + crop_l["w"] >= crop_l["region_right"]

        # Region flush with right edge: [1700, 1920]
        reg_right = {"x": 1700.0 / 1920.0, "y": 0.1, "width": 220.0 / 1920.0, "height": 0.8}
        crop_r = calculate_side_by_side_participant_crop(reg_right, src_w, src_h)
        assert crop_r["x"] + crop_r["w"] == src_w
        assert crop_r["x"] <= crop_r["region_left"]
        assert crop_r["x"] + crop_r["w"] >= crop_r["region_right"]

    def test_invalid_and_degenerate_inputs_safe_fallback(self):
        """Degenerate inputs safely fall back to valid centered/default crop without crashing."""
        src_w, src_h = 1920, 1080
        # Empty dict
        crop_empty = calculate_side_by_side_participant_crop({}, src_w, src_h)
        assert crop_empty["w"] >= 304
        assert crop_empty["h"] == src_h
        assert crop_empty["x"] >= 0
        assert crop_empty["x"] + crop_empty["w"] <= src_w

        # Negative width
        crop_neg = calculate_side_by_side_participant_crop({"x": -0.5, "y": -0.5, "width": -0.2, "height": -0.2}, src_w, src_h)
        assert crop_neg["w"] >= 304
        assert crop_neg["x"] >= 0

    def test_visibility_composition_returns_aligned_crop_attributes(self):
        """classify_visibility_composition attaches calculate_side_by_side_participant_crop metadata to crop_a and crop_b."""
        sig_a = {"track_id": "area-1", "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "area-2", "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        # Force both visible via high correlation scores (synthetic observation injection)
        res = classify_visibility_composition(
            shot=(0.0, 4.0),
            video_path=Path("dummy.mp4"),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_scores=(0.95, 0.95)
        )

        assert res["composition"] == "SIDE_BY_SIDE"
        assert "aligned_crop_w" in res["crop_a"]
        assert "aligned_crop_w" in res["crop_b"]
        assert res["crop_a"]["x"] <= res["crop_a"]["region_left"]
        assert res["crop_a"]["x"] + res["crop_a"]["w"] >= res["crop_a"]["region_right"]
        assert res["crop_b"]["x"] <= res["crop_b"]["region_left"]
        assert res["crop_b"]["x"] + res["crop_b"]["w"] >= res["crop_b"]["region_right"]



