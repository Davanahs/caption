import json
from pathlib import Path
from backend.services.advanced_podcast_engine import build_visibility_driven_schedule

with open("uploads/authentic_podcast_ground_truth.json") as f:
    gt = json.load(f)

shots = build_visibility_driven_schedule(
    video_path=Path("uploads/authentic_podcast_test.mp4"),
    region_a={"id": "speaker_a", "x": 0.08, "y": 0.15, "width": 0.35, "height": 0.70},
    region_b={"id": "speaker_b", "x": 0.55, "y": 0.15, "width": 0.35, "height": 0.70},
    ref_timestamp=10.0
)

for seg in gt["segments"]:
    st, et = seg["start"], seg["end"]
    overlapping = [s for s in shots if s["start_time"] < et and s["end_time"] > st]
    comps = [(round(s["start_time"],1), round(s["end_time"],1), s.get("composition"), s.get("active_track_id")) for s in overlapping]
    print(f"{seg['segment_id']:2d}: [{st:6.2f} - {et:6.2f}] GT={seg['active_speaker']} ({seg['cut_type']}) -> Sys={comps}")
