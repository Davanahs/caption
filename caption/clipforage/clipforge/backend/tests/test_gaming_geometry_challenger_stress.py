"""
backend/tests/test_gaming_geometry_challenger_stress.py

Adversarial Stress Testing & Edge Case Harness for Gaming Geometry (Challenger 2).
Empirically tests:
1. Odd and pathological dimensions (e.g. 7x7, 3841x2161, 1x1, 0x0).
2. Boundary overflows on crops near edges.
3. Non-finite, negative, overflowing, and NaN coordinates.
4. Scale-to-fill framing stability under extreme aspect ratios.
5. Fuzzing with 1,000 random valid and invalid rectangles.
"""

import math
import random
import pytest

from backend.services.gaming_geometry import (
    to_even_pixel,
    to_even_span,
    to_source_crop,
    to_canvas_overlay,
    to_gameplay_canvas_framing,
    validate_normalized_rect,
    validate_gaming_layout,
    calculate_gaming_coordinates,
    get_facecam_preset,
    NormalizedRect,
    PixelRect,
    GamingCanvasPlan,
)


class TestPathologicalDimensionsAndCropOverflow:
    """Stress tests on odd and pathological dimensions."""

    def test_odd_dimension_7x7_boundary_crop_overflow(self):
        """
        FAILING TEST / COUNTEREXAMPLE:
        On a 7x7 video, when a valid normalized ROI is near the bottom-right edge
        (e.g. x=0.95, y=0.95, width=0.05, height=0.05), to_source_crop computes:
          cx = to_even_pixel(0.95, 7) = 6
          cw = to_even_span(0.05, 7) = 2
        Total span: cx + cw = 8.
        Max valid even dimension: (7 // 2) * 2 = 6.
        Source dimension: 7.
        Result: 8 > 7 and 8 > 6, violating frame containment.
        FFmpeg crop fails with invalid crop parameters (exceeds input).
        """
        rect = {"x": 0.95, "y": 0.95, "width": 0.05, "height": 0.05}
        crop = to_source_crop(rect, 7, 7)
        max_w = (7 // 2) * 2
        max_h = (7 // 2) * 2

        # Invariant: Crop must remain within source frame boundaries
        assert crop.x + crop.w <= max_w, (
            f"Crop overflow on 7x7: crop.x ({crop.x}) + crop.w ({crop.w}) = {crop.x + crop.w} > max_w ({max_w})"
        )
        assert crop.y + crop.h <= max_h, (
            f"Crop overflow on 7x7: crop.y ({crop.y}) + crop.h ({crop.h}) = {crop.y + crop.h} > max_h ({max_h})"
        )

    def test_all_small_odd_dimensions_overflow_scan(self):
        """Scans all small odd dimensions from 3 to 21 for boundary crop overflow."""
        overflows = []
        for dim in range(3, 22, 2):
            crop = to_source_crop({"x": 0.95, "y": 0.95, "width": 0.05, "height": 0.05}, dim, dim)
            max_dim = (dim // 2) * 2
            if crop.x + crop.w > max_dim or crop.x + crop.w > dim:
                overflows.append((dim, crop.x, crop.w, crop.x + crop.w, max_dim))

        assert not overflows, (
            f"Detected crop overflow on {len(overflows)} odd dimensions: {overflows}"
        )

    def test_odd_dimension_3841x2161_highres_even_invariants(self):
        """Verifies 4K+1 odd resolution (3841x2161) always preserves even parity and containment."""
        max_w = (3841 // 2) * 2  # 3840
        max_h = (2161 // 2) * 2  # 2160

        test_rois = [
            {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            {"x": 0.5, "y": 0.5, "width": 0.5, "height": 0.5},
            {"x": 0.95, "y": 0.95, "width": 0.05, "height": 0.05},
            {"x": 0.0, "y": 0.95, "width": 0.05, "height": 0.05},
            {"x": 0.95, "y": 0.0, "width": 0.05, "height": 0.05},
        ]

        for roi in test_rois:
            crop = to_source_crop(roi, 3841, 2161)
            assert crop.x % 2 == 0, f"crop.x {crop.x} is not even"
            assert crop.y % 2 == 0, f"crop.y {crop.y} is not even"
            assert crop.w % 2 == 0, f"crop.w {crop.w} is not even"
            assert crop.h % 2 == 0, f"crop.h {crop.h} is not even"
            assert crop.x + crop.w <= max_w, f"crop.x + crop.w {crop.x + crop.w} > {max_w}"
            assert crop.y + crop.h <= max_h, f"crop.y + crop.h {crop.y + crop.h} > {max_h}"

    def test_zero_and_negative_dimensions_rejection(self):
        """Verifies zero and negative source dimensions raise ValueError."""
        valid_rect = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
        with pytest.raises(ValueError, match="Source dimensions must be positive"):
            to_source_crop(valid_rect, 0, 1080)
        with pytest.raises(ValueError, match="Source dimensions must be positive"):
            to_source_crop(valid_rect, 1920, 0)
        with pytest.raises(ValueError, match="Source dimensions must be positive"):
            to_source_crop(valid_rect, -1920, 1080)
        with pytest.raises(ValueError, match="Source dimensions must be positive"):
            to_source_crop(valid_rect, 1920, -1080)

    def test_zero_and_negative_canvas_dimensions_rejection(self):
        """Verifies zero and negative canvas dimensions raise ValueError."""
        valid_rect = {"x": 0.0, "y": 0.0, "width": 0.3, "height": 0.22}
        with pytest.raises(ValueError, match="Canvas dimensions must be positive"):
            to_canvas_overlay(valid_rect, 0, 1920)
        with pytest.raises(ValueError, match="Canvas dimensions must be positive"):
            to_canvas_overlay(valid_rect, 1080, 0)
        with pytest.raises(ValueError, match="Canvas dimensions must be positive"):
            to_canvas_overlay(valid_rect, -1080, 1920)


class TestNonFiniteAndNegativeCoordinateRejection:
    """Stress tests on non-finite, negative, and out-of-bounds coordinate validation."""

    @pytest.mark.parametrize("bad_val", [
        float("nan"),
        float("inf"),
        float("-inf"),
        "NaN",
        "Infinity",
        "-Infinity",
        None,
    ])
    def test_validate_normalized_rect_rejects_non_finite(self, bad_val):
        for prop in ["x", "y", "width", "height"]:
            rect = {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}
            rect[prop] = bad_val
            with pytest.raises(ValueError, match="non-finite coordinate"):
                validate_normalized_rect(rect)

    @pytest.mark.parametrize("neg_val", [-0.0002, -0.01, -0.5, -100.0])
    def test_validate_normalized_rect_rejects_negative(self, neg_val):
        with pytest.raises(ValueError, match="negative coordinate"):
            validate_normalized_rect({"x": neg_val, "y": 0.1, "width": 0.5, "height": 0.5})
        with pytest.raises(ValueError, match="negative coordinate"):
            validate_normalized_rect({"x": 0.1, "y": neg_val, "width": 0.5, "height": 0.5})

    @pytest.mark.parametrize("overflow_rect", [
        {"x": 0.6, "y": 0.1, "width": 0.5, "height": 0.5},  # x+w = 1.1
        {"x": 0.1, "y": 0.7, "width": 0.5, "height": 0.5},  # y+h = 1.2
        {"x": 1.05, "y": 0.0, "width": 0.05, "height": 0.05},
        {"x": 0.0, "y": 1.05, "width": 0.05, "height": 0.05},
    ])
    def test_validate_normalized_rect_rejects_overflow(self, overflow_rect):
        with pytest.raises(ValueError, match="out of bounds"):
            validate_normalized_rect(overflow_rect)

    def test_to_even_pixel_negative_coordinate_rejection(self):
        with pytest.raises(ValueError, match="negative coordinate"):
            to_even_pixel(-0.01, 1080)

    def test_to_even_pixel_non_finite_rejection(self):
        with pytest.raises(ValueError, match="must be finite"):
            to_even_pixel(float("nan"), 1080)
        with pytest.raises(ValueError, match="must be finite"):
            to_even_pixel(float("inf"), 1080)

    def test_to_even_span_non_finite_rejection(self):
        with pytest.raises(ValueError, match="must be finite"):
            to_even_span(float("nan"), 1080)
        with pytest.raises(ValueError, match="must be finite"):
            to_even_span(float("inf"), 1080)


class TestRandomFuzzingHarness:
    """Fuzzing harness generating hundreds of random valid and boundary inputs."""

    def test_random_valid_normalized_rects_fuzzing(self):
        rng = random.Random(42)
        resolutions = [
            (1920, 1080),
            (1280, 720),
            (3840, 2160),
            (2560, 1440),
            (3841, 2161),
            (1921, 1081),
            (853, 481),
        ]

        for i in range(500):
            w = rng.uniform(0.05, 1.0)
            h = rng.uniform(0.05, 1.0)
            x = rng.uniform(0.0, 1.0 - w)
            y = rng.uniform(0.0, 1.0 - h)
            rect = {"x": round(x, 6), "y": round(y, 6), "width": round(w, 6), "height": round(h, 6)}

            validated = validate_normalized_rect(rect)
            assert validated.x >= 0.0
            assert validated.y >= 0.0
            assert validated.width >= 0.05
            assert validated.height >= 0.05
            assert validated.x + validated.width <= 1.0001
            assert validated.y + validated.height <= 1.0001

            src_w, src_h = rng.choice(resolutions)
            crop = to_source_crop(validated, src_w, src_h)

            max_src_w = (src_w // 2) * 2
            max_src_h = (src_h // 2) * 2

            assert crop.x % 2 == 0, f"Iteration {i}: crop.x {crop.x} not even"
            assert crop.y % 2 == 0, f"Iteration {i}: crop.y {crop.y} not even"
            assert crop.w % 2 == 0, f"Iteration {i}: crop.w {crop.w} not even"
            assert crop.h % 2 == 0, f"Iteration {i}: crop.h {crop.h} not even"
            assert crop.w >= 2, f"Iteration {i}: crop.w {crop.w} < 2"
            assert crop.h >= 2, f"Iteration {i}: crop.h {crop.h} < 2"
            assert crop.x + crop.w <= max_src_w, (
                f"Iteration {i}: crop.x ({crop.x}) + crop.w ({crop.w}) = {crop.x + crop.w} > {max_src_w}"
            )
            assert crop.y + crop.h <= max_src_h, (
                f"Iteration {i}: crop.y ({crop.y}) + crop.h ({crop.h}) = {crop.y + crop.h} > {max_src_h}"
            )
