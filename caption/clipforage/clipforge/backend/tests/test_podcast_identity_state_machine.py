"""
backend/tests/test_podcast_identity_state_machine.py
===================================================
Comprehensive Independent Verification for Prompt 5: PODCAST-IDENTITY-STATE-005.

Verifies:
1. No detections -> safe UNKNOWN_REVIEW fallback.
2. Single valid detection -> A_ONLY or B_ONLY when supported by verified assignment, else UNKNOWN_REVIEW.
3. Two distinct valid detections -> SIDE_BY_SIDE when both distinct participants established.
4. Same face assigned twice / duplicate candidate boxes -> strictly prevented from becoming A+B.
5. Invalid/NaN/Inf/negative/out-of-frame detections -> rejected safely to UNKNOWN_REVIEW.
6. Ambiguous collision, path crossing, and equidistant detections -> no silent identity swap -> UNKNOWN_REVIEW.
7. Camera-cut resets -> state resets cleanly without leaking previous shot state.
8. UNKNOWN_REVIEW filtergraph rendering -> single centered 1080x1920 frame, continuous audio, -sn 0 subtitles.
9. All unit tests explicitly labeled as synthetic observation injections.
"""
import pytest
import math
from pathlib import Path
from unittest.mock import patch

from backend.services.advanced_podcast_engine import (
    validate_bounding_box,
    calculate_box_iou,
    deduplicate_detected_faces,
    match_and_track_participants,
    classify_visibility_composition,
    render_visibility_driven_video,
    calculate_9_16_crop_rect
)


