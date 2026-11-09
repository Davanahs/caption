import cv2
from backend.services.advanced_podcast_engine import detect_faces_in_frame

for ts in [2, 10, 25, 45, 58, 65, 80, 95, 110, 125, 145, 165, 175]:
    p = f"backend/benchmarks/audit_frames/frame_{ts:03d}s.jpg"
    img = cv2.imread(p)
    faces = detect_faces_in_frame(img)
    info = [f"x={f['x']:.3f}, w={f['width']:.3f}" for f in faces]
    print(f"ts={ts:3d}s: count={len(faces)} | positions={info}")
