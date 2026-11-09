import cv2
from pathlib import Path

video_path = Path("uploads/authentic_podcast_test.mp4")
assert video_path.exists()

out_dir = Path("backend/benchmarks/audit_frames")
out_dir.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(str(video_path))
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

timestamps = [2.0, 10.0, 25.0, 45.0, 58.0, 65.0, 80.0, 95.0, 110.0, 125.0, 145.0, 165.0, 175.0]

for ts in timestamps:
    frame_idx = int(round(ts * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if ret:
        fn = out_dir / f"frame_{int(ts):03d}s.jpg"
        cv2.imwrite(str(fn), frame)
        print(f"Saved {fn} (shape: {frame.shape})")

cap.release()
print("All frames extracted.")
