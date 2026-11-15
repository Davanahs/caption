"""
backend/tests/test_gaming_m4_challenger_deep_audit.py

Adversarial Verification & Empirical Stress Test Suite for Milestone M4.
Constructed independently by EMPIRICAL CHALLENGER to stress-test:
1. Exact cross-language parity on all 32 golden vectors (Python vs TypeScript) with 0px integer delta and < 1e-6 float delta.
2. Extreme aspect ratios: 21:9 ultrawide, 32:9 super-ultrawide, 4:3 retro, 9:16 portrait, 1:1 square, and odd dimensions.
3. Coordinate limits: exactly 0.0, 1.0, minimum dimension (0.05), sub-0.05 rejection, handle inversions, drag boundary clamping.
4. Scale-to-fill framing and even-pixel codec quantization (YUV420p).
5. Strict R5 zero-caption invariant across all filtergraphs.
"""

import json
import math
import subprocess
from pathlib import Path
import pytest

from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    display_to_normalized_letterbox,
    validate_gaming_layout,
    validate_normalized_rect,
    to_source_crop,
    to_canvas_overlay,
    to_even_pixel,
    to_even_span,
    get_facecam_preset,
    FacecamPreset,
)

GOLDEN_VECTORS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "engineering" / "gaming_geometry_golden_vectors.json"


def run_ts_eval(action: str, payload: dict):
    """
    Executes TypeScript functions in Node.js via stdin and returns parsed JSON output.
    Supports 'calculate_gaming_coordinates', 'display_to_normalized_letterbox', 'validate_gaming_layout',
    'apply_drag', and 'calculate_resize'.
    """
    js_code = """
    import fs from 'node:fs';
    import {
        calculateGamingCoordinates,
        displayToNormalizedLetterbox,
        validateGamingLayout,
        applyDrag,
        calculateResize,
        toSourceCrop,
        toCanvasOverlay,
        getFacecamPreset,
        MIN_ROI_SIZE
    } from './lib/gamingCoordinates.ts';

    const inputData = fs.readFileSync(0, 'utf-8');
    const { action, payload } = JSON.parse(inputData);

    try {
        let result;
        if (action === 'calculate_gaming_coordinates') {
            result = calculateGamingCoordinates(payload);
        } else if (action === 'display_to_normalized_letterbox') {
            result = displayToNormalizedLetterbox(
                payload.clientX,
                payload.clientY,
                payload.container,
                payload.src_w,
                payload.src_h
            );
        } else if (action === 'validate_gaming_layout') {
            result = validateGamingLayout(payload);
        } else if (action === 'apply_drag') {
            result = applyDrag(payload.rect, payload.dx, payload.dy);
        } else if (action === 'calculate_resize') {
            result = calculateResize(payload.rect, payload.handle, payload.dx, payload.dy, payload.min_size || MIN_ROI_SIZE);
        } else if (action === 'to_source_crop') {
            result = toSourceCrop(payload.rect, payload.src_w, payload.src_h);
        } else if (action === 'to_canvas_overlay') {
            result = toCanvasOverlay(payload.rect, payload.canvas_w, payload.canvas_h);
        } else {
            throw new Error(`Unknown action: ${action}`);
        }
        console.log(JSON.stringify({ success: true, result }));
    } catch (err) {
        console.log(JSON.stringify({ success: false, error: err.message }));
    }
    """
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", js_code],
        cwd="frontend",
        input=json.dumps({"action": action, "payload": payload}),
        capture_output=True,
        text=True,
        check=True
    )
    stdout_lines = proc.stdout.strip().split("\n")
    json_line = [line for line in stdout_lines if line.startswith("{")][-1]
    return json.loads(json_line)


