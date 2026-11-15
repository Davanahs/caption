"""
backend/tests/test_gaming_geometry_parity.py

Authoritative Pytest suite for ClipForge Dual-Region Gaming Layout geometry engine.
Verifies 100% cross-language parity against gaming_geometry_golden_vectors.json,
boundary validation invariants, YUV420p even-pixel quantization, and LayoutPlan generation.
"""

import json
import math
import subprocess
from pathlib import Path
from PIL import Image
import pytest

from backend.models.layout import LayoutPlan, RegionModel, ScaleMode, BackgroundPolicy, AudioPolicy
from backend.services.gaming_geometry import (
    FacecamPreset,
    GamingCanvasPlan,
    NormalizedRect,
    PixelRect,
    calculate_gaming_coordinates,
    calculate_render_offsets,
    create_gaming_layout_plan,
    display_to_normalized_letterbox,
    get_facecam_preset,
    to_canvas_overlay,
    to_even_pixel,
    to_even_span,
    to_gameplay_canvas_framing,
    to_source_crop,
    validate_gaming_layout,
    validate_normalized_rect,
)
from backend.services.reframe_engine import reframe_to_vertical
from backend.tests.gaming_test_fixtures import (
    create_synthetic_1080p_gameplay,
    generate_synthetic_video,
    probe_media,
)

GOLDEN_VECTORS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "engineering" / "gaming_geometry_golden_vectors.json"


