import cv2
from pathlib import Path

raw_path = Path("/app/outputs/f7a1723b-7b93-48f6-bdd6-cc5f6cc68c9e/4fc77e0c-106a-478f-b1c9-2a08648c6d2e/raw.mp4")
vertical_path = Path("/app/outputs/f7a1723b-7b93-48f6-bdd6-cc5f6cc68c9e/4fc77e0c-106a-478f-b1c9-2a08648c6d2e/vertical.mp4")
out_dir = Path("/app/outputs")

def extract_frames():
    for name, path in [("raw", raw_path), ("vertical", vertical_path)]:
        if not path.exists():
            print(f"Error: {path} does not exist.")
            continue
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            print(f"Error: Could not open {path}")
            continue
        
        # Read the first frame
        ret, frame = cap.read()
        if ret:
            out_file = out_dir / f"mysterious_room_frame_{name}.jpg"
            cv2.imwrite(str(out_file), frame)
            print(f"Saved {name} frame to {out_file} (Resolution: {frame.shape[1]}x{frame.shape[0]})")
        else:
            print(f"Failed to read frame from {path}")
        cap.release()

if __name__ == "__main__":
    extract_frames()
