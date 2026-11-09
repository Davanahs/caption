"""
ClipForge Camera-Cut Detection Research Bake-off
=================================================
Work Item: PODCAST-CUT-DETECTION-013
Proposal: docs/engineering/proposals/CLIPFORGE_CAMERA_CUT_DETECTION_RESEARCH_PROPOSAL.md

MODE: RESEARCH + ISOLATED BENCHMARK ONLY.
DO NOT modify production detector logic, active dependencies, Docker config,
Python runtime, or frozen L7 code.

Candidates evaluated:
  BASELINE-0  : Current ClipForge detect_camera_cuts (FFmpeg scdet + OpenCV fallback)
  CLASSIC-1   : PySceneDetect AdaptiveDetector
  CLASSIC-2   : PySceneDetect ContentDetector
  CLASSIC-3a  : PySceneDetect HashDetector
  CLASSIC-3b  : PySceneDetect HistogramDetector
  FFMPEG-1    : FFmpeg scdet raw output at multiple thresholds
  (ML-1/TransNetV2 handled separately in transnetv2_bench.py)

Evaluation covers:
  - First 180s (primary acceptance window, matches ground truth annotations)
  - Extended region 180-300s (extended annotations)
  - Metrics: precision, recall, F1, TP, FP, FN, MATE (mean absolute timing error), runtime, fps

Output: backend/benchmarks/bakeoff_results/
"""

import sys
import os
import io

# Force UTF-8 on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import time
import subprocess
import re
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

VIDEO_PATH = REPO_ROOT / "uploads" / "authentic_podcast_test.mp4"
GT_PATH = REPO_ROOT / "backend" / "benchmarks" / "authentic_podcast_ground_truth.json"
RESULTS_DIR = REPO_ROOT / "backend" / "benchmarks" / "bakeoff_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

assert VIDEO_PATH.exists(), f"Authentic video missing: {VIDEO_PATH}"
assert GT_PATH.exists(), f"Ground truth missing: {GT_PATH}"

# ── Load ground truth ─────────────────────────────────────────────────────────
with open(GT_PATH, encoding="utf-8") as f:
    GT = json.load(f)

# Ground-truth cut timestamps (start > 0) for 0-180s window
GT_CUTS_180 = sorted([
    float(s["start"]) for s in GT["segments"]
    if 0.0 < float(s["start"]) <= 180.0
])

# Extended 180-300s window (from extended_segments_180_to_300)
GT_CUTS_300 = sorted([
    float(s["start"]) for s in GT.get("extended_segments_180_to_300", [])
    if 180.0 < float(s["start"]) <= 300.0
])

GT_ALL_CUTS = sorted(GT_CUTS_180 + GT_CUTS_300)

EVAL_WINDOWS = {
    "0-180s": (0.0, 180.0, GT_CUTS_180),
    "0-300s": (0.0, 300.0, GT_ALL_CUTS),
}

print(f"Ground Truth loaded:")
print(f"  0-180s cuts ({len(GT_CUTS_180)}): {GT_CUTS_180}")
print(f"  Extended 180-300s cuts ({len(GT_CUTS_300)}): {GT_CUTS_300}")
print(f"  Video: {VIDEO_PATH} ({VIDEO_PATH.stat().st_size / 1e6:.1f} MB)")
print()


# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_cuts(
    predicted_cuts: List[float],
    gt_cuts: List[float],
    window_start: float,
    window_end: float,
    tolerance: float = 0.25
) -> Dict[str, Any]:
    """
    Greedy one-to-one nearest-neighbor boundary matching.
    Exact-frame metrics (tol=0) and tolerance-based (tol=0.25s, tol=0.5s).
    """
    # Filter predictions to this window
    pred = sorted([c for c in predicted_cuts if window_start < c < window_end])
    gt = sorted([c for c in gt_cuts if window_start < c < window_end])

    results = {}
    for tol in [0.0, 0.25, 0.5]:
        matched_gt = set()
        matched_pred = set()
        timing_errors = []

        for pi, pc in enumerate(pred):
            best_err = float("inf")
            best_gi = None
            for gi, gc in enumerate(gt):
                err = abs(pc - gc)
                if err <= tol and gi not in matched_gt and err < best_err:
                    best_err = err
                    best_gi = gi
            if best_gi is not None:
                matched_gt.add(best_gi)
                matched_pred.add(pi)
                timing_errors.append(best_err)

        tp = len(matched_gt)
        fp = len(pred) - len(matched_pred)
        fn = len(gt) - len(matched_gt)
        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if len(gt) == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if len(gt) == 0 else 0.0)
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        mate = sum(timing_errors) / len(timing_errors) if timing_errors else None

        tol_key = "exact" if tol == 0.0 else f"tol_{int(tol*1000)}ms"
        results[tol_key] = {
            "TP": tp, "FP": fp, "FN": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "F1": round(f1, 4),
            "MATE_s": round(mate, 4) if mate is not None else None,
            "predicted_count": len(pred),
            "gt_count": len(gt),
        }

    return results


def run_evaluation(
    candidate_id: str,
    detected_cuts: List[float],
    elapsed_s: float,
    video_duration_s: float,
    extra_info: Optional[Dict] = None
) -> Dict[str, Any]:
    """Build and save a full evaluation record for one candidate."""
    out_path = RESULTS_DIR / f"{candidate_id.replace(' ', '_').replace('/', '_')}.json"
    if out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            print(f"  [CACHED] Loaded existing results from: {out_path.name}")
            return cached
        except Exception:
            pass

    record: Dict[str, Any] = {
        "candidate_id": candidate_id,
        "elapsed_seconds": round(elapsed_s, 3),
        "video_duration_s": round(video_duration_s, 2),
        "processing_fps": round(video_duration_s / elapsed_s, 2) if elapsed_s > 0 else None,
        "detected_cuts": sorted(detected_cuts),
        "detected_cut_count": len(detected_cuts),
        "extra_info": extra_info or {},
        "windows": {},
    }

    for win_name, (ws, we, gt_cuts) in EVAL_WINDOWS.items():
        record["windows"][win_name] = evaluate_cuts(
            detected_cuts, gt_cuts, ws, we
        )

    # Primary acceptance gate (0-180s, tol 0.25s)
    prim = record["windows"]["0-180s"]["tol_250ms"]
    record["acceptance_gate"] = {
        "precision": prim["precision"],
        "recall": prim["recall"],
        "F1": prim["F1"],
        "pass_precision": prim["precision"] >= 0.95,
        "pass_recall": prim["recall"] >= 0.90,
        "gate_result": "PASS" if (prim["precision"] >= 0.95 and prim["recall"] >= 0.90) else "FAIL"
    }

    out_path = RESULTS_DIR / f"{candidate_id.replace(' ', '_').replace('/', '_')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print(f"  -> Saved: {out_path.name}")
    return record


# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATE 0: BASELINE — Current ClipForge detect_camera_cuts
# ═══════════════════════════════════════════════════════════════════════════════

