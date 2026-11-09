import cv2
import numpy as np
from pathlib import Path

video_path = Path("uploads/authentic_podcast_test.mp4")
assert video_path.exists()

cap = cv2.VideoCapture(str(video_path))
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
print(f"Video FPS: {fps}")

def get_frame_at(sec):
    frame_idx = int(round(sec * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret:
        return None
    return frame_idx, frame

# Inspect transition 1: around 2.0s - 3.8s
print("\n--- Inspecting Transition 1 (Title to Wide) ---")
for t in np.arange(2.0, 3.8, 0.2):
    f_idx, frame = get_frame_at(t)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_val = np.mean(gray)
    std_val = np.std(gray)
    print(f"t={t:5.2f}s (frame {f_idx:4d}): mean={mean_val:6.2f}, std={std_val:6.2f}")

# Inspect transition 2: around 16.5s - 18.0s
print("\n--- Inspecting Transition 2 (Wide to Solo A) ---")
for t in np.arange(16.8, 17.8, 0.1):
    f_idx, frame = get_frame_at(t)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    print(f"t={t:5.2f}s (frame {f_idx:4d}): mean={np.mean(gray):6.2f}")

cap.release()
