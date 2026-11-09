import cv2
import os

def run_diagnostic():
    video_path = "/app/outputs/13ef4a42-a46e-470d-956a-abd5bdba5aa4/57b39c95-4247-4527-bd94-8566b0d750df/raw.mp4"

    if not os.path.exists(video_path):
        print(f"Error: video path {video_path} does not exist.")
        return

    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Video info: {width}x{height}, {fps} fps, {total_frames} total frames")

    # Load Haar Cascade face classifier
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    print(f"Loading cascade from: {cascade_path}")
    face_cascade = cv2.CascadeClassifier(cascade_path)

    if face_cascade.empty():
        print("Error: Could not load face cascade classifier.")
        return

    # Target vertical crop dimensions
    crop_w = int(height * 9 / 16)
    print(f"Target crop width: {crop_w}")

    # Sample frame indices (1 frame per second)
    sample_interval = max(1, int(fps))
    frame_indices = list(range(0, total_frames, sample_interval))

    face_x_coords = []

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Detect faces with basic scale factors
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(60, 60))
        
        for (x, y, w, h) in faces:
            # Calculate center X coordinate of the face
            face_center_x = x + w // 2
            face_x_coords.append(face_center_x)
            print(f"Frame {idx}: Face detected at x={x}, y={y}, w={w}, h={h} (center_x={face_center_x})")

    cap.release()

    if face_x_coords:
        # Compute median or average X coordinate of faces
        avg_face_x = sum(face_x_coords) / len(face_x_coords)
        # Calculate crop_x centering on the face
        crop_x = int(avg_face_x - crop_w // 2)
        # Clamp crop_x between 0 and width - crop_w
        crop_x_clamped = max(0, min(width - crop_w, crop_x))
        print(f"Average Face X: {avg_face_x:.1f}")
        print(f"Calculated Crop X (centered): {crop_x} -> Clamped: {crop_x_clamped}")
    else:
        default_crop_x = (width - crop_w) // 2
        print(f"No faces detected. Defaulting to center crop: {default_crop_x}")


if __name__ == "__main__":
    run_diagnostic()

