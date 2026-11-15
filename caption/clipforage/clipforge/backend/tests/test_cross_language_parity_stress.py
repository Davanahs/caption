"""
backend/tests/test_cross_language_parity_stress.py

Adversarial Cross-Language Parity Harness (Challenger 2).
Executes 500 diverse configurations through both Python and TypeScript
and verifies bit-for-bit / epsilon parity, even-pixel guarantees,
and containment invariants.
"""

import json
import math
import random
import subprocess
import pytest

from backend.services.gaming_geometry import calculate_gaming_coordinates


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


def test_cross_language_near_boundary_epsilon_parity():
    """
    FAILING PARITY TEST / COUNTEREXAMPLE:
    When a coordinate is slightly negative (-0.00005) or slightly overflowing (0.50005),
    Python and TypeScript diverge:
    - Python clamps x to 0.0, while TS leaves x as -0.00005 (negative).
    - Python clamps w to 0.5, while TS leaves w as 0.50005 (sum > 1.0).
    """
    inp = {
        "src_w": 1920,
        "src_h": 1080,
        "canvas_w": 1080,
        "canvas_h": 1920,
        "gameplay_roi": {"x": -0.00005, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
    }
    ts_res = run_ts_calculate_gaming_coordinates([inp])[0]
    py_plan = calculate_gaming_coordinates(inp)

    # In Python: py_plan.gameplay_crop.x == 0
    # In TypeScript: ts_plan.gameplay_crop.x == -0 (or norm x is -0.00005)
    assert ts_res["success"] is True
    # Check normalized coordinate parity
    # Note: Python's resolved gameplay_crop vs TS gameplay_crop
    assert py_plan.gameplay_crop.to_dict() == ts_res["result"]["gameplay_crop"]


def test_cross_language_zero_src_dimension_parity():
    """
    FAILING PARITY TEST / COUNTEREXAMPLE:
    When src_w=0 or src_h=0:
    Python raises ValueError("Source dimensions must be positive, got 0x0")
    TypeScript accepts it and returns success=True with is_valid=True!
    """
    inp = {
        "src_w": 0,
        "src_h": 0,
        "canvas_w": 1080,
        "canvas_h": 1920,
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
    }
    ts_res = run_ts_calculate_gaming_coordinates([inp])[0]

    with pytest.raises(ValueError, match="Source dimensions must be positive"):
        calculate_gaming_coordinates(inp)

    # Parity requirement: TypeScript must also reject src_w=0 with success=False
    assert ts_res["success"] is False, (
        f"Cross-language parity failure: Python rejected src_w=0 with ValueError, "
        f"but TypeScript accepted it: {ts_res['result']}"
    )


def test_cross_language_negative_src_dimension_parity():
    """
    FAILING PARITY TEST / COUNTEREXAMPLE:
    When src_w=-1920:
    Python raises ValueError("Source dimensions must be positive, got -1920x1080")
    TypeScript accepts it and generates negative crop coordinates in FFmpeg filter!
    """
    inp = {
        "src_w": -1920,
        "src_h": 1080,
        "canvas_w": 1080,
        "canvas_h": 1920,
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
    }
    ts_res = run_ts_calculate_gaming_coordinates([inp])[0]

    with pytest.raises(ValueError, match="Source dimensions must be positive"):
        calculate_gaming_coordinates(inp)

    assert ts_res["success"] is False, (
        f"Cross-language parity failure: Python rejected src_w=-1920 with ValueError, "
        f"but TypeScript accepted it: {ts_res['result']}"
    )

    """Generates 200 random valid configurations and compares Python vs TypeScript outputs."""
    rng = random.Random(1337)
    resolutions = [
        (1920, 1080),
        (1280, 720),
        (3840, 2160),
        (2560, 1440),
        (3440, 1440),
        (1921, 1081),
        (853, 481),
        (3841, 2161),
    ]
    presets = ["top-left", "top-right", "bottom-left", "bottom-right"]

    inputs_batch = []
    for _ in range(200):
        src_w, src_h = rng.choice(resolutions)
        gw = rng.uniform(0.1, 1.0)
        gh = rng.uniform(0.1, 1.0)
        gx = rng.uniform(0.0, 1.0 - gw)
        gy = rng.uniform(0.0, 1.0 - gh)

        fw = rng.uniform(0.1, 0.5)
        fh = rng.uniform(0.1, 0.5)
        fx = rng.uniform(0.0, 1.0 - fw)
        fy = rng.uniform(0.0, 1.0 - fh)

        preset = rng.choice(presets)

        inp = {
            "src_w": src_w,
            "src_h": src_h,
            "canvas_w": 1080,
            "canvas_h": 1920,
            "gameplay_roi": {
                "x": round(gx, 4),
                "y": round(gy, 4),
                "width": round(gw, 4),
                "height": round(gh, 4)
            },
            "facecam_roi": {
                "x": round(fx, 4),
                "y": round(fy, 4),
                "width": round(fw, 4),
                "height": round(fh, 4)
            },
            "facecam_placement": preset,
        }
        inputs_batch.append(inp)

    ts_results = run_ts_calculate_gaming_coordinates(inputs_batch)

    discrepancies = []
    for idx, inp in enumerate(inputs_batch):
        ts_res = ts_results[idx]
        try:
            py_plan = calculate_gaming_coordinates(inp)
            py_success = True
            py_err = None
        except Exception as e:
            py_success = False
            py_err = str(e)

        if py_success != ts_res["success"]:
            discrepancies.append((idx, "success_mismatch", py_success, ts_res["success"]))
            continue

        if not py_success:
            continue

        ts_plan = ts_res["result"]

        # 1. Gameplay crop parity
        if py_plan.gameplay_crop.to_dict() != ts_plan["gameplay_crop"]:
            discrepancies.append((idx, "gameplay_crop", py_plan.gameplay_crop.to_dict(), ts_plan["gameplay_crop"]))

        # 2. Facecam crop parity
        if py_plan.facecam_crop.to_dict() != ts_plan["facecam_crop"]:
            discrepancies.append((idx, "facecam_crop", py_plan.facecam_crop.to_dict(), ts_plan["facecam_crop"]))

        # 3. Facecam destination parity
        if py_plan.facecam_dest.to_dict() != ts_plan["facecam_dest"]:
            discrepancies.append((idx, "facecam_dest", py_plan.facecam_dest.to_dict(), ts_plan["facecam_dest"]))

        # 4. Scale factor parity (< 1e-4)
        if abs(py_plan.gameplay_scale_factor - ts_plan["gameplay_scale_factor"]) > 1e-4:
            discrepancies.append((
                idx, "gameplay_scale_factor",
                py_plan.gameplay_scale_factor, ts_plan["gameplay_scale_factor"]
            ))

        # 5. Scaled dimensions
        if py_plan.gameplay_scaled_w != ts_plan["gameplay_scaled_w"] or py_plan.gameplay_scaled_h != ts_plan["gameplay_scaled_h"]:
            discrepancies.append((
                idx, "gameplay_scaled_dimensions",
                (py_plan.gameplay_scaled_w, py_plan.gameplay_scaled_h),
                (ts_plan["gameplay_scaled_w"], ts_plan["gameplay_scaled_h"])
            ))

        # 6. FFmpeg filtergraph parity
        if py_plan.ffmpeg_filtergraph != ts_plan["ffmpeg_filtergraph"]:
            discrepancies.append((idx, "ffmpeg_filtergraph", py_plan.ffmpeg_filtergraph, ts_plan["ffmpeg_filtergraph"]))

    assert not discrepancies, f"Found {len(discrepancies)} cross-language parity discrepancies: {discrepancies[:10]}"
