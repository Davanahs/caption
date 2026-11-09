import cv2
from backend.services.advanced_podcast_engine import detect_faces_in_frame

cap = cv2.VideoCapture("uploads/authentic_podcast_test.mp4")
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

for sec in range(5, 180, 5):
    cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
    ret, frame = cap.read()
    if not ret:
        break
    faces = detect_faces_in_frame(frame)
    if len(faces) == 1:
        f = faces[0]
        cx = f["x"] + f["width"] / 2.0
        print(f"{sec:3d}s: 1 face center_x={cx:.3f} w={f['width']:.3f} y={f['y']:.3f}")
    elif len(faces) == 2:
        cx1 = faces[0]["x"] + faces[0]["width"] / 2.0
        cx2 = faces[1]["x"] + faces[1]["width"] / 2.0
        print(f"{sec:3d}s: 2 faces center_x1={cx1:.3f}, center_x2={cx2:.3f}")
    else:
        print(f"{sec:3d}s: {len(faces)} faces")

cap.release()
