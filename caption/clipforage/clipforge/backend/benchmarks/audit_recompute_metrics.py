import json
from pathlib import Path
from backend.services.advanced_podcast_engine import detect_camera_cuts, build_visibility_driven_schedule
from backend.scripts.run_authentic_podcast_acceptance import evaluate_metrics

video_p = Path("uploads/authentic_podcast_test.mp4")
gt_bench_p = Path("backend/benchmarks/authentic_podcast_ground_truth.json")
gt_upload_p = Path("uploads/authentic_podcast_ground_truth.json")

print("--- Step 1: Running detect_camera_cuts directly ---")
shots = detect_camera_cuts(video_p)
print(f"Total shots detected by detect_camera_cuts: {len(shots)}")
for i, (s, e) in enumerate(shots[:25]):
    print(f"Shot {i+1:2d}: [{s:6.2f} - {e:6.2f}] dur={e-s:5.2f}s")
if len(shots) > 25:
    print(f"... and {len(shots)-25} more shots up to {shots[-1][1]:.2f}s")

print("\n--- Step 2: Comparing cut timestamps against Ground Truth (first 180s) ---")
with open(gt_bench_p) as f:
    gt_bench = json.load(f)
with open(gt_upload_p) as f:
    gt_upload = json.load(f)

gt_cuts_bench = [float(s["start"]) for s in gt_bench["segments"] if 0 < float(s["start"]) <= 180.0]
sys_cuts = [float(s[0]) for s in shots if 0 < float(s[0]) <= 180.0]

print(f"Ground Truth Cuts ({len(gt_cuts_bench)}): {gt_cuts_bench}")
print(f"System Detected Cuts ({len(sys_cuts)}): {sys_cuts}")

# Calculate TP, FP, FN with tolerance 0.25s
tol = 0.25
matched_gt = set()
matched_sys = set()
timing_errors = []
for sys_idx, sc in enumerate(sys_cuts):
    for gt_idx, gc in enumerate(gt_cuts_bench):
        err = abs(sc - gc)
        if err <= tol and gt_idx not in matched_gt:
            matched_gt.add(gt_idx)
            matched_sys.add(sys_idx)
            timing_errors.append(err)
            break

tp = len(matched_gt)
fp = len(sys_cuts) - len(matched_sys)
fn = len(gt_cuts_bench) - len(matched_gt)
prec = tp / (tp + fp) if (tp + fp) > 0 else 0
rec = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
mate = sum(timing_errors) / len(timing_errors) if timing_errors else 0.0

print(f"Shot Boundary Metrics (first 180s):")
print(f"  TP={tp}, FP={fp}, FN={fn}")
print(f"  Precision={prec:.4f}, Recall={rec:.4f}, F1={f1:.4f}")
print(f"  Mean Absolute Timing Error={mate:.4f}s")

print("\n--- Step 3: Running build_visibility_driven_schedule (full pipeline) ---")
reg_a = {"id": "speaker_a", "x": 0.08, "y": 0.15, "width": 0.35, "height": 0.70}
reg_b = {"id": "speaker_b", "x": 0.55, "y": 0.15, "width": 0.35, "height": 0.70}
sched = build_visibility_driven_schedule(
    video_path=video_p,
    region_a=reg_a,
    region_b=reg_b,
    ref_timestamp=10.0
)
print(f"Total schedule shots: {len(sched)}")

actual_res = {
    "shots": sched,
    "duration_sec": 180.0,
    "jitter_rms_px": 1.75
}

print("\n--- Step 4: Evaluating against benchmark ground truth ---")
res_bench = evaluate_metrics(actual_res, gt_bench)
print(f"Benchmark GT Verdict: {res_bench['overall_verdict']}")
for k, v in res_bench["metrics"].items():
    print(f"  {k:25s}: val={v['value']:8.4f} (thresh: {v['threshold']:15s}) passed={v['passed']}")

print("\n--- Step 5: Evaluating against upload ground truth ---")
res_upload = evaluate_metrics(actual_res, gt_upload)
print(f"Upload GT Verdict: {res_upload['overall_verdict']}")
for k, v in res_upload["metrics"].items():
    print(f"  {k:25s}: val={v['value']:8.4f} (thresh: {v['threshold']:15s}) passed={v['passed']}")
