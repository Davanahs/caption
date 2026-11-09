import json
import time
from pathlib import Path
from backend.services.advanced_podcast_engine import detect_camera_cuts

video_path = Path("uploads/authentic_podcast_test.mp4")
assert video_path.exists(), f"Video missing: {video_path}"

t0 = time.time()
shots = detect_camera_cuts(video_path)
elapsed = time.time() - t0

print(f"BASELINE-0 EXECUTION REPORT")
print(f"Video: {video_path}")
print(f"Elapsed time: {elapsed:.2f}s")
print(f"Total detected shots: {len(shots)}")
for i, (s, e) in enumerate(shots):
    print(f"Shot {i:2d}: [{s:6.2f} - {e:6.2f}] duration={e-s:5.2f}s")

output_report = {
    "detector": "BASELINE-0 (Current ClipForge detect_camera_cuts)",
    "video_path": str(video_path),
    "elapsed_seconds": round(elapsed, 3),
    "shot_count": len(shots),
    "shots": [{"index": i, "start": s, "end": e, "duration": round(e - s, 2)} for i, (s, e) in enumerate(shots)]
}

out_p = Path("backend/benchmarks/baseline_0_reproduction.json")
out_p.parent.mkdir(parents=True, exist_ok=True)
with open(out_p, "w", encoding="utf-8") as f:
    json.dump(output_report, f, indent=2)
print(f"Saved reproduction to {out_p}")
