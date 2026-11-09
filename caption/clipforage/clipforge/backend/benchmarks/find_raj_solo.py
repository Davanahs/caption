import cv2
import numpy as np
from pathlib import Path

video_p = Path("uploads/authentic_podcast_test.mp4")
cap = cv2.VideoCapture(str(video_p))
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

# Raj Shamani wears a black t-shirt and has black hair, no glasses, no vest.
# Dr. Sweta Adatia wears a light pink polo shirt with a dark blue vest, glasses, greyish-black hair.
# In solo shots, Dr. Sweta is centered at x ~ 0.42-0.50.
# Let's check mean color in region of chest/shirt (norm_y 0.55 to 0.75, norm_x 0.40 to 0.60).
# For Raj (black shirt), mean BGR brightness will be very low (< 40).
# For Dr. Sweta (light shirt + blue vest), mean brightness is higher (> 70).

raj_solo_candidates = []
for sec in range(0, 180, 2):
    f_idx = int(round(sec * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
    ret, frame = cap.read()
    if not ret:
        continue
    h, w = frame.shape[:2]
    # Check if wide shot: look at left and right corners
    left_crop = frame[int(0.2*h):int(0.6*h), int(0.1*w):int(0.3*w)]
    right_crop = frame[int(0.2*h):int(0.6*h), int(0.6*w):int(0.8*w)]
    center_chest = frame[int(0.55*h):int(0.75*h), int(0.40*w):int(0.60*w)]
    
    chest_brightness = np.mean(center_chest)
    if chest_brightness < 45.0:
        raj_solo_candidates.append((sec, chest_brightness))

print("Potential Raj solo frames (black shirt at center):", raj_solo_candidates)
cap.release()