def load_golden_vectors():
    with open(GOLDEN_VECTORS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["vectors"]


class TestGoldenVectorsCrossLanguageParity:
    """Evaluates all 32 golden vectors directly comparing Python vs TypeScript."""

    @pytest.mark.parametrize("vector", load_golden_vectors(), ids=lambda v: v["id"])
    def test_golden_vector_exact_cross_language_parity(self, vector):
        inp = vector["input"]
        exp = vector["expected"]

        if exp["is_valid"]:
            if "container" in inp and "pointer" in inp:
                # Letterboxed pointer calculation (vectors 23-26)
                py_res = display_to_normalized_letterbox(
                    inp["pointer"]["clientX"],
                    inp["pointer"]["clientY"],
                    inp["container"],
                    inp["src_w"],
                    inp["src_h"]
                )

                ts_eval = run_ts_eval("display_to_normalized_letterbox", {
                    "clientX": inp["pointer"]["clientX"],
                    "clientY": inp["pointer"]["clientY"],
                    "container": inp["container"],
                    "src_w": inp["src_w"],
                    "src_h": inp["src_h"]
                })
                assert ts_eval["success"] is True, f"TS evaluation failed: {ts_eval.get('error')}"
                ts_res = ts_eval["result"]

                # 1. Parity against expected golden vector
                assert py_res["render_rect"] == exp["render_rect"]
                assert ts_res["render_rect"] == exp["render_rect"]
                assert abs(py_res["normalized_pointer"]["x"] - exp["normalized_pointer"]["x"]) < 1e-6
                assert abs(py_res["normalized_pointer"]["y"] - exp["normalized_pointer"]["y"]) < 1e-6
                assert abs(ts_res["normalized_pointer"]["x"] - exp["normalized_pointer"]["x"]) < 1e-6
                assert abs(ts_res["normalized_pointer"]["y"] - exp["normalized_pointer"]["y"]) < 1e-6

                # 2. Direct Python vs TypeScript 0px / 1e-6 parity
                assert py_res["render_rect"] == ts_res["render_rect"], "Python vs TS render_rect mismatch!"
                assert abs(py_res["normalized_pointer"]["x"] - ts_res["normalized_pointer"]["x"]) < 1e-6
                assert abs(py_res["normalized_pointer"]["y"] - ts_res["normalized_pointer"]["y"]) < 1e-6

            else:
                # Dual-region layout plan calculation (vectors 01-22, 31, 32)
                py_plan = calculate_gaming_coordinates(inp)
                ts_eval = run_ts_eval("calculate_gaming_coordinates", inp)
                assert ts_eval["success"] is True, f"TS evaluation failed: {ts_eval.get('error')}"
                ts_plan = ts_eval["result"]

                # 1. Resolved facecam output rect: 0 float delta (< 1e-6)
                for coord in ["x", "y", "width", "height"]:
                    py_v = py_plan.facecam_resolved_output_rect[coord]
                    ts_v = ts_plan["facecam_resolved_output_rect"][coord]
                    exp_v = exp["facecam_resolved_output_rect"][coord]
                    assert abs(py_v - exp_v) < 1e-6, f"Py vs Exp mismatch on {coord}"
                    assert abs(ts_v - exp_v) < 1e-6, f"TS vs Exp mismatch on {coord}"
                    assert abs(py_v - ts_v) < 1e-6, f"Py vs TS mismatch on {coord}"

                # 2. Pixel coordinates: EXACT 0px delta between Python and TypeScript
                for field in ["gameplay_crop", "facecam_crop", "facecam_dest"]:
                    py_dict = getattr(py_plan, field).to_dict()
                    ts_dict = ts_plan[field]
                    exp_dict = exp[field]
                    assert py_dict == exp_dict, f"Python {field} != expected in {vector['id']}"
                    assert ts_dict == exp_dict, f"TypeScript {field} != expected in {vector['id']}"
                    assert py_dict == ts_dict, f"Python {field} != TypeScript {field} in {vector['id']}"

                    # Invariant: Even-pixel guarantee (YUV420p)
                    for k, val in py_dict.items():
                        assert val % 2 == 0, f"Python {field}.{k} ({val}) is not even!"
                        assert ts_dict[k] % 2 == 0, f"TypeScript {field}.{k} ({ts_dict[k]}) is not even!"

                # 3. Scaling metrics
                assert abs(py_plan.gameplay_scale_factor - exp["gameplay_scale_factor"]) < 1e-4
                assert abs(ts_plan["gameplay_scale_factor"] - exp["gameplay_scale_factor"]) < 1e-4
                assert abs(py_plan.gameplay_scale_factor - ts_plan["gameplay_scale_factor"]) < 1e-6
                assert py_plan.gameplay_scaled_w == ts_plan["gameplay_scaled_w"] == exp["gameplay_scaled_w"]
                assert py_plan.gameplay_scaled_h == ts_plan["gameplay_scaled_h"] == exp["gameplay_scaled_h"]

                # 4. FFmpeg filtergraph strings
                assert py_plan.ffmpeg_crop_gameplay == ts_plan["ffmpeg_crop_gameplay"] == exp["ffmpeg_crop_gameplay"]
                assert py_plan.ffmpeg_crop_facecam == ts_plan["ffmpeg_crop_facecam"] == exp["ffmpeg_crop_facecam"]
                assert py_plan.ffmpeg_filtergraph == ts_plan["ffmpeg_filtergraph"] == exp["ffmpeg_filtergraph"]

                # 5. Invariant R5: Zero captions
                for s in [py_plan.ffmpeg_filtergraph, ts_plan["ffmpeg_filtergraph"]]:
                    assert "drawtext" not in s
                    assert "subtitles" not in s
                    assert ".srt" not in s
                    assert ".ass" not in s
                    assert ".vtt" not in s
                    assert "setsar=1" in s
                    assert "eof_action=pass:repeatlast=0" in s

        else:
            # Rejection vectors (vectors 27-30)
            with pytest.raises(ValueError) as py_err:
                validate_gaming_layout(inp)
            assert exp["error_message_substring"].lower() in str(py_err.value).lower()

            ts_eval = run_ts_eval("validate_gaming_layout", inp)
            assert ts_eval["success"] is False, f"TypeScript should have rejected {vector['id']}!"
            assert exp["error_message_substring"].lower() in ts_eval["error"].lower()


class TestExtremeAspectRatiosAndResolutions:
    """Adversarially tests non-standard, ultrawide, retro, portrait, square, and odd dimensions."""

    RESOLUTIONS = [
        ("21:9 Ultrawide 1440p", 3440, 1440),
        ("21:9 Ultrawide 1600p", 3840, 1600),
        ("21:9 Ultrawide 1080p", 2560, 1080),
        ("32:9 Super-Ultrawide 1440p", 5120, 1440),
        ("32:9 Super-Ultrawide 1080p", 3840, 1080),
        ("4:3 Retro SD", 640, 480),
        ("4:3 Retro HD", 1440, 1080),
        ("1:1 Square Standard", 1080, 1080),
        ("1:1 Square Small", 800, 800),
        ("9:16 Portrait Standard", 1080, 1920),
        ("9:16 Portrait 4K", 2160, 3840),
        ("Odd Dimension 1080p+1", 1921, 1081),
        ("Odd Dimension 1080p-1", 1919, 1079),
        ("Odd Dimension 720p+1", 1281, 721),
        ("Odd Dimension Custom", 853, 481),
        ("Small Odd 7x7", 7, 7),
    ]

    @pytest.mark.parametrize("name,src_w,src_h", RESOLUTIONS)
    def test_extreme_resolution_full_pipeline_cross_parity(self, name, src_w, src_h):
        presets = ["top-left", "top-right", "bottom-left", "bottom-right"]
        for preset in presets:
            inp = {
                "src_w": src_w,
                "src_h": src_h,
                "canvas_w": 1080,
                "canvas_h": 1920,
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
                "facecam_placement": preset,
            }

            py_plan = calculate_gaming_coordinates(inp)
            ts_eval = run_ts_eval("calculate_gaming_coordinates", inp)
            assert ts_eval["success"] is True, f"[{name}] TS failed for {preset}: {ts_eval.get('error')}"
            ts_plan = ts_eval["result"]

            # Exact pixel parity (0px delta) between Python and TypeScript
            assert py_plan.gameplay_crop.to_dict() == ts_plan["gameplay_crop"]
            assert py_plan.facecam_crop.to_dict() == ts_plan["facecam_crop"]
            assert py_plan.facecam_dest.to_dict() == ts_plan["facecam_dest"]

            # Even-pixel invariants
            max_even_src_w = (src_w // 2) * 2
            max_even_src_h = (src_h // 2) * 2

            for crop in [py_plan.gameplay_crop, py_plan.facecam_crop]:
                assert crop.x % 2 == 0
                assert crop.y % 2 == 0
                assert crop.w % 2 == 0
                assert crop.h % 2 == 0
                assert crop.w >= 2
                assert crop.h >= 2
                assert crop.x + crop.w <= max_even_src_w, f"Crop X overflow on {name}: {crop.x + crop.w} > {max_even_src_w}"
                assert crop.y + crop.h <= max_even_src_h, f"Crop Y overflow on {name}: {crop.y + crop.h} > {max_even_src_h}"

            # Canvas overlay containment
            assert py_plan.facecam_dest.x % 2 == 0
            assert py_plan.facecam_dest.y % 2 == 0
            assert py_plan.facecam_dest.w % 2 == 0
            assert py_plan.facecam_dest.h % 2 == 0
            assert py_plan.facecam_dest.x + py_plan.facecam_dest.w <= 1080
            assert py_plan.facecam_dest.y + py_plan.facecam_dest.h <= 1920

            # Scale-to-fill framing: Output scaled dimensions MUST cover 1080x1920
            assert py_plan.gameplay_scaled_w >= 1080
            assert py_plan.gameplay_scaled_h >= 1920
            # At least one dimension must match 1080 or 1920 exactly
            assert py_plan.gameplay_scaled_w == 1080 or py_plan.gameplay_scaled_h == 1920

    @pytest.mark.parametrize("name,src_w,src_h", RESOLUTIONS)
    def test_extreme_boundary_corner_facecam_roi(self, name, src_w, src_h):
        """Corner ROI at exact edge x=0.95, y=0.95, w=0.05, h=0.05."""
        inp = {
            "src_w": src_w,
            "src_h": src_h,
            "canvas_w": 1080,
            "canvas_h": 1920,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.95, "y": 0.95, "width": 0.05, "height": 0.05},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.70, "y": 0.70, "width": 0.25, "height": 0.25},
        }

        py_plan = calculate_gaming_coordinates(inp)
        ts_eval = run_ts_eval("calculate_gaming_coordinates", inp)
        assert ts_eval["success"] is True
        ts_plan = ts_eval["result"]

        # Exact pixel parity (0px delta)
        assert py_plan.facecam_crop.to_dict() == ts_plan["facecam_crop"]
        assert py_plan.facecam_dest.to_dict() == ts_plan["facecam_dest"]

        max_even_src_w = (src_w // 2) * 2
        max_even_src_h = (src_h // 2) * 2
        assert py_plan.facecam_crop.x + py_plan.facecam_crop.w <= max_even_src_w
        assert py_plan.facecam_crop.y + py_plan.facecam_crop.h <= max_even_src_h


class TestCoordinateLimitsAndInteractiveBehaviors:
    """Stress tests boundary dragging, handle inversions, and sub-0.05 dimension rejection."""

    def test_sub_0_05_dimension_rejection_parity(self):
        """Dimensions below 0.05 (beyond epsilon 1e-4) must be rejected in both Python and TypeScript."""
        bad_inputs = [
            {"x": 0.1, "y": 0.1, "width": 0.048, "height": 0.5},
            {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.045},
            {"x": 0.1, "y": 0.1, "width": 0.02, "height": 0.02},
            {"x": 0.1, "y": 0.1, "width": 0.0001, "height": 0.0001},
            {"x": 0.1, "y": 0.1, "width": 0.0, "height": 0.5},
        ]
        for bad_roi in bad_inputs:
            with pytest.raises(ValueError, match="must be >= 0.05"):
                validate_normalized_rect(bad_roi)

            ts_eval = run_ts_eval("validate_gaming_layout", {
                "src_w": 1920,
                "src_h": 1080,
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": bad_roi,
                "facecam_placement": "top-right"
            })
            assert ts_eval["success"] is False
            assert "0.05" in ts_eval["error"]

    def test_epsilon_tolerance_near_0_05_boundary_parity(self):
        """
        Coordinates within 1e-4 epsilon of 0.05 (e.g. 0.04995) are accepted
        and safely clamped to min_size (0.05) by both Python and TypeScript.
        """
        near_boundary_roi = {"x": 0.1, "y": 0.1, "width": 0.04995, "height": 0.5}
        py_clean = validate_normalized_rect(near_boundary_roi)
        assert py_clean.width >= 0.05

        ts_eval = run_ts_eval("validate_gaming_layout", {
            "src_w": 1920,
            "src_h": 1080,
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": near_boundary_roi,
            "facecam_placement": "top-right"
        })
        assert ts_eval["success"] is True

    def test_extreme_pointer_drag_cross_boundary_clamping(self):
        """Dragging ROI across screen boundaries must clamp without size mutation."""
        initial_rect = {"x": 0.5, "y": 0.5, "width": 0.3, "height": 0.25}

        extreme_drags = [
            (-100.0, -100.0, 0.0, 0.0),       # Extreme top-left
            (100.0, 100.0, 0.7, 0.75),        # Extreme bottom-right (1.0 - 0.3, 1.0 - 0.25)
            (-50.0, 50.0, 0.0, 0.75),         # Bottom-left
            (50.0, -50.0, 0.7, 0.0),          # Top-right
        ]

        for dx, dy, exp_x, exp_y in extreme_drags:
            ts_eval = run_ts_eval("apply_drag", {"rect": initial_rect, "dx": dx, "dy": dy})
            assert ts_eval["success"] is True
            dragged = ts_eval["result"]

            assert abs(dragged["x"] - exp_x) < 1e-4
            assert abs(dragged["y"] - exp_y) < 1e-4
            assert abs(dragged["width"] - initial_rect["width"]) < 1e-6
            assert abs(dragged["height"] - initial_rect["height"]) < 1e-6

    def test_resize_handle_inversions_across_all_corners(self):
        """
        Dragging resize handles past opposite corner must clamp to min_size (0.05)
        and preserve opposite anchor without negative dimensions.
        """
        rect = {"x": 0.3, "y": 0.3, "width": 0.4, "height": 0.4}

        cases = [
            # Handle, dx, dy, expected_x, expected_y, expected_w, expected_h
            ("se", -10.0, -10.0, 0.3, 0.3, 0.05, 0.05),     # SE inverted top-left
            ("se", 10.0, 10.0, 0.3, 0.3, 0.7, 0.7),        # SE expanded bottom-right (clamp at 1.0)
            ("nw", 10.0, 10.0, 0.65, 0.65, 0.05, 0.05),    # NW inverted bottom-right
            ("nw", -10.0, -10.0, 0.0, 0.0, 0.7, 0.7),      # NW expanded top-left (clamp at 0.0)
            ("ne", -10.0, 10.0, 0.3, 0.65, 0.05, 0.05),    # NE inverted bottom-left
            ("sw", 10.0, -10.0, 0.65, 0.3, 0.05, 0.05),    # SW inverted top-right
        ]

        for handle, dx, dy, exp_x, exp_y, exp_w, exp_h in cases:
            ts_eval = run_ts_eval("calculate_resize", {
                "rect": rect,
                "handle": handle,
                "dx": dx,
                "dy": dy,
                "min_size": 0.05
            })
            assert ts_eval["success"] is True
            resized = ts_eval["result"]

            assert abs(resized["x"] - exp_x) < 1e-3, f"Handle {handle} X: expected {exp_x}, got {resized['x']}"
            assert abs(resized["y"] - exp_y) < 1e-3, f"Handle {handle} Y: expected {exp_y}, got {resized['y']}"
            assert abs(resized["width"] - exp_w) < 1e-3, f"Handle {handle} W: expected {exp_w}, got {resized['width']}"
            assert abs(resized["height"] - exp_h) < 1e-3, f"Handle {handle} H: expected {exp_h}, got {resized['height']}"

            # Invariants
            assert resized["x"] >= 0.0
            assert resized["y"] >= 0.0
            assert resized["width"] >= 0.05
            assert resized["height"] >= 0.05
            assert resized["x"] + resized["width"] <= 1.0001
            assert resized["y"] + resized["height"] <= 1.0001
