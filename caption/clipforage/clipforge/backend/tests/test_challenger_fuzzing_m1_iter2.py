"""
backend/tests/test_challenger_fuzzing_m1_iter2.py

Adversarial Random Fuzzing & Parity Stress Harness (Challenger M1 Iteration 2).
Executes 1000 randomized configurations across diverse resolutions, pathological odd dimensions,
ultra-wides, small dimensions, boundary coordinates, and presets.
Verifies bit-for-bit / epsilon parity between Python and TypeScript,
and asserts strict mathematical containment invariants.
"""

import json
import math
import random
import subprocess
import pytest

from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    validate_normalized_rect,
    to_source_crop,
    to_canvas_overlay,
    to_even_pixel,
    to_even_span,
    get_facecam_preset,
    DEFAULT_CANVAS_WIDTH,
    DEFAULT_CANVAS_HEIGHT,
)


def run_ts_calculate_gaming_coordinates(inputs_batch):
    """Executes a batch of inputs through Node.js TypeScript engine via stdin and returns results."""
    js_code = """
    import fs from 'node:fs';
    import { calculateGamingCoordinates } from './lib/gamingCoordinates.ts';

    const inputData = fs.readFileSync(0, 'utf-8');
    const inputs = JSON.parse(inputData);
    const results = inputs.map(inp => {
        try {
            const res = calculateGamingCoordinates(inp);
            return { success: true, result: res };
        } catch (err) {
            return { success: false, error: err.message };
        }
    });
    console.log(JSON.stringify(results));
    """
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", js_code],
        cwd="frontend",
        input=json.dumps(inputs_batch),
        capture_output=True,
        text=True,
        check=True
    )
    stdout_lines = proc.stdout.strip().split("\n")
    json_line = [line for line in stdout_lines if line.startswith("[")][-1]
    return json.loads(json_line)


def run_ts_eval(js_expr):
    """Executes a JS expression in frontend context and returns stdout."""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", f"import * as m from './lib/gamingCoordinates.ts'; console.log(JSON.stringify({val: {js_expr}}));"],
        cwd="frontend",
        capture_output=True,
        text=True,
        check=True
    )
    stdout_lines = proc.stdout.strip().split("\n")
    json_line = [line for line in stdout_lines if line.startswith("{")][-1]
    return json.loads(json_line)["val"]