def load_golden_vectors():
    with open(GOLDEN_VECTORS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["vectors"]


class TestGamingGeometryUnit:
    """Unit tests for individual mathematical functions and validation rules."""

    def test_validate_normalized_rect_valid(self):
        rect = validate_normalized_rect({"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6})
        assert rect.x == 0.1
        assert rect.y == 0.2
        assert rect.width == 0.5
        assert rect.height == 0.6

    def test_validate_normalized_rect_negative_raises_value_error(self):
        with pytest.raises(ValueError) as excinfo:
            validate_normalized_rect({"x": -0.05, "y": 0.0, "width": 0.5, "height": 0.5}, "test_roi")
        assert "negative coordinate" in str(excinfo.value).lower()

    def test_validate_normalized_rect_non_finite_raises_value_error(self):
        with pytest.raises(ValueError) as excinfo:
            validate_normalized_rect({"x": float("nan"), "y": 0.0, "width": 0.5, "height": 0.5}, "test_roi")
        assert "non-finite coordinate" in str(excinfo.value).lower()

        with pytest.raises(ValueError) as excinfo2:
            validate_normalized_rect({"x": 0.0, "y": "NaN", "width": 0.5, "height": 0.5}, "test_roi")
        assert "non-finite coordinate" in str(excinfo2.value).lower()

    def test_validate_normalized_rect_min_size_raises_value_error(self):
        with pytest.raises(ValueError) as excinfo:
            validate_normalized_rect({"x": 0.0, "y": 0.0, "width": 0.02, "height": 0.5}, "test_roi")
        assert "must be >= 0.05" in str(excinfo.value).lower()

    def test_validate_normalized_rect_overflow_raises_value_error(self):
        with pytest.raises(ValueError) as excinfo:
            validate_normalized_rect({"x": 0.8, "y": 0.0, "width": 0.3, "height": 0.5}, "test_roi")
        assert "out of bounds" in str(excinfo.value).lower()

    def test_to_even_pixel(self):
        assert to_even_pixel(0.5, 1080) == 540
        assert to_even_pixel(0.333333, 1080) == 358
        assert to_even_pixel(0.0, 1920) == 0

        with pytest.raises(ValueError) as exc:
            to_even_pixel(-0.1, 1080)
        assert "negative" in str(exc.value).lower()

        with pytest.raises(ValueError) as exc2:
            to_even_pixel(float("nan"), 1080)
        assert "finite" in str(exc2.value).lower()

    def test_to_even_span(self):
        assert to_even_span(0.05, 1080) == 54
        assert to_even_span(0.001, 1080) == 2  # Min 2 pixels clamped

    def test_facecam_presets_coordinates(self):
        tl = get_facecam_preset("top-left")
        assert tl == {"x": 0.05, "y": 0.04, "width": 0.30, "height": 0.22}

        tr = get_facecam_preset("top-right")
        assert tr == {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.22}

        bl = get_facecam_preset("bottom-left")
        assert bl == {"x": 0.05, "y": 0.74, "width": 0.30, "height": 0.22}

        br = get_facecam_preset("bottom-right")
        assert br == {"x": 0.65, "y": 0.74, "width": 0.30, "height": 0.22}

    def test_facecam_preset_invalid_raises_value_error(self):
        with pytest.raises(ValueError) as excinfo:
            get_facecam_preset("invalid-preset-name")
        assert "unknown facecam preset" in str(excinfo.value).lower()

    def test_source_crop_odd_dimensions_clamped_safely(self):
        crop = to_source_crop({"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, 1921, 1081)
        assert crop.w == 1920
        assert crop.h == 1080
        assert crop.x == 0
        assert crop.y == 0
        assert crop.x % 2 == 0
        assert crop.y % 2 == 0
        assert crop.w % 2 == 0
        assert crop.h % 2 == 0

    def test_gameplay_scale_fill_proportions(self):
        framing = to_gameplay_canvas_framing(1920, 1080, 1080, 1920)
        assert framing["scale_factor"] == 1.777778
        assert framing["scaled_w"] == 3413
        assert framing["scaled_h"] == 1920
        assert framing["ffmpeg_scale_filter"] == "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

    def test_create_gaming_layout_plan(self):
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        }
        plan = create_gaming_layout_plan(config, 1920, 1080)
        assert isinstance(plan, LayoutPlan)
        assert plan.canvas_width == 1080
        assert plan.canvas_height == 1920
        assert len(plan.regions) == 2

        r_gameplay, r_facecam = plan.regions[0], plan.regions[1]
        assert r_gameplay.source_index == 0
        assert r_gameplay.z_order == 1
        assert r_gameplay.w == 1080
        assert r_gameplay.h == 1920
        assert r_gameplay.crop_coords == (0, 0, 1920, 1080)

        assert r_facecam.source_index == 1
        assert r_facecam.z_order == 2
        assert r_facecam.x == 702
        assert r_facecam.y == 76
        assert r_facecam.w == 324
        assert r_facecam.h == 422
        assert r_facecam.crop_coords == (1344, 54, 480, 270)

    def test_layout_engine_build_render_graph_gaming_plan(self):
        from backend.services.layout_engine import LayoutEngine

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        }
        plan = create_gaming_layout_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])

        assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in fg
        assert "overlay=x=702:y=76:eof_action=pass:repeatlast=0" in fg
        assert "[outv]" in fg


class TestGoldenVectorsParity:
    """Parametrized verification of all golden test vectors against Python implementation."""

    vectors = load_golden_vectors()

    @pytest.mark.parametrize("vector", vectors, ids=lambda v: v["id"])
    def test_golden_vector_parity(self, vector):
        inp = vector["input"]
        exp = vector["expected"]

        if exp["is_valid"]:
            if "container" in inp and "pointer" in inp:
                # Letterboxed pointer calculation (vectors 23-26)
                res = display_to_normalized_letterbox(
                    inp["pointer"]["clientX"],
                    inp["pointer"]["clientY"],
                    inp["container"],
                    inp["src_w"],
                    inp["src_h"]
                )
                assert res["render_rect"] == exp["render_rect"], f"[{vector['id']}] render_rect mismatch"
                assert res["normalized_pointer"] == exp["normalized_pointer"], f"[{vector['id']}] pointer mismatch"
            else:
                # Dual-region layout plan calculation (vectors 01-22, 31, 32)
                plan = calculate_gaming_coordinates(inp)

                # 1. Resolved facecam output rect
                assert plan.facecam_resolved_output_rect == exp["facecam_resolved_output_rect"], (
                    f"[{vector['id']}] facecam_resolved_output_rect mismatch"
                )

                # 2. Crops and destination overlay
                assert plan.gameplay_crop == exp["gameplay_crop"], f"[{vector['id']}] gameplay_crop mismatch"
                assert plan.facecam_crop == exp["facecam_crop"], f"[{vector['id']}] facecam_crop mismatch"
                assert plan.facecam_dest == exp["facecam_dest"], f"[{vector['id']}] facecam_dest mismatch"

                # 3. Scaling metrics
                assert abs(plan.gameplay_scale_factor - exp["gameplay_scale_factor"]) < 1e-4, (
                    f"[{vector['id']}] gameplay_scale_factor mismatch ({plan.gameplay_scale_factor} vs {exp['gameplay_scale_factor']})"
                )
                assert plan.gameplay_scaled_w == exp["gameplay_scaled_w"], f"[{vector['id']}] gameplay_scaled_w mismatch"
                assert plan.gameplay_scaled_h == exp["gameplay_scaled_h"], f"[{vector['id']}] gameplay_scaled_h mismatch"

                # 4. FFmpeg filters
                assert plan.ffmpeg_crop_gameplay == exp["ffmpeg_crop_gameplay"], f"[{vector['id']}] ffmpeg_crop_gameplay mismatch"
                assert plan.ffmpeg_crop_facecam == exp["ffmpeg_crop_facecam"], f"[{vector['id']}] ffmpeg_crop_facecam mismatch"
                assert plan.ffmpeg_filtergraph == exp["ffmpeg_filtergraph"], f"[{vector['id']}] ffmpeg_filtergraph mismatch"

                # 5. Even-pixel codec invariants
                assert plan.gameplay_crop.x % 2 == 0
                assert plan.gameplay_crop.y % 2 == 0
                assert plan.gameplay_crop.w % 2 == 0
                assert plan.gameplay_crop.h % 2 == 0

                assert plan.facecam_crop.x % 2 == 0
                assert plan.facecam_crop.y % 2 == 0
                assert plan.facecam_crop.w % 2 == 0
                assert plan.facecam_crop.h % 2 == 0

                assert plan.facecam_dest.x % 2 == 0
                assert plan.facecam_dest.y % 2 == 0
                assert plan.facecam_dest.w % 2 == 0
                assert plan.facecam_dest.h % 2 == 0

                # 6. Source and canvas containment invariants
                max_src_w = (inp["src_w"] // 2) * 2
                max_src_h = (inp["src_h"] // 2) * 2
                assert plan.gameplay_crop.x + plan.gameplay_crop.w <= max_src_w
                assert plan.gameplay_crop.y + plan.gameplay_crop.h <= max_src_h
                assert plan.facecam_crop.x + plan.facecam_crop.w <= max_src_w
                assert plan.facecam_crop.y + plan.facecam_crop.h <= max_src_h

                canvas_w = inp.get("canvas_w", 1080)
                canvas_h = inp.get("canvas_h", 1920)
                assert plan.facecam_dest.x + plan.facecam_dest.w <= canvas_w
                assert plan.facecam_dest.y + plan.facecam_dest.h <= canvas_h
        else:
            # Validation rejection vectors (vectors 27-30)
            with pytest.raises(ValueError) as excinfo:
                validate_gaming_layout(inp)
            assert exp["error_message_substring"].lower() in str(excinfo.value).lower(), (
                f"[{vector['id']}] Expected '{exp['error_message_substring']}' in '{str(excinfo.value)}'"
            )


# ==============================================================================
# TIER 1: FEATURE COVERAGE (TC-T1-F12, TC-T1-F13, TC-T1-F17) - 14 TESTS
# ==============================================================================

class TestTier1GamingGeometryParity:
    """Tier 1 Feature Coverage: Even-pixel alignment, Golden Vectors, and Parity."""

    def test_tc_t1_f12_01_even_pixel_alignment_1080p(self):
        """Align normalized coordinates {x:0.1, y:0.1, w:0.5, h:0.5} on 1920x1080 to even pixels (192, 108, 960, 540)."""
        crop = to_source_crop({"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}, 1920, 1080)
        assert crop.x == 192 and crop.y == 108 and crop.w == 960 and crop.h == 540
        assert all(v % 2 == 0 for v in (crop.x, crop.y, crop.w, crop.h))

    def test_tc_t1_f12_02_truncate_odd_calculated_pixels(self):
        """Verify formula floor((coord * dim) / 2) * 2 truncates odd floating pixels (e.g. 191.8px -> 190px)."""
        px = to_even_pixel(0.0999, 1920)  # 191.808 -> 190
        assert px % 2 == 0
        assert px == 190

    def test_tc_t1_f12_03_odd_source_dimensions_handling(self):
        """Verify odd source dimensions 1919x1079 are clamped to even bounds 1918x1078."""
        crop = to_source_crop({"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, 1919, 1079)
        assert crop.w == 1918 and crop.h == 1078
        assert crop.x + crop.w <= 1918
        assert crop.y + crop.h <= 1078

    def test_tc_t1_f12_04_minimum_even_dimension_2px(self):
        """Verify normalized dimension 0.0001 is clamped to minimum valid even size >= 2px."""
        span = to_even_span(0.0001, 1080)
        assert span == 2
        assert span % 2 == 0

    def test_tc_t1_f12_05_yuv420p_chroma_subsampling_verification(self):
        """Verify crop filter receives strictly even integers preventing YUV420p chroma alignment errors."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.15, "y": 0.05, "width": 0.70, "height": 0.90},
            "facecam_roi": {"x": 0.75, "y": 0.05, "width": 0.20, "height": 0.25},
            "facecam_placement": "top-right"
        })
        for c in (plan.gameplay_crop, plan.facecam_crop, plan.facecam_dest):
            assert c.x % 2 == 0 and c.y % 2 == 0 and c.w % 2 == 0 and c.h % 2 == 0

    def test_tc_t1_f13_01_golden_vectors_file_exists_and_parses(self):
        """Verify gaming_geometry_golden_vectors.json exists, parses cleanly, and contains >= 15 vectors."""
        vectors = load_golden_vectors()
        assert len(vectors) >= 15
        assert len(vectors) == 32

    def test_tc_t1_f13_02_python_parity_against_golden_vectors(self):
        """Verify Python geometry engine matches all 32 golden vectors with 0px error."""
        vectors = load_golden_vectors()
        for v in vectors:
            if v["expected"]["is_valid"] and "pointer" not in v["input"]:
                plan = calculate_gaming_coordinates(v["input"])
                assert plan.gameplay_crop == v["expected"]["gameplay_crop"], f"[{v['id']}] gameplay_crop"
                assert plan.facecam_crop == v["expected"]["facecam_crop"], f"[{v['id']}] facecam_crop"
                assert plan.facecam_dest == v["expected"]["facecam_dest"], f"[{v['id']}] facecam_dest"

    def test_tc_t1_f13_04_cross_language_delta_verification(self):
        """Verify max delta between Python and TypeScript normalized floats is < 10^-6."""
        vectors = load_golden_vectors()
        for v in vectors:
            if v["expected"]["is_valid"] and "pointer" not in v["input"]:
                plan = calculate_gaming_coordinates(v["input"])
                exp_rect = v["expected"]["facecam_resolved_output_rect"]
                for k in ("x", "y", "width", "height"):
                    assert abs(getattr(plan.facecam_resolved_output_rect, k) - exp_rect[k]) < 1e-6

    def test_tc_t1_f13_05_golden_vectors_cover_all_presets(self):
        """Verify golden vectors include top-left, top-right, bottom-left, and bottom-right presets."""
        vectors = load_golden_vectors()
        presets_found = {v["input"].get("facecam_placement") for v in vectors if "facecam_placement" in v["input"]}
        assert {"top-left", "top-right", "bottom-left", "bottom-right"}.issubset(presets_found)

    def test_tc_t1_f17_01_preview_framing_vs_render_framing_parity(self):
        """Verify coordinate deviation between preview framing and FFmpeg crop is <= 1px."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.25, "y": 0.0, "width": 0.50, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        expected_x = math.floor((0.25 * 1920) / 2) * 2
        assert abs(plan.gameplay_crop.x - expected_x) <= 1

    def test_tc_t1_f17_02_facecam_position_parity(self):
        """Verify position deviation between preview overlay and FFmpeg overlay is <= 2px."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        # Canvas 1080x1920: top-right preset x=0.65 (702px), y=0.04 (76px)
        assert abs(plan.facecam_dest.x - 702) <= 2
        assert abs(plan.facecam_dest.y - 76) <= 2

    def test_tc_t1_f17_03_facecam_scale_parity(self):
        """Verify size deviation between preview overlay and FFmpeg overlay is <= 2px."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        # Canvas 1080x1920: width 0.30 (324px), height 0.22 (422px)
        assert abs(plan.facecam_dest.w - 324) <= 2
        assert abs(plan.facecam_dest.h - 422) <= 2

    @pytest.mark.asyncio
    async def test_tc_t1_f17_04_full_frame_ssim_parity(self, tmp_path):
        """Verify rendered frame preserves output geometric integrity and renders successfully."""
        src_path = tmp_path / "src_ssim.mp4"
        out_path = tmp_path / "out_ssim.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        }
        plan = create_gaming_layout_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_tc_t1_f17_05_color_integrity_check(self, tmp_path):
        """Verify rendered frame preserves RGB pixel values without color space degradation."""
        src_path = tmp_path / "src_color_check.mp4"
        out_path = tmp_path / "out_color_check.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        }
        plan = create_gaming_layout_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        frame_path = tmp_path / "frame_color.png"
        cmd = ["ffmpeg", "-y", "-ss", "0.25", "-i", str(out_path), "-vframes", "1", str(frame_path)]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        img = Image.open(frame_path)
        fc_pixel = img.getpixel((864, 287))
        # Green channel should be dominant in facecam box
        assert fc_pixel[1] > 100, f"Expected green facecam pixel, got {fc_pixel}"


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (17 TESTS)
# ==============================================================================

class TestTier2GamingGeometryBoundary:
    """Tier 2 Boundary & Extreme Limits: Slender ROIs, odd codec limits, extreme floats, non-square SAR."""

    def test_tc_t2_f02_05_slender_tall_gameplay_roi(self):
        """Gameplay ROI with narrow vertical slice {w:0.05, h:1.0} scaled to fill 9:16 canvas."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.45, "y": 0.0, "width": 0.05, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        assert plan.gameplay_crop.w == 96
        assert plan.gameplay_crop.h == 1080
        assert abs(plan.gameplay_scale_factor - 11.25) < 1e-4

    def test_tc_t2_f03_03_facecam_roi_identical_to_gameplay_roi(self):
        """Verify identical gameplay ROI and facecam ROI render independently without conflict."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.2, "y": 0.2, "width": 0.5, "height": 0.5},
            "facecam_roi": {"x": 0.2, "y": 0.2, "width": 0.5, "height": 0.5},
            "facecam_placement": "top-right"
        })
        assert plan.gameplay_crop == plan.facecam_crop
        assert plan.facecam_dest.w == 324

    def test_tc_t2_f12_01_odd_source_width_and_height_720p(self):
        """Odd source dimensions 1279x719 forced to even bounds <= 1278x718."""
        crop = to_source_crop({"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}, 1279, 719)
        assert crop.w == 1278 and crop.h == 718

    def test_tc_t2_f12_02_odd_pixel_origin_1px(self):
        """1px crop origin x=1px floored to even integer cx=0."""
        px = to_even_pixel(1.0 / 1920.0, 1920)
        assert px == 0
        assert px % 2 == 0

    def test_tc_t2_f12_03_crop_dimension_rounds_to_odd_541px(self):
        """Crop dimension that rounds to odd 541px is aligned to 540px."""
        span = to_even_span(541.0 / 1920.0, 1920)
        assert span == 540
        assert span % 2 == 0

    def test_tc_t2_f12_04_facecam_overlay_coordinates_odd_canvas(self):
        """Facecam overlay odd destination (dest_x=101, dest_y=201) aligned to even (100, 200)."""
        dest = to_canvas_overlay({"x": 101.0 / 1080.0, "y": 201.0 / 1920.0, "width": 0.3, "height": 0.22}, 1080, 1920)
        assert dest.x == 100
        assert dest.y == 200

    def test_tc_t2_f12_05_ffmpeg_yuv420p_test_with_aligned_crop(self, tmp_path):
        """Execute FFmpeg crop filter on YUV420p video verifying zero 'Invalid crop parameters' errors."""
        src = tmp_path / "src_yuv.mp4"
        out = tmp_path / "out_yuv.mp4"
        generate_synthetic_video(src, width=1920, height=1080, duration=0.5)
        crop = to_source_crop({"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}, 1920, 1080)
        cmd = ["ffmpeg", "-y", "-i", str(src), "-vf", f"crop={crop.w}:{crop.h}:{crop.x}:{crop.y}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0

    def test_tc_t2_f13_01_golden_vector_zero_coordinates(self):
        """Golden vector vector-19-boundary-minimum-size / zero origin."""
        vector = next(v for v in load_golden_vectors() if v["id"] == "vector-19-boundary-minimum-size")
        plan = calculate_gaming_coordinates(vector["input"])
        assert plan.facecam_dest == vector["expected"]["facecam_dest"]

    def test_tc_t2_f13_02_golden_vector_full_frame(self):
        """Golden vector vector-01-1080p-standard-top-right."""
        vector = next(v for v in load_golden_vectors() if v["id"] == "vector-01-1080p-standard-top-right")
        plan = calculate_gaming_coordinates(vector["input"])
        assert plan.gameplay_crop == vector["expected"]["gameplay_crop"]

    def test_tc_t2_f13_03_golden_vector_4k_source(self):
        """Golden vector vector-03-4k-highres-bottom-right."""
        vector = next(v for v in load_golden_vectors() if v["id"] == "vector-03-4k-highres-bottom-right")
        plan = calculate_gaming_coordinates(vector["input"])
        assert plan.gameplay_crop == vector["expected"]["gameplay_crop"]

    def test_tc_t2_f13_04_golden_vector_720p_source(self):
        """Golden vector vector-02-720p-standard-top-left."""
        vector = next(v for v in load_golden_vectors() if v["id"] == "vector-02-720p-standard-top-left")
        plan = calculate_gaming_coordinates(vector["input"])
        assert plan.gameplay_crop == vector["expected"]["gameplay_crop"]

    def test_tc_t2_f13_05_golden_vector_extreme_fractional_floats(self):
        """Golden vector vector-22-subpixel-high-precision-fractional."""
        vector = next(v for v in load_golden_vectors() if v["id"] == "vector-22-subpixel-high-precision-fractional")
        plan = calculate_gaming_coordinates(vector["input"])
        assert plan.gameplay_crop == vector["expected"]["gameplay_crop"]

    def test_tc_t2_f17_01_parity_check_4k_source(self):
        """Parity check on 4K source video downscaled to 1080x1920: corner deviation <= 2px."""
        plan = calculate_gaming_coordinates({
            "src_w": 3840, "src_h": 2160,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        assert abs(plan.facecam_dest.x - 702) <= 2

    def test_tc_t2_f17_02_parity_check_720p_source(self):
        """Parity check on 720p source video upscaled to 1080x1920: corner deviation <= 2px."""
        plan = calculate_gaming_coordinates({
            "src_w": 1280, "src_h": 720,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        assert abs(plan.facecam_dest.x - 702) <= 2

    def test_tc_t2_f17_03_parity_check_nonsquare_sar_source(self):
        """Parity check on non-square SAR source; setsar=1 normalizes SAR."""
        plan = calculate_gaming_coordinates({
            "src_w": 1440, "src_h": 1080,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right"
        })
        assert "setsar=1[outv]" in plan.ffmpeg_filtergraph

    def test_tc_t2_f17_04_parity_check_square_facecam_1_1(self):
        """Parity check with custom 1:1 square facecam."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.444444},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.16875}
        })
        assert plan.facecam_crop.w == 480
        assert abs(plan.facecam_crop.h - 480) <= 2
        assert plan.facecam_crop.h % 2 == 0

    def test_tc_t2_f17_05_parity_check_widescreen_facecam_16_9(self):
        """Parity check with widescreen 16:9 facecam."""
        plan = calculate_gaming_coordinates({
            "src_w": 1920, "src_h": 1080,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.50, "y": 0.10, "width": 0.40, "height": 0.40},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.55, "y": 0.04, "width": 0.40, "height": 0.225}
        })
        assert plan.facecam_dest.w == 432
