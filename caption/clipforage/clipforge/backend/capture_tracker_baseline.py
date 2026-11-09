import asyncio
from pathlib import Path
import sys
import matplotlib.pyplot as plt

# Add backend to path
sys.path.insert(0, str(Path(r"d:\automation video clips\clipforge").absolute()))

from backend.services.reframe_engine import build_dynamic_crop_coords

async def main():
    video_path = Path("/app/uploads/user_video_h264.mp4")
    if not video_path.exists():
        print(f"Error: {video_path} not found.")
        return

    print(f"Analyzing {video_path}")
    
    # Typical params
    crop_w = 1080
    crop_h = 1920
    width = 1920
    height = 1080
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("Cannot open video")
        return
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    crop_h = height
    crop_w = int(height * 9 / 16)
    if crop_w > width:
        crop_w = width
        crop_h = int(width * 16 / 9)

    print(f"Video dims: {width}x{height}, Crop dims: {crop_w}x{crop_h}")

    # Let's run with standard 0.15 alpha as currently in code
    coords, frame_indices, fps, total_frames = await asyncio.to_thread(
        build_dynamic_crop_coords,
        video_path,
        crop_w,
        crop_h,
        width,
        height,
        alpha=0.15,
        sample_fps=5.0
    )
    
    # We also want raw trajectory to show the difference.
    # We will temporarily run it again but with alpha=1.0 to get raw coords
    raw_coords, _, _, _ = await asyncio.to_thread(
        build_dynamic_crop_coords,
        video_path,
        crop_w,
        crop_h,
        width,
        height,
        alpha=1.0,
        sample_fps=5.0
    )

    default_x = (width - crop_w) // 2
    face_frames = [c for c in raw_coords if c[0] != default_x]
    print(f"Frames with non-default tracking: {len(face_frames)} / {len(raw_coords)}")
    print(f"First 10 raw coords: {raw_coords[:10]}")
    
    x_vals_smooth = [c[0] for c in coords]
    y_vals_smooth = [c[1] for c in coords]
    
    x_vals_raw = [c[0] for c in raw_coords]
    y_vals_raw = [c[1] for c in raw_coords]

    print("--- Stats ---")
    
    def calc_stats(x_vals, name=""):
        diffs = [abs(x_vals[i] - x_vals[i-1]) for i in range(1, len(x_vals))]
        avg_move = sum(diffs)/len(diffs) if diffs else 0
        max_move = max(diffs) if diffs else 0
        reversals = 0
        for i in range(2, len(x_vals)):
            d1 = x_vals[i-1] - x_vals[i-2]
            d2 = x_vals[i] - x_vals[i-1]
            if d1 * d2 < 0:
                reversals += 1
        print(f"[{name}] Avg Move: {avg_move:.2f}px, Max Move: {max_move:.2f}px, Reversals: {reversals}")

    calc_stats(x_vals_raw, "Raw Trajectory")
    calc_stats(x_vals_smooth, "Smoothed Trajectory")
    
    # Plot
    plt.figure(figsize=(10, 5))
    plt.plot(frame_indices, x_vals_raw, label='Raw X', alpha=0.5, marker='o', markersize=3)
    plt.plot(frame_indices, x_vals_smooth, label='Smoothed X', linewidth=2)
    plt.title(f"Crop X Trajectory (alpha=0.15)")
    plt.xlabel("Frame Index")
    plt.ylabel("Crop X Coordinate")
    plt.legend()
    plt.grid(True)
    out_img = Path("/app/uploads/trajectory.png")
    plt.savefig(out_img)
    print(f"Saved plot to {out_img}")

if __name__ == "__main__":
    asyncio.run(main())
