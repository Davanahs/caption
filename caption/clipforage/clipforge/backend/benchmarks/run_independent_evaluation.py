"""
ClipForge Independent Camera Cut Benchmark Evaluation Runner
============================================================
Work Item: PODCAST-CUT-VALIDATION-015
Logic Domain: L7 (Camera Cut Detection)

Reruns evaluation of all candidate detectors against the independent reference ground truth (v3.0.0)
across both 0-180s and 0-300s windows, generating the authoritative benchmark dataset.
"""

import json
import os
import sys

from backend.benchmarks.evaluate_independent_camera_cuts import CameraCutEvaluator

CANDIDATE_FILES = {
    "BASELINE-0": {
        "file": "BASELINE-0.json",
        "name": "Current Baseline (FFmpeg scdet=17.5 + OpenCV fallback)",
        "type": "Production L7 Hybrid",
        "license": "GPL-3.0 (host ffmpeg)",
        "runtime_sec": 18.3,
        "throughput_fps": 54.6,
        "ram_mb": 65.0,
    },
    "FFMPEG_scdet_17.5": {
        "file": "FFMPEG-1_scdet_thr17.5.json",
        "name": "FFmpeg scdet (threshold=17.5)",
        "type": "Command-Line Filter",
        "license": "GPL-3.0",
        "runtime_sec": 17.9,
        "throughput_fps": 55.8,
        "ram_mb": 45.0,
    },
    "FFMPEG_scdet_12.0": {
        "file": "FFMPEG-1_scdet_thr12.0.json",
        "name": "FFmpeg scdet (threshold=12.0)",
        "type": "Command-Line Filter",
        "license": "GPL-3.0",
        "runtime_sec": 17.8,
        "throughput_fps": 56.1,
        "ram_mb": 45.0,
    },
    "FFMPEG_scdet_8.0": {
        "file": "FFMPEG-1_scdet_thr8.0.json",
        "name": "FFmpeg scdet (threshold=8.0)",
        "type": "Command-Line Filter",
        "license": "GPL-3.0",
        "runtime_sec": 17.9,
        "throughput_fps": 55.8,
        "ram_mb": 45.0,
    },
    "FFMPEG_scdet_22.0": {
        "file": "FFMPEG-1_scdet_thr22.0.json",
        "name": "FFmpeg scdet (threshold=22.0)",
        "type": "Command-Line Filter",
        "license": "GPL-3.0",
        "runtime_sec": 17.8,
        "throughput_fps": 56.1,
        "ram_mb": 45.0,
    },
    "FFMPEG_scdet_30.0": {
        "file": "FFMPEG-1_scdet_thr30.0.json",
        "name": "FFmpeg scdet (threshold=30.0)",
        "type": "Command-Line Filter",
        "license": "GPL-3.0",
        "runtime_sec": 17.8,
        "throughput_fps": 56.1,
        "ram_mb": 45.0,
    },
    "CLASSIC-0_PureHSV": {
        "file": "CLASSIC-0_PureHSVHist_thr0.40.json",
        "name": "Pure HSV Histogram Correlation (Historical)",
        "type": "OpenCV Single-Signal",
        "license": "Apache-2.0",
        "runtime_sec": 14.2,
        "throughput_fps": 70.4,
        "ram_mb": 85.0,
    },
    "CLASSIC-1_AdaptiveDetector": {
        "file": "CLASSIC-1_AdaptiveDetector.json",
        "name": "PySceneDetect AdaptiveDetector",
        "type": "Classical Adaptive Filter",
        "license": "BSD-3-Clause",
        "runtime_sec": 87.2,
        "throughput_fps": 11.5,
        "ram_mb": 115.0,
    },
    "CLASSIC-2_ContentDetector": {
        "file": "CLASSIC-2_ContentDetector.json",
        "name": "PySceneDetect ContentDetector",
        "type": "Classical HSV Luminance Filter",
        "license": "BSD-3-Clause",
        "runtime_sec": 84.1,
        "throughput_fps": 11.9,
        "ram_mb": 112.0,
    },
    "CLASSIC-2b_ContentDetector_Edge": {
        "file": "CLASSIC-2b_ContentDetector_EdgeWeighted.json",
        "name": "PySceneDetect ContentDetector (Edge-Weighted)",
        "type": "Classical Edge + HSV Filter",
        "license": "BSD-3-Clause",
        "runtime_sec": 88.5,
        "throughput_fps": 11.3,
        "ram_mb": 118.0,
    },
    "CLASSIC-3a_HashDetector": {
        "file": "CLASSIC-3a_HashDetector.json",
        "name": "PySceneDetect HashDetector",
        "type": "Perceptual Hash Difference",
        "license": "BSD-3-Clause",
        "runtime_sec": 79.4,
        "throughput_fps": 12.6,
        "ram_mb": 105.0,
    },
    "CLASSIC-3b_HistogramDetector": {
        "file": "CLASSIC-3b_HistogramDetector.json",
        "name": "PySceneDetect HistogramDetector",
        "type": "PySceneDetect YUV Histogram",
        "license": "BSD-3-Clause",
        "runtime_sec": 81.3,
        "throughput_fps": 12.3,
        "ram_mb": 110.0,
    },
    "ML-1_TransNetV2": {
        "file": "ML-1_TransNetV2_PyPI.json",
        "name": "TransNetV2 (PyTorch DDCNN Deep Neural Network)",
        "type": "Deep Learning (CNN)",
        "license": "MIT",
        "runtime_sec": 224.2,
        "throughput_fps": 4.4,
        "ram_mb": 850.0,
    },
}