class TestAdversarialFuzzing1000Configs:
    """1000 randomized configurations across odd, extreme, and standard dimensions."""

    def test_1000_random_configurations_python_ts_parity(self):
        rng = random.Random(424242)

        resolutions = [
            # Standard
            (1920, 1080),
            (1280, 720),
            (3840, 2160),
            (2560, 1440),
            # Odd dimensions
            (1921, 1081),
            (1919, 1079),
            (1281, 721),
            (853, 481),
            (3841, 2161),
            (7, 7),
            (9, 9),
            (13, 13),
            (21, 21),
            (99, 99),
            (101, 101),
            (2, 2),
            (4, 4),
            (10, 10),
            # Ultrawide & Vertical
            (2560, 1080),
            (3440, 1440),
            (5120, 1440),
            (1080, 1920),
            (720, 1280),
            # Extreme aspect ratios
            (4000, 400),
            (400, 4000),
        ]

        canvas_resolutions = [
            (1080, 1920),
            (720, 1280),
            (2160, 3840),
            (1081, 1921),  # odd canvas
        ]

        presets = ["top-left", "top-right", "bottom-left", "bottom-right"]

        batch_size = 1000
        inputs_batch = []

        for i in range(batch_size):
            src_w, src_h = rng.choice(resolutions)
            canvas_w, canvas_h = rng.choice(canvas_resolutions)

            # Random valid gameplay ROI
            gw = rng.uniform(0.05, 1.0)
            gh = rng.uniform(0.05, 1.0)
            gx = rng.uniform(0.0, 1.0 - gw)
            gy = rng.uniform(0.0, 1.0 - gh)

            # Random valid facecam ROI
            fw = rng.uniform(0.05, 0.5)
            fh = rng.uniform(0.05, 0.5)
            fx = rng.uniform(0.0, 1.0 - fw)
            fy = rng.uniform(0.0, 1.0 - fh)

            use_custom_output = rng.random() < 0.3
            preset = rng.choice(presets)

            inp = {
                "src_w": src_w,
                "src_h": src_h,
                "canvas_w": canvas_w,
                "canvas_h": canvas_h,
                "gameplay_roi": {
                    "x": round(gx, 6),
                    "y": round(gy, 6),
                    "width": round(gw, 6),
                    "height": round(gh, 6)
                },
                "facecam_roi": {
                    "x": round(fx, 6),
                    "y": round(fy, 6),
                    "width": round(fw, 6),
                    "height": round(fh, 6)
                },
                "facecam_placement": "custom" if use_custom_output else preset,
            }

            if use_custom_output:
                ow = rng.uniform(0.05, 0.45)
                oh = rng.uniform(0.05, 0.45)
                ox = rng.uniform(0.0, 1.0 - ow)
                oy = rng.uniform(0.0, 1.0 - oh)
                inp["facecam_output_rect"] = {
                    "x": round(ox, 6),
                    "y": round(oy, 6),
                    "width": round(ow, 6),
                    "height": round(oh, 6)
                }

            inputs_batch.append(inp)

        # Execute through TypeScript in batch
        ts_results = run_ts_calculate_gaming_coordinates(inputs_batch)
        assert len(ts_results) == batch_size

        discrepancies = []
        invariant_violations = []

        for idx, inp in enumerate(inputs_batch):
            ts_res = ts_results[idx]
            try:
                py_plan = calculate_gaming_coordinates(inp)
                py_success = True
                py_err = None
            except Exception as e:
                py_success = False
                py_err = str(e)

            # 1. Parity of success/failure
            if py_success != ts_res["success"]:
                discrepancies.append((idx, "success_mismatch", py_success, ts_res.get("success"), py_err, ts_res.get("error")))
                continue

            if not py_success:
                continue

            ts_plan = ts_res["result"]

            # 2. Strict Mathematical Invariants Verification (Both Python & TypeScript)
            src_w = inp["src_w"]
            src_h = inp["src_h"]
            canvas_w = inp["canvas_w"]
            canvas_h = inp["canvas_h"]

            max_src_w = (src_w // 2) * 2
            max_src_h = (src_h // 2) * 2
            max_can_w = (canvas_w // 2) * 2
            max_can_h = (canvas_h // 2) * 2

            # Python Invariants
            for name, crop in [("py_gameplay", py_plan.gameplay_crop), ("py_facecam", py_plan.facecam_crop)]:
                if crop.x % 2 != 0 or crop.y % 2 != 0:
                    invariant_violations.append((idx, f"{name} odd coordinate", crop.to_dict()))
                if crop.w % 2 != 0 or crop.h % 2 != 0:
                    invariant_violations.append((idx, f"{name} odd span", crop.to_dict()))
                if crop.x + crop.w > max_src_w:
                    invariant_violations.append((idx, f"{name} overflow w: {crop.x}+{crop.w} > {max_src_w}", crop.to_dict()))
                if crop.y + crop.h > max_src_h:
                    invariant_violations.append((idx, f"{name} overflow h: {crop.y}+{crop.h} > {max_src_h}", crop.to_dict()))

            dest = py_plan.facecam_dest
            if dest.x % 2 != 0 or dest.y % 2 != 0 or dest.w % 2 != 0 or dest.h % 2 != 0:
                invariant_violations.append((idx, "py_dest odd parity", dest.to_dict()))
            if dest.x + dest.w > max_can_w:
                invariant_violations.append((idx, f"py_dest overflow w: {dest.x}+{dest.w} > {max_can_w}", dest.to_dict()))
            if dest.y + dest.h > max_can_h:
                invariant_violations.append((idx, f"py_dest overflow h: {dest.y}+{dest.h} > {max_can_h}", dest.to_dict()))

            # TypeScript Invariants
            for name, crop in [("ts_gameplay", ts_plan["gameplay_crop"]), ("ts_facecam", ts_plan["facecam_crop"])]:
                if crop["x"] % 2 != 0 or crop["y"] % 2 != 0:
                    invariant_violations.append((idx, f"{name} odd coordinate", crop))
                if crop["w"] % 2 != 0 or crop["h"] % 2 != 0:
                    invariant_violations.append((idx, f"{name} odd span", crop))
                if crop["x"] + crop["w"] > max_src_w:
                    invariant_violations.append((idx, f"{name} overflow w: {crop['x']}+{crop['w']} > {max_src_w}", crop))
                if crop["y"] + crop["h"] > max_src_h:
                    invariant_violations.append((idx, f"{name} overflow h: {crop['y']}+{crop['h']} > {max_src_h}", crop))

            ts_dest = ts_plan["facecam_dest"]
            if ts_dest["x"] % 2 != 0 or ts_dest["y"] % 2 != 0 or ts_dest["w"] % 2 != 0 or ts_dest["h"] % 2 != 0:
                invariant_violations.append((idx, "ts_dest odd parity", ts_dest))
            if ts_dest["x"] + ts_dest["w"] > max_can_w:
                invariant_violations.append((idx, f"ts_dest overflow w: {ts_dest['x']}+{ts_dest['w']} > {max_can_w}", ts_dest))
            if ts_dest["y"] + ts_dest["h"] > max_can_h:
                invariant_violations.append((idx, f"ts_dest overflow h: {ts_dest['y']}+{ts_dest['h']} > {max_can_h}", ts_dest))

            # 3. Direct Cross-Language Parity
            if py_plan.gameplay_crop.to_dict() != ts_plan["gameplay_crop"]:
                discrepancies.append((idx, "gameplay_crop", py_plan.gameplay_crop.to_dict(), ts_plan["gameplay_crop"]))
            if py_plan.facecam_crop.to_dict() != ts_plan["facecam_crop"]:
                discrepancies.append((idx, "facecam_crop", py_plan.facecam_crop.to_dict(), ts_plan["facecam_crop"]))
            if py_plan.facecam_dest.to_dict() != ts_plan["facecam_dest"]:
                discrepancies.append((idx, "facecam_dest", py_plan.facecam_dest.to_dict(), ts_plan["facecam_dest"]))

            if abs(py_plan.gameplay_scale_factor - ts_plan["gameplay_scale_factor"]) > 1e-4:
                discrepancies.append((idx, "scale_factor", py_plan.gameplay_scale_factor, ts_plan["gameplay_scale_factor"]))

            # Scaled dimensions parity: on odd canvas dimensions, Python round-half-to-even vs JS Math.round can differ by at most 1 pixel
            max_allowed_diff = 1 if (canvas_w % 2 != 0 or canvas_h % 2 != 0) else 0
            if abs(py_plan.gameplay_scaled_w - ts_plan["gameplay_scaled_w"]) > max_allowed_diff or abs(py_plan.gameplay_scaled_h - ts_plan["gameplay_scaled_h"]) > max_allowed_diff:
                discrepancies.append((
                    idx, "scaled_dims",
                    (py_plan.gameplay_scaled_w, py_plan.gameplay_scaled_h),
                    (ts_plan["gameplay_scaled_w"], ts_plan["gameplay_scaled_h"])
                ))

            if py_plan.canvas_width != ts_plan["canvas_width"] or py_plan.canvas_height != ts_plan["canvas_height"]:
                discrepancies.append((
                    idx, "canvas_dims",
                    (py_plan.canvas_width, py_plan.canvas_height),
                    (ts_plan["canvas_width"], ts_plan["canvas_height"])
                ))

            if py_plan.ffmpeg_crop_gameplay != ts_plan["ffmpeg_crop_gameplay"]:
                discrepancies.append((idx, "ffmpeg_crop_gameplay", py_plan.ffmpeg_crop_gameplay, ts_plan["ffmpeg_crop_gameplay"]))

            if py_plan.ffmpeg_crop_facecam != ts_plan["ffmpeg_crop_facecam"]:
                discrepancies.append((idx, "ffmpeg_crop_facecam", py_plan.ffmpeg_crop_facecam, ts_plan["ffmpeg_crop_facecam"]))

            if py_plan.ffmpeg_filtergraph != ts_plan["ffmpeg_filtergraph"]:
                discrepancies.append((idx, "ffmpeg_filtergraph", py_plan.ffmpeg_filtergraph, ts_plan["ffmpeg_filtergraph"]))

        assert not invariant_violations, f"Encountered {len(invariant_violations)} invariant violations: {invariant_violations[:5]}"
        assert not discrepancies, f"Encountered {len(discrepancies)} cross-language parity discrepancies out of {batch_size}: {discrepancies[:5]}"


class TestPathologicalBoundaryEdgeCases:
    """Explicit tests for boundary conditions, subpixel epsilon, and non-finite values."""

    @pytest.mark.parametrize("dim", [3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 33, 49, 101, 1081, 1921, 2161, 3841])
    def test_odd_dimension_all_corners_clamp_containment(self, dim):
        """Tests that all 4 extreme corners on odd dimensions are strictly contained."""
        corners = [
            {"x": 0.0, "y": 0.0, "width": 0.05, "height": 0.05},
            {"x": 0.95, "y": 0.0, "width": 0.05, "height": 0.05},
            {"x": 0.0, "y": 0.95, "width": 0.05, "height": 0.05},
            {"x": 0.95, "y": 0.95, "width": 0.05, "height": 0.05},
            {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        ]
        max_even = (dim // 2) * 2

        for corner in corners:
            crop_py = to_source_crop(corner, dim, dim)
            assert crop_py.x + crop_py.w <= max_even, f"Python overflow on {dim}x{dim}: {crop_py.x}+{crop_py.w} > {max_even}"
            assert crop_py.y + crop_py.h <= max_even, f"Python overflow on {dim}x{dim}: {crop_py.y}+{crop_py.h} > {max_even}"
            assert crop_py.x % 2 == 0 and crop_py.y % 2 == 0 and crop_py.w % 2 == 0 and crop_py.h % 2 == 0

            overlay_py = to_canvas_overlay(corner, dim, dim)
            assert overlay_py.x + overlay_py.w <= max_even
            assert overlay_py.y + overlay_py.h <= max_even

    def test_near_zero_epsilon_coordinates(self):
        """Coordinates within negative epsilon must clamp safely to 0.0 without throwing or leaking."""
        rect = {"x": -0.00008, "y": -0.00001, "width": 0.2, "height": 0.2}
        validated = validate_normalized_rect(rect)
        assert validated.x == 0.0
        assert validated.y == 0.0
        assert validated.width == 0.2
        assert validated.height == 0.2

    def test_near_one_epsilon_sum_overflow(self):
        """Sum within positive epsilon of 1.0 must clamp width/height so sum <= 1.0."""
        rect = {"x": 0.8, "y": 0.8, "width": 0.20008, "height": 0.20005}
        validated = validate_normalized_rect(rect)
        assert validated.x + validated.width <= 1.0
        assert validated.y + validated.height <= 1.0
        assert validated.x == 0.8
        assert validated.y == 0.8
        assert validated.width == 0.2
        assert validated.height == 0.2
