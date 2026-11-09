import json
from pathlib import Path
from backend.services.advanced_podcast_engine import build_visibility_driven_schedule

shots = build_visibility_driven_schedule(
    video_path=Path("uploads/authentic_podcast_test.mp4"),
    region_a={"id": "speaker_a", "x": 0.08, "y": 0.15, "width": 0.35, "height": 0.70},
    region_b={"id": "speaker_b", "x": 0.55, "y": 0.15, "width": 0.35, "height": 0.70},
    ref_timestamp=10.0
)

review_shots = [s for s in shots if s["start_time"] < 180.0 and (s.get("review_needed") or s.get("needs_manual_review"))]
print(f"Total review shots in 180s: {len(review_shots)}")
total_rev_dur = 0.0
for s in review_shots:
    dur = s.get("duration", s["end_time"] - s["start_time"])
    total_rev_dur += dur
    print(f"{s['start_time']:.2f}s - {s['end_time']:.2f}s ({dur:.2f}s): comp={s.get('composition')} track={s.get('active_track_id')}")

print(f"Total review duration: {total_rev_dur:.2f}s / 180s = {total_rev_dur/180.0:.4f}")
