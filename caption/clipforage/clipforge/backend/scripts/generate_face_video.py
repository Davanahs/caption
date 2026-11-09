import cv2
import numpy as np
import urllib.request
import math

def main():
    # Download a face image
    url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    arr = np.asarray(bytearray(response.read()), dtype=np.uint8)
    face_img = cv2.imdecode(arr, -1)
    
    # Resize face to be a bit smaller
    face_img = cv2.resize(face_img, (300, 400))
    fh, fw = face_img.shape[:2]

    # Create video writer
    width, height = 1920, 1080
    fps = 25
    out = cv2.VideoWriter("/app/uploads/face_jitter.mp4", cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    frames = fps * 10 # 10 seconds
    
    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Calculate moving X position
        # Base X centered, with a sine wave movement + some random jitter
        base_x = (width - fw) // 2
        offset = int(math.sin(i * 0.1) * 300)
        jitter = int(np.random.normal(0, 10))
        
        x = base_x + offset + jitter
        y = (height - fh) // 2
        
        # Ensure bounds
        x = max(0, min(width - fw, x))
        
        frame[y:y+fh, x:x+fw] = face_img
        
        out.write(frame)
        
    out.release()
    print("Generated /app/uploads/face_jitter.mp4")

if __name__ == "__main__":
    main()