def run_baseline() -> Dict[str, Any]:
    candidate_id = "BASELINE-0"
    out_path = RESULTS_DIR / f"{candidate_id}.json"
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print("\n" + "="*60)
    print("BASELINE-0: Current ClipForge detect_camera_cuts")
    print("="*60)
    from backend.services.advanced_podcast_engine import detect_camera_cuts

    t0 = time.perf_counter()
    shots = detect_camera_cuts(VIDEO_PATH)
    elapsed = time.perf_counter() - t0

    # Extract cut timestamps (start of each shot except the first)
    cuts = sorted([float(s) for s, e in shots if s > 0.0])
    print(f"  Shots detected: {len(shots)}, Cuts: {len(cuts)}, Time: {elapsed:.2f}s")

    import cv2
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_dur = total_frames / fps
    cap.release()

    return run_evaluation(
        "BASELINE-0",
        cuts,
        elapsed,
        video_dur,
        extra_info={
            "description": "Current ClipForge detect_camera_cuts (FFmpeg scdet primary + OpenCV multi-signal fallback)",
            "parameters": {
                "min_shot_duration": 0.8,
                "cut_threshold": 0.40,
                "sample_fps": 5.0,
                "scdet_threshold": 17.5,
                "composite_score_weights": "0.45 MAE + 0.35 EdgeDiff + 0.20 HistDrop"
            },
            "shot_count": len(shots)
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATES 1-3: PySceneDetect
# ═══════════════════════════════════════════════════════════════════════════════

def run_pyscenedetect_candidate(
    candidate_id: str,
    detector_factory,
    description: str,
    parameters: Dict
) -> Dict[str, Any]:
    out_path = RESULTS_DIR / f"{candidate_id.replace(' ', '_').replace('/', '_')}.json"
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"\n{'='*60}")
    print(f"{candidate_id}: {description}")
    print("="*60)

    from scenedetect import open_video, SceneManager

    t0 = time.perf_counter()
    video = open_video(str(VIDEO_PATH))
    scene_manager = SceneManager()
    scene_manager.add_detector(detector_factory())
    scene_manager.detect_scenes(video, show_progress=False)
    scene_list = scene_manager.get_scene_list()
    elapsed = time.perf_counter() - t0

    # Get video duration
    from scenedetect import open_video as ov
    v2 = ov(str(VIDEO_PATH))
    video_dur = v2.duration.get_seconds()

    # Cut timestamps = start of each scene except the first
    cuts = []
    for i, (start_tc, end_tc) in enumerate(scene_list):
        if i > 0:
            cuts.append(round(start_tc.get_seconds(), 3))

    print(f"  Scenes detected: {len(scene_list)}, Cuts: {len(cuts)}, Time: {elapsed:.2f}s")

    return run_evaluation(
        candidate_id, cuts, elapsed, video_dur,
        extra_info={
            "description": description,
            "parameters": parameters,
            "scene_count": len(scene_list),
            "library": "PySceneDetect 0.7.2",
            "license": "BSD-3-Clause"
        }
    )


def run_classic1_adaptive():
    from scenedetect.detectors import AdaptiveDetector
    return run_pyscenedetect_candidate(
        "CLASSIC-1_AdaptiveDetector",
        lambda: AdaptiveDetector(),
        "PySceneDetect AdaptiveDetector (default parameters)",
        {"adaptive_threshold": 3.0, "min_scene_len": 15, "window_width": 2}
    )


def run_classic2_content():
    from scenedetect.detectors import ContentDetector
    return run_pyscenedetect_candidate(
        "CLASSIC-2_ContentDetector",
        lambda: ContentDetector(threshold=27.0, min_scene_len=15),
        "PySceneDetect ContentDetector (default threshold=27)",
        {"threshold": 27.0, "min_scene_len": 15, "weights": "default (luma+chroma+hue)"}
    )


def run_classic2b_content_edge():
    """ContentDetector with edge-change weighting as described in proposal."""
    from scenedetect.detectors import ContentDetector
    try:
        # Try the weights parameter if available in 0.7.2
        from scenedetect.detectors import ContentDetector
        weights = ContentDetector.Components(
            delta_hue=1.0, delta_sat=1.0, delta_lum=1.0, delta_edges=0.5
        )
        det = ContentDetector(threshold=27.0, weights=weights, min_scene_len=15)
        det_factory = lambda: ContentDetector(threshold=27.0, weights=weights, min_scene_len=15)
        params = {"threshold": 27.0, "min_scene_len": 15, "weights": "with delta_edges=0.5"}
    except Exception:
        det_factory = lambda: ContentDetector(threshold=27.0, min_scene_len=15)
        params = {"threshold": 27.0, "min_scene_len": 15, "note": "edge weight not available in this version"}

    return run_pyscenedetect_candidate(
        "CLASSIC-2b_ContentDetector_EdgeWeighted",
        det_factory,
        "PySceneDetect ContentDetector with edge-change weighting experiment",
        params
    )


def run_classic3a_hash():
    try:
        from scenedetect.detectors import HashDetector
        return run_pyscenedetect_candidate(
            "CLASSIC-3a_HashDetector",
            lambda: HashDetector(),
            "PySceneDetect HashDetector (perceptual hash, control)",
            {"size": 16, "lowpass": 2, "threshold": 0.395}
        )
    except ImportError:
        print("  HashDetector not available in this scenedetect build — skipping")
        return None


def run_classic3b_histogram():
    try:
        from scenedetect.detectors import HistogramDetector
        return run_pyscenedetect_candidate(
            "CLASSIC-3b_HistogramDetector",
            lambda: HistogramDetector(),
            "PySceneDetect HistogramDetector (Y-channel histogram, control)",
            {"threshold": 0.05, "bins": 256, "min_scene_len": 15}
        )
    except ImportError:
        print("  HistogramDetector not available in this scenedetect build — skipping")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATE FFMPEG-1: FFmpeg scdet at multiple thresholds
# ═══════════════════════════════════════════════════════════════════════════════

def run_ffmpeg_scdet(threshold: float = 17.5, candidate_suffix: str = "default") -> Dict[str, Any]:
    candidate_id = f"FFMPEG-1_scdet_thr{threshold:.1f}"
    out_path = RESULTS_DIR / f"{candidate_id.replace(' ', '_').replace('/', '_')}.json"
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"\n{'='*60}")
    print(f"{candidate_id}: FFmpeg scdet threshold={threshold}")
    print("="*60)

    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg_bin, "-hide_banner", "-nostats",
        "-i", str(VIDEO_PATH),
        "-vf", f"scdet=threshold={threshold}",
        "-f", "null", "-"
    ]

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    elapsed = time.perf_counter() - t0

    cuts = []
    for line in proc.stderr.splitlines():
        if "lavfi.scd.time" in line:
            m = re.search(r"lavfi\.scd\.time:\s*([\d\.]+)", line)
            if m:
                t = round(float(m.group(1)), 3)
                cuts.append(t)

    cuts = sorted(set(cuts))

    # Get duration from ffprobe
    try:
        fp = subprocess.run(
            [shutil.which("ffprobe") or "ffprobe", "-v", "error",
             "-show_entries", "format=duration", "-of", "csv=p=0", str(VIDEO_PATH)],
            capture_output=True, text=True, timeout=30
        )
        video_dur = float(fp.stdout.strip())
    except Exception:
        video_dur = 981.0  # from ground truth metadata

    print(f"  Raw cuts detected: {len(cuts)}, Time: {elapsed:.2f}s")

    return run_evaluation(
        candidate_id, cuts, elapsed, video_dur,
        extra_info={
            "description": f"FFmpeg scdet filter (threshold={threshold})",
            "parameters": {"threshold": threshold, "filter": "scdet"},
            "ffmpeg_version": "N-123074-g4e32fb4c2a-20260228",
            "license": "GPL-2.0 (FFmpeg)"
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PYTH-ONLY OpenCV Baseline: pure HSV histogram (documents current failure mode)
# ═══════════════════════════════════════════════════════════════════════════════

def run_pure_hsv_histogram(threshold: float = 0.40) -> Dict[str, Any]:
    """
    Pure global HSV histogram correlation — documents the original failure mode
    mentioned in the proposal (prior approach, not the current production code).
    """
    candidate_id = f"CLASSIC-0_PureHSVHist_thr{threshold:.2f}"
    out_path = RESULTS_DIR / f"{candidate_id.replace(' ', '_').replace('/', '_')}.json"
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"\n{'='*60}")
    print(f"{candidate_id}: Pure HSV Histogram (original failure mode reproduction)")
    print("="*60)

    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_dur = total_frames / fps
    frame_step = max(1, int(fps / 5.0))  # 5fps sampling

    cuts = []
    prev_hist = None
    frame_idx = 0

    t0 = time.perf_counter()
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_step == 0:
            current_time = round(frame_idx / fps, 2)
            small = cv2.resize(frame, (160, 90))
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
            cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

            if prev_hist is not None:
                corr = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                # Cut when correlation drops below threshold (1-threshold = drop threshold)
                if corr < threshold and current_time > 0.05:
                    cuts.append(current_time)

            prev_hist = hist
        frame_idx += 1
    cap.release()
    elapsed = time.perf_counter() - t0

    # Deduplicate nearby cuts (min 0.8s apart)
    deduped = []
    for c in sorted(cuts):
        if not deduped or (c - deduped[-1]) >= 0.8:
            deduped.append(c)

    print(f"  Raw cuts: {len(cuts)}, Deduped: {len(deduped)}, Time: {elapsed:.2f}s")

    return run_evaluation(
        candidate_id, deduped, elapsed, video_dur,
        extra_info={
            "description": "Pure global HSV histogram correlation (original failure mode)",
            "parameters": {"threshold": threshold, "sample_fps": 5.0, "bins": "24H×24S"},
            "note": "Documents why the histogram-only approach fails on same-background podcasts"
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary_table(all_results: List[Dict[str, Any]]) -> None:
    print("\n" + "="*100)
    print("BAKE-OFF SUMMARY TABLE (0-180s window, ±0.25s tolerance)")
    print("="*100)
    header = f"{'Candidate':<45} {'Prec':>6} {'Rec':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4} {'MATE':>7} {'Time':>7} {'Gate'}"
    print(header)
    print("-"*100)

    for r in all_results:
        if r is None:
            continue
        cid = r["candidate_id"][:44]
        prim = r["windows"]["0-180s"]["tol_250ms"]
        gate = r["acceptance_gate"]["gate_result"]
        mate = prim["MATE_s"]
        mate_str = f"{mate:.3f}s" if mate is not None else "  N/A "
        print(
            f"{cid:<45} {prim['precision']:>6.3f} {prim['recall']:>6.3f} "
            f"{prim['F1']:>6.3f} {prim['TP']:>4d} {prim['FP']:>4d} {prim['FN']:>4d} "
            f"{mate_str:>7} {r['elapsed_seconds']:>6.1f}s  {gate}"
        )
    print("="*100)
    print("Acceptance gate: Precision ≥ 0.95 AND Recall ≥ 0.90 (at ±0.25s tolerance)")
    print()


def main():
    print(f"\n{'#'*60}")
    print("# ClipForge Camera-Cut Detection Research Bake-off")
    print(f"# Work Item: PODCAST-CUT-DETECTION-013")
    print(f"# Mode: RESEARCH ONLY — no production code modified")
    print(f"# Video: {VIDEO_PATH.name} ({VIDEO_PATH.stat().st_size / 1e6:.0f} MB)")
    print(f"# GT cuts 0-180s: {len(GT_CUTS_180)}")
    print(f"# GT cuts 180-300s: {len(GT_CUTS_300)}")
    print(f"{'#'*60}")

    results = []

    # Step 1: Document pure HSV failure mode
    results.append(run_pure_hsv_histogram(threshold=0.40))

    # Step 2: Baseline — current ClipForge production detector
    results.append(run_baseline())

    # Step 3: FFmpeg scdet at multiple thresholds
    for thr in [8.0, 12.0, 17.5, 22.0, 30.0]:
        results.append(run_ffmpeg_scdet(threshold=thr))

    # Step 4: PySceneDetect candidates
    results.append(run_classic1_adaptive())
    results.append(run_classic2_content())
    results.append(run_classic2b_content_edge())
    results.append(run_classic3a_hash())
    results.append(run_classic3b_histogram())

    # Filter out None (skipped detectors)
    results = [r for r in results if r is not None]

    # Print summary
    print_summary_table(results)

    # Save combined report
    combined_path = RESULTS_DIR / "bakeoff_combined_report.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump({
            "title": "ClipForge Camera-Cut Detection Research Bake-off",
            "work_item": "PODCAST-CUT-DETECTION-013",
            "video": str(VIDEO_PATH),
            "ground_truth": str(GT_PATH),
            "ground_truth_cuts_0_180s": GT_CUTS_180,
            "ground_truth_cuts_180_300s": GT_CUTS_300,
            "results": results
        }, f, indent=2)
    print(f"Combined report saved: {combined_path}")
    return results


if __name__ == "__main__":
    main()