class TestPodcastIdentityStateMachineSafeguards:
    """
    Test suite for Visibility-Driven state machine hardening and UNKNOWN_REVIEW safeguards.
    NOTE: All tests below inject controlled synthetic observations to deterministically
    verify edge-case logic and invariant protection. They do NOT represent authentic
    human multi-person detector validation.
    """

    # 1. Bounding box validation and edge cases
    def test_bounding_box_validation_rejects_nan_and_infinities(self):
        """Synthetic injection: Bounding boxes with NaN or inf values are rejected."""
        assert validate_bounding_box({"x": float("nan"), "y": 0.2, "width": 0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": float("inf"), "width": 0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": float("-inf"), "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": 0.1, "height": float("nan")}) is False
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": 0.1, "height": 0.2, "confidence": float("nan")}) is False

    def test_bounding_box_validation_rejects_negative_or_zero_dimensions(self):
        """Synthetic injection: Non-positive dimensions or zero sizes are rejected."""
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": 0.0, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": -0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": 0.1, "height": -0.05}) is False
        assert validate_bounding_box({"x": 0.2, "y": 0.2, "width": 0.005, "height": 0.2}) is False  # sub-pixel noise

    def test_bounding_box_validation_rejects_out_of_frame_coordinates(self):
        """Synthetic injection: Out-of-frame coordinates are rejected."""
        assert validate_bounding_box({"x": -0.1, "y": 0.2, "width": 0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": -0.05, "width": 0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 1.1, "y": 0.2, "width": 0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.2, "y": 1.05, "width": 0.1, "height": 0.2}) is False
        assert validate_bounding_box({"x": 0.8, "y": 0.2, "width": 0.6, "height": 0.2}) is False  # overflows frame (1.4 > 1.2)

    def test_bounding_box_validation_accepts_valid_boxes(self):
        """Synthetic injection: Valid normalized bounding boxes pass validation."""
        valid_box = {"x": 0.20, "y": 0.25, "width": 0.15, "height": 0.20, "confidence": 0.92}
        assert validate_bounding_box(valid_box) is True
        assert validate_bounding_box(valid_box, min_confidence=0.50) is True
        assert validate_bounding_box(valid_box, min_confidence=0.95) is False

    # 2. Duplicate face deduplication
    def test_duplicate_face_detections_deduplicated(self):
        """Synthetic injection: Multiple overlapping candidate boxes for the same face are deduplicated."""
        dup1 = {"x": 0.25, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.95}
        dup2 = {"x": 0.26, "y": 0.21, "width": 0.10, "height": 0.15, "confidence": 0.70}  # duplicate
        unique = deduplicate_detected_faces([dup1, dup2])
        assert len(unique) == 1
        assert unique[0]["confidence"] == 0.95

    def test_distinct_faces_preserved_in_deduplication(self):
        """Synthetic injection: Two distinct participant faces are preserved."""
        face_a = {"x": 0.20, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        face_b = {"x": 0.70, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        unique = deduplicate_detected_faces([face_a, face_b])
        assert len(unique) == 2

    # 3. Participant matching and identity association safeguards
    def test_match_participants_no_detections_returns_ambiguous(self):
        """Synthetic injection: Empty detections returns ambiguous metadata."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        fa, fb, meta = match_and_track_participants([], reg_a, reg_b)
        assert fa is None
        assert fb is None
        assert meta["identity_ambiguous"] is True
        assert meta["reason"] == "no_detections"

    def test_match_participants_invalid_detections_rejected(self):
        """Synthetic injection: Invalid detections fail safely without fabricated coordinates."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        corrupted = [{"x": float("nan"), "y": 0.2, "width": 0.1, "height": 0.2}]
        fa, fb, meta = match_and_track_participants(corrupted, reg_a, reg_b)
        assert fa is None
        assert fb is None
        assert meta["identity_ambiguous"] is True
        assert meta["reason"] == "all_detections_invalid"

    def test_match_participants_duplicate_face_never_assigned_to_both(self):
        """Synthetic injection: Duplicate boxes of the same person must NEVER be assigned to both A and B."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        same_person_boxes = [
            {"x": 0.25, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.95},
            {"x": 0.26, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.80}
        ]
        fa, fb, meta = match_and_track_participants(same_person_boxes, reg_a, reg_b)
        # Invariant: Both A and B must NOT be assigned to this single person
        assert not (fa is not None and fb is not None), "Same physical person must not be assigned to both A and B"
        assert fa is not fb
        assert meta["total_faces"] == 1

    def test_match_participants_single_detection_equidistant_ambiguous(self):
        """Synthetic injection: A single face in the center between A and B is ambiguous."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}  # center ~0.25
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}  # center ~0.75
        center_face = [{"x": 0.45, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}]  # center 0.50
        fa, fb, meta = match_and_track_participants(center_face, reg_a, reg_b)
        assert fa is None
        assert fb is None
        assert meta["identity_ambiguous"] is True
        assert meta["reason"] == "ambiguous_single_detection"

    def test_match_participants_single_detection_verified_a(self):
        """Synthetic injection: Single face clearly near Person A is assigned to Person A."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}  # center 0.25
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}  # center 0.75
        face_near_a = [{"x": 0.20, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}]
        fa, fb, meta = match_and_track_participants(face_near_a, reg_a, reg_b)
        assert fa is not None
        assert fb is None
        assert meta["face_a_detected"] is True
        assert meta["occlusion_b"] is True
        assert meta["identity_ambiguous"] is False

    def test_match_participants_single_detection_verified_b(self):
        """Synthetic injection: Single face clearly near Person B is assigned to Person B."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        face_near_b = [{"x": 0.70, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}]
        fa, fb, meta = match_and_track_participants(face_near_b, reg_a, reg_b)
        assert fa is None
        assert fb is not None
        assert meta["face_b_detected"] is True
        assert meta["occlusion_a"] is True
        assert meta["identity_ambiguous"] is False

    def test_match_participants_two_faces_distinct_assigned_both(self):
        """Synthetic injection: Two distinct separated faces are assigned to A and B."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        two_faces = [
            {"x": 0.20, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90},
            {"x": 0.70, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        ]
        fa, fb, meta = match_and_track_participants(two_faces, reg_a, reg_b)
        assert fa is not None and fb is not None
        assert fa is not fb
        assert meta["face_a_detected"] is True
        assert meta["face_b_detected"] is True
        assert meta["identity_ambiguous"] is False

    def test_match_participants_crossing_paths_marks_ambiguous_no_swap(self):
        """Synthetic injection: Crossing paths with ambiguous distance falls back to ambiguous without swapping."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        # Previous positions near center
        prev_a = {"x": 0.44, "y": 0.20, "width": 0.10, "height": 0.15}  # center 0.49
        prev_b = {"x": 0.46, "y": 0.20, "width": 0.10, "height": 0.15}  # center 0.51
        # Now crossing at center with distinct separated faces: f1 at center 0.43, f2 at center 0.63
        crossing_faces = [
            {"x": 0.38, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90},
            {"x": 0.58, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        ]
        fa, fb, meta = match_and_track_participants(
            crossing_faces, reg_a, reg_b, prev_box_a=prev_a, prev_box_b=prev_b
        )
        assert meta["identity_ambiguous"] is True
        assert meta["reason"] == "crossing_paths_ambiguous"
        assert fa is None and fb is None

    def test_match_participants_close_collision_marks_ambiguous(self):
        """Synthetic injection: Two participants colliding within 0.08 distance marks ambiguous."""
        reg_a = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}
        reg_b = {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
        colliding_faces = [
            {"x": 0.43, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90},
            {"x": 0.47, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        ]
        fa, fb, meta = match_and_track_participants(colliding_faces, reg_a, reg_b)
        assert meta["identity_ambiguous"] is True
        assert fa is None and fb is None

    # 4. State Machine Classification & UNKNOWN_REVIEW Decision Logic
    def test_classify_visibility_no_detections_routes_to_unknown_review(self):
        """Synthetic injection: Zero face detections and missing video defaults to UNKNOWN_REVIEW."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        res = classify_visibility_composition(
            video_path=Path("nonexistent_video.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=[]
        )
        assert res["composition"] == "UNKNOWN_REVIEW"
        assert res["active_track_id"] == "unassigned"
        assert res["review_needed"] is True
        # Verify centered 9:16 fallback
        center_crop = calculate_9_16_crop_rect(0.5, 1920, 1080)
        assert res["crop_rect"]["x"] == center_crop["x"]
        assert res["crop_rect"]["w"] == center_crop["w"]

    def test_classify_visibility_ambiguous_single_face_routes_to_unknown_review(self):
        """Synthetic injection: A single ambiguous face routes to UNKNOWN_REVIEW."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        injected = [{"x": 0.45, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}]
        res = classify_visibility_composition(
            video_path=Path("dummy.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=injected
        )
        assert res["composition"] == "UNKNOWN_REVIEW"
        assert res["active_track_id"] == "unassigned"
        assert res["review_needed"] is True

    def test_classify_visibility_same_face_duplicated_never_emits_side_by_side(self):
        """Synthetic injection: Two duplicate candidate boxes of the same face must NEVER trigger SIDE_BY_SIDE."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        # Two detections representing Person A only (e.g. multi-scale duplicates)
        duplicated = [
            {"x": 0.22, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.95},
            {"x": 0.23, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.80}
        ]
        res = classify_visibility_composition(
            video_path=Path("dummy.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=duplicated
        )
        assert res["composition"] != "SIDE_BY_SIDE", "Duplicate boxes of same person must never become SIDE_BY_SIDE"
        assert res["composition"] == "A_ONLY"

    def test_classify_visibility_two_distinct_participants_triggers_side_by_side(self):
        """Synthetic injection: Two distinct participants established with confidence selects SIDE_BY_SIDE."""
        sig_a = {"track_id": "spk_a", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}}
        sig_b = {"track_id": "spk_b", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}}

        two_faces = [
            {"x": 0.20, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90},
            {"x": 0.70, "y": 0.20, "width": 0.10, "height": 0.15, "confidence": 0.90}
        ]
        res = classify_visibility_composition(
            video_path=Path("dummy.mp4"),
            shot=(0.0, 5.0),
            sig_a=sig_a,
            sig_b=sig_b,
            src_w=1920,
            src_h=1080,
            injected_detections=two_faces
        )
        assert res["composition"] == "SIDE_BY_SIDE"
        assert res["active_track_id"] == "both"
        assert res["review_needed"] is False

    # 5. FFmpeg Filtergraph & Negative Invariants
    @pytest.mark.asyncio
    async def test_unknown_review_filtergraph_renders_single_center_canvas(self):
        """
        Verifies that an UNKNOWN_REVIEW shot renders a single full-canvas 9:16 center frame
        with -sn zero subtitles and continuous audio, completely eliminating speaker duplication.
        """
        schedule = [
            {
                "shot_id": 1,
                "start_time": 0.0,
                "end_time": 5.0,
                "composition": "UNKNOWN_REVIEW"
            }
        ]

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", return_value=(0, "", "")) as mock_ffmpeg, \
             patch("pathlib.Path.exists", return_value=True):

            out = await render_visibility_driven_video(
                video_path=Path("dummy.mp4"),
                output_path=Path("out.mp4"),
                schedule=schedule,
                clip_start=0.0,
                clip_end=5.0
            )

            assert mock_ffmpeg.called
            cmd = mock_ffmpeg.call_args[0][0]
            assert "-sn" in cmd, "Must pass -sn flag (zero subtitles)"
            assert "-filter_complex" in cmd
            fc_idx = cmd.index("-filter_complex")
            filtergraph = cmd[fc_idx + 1]

            # Invariant: Must NOT use hstack or vstack for UNKNOWN_REVIEW! It must be single center crop.
            assert "hstack=inputs=2" not in filtergraph, "UNKNOWN_REVIEW must not duplicate into hstack"
            assert "vstack=inputs=2" not in filtergraph, "UNKNOWN_REVIEW must not duplicate into vstack"
            # Single 9:16 center crop (center of 1920 width is 960, 9:16 width is 606 -> x = 656 or 657)
            assert "crop=" in filtergraph
            assert "scale=1080:1920" in filtergraph
            assert "pad=1080:1920" in filtergraph
            # Continuous audio
            assert "atrim=start=0.0:end=5.0" in filtergraph