def main():
    os.chdir("D:/automation video clips/clipforge")
    evaluator = CameraCutEvaluator()

    bakeoff_dir = "backend/benchmarks/bakeoff_results"
    all_results = {
        "benchmark_title": "ClipForge Independent Camera Cut Benchmark (v3 Ground Truth)",
        "work_item": "PODCAST-CUT-VALIDATION-015",
        "governance_rule": "Master Engineering Rulebook Rule 15 & Frozen Domain L7",
        "ground_truth_version": "3.0.0 (Independent Reference)",
        "ground_truth_cuts_0_180": 21,
        "ground_truth_cuts_0_300": 30,
        "candidates": {},
    }

    print("\n" + "=" * 90)
    print("CLIPFORGE INDEPENDENT CAMERA-CUT BENCHMARK EXECUTION (AGAINST V3.0.0 GROUND TRUTH)")
    print("=" * 90)

    for cid, meta in CANDIDATE_FILES.items():
        p = os.path.join(bakeoff_dir, meta["file"])
        if not os.path.exists(p):
            print(f"Skipping {cid}: file {p} does not exist")
            continue

        with open(p, "r", encoding="utf-8") as f:
            cdata = json.load(f)

        raw_cuts = cdata.get("detected_cuts", cdata.get("cut_timestamps", []))

        # Evaluate 0-180s (Primary window)
        eval_180_editorial = evaluator.evaluate(
            predictions=raw_cuts, max_time_sec=180.0, include_graphic_inserts=False
        )
        eval_180_all = evaluator.evaluate(
            predictions=raw_cuts, max_time_sec=180.0, include_graphic_inserts=True
        )

        # Evaluate 0-300s (Extended window)
        eval_300_editorial = evaluator.evaluate(
            predictions=raw_cuts, max_time_sec=300.0, include_graphic_inserts=False
        )
        eval_300_all = evaluator.evaluate(
            predictions=raw_cuts, max_time_sec=300.0, include_graphic_inserts=True
        )

        # Primary acceptance gate check: Window 0-180s at tight_120ms tolerance
        t120_180 = eval_180_editorial["tolerance_tiers"]["tight_120ms"]
        gate_verdict = (
            "PASS"
            if (t120_180["precision"] >= 0.90 and t120_180["recall"] >= 0.90)
            else "FAIL"
        )

        candidate_record = {
            "metadata": meta,
            "raw_cuts_in_0_180": len([c for c in raw_cuts if c <= 180.0]),
            "raw_cuts_in_0_300": len([c for c in raw_cuts if c <= 300.0]),
            "total_raw_cuts": len(raw_cuts),
            "gate_verdict_0_180_120ms": gate_verdict,
            "eval_0_180_editorial": eval_180_editorial,
            "eval_0_180_all_transitions": eval_180_all,
            "eval_0_300_editorial": eval_300_editorial,
            "eval_0_300_all_transitions": eval_300_all,
        }

        all_results["candidates"][cid] = candidate_record

        print(
            f"\n--- {meta['name']} ({cid}) ---"
            f"\n  [0-180s Editorial @ 120ms]: P={t120_180['precision']:.3f}, "
            f"R={t120_180['recall']:.3f}, F1={t120_180['f1']:.3f}, "
            f"TP={t120_180['tp']}/21, FP={t120_180['fp']}, FN={t120_180['fn']}, "
            f"MATE={t120_180['mate_sec']*1000:.1f}ms | Gate: {gate_verdict}"
        )
        t120_300 = eval_300_editorial["tolerance_tiers"]["tight_120ms"]
        print(
            f"  [0-300s Editorial @ 120ms]: P={t120_300['precision']:.3f}, "
            f"R={t120_300['recall']:.3f}, F1={t120_300['f1']:.3f}, "
            f"TP={t120_300['tp']}/30, FP={t120_300['fp']}, FN={t120_300['fn']}, "
            f"MATE={t120_300['mate_sec']*1000:.1f}ms"
        )

    out_p = "backend/benchmarks/independent_camera_cut_benchmark_results.json"
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 90)
    print(f"Authoritative benchmark results written to: {out_p}")
    print("=" * 90)


if __name__ == "__main__":
    main()
