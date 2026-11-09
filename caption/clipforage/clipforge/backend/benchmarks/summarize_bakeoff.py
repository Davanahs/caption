import json
from pathlib import Path

res_dir = Path("backend/benchmarks/bakeoff_results")
files = sorted(res_dir.glob("*.json"))

print("=" * 115)
print("COMPREHENSIVE BAKE-OFF COMPARISON ACROSS ALL CANDIDATES & EVALUATION WINDOWS")
print("=" * 115)
print(f"{'Candidate':<40} {'Window':<8} {'Prec':>6} {'Rec':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4} {'Time':>7} {'FPS':>8} {'Gate'}")
print("-" * 115)

# Sort candidates in logical order
candidate_order = [
    "CLASSIC-0_PureHSVHist_thr0.40",
    "BASELINE-0",
    "FFMPEG-1_scdet_thr8.0",
    "FFMPEG-1_scdet_thr12.0",
    "FFMPEG-1_scdet_thr17.5",
    "FFMPEG-1_scdet_thr22.0",
    "FFMPEG-1_scdet_thr30.0",
    "CLASSIC-1_AdaptiveDetector",
    "CLASSIC-2_ContentDetector",
    "CLASSIC-2b_ContentDetector_EdgeWeighted",
    "CLASSIC-3a_HashDetector",
    "CLASSIC-3b_HistogramDetector",
    "ML-1_TransNetV2_PyPI"
]

all_data = {}
for f in files:
    if f.name in ["bakeoff_combined_report.json", "ML-1_TransNetV2_AvailabilityCheck.json", "ML-1_TransNetV2_DependencyReport.json"]:
        continue
    d = json.loads(f.read_text(encoding="utf-8"))
    cid = d.get("candidate_id", f.stem)
    all_data[cid] = d

for cid in candidate_order:
    if cid not in all_data:
        continue
    data = all_data[cid]
    time_s = data.get("elapsed_seconds", 0.0)
    fps = data.get("processing_fps", 0.0)
    
    for win in ["0-180s", "0-300s"]:
        if win in data.get("windows", {}):
            w = data["windows"][win]["tol_250ms"]
            gate = "PASS" if (w["precision"] >= 0.95 and w["recall"] >= 0.90) else "FAIL"
            fps_str = f"{fps:.1f}x" if fps else "N/A"
            print(f"{cid:<40} {win:<8} {w['precision']:>6.3f} {w['recall']:>6.3f} {w['F1']:>6.3f} {w['TP']:>4d} {w['FP']:>4d} {w['FN']:>4d} {time_s:>6.1f}s {fps_str:>8}  {gate}")
    print("-" * 115)

print("=" * 115)

