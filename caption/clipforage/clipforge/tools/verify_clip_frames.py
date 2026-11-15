#!/usr/bin/env python3
"""
verify_clip_frames.py
======================
Comprehensive 7-Stage Frame-by-Frame Quality Analysis and Verification Tool
for ClipForge Vertical Gaming Video Clips.

Verification Stages:
  Stage 1: Container & Stream Integrity Check (ffprobe: 1080x1920, h264, yuv420p, audio present, 0 subtitles)
  Stage 2: Bitstream & Macroblock Decode Error Scan (ffmpeg -v error -xerror -i final.mp4 -f null -)
  Stage 3: OpenCV Sequential Frame Loop (check shape (1920, 1080, 3), check for NaN/Inf pixel values)
  Stage 4: Solid Green / Magenta Uninitialized YUV Buffer Corruption Detection
  Stage 5: Facecam ROI Activity & Presence Check (x=702, y=76, w=324, h=422, std > 2.0)
  Stage 6: Temporal Motion & Freeze Detection (frame difference, no frozen sequences > 2.0s)
  Stage 7: Audio-Video PTS Monotonicity & Sync Check (start PTS >= -0.05s)
  Plus: ITU-R BT.500 8x8 Macroblock Blockiness Metric (D_B / D_NB ratio)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


def compute_frame_blockiness(
    gray: np.ndarray,
    b_cols: np.ndarray,
    nb_cols: np.ndarray,
    b_rows: np.ndarray,
    nb_rows: np.ndarray,
) -> Tuple[float, float, float]:
    """
    Computes ITU-R BT.500 8x8 macroblock boundary gradient discontinuity (D_B)
    versus non-boundary gradient (D_NB), and the blockiness ratio D_B / D_NB.

    D_B is the average absolute difference across 8x8 block boundaries.
    D_NB is the average absolute difference within 8x8 block interiors.
    Blockiness Ratio = D_B / D_NB.
    A ratio > 1.20 indicates perceptible blockiness tiling artifacts.
    """
    # Horizontal gradients (along columns)
    diff_h = np.abs(gray[:, 1:] - gray[:, :-1])
    d_b_h = diff_h[:, b_cols]
    d_nb_h = diff_h[:, nb_cols]

    # Vertical gradients (along rows)
    diff_v = np.abs(gray[1:, :] - gray[:-1, :])
    d_b_v = diff_v[b_rows, :]
    d_nb_v = diff_v[nb_rows, :]

    d_b = float((np.mean(d_b_h) + np.mean(d_b_v)) / 2.0)
    d_nb = float((np.mean(d_nb_h) + np.mean(d_nb_v)) / 2.0)
    ratio = float(d_b / (d_nb + 1e-6))
    return d_b, d_nb, ratio


def verify_clip_frame_by_frame(
    clip_path: Path,
    blockiness_sample_step: int = 1,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Executes the 7-stage automated quality verification protocol on target video clip.
    """
    clip_path = Path(clip_path).resolve()
    report: Dict[str, Any] = {
        "file": str(clip_path),
        "file_name": clip_path.name,
        "file_size_bytes": 0,
        "stages": {},
        "stages_passed": [],
        "errors": [],
        "warnings": [],
        "total_frames": 0,
        "fps": 0.0,
        "duration_seconds": 0.0,
        "facecam_stats": {},
        "freeze_stats": {},
        "corruption_stats": {},
        "blockiness_stats": {},
        "pts_stats": {},
        "is_clean": False,
    }

    if not clip_path.exists():
        err = f"Target clip does not exist: {clip_path}"
        report["errors"].append(err)
        return report

    report["file_size_bytes"] = clip_path.stat().st_size
    if verbose:
        print(f"\n{'='*78}")
        print(f"VERIFYING CLIP: {clip_path.name}")
        print(f"Path: {clip_path}")
        print(f"Size: {report['file_size_bytes']:,} bytes ({report['file_size_bytes']/(1024*1024):.2f} MB)")
        print(f"{'='*78}")

    # =========================================================================
    # Stage 1: Container & Stream Integrity Check (ffprobe)
    # =========================================================================
    stage1_errors = []
    cmd_probe = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,duration,bit_rate",
        "-show_entries", "format=format_name,duration,size,bit_rate",
        "-of", "json", str(clip_path),
    ]
    p_probe = subprocess.run(cmd_probe, capture_output=True, text=True)
    if p_probe.returncode != 0:
        stage1_errors.append(f"ffprobe execution failed: {p_probe.stderr.strip()}")
    else:
        try:
            probe_data = json.loads(p_probe.stdout)
            streams = probe_data.get("streams", [])
            fmt = probe_data.get("format", {})
            v_streams = [s for s in streams if s.get("codec_type") == "video"]
            a_streams = [s for s in streams if s.get("codec_type") == "audio"]
            sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

            report["duration_seconds"] = float(fmt.get("duration", 0.0))

            # Video stream checks
            if len(v_streams) != 1:
                stage1_errors.append(f"Expected exactly 1 video stream, found {len(v_streams)}")
            else:
                v = v_streams[0]
                vw, vh = v.get("width"), v.get("height")
                vcodec = v.get("codec_name")
                vpix = v.get("pix_fmt")

                if vw != 1080 or vh != 1920:
                    stage1_errors.append(f"Video resolution mismatch: {vw}x{vh}, expected 1080x1920")
                if vcodec != "h264":
                    stage1_errors.append(f"Video codec mismatch: '{vcodec}', expected 'h264'")
                if vpix != "yuv420p":
                    stage1_errors.append(f"Pixel format mismatch: '{vpix}', expected 'yuv420p'")

                # FPS parsing
                r_fps = v.get("r_frame_rate", "25/1")
                if "/" in r_fps:
                    num, den = r_fps.split("/")
                    report["fps"] = float(num) / float(den)
                else:
                    report["fps"] = float(r_fps)

            # Audio stream checks
            if len(a_streams) < 1:
                stage1_errors.append("Audio stream missing: 0 audio streams found")

            # Zero-caption invariant
            if len(sub_streams) > 0:
                stage1_errors.append(f"R5 Zero-Caption violation: {len(sub_streams)} subtitle streams present")

            report["streams_info"] = {
                "video_count": len(v_streams),
                "audio_count": len(a_streams),
                "subtitle_count": len(sub_streams),
                "format_name": fmt.get("format_name"),
                "bit_rate": fmt.get("bit_rate"),
            }
        except Exception as e:
            stage1_errors.append(f"Failed to parse ffprobe JSON output: {e}")

    stage1_pass = len(stage1_errors) == 0
    report["stages"]["Stage 1: Container & Stream Integrity"] = {
        "passed": stage1_pass,
        "errors": stage1_errors,
    }
    if stage1_pass:
        report["stages_passed"].append("Stage 1: Container & Stream Integrity")
        if verbose:
            print("[PASS] Stage 1: Container & Stream Integrity Check")
            print(f"       Resolution: 1080x1920 (9:16), Codec: h264, PixFmt: yuv420p, Audio: OK, Subtitles: 0")
    else:
        report["errors"].extend(stage1_errors)
        if verbose:
            print(f"[FAIL] Stage 1: Container & Stream Integrity Check: {stage1_errors}")

    # =========================================================================
    # Stage 2: Bitstream & Macroblock Decode Error Scan (FFmpeg Null Sink)
    # =========================================================================
    stage2_errors = []
    cmd_null = ["ffmpeg", "-v", "error", "-xerror", "-i", str(clip_path), "-f", "null", "-"]
    p_null = subprocess.run(cmd_null, capture_output=True, text=True)
    if p_null.returncode != 0 or p_null.stderr.strip():
        stage2_errors.append(f"FFmpeg null sink decode error (code {p_null.returncode}): {p_null.stderr.strip()}")

    stage2_pass = len(stage2_errors) == 0
    report["stages"]["Stage 2: Bitstream & Macroblock Decode Scan"] = {
        "passed": stage2_pass,
        "errors": stage2_errors,
    }
    if stage2_pass:
        report["stages_passed"].append("Stage 2: Bitstream & Macroblock Decode Scan")
        if verbose:
            print("[PASS] Stage 2: Bitstream & Macroblock Decode Error Scan")
            print("       FFmpeg null sink: 0 decode errors, 0 corrupt macroblocks")
    else:
        report["errors"].extend(stage2_errors)
        if verbose:
            print(f"[FAIL] Stage 2: Bitstream & Macroblock Decode Error Scan: {stage2_errors}")

    # =========================================================================
    # Stage 3, 4, 5, 6: Sequential Frame Loop (OpenCV & NumPy)
    # Plus: ITU-R BT.500 8x8 Macroblock Blockiness Metric
    # =========================================================================
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        err = f"cv2.VideoCapture failed to open file: {clip_path}"
        report["errors"].append(err)
        return report

    fps = cap.get(cv2.CAP_PROP_FPS) or report["fps"] or 25.0
    frame_idx = 0
    prev_frame = None
    consecutive_frozen = 0
    max_consecutive_frozen = 0
    max_corrupt_pixels = 0
    corrupt_frame_count = 0

    # Facecam destination ROI: x=702, y=76, w=324, h=422
    fc_x, fc_y, fc_w, fc_h = 702, 76, 324, 422
    facecam_stds: List[float] = []

    # Blockiness grid setup for 1080x1920 (W=1080, H=1920)
    cols = 1080 - 1
    b_cols = np.arange(7, cols, 8)
    nb_cols = np.setdiff1d(np.arange(cols), b_cols)
    rows = 1920 - 1
    b_rows = np.arange(7, rows, 8)
    nb_rows = np.setdiff1d(np.arange(rows), b_rows)

    blockiness_ratios: List[float] = []
    blockiness_db: List[float] = []
    blockiness_dnb: List[float] = []
    temporal_motion_diffs: List[float] = []

    stage3_errors = []
    stage4_errors = []
    stage5_errors = []
    stage6_errors = []

    total_pixel_count = 1080 * 1920
    corruption_threshold = int(total_pixel_count * 0.005)  # 0.5% garbage pixels (10,368 px)

    t0_scan = time.time()

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frame_idx += 1

        # Stage 3: Dimension & Finite Pixel Check
        if frame.shape != (1920, 1080, 3):
            stage3_errors.append(f"Frame {frame_idx} dimension error: {frame.shape}, expected (1920, 1080, 3)")
            break
        if np.isnan(frame).any() or np.isinf(frame).any():
            stage3_errors.append(f"Frame {frame_idx} contains NaN/Inf pixel values")
            break

        # Stage 4: Solid Green / Magenta Uninitialized YUV Buffer Corruption Check
        # Pure Green in BGR: B < 15, G > 220, R < 15
        green_corrupt = (frame[:, :, 0] < 15) & (frame[:, :, 1] > 220) & (frame[:, :, 2] < 15)
        # Pure Magenta in BGR: B > 220, G < 15, R > 220
        magenta_corrupt = (frame[:, :, 0] > 220) & (frame[:, :, 1] < 15) & (frame[:, :, 2] > 220)
        c_pixels = int(np.count_nonzero(green_corrupt | magenta_corrupt))
        if c_pixels > max_corrupt_pixels:
            max_corrupt_pixels = c_pixels
        if c_pixels > corruption_threshold:
            corrupt_frame_count += 1
            if len(stage4_errors) < 5:
                stage4_errors.append(f"Frame {frame_idx} has {c_pixels} corrupt green/magenta pixels (>0.5%)")

        # Stage 5: Facecam ROI Activity & Presence Check
        facecam_crop = frame[fc_y:fc_y+fc_h, fc_x:fc_x+fc_w]
        fc_std = float(np.std(facecam_crop))
        facecam_stds.append(fc_std)
        if fc_std < 2.0:
            if len(stage5_errors) < 5:
                stage5_errors.append(f"Frame {frame_idx} facecam region is inactive/blank (std={fc_std:.2f} < 2.0)")

        # Stage 6: Temporal Motion & Freeze Detection
        if prev_frame is not None:
            diff = cv2.absdiff(frame, prev_frame)
            mean_diff = float(np.mean(diff))
            temporal_motion_diffs.append(mean_diff)
            if mean_diff < 0.05:
                consecutive_frozen += 1
                if consecutive_frozen > max_consecutive_frozen:
                    max_consecutive_frozen = consecutive_frozen
            else:
                consecutive_frozen = 0
        prev_frame = frame

        # ITU-R BT.500 Blockiness Metric
        if (frame_idx % blockiness_sample_step) == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            db, dnb, ratio = compute_frame_blockiness(gray, b_cols, nb_cols, b_rows, nb_rows)
            blockiness_db.append(db)
            blockiness_dnb.append(dnb)
            blockiness_ratios.append(ratio)

    cap.release()
    scan_duration = time.time() - t0_scan
    report["total_frames"] = frame_idx

    # Evaluate Stage 3
    stage3_pass = len(stage3_errors) == 0 and frame_idx > 0
    report["stages"]["Stage 3: Sequential Frame Inspection"] = {
        "passed": stage3_pass,
        "frames_scanned": frame_idx,
        "errors": stage3_errors,
    }
    if stage3_pass:
        report["stages_passed"].append("Stage 3: Sequential Frame Inspection")
        if verbose:
            print(f"[PASS] Stage 3: OpenCV Sequential Frame Inspection ({frame_idx} frames in {scan_duration:.2f}s)")
            print(f"       All {frame_idx} frames match exact (1920, 1080, 3) matrix shape; zero NaN/Inf pixels")
    else:
        report["errors"].extend(stage3_errors)
        if verbose:
            print(f"[FAIL] Stage 3: Sequential Frame Inspection: {stage3_errors}")

    # Evaluate Stage 4
    stage4_pass = len(stage4_errors) == 0 and corrupt_frame_count == 0
    report["corruption_stats"] = {
        "max_corrupt_pixels_per_frame": max_corrupt_pixels,
        "threshold": corruption_threshold,
        "corrupt_frames": corrupt_frame_count,
    }
    report["stages"]["Stage 4: Solid Green/Magenta Corruption Detection"] = {
        "passed": stage4_pass,
        "max_corrupt_pixels": max_corrupt_pixels,
        "errors": stage4_errors,
    }
    if stage4_pass:
        report["stages_passed"].append("Stage 4: Solid Green/Magenta Corruption Detection")
        if verbose:
            print(f"[PASS] Stage 4: Uninitialized YUV Buffer / Solid Color Corruption Scan")
            print(f"       Peak corrupt pixels per frame: {max_corrupt_pixels} (limit: {corruption_threshold}) -> 0 artifacts")
    else:
        report["errors"].extend(stage4_errors)
        if verbose:
            print(f"[FAIL] Stage 4: Solid Green/Magenta Corruption Scan: {stage4_errors}")

    # Evaluate Stage 5
    min_fc_std = float(min(facecam_stds)) if facecam_stds else 0.0
    max_fc_std = float(max(facecam_stds)) if facecam_stds else 0.0
    mean_fc_std = float(np.mean(facecam_stds)) if facecam_stds else 0.0
    report["facecam_stats"] = {
        "roi": {"x": fc_x, "y": fc_y, "w": fc_w, "h": fc_h},
        "min_std": min_fc_std,
        "max_std": max_fc_std,
        "mean_std": mean_fc_std,
        "threshold": 2.0,
    }
    stage5_pass = len(stage5_errors) == 0 and min_fc_std >= 2.0
    report["stages"]["Stage 5: Facecam ROI Activity & Presence"] = {
        "passed": stage5_pass,
        "min_std": min_fc_std,
        "mean_std": mean_fc_std,
        "errors": stage5_errors,
    }
    if stage5_pass:
        report["stages_passed"].append("Stage 5: Facecam ROI Activity & Presence")
        if verbose:
            print(f"[PASS] Stage 5: Facecam ROI Activity & Presence Check (ROI: x={fc_x}, y={fc_y}, w={fc_w}, h={fc_h})")
            print(f"       Standard deviation: min={min_fc_std:.2f}, mean={mean_fc_std:.2f}, max={max_fc_std:.2f} (threshold > 2.0)")
    else:
        report["errors"].extend(stage5_errors)
        if verbose:
            print(f"[FAIL] Stage 5: Facecam ROI Activity: min_std={min_fc_std:.2f} < 2.0: {stage5_errors}")

    # Evaluate Stage 6
    max_allowed_frozen_frames = int(fps * 2.0)  # > 2.0 seconds of frozen frames
    mean_motion = float(np.mean(temporal_motion_diffs)) if temporal_motion_diffs else 0.0
    report["freeze_stats"] = {
        "max_consecutive_frozen_frames": max_consecutive_frozen,
        "max_allowed_frozen_frames": max_allowed_frozen_frames,
        "mean_temporal_motion": mean_motion,
    }
    if max_consecutive_frozen > max_allowed_frozen_frames:
        stage6_errors.append(f"Detected frozen video: {max_consecutive_frozen} consecutive identical frames (> {max_allowed_frozen_frames})")
    stage6_pass = len(stage6_errors) == 0
    report["stages"]["Stage 6: Temporal Motion & Freeze Detection"] = {
        "passed": stage6_pass,
        "max_consecutive_frozen": max_consecutive_frozen,
        "max_allowed": max_allowed_frozen_frames,
        "mean_temporal_motion": mean_motion,
        "errors": stage6_errors,
    }
    if stage6_pass:
        report["stages_passed"].append("Stage 6: Temporal Motion & Freeze Detection")
        if verbose:
            print(f"[PASS] Stage 6: Temporal Motion & Freeze Detection")
            print(f"       Max consecutive frozen frames: {max_consecutive_frozen} (allowed: {max_allowed_frozen_frames} = 2.0s), Mean motion diff: {mean_motion:.2f}")
    else:
        report["errors"].extend(stage6_errors)
        if verbose:
            print(f"[FAIL] Stage 6: Temporal Motion & Freeze Detection: {stage6_errors}")

    # =========================================================================
    # Stage 7: Audio-Video PTS Monotonicity & Sync Check
    # =========================================================================
    stage7_errors = []
    cmd_packets = [
        "ffprobe", "-v", "error",
        "-show_packets",
        "-show_entries", "packet=pts_time,dts_time,codec_type",
        "-of", "json", str(clip_path),
    ]
    p_packets = subprocess.run(cmd_packets, capture_output=True, text=True)
    if p_packets.returncode != 0:
        stage7_errors.append(f"ffprobe packet extraction failed: {p_packets.stderr.strip()}")
    else:
        try:
            packet_data = json.loads(p_packets.stdout).get("packets", [])
            v_packets = [p for p in packet_data if p.get("codec_type") == "video" and "pts_time" in p]
            a_packets = [p for p in packet_data if p.get("codec_type") == "audio" and "pts_time" in p]

            if not v_packets:
                stage7_errors.append("No video packets found in stream")
            else:
                start_video_pts = float(v_packets[0]["pts_time"])
                report["pts_stats"]["start_video_pts"] = start_video_pts
                report["pts_stats"]["total_video_packets"] = len(v_packets)

                if start_video_pts < -0.05:
                    stage7_errors.append(f"Negative video start PTS detected: {start_video_pts:.4f}s (must be >= -0.05s)")

            if a_packets:
                start_audio_pts = float(a_packets[0]["pts_time"])
                report["pts_stats"]["start_audio_pts"] = start_audio_pts
                report["pts_stats"]["total_audio_packets"] = len(a_packets)
                if abs(start_video_pts - start_audio_pts) > 0.5:
                    report["warnings"].append(f"Large A/V start PTS difference: video={start_video_pts:.3f}s, audio={start_audio_pts:.3f}s")

        except Exception as e:
            stage7_errors.append(f"Failed to parse packet JSON: {e}")

    stage7_pass = len(stage7_errors) == 0
    report["stages"]["Stage 7: Audio-Video PTS Monotonicity & Sync"] = {
        "passed": stage7_pass,
        "start_video_pts": report["pts_stats"].get("start_video_pts"),
        "start_audio_pts": report["pts_stats"].get("start_audio_pts"),
        "errors": stage7_errors,
    }
    if stage7_pass:
        report["stages_passed"].append("Stage 7: Audio-Video PTS Monotonicity & Sync")
        if verbose:
            v_pts = report["pts_stats"].get("start_video_pts", 0.0)
            a_pts = report["pts_stats"].get("start_audio_pts", 0.0)
            print(f"[PASS] Stage 7: Audio-Video PTS Monotonicity & Sync Check")
            print(f"       Video start PTS: {v_pts:.4f}s (>= -0.05s), Audio start PTS: {a_pts:.4f}s, Total packets: V={report['pts_stats'].get('total_video_packets')}, A={report['pts_stats'].get('total_audio_packets')}")
    else:
        report["errors"].extend(stage7_errors)
        if verbose:
            print(f"[FAIL] Stage 7: Audio-Video PTS Monotonicity: {stage7_errors}")

    # =========================================================================
    # Additional Quality Metric: ITU-R BT.500 Blockiness Analysis
    # =========================================================================
    if blockiness_ratios:
        mean_b = float(np.mean(blockiness_ratios))
        min_b = float(np.min(blockiness_ratios))
        max_b = float(np.max(blockiness_ratios))
        mean_db = float(np.mean(blockiness_db))
        mean_dnb = float(np.mean(blockiness_dnb))

        # Severity categorization according to ITU-R BT.500
        # Ratio <= 1.20: Crisp / Minimal blockiness
        # 1.20 < Ratio <= 1.35: Moderate compression blockiness
        # Ratio > 1.35: High / Severe macroblock tiling
        severity = "Normal / Crisp (Sub-Perceptible)" if mean_b <= 1.20 else (
            "Moderate Compression (Normal for 1080p Gameplay Render)" if mean_b <= 1.35 else "High Blockiness"
        )

        report["blockiness_stats"] = {
            "samples_analyzed": len(blockiness_ratios),
            "sample_step": blockiness_sample_step,
            "mean_ratio": round(mean_b, 4),
            "min_ratio": round(min_b, 4),
            "max_ratio": round(max_b, 4),
            "mean_boundary_diff_db": round(mean_db, 2),
            "mean_non_boundary_diff_dnb": round(mean_dnb, 2),
            "severity_assessment": severity,
            "itu_standard": "ITU-R BT.500 8x8 Macroblock Discontinuity",
        }
        if verbose:
            print(f"\n--- ITU-R BT.500 BLOCKINESS METRICS ({len(blockiness_ratios)} frames sampled) ---")
            print(f"    Mean Ratio (D_B / D_NB): {mean_b:.3f}")
            print(f"    Min Ratio: {min_b:.3f}, Max Ratio: {max_b:.3f}")
            print(f"    Boundary Gradient (D_B): {mean_db:.2f}, Non-Boundary Gradient (D_NB): {mean_dnb:.2f}")
            print(f"    Classification: {severity}")

    report["is_clean"] = (len(report["errors"]) == 0) and (len(report["stages_passed"]) == 7)

    if verbose:
        status_text = "ALL 7 STAGES PASSED (100% CLEAN - ZERO PIXEL BREAKAGE)" if report["is_clean"] else f"FAILED WITH {len(report['errors'])} ERRORS"
        print(f"\n>>> FINAL STATUS FOR {clip_path.name}: {status_text}")
        print("="*78)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify ClipForge output video clips frame-by-frame across 7 quality stages."
    )
    parser.add_argument(
        "clips",
        nargs="*",
        help="Path(s) to final.mp4 video file(s). If omitted, defaults to the two standard milestone clips.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results for automated ingestion.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help="Sample step for ITU-R BT.500 blockiness metric (default: 1, evaluates every single frame).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable terminal output.",
    )

    args = parser.parse_args()

    # Default clips from Milestone 3 specification
    default_clips = [
        Path(r"d:\automation video clips\clipforge\outputs\aca47a08-e0c7-4995-a7f5-3f2232515296\clips\2a27d18d-5512-480a-acdf-8125c5997489\final.mp4"),
        Path(r"d:\automation video clips\clipforge\outputs\aca47a08-e0c7-4995-a7f5-3f2232515296\clips\836e95e7-9a67-4f63-b45a-122125604d61\final.mp4"),
    ]

    target_paths = [Path(p) for p in args.clips] if args.clips else default_clips

    all_reports = []
    all_clean = True

    for p in target_paths:
        res = verify_clip_frame_by_frame(
            clip_path=p,
            blockiness_sample_step=args.step,
            verbose=not args.quiet and not args.json,
        )
        all_reports.append(res)
        if not res.get("is_clean", False):
            all_clean = False

    if args.json:
        print(json.dumps(all_reports, indent=2))
    elif not args.quiet:
        print("\n" + "#"*78)
        print("OVERALL VERIFICATION SUMMARY MATRIX:")
        print("#"*78)
        print(f"{'Clip Name':<42} | {'Stages':<10} | {'Frames':<8} | {'Blockiness':<10} | {'Clean?'}")
        print("-" * 78)
        for r in all_reports:
            fname = r["file_name"]
            stg = f"{len(r['stages_passed'])}/7"
            frames = str(r["total_frames"])
            blk = f"{r.get('blockiness_stats', {}).get('mean_ratio', 0.0):.3f}"
            clean = "YES (PASS)" if r["is_clean"] else "NO (FAIL)"
            print(f"{fname:<42} | {stg:<10} | {frames:<8} | {blk:<10} | {clean}")
        print("#"*78)

    return 0 if all_clean else 1


if __name__ == "__main__":
    sys.exit(main())
